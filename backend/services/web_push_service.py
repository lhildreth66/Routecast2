"""
Web Push delivery helper using pywebpush.

Requires environment variables:
- VAPID_PUBLIC_KEY
- VAPID_PRIVATE_KEY
- VAPID_EMAIL (used for the VAPID subject mailto:)
"""

import json
import logging
import os
from typing import Dict, Optional

from pywebpush import webpush, WebPushException  # type: ignore

logger = logging.getLogger(__name__)


class WebPushService:
    def __init__(self):
        self.public_key = os.environ.get("VAPID_PUBLIC_KEY")
        self.private_key = os.environ.get("VAPID_PRIVATE_KEY")
        email = os.environ.get("VAPID_EMAIL") or os.environ.get("SUPPORT_EMAIL")
        self.vapid_subject = f"mailto:{email}" if email else None

    def _vapid_kwargs(self) -> Dict[str, str]:
        if not self.public_key or not self.private_key:
            raise RuntimeError("VAPID keys not configured")
        if not self.vapid_subject:
            raise RuntimeError("VAPID_EMAIL not configured")
        return {
            "vapid_private_key": self.private_key,
            "vapid_claims": {"sub": self.vapid_subject},
        }

    def send(self, subscription: Dict[str, str], payload: Dict[str, str]) -> Dict[str, str]:
        """Send a single Web Push notification.

        Args:
            subscription: dict with endpoint, keys.p256dh, keys.auth
            payload: dict to JSON-encode for the notification
        """
        try:
            vapid_args = self._vapid_kwargs()
        except RuntimeError as exc:
            logger.error("[webpush] VAPID configuration missing: %s", exc)
            return {"success": False, "error": str(exc)}

        try:
            response = webpush(
                subscription_info=subscription,
                data=json.dumps(payload),
                **vapid_args,
            )
            logger.info(
                "[webpush] sent status=%s endpoint=%s",
                response.status_code,
                (subscription.get("endpoint") or "")[:32] + "…",
            )
            return {"success": True, "status": response.status_code}
        except WebPushException as exc:  # type: ignore
            logger.warning(
                "[webpush] failure endpoint=%s detail=%s",
                (subscription.get("endpoint") or "")[:32] + "…",
                getattr(exc, "__str__", lambda: str(exc))(),
            )
            return {"success": False, "error": str(exc)}
        except Exception as exc:  # noqa: BLE001
            logger.error("[webpush] unexpected error: %s", exc)
            return {"success": False, "error": str(exc)}
