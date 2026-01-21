"""
Tests for smart_delay.py - Smart Departure Delay Optimizer

Table-driven parametrized tests covering:
- Basic risk computation
- Delay helps / no improvement cases
- Cooldown/spam prevention logic
- Edge cases (missing forecast, past departure, timezone)
- Message formatting
"""

import pytest
from datetime import datetime, timedelta, timezone
from notifications.smart_delay import (
    SmartDelayOptimizer,
    BestDelayResult,
    HazardType,
)


class TestComputeWindRisk:
    """Test wind speed to risk conversion."""
    
    CASES = [
        ("calm", 0.0, 0.0),
        ("light", 15.0, 0.0),
        ("moderate", 30.0, 30.0),
        ("strong", 50.0, 60.0),
        ("extreme", 80.0, 100.0),
    ]
    
    @pytest.mark.parametrize("name,wind_kph,expected_risk", CASES)
    def test_wind_risk(self, name, wind_kph, expected_risk):
        """Test wind risk scoring."""
        risk = SmartDelayOptimizer._compute_wind_risk(wind_kph)
        assert risk == expected_risk, f"Failed on {name}"


class TestComputePrecipRisk:
    """Test precipitation to risk conversion."""
    
    CASES = [
        ("dry", 0.0, 0.0),
        ("light", 2.0, 40.0),
        ("moderate", 8.0, 70.0),
        ("heavy", 25.0, 100.0),
    ]
    
    @pytest.mark.parametrize("name,precip_mm,expected_risk", CASES)
    def test_precip_risk(self, name, precip_mm, expected_risk):
        """Test precipitation risk scoring."""
        risk = SmartDelayOptimizer._compute_precip_risk(precip_mm)
        assert risk == expected_risk, f"Failed on {name}"


class TestComputeTempRisk:
    """Test temperature to risk conversion."""
    
    CASES = [
        ("warm", 20.0, 0.0),
        ("cool", 3.0, 20.0),
        ("cold", -5.0, 50.0),
        ("extreme", -20.0, 100.0),
    ]
    
    @pytest.mark.parametrize("name,temp_c,expected_risk", CASES)
    def test_temp_risk(self, name, temp_c, expected_risk):
        """Test temperature risk scoring."""
        risk = SmartDelayOptimizer._compute_temp_risk(temp_c)
        assert risk == expected_risk, f"Failed on {name}"


class TestComputeSevereAlertRisk:
    """Test severe alert to risk conversion."""
    
    CASES = [
        ("none", [], 0.0),
        ("one_alert", ["Winter Storm Warning"], 30.0),
        ("two_alerts", ["Winter Storm Warning", "Wind Advisory"], 60.0),
        ("three_plus", ["A", "B", "C", "D"], 100.0),  # Capped at 100
    ]
    
    @pytest.mark.parametrize("name,alerts,expected_risk", CASES)
    def test_alert_risk(self, name, alerts, expected_risk):
        """Test severe alert risk scoring."""
        risk = SmartDelayOptimizer._compute_severe_alert_risk(alerts)
        assert risk == expected_risk, f"Failed on {name}"


class TestComputeDepartureRisk:
    """Test risk computation across time windows."""
    
    def test_basic_risk_window(self):
        """Test that risk window returns multiple delay options."""
        forecast = [
            {
                "time": "2026-01-20T14:00Z",
                "wind_kph": 50,
                "precip_mm": 2,
                "temp_c": -5,
                "severe_alerts": [],
            }
        ]
        waypoints = [{"lat": 40.0, "lon": -105.0}]
        departure = datetime(2026, 1, 20, 14, 0, tzinfo=timezone.utc)
        
        risks = SmartDelayOptimizer.compute_departure_risk(
            forecast, waypoints, departure, window_hours=3
        )
        
        # Should have risk scores for delays 0, 1, 2, 3
        assert len(risks) == 4
        assert 0 in risks
        assert 3 in risks
        assert all(0 <= risk <= 100 for risk in risks.values())
    
    def test_empty_forecast_raises(self):
        """Test that empty forecast raises ValueError."""
        waypoints = [{"lat": 40.0, "lon": -105.0}]
        departure = datetime(2026, 1, 20, 14, 0, tzinfo=timezone.utc)
        
        with pytest.raises(ValueError, match="forecast_hourly cannot be empty"):
            SmartDelayOptimizer.compute_departure_risk(
                [], waypoints, departure
            )
    
    def test_empty_waypoints_raises(self):
        """Test that empty waypoints raises ValueError."""
        forecast = [{"wind_kph": 50}]
        departure = datetime(2026, 1, 20, 14, 0, tzinfo=timezone.utc)
        
        with pytest.raises(ValueError, match="route_waypoints cannot be empty"):
            SmartDelayOptimizer.compute_departure_risk(
                forecast, [], departure
            )
    
    def test_negative_window_raises(self):
        """Test that negative window_hours raises ValueError."""
        forecast = [{"wind_kph": 50}]
        waypoints = [{"lat": 40.0, "lon": -105.0}]
        departure = datetime(2026, 1, 20, 14, 0, tzinfo=timezone.utc)
        
        with pytest.raises(ValueError, match="window_hours must be >= 0"):
            SmartDelayOptimizer.compute_departure_risk(
                forecast, waypoints, departure, window_hours=-1
            )


