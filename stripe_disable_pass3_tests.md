Stripe Disable Pass 3 — Tests (Google Play submission)
======================================================

What changed (commented, not deleted)
------------------------------------
- backend/test_checkout_plan_selection.py — entire file commented with header.
- backend/test_subscription_portal_endpoint.py — entire file commented with header.
- backend/test_bridge_height_service.py — only the stripe stub import commented; rest restored.

Verification snippets (first 3 lines of each commented block)
------------------------------------------------------------
- backend/test_checkout_plan_selection.py
  # STRIPE DISABLED - Google Play submission - do not delete
  """
  Tests: checkout plan → Stripe price_id mapping

- backend/test_subscription_portal_endpoint.py
  # STRIPE DISABLED - Google Play submission - do not delete
  """
  Entire file disabled for Stripe removal.

- backend/test_bridge_height_service.py (stripe stub line)
  _STUB_MODS = [
      "sendgrid", "sendgrid.helpers", "sendgrid.helpers.mail",
      # "stripe",  # STRIPE DISABLED - Google Play submission - do not delete

Notes
-----
- All changes are comments only; original code preserved inside the commented sections or via inline comment on the stub line.
- No commits made.
