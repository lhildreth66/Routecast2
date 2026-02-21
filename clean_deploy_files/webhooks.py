"""
Webhook Router for RouteCast
Handles incoming webhooks from Stripe, Apple, and Google
"""
from fastapi import APIRouter, HTTPException, Request, Header
from typing import Optional
from datetime import datetime, timezone, timedelta
import os
import json
import logging
import stripe

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/stripe", tags=["Webhooks"])

STRIPE_API_KEY = os.environ.get('STRIPE_API_KEY', '')
STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET', '')

# Initialize Stripe
if STRIPE_API_KEY:
    stripe.api_key = STRIPE_API_KEY


async def process_stripe_event(db, event_type: str, data: dict):
    """Process Stripe event in background to return 200 quickly"""
    try:
        now = datetime.now(timezone.utc)
        
        if event_type == "checkout.session.completed":
            await handle_checkout_completed(db, data, now)
        
        elif event_type == "customer.subscription.updated":
            await handle_subscription_updated(db, data, now)
        
        elif event_type == "customer.subscription.deleted":
            await handle_subscription_deleted(db, data, now)
        
        elif event_type == "customer.subscription.created":
            await handle_subscription_created(db, data, now)
        
        elif event_type == "invoice.paid":
            await handle_invoice_paid(db, data, now)
        
        elif event_type == "invoice.payment_failed":
            await handle_invoice_failed(db, data, now)
            
    except Exception as e:
        logger.error(f"Error processing Stripe event {event_type}: {e}")


async def get_customer_email(customer_id: str) -> Optional[str]:
    """Fetch customer email from Stripe"""
    if not STRIPE_API_KEY or not customer_id:
        return None
    try:
        customer = stripe.Customer.retrieve(customer_id)
        return customer.get("email")
    except Exception as e:
        logger.error(f"Error fetching Stripe customer {customer_id}: {e}")
        return None


async def find_or_link_user(db, customer_id: str, email: str = None):
    """
    Find user by Stripe customer ID or email.
    Links Stripe customer to existing user if found by email.
    """
    # First try to find by Stripe customer ID
    user = await db.users.find_one({"stripe_customer_id": customer_id})
    if user:
        return user
    
    # Get email from Stripe if not provided
    if not email:
        email = await get_customer_email(customer_id)
    
    if not email:
        logger.warning(f"No email found for Stripe customer {customer_id}")
        return None
    
    # Find user by email
    user = await db.users.find_one({"email": email.lower()})
    if user:
        # Link Stripe customer to this user
        await db.users.update_one(
            {"user_id": user["user_id"]},
            {"$set": {
                "stripe_customer_id": customer_id,
                "updated_at": datetime.now(timezone.utc)
            }}
        )
        logger.info(f"Linked Stripe customer {customer_id} to user {user['user_id']}")
        return user
    
    logger.warning(f"No user found for email {email}")
    return None


def determine_plan(data: dict) -> str:
    """Determine if subscription is monthly or yearly"""
    # Check line items or subscription items
    line_items = data.get("line_items", {}).get("data", [])
    if line_items:
        for item in line_items:
            price = item.get("price", {})
            interval = price.get("recurring", {}).get("interval", "")
            if interval == "year":
                return "yearly"  # Fixed: was "annual", must match SubscriptionPlan.YEARLY
            elif interval == "month":
                return "monthly"
    
    # Check subscription directly
    items = data.get("items", {}).get("data", [])
    if items:
        for item in items:
            price = item.get("price", {})
            interval = price.get("recurring", {}).get("interval", "")
            if interval == "year":
                return "yearly"  # Fixed: was "annual"
    
    # Check plan object (older format)
    plan = data.get("plan", {})
    interval = plan.get("interval", "")
    if interval == "year":
        return "yearly"  # Fixed: was "annual"
    
    # Check amount to determine (fallback)
    amount = data.get("amount_total", 0) or data.get("amount", 0)
    if amount:
        amount_dollars = amount / 100
        if amount_dollars > 50:  # Annual/yearly is ~$60
            return "yearly"  # Fixed: was "annual"
    
    return "monthly"


