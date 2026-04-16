"""
Authentication Router for RouteCast
Handles signup, login, email verification, password reset, and user profile.

Flow:  signup → verify-email (302 → Stripe Checkout) → /welcome (activate + JWT)
"""
from fastapi import APIRouter, HTTPException, Depends, Header, Request, BackgroundTasks
from fastapi.responses import JSONResponse, RedirectResponse, HTMLResponse
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta, timezone
import hmac
import hashlib
import logging
import os
from html import escape as html_escape
from urllib.parse import quote as urlquote

try:
    import stripe as stripe_module
except ImportError:  # Stripe SDK not installed in some environments
    class _MissingStripe:
        def __getattr__(self, name):  # pragma: no cover - runtime guard
            raise ImportError("stripe is not installed")
    stripe_module = _MissingStripe()

logger = logging.getLogger(__name__)

from models.user import (
    UserCreate, UserLogin, UserResponse, UserMeResponse,
    TokenResponse, TokenRefreshRequest, PasswordResetRequest,
    PasswordResetConfirm, ChangePasswordRequest,
    SubscriptionStatus, SubscriptionPlan, EntitlementState,
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
    send_verification_email, send_password_reset_email, send_signup_notification_email
)

router = APIRouter(prefix="/auth", tags=["Authentication"])

FRONTEND_URL = (
    os.environ.get("FRONTEND_URL")
    or os.environ.get("APP_URL")
    or "https://routecastweather.com"
).rstrip("/")
MOBILE_APP_SCHEME = os.environ.get("MOBILE_APP_SCHEME", "routecast2")
ANDROID_PLAY_URL = "https://play.google.com/store/apps/details?id=com.routecast.app"

# STRIPE DISABLED - Google Play submission - do not delete
# STRIPE_API_KEY = os.environ.get("STRIPE_API_KEY", "")
# STRIPE_PRICE_MONTHLY = os.environ.get("STRIPE_PRICE_MONTHLY", "")
# STRIPE_PRICE_YEARLY = os.environ.get("STRIPE_PRICE_YEARLY", "")
# FRONTEND_URL = (
#     os.environ.get("FRONTEND_URL")
#     or os.environ.get("APP_URL")
#     or "https://routecastweather.com"
# )

# if STRIPE_API_KEY:
#     stripe_module.api_key = STRIPE_API_KEY


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

        # Internal signup notification — fire-and-forget, never blocks signup
        try:
            created_at_str = str(user.get("created_at", ""))
            sent = send_signup_notification_email(
                user_id=user["user_id"],
                email=user["email"],
                name=user.get("name"),
                created_at=created_at_str,
                email_verified=bool(user.get("email_verified", False)),
            )
            if sent:
                logger.info(
                    "signup notification sent user_id=%s",
                    user["user_id"],
                )
            else:
                logger.warning(
                    "signup notification failed user_id=%s reason=send_returned_false",
                    user["user_id"],
                )
        except Exception as _notify_exc:
            logger.error(
                "signup notification failed user_id=%s error=%s",
                user["user_id"], _notify_exc,
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
    response_format: Optional[str] = FastQuery(None, alias="format"),
):
    """Verify email via GET — primary path triggered by clicking the link.

    On success: creates a Stripe Customer + Checkout Session and returns
    an HTTP 302 redirect to the Stripe-hosted checkout page.
    On failure: 302 redirect back to the frontend with an ``error`` query
    param so the page can show a friendly message.
    """
    raw = (token or t or "").strip()
    wants_json = (response_format or "").strip().lower() == "json"
    return await _verify_email_with_token(raw, background_tasks, request, wants_json)


# STRIPE DISABLED - Google Play submission - do not delete
# ── Helper: create Stripe Checkout Session ───────────────────────────────────

# async def _create_stripe_checkout_for_user(db, user_id: str, user: dict):
#     """Create a Stripe Customer (if needed) and Checkout Session.

#     Reads ``pending_plan`` from the user record to pick the correct price.
#     Returns ``(checkout_url, error_message)``.
#     """
#     email = user["email"]
#     name = user.get("name")
#     customer_id = user.get("stripe_customer_id")
#     pending_plan = user.get("pending_plan", "monthly")

#     try:
#         # Re-use existing Stripe customer if present (idempotent retry)
#         if not customer_id:
#             customer = stripe_module.Customer.create(
#                 email=email,
#                 name=name,
#                 metadata={"user_id": user_id, "email": email},
#             )
#             customer_id = customer.id
#             await update_user(db, user_id, {"stripe_customer_id": customer_id})
#             logger.info(f"[VERIFY] Stripe customer created: {customer_id} for user={user_id}")

#         # Pick the correct price based on the user's chosen plan
#         if pending_plan == "yearly" and STRIPE_PRICE_YEARLY:
#             price_id = STRIPE_PRICE_YEARLY
#         else:
#             price_id = STRIPE_PRICE_MONTHLY

