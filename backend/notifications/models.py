"""
Notification domain models and schemas for Task E1.

Defines data structures for planned trips, push tokens, and smart delay alerts.
"""

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Optional, List
from enum import Enum


class AlertType(str, Enum):
    """Types of notifications."""
    SMART_DELAY = "smart_delay"
    HAZARD_ALERT = "hazard_alert"


@dataclass(frozen=True)
class RouteWaypoint:
    """A waypoint along the planned route."""
    latitude: float
    longitude: float
    name: Optional[str] = None


@dataclass(frozen=True)
class PlannedTrip:
    """A user's planned trip for smart delay evaluation."""
    user_id: str
    trip_id: str
    route_waypoints: List[RouteWaypoint]  # Start → end waypoints
    planned_departure_local: datetime  # Local time of planned departure
    user_timezone: str  # e.g., "America/Denver"
    destination_name: Optional[str] = None
    created_at: datetime = None
    next_check_at: Optional[datetime] = None
    last_alert_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.created_at is None:
            object.__setattr__(self, 'created_at', datetime.now(timezone.utc))
    
    def to_mongo_doc(self) -> dict:
        """Convert to MongoDB document."""
        doc = asdict(self)
        doc['route_waypoints'] = [
            {'latitude': wp.latitude, 'longitude': wp.longitude, 'name': wp.name}
            for wp in self.route_waypoints
        ]
        return doc


@dataclass(frozen=True)
class PushToken:
    """Expo push token for a user/device."""
    user_id: str
    token: str
    device_id: Optional[str] = None
    registered_at: datetime = None
    last_used_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.registered_at is None:
            object.__setattr__(self, 'registered_at', datetime.now(timezone.utc))
    
    def to_mongo_doc(self) -> dict:
        """Convert to MongoDB document."""
        return asdict(self)


@dataclass(frozen=True)
class SmartDelayNotification:
    """A smart delay notification sent to user."""
    notification_id: str
    user_id: str
    trip_id: str
    alert_type: AlertType
    title: str
    body: str
    delay_hours: int
    improvement_pct: float
    sent_at: datetime = None
    
    def __post_init__(self):
        if self.sent_at is None:
            object.__setattr__(self, 'sent_at', datetime.now(timezone.utc))
    
    def to_mongo_doc(self) -> dict:
        """Convert to MongoDB document."""
        doc = asdict(self)
        doc['alert_type'] = self.alert_type.value
        return doc
