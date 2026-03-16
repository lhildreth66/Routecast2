# STRIPE DISABLED - Google Play submission - do not delete
"""
Entire file disabled for Stripe removal.
"""
import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import HTTPException

from routers import subscription as subscription_router


class _FakeUsersCollection:
    def __init__(self, user_doc):
        self.user_doc = user_doc

    async def find_one(self, query):
        if self.user_doc and query.get("user_id") == self.user_doc.get("user_id"):
            return self.user_doc
        return None


class _FakeDB:
    def __init__(self, user_doc):
        self.users = _FakeUsersCollection(user_doc)


def _fake_request_with_db(db):
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(db=db)))


@pytest.mark.asyncio
async def test_portal_returns_url_for_active_stripe_user(monkeypatch):
    user = {
        "user_id": "user_1",
        "email": "test@example.com",
        "name": "Test User",
        "stripe_customer_id": "cus_123",
        "stripe_subscription_id": "sub_123",
        "subscription_provider": "stripe",
    }

    monkeypatch.setattr(subscription_router, "STRIPE_API_KEY", "sk_test")
    monkeypatch.setattr(subscription_router, "FRONTEND_URL", "https://routecastweather.com")

    async def _to_thread(func, *args, **kwargs):
        return func(*args, **kwargs)

    monkeypatch.setattr(subscription_router.asyncio, "to_thread", _to_thread)
    monkeypatch.setattr(
        subscription_router.stripe.billing_portal.Session,
        "create",
        lambda **kwargs: SimpleNamespace(url="https://billing.stripe.com/session_abc"),
    )

    db = _FakeDB(user)
    request = _fake_request_with_db(db)

    result = await subscription_router.create_customer_portal_session(
        request=request,
        current_user={"sub": "user_1", "email": "test@example.com"},
    )

    assert result["url"] == "https://billing.stripe.com/session_abc"


@pytest.mark.asyncio
async def test_portal_returns_400_when_no_active_subscription(monkeypatch):
    user = {
        "user_id": "user_2",
        "email": "inactive@example.com",
        "name": "Inactive User",
        "stripe_customer_id": None,
        "stripe_subscription_id": None,
        "subscription_provider": None,
    }

    monkeypatch.setattr(subscription_router, "STRIPE_API_KEY", "sk_test")

    db = _FakeDB(user)
    request = _fake_request_with_db(db)

    with pytest.raises(HTTPException) as exc_info:
        await subscription_router.create_customer_portal_session(
            request=request,
            current_user={"sub": "user_2", "email": "inactive@example.com"},
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "No active subscription found"


@pytest.mark.asyncio
async def test_portal_creates_customer_when_missing_for_stripe_user(monkeypatch):
    user = {
        "user_id": "user_3",
        "email": "trial@example.com",
        "name": "Trial User",
        "stripe_customer_id": None,
        "stripe_subscription_id": None,
        "subscription_provider": "stripe",
    }

    monkeypatch.setattr(subscription_router, "STRIPE_API_KEY", "sk_test")

    async def _to_thread(func, *args, **kwargs):
        return func(*args, **kwargs)

    monkeypatch.setattr(subscription_router.asyncio, "to_thread", _to_thread)
    monkeypatch.setattr(
        subscription_router.stripe.Customer,
        "create",
        lambda **kwargs: SimpleNamespace(id="cus_new"),
    )
    monkeypatch.setattr(
        subscription_router.stripe.Subscription,
        "list",
        lambda **kwargs: {"data": [{"id": "sub_trial", "status": "trialing"}]},
    )
    monkeypatch.setattr(
        subscription_router.stripe.billing_portal.Session,
        "create",
        lambda **kwargs: SimpleNamespace(url="https://billing.stripe.com/session_new"),
    )

    update_user_mock = AsyncMock(return_value=True)
    monkeypatch.setattr(subscription_router, "update_user", update_user_mock)

    db = _FakeDB(user)
    request = _fake_request_with_db(db)

    result = await subscription_router.create_customer_portal_session(
        request=request,
        current_user={"sub": "user_3", "email": "trial@example.com"},
    )

    assert result["url"] == "https://billing.stripe.com/session_new"
    update_user_mock.assert_awaited_once_with(db, "user_3", {"stripe_customer_id": "cus_new"})
"""
