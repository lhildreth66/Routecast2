"""
Smart Delay Notification Scheduler

Periodic job that:
1. Finds trips needing evaluation
2. Fetches hourly forecast for route
3. Computes departure risks
4. Sends push notifications if delay improves safety

Runs every 30 minutes via APScheduler.

Pro-only feature: Only evaluates/sends alerts for Premium users.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from backend.notifications.smart_delay import SmartDelayOptimizer
from backend.notifications.service import NotificationService
from backend.notifications.expo_push import ExpoPushClient
from backend.providers.weather_provider import WeatherProvider
from backend.billing.premium_service import PremiumService

logger = logging.getLogger(__name__)


class SmartDelayScheduler:
    """Scheduler for smart delay evaluation and notifications."""
    
    # Improvement threshold: only recommend delay if improvement >= this %
    MIN_IMPROVEMENT_PCT = 15
    
    # Forecast window: evaluate delays up to this many hours ahead
    DELAY_WINDOW_HOURS = 3
    
    # Schedule interval: run job every N minutes
    SCHEDULE_INTERVAL_MINUTES = 30
    
    def __init__(
        self,
        notification_service: NotificationService,
        weather_provider: WeatherProvider,
        premium_service: PremiumService,
    ):
        """
        Initialize scheduler.
        
        Args:
            notification_service: NotificationService instance
            weather_provider: Weather provider for forecasts
            premium_service: Premium/subscription validator
        """
        self.notification_service = notification_service
        self.weather_provider = weather_provider
        self.premium_service = premium_service
    
    def evaluate_and_notify(self):
        """
        Evaluate all pending trips and send smart delay notifications.
        
        Called periodically by APScheduler.
        """
        logger.info("[PREMIUM] Starting smart delay evaluation job")
        
        try:
            trips = self.notification_service.get_trips_needing_evaluation(
                hours_ahead=6
            )
            
            total_evaluated = 0
            total_notified = 0
            
            for trip_doc in trips:
                result = self._evaluate_trip(trip_doc)
                if result:
                    total_evaluated += 1
                    if result.get("notified"):
                        total_notified += 1
            
            logger.info(
                f"[PREMIUM] Smart delay job complete: "
                f"{total_evaluated} evaluated, {total_notified} notified"
            )
        
        except Exception as e:
            logger.error(f"[PREMIUM] Smart delay job error: {e}")
    
    def _evaluate_trip(self, trip_doc: dict) -> Optional[dict]:
        """
        Evaluate a single trip for smart delay opportunity.
        
        Args:
            trip_doc: Trip document from MongoDB
        
        Returns:
            Dict with evaluation result, or None if error
        """
        user_id = trip_doc.get("user_id")
        trip_id = trip_doc.get("trip_id")
        
        # Step 1: Verify user is Premium
        if not self.premium_service.is_premium(user_id):
            logger.debug(
                f"[PREMIUM] Skipping trip {trip_id}: user {user_id} not premium"
            )
            return {"notified": False, "reason": "not_premium"}
        
        # Step 2: Check cooldown (don't spam same trip)
        if not self.notification_service.should_send_alert(user_id, trip_id):
            logger.debug(
                f"[PREMIUM] Skipping trip {trip_id}: cooldown active"
            )
            # Update next check time
            next_check = datetime.now(timezone.utc) + timedelta(minutes=30)
            self.notification_service.update_trip_check_time(trip_id, next_check)
            return {"notified": False, "reason": "cooldown"}
        
        # Step 3: Get forecast for route
        try:
            waypoints = trip_doc.get("route_waypoints", [])
            if not waypoints:
                return {"notified": False, "reason": "no_waypoints"}
            
            # Use first waypoint as reference for forecast
            lat = waypoints[0].get("latitude")
            lon = waypoints[0].get("longitude")
            
            forecast_hourly = self.weather_provider.get_hourly_forecast(
                lat, lon, hours=6
            )
            if not forecast_hourly:
                logger.warning(
                    f"[PREMIUM] No forecast available for trip {trip_id}"
                )
                return {"notified": False, "reason": "no_forecast"}
        
        except Exception as e:
            logger.error(f"[PREMIUM] Failed to fetch forecast: {e}")
            return {"notified": False, "reason": "forecast_error"}
        
        # Step 4: Compute departure risks
        planned_departure_local = trip_doc.get("planned_departure_local")
        if isinstance(planned_departure_local, str):
            # Parse ISO format
            planned_departure_local = datetime.fromisoformat(planned_departure_local)
        
        try:
            risk_scores = SmartDelayOptimizer.compute_departure_risk(
                forecast_hourly,
                waypoints,
                planned_departure_local,
                window_hours=self.DELAY_WINDOW_HOURS,
            )
        except Exception as e:
            logger.error(f"[PREMIUM] Risk computation failed: {e}")
            return {"notified": False, "reason": "risk_error"}
        
        # Step 5: Find best delay option
        best_delay = SmartDelayOptimizer.best_delay_option(
            risk_scores,
            threshold_improvement_pct=self.MIN_IMPROVEMENT_PCT,
        )
        
        if best_delay is None:
            logger.debug(f"[PREMIUM] No significant delay improvement for trip {trip_id}")
            # Update next check time
            next_check = datetime.now(timezone.utc) + timedelta(hours=1)
            self.notification_service.update_trip_check_time(trip_id, next_check)
            return {"notified": False, "reason": "no_improvement"}
        
        # Step 6: Send push notification
        push_token = self.notification_service.get_push_token(user_id)
        if not push_token:
            logger.warning(
                f"[PREMIUM] No push token for user {user_id}, cannot notify"
            )
            return {"notified": False, "reason": "no_token"}
        
        success = self.notification_service.expo_client.send_smart_delay_notification(
            push_token=push_token,
            delay_hours=best_delay.best_delay_hours,
            improvement_pct=best_delay.improvement_pct,
            trip_id=trip_id,
        )
        
        if success:
            # Step 7: Record notification and update trip
            self.notification_service.record_notification(
                user_id=user_id,
                trip_id=trip_id,
                title="Smart departure suggestion",
                body=best_delay.message,
                delay_hours=best_delay.best_delay_hours,
                improvement_pct=best_delay.improvement_pct,
            )
            
            # Update trip alert time and next check
            self.notification_service.update_trip_alert_time(trip_id)
            next_check = datetime.now(timezone.utc) + timedelta(hours=2)
            self.notification_service.update_trip_check_time(trip_id, next_check)
            
            logger.info(
                f"[PREMIUM] Sent smart delay alert to user {user_id} "
                f"(trip {trip_id}, delay {best_delay.best_delay_hours}h, "
                f"improvement {best_delay.improvement_pct}%)"
            )
            return {"notified": True, "delay_hours": best_delay.best_delay_hours}
        else:
            logger.warning(f"[PREMIUM] Failed to send notification for trip {trip_id}")
            # Try again later
            next_check = datetime.now(timezone.utc) + timedelta(minutes=15)
            self.notification_service.update_trip_check_time(trip_id, next_check)
            return {"notified": False, "reason": "send_failed"}
