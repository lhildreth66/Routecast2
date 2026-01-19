"""
Expo Push Notifications Client

Sends push notifications via Expo Push API.
https://docs.expo.dev/push-notifications/overview/

Pro-only feature: Smart Departure & Hazard Alerts
"""

import httpx
import logging
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

# Expo Push API endpoint
EXPO_PUSH_API_URL = "https://exp.host/--/api/v2/push/send"


class ExpoPushClient:
    """Client for sending push notifications via Expo."""
    
    def __init__(self, access_token: Optional[str] = None):
        """
        Initialize Expo push client.
        
        Args:
            access_token: Optional Expo access token (may not be required for basic usage)
        """
        self.access_token = access_token
        self.client = httpx.Client(timeout=10.0)
    
    def send_smart_delay_notification(
        self,
        push_token: str,
        delay_hours: int,
        improvement_pct: float,
        trip_id: str,
    ) -> bool:
        """
        Send smart delay optimizer notification.
        
        Args:
            push_token: Expo push token for the device
            delay_hours: Recommended delay in hours
            improvement_pct: Percent improvement by delaying
            trip_id: ID of the trip
        
        Returns:
            True if successfully sent, False otherwise
        """
        title = "Smart departure suggestion"
        improvement_rounded = int(round(improvement_pct / 5) * 5)
        body = f"Delay {delay_hours}h avoids ~{improvement_rounded}% hazards"
        
        return self.send_notification(
            push_token=push_token,
            title=title,
            body=body,
            data={
                "type": "smart_delay",
                "delayHours": str(delay_hours),
                "improvementPct": str(int(improvement_pct)),
                "tripId": trip_id,
            },
        )
    
    def send_notification(
        self,
        push_token: str,
        title: str,
        body: str,
        data: Optional[Dict[str, str]] = None,
        sound: str = "default",
    ) -> bool:
        """
        Send a push notification via Expo.
        
        Args:
            push_token: Expo push token
            title: Notification title
            body: Notification body
            data: Optional data payload
            sound: Sound to play ("default" or "none")
        
        Returns:
            True if sent successfully, False otherwise
        """
        if not push_token:
            logger.warning("Cannot send notification: empty push token")
            return False
        
        if not push_token.startswith("ExponentPushToken["):
            logger.warning(f"Invalid push token format: {push_token[:20]}...")
            return False
        
        payload = {
            "to": push_token,
            "title": title,
            "body": body,
            "sound": sound,
            "badge": 1,  # Show badge on app icon
        }
        
        if data:
            payload["data"] = data
        
        try:
            response = self.client.post(
                EXPO_PUSH_API_URL,
                json=payload,
                headers=self._get_headers(),
            )
            
            if response.status_code == 200:
                result = response.json()
                
                # Check response status
                if result.get("data", {}).get("status") == "error":
                    error = result.get("data", {}).get("message", "Unknown error")
                    logger.error(f"Expo push error: {error}")
                    return False
                
                logger.info(
                    f"[PREMIUM] Push sent to {push_token[:30]}... "
                    f"(title: {title[:30]})"
                )
                return True
            else:
                logger.error(
                    f"Expo push API error: {response.status_code} {response.text}"
                )
                return False
        
        except Exception as e:
            logger.error(f"Failed to send push notification: {e}")
            return False
    
    def _get_headers(self) -> dict:
        """Get HTTP headers for Expo API."""
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        return headers
    
    def close(self):
        """Close HTTP client."""
        self.client.close()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
