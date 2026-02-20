"""
Admin Router for RouteCast
Handles admin operations for user and subscription management
"""
from fastapi import APIRouter, HTTPException, Depends, Header, Request, Query
from typing import Optional, List
from datetime import datetime, timezone
import os

from models.user import (
    UserResponse, AdminUserListResponse,
    AdminGrantSubscriptionRequest, AdminRevokeSubscriptionRequest,
    SubscriptionStatus, SubscriptionPlan
)
from services.subscription_service import grant_subscription, revoke_subscription
from routers.auth import get_current_user, get_db

router = APIRouter(prefix="/admin", tags=["Admin"])

# Simple admin authentication - in production use proper RBAC
ADMIN_API_KEY = os.environ.get('ADMIN_API_KEY', 'routecast-admin-key-2025')


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
