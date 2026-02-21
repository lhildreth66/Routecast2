"""
RouteCast Stripe Webhook API Tests
Tests for Stripe webhook handling, subscription management, and user premium status.
Tests email-based user lookup for generic payment links (buy.stripe.com).
"""

import pytest
import requests
import os
import json
import uuid
from datetime import datetime, timezone

# Get BASE_URL from environment - DO NOT add default URL
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL')
if not BASE_URL:
    # Fallback for testing environment
    BASE_URL = "https://premium-access-sync.preview.emergentagent.com"

BASE_URL = BASE_URL.rstrip('/')

# JWT secret for generating test tokens
JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'routecast-jwt-secret-key-2025-production')


class TestSubscriptionPlansEndpoint:
    """Test GET /api/subscription/plans - available subscription plans"""
    
    def test_get_subscription_plans(self):
        """Test fetching available subscription plans"""
        response = requests.get(f"{BASE_URL}/api/subscription/plans")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "plans" in data, "Missing 'plans' field in response"
        assert len(data["plans"]) >= 2, "Expected at least 2 plans (monthly, yearly)"
        
        # Verify plan structure
        monthly_plan = next((p for p in data["plans"] if p["id"] == "monthly"), None)
        yearly_plan = next((p for p in data["plans"] if p["id"] == "yearly"), None)
        
        assert monthly_plan is not None, "Missing monthly plan"
        assert yearly_plan is not None, "Missing yearly plan"
        
        # Check required fields
        for plan in data["plans"]:
            assert "id" in plan, "Missing id in plan"
            assert "name" in plan, "Missing name in plan"
            assert "price" in plan, "Missing price in plan"
            assert "currency" in plan, "Missing currency in plan"
            assert "interval" in plan, "Missing interval in plan"
            assert "features" in plan, "Missing features in plan"
        
        print(f"✓ Subscription plans retrieved: {len(data['plans'])} plans")
        print(f"  Monthly: ${monthly_plan['price']}/{monthly_plan['interval']}")
        print(f"  Yearly: ${yearly_plan['price']}/{yearly_plan['interval']}")