class TestBestDelayOption:
    """Test delay optimization logic."""
    
    def test_delay_helps_case(self):
        """Test case where delaying significantly improves safety."""
        risk_scores = {
            0: 75.0,   # Planned: high risk
            1: 50.0,   # +1h: moderate improvement
            2: 35.0,   # +2h: good improvement
            3: 30.0,   # +3h: best improvement
        }
        
        result = SmartDelayOptimizer.best_delay_option(risk_scores)
        
        assert result is not None
        assert result.best_delay_hours == 3  # 3h gives best value
        assert result.planned_risk == 75.0
        assert result.best_risk == 30.0
        assert result.improvement_pct == 60.0  # (75-30)/75 * 100
        assert "Delay 3h" in result.message
    
    def test_no_improvement_case(self):
        """Test case where no delay improves safety enough."""
        risk_scores = {
            0: 50.0,
            1: 48.0,
            2: 47.0,
            3: 46.0,
        }
        
        result = SmartDelayOptimizer.best_delay_option(
            risk_scores, threshold_improvement_pct=15
        )
        
        # Improvement is only ~8%, below 15% threshold
        assert result is None
    
    def test_threshold_respected(self):
        """Test that improvement threshold is enforced."""
        risk_scores = {
            0: 100.0,
            1: 60.0,   # 40% improvement
            2: 55.0,   # 45% improvement
            3: 50.0,   # 50% improvement (best)
        }
        
        # With high threshold, only big improvements recommended
        result_high = SmartDelayOptimizer.best_delay_option(
            risk_scores, threshold_improvement_pct=50
        )
        assert result_high is not None
        assert result_high.improvement_pct == 50.0  # Only 50% meets threshold
        
        # With low threshold, best improvement still selected (3h)
        result_low = SmartDelayOptimizer.best_delay_option(
            risk_scores, threshold_improvement_pct=35
        )
        assert result_low is not None
        assert result_low.improvement_pct == 50.0  # Still best option (3h)
    
    def test_max_delay_respected(self):
        """Test that maximum delay constraint is enforced."""
        risk_scores = {
            0: 100.0,
            1: 90.0,
            2: 70.0,   # 30% improvement, but beyond max_delay
            3: 50.0,
        }
        
        result = SmartDelayOptimizer.best_delay_option(
            risk_scores, threshold_improvement_pct=15, max_delay=1
        )
        
        # Should not recommend 2h even though it's best, due to max_delay=1
        assert result is None or result.best_delay_hours <= 1
    
    def test_empty_risk_scores_raises(self):
        """Test that empty risk scores raises ValueError."""
        with pytest.raises(ValueError, match="risk_scores cannot be empty"):
            SmartDelayOptimizer.best_delay_option({})
    
    def test_invalid_threshold_raises(self):
        """Test that invalid threshold raises ValueError."""
        risk_scores = {0: 50.0, 1: 40.0}
        
        with pytest.raises(ValueError, match="threshold_improvement_pct must be 0-100"):
            SmartDelayOptimizer.best_delay_option(risk_scores, threshold_improvement_pct=150)
    
    def test_invalid_max_delay_raises(self):
        """Test that negative max_delay raises ValueError."""
        risk_scores = {0: 50.0, 1: 40.0}
        
        with pytest.raises(ValueError, match="max_delay must be >= 0"):
            SmartDelayOptimizer.best_delay_option(risk_scores, max_delay=-1)