#         if not price_id:
#             logger.error(f"[VERIFY] Stripe price not configured for plan={pending_plan}")
#             return None, "Billing is not configured. Please contact support."

#         logger.info(f"[VERIFY] Using plan={pending_plan} price_id={price_id} for user={user_id}")

#        session = stripe_module.checkout.Session.create(
#             customer=customer_id,
#             mode="subscription",
#             line_items=[{"price": price_id, "quantity": 1}],
#             subscription_data={"trial_period_days": 7},
#             payment_method_collection="always",
#             success_url=f"{FRONTEND_URL}/welcome?session_id={{CHECKOUT_SESSION_ID}}",
#             cancel_url=f"{FRONTEND_URL}/signup",
#         )
#         logger.info(f"[VERIFY] Checkout session created: {session.id} for user={user_id}")
#         return session.url, None

#     except stripe_module.error.StripeError as e:
#         logger.error(f"[VERIFY] Stripe error for user={user_id}: {e}")
#         return None, "Unable to start checkout. Please try again later."
#     except Exception as e:
#         logger.error(f"[VERIFY] Unexpected error creating checkout for user={user_id}: {e}")
#         return None, "Unable to start checkout. Please try again later."


# ── Failure-redirect URL ─────────────────────────────────────────────────────
_ERROR_REDIRECT = f"{os.environ.get('FRONTEND_URL', '')}/signup?error=invalid_token"


def _build_native_verify_success_response(email: str = "") -> HTMLResponse:
        safe_email = html_escape(email or "")
        encoded_email = urlquote(email or "", safe="")
        app_url = f"{MOBILE_APP_SCHEME}://subscription"
        html = f"""
        <!doctype html>
        <html>
            <head>
                <meta charset=\"utf-8\" />
                <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
                <title>RouteCast Verification Complete</title>
            </head>
            <body style=\"font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; background:#0f0f0f; color:#fff; margin:0;\">
                <div style=\"max-width:560px; margin:0 auto; min-height:100vh; display:flex; align-items:center; justify-content:center; padding:24px;\">
                    <div style=\"width:100%; background:#1f2937; border:1px solid #374151; border-radius:14px; padding:24px; text-align:center;\">
                        <h1 style=\"margin:0 0 8px; color:#22c55e;\">Email Verified</h1>
                        <p style=\"margin:0 0 20px; color:#d1d5db;\">{safe_email if safe_email else 'Your account is verified.'}</p>

                        <!-- Opening state: shown immediately while deep link is attempted -->
                        <div id=\"rc-opening\">
                            <p style=\"margin:0 0 16px; color:#e5e7eb;\">Opening RouteCast app to choose a subscription plan...</p>
                            <a href=\"{app_url}\" style=\"display:inline-block; background:#eab308; color:#111827; text-decoration:none; font-weight:700; border-radius:10px; padding:12px 18px;\">Open RouteCast App</a>
                        </div>

                        <!-- Fallback state: shown after 1500ms if page is still visible (app didn't open) -->
                        <div id=\"rc-fallback\" style=\"display:none;\">
                            <p style=\"margin:0 0 16px; color:#e5e7eb; font-size:16px; line-height:1.5;\">The app didn&apos;t open automatically.<br>Tap below to install or open RouteCast.</p>
                            <a onclick=\"window.location='{MOBILE_APP_SCHEME}://subscription';setTimeout(function(){{if(document.visibilityState!=='hidden'){{window.location='{ANDROID_PLAY_URL}';}}}},1500);return false;\" href=\"{ANDROID_PLAY_URL}\" style=\"display:block; background:#eab308; color:#111827; text-decoration:none; font-weight:700; border-radius:10px; padding:16px 24px; font-size:17px; box-sizing:border-box; cursor:pointer;\">Get RouteCast on Google Play</a>
                        </div>
                    </div>
                </div>
                <script>
                    (function() {{
                        var appUrl = {app_url!r};
                        // Attempt deep link immediately
                        window.location.replace(appUrl);
                        // After 1500ms, check if the page is still visible.
                        // If visibilityState is 'hidden', the app opened and took focus — do nothing.
                        // If still visible, the deep link failed — show the Google Play fallback.
                        setTimeout(function() {{
                            if (document.visibilityState !== 'hidden') {{
                                var opening = document.getElementById('rc-opening');
                                var fallback = document.getElementById('rc-fallback');
                                if (opening) opening.style.display = 'none';
                                if (fallback) fallback.style.display = 'block';
                            }}
                        }}, 1500);
                    }})();
                </script>
            </body>
        </html>
        """
        return HTMLResponse(content=html, status_code=200)


