# STRIPE DISABLED - Google Play submission - do not delete
"""
Subscription Service for RouteCast
Handles Stripe subscriptions, Apple/Google receipt verification, and entitlements
"""
import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from motor.motor_asyncio import AsyncIOMotorDatabase
import logging
import httpx

# STRIPE DISABLED - Google Play submission - do not delete
# import stripe

# Initialise Stripe SDK once
_STRIPE_API_KEY = os.environ.get('STRIPE_API_KEY', '')
if _STRIPE_API_KEY:
    stripe.api_key = _STRIPE_API_KEY

# How often to re-verify subscription status against Stripe (seconds).
# Set to 0 to disable live checks entirely.
STRIPE_CHECK_TTL_SECONDS = int(os.environ.get('STRIPE_CHECK_TTL_SECONDS', '300'))  # 5 min default

# Statuses that mean the user currently has paid access.
# "canceling" = Stripe active + cancel_at_period_end; user paid for the period.
PREMIUM_STATUSES = frozenset({"active", "trialing", "canceling"})

# Statuses that are definitively not premium (per spec).
NON_PREMIUM_STATUSES = frozenset({
    "canceled", "expired", "incomplete", "incomplete_expired",
    "past_due", "unpaid", "inactive",
})

logger = logging.getLogger(__name__)


async def _revoke_premium(
    db: AsyncIOMotorDatabase,
    user_id: str,
    reason: str,
    now: datetime,
    clear_sub_id: bool = False,
) -> None:
    """
    Immediately strip premium access from a user and log the reason.
    Used when Stripe confirms there is no valid subscription.
    """
    fields: dict = {
        "is_premium": False,
        "subscription_status": "inactive",
        "subscription_plan": "free",
        "plan": "free",
        "subscription_expiration": None,
        "stripe_status_verified_at": now,
        "updated_at": now,
    }
    if clear_sub_id:
        fields["stripe_subscription_id"] = None

    await db.users.update_one({"user_id": user_id}, {"$set": fields})
    try:
        await db.subscription_logs.insert_one({
            "user_id": user_id,
            "action": "revoked",
            "reason": reason,
            "admin_action": False,
            "timestamp": now,
        })
    except Exception:
        pass
    logger.info(f"[STRIPE] Premium revoked user={user_id} reason={reason}")
SUBSCRIPTION_PRICES = {
    "monthly": {
        "amount": 9.99,
        "stripe_price_id": None,  # Will be set from Stripe dashboard
        "trial_days": 7,
    },
    "yearly": {
        "amount": 59.99,
        "stripe_price_id": None,  # Will be set from Stripe dashboard
        "trial_days": 7,
    }
}

# Trial duration
TRIAL_DAYS = 7


