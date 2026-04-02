"""
Push Notification Router for RouteCast
Handles push token registration and route monitoring.
"""

from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel, Field
from typing import Optional, Dict, List
from datetime import datetime
import logging

from services.push_notification_service import PushNotificationService, RouteMonitorService
from routers.auth import get_current_user_optional, get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Push Notifications"])


# Request/Response Models
class RegisterTokenRequest(BaseModel):
    token: str  # Expo push token
    platform: str = "unknown"  # ios, android, web
    device_info: Optional[Dict] = None


class CreateMonitorRequest(BaseModel):
    route_id: str
    origin: str
    destination: str
    departure_time: datetime
    alert_preferences: Optional[Dict] = None


class MonitorResponse(BaseModel):
    id: str
    route_id: str
    origin: str
    destination: str
    departure_time: datetime
    status: str
    alerts_sent: int


# Dependency to get services
async def get_push_service(db=None):
    from server import db as app_db
    return PushNotificationService(db or app_db)


async def get_monitor_service(db=None):
    from server import db as app_db
    push_service = PushNotificationService(db or app_db)
    return RouteMonitorService(db or app_db, push_service)


@router.post("/tokens")
async def register_push_token(
    request: RegisterTokenRequest,
    user: Optional[dict] = Depends(get_current_user_optional)
):
    """
    Register a push notification token.
    
    Works for both authenticated and anonymous users.
    Anonymous users get a generated ID.
    """
    from server import db
    
    user_id = user.get("sub") if user else f"anon_{request.token[-12:]}"
    
    push_service = PushNotificationService(db)
    success = await push_service.register_push_token(
        user_id=user_id,
        push_token=request.token,
        platform=request.platform,
        device_info=request.device_info
    )
    
    if success:
        return {"success": True, "user_id": user_id}
    else:
        raise HTTPException(status_code=400, detail="Failed to register push token")


@router.delete("/tokens")
async def unregister_push_token(
    token: str,
    user: dict = Depends(get_current_user)
):
    """Unregister a push token (requires auth)."""
    from server import db
    
    push_service = PushNotificationService(db)
    success = await push_service.unregister_push_token(
        user_id=user["sub"],
        push_token=token
    )
    
    return {"success": success}



class PushSettingsRequest(BaseModel):
    push_enabled: bool
    push_token: Optional[str] = None
    platform: str = "unknown"


def _redact_endpoint(endpoint: Optional[str]) -> str:
    if not endpoint:
        return ""
    if len(endpoint) <= 10:
        return endpoint
    return f"{endpoint[:16]}…{endpoint[-6:]}"


class WebPushSubscription(BaseModel):
    """Browser Web Push subscription payload (aligned with PushSubscription JSON)."""

    endpoint: str
    expirationTime: Optional[float] = Field(None, alias="expirationTime")
    keys: Dict[str, str]
    user_agent: Optional[str] = None
    platform: Optional[str] = None
    title: Optional[str] = None  # optional label from client UI


@router.get("/settings")
async def get_push_settings(
    user: dict = Depends(get_current_user)
):
    """Get push notification settings for current user."""
    from server import db
    
    user_record = await db.users.find_one(
        {"user_id": user["sub"]},
        {"push_enabled": 1, "push_token": 1, "push_platform": 1}
    )

    web_sub = await db.web_push_subscriptions.find_one({"user_id": user["sub"]})
    web_subscribed = bool(web_sub and web_sub.get("endpoint"))
    web_endpoint = _redact_endpoint(web_sub.get("endpoint") if web_sub else None)
    
    if not user_record:
        return {
            "push_enabled": False,
            "push_token": None,
            "platform": None,
            "web_subscribed": web_subscribed,
            "web_endpoint": web_endpoint,
        }
    
    return {
        "push_enabled": user_record.get("push_enabled", False),
        "push_token": user_record.get("push_token"),
        "platform": user_record.get("push_platform"),
        "web_subscribed": web_subscribed,
        "web_endpoint": web_endpoint,
    }


@router.post("/settings")
async def update_push_settings(
    request: PushSettingsRequest,
    user: dict = Depends(get_current_user)
):
    """Update push notification settings for current user."""
    from server import db
    
    update_data = {
        "push_enabled": request.push_enabled,
        "push_platform": request.platform
    }
    
    if request.push_token:
        update_data["push_token"] = request.push_token
    
    # If disabling, also register/unregister token
    push_service = PushNotificationService(db)
    
    if request.push_enabled and request.push_token:
        saved = await push_service.register_push_token(
            user_id=user["sub"],
            push_token=request.push_token,
            platform=request.platform
        )
        if not saved:
            raise HTTPException(
                status_code=400,
                detail="Push token registration failed. Confirm notifications are enabled and try again.",
            )
    elif not request.push_enabled and request.push_token:
        removed = await push_service.unregister_push_token(
            user_id=user["sub"],
            push_token=request.push_token
        )
        if not removed:
            raise HTTPException(
                status_code=400,
                detail="Could not disable push notifications right now. Please try again.",
            )
    
    await db.users.update_one(
        {"user_id": user["sub"]},
        {"$set": update_data}
    )
    
    return {
        "success": True,
        "push_enabled": request.push_enabled
    }


