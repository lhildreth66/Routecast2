"""
Premium Gating

Backend decorator and helper for enforcing premium entitlements.
"""

from functools import wraps
from typing import Optional, Callable, Any
from fastapi import HTTPException, Request
from .features import is_premium_feature


class PremiumLockedError(HTTPException):
    """Raised when a premium feature is accessed without entitlement."""
    
    def __init__(self, feature: str):
        super().__init__(
            status_code=403,
            detail={
                "error": "premium_locked",
                "feature": feature,
            }
        )
        self.feature = feature


def check_entitlement(subscription_id: Optional[str], feature: str) -> bool:
    """
    Check if user has entitlement for a premium feature.
    
    Args:
        subscription_id: User's subscription identifier (from request)
        feature: Feature identifier to check
    
    Returns:
        True if entitled, False otherwise
    """
    if not is_premium_feature(feature):
        # Unknown feature - fail closed
        return False
    
    # Simple check: user must have a subscription_id
    # In production, this would validate with Play/App Store
    return subscription_id is not None and len(subscription_id) > 0


def premium_gate(feature: str):
    """
    Decorator to enforce premium gating on endpoint functions.
    
    Usage:
        @premium_gate("solar_forecast")
        async def solar_forecast_endpoint(request: SolarRequest):
            ...
    
    The decorated function must accept a parameter named 'subscription_id'
    or the decorator will extract it from a 'request' parameter with 
    request.subscription_id attribute.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Extract subscription_id from kwargs or request object
            subscription_id = kwargs.get('subscription_id')
            
            if subscription_id is None:
                # Try to get from request object
                request = kwargs.get('request')
                if request and hasattr(request, 'subscription_id'):
                    subscription_id = request.subscription_id
            
            # Check entitlement
            if not check_entitlement(subscription_id, feature):
                raise PremiumLockedError(feature)
            
            # Execute the function
            return await func(*args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Extract subscription_id from kwargs or request object
            subscription_id = kwargs.get('subscription_id')
            
            if subscription_id is None:
                # Try to get from request object
                request = kwargs.get('request')
                if request and hasattr(request, 'subscription_id'):
                    subscription_id = request.subscription_id
            
            # Check entitlement
            if not check_entitlement(subscription_id, feature):
                raise PremiumLockedError(feature)
            
            # Execute the function
            return func(*args, **kwargs)
        
        # Return appropriate wrapper based on whether function is async
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def require_premium(subscription_id: Optional[str], feature: str) -> None:
    """
    Helper function to manually check premium access and raise if locked.
    
    Usage:
        require_premium(request.subscription_id, "road_sim")
        # ... proceed with premium logic
    """
    if not check_entitlement(subscription_id, feature):
        raise PremiumLockedError(feature)
