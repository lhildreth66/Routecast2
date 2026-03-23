Stripe Disable Pass 1 — Backend (Google Play submission)
===========================================================

What changed (commented, not deleted)
------------------------------------
- backend/routers/subscription.py — entire file wrapped with header marker `# STRIPE DISABLED - Google Play submission - do not delete` and closing triple quotes.
- backend/routers/webhooks.py — entire file wrapped with the same header marker and triple quotes.
- backend/services/subscription_service.py — entire file wrapped with the same header marker and triple quotes.
- backend/routers/admin.py — lines 274-531 (reconcile-subscriptions endpoint) wrapped with the same header marker and triple quotes.
- backend/server.py —
  - lines 300-305: Stripe config/env block wrapped with the header marker and triple quotes.
  - lines 4633-4767: Stripe checkout/billing helpers and endpoints wrapped with the header marker and triple quotes.

Verification snippets (first 3 lines of each commented block)
------------------------------------------------------------
- backend/routers/subscription.py
  # STRIPE DISABLED - Google Play submission - do not delete
  """
  Subscription Router for RouteCast

- backend/routers/webhooks.py
  # STRIPE DISABLED - Google Play submission - do not delete
  """
  Webhook Router for RouteCast

- backend/services/subscription_service.py
  # STRIPE DISABLED - Google Play submission - do not delete
  """
  Subscription Service for RouteCast

- backend/routers/admin.py (reconcile-subscriptions block)
  # STRIPE DISABLED - Google Play submission - do not delete
  """
  @router.post("/reconcile-subscriptions")

- backend/server.py (Stripe config block)
  # STRIPE DISABLED - Google Play submission - do not delete
  """
  STRIPE_API_KEY = os.environ.get("STRIPE_API_KEY")

- backend/server.py (Stripe checkout/billing block)
  # STRIPE DISABLED - Google Play submission - do not delete
  """
  class BillingVerifyRequest(BaseModel):

Notes
-----
- All changes are comments only; original code preserved inside triple-quoted blocks.
- No commits made.
