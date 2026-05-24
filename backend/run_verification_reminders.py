"""
Unverified-account email reminder cron worker.

Schedule (Render cron): 0 * * * *  (every hour)
Command: python backend/run_verification_reminders.py

Qualifying users
- email_verified is False (or missing/null)
- email field exists and is non-empty
- email_opt_out is not True
- subscription_status NOT in active/trialing/canceling  ← protects all paid users
- verification_reminder_stage < target stage            ← never re-send or skip ahead

Stage windows (from created_at):
  Stage 1:  45 min – 2 h    (centre ~1 h)
  Stage 2:  22 h   – 26 h   (centre ~24 h)

Max 2 reminders total. Stops automatically once email_verified = True.

Tracking fields (written lazily via $set — no schema migration required):
  verification_reminder_stage         int   0 / 1 / 2
  last_verification_reminder_sent_at  datetime UTC

A fresh 24-hour verification token is generated and stored at send time so
the recipient always receives a valid (non-expired) link regardless of when
the original token was issued.

Safe-guards
- Belt-and-suspenders re-check at send time (status + verified flag)
- PROTECTED_STATUSES covers all paid/trial states
- DRY_RUN=1 logs without sending or writing to DB
- Idempotent: stage field prevents duplicate sends
"""

import os
import sys
import hmac
import hashlib
import logging
import secrets
from datetime import datetime, timezone, timedelta
from urllib.parse import quote as urlquote

from pymongo import MongoClient

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("verification_reminders")

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------
MONGO_URL = os.environ.get("MONGODB_URI") or os.environ.get("MONGO_URL")
DB_NAME   = os.environ.get("DB_NAME", "routecast_db")
BACKEND_URL = (
    os.environ.get("BACKEND_PUBLIC_URL")
    or os.environ.get("BACKEND_URL")
    or "https://api.routecastweather.com"
).rstrip("/")
TOKEN_SECRET = os.environ.get("EMAIL_UNSUBSCRIBE_SECRET") or os.environ.get("SECRET_KEY", "")
DRY_RUN = os.environ.get("REMINDER_DRY_RUN", "0").lower() in {"1", "true", "yes"}

# Statuses that mean the user is already a paying/trial customer — never email these
PROTECTED_STATUSES = {"active", "trialing", "canceling"}

# Stage windows: (min_age, max_age, stage_number)
STAGE_WINDOWS = [
    (timedelta(minutes=45), timedelta(hours=2),  1),
    (timedelta(hours=22),   timedelta(hours=26), 2),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_unsubscribe_token(user_id: str) -> str:
    """Deterministic HMAC-SHA256 token — matches run_signup_reminders.py convention."""
    if not TOKEN_SECRET:
        raise RuntimeError("EMAIL_UNSUBSCRIBE_SECRET or SECRET_KEY must be set")
    return hmac.new(
        TOKEN_SECRET.encode("utf-8"),
        user_id.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def make_unsubscribe_url(user_id: str) -> str:
    token = make_unsubscribe_token(user_id)
    return f"{BACKEND_URL}/api/auth/email-opt-out?token={token}&uid={user_id}"


def issue_verification_token(db, user_id: str) -> str:
    """Generate and store a fresh 24-hour email verification token (sync PyMongo)."""
    token = secrets.token_urlsafe(48)
    now   = datetime.now(timezone.utc)
    db.verification_tokens.insert_one({
        "user_id":    user_id,
        "token":      token,
        "token_type": "email_verification",
        "created_at": now,
        "expires_at": now + timedelta(hours=24),
        "used":       False,
    })
    return token


def make_verify_url(token: str) -> str:
    return f"{BACKEND_URL}/api/auth/verify-email?token={urlquote(token, safe='')}"


# ---------------------------------------------------------------------------
# Core job
# ---------------------------------------------------------------------------

def run_once(db) -> int:
    """Send verification reminder emails for all qualifying users. Returns count sent."""
    now           = datetime.now(timezone.utc)
    total_sent    = 0
    total_skipped = 0

    for min_age, max_age, stage in STAGE_WINDOWS:
        window_start = now - max_age   # created more than max_age ago
        window_end   = now - min_age   # created less than min_age ago

        query = {
            # Must be unverified
            "email_verified": {"$in": [False, None]},
            # Must have an email address
            "email": {"$exists": True, "$nin": [None, ""]},
            # Respect opt-out
            "email_opt_out": {"$ne": True},
            # Protect all paid / trial users
            "subscription_status": {"$nin": list(PROTECTED_STATUSES)},
            # Only advance by one stage at a time
            "$or": [
                {"verification_reminder_stage": {"$exists": False}},
                {"verification_reminder_stage": None},
                {"verification_reminder_stage": stage - 1},
            ],
            # Within the time window for this stage
            "created_at": {"$gte": window_start, "$lte": window_end},
        }

        cursor = db.users.find(query)
        for user in cursor:
            user_id = str(user.get("user_id") or user.get("_id", ""))
            email   = user.get("email", "")
            name    = user.get("name") or user.get("display_name") or None

            if not email:
                logger.warning(
                    "[verify_reminder] skipped stage=%d user_id=%s reason=no_email",
                    stage, user_id,
                )
                total_skipped += 1
                continue

            # Belt-and-suspenders: re-read live state at send time
            if user.get("email_verified"):
                logger.info(
                    "[verify_reminder] skipped stage=%d user_id=%s reason=now_verified",
                    stage, user_id,
                )
                total_skipped += 1
                continue

            live_status = (user.get("subscription_status") or "").lower()
            if live_status in PROTECTED_STATUSES:
                logger.info(
                    "[verify_reminder] skipped stage=%d user_id=%s reason=protected_status status=%s",
                    stage, user_id, live_status,
                )
                total_skipped += 1
                continue

            unsubscribe_url = make_unsubscribe_url(user_id)

            if DRY_RUN:
                logger.info(
                    "[verify_reminder] DRY_RUN stage=%d user_id=%s email=%s",
                    stage, user_id, email,
                )
                total_sent += 1
                continue

            try:
                fresh_token = issue_verification_token(db, user_id)
                verify_url  = make_verify_url(fresh_token)
                from services.email_service import send_verification_reminder_email, EmailDeliveryError
                sent = send_verification_reminder_email(
                    email, name, stage, verify_url, unsubscribe_url
                )
            except Exception as exc:
                logger.error(
                    "[verify_reminder] send_failed stage=%d user_id=%s email=%s error=%s",
                    stage, user_id, email, exc,
                )
                continue

            if sent:
                db.users.update_one(
                    {"_id": user["_id"]},
                    {"$set": {
                        "verification_reminder_stage":        stage,
                        "last_verification_reminder_sent_at": now,
                    }},
                )
                logger.info(
                    "[verify_reminder] sent stage=%d user_id=%s email=%s",
                    stage, user_id, email,
                )
                total_sent += 1
            else:
                logger.warning(
                    "[verify_reminder] send_returned_false stage=%d user_id=%s email=%s",
                    stage, user_id, email,
                )

    logger.info(
        "[verify_reminder] run complete sent=%d skipped=%d",
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
        logger.info("[verify_reminder] worker finished sent=%d", sent)
    except Exception as exc:
        logger.exception("[verify_reminder] worker error: %s", exc)
        sys.exit(1)
    finally:
        client.close()

    sys.exit(0)
