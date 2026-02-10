"""
Notifications package - Task E1: Smart Departure & Hazard Alerts

Submodules:
- smart_delay: Pure domain logic for delay optimization
- models: Data models for trips, tokens, notifications
- expo_push: Expo push notification client
- service: Notification service with database integration

API router:
- health, register, and test push endpoints mounted under /api/notifications
"""

import logging
import os
from datetime import datetime
from typing import Dict, Any, Optional, List, Set

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, ConfigDict
from pymongo import MongoClient
from exponent_server_sdk import PushClient, PushMessage

from .smart_delay import SmartDelayOptimizer, BestDelayResult
from .models import PlannedTrip, PushToken, SmartDelayNotification
from .expo_push import ExpoPushClient
from .service import NotificationService
from .route_alerts import RouteAlertService

logger = logging.getLogger(__name__)

# Shared router for notifications endpoints
router = APIRouter()

# Lightweight sync Mongo connection for token persistence
_mongo_url = os.environ.get("MONGODB_URI") or os.environ.get("MONGO_URL")
_db_name = os.environ.get("DB_NAME", "routecast_test")
_db = None
if _mongo_url:
    try:
        _sync_client = MongoClient(_mongo_url, serverSelectionTimeoutMS=5000)
        _sync_client.admin.command("ping")
        _db = _sync_client[_db_name]
        logger.info("[notifications] Mongo connected db=%s", _db_name)
    except Exception as exc:
        logger.warning("[notifications] Mongo init failed: %s", exc)
else:
    logger.warning("[notifications] Mongo URL missing; push tokens not persisted")

# In-memory token cache as fallback when DB is unavailable
_in_memory_tokens: Set[str] = set()

# Critical alert service (lazy init)
_route_alert_service: Optional[RouteAlertService] = None


def get_route_alert_service() -> RouteAlertService:
    """Shared accessor for the critical route alert service."""
    global _route_alert_service
    if _db is None:
        raise HTTPException(status_code=500, detail="MongoDB not configured")
    if _route_alert_service is None:
        _route_alert_service = RouteAlertService(_db)
    return _route_alert_service


class ExpoRegisterRequest(BaseModel):
    """Request payload for saving Expo push tokens."""

    expoPushToken: str
    userId: Optional[str] = None
    enabled: bool = True


class SendNotificationRequest(BaseModel):
    title: Optional[str] = "🚛 Routecast Test Alert"
    body: Optional[str] = "Push notifications are working!"
    data: Optional[Dict[str, Any]] = None



class RoutePoint(BaseModel):
    lat: float
    lon: float
    name: Optional[str] = None


class StartRouteMonitorRequest(BaseModel):
    """Accept both camelCase and snake_case route monitor payloads."""

    model_config = ConfigDict(populate_by_name=True)

    user_id: Optional[str] = Field(None, alias="userId")
    push_token: Optional[str] = Field(None, alias="pushToken")
    expo_push_token: Optional[str] = Field(None, alias="expoPushToken")
    route_id: str = Field(..., alias="routeId")
    route: Optional[List[RoutePoint]] = None
    route_points: Optional[List[RoutePoint]] = Field(None, alias="routePoints")
    sample_points: Optional[List[RoutePoint]] = Field(None, alias="samplePoints")
    waypoints: Optional[List[Dict[str, Any]]] = None
    route_polyline: Optional[str] = Field(None, alias="routePolyline")
    sample_miles: float = Field(10.0, alias="sampleMiles")
    max_points: int = Field(25, alias="maxPoints")


class StopRouteMonitorRequest(BaseModel):
    userId: Optional[str] = None
    monitorId: Optional[str] = None
    pushToken: Optional[str] = None