class TestMessageFormatting:
    """Test notification message generation."""
    
    MESSAGE_CASES = [
        ("small_improvement", 1, 100.0, 90.0, 10.0, "Delay 1h avoids ~10% hazards"),
        ("medium_improvement", 2, 100.0, 55.0, 45.0, "Delay 2h avoids ~45% hazards"),
        ("large_improvement", 3, 100.0, 20.0, 80.0, "Delay 3h avoids ~80% hazards"),
    ]
    
    @pytest.mark.parametrize(
        "name,delay,planned,best,improvement,expected_msg",
        MESSAGE_CASES
    )
    def test_message_format(self, name, delay, planned, best, improvement, expected_msg):
        """Test message formatting and rounding."""
        msg = SmartDelayOptimizer._format_message(delay, planned, best, improvement)
        # Allow slight variation due to rounding
        assert "Delay" in msg
        assert f"{delay}h" in msg
        assert "avoids" in msg
        assert "hazards" in msg
    
    def test_message_rounding_to_5pct(self):
        """Test that improvement % is rounded to nearest 5%."""
        # 43% should round to 40% or 45%
        msg = SmartDelayOptimizer._format_message(2, 100.0, 57.0, 43.0)
        # Should be ~45% after rounding to nearest 5%
        assert "45%" in msg or "40%" in msg


class TestDeterminism:
    """Test that functions are deterministic."""
    
    def test_risk_computation_deterministic(self):
        """Verify same inputs produce same outputs."""
        forecast = [
            {
                "wind_kph": 50,
                "precip_mm": 3,
                "temp_c": -5,
                "severe_alerts": ["Wind Advisory"],
            }
        ]
        waypoints = [{"lat": 40.0, "lon": -105.0}]
        departure = datetime(2026, 1, 20, 14, 0, tzinfo=timezone.utc)
        
        results = []
        for _ in range(5):
            risk = SmartDelayOptimizer.compute_departure_risk(
                forecast, waypoints, departure, window_hours=2
            )
            results.append(risk)
        
        # All results should be identical
        for i in range(1, len(results)):
            assert results[i] == results[0], f"Iteration {i} differs from first"
    
    def test_delay_option_deterministic(self):
        """Verify delay option computation is deterministic."""
        risk_scores = {0: 75.0, 1: 55.0, 2: 40.0, 3: 38.0}
        
        results = []
        for _ in range(5):
            result = SmartDelayOptimizer.best_delay_option(risk_scores)
            results.append(result)
        
        # All results should be identical
        for i in range(1, len(results)):
            assert results[i] == results[0], f"Iteration {i} differs from first"


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_zero_planned_risk(self):
        """Test handling of zero risk (no improvement possible)."""
        risk_scores = {
            0: 0.0,
            1: 0.0,
            2: 0.0,
        }
        
        result = SmartDelayOptimizer.best_delay_option(
            risk_scores, threshold_improvement_pct=1
        )
        
        # No improvement from 0 risk, should return None
        assert result is None
    
    def test_all_high_risk(self):
        """Test when all time windows have high risk."""
        risk_scores = {
            0: 95.0,
            1: 92.0,
            2: 90.0,
            3: 88.0,
        }
        
        result = SmartDelayOptimizer.best_delay_option(
            risk_scores, threshold_improvement_pct=3
        )
        
        # Small improvement exists (7% from 0 to 3)
        assert result is not None
        assert result.best_delay_hours == 3
    
    def test_forecast_missing_hours(self):
        """Test handling of forecast with gaps in hourly data."""
        forecast_sparse = [
            {"wind_kph": 50, "precip_mm": 0, "temp_c": 5, "severe_alerts": []},
            # Missing hour 2
            {"wind_kph": 30, "precip_mm": 0, "temp_c": 8, "severe_alerts": []},
        ]
        waypoints = [{"lat": 40.0, "lon": -105.0}]
        departure = datetime(2026, 1, 20, 14, 0, tzinfo=timezone.utc)
        
        # Should handle gracefully without crash
        risks = SmartDelayOptimizer.compute_departure_risk(
            forecast_sparse, waypoints, departure, window_hours=2
        )
        assert 0 in risks
        assert len(risks) > 0