class TestAuthAndUserProfile:
    """Test user authentication and profile endpoints"""
    
    @pytest.fixture
    def test_user_credentials(self):
        """Generate unique test user credentials"""
        unique_id = str(uuid.uuid4())[:8]
        return {
            "email": f"test_stripe_{unique_id}@example.com",
            "password": "TestPass123!",
            "name": "Stripe Test User"
        }
    
    def test_signup_new_user(self, test_user_credentials):
        """Test creating a new user via signup"""
        response = requests.post(
            f"{BASE_URL}/api/auth/signup",
            json=test_user_credentials
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "access_token" in data, "Missing access_token"
        assert "refresh_token" in data, "Missing refresh_token"
        assert "expires_in" in data, "Missing expires_in"
        
        print(f"✓ User created: {test_user_credentials['email']}")
        return data
    
    def test_get_me_unauthenticated(self):
        """Test GET /api/auth/me without token returns 401"""
        response = requests.get(f"{BASE_URL}/api/auth/me")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ /api/auth/me correctly returns 401 for unauthenticated requests")
    
    def test_get_me_authenticated(self, test_user_credentials):
        """Test GET /api/auth/me with token returns user profile"""
        # First signup
        signup_response = requests.post(
            f"{BASE_URL}/api/auth/signup",
            json=test_user_credentials
        )
        assert signup_response.status_code == 200
        
        token = signup_response.json()["access_token"]
        
        # Get user profile
        response = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "user_id" in data, "Missing user_id"
        assert "email" in data, "Missing email"
        assert "is_premium" in data, "Missing is_premium field"
        assert "subscription_status" in data, "Missing subscription_status"
        assert "subscription_plan" in data, "Missing subscription_plan"
        
        # New user should not be premium
        assert data["is_premium"] == False, "New user should not be premium"
        assert data["subscription_status"] == "inactive", f"Expected 'inactive', got {data['subscription_status']}"
        
        print(f"✓ User profile retrieved: {data['email']}")
        print(f"  is_premium: {data['is_premium']}")
        print(f"  subscription_status: {data['subscription_status']}")
        print(f"  subscription_plan: {data['subscription_plan']}")


class TestStripeWebhookEndpoint:
    """Test POST /api/webhook/stripe - Stripe webhook handling"""
    
    @pytest.fixture(scope="class")
    def test_user_for_webhook(self):
        """Create a test user for webhook tests"""
        unique_id = str(uuid.uuid4())[:8]
        credentials = {
            "email": f"webhook_test_{unique_id}@example.com",
            "password": "WebhookTest123!",
            "name": "Webhook Test User"
        }
        
        signup_response = requests.post(
            f"{BASE_URL}/api/auth/signup",
            json=credentials
        )
        
        if signup_response.status_code == 200:
            token = signup_response.json()["access_token"]
            # Get user details
            me_response = requests.get(
                f"{BASE_URL}/api/auth/me",
                headers={"Authorization": f"Bearer {token}"}
            )
            user_data = me_response.json()
            return {
                "email": credentials["email"],
                "user_id": user_data["user_id"],
                "token": token
            }
        else:
            pytest.skip(f"Failed to create test user: {signup_response.text}")
    
    def test_webhook_returns_200_for_valid_json(self):
        """Test webhook endpoint accepts valid JSON and returns 200"""
        payload = {
            "type": "test.event",
            "data": {
                "object": {}
            }
        }
        
        response = requests.post(
            f"{BASE_URL}/api/webhook/stripe",
            json=payload
        )
        
        # Webhook should return 200 to acknowledge receipt
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("received") == True, "Expected 'received: true' in response"
        
        print("✓ Webhook endpoint accepts valid JSON and returns 200")
    
    def test_webhook_checkout_session_completed(self, test_user_for_webhook):
        """Test checkout.session.completed event grants premium access"""
        user_email = test_user_for_webhook["email"]
        user_token = test_user_for_webhook["token"]
        
        # Simulate checkout.session.completed event from Stripe
        webhook_payload = {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": f"cs_test_{uuid.uuid4().hex[:16]}",
                    "customer": f"cus_test_{uuid.uuid4().hex[:12]}",
                    "customer_email": user_email,
                    "customer_details": {
                        "email": user_email
                    },
                    "payment_status": "paid",
                    "mode": "subscription",
                    "subscription": f"sub_test_{uuid.uuid4().hex[:12]}",
                    "amount_total": 999,  # $9.99 monthly
                    "line_items": {
                        "data": [
                            {
                                "price": {
                                    "recurring": {
                                        "interval": "month"
                                    }
                                }
                            }
                        ]
                    }
                }
            }
        }
        
        # Send webhook
        webhook_response = requests.post(
            f"{BASE_URL}/api/webhook/stripe",
            json=webhook_payload
        )
        assert webhook_response.status_code == 200, f"Webhook failed: {webhook_response.text}"
        
        # Wait for background task to complete (webhook processes async)
        import time
        time.sleep(2)
        
        # Check user profile - should now be premium
        me_response = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {user_token}"}
        )
        assert me_response.status_code == 200
        
        user_data = me_response.json()
        
        print(f"✓ Checkout completed webhook processed")
        print(f"  is_premium: {user_data.get('is_premium')}")
        print(f"  subscription_status: {user_data.get('subscription_status')}")
        print(f"  subscription_plan: {user_data.get('subscription_plan')}")
        
        # Verify premium status was granted
        assert user_data.get("is_premium") == True, f"User should be premium after checkout. Got: {user_data}"
        assert user_data.get("subscription_status") == "active", f"Status should be 'active'. Got: {user_data.get('subscription_status')}"
    
    def test_webhook_checkout_unpaid_does_not_grant_premium(self):
        """Test checkout.session.completed with unpaid status doesn't grant premium"""
        unique_id = str(uuid.uuid4())[:8]
        test_email = f"unpaid_test_{unique_id}@example.com"
        
        # Create user first
        credentials = {
            "email": test_email,
            "password": "UnpaidTest123!",
            "name": "Unpaid Test User"
        }
        signup_response = requests.post(f"{BASE_URL}/api/auth/signup", json=credentials)
        assert signup_response.status_code == 200
        token = signup_response.json()["access_token"]
        
        # Send webhook with unpaid status
        webhook_payload = {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": f"cs_test_{uuid.uuid4().hex[:16]}",
                    "customer": f"cus_test_{uuid.uuid4().hex[:12]}",
                    "customer_email": test_email,
                    "payment_status": "unpaid",  # Not paid
                    "mode": "subscription"
                }
            }
        }
        
        webhook_response = requests.post(f"{BASE_URL}/api/webhook/stripe", json=webhook_payload)
        assert webhook_response.status_code == 200
        
        import time
        time.sleep(2)
        
        # User should still NOT be premium
        me_response = requests.get(f"{BASE_URL}/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        user_data = me_response.json()
        
        assert user_data.get("is_premium") == False, "User should not be premium with unpaid checkout"
        print("✓ Unpaid checkout correctly does not grant premium")


class TestSubscriptionUpdatedWebhook:
    """Test customer.subscription.updated webhook events"""
    
    @pytest.fixture(scope="class")
    def premium_user(self):
        """Create a user and grant them premium via webhook"""
        unique_id = str(uuid.uuid4())[:8]
        email = f"sub_update_{unique_id}@example.com"
        customer_id = f"cus_update_{uuid.uuid4().hex[:12]}"
        subscription_id = f"sub_update_{uuid.uuid4().hex[:12]}"
        
        # Create user
        credentials = {"email": email, "password": "SubUpdate123!", "name": "Sub Update User"}
        signup_response = requests.post(f"{BASE_URL}/api/auth/signup", json=credentials)
        assert signup_response.status_code == 200
        token = signup_response.json()["access_token"]
        
        # Grant premium via checkout webhook
        webhook_payload = {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "customer": customer_id,
                    "customer_email": email,
                    "payment_status": "paid",
                    "mode": "subscription",
                    "subscription": subscription_id,
                    "amount_total": 999
                }
            }
        }
        requests.post(f"{BASE_URL}/api/webhook/stripe", json=webhook_payload)
        
        import time
        time.sleep(2)  # Wait for background task
        
        return {
            "email": email,
            "token": token,
            "customer_id": customer_id,
            "subscription_id": subscription_id
        }
    
    def test_subscription_updated_to_canceled_status(self, premium_user):
        """Test subscription update with cancel_at_period_end=True"""
        webhook_payload = {
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "id": premium_user["subscription_id"],
                    "customer": premium_user["customer_id"],
                    "status": "active",
                    "cancel_at_period_end": True,  # User is canceling
                    "current_period_end": int((datetime.now(timezone.utc).timestamp())) + 86400 * 30  # 30 days
                }
            }
        }
        
        response = requests.post(f"{BASE_URL}/api/webhook/stripe", json=webhook_payload)
        assert response.status_code == 200
        
        import time
        time.sleep(2)  # Wait for background task
        
        # User should still have premium (until period ends)
        me_response = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {premium_user['token']}"}
        )
        user_data = me_response.json()
        
        # User should still be premium during grace period
        assert user_data.get("is_premium") == True, "User should still be premium during cancellation period"
        
        # Status should be 'canceling' as it's active but cancel_at_period_end is true
        print(f"✓ Subscription update (canceling) processed")
        print(f"  is_premium: {user_data.get('is_premium')}")
        print(f"  subscription_status: {user_data.get('subscription_status')}")
    
    def test_subscription_updated_past_due(self, premium_user):
        """Test subscription update to past_due status"""
        webhook_payload = {
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "id": premium_user["subscription_id"],
                    "customer": premium_user["customer_id"],
                    "status": "past_due",  # Payment failed
                    "cancel_at_period_end": False
                }
            }
        }
        
        response = requests.post(f"{BASE_URL}/api/webhook/stripe", json=webhook_payload)
        assert response.status_code == 200
        
        import time
        time.sleep(1)
        
        me_response = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {premium_user['token']}"}
        )
        user_data = me_response.json()
        
        # User should still have premium during grace period (past_due)
        assert user_data.get("is_premium") == True, "User should keep premium during past_due grace period"
        assert user_data.get("subscription_status") == "past_due", f"Status should be 'past_due'. Got: {user_data.get('subscription_status')}"
        
        print(f"✓ Subscription past_due processed - grace period active")
        print(f"  is_premium: {user_data.get('is_premium')}")
        print(f"  subscription_status: {user_data.get('subscription_status')}")


