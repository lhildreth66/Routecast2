"""
Push Notification Service for RouteCast
Handles push token storage, route monitoring, and weather alerts.
Uses Expo Push Notification Service for delivery.
"""

import httpx
import asyncio
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging

logger = logging.getLogger(__name__)

# Expo Push API
EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"


class PushNotificationService:
    """Service for managing push notifications."""

    def __init__(self, db):
        self.db = db

    async def register_push_token(
        self,
        user_id: str,
        push_token: str,
        platform: str = "unknown",
        device_info: Optional[Dict] = None
    ) -> bool:
        """
        Register or update a push token for a user.

        Args:
            user_id: The user's ID
            push_token: Expo push token (ExponentPushToken[...])
            platform: ios, android, or web
            device_info: Optional device metadata
        """
        try:
            # Validate token format
            if not push_token.startswith("ExponentPushToken["):
                logger.warning(f"Invalid push token format: {push_token[:20]}...")
                return False

            # Upsert the token
            await self.db.push_tokens.update_one(
                {"user_id": user_id, "token": push_token},
                {
                    "$set": {
                        "user_id": user_id,
                        "token": push_token,
                        "platform": platform,
                        "device_info": device_info or {},
                        "updated_at": datetime.utcnow(),
                        "active": True
                    },
                    "$setOnInsert": {
                        "created_at": datetime.utcnow()
                    }
                },
                upsert=True
            )

            logger.info(f"Registered push token for user {user_id}")
            return True

        except Exception as e:
            logger.error(f"Error registering push token: {e}")
            return False

    async def unregister_push_token(self, user_id: str, push_token: str) -> bool:
        """Remove a push token."""
        try:
            await self.db.push_tokens.update_one(
                {"user_id": user_id, "token": push_token},
                {"$set": {"active": False}}
            )
            return True
        except Exception as e:
            logger.error(f"Error unregistering push token: {e}")
            return False

    async def get_user_tokens(self, user_id: str) -> List[str]:
        """Get all active push tokens for a user."""
        tokens = await self.db.push_tokens.find(
            {"user_id": user_id, "active": True},
            {"token": 1}
        ).to_list(10)

        return [t["token"] for t in tokens]

    async def send_notification(
        self,
        push_tokens: List[str],
        title: str,
        body: str,
        data: Optional[Dict] = None,
        sound: str = "default",
        badge: Optional[int] = None,
        channel_id: str = "weather-alerts"
    ) -> Dict:
        """
        Send push notification to one or more tokens.

        Args:
            push_tokens: List of Expo push tokens
            title: Notification title
            body: Notification body text
            data: Optional payload data
            sound: Sound to play (default, or custom)
            badge: Badge count to set
            channel_id: Android notification channel
        """
        if not push_tokens:
            return {"success": False, "error": "No push tokens provided"}

        messages = []
        for token in push_tokens:
            message = {
                "to": token,
                "title": title,
                "body": body,
                "sound": sound,
                "channelId": channel_id,
            }

            if data:
                message["data"] = data

            if badge is not None:
                message["badge"] = badge

            messages.append(message)

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    EXPO_PUSH_URL,
                    json=messages,
                    headers={
                        "Accept": "application/json",
                        "Content-Type": "application/json"
                    }
                )

                if response.status_code == 200:
                    result = response.json()

                    # Check for individual ticket errors
                    tickets = result.get("data", [])
                    errors = []
                    successes = 0

                    for i, ticket in enumerate(tickets):
                        if ticket.get("status") == "error":
                            errors.append({
                                "token": push_tokens[i][:30] + "...",
                                "error": ticket.get("message")
                            })

                            # Mark token as inactive if it's invalid
                            if ticket.get("details", {}).get("error") == "DeviceNotRegistered":
                                await self.db.push_tokens.update_one(
                                    {"token": push_tokens[i]},
                                    {"$set": {"active": False}}
                                )
                        else:
                            successes += 1

                    return {
                        "success": True,
                        "sent": successes,
                        "errors": errors
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Expo API error: {response.status_code}"
                    }

        except Exception as e:
            logger.error(f"Error sending push notification: {e}")
            return {"success": False, "error": str(e)}

    async def send_to_user(
        self,
        user_id: str,
        title: str,
        body: str,
        data: Optional[Dict] = None,
        **kwargs
    ) -> Dict:
        """Send notification to all of a user's registered devices."""
        tokens = await self.get_user_tokens(user_id)

        if not tokens:
            return {"success": False, "error": "No registered devices"}

        return await self.send_notification(tokens, title, body, data, **kwargs)


