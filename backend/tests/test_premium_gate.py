"""
Tests for Premium Gating

Tests the premium_gate decorator and helper functions.
"""

import pytest
from common.premium_gate import (
    premium_gate,
    require_premium,
    check_entitlement,
    PremiumLockedError,
)
from common.features import (
    SOLAR_FORECAST,
    PROPANE_USAGE,
    ROAD_SIM,
    CELL_STARLINK,
    CLAIM_LOG,
)


class TestCheckEntitlement:
    """Test entitlement checking logic."""
    
    def test_no_subscription_id_returns_false(self):
        assert check_entitlement(None, SOLAR_FORECAST) is False
        assert check_entitlement("", SOLAR_FORECAST) is False
    
    def test_valid_subscription_id_returns_true(self):
        assert check_entitlement("test_sub_123", SOLAR_FORECAST) is True
        assert check_entitlement("premium_user", PROPANE_USAGE) is True
    
    def test_unknown_feature_returns_false(self):
        assert check_entitlement("test_sub_123", "unknown_feature") is False
    
    def test_all_premium_features_check(self):
        sub_id = "test_sub"
        assert check_entitlement(sub_id, SOLAR_FORECAST) is True
        assert check_entitlement(sub_id, PROPANE_USAGE) is True
        assert check_entitlement(sub_id, ROAD_SIM) is True
        assert check_entitlement(sub_id, CELL_STARLINK) is True
        assert check_entitlement(sub_id, CLAIM_LOG) is True


class TestRequirePremium:
    """Test require_premium helper function."""
    
    def test_no_subscription_raises_error(self):
        with pytest.raises(PremiumLockedError) as exc_info:
            require_premium(None, SOLAR_FORECAST)
        
        assert exc_info.value.status_code == 403
        assert exc_info.value.detail["error"] == "premium_locked"
        assert exc_info.value.detail["feature"] == SOLAR_FORECAST
    
    def test_empty_subscription_raises_error(self):
        with pytest.raises(PremiumLockedError) as exc_info:
            require_premium("", PROPANE_USAGE)
        
        assert exc_info.value.detail["feature"] == PROPANE_USAGE
    
    def test_valid_subscription_does_not_raise(self):
        # Should not raise
        require_premium("test_sub_123", SOLAR_FORECAST)
        require_premium("premium_user", ROAD_SIM)
    
    def test_error_includes_feature_id(self):
        features = [SOLAR_FORECAST, PROPANE_USAGE, ROAD_SIM, CELL_STARLINK, CLAIM_LOG]
        
        for feature in features:
            with pytest.raises(PremiumLockedError) as exc_info:
                require_premium(None, feature)
            
            assert exc_info.value.feature == feature
            assert exc_info.value.detail["feature"] == feature


class TestPremiumGateDecorator:
    """Test premium_gate decorator."""
    
    @pytest.mark.asyncio
    async def test_async_function_without_subscription_raises(self):
        @premium_gate(SOLAR_FORECAST)
        async def solar_forecast_func(subscription_id=None):
            return {"forecast": "sunny"}
        
        with pytest.raises(PremiumLockedError) as exc_info:
            await solar_forecast_func(subscription_id=None)
        
        assert exc_info.value.detail["feature"] == SOLAR_FORECAST
    
    @pytest.mark.asyncio
    async def test_async_function_with_subscription_executes(self):
        @premium_gate(SOLAR_FORECAST)
        async def solar_forecast_func(subscription_id=None):
            return {"forecast": "sunny"}
        
        result = await solar_forecast_func(subscription_id="test_sub")
        assert result == {"forecast": "sunny"}
    
    def test_sync_function_without_subscription_raises(self):
        @premium_gate(PROPANE_USAGE)
        def propane_usage_func(subscription_id=None):
            return {"usage": 5.2}
        
        with pytest.raises(PremiumLockedError) as exc_info:
            propane_usage_func(subscription_id=None)
        
        assert exc_info.value.detail["feature"] == PROPANE_USAGE
    
    def test_sync_function_with_subscription_executes(self):
        @premium_gate(PROPANE_USAGE)
        def propane_usage_func(subscription_id=None):
            return {"usage": 5.2}
        
        result = propane_usage_func(subscription_id="test_sub")
        assert result == {"usage": 5.2}
    
    @pytest.mark.asyncio
    async def test_decorator_extracts_subscription_from_request(self):
        """Test that decorator can extract subscription_id from request object."""
        
        class MockRequest:
            def __init__(self, subscription_id):
                self.subscription_id = subscription_id
        
        @premium_gate(ROAD_SIM)
        async def road_sim_func(request=None):
            return {"score": 85}
        
        # Without subscription should raise
        with pytest.raises(PremiumLockedError):
            await road_sim_func(request=MockRequest(None))
        
        # With subscription should execute
        result = await road_sim_func(request=MockRequest("test_sub"))
        assert result == {"score": 85}
    
    def test_feature_id_matches_in_error(self):
        """Test that raised errors contain correct feature IDs."""
        
        features = {
            SOLAR_FORECAST: lambda: "solar",
            PROPANE_USAGE: lambda: "propane",
            ROAD_SIM: lambda: "road",
            CELL_STARLINK: lambda: "connectivity",
            CLAIM_LOG: lambda: "claim",
        }
        
        for feature, func in features.items():
            decorated = premium_gate(feature)(func)
            
            with pytest.raises(PremiumLockedError) as exc_info:
                decorated(subscription_id=None)
            
            assert exc_info.value.feature == feature
            assert exc_info.value.detail["feature"] == feature


class TestPremiumLockedError:
    """Test PremiumLockedError exception."""
    
    def test_error_status_code(self):
        error = PremiumLockedError(SOLAR_FORECAST)
        assert error.status_code == 403
    
    def test_error_detail_shape(self):
        error = PremiumLockedError(SOLAR_FORECAST)
        assert error.detail == {
            "error": "premium_locked",
            "feature": SOLAR_FORECAST,
        }
    
    def test_error_has_feature_attribute(self):
        error = PremiumLockedError(ROAD_SIM)
        assert error.feature == ROAD_SIM
    
    def test_all_features_create_valid_errors(self):
        features = [SOLAR_FORECAST, PROPANE_USAGE, ROAD_SIM, CELL_STARLINK, CLAIM_LOG]
        
        for feature in features:
            error = PremiumLockedError(feature)
            assert error.status_code == 403
            assert error.detail["error"] == "premium_locked"
            assert error.detail["feature"] == feature
            assert error.feature == feature
