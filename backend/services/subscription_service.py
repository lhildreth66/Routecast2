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

logger = logging.getLogger(__name__)

# Subscription pricing
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
    """Check and update subscription status for a user"""
    user = await db.users.find_one({"user_id": user_id})
    if not user:
        return {"status": "inactive", "is_premium": False}

    now = datetime.now(timezone.utc)
    status = user.get("subscription_status", "inactive")
    expiration = user.get("subscription_expiration")

    # Check if subscription has expired
    if expiration and isinstance(expiration, datetime):
        # Make sure expiration is timezone-aware
        if expiration.tzinfo is None:
            expiration = expiration.replace(tzinfo=timezone.utc)
        if expiration < now and status in ["active", "trialing"]:
            # Subscription has expired
            await db.users.update_one(
                {"user_id": user_id},
                {"$set": {
                    "subscription_status": "expired",
                    "updated_at": now
                }}
            )
            status = "expired"

    is_premium = status in ["active", "trialing"]

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
            "subscription_status": "inactive",
            "subscription_plan": "free",
            "subscription_expiration": None,
            "updated_at": now
        }}
    )

    if reason:
        await db.subscription_logs.insert_one({
            "user_id": user_id,
            "action": "revoke",
            "reason": reason,
            "admin_action": True,
            "timestamp": now
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
