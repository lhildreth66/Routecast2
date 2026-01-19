"""
Notification Service - Manages planned trips, push tokens, and smart delay alerts.

Handles:
- Registering planned trips for users
- Storing Expo push tokens
- Retrieving trips needing evaluation
- Recording sent notifications
- Pro gating and premium feature checks
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, List
from uuid import uuid4

from pymongo import MongoClient
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from .models import (
    PlannedTrip,
    PushToken,
    RouteWaypoint,
    SmartDelayNotification,
    AlertType,
)
from .expo_push import ExpoPushClient

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for managing notifications and smart delay alerts."""
    
    COOLDOWN_HOURS = 12  # Don't alert for same trip more than once per 12h
    
    def __init__(self, db: Database, expo_client: Optional[ExpoPushClient] = None):
        """
        Initialize notification service.
        
        Args:
            db: MongoDB database instance
            expo_client: Optional Expo push client (default: create new)
        """
        self.db = db
        self.expo_client = expo_client or ExpoPushClient()
        
        # Ensure indexes for efficient queries
        self._ensure_indexes()
    
    def _ensure_indexes(self):
        """Create MongoDB indexes for queries."""
        self.db.planned_trips.create_index("user_id")
        self.db.planned_trips.create_index("next_check_at")
        self.db.planned_trips.create_index("created_at")
        
        self.db.push_tokens.create_index("user_id", unique=False)
        self.db.push_tokens.create_index("token", unique=True, sparse=True)
        
        self.db.smart_delay_notifications.create_index("user_id")
        self.db.smart_delay_notifications.create_index("trip_id")
        self.db.smart_delay_notifications.create_index("sent_at")
    
    def register_planned_trip(
        self,
        user_id: str,
        route_waypoints: List[dict],  # [{"lat": x, "lon": y}, ...]
        planned_departure_local: datetime,
        user_timezone: str,
        destination_name: Optional[str] = None,
    ) -> str:
        """
        Register a planned trip for smart delay evaluation.
        
        Args:
            user_id: User ID
            route_waypoints: List of waypoints with lat/lon
            planned_departure_local: Planned departure in local time
            user_timezone: User's timezone (e.g., "America/Denver")
            destination_name: Optional destination name
        
        Returns:
            trip_id of registered trip
        
        Raises:
            ValueError: If inputs invalid
        """
        if not user_id or not route_waypoints or not user_timezone:
            raise ValueError("user_id, route_waypoints, and user_timezone required")
        
        if planned_departure_local.tzinfo is None:
            raise ValueError("planned_departure_local must include timezone info")
        
        trip_id = str(uuid4())
        
        # Convert waypoints to RouteWaypoint objects
        waypoints = [
            RouteWaypoint(
                latitude=wp.get("lat", wp.get("latitude")),
                longitude=wp.get("lon", wp.get("longitude")),
                name=wp.get("name"),
            )
            for wp in route_waypoints
        ]
        
        trip = PlannedTrip(
            user_id=user_id,
            trip_id=trip_id,
            route_waypoints=waypoints,
            planned_departure_local=planned_departure_local,
            user_timezone=user_timezone,
            destination_name=destination_name,
            next_check_at=datetime.now(timezone.utc),  # Check immediately
        )
        
        try:
            self.db.planned_trips.insert_one(trip.to_mongo_doc())
            logger.info(f"[PREMIUM] Registered planned trip {trip_id} for user {user_id}")
            return trip_id
        except Exception as e:
            logger.error(f"Failed to register trip: {e}")
            raise
    
    def register_push_token(
        self,
        user_id: str,
        token: str,
        device_id: Optional[str] = None,
    ) -> bool:
        """
        Register Expo push token for a user/device.
        
        Args:
            user_id: User ID
            token: Expo push token (starts with "ExponentPushToken[")
            device_id: Optional device identifier
        
        Returns:
            True if registered successfully
        
        Raises:
            ValueError: If token format invalid
        """
        if not token.startswith("ExponentPushToken["):
            raise ValueError("Invalid Expo push token format")
        
        push_token = PushToken(
            user_id=user_id,
            token=token,
            device_id=device_id,
        )
        
        try:
            # Upsert: update if exists, insert if not
            self.db.push_tokens.update_one(
                {"token": token},
                {"$set": push_token.to_mongo_doc()},
                upsert=True,
            )
            logger.info(f"[PREMIUM] Registered push token for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to register push token: {e}")
            raise
    
    def get_trips_needing_evaluation(
        self, hours_ahead: int = 6
    ) -> List[dict]:
        """
        Get trips that need smart delay evaluation.
        
        Retrieves trips where next_check_at <= now and departure within hours_ahead.
        
        Args:
            hours_ahead: Only evaluate trips departing within this many hours
        
        Returns:
            List of trip documents from MongoDB
        """
        now = datetime.now(timezone.utc)
        future = now + timedelta(hours=hours_ahead)
        
        trips = list(
            self.db.planned_trips.find({
                "next_check_at": {"$lte": now},
                "planned_departure_local": {"$lte": future},
            })
        )
        
        logger.info(f"Found {len(trips)} trips needing evaluation")
        return trips
    
    def get_push_token(self, user_id: str) -> Optional[str]:
        """
        Get the most recent push token for a user.
        
        Args:
            user_id: User ID
        
        Returns:
            Push token or None if not registered
        """
        doc = self.db.push_tokens.find_one(
            {"user_id": user_id},
            sort=[("registered_at", -1)],
        )
        return doc.get("token") if doc else None
    
    def should_send_alert(
        self, user_id: str, trip_id: str
    ) -> bool:
        """
        Check if enough time has passed to send another alert for this trip.
        
        Implements cooldown to prevent alert spam.
        
        Args:
            user_id: User ID
            trip_id: Trip ID
        
        Returns:
            True if alert should be sent (cooldown expired)
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=self.COOLDOWN_HOURS)
        
        recent = self.db.smart_delay_notifications.find_one({
            "user_id": user_id,
            "trip_id": trip_id,
            "sent_at": {"$gte": cutoff},
        })
        
        return recent is None
    
    def record_notification(
        self,
        user_id: str,
        trip_id: str,
        title: str,
        body: str,
        delay_hours: int,
        improvement_pct: float,
    ) -> str:
        """
        Record a smart delay notification in database.
        
        Args:
            user_id: User ID
            trip_id: Trip ID
            title: Notification title
            body: Notification body
            delay_hours: Recommended delay hours
            improvement_pct: Improvement percentage
        
        Returns:
            notification_id
        """
        notification = SmartDelayNotification(
            notification_id=str(uuid4()),
            user_id=user_id,
            trip_id=trip_id,
            alert_type=AlertType.SMART_DELAY,
            title=title,
            body=body,
            delay_hours=delay_hours,
            improvement_pct=improvement_pct,
        )
        
        try:
            self.db.smart_delay_notifications.insert_one(notification.to_mongo_doc())
            logger.info(
                f"[PREMIUM] Recorded notification {notification.notification_id} "
                f"for trip {trip_id}"
            )
            return notification.notification_id
        except Exception as e:
            logger.error(f"Failed to record notification: {e}")
            raise
    
    def update_trip_check_time(
        self, trip_id: str, next_check_at: datetime
    ):
        """
        Update next_check_at for a trip.
        
        Args:
            trip_id: Trip ID
            next_check_at: When to check next
        """
        self.db.planned_trips.update_one(
            {"trip_id": trip_id},
            {"$set": {"next_check_at": next_check_at}},
        )
    
    def update_trip_alert_time(self, trip_id: str):
        """
        Update last_alert_at to current time (for cooldown).
        
        Args:
            trip_id: Trip ID
        """
        self.db.planned_trips.update_one(
            {"trip_id": trip_id},
            {"$set": {"last_alert_at": datetime.now(timezone.utc)}},
        )
    
    def close(self):
        """Close resources."""
        if self.expo_client:
            self.expo_client.close()
