"""
Notifications package - Task E1: Smart Departure & Hazard Alerts

Submodules:
- smart_delay: Pure domain logic for delay optimization
- models: Data models for trips, tokens, notifications
- expo_push: Expo push notification client
- service: Notification service with database integration
"""

from backend.notifications.smart_delay import SmartDelayOptimizer, BestDelayResult
from backend.notifications.models import PlannedTrip, PushToken, SmartDelayNotification
from backend.notifications.expo_push import ExpoPushClient
from backend.notifications.service import NotificationService

__all__ = [
    "SmartDelayOptimizer",
    "BestDelayResult",
    "PlannedTrip",
    "PushToken",
    "SmartDelayNotification",
    "ExpoPushClient",
    "NotificationService",
]