async def check_subscription_status(db: AsyncIOMotorDatabase, user_id: str) -> dict:
    """
    Return authoritative subscription status for a user.

    Premium is derived from Stripe state, not cached DB optimism:
      - 'active'    → premium
      - 'trialing'  → premium (within trial window)
      - 'canceling' → premium UNTIL current_period_end
      - everything else → NOT premium

    A Stripe live-check is performed when the user has a
    stripe_subscription_id and the cached result is older than
    STRIPE_CHECK_TTL_SECONDS.  This catches missed webhooks.
    """
    user = await db.users.find_one({"user_id": user_id})
    if not user:
        return {"status": "inactive", "is_premium": False, "plan": "free",
                "provider": None, "expiration": None}

    now = datetime.now(timezone.utc)
    status = user.get("subscription_status", "inactive")
    expiration = user.get("subscription_expiration")
    provider = user.get("subscription_provider", "")
    stripe_sub_id = user.get("stripe_subscription_id")
    stripe_customer_id = user.get("stripe_customer_id")
    is_db_premium = user.get("is_premium", False)

    # Normalise expiration timezone
    if expiration and isinstance(expiration, datetime):
        if expiration.tzinfo is None:
            expiration = expiration.replace(tzinfo=timezone.utc)

    # ── Guard: Stripe provider, DB says premium, but NO subscription ID ──────
    # This is the exact failure mode when a Stripe subscription is fully deleted
    # and no webhook updated the DB (or was never linked at all).  We must not
    # trust DB optimism when we can ask Stripe directly.
    if is_db_premium and provider == "stripe" and not stripe_sub_id and _STRIPE_API_KEY:
        # Try to find any live subscription for this customer in Stripe.
        found_sub_id: Optional[str] = None
        if stripe_customer_id:
            try:
                subs = stripe.Subscription.list(  # type: ignore[attr-defined]
                    customer=stripe_customer_id, limit=10
                )
                for s in (subs.get("data") or []):
                    if s.get("status") in ("active", "trialing", "past_due"):
                        found_sub_id = s["id"]
                        break
            except Exception as _e:
                logger.warning(f"[STRIPE GUARD] list subs failed user={user_id}: {_e}")
                # API error — don't revoke; fall through with DB cached value
                found_sub_id = "_api_error_"
        if found_sub_id and found_sub_id != "_api_error_":
            # Link the rediscovered subscription ID, then fall through to live-check
            stripe_sub_id = found_sub_id
            await db.users.update_one(
                {"user_id": user_id},
                {"$set": {"stripe_subscription_id": stripe_sub_id, "updated_at": now}},
            )
            logger.info(f"[STRIPE GUARD] Re-linked sub {stripe_sub_id} to user={user_id}")
        elif found_sub_id != "_api_error_":
            # Stripe confirms: no subscription exists → revoke immediately
            reason = (
                "no_subscription_found_for_customer" if stripe_customer_id
                else "stripe_provider_no_customer_id"
            )
            await _revoke_premium(db, user_id, reason, now)
            return {
                "status": "inactive", "is_premium": False, "plan": "free",
                "provider": provider, "expiration": None,
            }
    if stripe_sub_id and _STRIPE_API_KEY and STRIPE_CHECK_TTL_SECONDS > 0:
        verified_at = user.get("stripe_status_verified_at")
        if isinstance(verified_at, datetime) and verified_at.tzinfo is None:
            verified_at = verified_at.replace(tzinfo=timezone.utc)
        age_seconds = (
            (now - verified_at).total_seconds() if verified_at else STRIPE_CHECK_TTL_SECONDS + 1
        )
        if age_seconds > STRIPE_CHECK_TTL_SECONDS:
            try:
                sub = stripe.Subscription.retrieve(stripe_sub_id)  # type: ignore[attr-defined]
                s_status = sub["status"]          # active, trialing, canceled, past_due …
                s_period_end = sub.get("current_period_end")       # Unix timestamp
                s_cancel_at_period_end = sub.get("cancel_at_period_end", False)

                # Map Stripe status → internal status
                if s_status == "active" and s_cancel_at_period_end:
                    internal = "canceling"
                else:
                    internal = s_status  # active, trialing, canceled, past_due, unpaid, …

                # Refresh expiration from Stripe
                if s_period_end:
                    expiration = datetime.fromtimestamp(s_period_end, tz=timezone.utc)

                # Determine is_premium from live Stripe data
                if internal in ("active", "trialing"):
                    live_premium = True
                elif internal == "canceling" and expiration and expiration > now:
                    live_premium = True
                else:
                    live_premium = False

                # Persist updated state back to DB
                db_update: dict = {
                    "subscription_status": internal,
                    "is_premium": live_premium,
                    "stripe_status_verified_at": now,
                    "updated_at": now,
                }
                if expiration:
                    db_update["subscription_expiration"] = expiration
                if not live_premium:
                    # Also clear the plan if fully lapsed
                    if internal not in ("canceling",):
                        db_update["subscription_plan"] = "free"

                await db.users.update_one({"user_id": user_id}, {"$set": db_update})
                status = internal
                logger.info(
                    f"[STRIPE LIVE] user={user_id} stripe_status={s_status} "
                    f"internal={internal} is_premium={live_premium}"
                )
            except stripe.error.InvalidRequestError as e:  # type: ignore[attr-defined]
                # Stripe says this subscription ID does not exist.
                # This is definitive — revoke premium immediately.
                logger.warning(
                    f"[STRIPE LIVE] Sub {stripe_sub_id} not found — "
                    f"revoking premium for user={user_id}: {e}"
                )
                await _revoke_premium(db, user_id, f"stripe_sub_not_found:{stripe_sub_id}", now,
                                      clear_sub_id=True)
                return {
                    "status": "inactive", "is_premium": False, "plan": "free",
                    "provider": provider, "expiration": None,
                }
            except Exception as e:
                # Transient network / API error — fall through to DB-cached value.
                logger.warning(f"[STRIPE LIVE] check failed for user={user_id}: {e}")

    # ── Local expiration check (catches period rollovers without a webhook) ─
    if expiration and isinstance(expiration, datetime):
        if expiration.tzinfo is None:
            expiration = expiration.replace(tzinfo=timezone.utc)
        # Any of the "still paid" statuses should expire when the period ends
        if expiration < now and status in PREMIUM_STATUSES:
            await db.users.update_one(
                {"user_id": user_id},
                {"$set": {
                    "subscription_status": "expired",
                    "is_premium": False,
                    "subscription_plan": "free",
                    "updated_at": now,
                }},
            )
            status = "expired"

    # Derive is_premium: canceling is premium only while period is still valid
    if status == "canceling":
        is_premium = bool(expiration and expiration > now)
    else:
        is_premium = status in PREMIUM_STATUSES

    return {
        "status": status,
        "is_premium": is_premium,
        "plan": user.get("subscription_plan", "free"),
        "provider": user.get("subscription_provider"),
        "expiration": expiration,
    }


