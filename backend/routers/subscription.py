"""
Subscription Router for RouteCast
Handles Stripe checkout, webhooks, and subscription management
"""
from fastapi import APIRouter, HTTPException, Depends, Header, Request
from typing import Optional
from datetime import datetime, timezone
import os
import logging

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
from services.email_service import send_subscription_confirmation_email
from routers.auth import get_current_user, get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/subscription", tags=["Subscription"])

# Stripe integration
STRIPE_API_KEY = os.environ.get("STRIPE_API_KEY")


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
    """Create a Stripe checkout session for subscription"""
    db = get_db(request)
    user_id = current_user.get("sub")
    email = current_user.get("email")

    # Validate plan
    if data.plan not in [SubscriptionPlan.MONTHLY, SubscriptionPlan.YEARLY]:
        raise HTTPException(status_code=400, detail="Invalid plan")

    plan_key = data.plan.value
    price_config = SUBSCRIPTION_PRICES.get(plan_key)

    if not price_config:
        raise HTTPException(status_code=400, detail="Plan not found")

    try:
        from emergentintegrations.payments.stripe.checkout import (
            StripeCheckout, CheckoutSessionRequest
        )

        # Build URLs
        success_url = f"{data.origin_url}/subscription/success?session_id={{CHECKOUT_SESSION_ID}}"
        cancel_url = f"{data.origin_url}/subscription/cancel"

        # Get webhook URL
        api_url = os.environ.get('API_URL', data.origin_url.replace('app.', 'api.'))
        webhook_url = f"{api_url}/api/webhook/stripe"

        # Initialize Stripe
        stripe_checkout = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=webhook_url)

        # Create checkout session
        checkout_request = CheckoutSessionRequest(
            amount=float(price_config["amount"]),
            currency="usd",
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                "user_id": user_id,
                "plan": plan_key,
                "email": email
            }
        )

        session = await stripe_checkout.create_checkout_session(checkout_request)

        # Store transaction record
        await db.payment_transactions.insert_one({
            "session_id": session.session_id,
            "user_id": user_id,
            "email": email,
            "plan": plan_key,
            "amount": price_config["amount"],
            "currency": "usd",
            "payment_status": "pending",
            "created_at": datetime.now(timezone.utc)
        })

        return CheckoutResponse(
            checkout_url=session.url,
            session_id=session.session_id
        )

    except Exception as e:
        logger.error(f"Stripe checkout error: {e}")
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

    result = await verify_google_receipt(data.purchase_token, data.product_id, data.package_name)

    if result["valid"]:
        # Determine plan from product_id
        plan = "yearly" if "yearly" in data.product_id.lower() else "monthly"

        await activate_subscription(
            db=db,
            user_id=user_id,
            plan=plan,
            provider="google",
            google_purchase_token=data.purchase_token
        )

    return ReceiptVerifyResponse(
        valid=result["valid"],
        subscription_status=SubscriptionStatus(result["subscription_status"]) if result["subscription_status"] in [s.value for s in SubscriptionStatus] else SubscriptionStatus.INACTIVE,
        expiration=result.get("expiration"),
        message=result["message"]
    )


@router.get("/portal")
async def get_customer_portal(
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """Get Stripe customer portal URL for managing subscription"""
    db = get_db(request)
    user_id = current_user.get("sub")

    user = await db.users.find_one({"user_id": user_id})

    if not user or not user.get("stripe_customer_id"):
        raise HTTPException(status_code=400, detail="No Stripe subscription found")

    # In production, you would create a Stripe portal session
    # For now, return a placeholder
    return {
        "message": "Customer portal not yet configured",
        "portal_url": None
    }


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