async def handle_checkout_completed(db, data: dict, now: datetime):
    """Handle checkout.session.completed - immediate premium unlock"""
    customer_id = data.get("customer")
    customer_email = data.get("customer_email") or data.get("customer_details", {}).get("email")
    payment_status = data.get("payment_status")
    mode = data.get("mode")
    
    logger.info(f"Checkout completed: customer={customer_id}, email={customer_email}, status={payment_status}, mode={mode}")
    
    # Only process successful payments
    if payment_status != "paid":
        logger.info(f"Checkout not paid yet: {payment_status}")
        return
    
    # Find or link user
    user = await find_or_link_user(db, customer_id, customer_email)
    if not user:
        # Log for manual resolution
        await db.pending_subscriptions.insert_one({
            "stripe_customer_id": customer_id,
            "email": customer_email,
            "event": "checkout.session.completed",
            "data": data,
            "created_at": now,
            "resolved": False
        })
        logger.warning(f"No user found for checkout, saved for manual resolution")
        return
    
    user_id = user["user_id"]
    plan = determine_plan(data)
    
    # Calculate expiration
    if plan == "yearly":
        expiration = now + timedelta(days=365)
    else:
        expiration = now + timedelta(days=30)
    
    # Get subscription ID if this was a subscription checkout
    subscription_id = data.get("subscription")
    
    # Update user - IMMEDIATE premium access
    update_data = {
        "is_premium": True,
        "plan": plan,
        "subscription_status": "active",
        "subscription_plan": plan,
        "subscription_provider": "stripe",
        "subscription_expiration": expiration,
        "stripe_customer_id": customer_id,
        "updated_at": now
    }
    
    if subscription_id:
        update_data["stripe_subscription_id"] = subscription_id
    
    await db.users.update_one(
        {"user_id": user_id},
        {"$set": update_data}
    )
    
    logger.info(f"Premium activated for user {user_id}: plan={plan}, expires={expiration}")
    
    # Log the activation
    await db.subscription_logs.insert_one({
        "user_id": user_id,
        "action": "activated",
        "plan": plan,
        "provider": "stripe",
        "stripe_customer_id": customer_id,
        "stripe_subscription_id": subscription_id,
        "timestamp": now
    })


async def handle_subscription_created(db, data: dict, now: datetime):
    """Handle customer.subscription.created"""
    customer_id = data.get("customer")
    subscription_id = data.get("id")
    status = data.get("status")
    
    logger.info(f"Subscription created: {subscription_id}, status={status}")
    
    user = await find_or_link_user(db, customer_id)
    if not user:
        return
    
    user_id = user["user_id"]
    plan = determine_plan(data)
    
    # Only activate if status is active or trialing
    if status in ["active", "trialing"]:
        if plan == "annual":
            expiration = now + timedelta(days=365)
        else:
            expiration = now + timedelta(days=30)
        
        await db.users.update_one(
            {"user_id": user_id},
            {"$set": {
                "is_premium": True,
                "plan": plan,
                "subscription_status": status,
                "subscription_plan": plan,
                "subscription_provider": "stripe",
                "subscription_expiration": expiration,
                "stripe_subscription_id": subscription_id,
                "updated_at": now
            }}
        )
        logger.info(f"Subscription activated for user {user_id}: {plan}")


async def handle_subscription_updated(db, data: dict, now: datetime):
    """Handle customer.subscription.updated - plan changes, renewals, status changes"""
    customer_id = data.get("customer")
    subscription_id = data.get("id")
    status = data.get("status")  # active, past_due, canceled, unpaid, trialing
    cancel_at_period_end = data.get("cancel_at_period_end", False)
    current_period_end = data.get("current_period_end")
    
    logger.info(f"Subscription updated: {subscription_id}, status={status}, cancel_at_period_end={cancel_at_period_end}")
    
    user = await find_or_link_user(db, customer_id)
    if not user:
        return
    
    user_id = user["user_id"]
    plan = determine_plan(data)
    
    # Determine premium status based on Stripe status
    is_premium = status in ["active", "trialing"]
    
    # Map Stripe status to our status
    if status == "active" and cancel_at_period_end:
        subscription_status = "canceling"  # Will cancel at period end
    elif status == "active":
        subscription_status = "active"
    elif status == "trialing":
        subscription_status = "trialing"
    elif status == "past_due":
        subscription_status = "past_due"
        is_premium = True  # Give grace period
    elif status == "canceled":
        subscription_status = "canceled"
        is_premium = False
    elif status == "unpaid":
        subscription_status = "unpaid"
        is_premium = False
    else:
        subscription_status = status
    
    # Calculate expiration from Stripe's period end
    if current_period_end:
        expiration = datetime.fromtimestamp(current_period_end, tz=timezone.utc)
    elif plan == "annual":
        expiration = now + timedelta(days=365)
    else:
        expiration = now + timedelta(days=30)
    
    await db.users.update_one(
        {"user_id": user_id},
        {"$set": {
            "is_premium": is_premium,
            "plan": plan if is_premium else user.get("plan", "free"),
            "subscription_status": subscription_status,
            "subscription_plan": plan,
            "subscription_expiration": expiration,
            "stripe_subscription_id": subscription_id,
            "updated_at": now
        }}
    )
    
    logger.info(f"User {user_id} subscription updated: status={subscription_status}, is_premium={is_premium}")


