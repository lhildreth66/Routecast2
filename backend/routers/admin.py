"""
Admin Router for RouteCast
Handles admin operations for user and subscription management
"""
from fastapi import APIRouter, HTTPException, Depends, Header, Request, Query
from typing import Optional, List
from datetime import datetime, timezone
import os
import logging
import stripe

from models.user import (
    UserResponse, AdminUserListResponse,
    AdminGrantSubscriptionRequest, AdminRevokeSubscriptionRequest,
    SubscriptionStatus, SubscriptionPlan
)
from services.subscription_service import grant_subscription, revoke_subscription, PREMIUM_STATUSES
from routers.auth import get_current_user, get_db

router = APIRouter(prefix="/admin", tags=["Admin"])
logger = logging.getLogger(__name__)

# Simple admin authentication - in production use proper RBAC
ADMIN_API_KEY = os.environ.get('ADMIN_API_KEY') or os.environ.get('ADMIN_TOKEN', 'routecast-admin-key-2025')

_STRIPE_API_KEY = os.environ.get('STRIPE_API_KEY', '')
if _STRIPE_API_KEY:
    stripe.api_key = _STRIPE_API_KEY


async def verify_admin(x_admin_key: Optional[str] = Header(None)):
    """Verify admin API key"""
    if not x_admin_key or x_admin_key != ADMIN_API_KEY:
        raise HTTPException(status_code=403, detail="Admin access required")
    return True


@router.get("/users", response_model=AdminUserListResponse)
async def list_users(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    subscription_status: Optional[str] = None,
    admin: bool = Depends(verify_admin)
):
    """List all users with pagination and filtering"""
    db = get_db(request)

    # Build query
    query = {}
    if search:
        query["$or"] = [
            {"email": {"$regex": search, "$options": "i"}},
            {"name": {"$regex": search, "$options": "i"}}
        ]
    if subscription_status:
        query["subscription_status"] = subscription_status

    # Get total count
    total = await db.users.count_documents(query)

    # Get paginated results
    skip = (page - 1) * per_page
    cursor = db.users.find(query, {"hashed_password": 0}).skip(skip).limit(per_page).sort("created_at", -1)
    users = await cursor.to_list(length=per_page)

    # Format response
    user_responses = []
    for user in users:
        user_responses.append(UserResponse(
            user_id=user["user_id"],
            email=user["email"],
            name=user.get("name"),
            email_verified=user.get("email_verified", False),
            created_at=user["created_at"],
            subscription_status=SubscriptionStatus(user.get("subscription_status", "inactive")),
            subscription_plan=SubscriptionPlan(user.get("subscription_plan", "free")),
            subscription_provider=user.get("subscription_provider"),
            subscription_expiration=user.get("subscription_expiration"),
            is_premium=user.get("subscription_status") in ["active", "trialing"]
        ))

    return AdminUserListResponse(
        users=user_responses,
        total=total,
        page=page,
        per_page=per_page
    )


