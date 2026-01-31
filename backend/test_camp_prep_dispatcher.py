"""
Tests for Camp Prep Chat Dispatcher

Validates:
- Command parsing
- Routing to correct handlers
- Premium gating
- Response shape consistency
- Unknown command handling
"""
import pytest
from chat.camp_prep_dispatcher import dispatch, _parse_args


class TestArgParsing:
    """Test command argument parsing."""
    
    def test_parse_empty_args(self):
        result = _parse_args("/prep-checklist")
        assert result == {}
    
    def test_parse_single_arg(self):
        result = _parse_args("/power-forecast lat=34.05")
        assert result == {"lat": 34.05}
    
    def test_parse_multiple_args(self):
        result = _parse_args("/cell-starlink carrier=verizon towerDistanceKm=8 terrainObstruction=45")
        assert result == {
            "carrier": "verizon",
            "towerDistanceKm": 8,
            "terrainObstruction": 45,
        }
    
    def test_parse_boolean_args(self):
        result = _parse_args("/test enabled=true disabled=false")
        assert result == {"enabled": True, "disabled": False}
    
    def test_parse_float_args(self):
        result = _parse_args("/test value=3.14 score=0.5")
        assert result == {"value": 3.14, "score": 0.5}
    
    def test_parse_int_args(self):
        result = _parse_args("/test count=42 temp=-10")
        assert result == {"count": 42, "temp": -10}


class TestCommandRouting:
    """Test command routing to correct handlers."""
    
    def test_prep_checklist_routes_correctly(self):
        response = dispatch("/prep-checklist")
        assert response.mode == "camp_prep"
        assert response.command == "/prep-checklist"
        assert response.payload is not None
        assert "checklist" in response.payload
    
    def test_power_forecast_routes_correctly(self):
        response = dispatch("/power-forecast", subscription_id="test_sub")
        assert response.mode == "camp_prep"
        assert response.command == "/power-forecast"
        assert response.premium.feature == "solar_forecast"
    
    def test_propane_usage_routes_correctly(self):
        response = dispatch("/propane-usage", subscription_id="test_sub")
        assert response.mode == "camp_prep"
        assert response.command == "/propane-usage"
        assert response.premium.feature == "propane_usage"
    
    def test_water_plan_routes_correctly(self):
        response = dispatch("/water-plan", subscription_id="test_sub")
        assert response.mode == "camp_prep"
        assert response.command == "/water-plan"
        assert response.premium.feature == "water_budget"
    
    def test_road_sim_routes_correctly(self):
        response = dispatch("/road-sim", subscription_id="test_sub")
        assert response.mode == "camp_prep"
        assert response.command == "/road-sim"
        assert response.premium.feature == "road_passability"
    
    def test_cell_starlink_routes_correctly(self):
        response = dispatch("/cell-starlink", subscription_id="test_sub")
        assert response.mode == "camp_prep"
        assert response.command == "/cell-starlink"
        assert response.premium.feature == "connectivity_prediction"
    
    def test_camp_index_routes_correctly(self):
        response = dispatch("/camp-index", subscription_id="test_sub")
        assert response.mode == "camp_prep"
        assert response.command == "/camp-index"
        assert response.premium.feature == "campsite_index"


class TestPremiumGating:
    """Test premium feature gating."""
    
    def test_prep_checklist_free_tier(self):
        response = dispatch("/prep-checklist")
        assert response.premium.required is False
        assert response.premium.locked is False
        assert response.error is None
    
    def test_power_forecast_locked_without_subscription(self):
        response = dispatch("/power-forecast")
        assert response.premium.required is True
        assert response.premium.locked is True
        assert response.error == "premium_locked"
        assert response.payload is None
        assert "premium subscription" in response.human
    
    def test_power_forecast_unlocked_with_subscription(self):
        response = dispatch("/power-forecast", subscription_id="test_sub")
        assert response.premium.required is True
        assert response.premium.locked is False
        assert response.error is None
        assert response.payload is not None
    
    def test_propane_locked_without_subscription(self):
        response = dispatch("/propane-usage")
        assert response.premium.locked is True
        assert response.error == "premium_locked"
    
    def test_road_sim_locked_without_subscription(self):
        response = dispatch("/road-sim")
        assert response.premium.locked is True
        assert response.error == "premium_locked"
    
    def test_all_premium_commands_locked_without_sub(self):
        premium_commands = [
            "/power-forecast",
            "/propane-usage",
            "/water-plan",
            "/terrain-shade",
            "/wind-shelter",
            "/road-sim",
            "/cell-starlink",
            "/camp-index",
            "/claim-log",
        ]
        for cmd in premium_commands:
            response = dispatch(cmd)
            assert response.premium.locked is True, f"{cmd} should be locked"
            assert response.error == "premium_locked", f"{cmd} should have error"