async def start_trial(db: AsyncIOMotorDatabase, user_id: str) -> Tuple[bool, str]:
    """Start a free trial for a user"""
    user = await db.users.find_one({"user_id": user_id})
    if not user:
        return False, "User not found"

    if user.get("trial_used", False):
        return False, "Trial already used"

    now = datetime.now(timezone.utc)
    trial_end = now + timedelta(days=TRIAL_DAYS)

    await db.users.update_one(
        {"user_id": user_id},
        {"$set": {
            "subscription_status": "trialing",
            "subscription_plan": "monthly",  # Trial gives monthly features
            "trial_used": True,
            "trial_start": now,
            "trial_end": trial_end,
            "subscription_expiration": trial_end,
            "updated_at": now
        }}
    )

    return True, f"Trial started. Expires in {TRIAL_DAYS} days."


async def activate_subscription(
    db: AsyncIOMotorDatabase,
    user_id: str,
    plan: str,
    provider: str,
    duration_days: Optional[int] = None,
    stripe_subscription_id: Optional[str] = None,
    stripe_customer_id: Optional[str] = None,
    apple_transaction_id: Optional[str] = None,
    google_purchase_token: Optional[str] = None
) -> bool:
    """Activate a subscription for a user"""
    now = datetime.now(timezone.utc)

    # Calculate expiration
    if duration_days:
        expiration = now + timedelta(days=duration_days)
    else:
        # Default durations
        if plan == "monthly":
            expiration = now + timedelta(days=30)
        elif plan == "yearly":
            expiration = now + timedelta(days=365)
        else:
            expiration = now + timedelta(days=30)

    update_data = {
        "subscription_status": "active",
        "subscription_plan": plan,
        "subscription_provider": provider,
        "subscription_expiration": expiration,
        "updated_at": now
    }

    if stripe_subscription_id:
        update_data["stripe_subscription_id"] = stripe_subscription_id
    if stripe_customer_id:
        update_data["stripe_customer_id"] = stripe_customer_id
    if apple_transaction_id:
        update_data["apple_original_transaction_id"] = apple_transaction_id
    if google_purchase_token:
        update_data["google_purchase_token"] = google_purchase_token

    result = await db.users.update_one(
        {"user_id": user_id},
        {"$set": update_data}
    )

    return result.modified_count > 0


async def cancel_subscription(db: AsyncIOMotorDatabase, user_id: str, reason: Optional[str] = None) -> bool:
    """Cancel a subscription (access continues until expiration)"""
    now = datetime.now(timezone.utc)

    result = await db.users.update_one(
        {"user_id": user_id},
        {"$set": {
            "subscription_status": "canceled",
            "updated_at": now
        }}
    )

    if reason:
        await db.subscription_logs.insert_one({
            "user_id": user_id,
            "action": "cancel",
            "reason": reason,
            "timestamp": now
        })

    return result.modified_count > 0


async def revoke_subscription(db: AsyncIOMotorDatabase, user_id: str, reason: Optional[str] = None) -> bool:
    """Immediately revoke subscription access"""
    now = datetime.now(timezone.utc)

    result = await db.users.update_one(
        {"user_id": user_id},
        {"$set": {
            "is_premium": False,
            "subscription_status": "inactive",
            "subscription_plan": "free",
            "plan": "free",
            "subscription_expiration": None,
            "stripe_status_verified_at": now,
            "updated_at": now,
        }}
    )

    await db.subscription_logs.insert_one({
        "user_id": user_id,
        "action": "revoke",
        "reason": reason or "admin_revoke",
        "admin_action": True,
        "timestamp": now,
    })

    return result.modified_count > 0


