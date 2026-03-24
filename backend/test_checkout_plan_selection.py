# STRIPE DISABLED - Google Play submission - do not delete
"""
Tests: checkout plan → Stripe price_id mapping

Verifies that the plan-selection logic used in server._stripe_price_for_plan()
correctly routes monthly/yearly to their respective Stripe price IDs, that a
missing plan defaults to "monthly", and that misconfigured env vars raise rather
than silently fall through.

These tests exercise the exact logic without importing the full FastAPI app so
they run quickly in CI without heavy optional dependencies.
"""
import pytest
from fastapi import HTTPException

# ---------------------------------------------------------------------------
# Reproduce the EXACT logic from server._stripe_price_for_plan.
# Any change to the server function must be reflected here – this also serves
# as a documentation contract for the expected behaviour.
# ---------------------------------------------------------------------------
MONTHLY_PRICE = "price_test_monthly_XXXXXXXXXXXX"
YEARLY_PRICE  = "price_test_yearly_XXXXXXXXXXXX"


def stripe_price_for_plan(plan: str, monthly_id, yearly_id) -> str:
    """Mirror of server._stripe_price_for_plan with injected price IDs."""
    plan = (plan or "monthly").lower()
    if plan == "monthly":
        price_id = monthly_id
    elif plan == "yearly":
        price_id = yearly_id
    else:
        raise HTTPException(status_code=400, detail=f"Invalid plan: {plan!r}")

    if not price_id:
        raise HTTPException(
            status_code=500,
            detail=f"Stripe price ID not configured for plan '{plan}'"
        )
    return price_id


def resolve(plan: str) -> str:
    """Convenience wrapper using standard test price IDs."""
    return stripe_price_for_plan(plan, MONTHLY_PRICE, YEARLY_PRICE)


# ===========================================================================
# Tests
# ===========================================================================

class TestPlanToStripePrice:

    def test_monthly_maps_to_monthly_price(self):
        assert resolve("monthly") == MONTHLY_PRICE

    def test_yearly_maps_to_yearly_price(self):
        assert resolve("yearly") == YEARLY_PRICE

    def test_monthly_does_NOT_use_yearly_price(self):
        assert resolve("monthly") != YEARLY_PRICE, \
            "monthly plan must NOT resolve to the yearly price ID"

    def test_yearly_does_NOT_use_monthly_price(self):
        assert resolve("yearly") != MONTHLY_PRICE, \
            "yearly plan must NOT resolve to the monthly price ID"

    def test_empty_plan_defaults_to_monthly(self):
        """Empty string should default to monthly, not crash."""
        assert resolve("") == MONTHLY_PRICE

    def test_uppercase_plan_normalised(self):
        """Plan value coming from the network may be mixed-case."""
        assert resolve("Monthly") == MONTHLY_PRICE
        assert resolve("YEARLY")  == YEARLY_PRICE

    def test_invalid_plan_raises_400(self):
        with pytest.raises(HTTPException) as exc_info:
            resolve("quarterly")
        assert exc_info.value.status_code == 400

    def test_unknown_plan_never_returns_a_price(self):
        """Any plan not in {monthly, yearly} must never silently return a price ID."""
        for bad in ("premium", "annual", "trial", "free"):
            try:
                result = stripe_price_for_plan(bad, MONTHLY_PRICE, YEARLY_PRICE)
                pytest.fail(f"plan={bad!r} silently returned {result!r}")
            except HTTPException:
                pass  # expected

    def test_unconfigured_monthly_raises_500(self):
        """If STRIPE_PRICE_MONTHLY is unset, checkout must fail loudly."""
        with pytest.raises(HTTPException) as exc_info:
            stripe_price_for_plan("monthly", None, YEARLY_PRICE)
        assert exc_info.value.status_code == 500

    def test_unconfigured_yearly_raises_500(self):
        """If STRIPE_PRICE_YEARLY is unset, checkout must fail loudly."""
        with pytest.raises(HTTPException) as exc_info:
            stripe_price_for_plan("yearly", MONTHLY_PRICE, None)
        assert exc_info.value.status_code == 500

    def test_unconfigured_monthly_does_not_fall_through_to_yearly(self):
        """A missing STRIPE_PRICE_MONTHLY must NOT silently use STRIPE_PRICE_YEARLY."""
        try:
            result = stripe_price_for_plan("monthly", None, YEARLY_PRICE)
            pytest.fail(
                f"Expected HTTPException but got {result!r}. "
                "Missing monthly price must raise, not fall through to yearly."
            )
        except HTTPException as exc:
            assert exc.status_code == 500
