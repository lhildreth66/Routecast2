"""
Notifications package - Task E1: Smart Departure & Hazard Alerts

Submodules:
- smart_delay: Pure domain logic for delay optimization
- models: Data models for trips, tokens, notifications
- expo_push: Expo push notification client
- service: Notification service with database integration
"""

from .smart_delay import SmartDelayOptimizer, BestDelayResult
from .models import PlannedTrip, PushToken, SmartDelayNotification
from .expo_push import ExpoPushClient
from .service import NotificationService

__all__ = [
    "SmartDelayOptimizer",
    "BestDelayResult",
    "PlannedTrip",
    "PushToken",
    "SmartDelayNotification",
    "ExpoPushClient",
    "NotificationService",
]
