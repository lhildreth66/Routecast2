"""
Abandoned-signup reminder email cron worker.

Schedule (Render cron): 0 * * * *  (every hour)
Command: python backend/run_signup_reminders.py

Qualifying users
- subscription_status in ("inactive", "free")
- trial_start is null
- google_purchase_token is null
- email_verified is true
- email_opt_out is not true
- reminder_stage < target stage (never re-send or skip ahead)

Stage windows (from created_at):
  Stage 1:  45 min – 1h 30 min  (centre = 1 h,  ±45 min)
  Stage 2:  22 h   – 26 h       (centre = 24 h, ±2 h with buffer)
  Stage 3:  70 h   – 74 h       (centre = 72 h, ±2 h with buffer)

Tracking fields written lazily via $set (no schema migration required):
  reminder_stage          int  — 0/1/2/3
  last_reminder_sent_at   datetime UTC

Unsubscribe:
  A HMAC-SHA256 token derived from (user_id + secret) is embedded in the link.
  The auth router handles GET /api/auth/email-opt-out?token=<tok> and sets
  email_opt_out=True on the matching user.
"""

import os
import sys
import hmac
import hashlib
import logging
from datetime import datetime, timezone, timedelta

from pymongo import MongoClient

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("signup_reminders")

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------
MONGO_URL = os.environ.get("MONGODB_URI") or os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME", "routecast_db")
BACKEND_URL = (
    os.environ.get("BACKEND_PUBLIC_URL")
    or os.environ.get("BACKEND_URL")
    or "https://api.routecastweather.com"
).rstrip("/")
# Secret for HMAC unsubscribe tokens — falls back to JWT secret so no new env var is needed
TOKEN_SECRET = os.environ.get("EMAIL_UNSUBSCRIBE_SECRET") or os.environ.get("SECRET_KEY", "")

# Stage window definitions: (min_age_hours, max_age_hours, stage_number)
STAGE_WINDOWS = [
    (timedelta(minutes=45), timedelta(hours=1, minutes=30), 1),
    (timedelta(hours=22),   timedelta(hours=26),             2),
    (timedelta(hours=70),   timedelta(hours=74),             3),
]

DRY_RUN = os.environ.get("REMINDER_DRY_RUN", "0").lower() in {"1", "true", "yes"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_unsubscribe_token(user_id: str) -> str:
    """Generate a deterministic HMAC-SHA256 token for the unsubscribe link."""
    secret = TOKEN_SECRET.encode("utf-8") if TOKEN_SECRET else b"fallback-secret"
    return hmac.new(secret, user_id.encode("utf-8"), hashlib.sha256).hexdigest()


def make_unsubscribe_url(user_id: str) -> str:
    token = make_unsubscribe_token(user_id)
    return f"{BACKEND_URL}/api/auth/email-opt-out?token={token}&uid={user_id}"


# ---------------------------------------------------------------------------
# Core job
# ---------------------------------------------------------------------------

def run_once(db) -> int:
    """Send reminder emails for all qualifying users. Returns number sent."""
    now = datetime.now(timezone.utc)
    total_sent = 0
    total_skipped = 0

    for min_age, max_age, stage in STAGE_WINDOWS:
        window_start = now - max_age   # users created MORE than max_age ago
        window_end   = now - min_age   # users created LESS than min_age ago

        query = {
            "subscription_status": {"$in": ["inactive", "free"]},
            "trial_start": None,
            "google_purchase_token": None,
            "email_verified": True,
            "email_opt_out": {"$ne": True},
            # Only advance stage by exactly one (never skip or re-send)
            "$or": [
                {"reminder_stage": {"$exists": False}},
                {"reminder_stage": None},
                {"reminder_stage": stage - 1},
            ],
            "created_at": {"$gte": window_start, "$lte": window_end},
        }

        cursor = db.users.find(query)
        for user in cursor:
            user_id = str(user.get("user_id") or user.get("_id", ""))
            email = user.get("email", "")
            name = user.get("name") or user.get("display_name") or None

            if not email:
                logger.warning(
                    "[reminder_email] skipped stage=%d user_id=%s reason=no_email",
                    stage, user_id,
                )
                total_skipped += 1
                continue

            # Belt-and-suspenders guard: re-check eligibility at send time
            current_status = user.get("subscription_status", "inactive")
            if current_status not in ("inactive", "free"):
                logger.info(
                    "[reminder_email] skipped stage=%d user_id=%s reason=already_subscribed status=%s",
                    stage, user_id, current_status,
                )
                total_skipped += 1
                continue
            if user.get("trial_start") is not None:
                logger.info(
                    "[reminder_email] skipped stage=%d user_id=%s reason=trial_already_started",
                    stage, user_id,
                )
                total_skipped += 1
                continue
            if user.get("google_purchase_token") is not None:
                logger.info(
                    "[reminder_email] skipped stage=%d user_id=%s reason=has_purchase_token",
                    stage, user_id,
                )
                total_skipped += 1
                continue

            unsubscribe_url = make_unsubscribe_url(user_id)

            if DRY_RUN:
                logger.info(
                    "[reminder_email] DRY_RUN stage=%d user_id=%s email=%s",
                    stage, user_id, email,
                )
                total_sent += 1
                continue

            try:
                from services.email_service import send_signup_reminder_email, EmailDeliveryError
                sent = send_signup_reminder_email(email, name, stage, unsubscribe_url)
            except Exception as exc:
                logger.error(
                    "[reminder_email] send_failed stage=%d user_id=%s email=%s error=%s",
                    stage, user_id, email, exc,
                )
                continue

            if sent:
                db.users.update_one(
                    {"_id": user["_id"]},
                    {
                        "$set": {
                            "reminder_stage": stage,
                            "last_reminder_sent_at": now,
                        }
                    },
                )
                logger.info(
                    "[reminder_email] sent stage=%d user_id=%s email=%s",
                    stage, user_id, email,
                )
                total_sent += 1
            else:
                logger.warning(
                    "[reminder_email] send_returned_false stage=%d user_id=%s email=%s",
                    stage, user_id, email,
                )

    logger.info(
        "[reminder_email] run complete sent=%d skipped=%d",
        total_sent, total_skipped,
    )
    return total_sent


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if not MONGO_URL:
        logger.error("MONGODB_URI / MONGO_URL not set — aborting")
        sys.exit(1)

    client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=8000)
    try:
        db = client[DB_NAME]
        sent = run_once(db)
        logger.info("[reminder_email] worker finished sent=%d", sent)
    except Exception as exc:
        logger.exception("[reminder_email] worker error: %s", exc)
        sys.exit(1)
    finally:
        client.close()

    sys.exit(0)