async def handle_subscription_deleted(db, data: dict, now: datetime):
    """Handle customer.subscription.deleted - subscription ended"""
    customer_id = data.get("customer")
    subscription_id = data.get("id")
    
    logger.info(f"Subscription deleted: {subscription_id}")
    
    user = await find_or_link_user(db, customer_id)
    if not user:
        return
    
    user_id = user["user_id"]
    
    # Revoke premium access
    await db.users.update_one(
        {"user_id": user_id},
        {"$set": {
            "is_premium": False,
            "plan": "free",
            "subscription_plan": "free",  # Fixed: also set subscription_plan field
            "subscription_status": "expired",
            "subscription_expiration": now,
            "stripe_subscription_id": None,
            "updated_at": now
        }}
    )
    
    logger.info(f"Premium revoked for user {user_id}")
    
    # Log the cancellation
    await db.subscription_logs.insert_one({
        "user_id": user_id,
        "action": "expired",
        "provider": "stripe",
        "stripe_customer_id": customer_id,
        "timestamp": now
    })


async def handle_invoice_paid(db, data: dict, now: datetime):
    """Handle invoice.paid - successful payment/renewal"""
    customer_id = data.get("customer")
    subscription_id = data.get("subscription")
    
    if not subscription_id:
        return  # Not a subscription invoice
    
    logger.info(f"Invoice paid for subscription {subscription_id}")
    
    user = await find_or_link_user(db, customer_id)
    if not user:
        return
    
    # The subscription.updated event will handle the actual update
    # Just log the payment
    await db.subscription_logs.insert_one({
        "user_id": user["user_id"],
        "action": "payment_succeeded",
        "provider": "stripe",
        "stripe_subscription_id": subscription_id,
        "amount": data.get("amount_paid", 0) / 100,
        "timestamp": now
    })


async def handle_invoice_failed(db, data: dict, now: datetime):
    """Handle invoice.payment_failed - failed payment"""
    customer_id = data.get("customer")
    subscription_id = data.get("subscription")
    
    if not subscription_id:
        return
    
    logger.info(f"Invoice payment failed for subscription {subscription_id}")
    
    user = await find_or_link_user(db, customer_id)
    if not user:
        return
    
    user_id = user["user_id"]
    
    # Set to past_due but keep premium for grace period
    await db.users.update_one(
        {"user_id": user_id},
        {"$set": {
            "subscription_status": "past_due",
            "updated_at": now
        }}
    )
    
    await db.subscription_logs.insert_one({
        "user_id": user_id,
        "action": "payment_failed",
        "provider": "stripe",
        "stripe_subscription_id": subscription_id,
        "timestamp": now
    })


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: Optional[str] = Header(None, alias="Stripe-Signature")
):
    """
    Handle Stripe webhook events.
    Processes synchronously to ensure DB updates complete before response.
    """
    db = request.app.state.db
    body = await request.body()
    
    try:
        # Verify webhook signature in production
        if STRIPE_WEBHOOK_SECRET and stripe_signature:
            try:
                event = stripe.Webhook.construct_event(
                    body, stripe_signature, STRIPE_WEBHOOK_SECRET
                )
                payload = event
            except stripe.error.SignatureVerificationError as e:
                logger.error(f"Stripe signature verification failed: {e}")
                raise HTTPException(status_code=400, detail="Invalid signature")
        else:
            # Development mode - parse directly
            payload = json.loads(body)
        
        event_type = payload.get("type", "")
        data = payload.get("data", {}).get("object", {})
        
        logger.info(f"Stripe webhook: {event_type}")
        
        # Process synchronously to ensure DB updates complete
        await process_stripe_event(db, event_type, data)
        
        return {"received": True}
        
    except json.JSONDecodeError:
        logger.error("Invalid JSON in Stripe webhook")
        raise HTTPException(status_code=400, detail="Invalid JSON")
    except Exception as e:
        logger.error(f"Stripe webhook error: {e}")
        # Return 200 anyway to prevent retries
        return {"received": True}


@router.post("/apple")
async def apple_webhook(request: Request):
    """Handle Apple App Store Server Notifications (v2)"""
    db = request.app.state.db
    
    try:
        body = await request.body()
        payload = json.loads(body)
        logger.info("Apple webhook received")
        
        # TODO: Implement Apple Server Notification handling
        return {"received": True}
        
    except Exception as e:
        logger.error(f"Apple webhook error: {e}")
        return {"received": True}


@router.post("/google")
async def google_webhook(request: Request):
    """Handle Google Play Real-time Developer Notifications"""
    db = request.app.state.db
    
    try:
        body = await request.body()
        payload = json.loads(body)
        logger.info("Google webhook received")
        
        # TODO: Implement Google Play RTDN handling
        return {"received": True}
        
    except Exception as e:
        logger.error(f"Google webhook error: {e}")
        return {"received": True}