async def grant_subscription(
    db: AsyncIOMotorDatabase,
    user_id: str,
    plan: str,
    duration_days: int,
    reason: Optional[str] = None
) -> bool:
    """Admin: Grant subscription to a user"""
    success = await activate_subscription(
        db=db,
        user_id=user_id,
        plan=plan,
        provider="admin",
        duration_days=duration_days
    )

    if success:
        now = datetime.now(timezone.utc)
        await db.subscription_logs.insert_one({
            "user_id": user_id,
            "action": "grant",
            "plan": plan,
            "duration_days": duration_days,
            "reason": reason,
            "admin_action": True,
            "timestamp": now
        })

    return success


# ==================== Apple Receipt Verification ====================

async def verify_apple_receipt(receipt_data: str, product_id: str) -> dict:
    """
    Verify an Apple App Store receipt.
    In production, this would call Apple's verifyReceipt endpoint.
    """
    # Production URL: https://buy.itunes.apple.com/verifyReceipt
    # Sandbox URL: https://sandbox.itunes.apple.com/verifyReceipt

    # TODO: Implement actual Apple receipt verification
    # For now, return scaffold response

    logger.info(f"Apple receipt verification requested for product: {product_id}")

    # Scaffold response - implement when Apple IAP is configured
    return {
        "valid": False,
        "message": "Apple receipt verification not yet configured. Please contact support.",
        "subscription_status": "inactive",
        "expiration": None
    }


# ==================== Google Play Receipt Verification ====================

async def verify_google_receipt(purchase_token: str, product_id: str, package_name: str) -> dict:
    """
    Verify a Google Play purchase token.
    In production, this would call Google Play Developer API.
    """
    # TODO: Implement actual Google Play verification
    # Requires: Google Play Developer API credentials

    logger.info(f"Google Play verification requested for product: {product_id}")

    # Scaffold response - implement when Google Play Billing is configured
    return {
        "valid": False,
        "message": "Google Play verification not yet configured. Please contact support.",
        "subscription_status": "inactive",
        "expiration": None
    }


# ==================== Stripe Webhook Handling ====================

async def handle_stripe_subscription_event(
    db: AsyncIOMotorDatabase,
    event_type: str,
    subscription_data: dict,
    customer_id: str
) -> bool:
    """Handle Stripe subscription webhook events"""

    # Find user by Stripe customer ID
    user = await db.users.find_one({"stripe_customer_id": customer_id})
    if not user:
        logger.warning(f"No user found for Stripe customer: {customer_id}")
        return False

    user_id = user["user_id"]
    now = datetime.now(timezone.utc)

    if event_type == "customer.subscription.created":
        # New subscription created
        plan = "yearly" if "year" in subscription_data.get("plan", {}).get("interval", "") else "monthly"
        await activate_subscription(
            db=db,
            user_id=user_id,
            plan=plan,
            provider="stripe",
            stripe_subscription_id=subscription_data.get("id")
        )
        return True

    elif event_type == "customer.subscription.updated":
        # Subscription updated (could be upgrade/downgrade)
        status = subscription_data.get("status")
        if status == "active":
            plan = "yearly" if "year" in subscription_data.get("plan", {}).get("interval", "") else "monthly"
            await activate_subscription(
                db=db,
                user_id=user_id,
                plan=plan,
                provider="stripe",
                stripe_subscription_id=subscription_data.get("id")
            )
        elif status in ["past_due", "unpaid"]:
            await db.users.update_one(
                {"user_id": user_id},
                {"$set": {"subscription_status": "past_due", "updated_at": now}}
            )
        return True

    elif event_type == "customer.subscription.deleted":
        # Subscription canceled or expired
        await db.users.update_one(
            {"user_id": user_id},
            {"$set": {
                "subscription_status": "expired",
                "stripe_subscription_id": None,
                "updated_at": now
            }}
        )
        return True

    elif event_type == "invoice.payment_succeeded":
        # Payment successful - extend subscription
        # The subscription.updated event will handle the actual update
        return True

    elif event_type == "invoice.payment_failed":
        # Payment failed
        await db.users.update_one(
            {"user_id": user_id},
            {"$set": {"subscription_status": "past_due", "updated_at": now}}
        )
        return True

    return False