async def send_expo_notification(push_token: str, title: str, body: str, data: Dict[str, Any] = None) -> bool:
    """Send a push notification via Expo Push Service."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://exp.host/--/api/v2/push/send",
                json={
                    "to": push_token,
                    "sound": "default",
                    "title": title,
                    "body": body,
                    "data": data or {},
                    "priority": "high",
                    "channelId": "weather-alerts",
                    "badge": 1,
                },
                headers={"Accept": "application/json", "Accept-Encoding": "gzip, deflate"},
            )
            return response.status_code == 200
    except Exception as exc:
        logger.error("Error sending Expo notification: %s", exc)
        return False


@router.get("/health")
async def notifications_health():
    """Simple health check for notifications endpoints."""
    return {"ok": True}


def _store_token(token: str, user_id: Optional[str], enabled: bool) -> None:
    """Persist token to Mongo when available and cache in memory."""
    _in_memory_tokens.add(token)
    if _db is not None:
        _db.push_tokens.update_one(
            {"push_token": token},
            {
                "$set": {
                    "push_token": token,
                    "user_id": user_id,
                    "enabled": enabled,
                    "created_at": datetime.utcnow(),
                    "last_used": datetime.utcnow(),
                }
            },
            upsert=True,
        )


def _load_tokens_from_db() -> List[str]:
    if _db is None:
        return []
    try:
        docs = _db.push_tokens.find({"enabled": True}, {"push_token": 1})
        return [d.get("push_token") for d in docs if d.get("push_token")]
    except Exception as exc:
        logger.warning("[notifications] Failed to load tokens from DB: %s", exc)
        return []


def _remove_token(token: str) -> None:
    """Remove a token from both in-memory cache and Mongo (if available)."""
    _in_memory_tokens.discard(token)
    if _db is not None:
        try:
            _db.push_tokens.delete_one({"push_token": token})
        except Exception as exc:
            logger.warning("[notifications] Failed to delete token %s: %s", token, exc)


@router.post("/route-monitor/start")
async def start_route_monitor(request: StartRouteMonitorRequest):
    """Start (or replace) a critical route monitor for a user/token."""
    from .route_alerts import sample_route_points, _compute_bbox, _decode_polyline_safe  # local import to avoid cycles

    service = get_route_alert_service()

    # Normalize tokens and user
    push_token = request.push_token or request.expo_push_token
    user_id = request.user_id or push_token

    if not push_token:
        raise HTTPException(status_code=400, detail="push_token required")

    # Collect candidate points
    route_points: List[Dict[str, float]] = []
    if request.route:
        route_points.extend([{"lat": p.lat, "lon": p.lon, "name": p.name} for p in request.route])
    if request.route_points:
        route_points.extend([{"lat": p.lat, "lon": p.lon, "name": p.name} for p in request.route_points])
    if request.waypoints:
        for wp in request.waypoints:
            lat = wp.get("lat")
            lon = wp.get("lon")
            if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
                route_points.append({"lat": float(lat), "lon": float(lon)})

    polyline_points = _decode_polyline_safe(request.route_polyline)
    sample_points_payload = []
    if request.sample_points:
        sample_points_payload = [
            {"lat": p.lat, "lon": p.lon}
            for p in request.sample_points
            if p.lat is not None and p.lon is not None
        ]

    # Prefer provided polyline, then provided samples, then provided route points
    if not route_points and polyline_points:
        route_points = polyline_points
    if not sample_points_payload and route_points:
        sample_points_payload = []  # will be generated below

    # Finalize geometry
    sample_miles = float(os.environ.get("ROUTE_ALERTS_SAMPLING_MILES", request.sample_miles))
    max_points = int(os.environ.get("ROUTE_ALERTS_MAX_POINTS", request.max_points))

    # Use provided samples when present, otherwise sample from route geometry
    sample_points: List[Dict[str, float]] = sample_points_payload
    if not sample_points:
        if len(route_points) >= 2:
            sample_points = sample_route_points(route_points, sample_miles=sample_miles, max_points=max_points)
        else:
            raise HTTPException(status_code=400, detail="route geometry required")

    bbox = _compute_bbox(sample_points) or _compute_bbox(route_points)
    if not bbox or not sample_points:
        raise HTTPException(status_code=400, detail="route geometry required")

    try:
        payload = service.start_monitor(
            user_id=user_id,
            push_token=push_token,
            route_id=request.route_id,
            route_points=route_points,
            sample_points=sample_points,
            route_polyline=request.route_polyline,
            bbox=bbox,
            sample_miles=sample_miles,
            max_points=max_points,
        )
        return {
            "ok": True,
            "monitor_id": payload["monitor_id"],
            "points": len(payload["sample_points"]),
            "route_signature": payload["route_signature"],
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to start route monitor: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to start monitor")


@router.post("/route-monitor/stop")
async def stop_route_monitor(request: StopRouteMonitorRequest):
    """Stop active monitors scoped by monitorId, userId, or pushToken."""
    service = get_route_alert_service()
    try:
        updated = service.stop_monitor(
            user_id=request.userId,
            monitor_id=request.monitorId,
            push_token=request.pushToken,
        )
        return {"stopped": updated}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to stop route monitor: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to stop monitor")


@router.post("/register")
async def register_push_token(request: ExpoRegisterRequest):
    """Register or update a user's Expo push token."""
    token = request.expoPushToken
    if not token.startswith("ExponentPushToken"):
        raise HTTPException(status_code=400, detail="Invalid Expo push token")

    try:
        _store_token(token, request.userId, request.enabled)
        return {
            "ok": True,
            "token": token[:20] + "...",
        }
    except Exception as exc:
        logger.error("Error registering push token: %s", exc)
        raise HTTPException(status_code=500, detail=f"Error registering token: {exc}")


@router.post("/send")
async def send_push_notification(request: SendNotificationRequest):
    """Send a test push notification to all stored tokens."""
    # Gather tokens from memory and DB, drop blanks and known placeholder
    tokens = {t for t in _in_memory_tokens if t and t != "ExponentPushToken[fake-token]"}
    tokens.update(t for t in _load_tokens_from_db() if t and t != "ExponentPushToken[fake-token]")

    if not tokens:
        raise HTTPException(status_code=400, detail="No tokens registered")

    tokens_list = list(tokens)

    messages = [
        PushMessage(
            to=token,
            title=request.title,
            body=request.body,
            sound="default",
            channel_id="default",
            data=request.data or {"type": "test"},
        )
        for token in tokens_list
    ]

    client = PushClient()
    try:
        # expo-server-sdk is synchronous; run in thread if needed
        responses = client.publish_multiple(messages)
    except Exception as exc:
        logger.error("Error sending notifications: %s", exc)
        raise HTTPException(status_code=500, detail=f"Error sending notifications: {exc}")

    tickets: List[Dict[str, Any]] = []
    success = 0

    for token, resp in zip(tokens_list, responses):
        ticket = {
            "to": token,
            "status": getattr(resp, "status", None),
            "id": getattr(resp, "id", None),
            "message": getattr(resp, "message", None),
            "details": getattr(resp, "details", None),
        }

        if ticket.get("status") == "ok":
            success += 1
        else:
            logger.error("[notifications] push ticket error", extra={"ticket": ticket})
            details = ticket.get("details") or {}
            if details.get("error") == "DeviceNotRegistered":
                _remove_token(token)

        tickets.append(ticket)

    return {
        "attempted": len(tokens_list),
        "success": success,
        "tickets": tickets,
    }


__all__ = [
    "SmartDelayOptimizer",
    "BestDelayResult",
    "PlannedTrip",
    "PushToken",
    "SmartDelayNotification",
    "ExpoPushClient",
    "NotificationService",
    "RouteAlertService",
    "router",
]
