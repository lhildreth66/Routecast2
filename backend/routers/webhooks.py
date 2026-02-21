"""
Webhook Router for RouteCast
Handles incoming webhooks from Stripe, Apple, and Google
"""
from fastapi import APIRouter, HTTPException, Request, Header
from typing import Optional
from datetime import datetime, timezone
import os
import json
import logging

from services.subscription_service import handle_stripe_subscription_event

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/stripe", tags=["Webhooks"])

STRIPE_API_KEY = os.environ.get("STRIPE_API_KEY")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET")


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: Optional[str] = Header(None, alias="Stripe-Signature")
):
    """Handle Stripe webhook events"""
    db = request.app.state.db

    # Get raw body
    body = await request.body()

    try:
        # In production, verify webhook signature
        # For now, parse the payload directly
        payload = json.loads(body)

        event_type = payload.get("type", "")
        data = payload.get("data", {}).get("object", {})

        logger.info(f"Stripe webhook received: {event_type}")

        # Handle subscription events
        if event_type.startswith("customer.subscription"):
            customer_id = data.get("customer")
            if customer_id:
                await handle_stripe_subscription_event(
                    db=db,
                    event_type=event_type,
                    subscription_data=data,
                    customer_id=customer_id
                )

        # Handle checkout completed
        elif event_type == "checkout.session.completed":
            session_id = data.get("id")
            payment_status = data.get("payment_status")

            if session_id and payment_status == "paid":
                # Update transaction record
                metadata = data.get("metadata", {})
                user_id = metadata.get("user_id")
                plan = metadata.get("plan")

                if user_id and plan:
                    # Store Stripe customer ID
                    customer_id = data.get("customer")
                    if customer_id:
                        await db.users.update_one(
                            {"user_id": user_id},
                            {"$set": {
                                "stripe_customer_id": customer_id,
                                "updated_at": datetime.now(timezone.utc)
                            }}
                        )

                    # Activate subscription
                    from services.subscription_service import activate_subscription
                    duration_days = 365 if plan == "yearly" else 30
                    await activate_subscription(
                        db=db,
                        user_id=user_id,
                        plan=plan,
                        provider="stripe",
                        duration_days=duration_days,
                        stripe_customer_id=customer_id
                    )

                    logger.info(f"Subscription activated for user {user_id}: {plan}")

        # Handle invoice events
        elif event_type.startswith("invoice"):
            customer_id = data.get("customer")
            if customer_id:
                await handle_stripe_subscription_event(
                    db=db,
                    event_type=event_type,
                    subscription_data=data,
                    customer_id=customer_id
                )

        return {"received": True}

    except json.JSONDecodeError:
        logger.error("Invalid JSON in Stripe webhook")
        raise HTTPException(status_code=400, detail="Invalid JSON")
    except Exception as e:
        logger.error(f"Stripe webhook error: {e}")
        # Return 200 to prevent Stripe from retrying
        return {"received": True, "error": str(e)}


@router.post("/apple")
async def apple_webhook(request: Request):
    """
    Handle Apple App Store Server Notifications (v2)
    This receives subscription status updates from Apple
    """
    db = request.app.state.db

    try:
        body = await request.body()
        payload = json.loads(body)

        logger.info(f"Apple webhook received")

        # TODO: Implement Apple Server Notification handling
        # This would decode the signedPayload JWT and process subscription events

        # Scaffold for Apple notification types:
        # - SUBSCRIBED
        # - DID_RENEW
        # - DID_CHANGE_RENEWAL_PREF
        # - DID_FAIL_TO_RENEW
        # - EXPIRED
        # - REFUND

        return {"received": True}

    except Exception as e:
        logger.error(f"Apple webhook error: {e}")
        return {"received": True, "error": str(e)}


@router.post("/google")
async def google_webhook(request: Request):
    """
    Handle Google Play Real-time Developer Notifications (RTDN)
    This receives subscription status updates from Google Play
    """
    db = request.app.state.db

    try:
        body = await request.body()
        payload = json.loads(body)

        logger.info(f"Google webhook received")

        # TODO: Implement Google Play RTDN handling
        # The payload contains a base64-encoded notification

        # Scaffold for Google notification types:
        # - SUBSCRIPTION_PURCHASED
        # - SUBSCRIPTION_RENEWED
        # - SUBSCRIPTION_CANCELED
        # - SUBSCRIPTION_EXPIRED
        # - SUBSCRIPTION_PAUSED
        # - SUBSCRIPTION_RESTARTED

        return {"received": True}

    except Exception as e:
        logger.error(f"Google webhook error: {e}")
        return {"received": True, "error": str(e)}