@router.get("/users/{user_id}")
async def get_user_details(
    user_id: str,
    request: Request,
    admin: bool = Depends(verify_admin)
):
    """Get detailed user information"""
    db = get_db(request)

    user = await db.users.find_one({"user_id": user_id}, {"hashed_password": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get subscription logs
    logs_cursor = db.subscription_logs.find({"user_id": user_id}).sort("timestamp", -1).limit(20)
    logs = await logs_cursor.to_list(length=20)

    # Get payment transactions
    transactions_cursor = db.payment_transactions.find({"user_id": user_id}).sort("created_at", -1).limit(20)
    transactions = await transactions_cursor.to_list(length=20)

    # Convert ObjectId to string for JSON serialization
    for log in logs:
        log["_id"] = str(log["_id"])
    for tx in transactions:
        tx["_id"] = str(tx["_id"])

    user["_id"] = str(user.get("_id", ""))

    return {
        "user": user,
        "subscription_logs": logs,
        "payment_transactions": transactions
    }


@router.post("/users/{user_id}/grant-subscription")
async def admin_grant_subscription(
    user_id: str,
    data: AdminGrantSubscriptionRequest,
    request: Request,
    admin: bool = Depends(verify_admin)
):
    """Grant subscription to a user"""
    db = get_db(request)

    if data.user_id != user_id:
        raise HTTPException(status_code=400, detail="User ID mismatch")

    # Verify user exists
    user = await db.users.find_one({"user_id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    success = await grant_subscription(
        db=db,
        user_id=user_id,
        plan=data.plan.value,
        duration_days=data.duration_days,
        reason=data.reason
    )

    if not success:
        raise HTTPException(status_code=500, detail="Failed to grant subscription")

    return {
        "message": f"Subscription granted: {data.plan.value} for {data.duration_days} days",
        "user_id": user_id
    }


@router.post("/users/{user_id}/revoke-subscription")
async def admin_revoke_subscription(
    user_id: str,
    data: AdminRevokeSubscriptionRequest,
    request: Request,
    admin: bool = Depends(verify_admin)
):
    """Revoke subscription from a user"""
    db = get_db(request)

    if data.user_id != user_id:
        raise HTTPException(status_code=400, detail="User ID mismatch")

    # Verify user exists
    user = await db.users.find_one({"user_id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    success = await revoke_subscription(
        db=db,
        user_id=user_id,
        reason=data.reason
    )

    if not success:
        raise HTTPException(status_code=500, detail="Failed to revoke subscription")

    return {
        "message": "Subscription revoked",
        "user_id": user_id
    }


@router.get("/stats")
async def get_admin_stats(
    request: Request,
    admin: bool = Depends(verify_admin)
):
    """Get overall platform statistics"""
    db = get_db(request)

    now = datetime.now(timezone.utc)

    # Total users
    total_users = await db.users.count_documents({})

    # Verified users
    verified_users = await db.users.count_documents({"email_verified": True})

    # Subscription counts
    active_subs = await db.users.count_documents({"subscription_status": "active"})
    trialing_subs = await db.users.count_documents({"subscription_status": "trialing"})

    # By provider
    stripe_subs = await db.users.count_documents({"subscription_provider": "stripe", "subscription_status": "active"})
    apple_subs = await db.users.count_documents({"subscription_provider": "apple", "subscription_status": "active"})
    google_subs = await db.users.count_documents({"subscription_provider": "google", "subscription_status": "active"})
    admin_subs = await db.users.count_documents({"subscription_provider": "admin", "subscription_status": "active"})

    # By plan
    monthly_subs = await db.users.count_documents({"subscription_plan": "monthly", "subscription_status": {"$in": ["active", "trialing"]}})
    yearly_subs = await db.users.count_documents({"subscription_plan": "yearly", "subscription_status": {"$in": ["active", "trialing"]}})

    return {
        "total_users": total_users,
        "verified_users": verified_users,
        "active_subscriptions": active_subs,
        "trialing_users": trialing_subs,
        "subscriptions_by_provider": {
            "stripe": stripe_subs,
            "apple": apple_subs,
            "google": google_subs,
            "admin": admin_subs
        },
        "subscriptions_by_plan": {
            "monthly": monthly_subs,
            "yearly": yearly_subs
        },
        "timestamp": now.isoformat()
    }


@router.get("/subscription-logs")
async def get_subscription_logs(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    admin: bool = Depends(verify_admin)
):
    """Get all subscription activity logs"""
    db = get_db(request)

    total = await db.subscription_logs.count_documents({})
    skip = (page - 1) * per_page

    cursor = db.subscription_logs.find({}).skip(skip).limit(per_page).sort("timestamp", -1)
    logs = await cursor.to_list(length=per_page)

    # Convert ObjectId to string
    for log in logs:
        log["_id"] = str(log["_id"])

    return {
        "logs": logs,
        "total": total,
        "page": page,
        "per_page": per_page
    }


# STRIPE DISABLED - Google Play submission - do not delete
@router.post("/reconcile-subscriptions")
async def reconcile_subscriptions(
    request: Request,
    dry_run: bool = Query(False, description="If true, report discrepancies without writing changes"),
    admin: bool = Depends(verify_admin),
):
    """
    Reconcile all users whose DB state says is_premium=True against Stripe.

    Checks every user who:
      - has is_premium=True in the DB, OR
      - has a subscription_status that implies access (active / trialing / canceling)

    For each user with a stripe_subscription_id, fetches the live Stripe subscription
    and fixes any discrepancy (missed/delayed webhooks, stale data).

    Use dry_run=true to preview what would change without writing to the DB.
    """
    if not _STRIPE_API_KEY:
        raise HTTPException(status_code=503, detail="Stripe API key not configured")

    db = get_db(request)
    now = datetime.now(timezone.utc)

    # Candidate users: anyone the DB currently thinks is premium
    cursor = db.users.find(
        {"$or": [
            {"is_premium": True},
            {"subscription_status": {"$in": list(PREMIUM_STATUSES)}},
        ]},
        {"hashed_password": 0},
    )
    candidates = await cursor.to_list(length=None)

    results: list = []
    fixed = 0
    errors = 0

    for user in candidates:
        user_id = user.get("user_id", "?")
        email = user.get("email", "?")
        db_status = user.get("subscription_status", "inactive")
        db_is_premium = user.get("is_premium", False)
        stripe_sub_id = user.get("stripe_subscription_id")
        stripe_customer_id = user.get("stripe_customer_id")
        provider = user.get("subscription_provider", "")

        # ── Case: has a subscription ID — check it directly ──────────────
        if stripe_sub_id:
            try:
                sub = stripe.Subscription.retrieve(stripe_sub_id)  # type: ignore[attr-defined]
                s_status = sub["status"]
                s_period_end = sub.get("current_period_end")
                s_cancel_at = sub.get("cancel_at_period_end", False)

                if s_status == "active" and s_cancel_at:
                    internal = "canceling"
                else:
                    internal = s_status

                if internal in ("active", "trialing"):
                    correct_premium = True
                elif internal == "canceling":
                    exp = datetime.fromtimestamp(s_period_end, tz=timezone.utc) if s_period_end else None
                    correct_premium = bool(exp and exp > now)
                else:
                    correct_premium = False

                needs_fix = (db_status != internal) or (db_is_premium != correct_premium)

                entry = {
                    "user_id": user_id,
                    "email": email,
                    "stripe_subscription_id": stripe_sub_id,
                    "db_status": db_status,
                    "stripe_status": s_status,
                    "internal_status": internal,
                    "db_is_premium": db_is_premium,
                    "correct_is_premium": correct_premium,
                    "needs_fix": needs_fix,
                    "action": "no_change",
                }

                if needs_fix and not dry_run:
                    update: dict = {
                        "subscription_status": internal,
                        "is_premium": correct_premium,
                        "stripe_status_verified_at": now,
                        "updated_at": now,
                    }
                    if s_period_end:
                        update["subscription_expiration"] = datetime.fromtimestamp(
                            s_period_end, tz=timezone.utc
                        )
                    if not correct_premium:
                        update["subscription_plan"] = "free"
                        update["plan"] = "free"

                    await db.users.update_one({"user_id": user_id}, {"$set": update})
                    await db.subscription_logs.insert_one({
                        "user_id": user_id,
                        "action": "reconciled",
                        "old_status": db_status,
                        "new_status": internal,
                        "old_is_premium": db_is_premium,
                        "new_is_premium": correct_premium,
                        "stripe_status": s_status,
                        "provider": "stripe",
                        "admin_action": True,
                        "timestamp": now,
                    })
                    entry["action"] = "fixed"
                    fixed += 1
                    logger.info(
                        f"[RECONCILE] user={user_id} email={email} "
                        f"{db_status}/{db_is_premium} → {internal}/{correct_premium}"
                    )
                elif needs_fix:
                    entry["action"] = "would_fix"

                results.append(entry)

            except stripe.error.InvalidRequestError:  # type: ignore[attr-defined]
                # Subscription ID doesn't exist in Stripe at all — revoke
                entry = {
                    "user_id": user_id, "email": email,
                    "stripe_subscription_id": stripe_sub_id,
                    "db_status": db_status, "db_is_premium": db_is_premium,
                    "stripe_status": "not_found", "correct_is_premium": False,
                    "needs_fix": db_is_premium,
                    "action": "no_change",
                }
                if db_is_premium and not dry_run:
                    await db.users.update_one(
                        {"user_id": user_id},
                        {"$set": {
                            "is_premium": False,
                            "subscription_status": "inactive",
                            "subscription_plan": "free",
                            "plan": "free",
                            "stripe_subscription_id": None,
                            "stripe_status_verified_at": now,
                            "updated_at": now,
                        }},
                    )
                    await db.subscription_logs.insert_one({
                        "user_id": user_id, "action": "reconciled",
                        "old_status": db_status, "new_status": "inactive",
                        "old_is_premium": True, "new_is_premium": False,
                        "stripe_status": "not_found",
                        "reason": f"subscription_id_not_found:{stripe_sub_id}",
                        "admin_action": True, "timestamp": now,
                    })
                    entry["action"] = "fixed"
                    fixed += 1
                    logger.info(f"[RECONCILE] revoked user={user_id} — sub {stripe_sub_id} not found in Stripe")
                elif db_is_premium:
                    entry["action"] = "would_fix"
                results.append(entry)

            except Exception as e:
                logger.error(f"[RECONCILE] error for user={user_id}: {e}")
                errors += 1
                results.append({
                    "user_id": user_id, "email": email,
                    "action": "error", "error": str(e), "db_status": db_status,
                })
            continue

        # ── Case: NO subscription ID in DB — check Stripe by customer ID ─
        # This covers Megan's exact scenario: is_premium=True but no sub ID.
        # Skip non-Stripe providers (admin grants, Apple, Google — handled elsewhere).
        if provider in ("apple", "google", "admin"):
            results.append({
                "user_id": user_id, "email": email,
                "action": "skipped",
                "reason": f"provider={provider} (non-Stripe, skip)",
                "db_status": db_status,
            })
            continue
        # provider is "stripe" OR None/unset — treat both as potentially Stripe

        # Look up all subscriptions for this customer in Stripe
        live_sub_id: Optional[str] = None
        live_sub_status: str = "not_found"
        if stripe_customer_id and _STRIPE_API_KEY:
            try:
                subs = stripe.Subscription.list(  # type: ignore[attr-defined]
                    customer=stripe_customer_id, limit=10
                )
                for s in (subs.get("data") or []):
                    if s.get("status") in ("active", "trialing", "past_due"):
                        live_sub_id = s["id"]
                        live_sub_status = s["status"]
                        break
            except Exception as e:
                logger.error(f"[RECONCILE] Stripe list error for user={user_id}: {e}")
                errors += 1
                results.append({
                    "user_id": user_id, "email": email,
                    "action": "error", "error": str(e), "db_status": db_status,
                })
                continue

        entry = {
            "user_id": user_id, "email": email,
            "stripe_customer_id": stripe_customer_id,
            "stripe_subscription_id": None,
            "db_status": db_status, "db_is_premium": db_is_premium,
            "stripe_status": live_sub_status,
            "correct_is_premium": live_sub_id is not None,
            "needs_fix": True,  # always needs fixing when sub_id is missing and db is premium
            "action": "no_change",
        }

        if live_sub_id:
            # Re-link the discovered subscription ID
            if not dry_run:
                await db.users.update_one(
                    {"user_id": user_id},
                    {"$set": {"stripe_subscription_id": live_sub_id, "updated_at": now}},
                )
                entry["action"] = "linked_subscription"
                entry["linked_subscription_id"] = live_sub_id
                fixed += 1
                logger.info(f"[RECONCILE] Re-linked sub {live_sub_id} to user={user_id}")
            else:
                entry["action"] = "would_link"
        else:
            # Stripe has no subscription for this customer → revoke
            if not dry_run:
                await db.users.update_one(
                    {"user_id": user_id},
                    {"$set": {
                        "is_premium": False,
                        "subscription_status": "inactive",
                        "subscription_plan": "free",
                        "plan": "free",
                        "subscription_expiration": None,
                        "stripe_status_verified_at": now,
                        "updated_at": now,
                    }},
                )
                await db.subscription_logs.insert_one({
                    "user_id": user_id, "action": "reconciled",
                    "old_status": db_status, "new_status": "inactive",
                    "old_is_premium": True, "new_is_premium": False,
                    "stripe_status": "no_subscription_in_stripe",
                    "reason": "no_active_subscription_for_customer",
                    "admin_action": True, "timestamp": now,
                })
                entry["action"] = "fixed"
                fixed += 1
                logger.info(
                    f"[RECONCILE] revoked user={user_id} email={email} — "
                    f"no Stripe subscription found for customer={stripe_customer_id}"
                )
            else:
                entry["action"] = "would_fix"

        results.append(entry)

    return {
        "dry_run": dry_run,
        "candidates_checked": len(candidates),
        "fixed": fixed if not dry_run else 0,
        "would_fix": sum(1 for r in results if r.get("action") == "would_fix"),
        "errors": errors,
        "timestamp": now.isoformat(),
        "results": results,
    }


@router.post("/setup-reviewer-account")
async def setup_reviewer_account(
    request: Request,
    admin: bool = Depends(verify_admin),
):
    """
    One-time setup: create or fix the Apple/Google review demo account.
    Sets email_verified=True, subscription_status=active, is_premium=True
    with expiration 2027-06-30. Safe to call multiple times (idempotent).
    """
    from services.auth_service import create_user, get_password_hash
    db = get_db(request)

    REVIEWER_EMAIL = "appreview@routecastweather.com"
    REVIEWER_PASSWORD = "RouteCast2026!"
    REVIEWER_NAME = "Apple App Review"
    EXPIRATION = datetime(2027, 6, 30, 23, 59, 59, tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)
    hashed_pw = get_password_hash(REVIEWER_PASSWORD)

    # Check if account already exists
    existing = await db.users.find_one({"email": REVIEWER_EMAIL})

    if existing:
        user_id = existing["user_id"]
        action = "updated"
    else:
        # Create new user document
        import uuid
        user_id = str(uuid.uuid4())
        await db.users.insert_one({
            "user_id": user_id,
            "email": REVIEWER_EMAIL,
            "name": REVIEWER_NAME,
            "hashed_password": hashed_pw,
            "email_verified": True,
            "created_at": now,
            "updated_at": now,
            "subscription_status": "active",
            "subscription_provider": "admin",
            "subscription_plan": "yearly",
            "subscription_expiration": EXPIRATION,
            "is_premium": True,
            "stripe_subscription_id": None,
            "stripe_customer_id": None,
        })
        action = "created"

    # Always apply the full desired state (idempotent)
    await db.users.update_one(
        {"user_id": user_id},
        {"$set": {
            "hashed_password": hashed_pw,
            "name": REVIEWER_NAME,
            "email_verified": True,
            "subscription_status": "active",
            "subscription_provider": "admin",
            "subscription_plan": "yearly",
            "subscription_expiration": EXPIRATION,
            "is_premium": True,
            "updated_at": now,
        }}
    )

    # Log the action
    await db.subscription_logs.insert_one({
        "user_id": user_id,
        "action": "reviewer_account_setup",
        "new_status": "active",
        "new_is_premium": True,
        "subscription_expiration": EXPIRATION,
        "admin_action": True,
        "timestamp": now,
    })

    logger.info(f"[REVIEWER SETUP] {action} reviewer account user_id={user_id} email={REVIEWER_EMAIL}")

    return {
        "action": action,
        "user_id": user_id,
        "email": REVIEWER_EMAIL,
        "email_verified": True,
        "subscription_status": "active",
        "subscription_plan": "yearly",
        "subscription_provider": "admin",
        "is_premium": True,
        "subscription_expiration": EXPIRATION.isoformat(),
        "timestamp": now.isoformat(),
    }