class TestSubscriptionDeletedWebhook:
    """Test customer.subscription.deleted webhook - revokes premium"""
    
    @pytest.fixture
    def premium_user_for_deletion(self):
        """Create a premium user to test deletion"""
        unique_id = str(uuid.uuid4())[:8]
        email = f"sub_delete_{unique_id}@example.com"
        customer_id = f"cus_delete_{uuid.uuid4().hex[:12]}"
        subscription_id = f"sub_delete_{uuid.uuid4().hex[:12]}"
        
        # Create user
        credentials = {"email": email, "password": "SubDelete123!", "name": "Sub Delete User"}
        signup_response = requests.post(f"{BASE_URL}/api/auth/signup", json=credentials)
        assert signup_response.status_code == 200
        token = signup_response.json()["access_token"]
        
        # Grant premium via checkout webhook
        webhook_payload = {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "customer": customer_id,
                    "customer_email": email,
                    "payment_status": "paid",
                    "mode": "subscription",
                    "subscription": subscription_id,
                    "amount_total": 999
                }
            }
        }
        requests.post(f"{BASE_URL}/api/webhook/stripe", json=webhook_payload)
        
        import time
        time.sleep(2)  # Wait for background task
        
        # Verify user is premium
        me_response = requests.get(f"{BASE_URL}/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me_response.json().get("is_premium") == True, "User should be premium before deletion test"
        
        return {
            "email": email,
            "token": token,
            "customer_id": customer_id,
            "subscription_id": subscription_id
        }
    
    def test_subscription_deleted_revokes_premium(self, premium_user_for_deletion):
        """Test that subscription.deleted revokes premium access"""
        webhook_payload = {
            "type": "customer.subscription.deleted",
            "data": {
                "object": {
                    "id": premium_user_for_deletion["subscription_id"],
                    "customer": premium_user_for_deletion["customer_id"],
                    "status": "canceled"
                }
            }
        }
        
        response = requests.post(f"{BASE_URL}/api/webhook/stripe", json=webhook_payload)
        assert response.status_code == 200
        
        import time
        time.sleep(2)  # Wait for background task
        
        # User should no longer be premium
        me_response = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {premium_user_for_deletion['token']}"}
        )
        user_data = me_response.json()
        
        assert user_data.get("is_premium") == False, f"User should not be premium after deletion. Got: {user_data}"
        assert user_data.get("subscription_status") == "expired", f"Status should be 'expired'. Got: {user_data.get('subscription_status')}"
        assert user_data.get("subscription_plan") == "free", f"Plan should be 'free'. Got: {user_data.get('subscription_plan')}"
        
        print(f"✓ Subscription deleted - premium revoked")
        print(f"  is_premium: {user_data.get('is_premium')}")
        print(f"  subscription_status: {user_data.get('subscription_status')}")
        print(f"  subscription_plan: {user_data.get('subscription_plan')}")