@router.get("/web-subscription")
async def get_web_push_subscription(user: dict = Depends(get_current_user)):
    """Return the stored Web Push subscription for the authenticated user (redacted endpoint)."""
    from server import db

    doc = await db.web_push_subscriptions.find_one({"user_id": user["sub"]})
    if not doc:
        return {"web_subscribed": False, "subscription": None}

    redacted = _redact_endpoint(doc.get("endpoint"))
    logger.info(
        "[push:web] subscription_lookup user=%s endpoint=%s",
        user["sub"],
        redacted,
    )

    doc.pop("_id", None)
    doc["endpoint"] = redacted
    return {"web_subscribed": True, "subscription": doc}


@router.post("/web-subscription")
async def save_web_push_subscription(
    subscription: WebPushSubscription,
    user_agent: Optional[str] = Header(None),
    user: dict = Depends(get_current_user),
):
    """Save or update a browser Web Push subscription for the current user."""
    from server import db

    now = datetime.utcnow()
    endpoint = subscription.endpoint
    if not endpoint or not subscription.keys.get("p256dh") or not subscription.keys.get("auth"):
        raise HTTPException(status_code=400, detail="Invalid Web Push subscription payload")

    record = {
        "user_id": user["sub"],
        "endpoint": endpoint,
        "keys": subscription.keys,
        "expirationTime": subscription.expirationTime,
        "user_agent": subscription.user_agent or user_agent,
        "platform": subscription.platform,
        "title": subscription.title,
        "updated_at": now,
    }

    result = await db.web_push_subscriptions.update_one(
        {"user_id": user["sub"]},
        {
            "$set": record,
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
    )

    logger.info(
        "[push:web] subscription_saved user=%s endpoint=%s matched=%s modified=%s upserted=%s",
        user["sub"],
        _redact_endpoint(endpoint),
        result.matched_count,
        result.modified_count,
        bool(getattr(result, "upserted_id", None)),
    )

    return {"success": True, "web_subscribed": True, "endpoint": _redact_endpoint(endpoint)}


@router.delete("/web-subscription")
async def delete_web_push_subscription(user: dict = Depends(get_current_user)):
    """Delete the stored Web Push subscription for the authenticated user."""
    from server import db

    result = await db.web_push_subscriptions.delete_one({"user_id": user["sub"]})
    logger.info(
        "[push:web] subscription_deleted user=%s deleted=%s",
        user["sub"],
        result.deleted_count,
    )
    return {"success": True, "web_subscribed": False, "deleted": result.deleted_count}



@router.post("/monitors", response_model=dict)
async def create_route_monitor(
    request: CreateMonitorRequest,
    user: dict = Depends(get_current_user)
):
    """
    Create a route weather monitor.
    
    Premium feature - checks user subscription status.
    """
    from server import db
    
    # Fetch full user from database to check subscription
    user_record = await db.users.find_one({"user_id": user["sub"]})
    
    if not user_record:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check subscription status
    sub_status = user_record.get("subscription_status", "inactive")
    if sub_status not in ["active", "trialing"]:
        raise HTTPException(
            status_code=403,
            detail="Route monitoring requires a premium subscription"
        )
    
    # Check user's monitor limit
    push_service = PushNotificationService(db)
    monitor_service = RouteMonitorService(db, push_service)
    existing = await monitor_service.get_user_monitors(user["sub"])
    
    # Free trial: 3 monitors, Premium: 10 monitors
    max_monitors = 3 if sub_status == "trialing" else 10
    
    if len(existing) >= max_monitors:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum of {max_monitors} active monitors allowed"
        )
    
    # Create the monitor
    monitor_id = await monitor_service.create_route_monitor(
        user_id=user["sub"],
        route_id=request.route_id,
        origin=request.origin,
        destination=request.destination,
        departure_time=request.departure_time,
        alert_preferences=request.alert_preferences
    )
    
    return {
        "success": True,
        "monitor_id": monitor_id,
        "message": "Route monitor created. You'll receive alerts starting 24 hours before departure."
    }


@router.get("/monitors")
async def list_route_monitors(
    user: dict = Depends(get_current_user)
):
    """List all active route monitors for the current user."""
    from server import db
    
    push_service = PushNotificationService(db)
    monitor_service = RouteMonitorService(db, push_service)
    
    monitors = await monitor_service.get_user_monitors(user["sub"])
    
    return {
        "monitors": monitors,
        "total": len(monitors)
    }


@router.delete("/monitors/{monitor_id}")
async def cancel_route_monitor(
    monitor_id: str,
    user: dict = Depends(get_current_user)
):
    """Cancel a route monitor."""
    from server import db
    
    push_service = PushNotificationService(db)
    monitor_service = RouteMonitorService(db, push_service)
    
    success = await monitor_service.cancel_monitor(
        user_id=user["sub"],
        monitor_id=monitor_id
    )
    
    if success:
        return {"success": True, "message": "Monitor cancelled"}
    else:
        raise HTTPException(status_code=404, detail="Monitor not found")


@router.post("/test")
async def send_test_notification(
    user: dict = Depends(get_current_user)
):
    """Send a test notification to the current user's devices."""
    from server import db
    
    push_service = PushNotificationService(db)
    
    result = await push_service.send_to_user(
        user_id=user["sub"],
        title="Test Notification",
        body="This is a test notification from RouteCast!",
        data={"type": "test"},
        channel_id="general"
    )
    
    return result
