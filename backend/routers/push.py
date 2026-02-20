"""
Push Notification Router for RouteCast
Handles push token registration and route monitoring.
"""

from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel
from typing import Optional, Dict, List
from datetime import datetime
import logging

from services.push_notification_service import PushNotificationService, RouteMonitorService
from routers.auth import get_current_user_optional, get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/push", tags=["Push Notifications"])


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
        "message": f"Route monitor created. You'll receive alerts starting 24 hours before departure."
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
