"""
Authentication Router for RouteCast
Handles signup, login, email verification, password reset, and user profile.

Flow:  signup → verify-email (302 → Stripe Checkout) → /welcome (activate + JWT)
"""
from fastapi import APIRouter, HTTPException, Depends, Header, Request, BackgroundTasks
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta, timezone
import logging
import os
import stripe as stripe_module

logger = logging.getLogger(__name__)

from models.user import (
    UserCreate, UserLogin, UserResponse, UserMeResponse,
    TokenResponse, TokenRefreshRequest, PasswordResetRequest,
    PasswordResetConfirm, ChangePasswordRequest,
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
    send_verification_email, send_password_reset_email
)

router = APIRouter(prefix="/auth", tags=["Authentication"])

# ── Stripe config ────────────────────────────────────────────────────────────
STRIPE_API_KEY = os.environ.get("STRIPE_API_KEY", "")
STRIPE_PRICE_MONTHLY = os.environ.get("STRIPE_PRICE_MONTHLY", "")
STRIPE_PRICE_YEARLY = os.environ.get("STRIPE_PRICE_YEARLY", "")
FRONTEND_URL = (
    os.environ.get("FRONTEND_URL")
    or os.environ.get("APP_URL")
    or "https://routecastweather.com"
)

if STRIPE_API_KEY:
    stripe_module.api_key = STRIPE_API_KEY


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