class TestResponseShape:
    """Test response shape consistency."""
    
    def test_response_has_required_fields(self):
        response = dispatch("/prep-checklist")
        assert hasattr(response, "mode")
        assert hasattr(response, "command")
        assert hasattr(response, "human")
        assert hasattr(response, "payload")
        assert hasattr(response, "premium")
        assert hasattr(response, "error")
    
    def test_premium_info_shape(self):
        response = dispatch("/power-forecast")
        assert hasattr(response.premium, "required")
        assert hasattr(response.premium, "locked")
        assert hasattr(response.premium, "feature")
        assert isinstance(response.premium.required, bool)
        assert isinstance(response.premium.locked, bool)
    
    def test_to_dict_serialization(self):
        response = dispatch("/prep-checklist")
        result = response.to_dict()
        assert "mode" in result
        assert "command" in result
        assert "human" in result
        assert "payload" in result
        assert "premium" in result
        assert "error" in result
        assert isinstance(result["premium"], dict)


class TestUnknownCommands:
    """Test handling of unknown commands."""
    
    def test_unknown_command_returns_error(self):
        response = dispatch("/unknown-command")
        assert response.error == "unknown_command"
        assert response.payload is not None
        assert "supported_commands" in response.payload
    
    def test_unknown_command_lists_supported(self):
        response = dispatch("/invalid")
        supported = response.payload["supported_commands"]
        assert "/prep-checklist" in supported
        assert "/power-forecast" in supported
        assert "/road-sim" in supported
    
    def test_invalid_format_without_slash(self):
        response = dispatch("hello")
        assert response.error == "invalid_format"
        assert "Commands must start with /" in response.human


class TestDeterminism:
    """Test deterministic behavior."""
    
    def test_same_command_same_result(self):
        response1 = dispatch("/power-forecast lat=34.05 lon=-111.03", subscription_id="test")
        response2 = dispatch("/power-forecast lat=34.05 lon=-111.03", subscription_id="test")
        # Should have same payload structure
        assert response1.command == response2.command
        assert response1.premium.locked == response2.premium.locked
        assert response1.error == response2.error
    
    def test_prep_checklist_consistent(self):
        responses = [dispatch("/prep-checklist") for _ in range(10)]
        # All should have checklist
        for r in responses:
            assert "checklist" in r.payload
            assert isinstance(r.payload["checklist"], list)


class TestCommandWithArguments:
    """Test commands with various arguments."""
    
    def test_power_forecast_with_args(self):
        response = dispatch(
            "/power-forecast lat=34.05 lon=-111.03 panelWatts=400 shadePct=20",
            subscription_id="test",
        )
        assert response.error is None
        assert response.payload is not None
        assert "daily_wh" in response.payload or response.error == "calculation_error"
    
    def test_cell_starlink_with_full_args(self):
        response = dispatch(
            "/cell-starlink carrier=verizon towerDistanceKm=8 terrainObstruction=45 horizonSouthDeg=30 canopyPct=60",
            subscription_id="test",
        )
        assert response.error is None
        assert response.payload is not None
        assert "cell_bars" in response.payload or response.error == "calculation_error"
    
    def test_road_sim_with_soil_type(self):
        response = dispatch(
            "/road-sim precip72h=30 slopePct=8 minTempF=35 soilType=clay",
            subscription_id="test",
        )
        assert response.error is None
        assert response.payload is not None
        assert "score" in response.payload or response.error == "calculation_error"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
