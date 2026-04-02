"""
User and Subscription Models for RouteCast
"""
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List, Literal
from datetime import datetime
from enum import Enum


class SubscriptionStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    TRIALING = "trialing"
    CANCELING = "canceling"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    EXPIRED = "expired"


class EntitlementState(str, Enum):
    FREE_TIER = "FREE_TIER"
    TRIAL_ACTIVE = "TRIAL_ACTIVE"
    SUBSCRIPTION_ACTIVE = "SUBSCRIPTION_ACTIVE"
    EXPIRED = "EXPIRED"


class SubscriptionProvider(str, Enum):
    STRIPE = "stripe"
    APPLE = "apple"
    GOOGLE = "google"
    ADMIN = "admin"  # Manually granted by admin


class SubscriptionPlan(str, Enum):
    FREE = "free"
    MONTHLY = "monthly"
    YEARLY = "yearly"


# ==================== User Models ====================

class UserBase(BaseModel):
    email: EmailStr


class UserCreate(UserBase):
    password: str = Field(..., min_length=8)
    name: Optional[str] = None
    plan: Optional[str] = "monthly"  # "monthly" or "yearly"


class UserLogin(UserBase):
    password: str


class UserInDB(UserBase):
    user_id: str
    name: Optional[str] = None
    hashed_password: str
    email_verified: bool = False
    created_at: datetime
    updated_at: datetime

    # Subscription fields
    subscription_status: SubscriptionStatus = SubscriptionStatus.INACTIVE
    subscription_provider: Optional[SubscriptionProvider] = None
    subscription_plan: SubscriptionPlan = SubscriptionPlan.FREE
    subscription_expiration: Optional[datetime] = None
    stripe_customer_id: Optional[str] = None
    stripe_subscription_id: Optional[str] = None
    apple_original_transaction_id: Optional[str] = None
    google_purchase_token: Optional[str] = None

    # Trial tracking
    trial_used: bool = False
    trial_start: Optional[datetime] = None
    trial_end: Optional[datetime] = None


class UserResponse(UserBase):
    user_id: str
    name: Optional[str] = None
    email_verified: bool
    created_at: datetime
    subscription_status: SubscriptionStatus
    subscription_plan: SubscriptionPlan
    subscription_provider: Optional[SubscriptionProvider] = None
    subscription_expiration: Optional[datetime] = None
    is_premium: bool = False


class UserMeResponse(UserResponse):
    """Extended response for /api/me endpoint"""
    entitlements: List[str] = []
    trial_available: bool = False
    trial_days_remaining: Optional[int] = None
    entitlement_state: EntitlementState = EntitlementState.FREE_TIER


# ==================== Auth Models ====================

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenRefreshRequest(BaseModel):
    refresh_token: str


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8)


class EmailVerificationRequest(BaseModel):
    token: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8)


# ==================== Subscription Models ====================

class SubscriptionInfo(BaseModel):
    status: SubscriptionStatus
    plan: SubscriptionPlan
    provider: Optional[SubscriptionProvider] = None
    expiration: Optional[datetime] = None
    is_active: bool = False
    can_access_premium: bool = False


class CreateCheckoutRequest(BaseModel):
    plan: SubscriptionPlan
    origin_url: str


class CheckoutResponse(BaseModel):
    checkout_url: str
    session_id: str


class SubscriptionWebhookPayload(BaseModel):
    event_type: str
    data: dict


# ==================== Apple/Google Receipt Models ====================

class AppleReceiptVerifyRequest(BaseModel):
    receipt_data: str
    product_id: str


class GoogleReceiptVerifyRequest(BaseModel):
    purchase_token: str
    product_id: str
    package_name: str = "com.routecast.app"


class ReceiptVerifyResponse(BaseModel):
    valid: bool
    subscription_status: SubscriptionStatus
    expiration: Optional[datetime] = None
    message: str


# ==================== Admin Models ====================

class AdminUserListResponse(BaseModel):
    users: List[UserResponse]
    total: int
    page: int
    per_page: int


class AdminGrantSubscriptionRequest(BaseModel):
    user_id: str
    plan: SubscriptionPlan
    duration_days: int = 30
    reason: Optional[str] = None


class AdminRevokeSubscriptionRequest(BaseModel):
    user_id: str
    reason: Optional[str] = None


# ==================== Entitlements ====================

# Define what features are available at each tier
ENTITLEMENTS = {
    SubscriptionPlan.FREE: [
        "basic_route_weather",
        "limited_alerts",  # Max 1 route monitor
    ],
    SubscriptionPlan.MONTHLY: [
        "basic_route_weather",
        "unlimited_alerts",
        "route_monitoring",
        "push_notifications",
        "ai_assistant",
        "advanced_weather",
        "truck_features",
        "boondocking_features",
        "export_routes",
    ],
    SubscriptionPlan.YEARLY: [
        "basic_route_weather",
        "unlimited_alerts",
        "route_monitoring",
        "push_notifications",
        "ai_assistant",
        "advanced_weather",
        "truck_features",
        "boondocking_features",
        "export_routes",
        "priority_support",
    ],
}

# Features that require premium subscription
PREMIUM_FEATURES = [
    "unlimited_alerts",
    "route_monitoring",
    "push_notifications",
    "ai_assistant",
    "advanced_weather",
    "truck_features",
    "boondocking_features",
    "export_routes",
    "priority_support",
]


def get_user_entitlements(user: UserInDB) -> List[str]:
    """Get list of entitlements for a user based on their subscription"""
    if user.subscription_status in [SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING, SubscriptionStatus.CANCELING]:
        return ENTITLEMENTS.get(user.subscription_plan, ENTITLEMENTS[SubscriptionPlan.FREE])
    return ENTITLEMENTS[SubscriptionPlan.FREE]


def user_has_entitlement(user: UserInDB, entitlement: str) -> bool:
    """Check if user has a specific entitlement"""
    return entitlement in get_user_entitlements(user)


def user_is_premium(user: UserInDB) -> bool:
    """Check if user has premium access"""
    if user.subscription_status not in [SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING, SubscriptionStatus.CANCELING]:
        return False
    return user.subscription_plan in [SubscriptionPlan.MONTHLY, SubscriptionPlan.YEARLY]