async def _verify_email_with_token(
    token: str,
    background_tasks: BackgroundTasks,
    request: Request,
    wants_json: bool = False,
):
    """Verify the email token and return either JSON or browser redirect/HTML.

    API/native callers can request JSON with ``format=json``.
    Browser link clicks receive redirect/HTML responses that open the app.
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
        if wants_json:
            return JSONResponse(status_code=400, content={"detail": "Verification token is required."})
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
                # STRIPE DISABLED - Google Play submission - do not delete
                # checkout_url, err = await _create_stripe_checkout_for_user(
                #     db, old_token_doc["user_id"], existing_user,
                # )
                # if err:
                #     logger.error(f"[VERIFY-EMAIL] Stripe checkout failed on retry: {err}")
                #     return RedirectResponse(url=_ERROR_REDIRECT, status_code=302)
                if wants_json:
                    return JSONResponse(
                        status_code=200,
                        content={"message": "Email verified successfully", "email": existing_user.get("email", "")},
                    )
                return _build_native_verify_success_response(existing_user.get("email", ""))
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
        if wants_json:
            return JSONResponse(status_code=400, content={"detail": "Verification failed. The link may be invalid or expired."})
        return RedirectResponse(url=_ERROR_REDIRECT, status_code=302)

    # ── Step 3: mark the user as verified ────────────────────────────────
    user = await get_user_by_id(db, user_id)
    if not user:
        logger.warning(f"[VERIFY-EMAIL] FAIL bucket=USER_MISMATCH user_id={user_id}")
        if wants_json:
            return JSONResponse(status_code=404, content={"detail": "User not found for verification token."})
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
    # STRIPE DISABLED - Google Play submission - do not delete
    # checkout_url, err = await _create_stripe_checkout_for_user(db, user_id, user)
    # if err:
    #     logger.error(f"[VERIFY-EMAIL] Stripe checkout creation failed: {err}")
    #     return RedirectResponse(url=_ERROR_REDIRECT, status_code=302)

    if wants_json:
        return JSONResponse(
            status_code=200,
            content={"message": "Email verified successfully", "email": user.get("email", "")},
        )

    return _build_native_verify_success_response(user.get("email", ""))


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

    normalized_status = sub_status["status"]
    if normalized_status == "trialing" and is_premium:
        entitlement_state = EntitlementState.TRIAL_ACTIVE
    elif normalized_status in ("active", "canceling") and is_premium:
        entitlement_state = EntitlementState.SUBSCRIPTION_ACTIVE
    elif normalized_status in ("expired", "canceled", "past_due", "unpaid"):
        entitlement_state = EntitlementState.EXPIRED
    else:
        entitlement_state = EntitlementState.FREE_TIER

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
        trial_days_remaining=trial_days_remaining,
        entitlement_state=entitlement_state,
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
            return_url=f"{FRONTEND_URL}/",
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


# ---------------------------------------------------------------------------
# Email opt-out (unsubscribe from reminder emails)
# ---------------------------------------------------------------------------

_EMAIL_UNSUBSCRIBE_SECRET = (
    os.environ.get("EMAIL_UNSUBSCRIBE_SECRET")
    or os.environ.get("SECRET_KEY", "")
)


def _verify_unsubscribe_token(user_id: str, token: str) -> bool:
    """Constant-time HMAC verification for unsubscribe tokens."""
    if not _EMAIL_UNSUBSCRIBE_SECRET:
        return False
    secret = _EMAIL_UNSUBSCRIBE_SECRET.encode("utf-8")
    expected = hmac.new(secret, user_id.encode("utf-8"), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, token)


@router.get("/email-opt-out")
async def email_opt_out(token: str, uid: str, request: Request):
    """One-click unsubscribe from signup reminder emails.

    Linked from reminder emails. Sets email_opt_out=True on the matching user
    so no further reminder emails are sent.
    """
    db = get_db(request)
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    if not _verify_unsubscribe_token(uid, token):
        raise HTTPException(status_code=400, detail="Invalid or expired unsubscribe link")

    result = await db.users.update_one(
        {"user_id": uid},
        {"$set": {"email_opt_out": True}},
    )

    if result.matched_count == 0:
        # Try by _id string as fallback
        await db.users.update_one(
            {"_id": uid},
            {"$set": {"email_opt_out": True}},
        )

    logger.info("[email_opt_out] user_id=%s opted out of reminder emails", uid)
    return HTMLResponse(
        content=(
            "<html><body style='font-family:sans-serif;text-align:center;padding:40px;'>"
            "<h2>&#10003; You have been unsubscribed</h2>"
            "<p>You will no longer receive signup reminder emails from RouteCast.</p>"
            "<p>You can still log in and manage your account at "
            "<a href='https://routecastweather.com'>routecastweather.com</a>.</p>"
            "</body></html>"
        ),
        status_code=200,
    )