class RouteMonitorService:
    """Service for monitoring routes and sending weather alerts."""

    def __init__(self, db, push_service: PushNotificationService):
        self.db = db
        self.push_service = push_service

    async def create_route_monitor(
        self,
        user_id: str,
        route_id: str,
        origin: str,
        destination: str,
        departure_time: datetime,
        alert_preferences: Optional[Dict] = None
    ) -> str:
        """
        Create a route monitor for weather alerts.

        Returns the monitor ID.
        """
        monitor = {
            "user_id": user_id,
            "route_id": route_id,
            "origin": origin,
            "destination": destination,
            "departure_time": departure_time,
            "alert_preferences": alert_preferences or {
                "severe_weather": True,
                "road_conditions": True,
                "temperature_extremes": True,
                "hours_before": 24  # Start alerting 24h before departure
            },
            "status": "active",
            "created_at": datetime.utcnow(),
            "last_checked": None,
            "last_alert_sent": None,
            "alerts_sent": 0
        }

        result = await self.db.route_monitors.insert_one(monitor)
        return str(result.inserted_id)

    async def get_active_monitors(self, lookahead_hours: int = 48) -> List[Dict]:
        """Get all active route monitors for upcoming departures."""
        cutoff = datetime.utcnow() + timedelta(hours=lookahead_hours)

        monitors = await self.db.route_monitors.find({
            "status": "active",
            "departure_time": {
                "$gte": datetime.utcnow(),
                "$lte": cutoff
            }
        }).to_list(1000)

        return monitors

    async def get_user_monitors(self, user_id: str) -> List[Dict]:
        """Get all monitors for a user."""
        monitors = await self.db.route_monitors.find({
            "user_id": user_id,
            "status": "active"
        }).to_list(50)

        # Convert _id to string
        for m in monitors:
            m["id"] = str(m.pop("_id"))

        return monitors

    async def cancel_monitor(self, user_id: str, monitor_id: str) -> bool:
        """Cancel a route monitor."""
        result = await self.db.route_monitors.update_one(
            {"_id": monitor_id, "user_id": user_id},
            {"$set": {"status": "cancelled"}}
        )
        return result.modified_count > 0

    async def check_for_alerts(self, monitor: Dict, weather_data: Dict) -> List[Dict]:
        """
        Check weather data for alert conditions.

        Returns list of alerts to send.
        """
        alerts = []
        prefs = monitor.get("alert_preferences", {})

        # Check for severe weather
        if prefs.get("severe_weather"):
            for alert in weather_data.get("hazard_alerts", []):
                if alert.get("severity") in ["Extreme", "Severe"]:
                    alerts.append({
                        "type": "severe_weather",
                        "title": f"Severe Weather Alert: {alert.get('event', 'Weather Alert')}",
                        "body": alert.get("headline", "Severe weather expected on your route"),
                        "severity": "high",
                        "data": alert
                    })

        # Check for road conditions
        if prefs.get("road_conditions"):
            worst_condition = weather_data.get("worst_road_condition")
            if worst_condition in ["Hazardous", "Very Poor"]:
                alerts.append({
                    "type": "road_condition",
                    "title": "Road Condition Warning",
                    "body": f"{worst_condition} road conditions expected on your route",
                    "severity": "medium",
                    "data": {"condition": worst_condition}
                })

        # Check for temperature extremes
        if prefs.get("temperature_extremes"):
            for wp in weather_data.get("waypoints", []):
                temp = wp.get("temperature")
                if temp and (temp < 20 or temp > 100):
                    extreme = "extreme cold" if temp < 20 else "extreme heat"
                    alerts.append({
                        "type": "temperature",
                        "title": f"Temperature Alert",
                        "body": f"Expect {extreme} ({temp}°F) at {wp.get('location', 'your route')}",
                        "severity": "low",
                        "data": {"temperature": temp, "location": wp.get("location")}
                    })
                    break  # Only one temp alert

        return alerts

    async def send_route_alert(
        self,
        user_id: str,
        monitor: Dict,
        alert: Dict
    ) -> bool:
        """Send a route weather alert to a user."""
        # Check user's subscription status
        user = await self.db.users.find_one({"user_id": user_id})

        if not user:
            return False

        # Only send to premium/trialing users
        sub_status = user.get("subscription_status")
        if sub_status not in ["active", "trialing"]:
            logger.info(f"Skipping alert for non-premium user {user_id}")
            return False

        # Send the notification
        result = await self.push_service.send_to_user(
            user_id=user_id,
            title=alert["title"],
            body=alert["body"],
            data={
                "type": "route_alert",
                "alert_type": alert["type"],
                "route_id": monitor.get("route_id"),
                "monitor_id": str(monitor.get("_id")),
                **alert.get("data", {})
            },
            channel_id="weather-alerts" if alert["severity"] == "high" else "route-updates"
        )

        if result.get("success"):
            # Update monitor stats
            await self.db.route_monitors.update_one(
                {"_id": monitor["_id"]},
                {
                    "$set": {"last_alert_sent": datetime.utcnow()},
                    "$inc": {"alerts_sent": 1}
                }
            )
            return True

        return False


async def run_route_alert_worker(db, interval_minutes: int = 15):
    """
    Background worker that checks routes and sends alerts.

    Should be run as a separate process/service.
    """
    push_service = PushNotificationService(db)
    monitor_service = RouteMonitorService(db, push_service)

    logger.info("Starting route alert worker...")

    while True:
        try:
            # Get active monitors
            monitors = await monitor_service.get_active_monitors()
            logger.info(f"Checking {len(monitors)} active route monitors")

            for monitor in monitors:
                # Skip if checked recently (within 30 min)
                last_checked = monitor.get("last_checked")
                if last_checked and (datetime.utcnow() - last_checked).seconds < 1800:
                    continue

                # Fetch current weather for the route
                # This would call the route/weather endpoint
                # For now, we'll mark it as checked

                await db.route_monitors.update_one(
                    {"_id": monitor["_id"]},
                    {"$set": {"last_checked": datetime.utcnow()}}
                )

                # In production, fetch weather and check for alerts
                # weather_data = await fetch_route_weather(monitor)
                # alerts = await monitor_service.check_for_alerts(monitor, weather_data)
                # for alert in alerts:
                #     await monitor_service.send_route_alert(monitor["user_id"], monitor, alert)

            # Wait for next check interval
            await asyncio.sleep(interval_minutes * 60)

        except Exception as e:
            logger.error(f"Error in route alert worker: {e}")
            await asyncio.sleep(60)  # Wait 1 min on error
