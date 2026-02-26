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
        
        elif event_type == "customer.subscription.trial_will_end":
            await handle_trial_will_end(db, data)
            
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
    """Handle checkout.session.completed — immediate premium unlock.

    We no longer gate on payment_status because Stripe sends
    'no_payment_required' for $0 trial checkouts (not 'paid').  Instead we
    fetch the subscription object from Stripe directly and gate on its status:
    'active' or 'trialing' both mean the user has a valid subscription.
    Falls back to optimistic unlock when the Stripe fetch fails so the user
    is never left without access due to a transient API error.
    """
    customer_id = data.get("customer")
    customer_email = data.get("customer_email") or data.get("customer_details", {}).get("email")
    payment_status = data.get("payment_status")
    mode = data.get("mode")
    subscription_id = data.get("subscription")

    logger.info(
        f"Checkout completed: customer={customer_id}, email={customer_email}, "
        f"status={payment_status}, mode={mode}, subscription={subscription_id}"
    )

    # Only process subscription checkouts — ignore one-time payment sessions.
    if mode != "subscription":
        logger.info(f"[STRIPE] Checkout skipped — mode={mode} is not 'subscription'")
        return

    # Determine subscription status from Stripe directly.
    # This is more reliable than payment_status which differs for $0 trials.
    stripe_sub_status = None
    current_period_end = None
    if subscription_id and STRIPE_API_KEY:
        try:
            sub = stripe.Subscription.retrieve(subscription_id)
            stripe_sub_status = sub.get("status")          # 'active', 'trialing', ...
            current_period_end = sub.get("current_period_end")  # Unix timestamp
            logger.info(f"[STRIPE] Subscription {subscription_id} status={stripe_sub_status}")
        except Exception as e:
            logger.warning(f"[STRIPE] Could not fetch subscription {subscription_id}: {e}")

    # Gate: only activate if subscription is genuinely active or in trial.
    # If we couldn't fetch the subscription (network error etc.), be optimistic
    # and proceed — customer.subscription.updated will correct it if wrong.
    if stripe_sub_status is not None and stripe_sub_status not in ("active", "trialing"):
        logger.info(f"[STRIPE] Checkout skipped — subscription status={stripe_sub_status}")
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
        logger.warning("No user found for checkout, saved for manual resolution")
        return

    user_id = user["user_id"]
    plan = determine_plan(data)

    # Prefer the real period end from Stripe; fall back to local calculation.
    if current_period_end:
        expiration = datetime.fromtimestamp(current_period_end, tz=timezone.utc)
    elif plan == "yearly":
        expiration = now + timedelta(days=365)
    else:
        expiration = now + timedelta(days=30)

    # Map Stripe status to our internal status label.
    internal_status = stripe_sub_status if stripe_sub_status else "active"

    # Update user — IMMEDIATE premium access
    update_data = {
        "is_premium": True,
        "plan": plan,
        "subscription_status": internal_status,
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

    logger.info(f"Premium activated for user {user_id}: plan={plan}, status={internal_status}, expires={expiration}")

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

    # ── Send "You're All Set" email (idempotent — only once) ─────────────
    # Atomically claim the right to send: only proceed if
    # welcome_email_sent_at has not been set yet.
    claim = await db.users.update_one(
        {"user_id": user_id, "welcome_email_sent_at": {"$exists": False}},
        {"$set": {"welcome_email_sent_at": now}},
    )
    if claim.modified_count == 1:
        try:
            from services.email_service import send_trial_started_email
            send_trial_started_email(user["email"], user.get("name"), plan)
            logger.info(f"[STRIPE] Trial-started email sent for user={user_id}")
        except Exception as e:
            logger.error(f"[STRIPE] Failed to send trial-started email for user={user_id}: {e}")
    else:
        logger.info(f"[STRIPE] Trial-started email already sent for user={user_id}, skipping")


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
        if plan == "yearly":
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

        # ── Send "You're All Set" email (idempotent — only once) ─────────
        # Atomically claim the right to send so two concurrent webhooks
        # can't both send the email.
        claim = await db.users.update_one(
            {"user_id": user_id, "welcome_email_sent_at": {"$exists": False}},
            {"$set": {"welcome_email_sent_at": now}},
        )
        if claim.modified_count == 1:
            try:
                from services.email_service import send_trial_started_email
                send_trial_started_email(user["email"], user.get("name"), plan)
                logger.info(f"[STRIPE] Trial-started email sent (sub_created) for user={user_id}")
            except Exception as e:
                logger.error(f"[STRIPE] Failed to send trial-started email (sub_created) for user={user_id}: {e}")
        else:
            logger.info(f"[STRIPE] Trial-started email already sent for user={user_id}, skipping")


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

    # ── Map Stripe status → internal status ───────────────────────────────
    # cancel_at_period_end=True with status=active means the user has scheduled
    # a cancellation but is still within their paid period — treat as "canceling".
    if status == "active" and cancel_at_period_end:
        subscription_status = "canceling"
    elif status in ("active", "trialing", "canceled", "unpaid",
                    "incomplete", "incomplete_expired", "past_due"):
        subscription_status = status
    else:
        subscription_status = status  # forward-compatible fall-through

    # ── Determine is_premium ───────────────────────────────────────────────
    # Per spec:
    #   premium ONLY when status == active OR trialing (within trial)
    #   canceling → premium until current_period_end  (checked via expiration below)
    #   past_due / unpaid / canceled / incomplete* → NOT premium
    if subscription_status in ("active", "trialing"):
        is_premium = True
    elif subscription_status == "canceling":
        # User paid for the period; keep premium until it ends.
        # check_subscription_status will flip is_premium=False when the
        # expiration timestamp passes.
        is_premium = True
    else:
        # canceled, past_due, unpaid, incomplete, incomplete_expired, …
        is_premium = False

    # ── Calculate expiration from Stripe's period end ─────────────────────
    if current_period_end:
        expiration = datetime.fromtimestamp(current_period_end, tz=timezone.utc)
    elif plan in ("annual", "yearly"):
        expiration = now + timedelta(days=365)
    else:
        expiration = now + timedelta(days=30)

    update_fields = {
        "is_premium": is_premium,
        "subscription_status": subscription_status,
        "subscription_plan": plan if is_premium else "free",
        "subscription_expiration": expiration,
        "stripe_subscription_id": subscription_id,
        # Reset Stripe live-check TTL so /me re-verifies promptly
        "stripe_status_verified_at": now,
        "updated_at": now,
    }
    if not is_premium:
        # Demote plan on non-premium transitions
        update_fields["plan"] = "free"

    await db.users.update_one({"user_id": user_id}, {"$set": update_fields})

    logger.info(
        f"[WEBHOOK] subscription.updated user={user_id} "
        f"stripe_status={status} cancel_at_period_end={cancel_at_period_end} "
        f"internal={subscription_status} is_premium={is_premium}"
    )


async def handle_subscription_deleted(db, data: dict, now: datetime):
    """Handle customer.subscription.deleted - subscription ended"""
    customer_id = data.get("customer")
    subscription_id = data.get("id")
    
    logger.info(f"Subscription deleted: {subscription_id}")
    
    user = await find_or_link_user(db, customer_id)
    if not user:
        return
    
    user_id = user["user_id"]

    # Revoke premium access immediately
    await db.users.update_one(
        {"user_id": user_id},
        {"$set": {
            "is_premium": False,
            "plan": "free",
            "subscription_plan": "free",
            "subscription_status": "canceled",
            "subscription_expiration": now,
            "stripe_subscription_id": None,
            # Reset live-check cache so /me picks up fresh state immediately
            "stripe_status_verified_at": now,
            "updated_at": now,
        }}
    )

    logger.info(f"[WEBHOOK] subscription.deleted — premium revoked for user={user_id}")

    await db.subscription_logs.insert_one({
        "user_id": user_id,
        "action": "canceled",
        "provider": "stripe",
        "stripe_customer_id": customer_id,
        "stripe_subscription_id": subscription_id,
        "timestamp": now,
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



async def handle_trial_will_end(db, data: dict):
    """Handle trial ending soon - send reminder email."""
    subscription_id = data.get("id")
    customer_id = data.get("customer")
    trial_end = data.get("trial_end")
    
    logger.info(f"Trial will end for subscription {subscription_id}")
    
    # Find user by Stripe customer ID
    user = await db.users.find_one({"stripe_customer_id": customer_id})
    
    if not user:
        # Try finding by subscription ID
        user = await db.users.find_one({"stripe_subscription_id": subscription_id})
    
    if not user:
        logger.warning(f"No user found for trial_will_end: customer={customer_id}")
        return
    
    user_id = user.get("user_id")
    email = user.get("email")
    
    # Log the event
    await db.subscription_logs.insert_one({
        "user_id": user_id,
        "action": "trial_will_end",
        "provider": "stripe",
        "stripe_subscription_id": subscription_id,
        "trial_end": trial_end,
        "timestamp": datetime.now(timezone.utc)
    })
    
    # Send reminder email (if SendGrid is configured)
    try:
        sendgrid_key = os.environ.get("SENDGRID_API_KEY")
        if sendgrid_key and email:
            import sendgrid
            from sendgrid.helpers.mail import Mail, Email, To, Content
            
            sg = sendgrid.SendGridAPIClient(api_key=sendgrid_key)
            from_email = Email("noreply@routecastweather.com")
            to_email = To(email)
            subject = "Your RouteCast trial ends soon"
            content = Content(
                "text/html",
                """
                <h2>Your RouteCast trial ends soon</h2>
                <p>Hi there,</p>
                <p>Your 7-day free trial is ending soon. After your trial ends, 
                your subscription will automatically convert to a paid plan.</p>
                <p>If you'd like to continue using RouteCast Premium, no action is needed.</p>
                <p>If you'd prefer to cancel, you can do so from your account settings 
                before your trial ends.</p>
                <p>Thanks for trying RouteCast!</p>
                """
            )
            mail = Mail(from_email, to_email, subject, content)
            sg.client.mail.send.post(request_body=mail.get())
            logger.info(f"Trial reminder email sent to {email}")
    except Exception as e:
        logger.warning(f"Failed to send trial reminder email: {e}")



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
