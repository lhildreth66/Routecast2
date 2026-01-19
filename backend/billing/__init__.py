"""
Billing Verification Module

Backend verification stub for Google Play purchase tokens.
TODO: Implement actual Google Play Developer API integration.
"""

from dataclasses import dataclass
from typing import Optional, Literal
from datetime import datetime, timedelta


@dataclass(frozen=True)
class VerificationRequest:
    """Request to verify a purchase token."""
    platform: Literal["android", "ios"]
    product_id: str
    purchase_token: str


@dataclass(frozen=True)
class VerificationResponse:
    """Response from purchase verification."""
    is_pro: bool
    product_id: Optional[str] = None
    expire_at: Optional[str] = None  # ISO timestamp
    error: Optional[str] = None


class BillingVerifier:
    """
    Service for verifying purchase tokens with Google Play.
    
    Current implementation is a STUB - returns mock responses.
    TODO: Integrate with Google Play Developer API:
    - https://developers.google.com/android-publisher/api-ref/rest/v3/purchases.subscriptions
    - Requires service account credentials
    - Should validate purchase token and return subscription status
    """
    
    def __init__(self):
        # TODO: Initialize Google Play Developer API client
        # from google.oauth2 import service_account
        # credentials = service_account.Credentials.from_service_account_file('service-account.json')
        # self.publisher_api = build('androidpublisher', 'v3', credentials=credentials)
        pass
    
    async def verify_purchase(self, request: VerificationRequest) -> VerificationResponse:
        """
        Verify a purchase token with the platform (Google Play/App Store).
        
        STUB IMPLEMENTATION: Returns mock response for development.
        TODO: Replace with actual API calls.
        """
        
        # Validate platform
        if request.platform not in ("android", "ios"):
            return VerificationResponse(
                is_pro=False,
                error=f"Unsupported platform: {request.platform}",
            )
        
        # Validate product ID
        valid_products = ["boondocking_pro_monthly", "boondocking_pro_yearly"]
        if request.product_id not in valid_products:
            return VerificationResponse(
                is_pro=False,
                error=f"Invalid product ID: {request.product_id}",
            )
        
        # STUB: Mock verification logic
        # TODO: Call Google Play Developer API
        # Example:
        # try:
        #     result = self.publisher_api.purchases().subscriptions().get(
        #         packageName='com.routecast.app',
        #         subscriptionId=request.product_id,
        #         token=request.purchase_token
        #     ).execute()
        #     
        #     # Check if subscription is active
        #     expiry_time_millis = int(result.get('expiryTimeMillis', 0))
        #     is_active = expiry_time_millis > int(datetime.now().timestamp() * 1000)
        #     
        #     if is_active:
        #         expire_at = datetime.fromtimestamp(expiry_time_millis / 1000).isoformat()
        #         return VerificationResponse(
        #             is_pro=True,
        #             product_id=request.product_id,
        #             expire_at=expire_at,
        #         )
        # except Exception as e:
        #     return VerificationResponse(is_pro=False, error=str(e))
        
        # MOCK RESPONSE for development
        print(f"[STUB] Verifying purchase: {request.product_id}, token: {request.purchase_token[:20]}...")
        
        # Simulate valid token format check
        if len(request.purchase_token) < 10:
            return VerificationResponse(
                is_pro=False,
                error="Invalid purchase token format",
            )
        
        # Mock active subscription
        now = datetime.now()
        if request.product_id == "boondocking_pro_monthly":
            expire_at = (now + timedelta(days=30)).isoformat()
        else:  # yearly
            expire_at = (now + timedelta(days=365)).isoformat()
        
        return VerificationResponse(
            is_pro=True,
            product_id=request.product_id,
            expire_at=expire_at,
        )


# Singleton instance
billing_verifier = BillingVerifier()
