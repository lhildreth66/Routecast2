# STRIPE DISABLED - Google Play submission - do not delete
"""
Subscription Router for RouteCast
Handles Stripe checkout, webhooks, and subscription management
"""
from fastapi import APIRouter, HTTPException, Depends, Header, Request
from typing import Optional
from datetime import datetime, timezone
import os
import asyncio
import logging

# STRIPE DISABLED - Google Play submission - do not delete
# import stripe

from models.user import (
    CreateCheckoutRequest, CheckoutResponse, SubscriptionInfo,
    AppleReceiptVerifyRequest, GoogleReceiptVerifyRequest, ReceiptVerifyResponse,
    SubscriptionStatus, SubscriptionPlan, SubscriptionProvider
)
from services.subscription_service import (
    check_subscription_status, start_trial, activate_subscription,
    verify_apple_receipt, verify_google_receipt, handle_stripe_subscription_event,
    SUBSCRIPTION_PRICES
)
from services.auth_service import update_user
from services.email_service import send_subscription_confirmation_email
from routers.auth import get_current_user, get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/subscription", tags=["Subscription"])

# Stripe integration
STRIPE_API_KEY = os.environ.get("STRIPE_API_KEY")
STRIPE_PRICE_MONTHLY = os.environ.get("STRIPE_PRICE_MONTHLY")
STRIPE_PRICE_YEARLY  = os.environ.get("STRIPE_PRICE_YEARLY")
FRONTEND_URL = (os.environ.get("FRONTEND_URL") or "https://routecastweather.com").rstrip("/")