class TestYearlySubscription:
    """Test yearly subscription flow via webhook"""
    
    def test_yearly_plan_checkout_completed(self):
        """Test checkout for yearly plan"""
        unique_id = str(uuid.uuid4())[:8]
        email = f"yearly_test_{unique_id}@example.com"
        
        # Create user
        credentials = {"email": email, "password": "YearlyTest123!", "name": "Yearly User"}
        signup_response = requests.post(f"{BASE_URL}/api/auth/signup", json=credentials)
        assert signup_response.status_code == 200
        token = signup_response.json()["access_token"]
        
        # Send yearly checkout webhook
        webhook_payload = {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "customer": f"cus_yearly_{uuid.uuid4().hex[:12]}",
                    "customer_email": email,
                    "payment_status": "paid",
                    "mode": "subscription",
                    "subscription": f"sub_yearly_{uuid.uuid4().hex[:12]}",
                    "amount_total": 5999,  # $59.99 yearly
                    "line_items": {
                        "data": [
                            {
                                "price": {
                                    "recurring": {
                                        "interval": "year"  # Yearly subscription
                                    }
                                }
                            }
                        ]
                    }
                }
            }
        }
        
        response = requests.post(f"{BASE_URL}/api/webhook/stripe", json=webhook_payload)
        assert response.status_code == 200
        
        import time
        time.sleep(1)
        
        me_response = requests.get(f"{BASE_URL}/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        user_data = me_response.json()
        
        assert user_data.get("is_premium") == True, "User should be premium"
        assert user_data.get("subscription_plan") == "yearly", f"Plan should be 'yearly'. Got: {user_data.get('subscription_plan')}"
        
        print(f"✓ Yearly subscription checkout processed")
        print(f"  subscription_plan: {user_data.get('subscription_plan')}")


class TestHealthAndEdgeCases:
    """Health checks and edge case tests"""
    
    def test_health_endpoint(self):
        """Test API health check"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        print("✓ Health check passed")
    
    def test_webhook_invalid_json(self):
        """Test webhook with invalid JSON returns 400"""
        response = requests.post(
            f"{BASE_URL}/api/webhook/stripe",
            data="not valid json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 400, f"Expected 400 for invalid JSON, got {response.status_code}"
        print("✓ Webhook correctly rejects invalid JSON with 400")
    
    def test_webhook_no_matching_user(self):
        """Test webhook with non-existent user email doesn't crash"""
        webhook_payload = {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "customer": "cus_nonexistent",
                    "customer_email": "nonexistent_user_12345@example.com",
                    "payment_status": "paid",
                    "mode": "subscription"
                }
            }
        }
        
        # Should still return 200 (acknowledge receipt) even if user not found
        response = requests.post(f"{BASE_URL}/api/webhook/stripe", json=webhook_payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        print("✓ Webhook handles non-existent user gracefully")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
