"""
Authentication Router for RouteCast
Handles signup, login, email verification, password reset, and user profile
"""
from fastapi import APIRouter, HTTPException, Depends, Header, Request, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import Optional
from datetime import datetime, timedelta, timezone
import os

from models.user import (
    UserCreate, UserLogin, UserResponse, UserMeResponse,
    TokenResponse, TokenRefreshRequest, PasswordResetRequest,
    PasswordResetConfirm, EmailVerificationRequest, ChangePasswordRequest,
    SubscriptionStatus, SubscriptionPlan,
    get_user_entitlements, user_is_premium
)
from services.auth_service import (
    create_tokens, verify_token, get_password_hash,
    verify_password, get_user_by_email, get_user_by_id,
    create_user, update_user, generate_verification_token,
    store_verification_token, verify_and_consume_token,
    authenticate_user
)
from services.email_service import (
    send_verification_email, send_password_reset_email, send_welcome_email
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


async def get_current_user(authorization: Optional[str] = Header(None)):
    """Dependency to get current authenticated user"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = authorization.split(" ")[1]
    payload = verify_token(token, "access")

    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return payload


async def get_current_user_optional(authorization: Optional[str] = Header(None)):
    """Optional authentication - returns None if not authenticated"""
    if not authorization or not authorization.startswith("Bearer "):
        return None

    token = authorization.split(" ")[1]
    payload = verify_token(token, "access")
    return payload


def get_db(request: Request):
    """Get database from app state"""
    return request.app.state.db


@router.post("/signup", response_model=TokenResponse)
async def signup(
    user_data: UserCreate,
    background_tasks: BackgroundTasks,
    request: Request
):
    """Register a new user"""
    try:
        db = get_db(request)

        existing_user = await get_user_by_email(db, user_data.email)
        if existing_user:
            raise HTTPException(status_code=400, detail="Email already registered")

        user = await create_user(db, user_data.email, user_data.password, user_data.name)

        verification_token = generate_verification_token()
        await store_verification_token(db, user["user_id"], verification_token, "email_verification", 24)

        background_tasks.add_task(
            send_verification_email,
            user_data.email,
            verification_token,
            user_data.name
        )

        access_token, refresh_token, expires_in = create_tokens(user["user_id"], user["email"])

        return JSONResponse(
            status_code=201,
            content={
                "access_token": access_token,
                "refresh_token": refresh_token,
                "expires_in": expires_in,
            },
        )
    except HTTPException as e:
        return JSONResponse(status_code=e.status_code, content={"detail": e.detail})
    except Exception as e:
        return JSONResponse(status_code=400, content={"detail": str(e)})


@router.post("/login", response_model=TokenResponse)
async def login(user_data: UserLogin, request: Request):
    """Login with email and password"""
    db = get_db(request)

    user = await authenticate_user(db, user_data.email, user_data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Generate tokens
    access_token, refresh_token, expires_in = create_tokens(user["user_id"], user["email"])

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(token_data: TokenRefreshRequest, request: Request):
    """Refresh access token using refresh token"""
    db = get_db(request)

    payload = verify_token(token_data.refresh_token, "refresh")
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    user_id = payload.get("sub")
    email = payload.get("email")

    # Verify user still exists
    user = await get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    # Generate new tokens
    access_token, refresh_token, expires_in = create_tokens(user_id, email)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in
    )


@router.post("/verify-email")
async def verify_email(
    data: EmailVerificationRequest,
    background_tasks: BackgroundTasks,
    request: Request
):
    """Verify email address with token"""
    db = get_db(request)

    user_id = await verify_and_consume_token(db, data.token, "email_verification")
    if not user_id:
        # Idempotency: check if this is an already-consumed token for a user
        # who is already verified (e.g. clicking the same link twice).
        old_token_doc = await db.verification_tokens.find_one({
            "token": data.token,
            "token_type": "email_verification",
        })
        if old_token_doc and old_token_doc.get("used"):
            existing_user = await get_user_by_id(db, old_token_doc["user_id"])
            if existing_user and existing_user.get("email_verified"):
                return {"message": "Email already verified"}
        raise HTTPException(status_code=400, detail="Invalid or expired verification token")

    # Mark email as verified
    user = await get_user_by_id(db, user_id)
    await update_user(db, user_id, {"email_verified": True})

    # Send welcome email
    background_tasks.add_task(
        send_welcome_email,
        user["email"],
        user.get("name")
    )

    return {"message": "Email verified successfully"}


@router.post("/resend-verification")
async def resend_verification(
    background_tasks: BackgroundTasks,
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """Resend email verification link"""
    db = get_db(request)

    user_id = current_user.get("sub")
    user = await get_user_by_id(db, user_id)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.get("email_verified"):
        raise HTTPException(status_code=400, detail="Email already verified")

    # Generate new verification token
    verification_token = generate_verification_token()
    await store_verification_token(db, user_id, verification_token, "email_verification", 24)

    # Send verification email
    background_tasks.add_task(
        send_verification_email,
        user["email"],
        verification_token,
        user.get("name")
    )

    return {"message": "Verification email sent"}


@router.post("/forgot-password")
async def forgot_password(
    data: PasswordResetRequest,
    background_tasks: BackgroundTasks,
    request: Request
):
    """Request password reset link"""
    db = get_db(request)

    user = await get_user_by_email(db, data.email)

    # Always return success to prevent email enumeration
    if user:
        # Generate reset token
        reset_token = generate_verification_token()
        await store_verification_token(db, user["user_id"], reset_token, "password_reset", 1)  # 1 hour expiry

        # Send reset email
        background_tasks.add_task(
            send_password_reset_email,
            user["email"],
            reset_token,
            user.get("name")
        )

    return {"message": "If that email exists, a password reset link has been sent"}


@router.post("/reset-password")
async def reset_password(data: PasswordResetConfirm, request: Request):
    """Reset password with token"""
    db = get_db(request)

    user_id = await verify_and_consume_token(db, data.token, "password_reset")
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    # Update password
    hashed_password = get_password_hash(data.new_password)
    await update_user(db, user_id, {"hashed_password": hashed_password})

    return {"message": "Password reset successfully"}


@router.post("/change-password")
async def change_password(
    data: ChangePasswordRequest,
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """Change password for authenticated user"""
    db = get_db(request)

    user_id = current_user.get("sub")
    user = await get_user_by_id(db, user_id)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Verify current password
    if not verify_password(data.current_password, user["hashed_password"]):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    # Update password
    hashed_password = get_password_hash(data.new_password)
    await update_user(db, user_id, {"hashed_password": hashed_password})

    return {"message": "Password changed successfully"}


@router.get("/me", response_model=UserMeResponse)
async def get_me(request: Request, current_user: dict = Depends(get_current_user)):
    """Get current user profile and subscription status"""
    db = get_db(request)

    user_id = current_user.get("sub")
    user = await get_user_by_id(db, user_id)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check subscription status
    from services.subscription_service import check_subscription_status
    sub_status = await check_subscription_status(db, user_id)

    # Calculate trial availability
    trial_available = not user.get("trial_used", False) and sub_status["status"] == "inactive"

    # Calculate trial days remaining
    trial_days_remaining = None
    if sub_status["status"] == "trialing" and user.get("trial_end"):
        trial_end = user["trial_end"]
        if isinstance(trial_end, datetime):
            # Make sure trial_end is timezone-aware
            if trial_end.tzinfo is None:
                trial_end = trial_end.replace(tzinfo=timezone.utc)
            remaining = (trial_end - datetime.now(timezone.utc)).days
            trial_days_remaining = max(0, remaining)

    # Get entitlements based on subscription
    class MockUser:
        def __init__(self, user_dict, sub_status):
            self.subscription_status = SubscriptionStatus(sub_status["status"]) if sub_status["status"] in [s.value for s in SubscriptionStatus] else SubscriptionStatus.INACTIVE
            self.subscription_plan = SubscriptionPlan(sub_status["plan"]) if sub_status["plan"] in [p.value for p in SubscriptionPlan] else SubscriptionPlan.FREE

    mock_user = MockUser(user, sub_status)
    entitlements = get_user_entitlements(mock_user)
    is_premium = user_is_premium(mock_user)

    return UserMeResponse(
        user_id=user["user_id"],
        email=user["email"],
        name=user.get("name"),
        email_verified=user.get("email_verified", False),
        created_at=user["created_at"],
        subscription_status=SubscriptionStatus(sub_status["status"]) if sub_status["status"] in [s.value for s in SubscriptionStatus] else SubscriptionStatus.INACTIVE,
        subscription_plan=SubscriptionPlan(sub_status["plan"]) if sub_status["plan"] in [p.value for p in SubscriptionPlan] else SubscriptionPlan.FREE,
        subscription_provider=sub_status.get("provider"),
        subscription_expiration=sub_status.get("expiration"),
        is_premium=is_premium,
        entitlements=entitlements,
        trial_available=trial_available,
        trial_days_remaining=trial_days_remaining
    )


@router.post("/logout")
async def logout(current_user: dict = Depends(get_current_user)):
    """Logout user (client should discard tokens)"""
    # In a more advanced implementation, you could blacklist the token
    return {"message": "Logged out successfully"}
