from types import SimpleNamespace

import pytest
from fastapi import BackgroundTasks

from routers import auth as auth_router


class _FakeVerificationTokens:
    def __init__(self, doc=None):
        self._doc = doc

    async def find_one(self, _query):
        return self._doc


class _FakeDb:
    def __init__(self, token_doc=None):
        self.verification_tokens = _FakeVerificationTokens(token_doc)


def _build_request(db):
    return SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(db=db)),
        url=SimpleNamespace(path='/api/auth/verify-email'),
        query_params={},
    )


@pytest.mark.asyncio
async def test_verify_email_marks_verified_only_not_premium(monkeypatch):
    db = _FakeDb()
    request = _build_request(db)
    updates = []

    async def _fake_verify_and_consume(_db, _token, _token_type):
        return 'user-123'

    async def _fake_get_user_by_id(_db, _user_id):
        return {
            'user_id': 'user-123',
            'email': 'new@example.com',
            'email_verified': False,
            'subscription_status': 'inactive',
            'subscription_plan': 'free',
            'is_premium': False,
            'trial_used': False,
        }

    async def _fake_update_user(_db, user_id, payload):
        updates.append((user_id, dict(payload)))
        return True

    monkeypatch.setattr(auth_router, 'verify_and_consume_token', _fake_verify_and_consume)
    monkeypatch.setattr(auth_router, 'get_user_by_id', _fake_get_user_by_id)
    monkeypatch.setattr(auth_router, 'update_user', _fake_update_user)

    response = await auth_router._verify_email_with_token('valid-token', BackgroundTasks(), request, wants_json=True)

    assert response.status_code == 200
    assert updates == [('user-123', {'email_verified': True})]


@pytest.mark.asyncio
async def test_idempotent_verify_retry_does_not_grant_trial_without_purchase(monkeypatch):
    db = _FakeDb(token_doc={'token': 'used-token', 'token_type': 'email_verification', 'used': True, 'user_id': 'user-abc'})
    request = _build_request(db)
    updates = []

    async def _fake_verify_and_consume(_db, _token, _token_type):
        return None

    async def _fake_get_user_by_id(_db, _user_id):
        return {
            'user_id': 'user-abc',
            'email': 'retry@example.com',
            'email_verified': True,
            'subscription_status': 'inactive',
            'subscription_plan': 'free',
            'is_premium': False,
            'trial_used': False,
        }

    async def _fake_update_user(_db, user_id, payload):
        updates.append((user_id, dict(payload)))
        return True

    monkeypatch.setattr(auth_router, 'verify_and_consume_token', _fake_verify_and_consume)
    monkeypatch.setattr(auth_router, 'get_user_by_id', _fake_get_user_by_id)
    monkeypatch.setattr(auth_router, 'update_user', _fake_update_user)

    response = await auth_router._verify_email_with_token('used-token', BackgroundTasks(), request, wants_json=True)

    assert response.status_code == 200
    assert updates == []