@router.post("/signup")
async def signup(
    user_data: UserCreate,
    background_tasks: BackgroundTasks,
    request: Request
):
    """Register a new user.

    Creates the account as *pending verification* and sends a verification
    email.  Does **not** log the user in — no JWT tokens are returned.
    """
    try:
        db = get_db(request)

        existing_user = await get_user_by_email(db, user_data.email)
        if existing_user:
            raise HTTPException(status_code=400, detail="Email already registered")

        # Normalize plan to "monthly" or "yearly"
        plan = (getattr(user_data, 'plan', None) or 'monthly').lower()
        if plan not in ('monthly', 'yearly'):
            plan = 'monthly'

        user = await create_user(db, user_data.email, user_data.password, user_data.name, pending_plan=plan)

        verification_token = generate_verification_token()
        await store_verification_token(db, user["user_id"], verification_token, "email_verification", 24)

        background_tasks.add_task(
            send_verification_email,
            user_data.email,
            verification_token,
            user_data.name
        )

        return JSONResponse(
            status_code=201,
            content={"message": "Check your email to verify your account."},
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


from fastapi import Query as FastQuery   # avoid shadowing


@router.get("/verify-email")
async def verify_email_get(
    background_tasks: BackgroundTasks,
    request: Request,
    token: Optional[str] = FastQuery(None, alias="token"),
    t: Optional[str] = FastQuery(None, alias="t"),
):
    """Verify email via GET — primary path triggered by clicking the link.

    On success: creates a Stripe Customer + Checkout Session and returns
    an HTTP 302 redirect to the Stripe-hosted checkout page.
    On failure: 302 redirect back to the frontend with an ``error`` query
    param so the page can show a friendly message.
    """
    raw = (token or t or "").strip()
    return await _verify_email_with_token(raw, background_tasks, request)


# ── Helper: create Stripe Checkout Session ───────────────────────────────────

async def _create_stripe_checkout_for_user(db, user_id: str, user: dict):
    """Create a Stripe Customer (if needed) and Checkout Session.

    Reads ``pending_plan`` from the user record to pick the correct price.
    Returns ``(checkout_url, error_message)``.
    """
    email = user["email"]
    name = user.get("name")
    customer_id = user.get("stripe_customer_id")
    pending_plan = user.get("pending_plan", "monthly")

    try:
        # Re-use existing Stripe customer if present (idempotent retry)
        if not customer_id:
            customer = stripe_module.Customer.create(
                email=email,
                name=name,
                metadata={"user_id": user_id, "email": email},
            )
            customer_id = customer.id
            await update_user(db, user_id, {"stripe_customer_id": customer_id})
            logger.info(f"[VERIFY] Stripe customer created: {customer_id} for user={user_id}")

        # Pick the correct price based on the user's chosen plan
        if pending_plan == "yearly" and STRIPE_PRICE_YEARLY:
            price_id = STRIPE_PRICE_YEARLY
        else:
            price_id = STRIPE_PRICE_MONTHLY

        if not price_id:
            logger.error(f"[VERIFY] Stripe price not configured for plan={pending_plan}")
            return None, "Billing is not configured. Please contact support."

        logger.info(f"[VERIFY] Using plan={pending_plan} price_id={price_id} for user={user_id}")

        session = stripe_module.checkout.Session.create(
            customer=customer_id,
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            subscription_data={"trial_period_days": 7},
            payment_method_collection="always",
            success_url=f"{FRONTEND_URL}/welcome?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{FRONTEND_URL}/signup",
        )
        logger.info(f"[VERIFY] Checkout session created: {session.id} for user={user_id}")
        return session.url, None

    except stripe_module.error.StripeError as e:
        logger.error(f"[VERIFY] Stripe error for user={user_id}: {e}")
        return None, "Unable to start checkout. Please try again later."
    except Exception as e:
        logger.error(f"[VERIFY] Unexpected error creating checkout for user={user_id}: {e}")
        return None, "Unable to start checkout. Please try again later."


# ── Failure-redirect URL ─────────────────────────────────────────────────────
_ERROR_REDIRECT = f"{FRONTEND_URL}/signup?error=invalid_token"


async def _verify_email_with_token(
    token: str,
    background_tasks: BackgroundTasks,
    request: Request,
):
    """Verify the email token, create a Stripe Checkout Session, and 302-redirect.

    Only two possible responses:
      • 302 → Stripe checkout URL  (success)
      • 302 → /signup?error=invalid_token  (any failure)

    Never returns JSON.
    """
    db = get_db(request)

    # ── Step 1: diagnostic logging ───────────────────────────────────────
    safe_preview = f"{token[:6]}...{token[-6:]}" if len(token) >= 12 else "<short>"
    logger.info(
        f"[VERIFY-EMAIL] path={request.url.path} "
        f"query_keys={list(request.query_params.keys())} "
        f"token_present={bool(token)} "
        f"token_len={len(token)} "
        f"token_head={token[:6] if token else None} "
        f"token_tail={token[-6:] if token else None}"
    )

    if not token:
        logger.warning("[VERIFY-EMAIL] FAIL bucket=MISSING — no token supplied")
        return RedirectResponse(url=_ERROR_REDIRECT, status_code=302)

    # ── Step 2: consume the token ────────────────────────────────────────
    user_id = await verify_and_consume_token(db, token, "email_verification")

    if not user_id:
        # ── Idempotency: already-consumed token → retry checkout ─────────
        old_token_doc = await db.verification_tokens.find_one({
            "token": token,
            "token_type": "email_verification",
        })
        if old_token_doc and old_token_doc.get("used"):
            existing_user = await get_user_by_id(db, old_token_doc["user_id"])
            if existing_user and existing_user.get("email_verified"):
                logger.info(
                    f"[VERIFY-EMAIL] idempotent retry — already verified "
                    f"user={old_token_doc['user_id']}"
                )
                checkout_url, err = await _create_stripe_checkout_for_user(
                    db, old_token_doc["user_id"], existing_user,
                )
                if err:
                    logger.error(f"[VERIFY-EMAIL] Stripe checkout failed on retry: {err}")
                    return RedirectResponse(url=_ERROR_REDIRECT, status_code=302)
                return RedirectResponse(url=checkout_url, status_code=302)
            logger.warning(
                f"[VERIFY-EMAIL] FAIL bucket=ALREADY_USED "
                f"user={old_token_doc['user_id']} preview={safe_preview}"
            )
        elif old_token_doc:
            logger.warning(
                f"[VERIFY-EMAIL] FAIL bucket=EXPIRED "
                f"user={old_token_doc.get('user_id')} "
                f"expires_at={old_token_doc.get('expires_at')} "
                f"preview={safe_preview}"
            )
        else:
            logger.warning(
                f"[VERIFY-EMAIL] FAIL bucket=NOT_FOUND "
                f"preview={safe_preview}"
            )
        return RedirectResponse(url=_ERROR_REDIRECT, status_code=302)

    # ── Step 3: mark the user as verified ────────────────────────────────
    user = await get_user_by_id(db, user_id)
    if not user:
        logger.warning(f"[VERIFY-EMAIL] FAIL bucket=USER_MISMATCH user_id={user_id}")
        return RedirectResponse(url=_ERROR_REDIRECT, status_code=302)

    await update_user(db, user_id, {"email_verified": True})
    logger.info(
        f"[VERIFY-EMAIL] SUCCESS user_id={user_id} "
        f"email={user.get('email', 'unknown')}"
    )

    # ── Step 4: Stripe Customer + Checkout Session → 302 redirect ────────
    # NOTE: The "You're All Set" welcome email is NOT sent here.
    # It is sent later by the Stripe webhook (checkout.session.completed)
    # after the user has actually completed payment/trial signup.
    checkout_url, err = await _create_stripe_checkout_for_user(db, user_id, user)
    if err:
        logger.error(f"[VERIFY-EMAIL] Stripe checkout creation failed: {err}")
        return RedirectResponse(url=_ERROR_REDIRECT, status_code=302)

    return RedirectResponse(url=checkout_url, status_code=302)


class ResendVerificationRequest(BaseModel):
    email: str


@router.post("/resend-verification")
async def resend_verification(
    body: ResendVerificationRequest,
    background_tasks: BackgroundTasks,
    request: Request,
):
    """Resend email verification link.

    Does **not** require authentication (the user is not logged in after
    signup).  Accepts ``email`` in the request body and always returns the
    same message to prevent email enumeration.
    """
    db = get_db(request)
    email = (body.email or "").strip().lower()

    if not email:
        raise HTTPException(status_code=400, detail="Email is required")

    user = await get_user_by_email(db, email)

    if user and not user.get("email_verified"):
        user_id = user["user_id"]

        # Invalidate all previous unused verification tokens for this user
        now = datetime.now(timezone.utc)
        invalidated = await db.verification_tokens.update_many(
            {"user_id": user_id, "token_type": "email_verification", "used": False},
            {"$set": {"used": True, "invalidated_by_resend": True, "invalidated_at": now}},
        )
        logger.info(
            f"[RESEND-VERIFY] user_id={user_id} invalidated {invalidated.modified_count} old token(s)"
        )

        verification_token = generate_verification_token()
        await store_verification_token(db, user_id, verification_token, "email_verification", 24)

        background_tasks.add_task(
            send_verification_email,
            user["email"],
            verification_token,
            user.get("name"),
        )

    # Always return same message — prevents email enumeration
    return {
        "message": "If that email is registered and unverified, a new verification link has been sent.",
    }


# ── Welcome endpoint — post-Stripe activation ───────────────────────────────


class WelcomeRequest(BaseModel):
    session_id: str


@router.post("/welcome")
async def welcome(body: WelcomeRequest, request: Request):
    """Validate a Stripe Checkout session, activate the user's trial
    subscription, and return JWT tokens (first login).

    Called by the ``/welcome`` frontend page after Stripe redirects back.
    """
    db = get_db(request)
    session_id = (body.session_id or "").strip()

    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")

    # ── Retrieve checkout session from Stripe ────────────────────────────
    try:
        session = stripe_module.checkout.Session.retrieve(session_id)
    except stripe_module.error.StripeError as e:
        logger.error(f"[WELCOME] Stripe session retrieve failed: {e}")
        raise HTTPException(status_code=400, detail="Invalid checkout session")

    customer_id = session.get("customer")
    subscription_id = session.get("subscription")

    if not customer_id:
        raise HTTPException(status_code=400, detail="No customer associated with this session")

    # ── Find user by stripe_customer_id ──────────────────────────────────
    user = await db.users.find_one({"stripe_customer_id": customer_id})
    if not user:
        # Fallback: try customer_email
        email = session.get("customer_email") or session.get("customer_details", {}).get("email")
        if email:
            user = await get_user_by_email(db, email.lower())
        if not user:
            raise HTTPException(status_code=404, detail="User not found for this checkout session")

    user_id = user["user_id"]

    # ── Determine the plan from the Stripe session ────────────────────────
    # Retrieve the subscription to check the price interval
    actual_plan = user.get("pending_plan", "monthly")
    if subscription_id:
        try:
            sub_obj = stripe_module.Subscription.retrieve(subscription_id)
            items = sub_obj.get("items", {}).get("data", [])
            if items:
                interval = items[0].get("price", {}).get("recurring", {}).get("interval", "")
                actual_plan = "yearly" if interval == "year" else "monthly"
        except Exception as e:
            logger.warning(f"[WELCOME] Could not fetch subscription to determine plan: {e}")

    # ── Activate trial subscription (idempotent) ─────────────────────────
    now = datetime.now(timezone.utc)
    update_fields = {
        "is_premium": True,
        "subscription_status": "trialing",
        "subscription_plan": actual_plan,
        "subscription_provider": "stripe",
        "stripe_customer_id": customer_id,
        "trial_used": True,
        "trial_start": now,
        "trial_end": now + timedelta(days=7),
        "subscription_expiration": now + timedelta(days=7),
    }
    if subscription_id:
        update_fields["stripe_subscription_id"] = subscription_id

    await update_user(db, user_id, update_fields)
    logger.info(f"[WELCOME] Trial activated for user={user_id} subscription={subscription_id}")

    # ── Log the activation ───────────────────────────────────────────────
    await db.subscription_logs.insert_one({
        "user_id": user_id,
        "action": "trial_activated_welcome",
        "provider": "stripe",
        "stripe_customer_id": customer_id,
        "stripe_subscription_id": subscription_id,
        "timestamp": now,
    })

    # ── Issue JWT tokens (first login) ───────────────────────────────────
    access_token, refresh_token, expires_in = create_tokens(user_id, user["email"])

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_in": expires_in,
    }


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


@router.post("/customer-portal")
async def customer_portal(request: Request, current_user: dict = Depends(get_current_user)):
    """Create a Stripe Customer Portal session so the user can manage/change their plan."""
    db = get_db(request)

    user_id = current_user.get("sub")
    user = await get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    customer_id = user.get("stripe_customer_id")
    if not customer_id:
        raise HTTPException(status_code=400, detail="No billing account found")

    try:
        session = stripe_module.billing_portal.Session.create(
            customer=customer_id,
            return_url=f"{FRONTEND_URL}/(tabs)",
        )
        return {"url": session.url}
    except Exception as e:
        logger.error(f"[PORTAL] Error creating portal session: {e}")
        raise HTTPException(status_code=500, detail="Could not create billing portal")


@router.post("/logout")
async def logout(current_user: dict = Depends(get_current_user)):
    """Logout user (client should discard tokens)"""
    # In a more advanced implementation, you could blacklist the token
    return {"message": "Logged out successfully"}
