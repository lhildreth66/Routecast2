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
from typing import Dict, Any, Optional

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from pymongo import MongoClient

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


class PushTokenRequest(BaseModel):
    """Request payload for saving Expo push tokens."""

    push_token: Optional[str] = None
    token: Optional[str] = None
    platform: Optional[str] = None
    enabled: bool = True


class TestNotificationRequest(BaseModel):
    push_token: str


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


@router.post("/register")
async def register_push_token(request: PushTokenRequest):
    """Register or update a user's push notification token."""
    token = request.push_token or request.token
    if not token:
        raise HTTPException(status_code=400, detail="Missing token")

    try:
        if _db is not None:
            _db.push_tokens.update_one(
                {"push_token": token},
                {
                    "$set": {
                        "push_token": token,
                        "platform": request.platform,
                        "enabled": request.enabled,
                        "created_at": datetime.utcnow(),
                        "last_used": datetime.utcnow(),
                    }
                },
                upsert=True,
            )
        else:
            logger.warning("[notifications] Database not available, token not persisted")

        return {
            "ok": True,
            "token": token[:20] + "...",
        }
    except Exception as exc:
        logger.error("Error registering push token: %s", exc)
        raise HTTPException(status_code=500, detail=f"Error registering token: {exc}")


@router.post("/test")
async def send_test_notification(request: TestNotificationRequest):
    """Send a test push notification to verify setup."""
    try:
        success = await send_expo_notification(
            push_token=request.push_token,
            title="🚛 Routecast Test Alert",
            body="Push notifications are working! You'll receive weather alerts for your routes.",
            data={
                "type": "test",
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

        if success:
            if _db is not None:
                _db.push_tokens.update_one(
                    {"push_token": request.push_token},
                    {"$set": {"last_used": datetime.utcnow()}},
                    upsert=True,
                )

            return {
                "success": True,
                "message": "Test notification sent successfully",
            }
        else:
            return {
                "success": False,
                "message": "Failed to send notification via Expo service",
            }
    except Exception as exc:
        logger.error("Error sending test notification: %s", exc)
        return {
            "success": False,
            "message": f"Error sending test notification: {exc}",
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
