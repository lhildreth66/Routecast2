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
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from pymongo import MongoClient
from exponent_server_sdk import PushClient, PushMessage

from .smart_delay import SmartDelayOptimizer, BestDelayResult
from .models import PlannedTrip, PushToken, SmartDelayNotification
from .expo_push import ExpoPushClient
from .service import NotificationService

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


class ExpoRegisterRequest(BaseModel):
    """Request payload for saving Expo push tokens."""

    expoPushToken: str
    userId: Optional[str] = None
    enabled: bool = True


class SendNotificationRequest(BaseModel):
    title: Optional[str] = "🚛 Routecast Test Alert"
    body: Optional[str] = "Push notifications are working!"
    data: Optional[Dict[str, Any]] = None


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
                    "badge": 1,
                    "priority": "high",
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
    # Gather tokens from memory and DB
    tokens = set(_in_memory_tokens)
    tokens.update(_load_tokens_from_db())

    if not tokens:
        raise HTTPException(status_code=400, detail="No Expo push tokens registered")

    messages = [
        PushMessage(
            to=token,
            sound="default",
            title=request.title,
            body=request.body,
            data=request.data or {"type": "test"},
        )
        for token in tokens
    ]

    client = PushClient()
    try:
        # expo-server-sdk is synchronous; run in thread if needed
        responses = client.publish_multiple(messages)
    except Exception as exc:
        logger.error("Error sending notifications: %s", exc)
        raise HTTPException(status_code=500, detail=f"Error sending notifications: {exc}")

    tickets_raw = jsonable_encoder(responses)

    def _flatten(items):
        for item in items:
            if isinstance(item, list):
                yield from _flatten(item)
            else:
                yield item

    tickets_flat = list(_flatten(tickets_raw))
    success = sum(1 for resp in tickets_flat if isinstance(resp, dict) and resp.get("status") == "ok")

    for ticket in tickets_flat:
        if not isinstance(ticket, dict):
            logger.error("[notifications] unexpected ticket type", extra={"ticket": ticket})
            continue
        if ticket.get("status") != "ok":
            logger.error("[notifications] push ticket error", extra={"ticket": ticket})

    return {
        "attempted": len(messages),
        "success": success,
        "tickets": tickets_flat,
    }


__all__ = [
    "SmartDelayOptimizer",
    "BestDelayResult",
    "PlannedTrip",
    "PushToken",
    "SmartDelayNotification",
    "ExpoPushClient",
    "NotificationService",
    "router",
]