@router.get("/status", response_model=SubscriptionInfo)
async def get_subscription_status(
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """Get current subscription status"""
    db = get_db(request)
    user_id = current_user.get("sub")

    status = await check_subscription_status(db, user_id)

    return SubscriptionInfo(
        status=SubscriptionStatus(status["status"]) if status["status"] in [s.value for s in SubscriptionStatus] else SubscriptionStatus.INACTIVE,
        plan=SubscriptionPlan(status["plan"]) if status["plan"] in [p.value for p in SubscriptionPlan] else SubscriptionPlan.FREE,
        provider=status.get("provider"),
        expiration=status.get("expiration"),
        is_active=status["is_premium"],
        can_access_premium=status["is_premium"]
    )


@router.post("/start-trial")
async def start_free_trial(
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """Start a 7-day free trial"""
    db = get_db(request)
    user_id = current_user.get("sub")

    success, message = await start_trial(db, user_id)

    if not success:
        raise HTTPException(status_code=400, detail=message)

    return {"message": message, "trial_days": 7}


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout_session(
    data: CreateCheckoutRequest,
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """Create a Stripe Checkout session for a recurring subscription.

    Uses STRIPE_PRICE_MONTHLY / STRIPE_PRICE_YEARLY from environment so that
    the correct recurring price is always applied.
    """
    db = get_db(request)
    user_id = current_user.get("sub")
    email = current_user.get("email")

    if not STRIPE_API_KEY:
        raise HTTPException(status_code=500, detail="Stripe API key not configured")

    # Normalise plan — default to monthly if missing
    plan_key = (getattr(data.plan, "value", data.plan) or "monthly").lower()
    logger.info(f"[CHECKOUT] received plan={plan_key!r} user_id={user_id}")

    # Map plan → Stripe price ID (hard fail if env var missing)
    if plan_key == "monthly":
        price_id = STRIPE_PRICE_MONTHLY
    elif plan_key == "yearly":
        price_id = STRIPE_PRICE_YEARLY
    else:
        raise HTTPException(status_code=400, detail=f"Invalid plan: {plan_key!r}")

    if not price_id:
        logger.error(f"[CHECKOUT] Stripe price ID not configured for plan={plan_key!r}")
        raise HTTPException(status_code=500, detail=f"Stripe price ID not configured for plan '{plan_key}'")

    logger.info(f"[CHECKOUT] plan={plan_key!r} → price_id={price_id!r}")

    origin = (data.origin_url or "https://routecastweather.com").rstrip("/")
    success_url = f"{origin}/subscription/success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url  = f"{origin}/subscription?canceled=1"

    try:
        stripe.api_key = STRIPE_API_KEY  # type: ignore[attr-defined]
        session = await asyncio.to_thread(
            stripe.checkout.Session.create,  # type: ignore[attr-defined]
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            subscription_data={"trial_period_days": 7},
            success_url=success_url,
            cancel_url=cancel_url,
            payment_method_collection="always",
            metadata={
                "user_id": user_id,
                "plan": plan_key,
                "email": email or "",
            },
        )

        # Store pending transaction so success/webhook can activate the subscription
        await db.payment_transactions.insert_one({
            "session_id": session.id,
            "user_id": user_id,
            "email": email,
            "plan": plan_key,
            "price_id": price_id,
            "currency": "usd",
            "payment_status": "pending",
            "created_at": datetime.now(timezone.utc),
        })

        logger.info(f"[CHECKOUT] session created: id={session.id} plan={plan_key!r} price={price_id!r}")
        return CheckoutResponse(
            checkout_url=session.url,
            session_id=session.id,
        )

    except stripe.error.StripeError as e:  # type: ignore[attr-defined]
        logger.error(f"[CHECKOUT] Stripe error: {e}")
        raise HTTPException(status_code=502, detail="Unable to start checkout")
    except Exception as e:
        logger.error(f"[CHECKOUT] Unexpected error: {e}")
        raise HTTPException(status_code=500, detail="Failed to create checkout session")


@router.get("/checkout/status/{session_id}")
async def get_checkout_status(
    session_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """Get checkout session status and activate subscription if paid"""
    db = get_db(request)
    user_id = current_user.get("sub")

    try:
        from emergentintegrations.payments.stripe.checkout import StripeCheckout

        stripe_checkout = StripeCheckout(api_key=STRIPE_API_KEY)
        status = await stripe_checkout.get_checkout_status(session_id)

        # Get transaction record
        transaction = await db.payment_transactions.find_one({"session_id": session_id})

        if not transaction:
            raise HTTPException(status_code=404, detail="Transaction not found")

        if transaction["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Not authorized")

        # Update transaction status
        now = datetime.now(timezone.utc)
        await db.payment_transactions.update_one(
            {"session_id": session_id},
            {"$set": {
                "payment_status": status.payment_status,
                "updated_at": now
            }}
        )

        # If payment successful and not already activated
        if status.payment_status == "paid" and transaction["payment_status"] != "paid":
            plan = transaction["plan"]

            # Activate subscription
            duration_days = 365 if plan == "yearly" else 30
            await activate_subscription(
                db=db,
                user_id=user_id,
                plan=plan,
                provider="stripe",
                duration_days=duration_days
            )

            # Send confirmation email
            user = await db.users.find_one({"user_id": user_id})
            if user:
                try:
                    send_subscription_confirmation_email(
                        user["email"],
                        plan,
                        user.get("name")
                    )
                except:
                    pass  # Don't fail if email fails

        return {
            "status": status.status,
            "payment_status": status.payment_status,
            "amount_total": status.amount_total,
            "currency": status.currency
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Checkout status error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get checkout status")


@router.post("/verify/apple", response_model=ReceiptVerifyResponse)
async def verify_apple_purchase(
    data: AppleReceiptVerifyRequest,
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """Verify Apple In-App Purchase receipt"""
    db = get_db(request)
    user_id = current_user.get("sub")

    result = await verify_apple_receipt(data.receipt_data, data.product_id)

    if result["valid"]:
        # Determine plan from product_id
        plan = "yearly" if "yearly" in data.product_id.lower() else "monthly"

        await activate_subscription(
            db=db,
            user_id=user_id,
            plan=plan,
            provider="apple",
            apple_transaction_id=result.get("transaction_id")
        )

    return ReceiptVerifyResponse(
        valid=result["valid"],
        subscription_status=SubscriptionStatus(result["subscription_status"]) if result["subscription_status"] in [s.value for s in SubscriptionStatus] else SubscriptionStatus.INACTIVE,
        expiration=result.get("expiration"),
        message=result["message"]
    )


@router.post("/verify/google", response_model=ReceiptVerifyResponse)
async def verify_google_purchase(
    data: GoogleReceiptVerifyRequest,
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """Verify Google Play purchase"""
    db = get_db(request)
    user_id = current_user.get("sub")

    token_preview = f"{data.purchase_token[:6]}...{data.purchase_token[-6:]}" if data.purchase_token and len(data.purchase_token) > 12 else "<short>"
    logger.info(
        "[GOOGLE_VERIFY] request user_id=%s product_id=%s package_name=%s token=%s",
        user_id,
        data.product_id,
        data.package_name,
        token_preview,
    )

    if not data.purchase_token or not data.product_id:
        logger.warning("[GOOGLE_VERIFY] malformed payload user_id=%s", user_id)
        raise HTTPException(status_code=400, detail="purchase_token and product_id are required")

    result = await verify_google_receipt(data.purchase_token, data.product_id, data.package_name)

    if not result.get("verified_with_google", False):
        # Do not mutate entitlement state on transient verification failures.
        logger.warning(
            "[GOOGLE_VERIFY] verification unavailable user_id=%s product_id=%s token=%s message=%s error_code=%s",
            user_id,
            data.product_id,
            token_preview,
            result.get("message"),
            result.get("error_code"),
        )
        raise HTTPException(status_code=502, detail=result.get("message", "Google Play verification unavailable"))

    now = datetime.now(timezone.utc)
    status = result.get("subscription_status", "inactive")
    expiration = result.get("expiration")
    plan = result.get("plan") or ("yearly" if "yearly" in data.product_id.lower() else "monthly")

    existing_user = await db.users.find_one({"user_id": user_id})
    if not existing_user:
        raise HTTPException(status_code=404, detail="User not found")

    update_data = {
        "subscription_status": status,
        "subscription_provider": "google",
        "subscription_expiration": expiration,
        "google_purchase_token": data.purchase_token,
        "updated_at": now,
    }

    if result["valid"]:
        update_data["is_premium"] = status in ["trialing", "active", "canceling"]
        update_data["subscription_plan"] = plan
        if status == "trialing":
            update_data["trial_used"] = True
            if expiration:
                update_data["trial_end"] = expiration
            if not existing_user.get("trial_start"):
                update_data["trial_start"] = now
    else:
        update_data["is_premium"] = False
        update_data["subscription_plan"] = "free"
        update_data["trial_end"] = None
        update_data["trial_start"] = None

    await db.users.update_one({"user_id": user_id}, {"$set": update_data})

    logger.info(
        "[GOOGLE_VERIFY] persisted user_id=%s valid=%s status=%s plan=%s expiration=%s is_premium=%s",
        user_id,
        result.get("valid"),
        status,
        update_data.get("subscription_plan"),
        update_data.get("subscription_expiration"),
        update_data.get("is_premium"),
    )

    return ReceiptVerifyResponse(
        valid=result["valid"],
        subscription_status=SubscriptionStatus(result["subscription_status"]) if result["subscription_status"] in [s.value for s in SubscriptionStatus] else SubscriptionStatus.INACTIVE,
        expiration=result.get("expiration"),
        message=result["message"]
    )


@router.post("/portal")
async def create_customer_portal_session(
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """Create Stripe customer portal session URL for managing subscription."""
    db = get_db(request)
    user_id = current_user.get("sub")
    email = current_user.get("email")

    if not STRIPE_API_KEY:
        raise HTTPException(status_code=500, detail="Stripe API key not configured")

    user = await db.users.find_one({"user_id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    stripe.api_key = STRIPE_API_KEY  # type: ignore[attr-defined]

    stripe_customer_id = user.get("stripe_customer_id")
    has_stripe_subscription = (
        user.get("subscription_provider") == "stripe"
        or bool(user.get("stripe_subscription_id"))
    )

    if not stripe_customer_id and has_stripe_subscription:
        try:
            customer = await asyncio.to_thread(
                stripe.Customer.create,  # type: ignore[attr-defined]
                email=email,
                name=user.get("name"),
                metadata={"user_id": user_id, "email": email or ""},
            )
            stripe_customer_id = customer.id
            await update_user(db, user_id, {"stripe_customer_id": stripe_customer_id})
            logger.info(f"[PORTAL] Stripe customer created user={user_id} customer={stripe_customer_id}")
        except stripe.error.StripeError as e:  # type: ignore[attr-defined]
            logger.error(f"[PORTAL] Failed to create Stripe customer user={user_id}: {e}")
            raise HTTPException(status_code=502, detail="Unable to create billing profile")

    if not stripe_customer_id:
        raise HTTPException(status_code=400, detail="No active subscription found")

    if not user.get("stripe_subscription_id"):
        try:
            subs = await asyncio.to_thread(
                stripe.Subscription.list,  # type: ignore[attr-defined]
                customer=stripe_customer_id,
                status="all",
                limit=10,
            )
            has_active_subscription = any(
                s.get("status") in ("active", "trialing", "past_due", "unpaid")
                for s in (subs.get("data") or [])
            )
            if not has_active_subscription:
                raise HTTPException(status_code=400, detail="No active subscription found")
        except HTTPException:
            raise
        except stripe.error.StripeError as e:  # type: ignore[attr-defined]
            logger.error(f"[PORTAL] Failed checking subscriptions user={user_id}: {e}")
            raise HTTPException(status_code=502, detail="Unable to verify subscription")

    try:
        session = await asyncio.to_thread(
            stripe.billing_portal.Session.create,  # type: ignore[attr-defined]
            customer=stripe_customer_id,
            return_url=f"{FRONTEND_URL}/account",
        )
        return {"url": session.url}
    except stripe.error.InvalidRequestError as e:  # type: ignore[attr-defined]
        logger.error(f"[PORTAL] Invalid Stripe portal configuration: {e}")
        raise HTTPException(
            status_code=502,
            detail="Stripe Customer Portal is not enabled. Please contact support.",
        )
    except stripe.error.StripeError as e:  # type: ignore[attr-defined]
        logger.error(f"[PORTAL] Stripe error creating portal session user={user_id}: {e}")
        raise HTTPException(status_code=502, detail="Unable to open subscription portal")
    except Exception as e:
        logger.error(f"[PORTAL] Unexpected error creating portal session user={user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to open subscription portal")


@router.get("/plans")
async def get_subscription_plans():
    """Get available subscription plans"""
    return {
        "plans": [
            {
                "id": "monthly",
                "name": "Monthly",
                "price": SUBSCRIPTION_PRICES["monthly"]["amount"],
                "currency": "usd",
                "interval": "month",
                "trial_days": SUBSCRIPTION_PRICES["monthly"]["trial_days"],
                "features": [
                    "Unlimited route monitoring",
                    "Push weather alerts",
                    "AI-powered recommendations",
                    "Advanced trucker features",
                    "Boondocking tools",
                    "Export routes"
                ]
            },
            {
                "id": "yearly",
                "name": "Yearly",
                "price": SUBSCRIPTION_PRICES["yearly"]["amount"],
                "currency": "usd",
                "interval": "year",
                "trial_days": SUBSCRIPTION_PRICES["yearly"]["trial_days"],
                "savings": "Save $60/year",
                "features": [
                    "Everything in Monthly",
                    "Priority support",
                    "2 months free"
                ]
            }
        ],
        "trial_days": 7
    }
