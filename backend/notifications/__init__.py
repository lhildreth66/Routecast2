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


def _remove_token(token: str) -> None:
    """Remove a token from both in-memory cache and Mongo (if available)."""
    _in_memory_tokens.discard(token)
    if _db is not None:
        try:
            _db.push_tokens.delete_one({"push_token": token})
        except Exception as exc:
            logger.warning("[notifications] Failed to delete token %s: %s", token, exc)


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
    "router",
]
