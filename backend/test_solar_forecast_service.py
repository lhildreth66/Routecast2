"""
Unit Tests for Solar Forecast Service

Uses pytest + table-driven tests for comprehensive coverage.
All tests are deterministic and isolated (no external dependencies).
"""

import pytest
from datetime import datetime
from solar_forecast_service import (
    SolarCondition,
    SolarForecast,
    SolarForecastService,
    calculate_sunrise_sunset_impact,
)


class TestCalculateSolarPotential:
    """Test suite for calculate_solar_potential pure function."""
    
    # Table-driven test cases: (description, condition, expected_min, expected_max)
    SOLAR_POTENTIAL_CASES = [
        (
            "clear_sky",
            SolarCondition(
                timestamp="2026-01-18T12:00:00Z",
                latitude=40.0,
                longitude=-88.0,
                cloud_cover_percent=0,
                uv_index=8.0,
                solar_irradiance_watts_m2=900,
                visibility_km=15,
            ),
            80.0,  # Expected high potential
            95.0,
        ),
        (
            "overcast",
            SolarCondition(
                timestamp="2026-01-18T12:00:00Z",
                latitude=40.0,
                longitude=-88.0,
                cloud_cover_percent=100,
                uv_index=0.5,
                solar_irradiance_watts_m2=50,
                visibility_km=2,
            ),
            0.0,
            10.0,
        ),
        (
            "partly_cloudy",
            SolarCondition(
                timestamp="2026-01-18T12:00:00Z",
                latitude=40.0,
                longitude=-88.0,
                cloud_cover_percent=50,
                uv_index=4.0,
                solar_irradiance_watts_m2=500,
                visibility_km=10,
            ),
            40.0,
            60.0,
        ),
        (
            "equatorial_noon",
            SolarCondition(
                timestamp="2026-01-18T12:00:00Z",
                latitude=0.0,
                longitude=0.0,
                cloud_cover_percent=10,
                uv_index=11.0,
                solar_irradiance_watts_m2=1200,
                visibility_km=20,
            ),
            85.0,
            100.0,
        ),
        (
            "polar_low_sun",
            SolarCondition(
                timestamp="2026-01-18T12:00:00Z",
                latitude=80.0,
                longitude=0.0,
                cloud_cover_percent=20,
                uv_index=2.0,
                solar_irradiance_watts_m2=200,
                visibility_km=10,
            ),
            45.0,
            60.0,
        ),
    ]
    
    @pytest.mark.parametrize(
        "name,condition,expected_min,expected_max",
        SOLAR_POTENTIAL_CASES,
        ids=[c[0] for c in SOLAR_POTENTIAL_CASES],
    )
    def test_calculate_solar_potential_range(
        self, name, condition, expected_min, expected_max
    ):
        """Test solar potential calculation with various weather conditions."""
        result = SolarForecastService.calculate_solar_potential(condition)
        
        assert expected_min <= result <= expected_max, (
            f"{name}: Expected potential between {expected_min}-{expected_max}, "
            f"got {result}"
        )
        assert 0 <= result <= 100, "Potential should always be 0-100"
    
    # Input validation test cases
    INVALID_INPUT_CASES = [
        (
            "invalid_latitude_high",
            SolarCondition(
                timestamp="2026-01-18T12:00:00Z",
                latitude=91.0,  # Invalid
                longitude=0.0,
                cloud_cover_percent=50,
                uv_index=5.0,
                solar_irradiance_watts_m2=500,
                visibility_km=10,
            ),
        ),
        (
            "invalid_latitude_low",
            SolarCondition(
                timestamp="2026-01-18T12:00:00Z",
                latitude=-91.0,  # Invalid
                longitude=0.0,
                cloud_cover_percent=50,
                uv_index=5.0,
                solar_irradiance_watts_m2=500,
                visibility_km=10,
            ),
        ),
        (
            "invalid_longitude",
            SolarCondition(
                timestamp="2026-01-18T12:00:00Z",
                latitude=40.0,
                longitude=181.0,  # Invalid
                cloud_cover_percent=50,
                uv_index=5.0,
                solar_irradiance_watts_m2=500,
                visibility_km=10,
            ),
        ),
        (
            "invalid_cloud_cover_high",
            SolarCondition(
                timestamp="2026-01-18T12:00:00Z",
                latitude=40.0,
                longitude=0.0,
                cloud_cover_percent=101,  # Invalid
                uv_index=5.0,
                solar_irradiance_watts_m2=500,
                visibility_km=10,
            ),
        ),
        (
            "invalid_cloud_cover_low",
            SolarCondition(
                timestamp="2026-01-18T12:00:00Z",
                latitude=40.0,
                longitude=0.0,
                cloud_cover_percent=-1,  # Invalid
                uv_index=5.0,
                solar_irradiance_watts_m2=500,
                visibility_km=10,
            ),
        ),
        (
            "invalid_uv_index",
            SolarCondition(
                timestamp="2026-01-18T12:00:00Z",
                latitude=40.0,
                longitude=0.0,
                cloud_cover_percent=50,
                uv_index=-1.0,  # Invalid
                solar_irradiance_watts_m2=500,
                visibility_km=10,
            ),
        ),
        (
            "invalid_irradiance",
            SolarCondition(
                timestamp="2026-01-18T12:00:00Z",
                latitude=40.0,
                longitude=0.0,
                cloud_cover_percent=50,
                uv_index=5.0,
                solar_irradiance_watts_m2=-100,  # Invalid
                visibility_km=10,
            ),
        ),
        (
            "invalid_visibility",
            SolarCondition(
                timestamp="2026-01-18T12:00:00Z",
                latitude=40.0,
                longitude=0.0,
                cloud_cover_percent=50,
                uv_index=5.0,
                solar_irradiance_watts_m2=500,
                visibility_km=-1,  # Invalid
            ),
        ),
    ]
    
    @pytest.mark.parametrize(
        "name,condition",
        INVALID_INPUT_CASES,
        ids=[c[0] for c in INVALID_INPUT_CASES],
    )
    def test_invalid_inputs_raise_error(self, name, condition):
        """Test that invalid inputs raise ValueError."""
        with pytest.raises(ValueError):
            SolarForecastService.calculate_solar_potential(condition)


class TestEvaluateSolarFavorability:
    """Test suite for evaluate_solar_favorability."""
    
    FAVORABILITY_CASES = [
        ("excellent_conditions", 90.0, 900.0, True),
        ("good_conditions", 75.0, 600.0, True),
        ("acceptable_conditions", 60.0, 100.0, True),
        ("marginal_potential", 59.0, 600.0, False),  # Potential too low
        ("low_irradiance", 75.0, 99.0, False),  # Irradiance too low
        ("both_marginal", 50.0, 90.0, False),
        ("completely_unfavorable", 10.0, 10.0, False),
    ]
    
    @pytest.mark.parametrize(
        "name,potential,irradiance,expected",
        FAVORABILITY_CASES,
        ids=[c[0] for c in FAVORABILITY_CASES],
    )
    def test_evaluate_solar_favorability(
        self, name, potential, irradiance, expected
    ):
        """Test favorability evaluation with various potential and irradiance values."""
        result = SolarForecastService.evaluate_solar_favorability(
            potential, irradiance
        )
        assert result == expected, (
            f"{name}: Expected {expected}, got {result} "
            f"(potential={potential}, irradiance={irradiance})"
        )


class TestFindBestSolarWindow:
    """Test suite for find_best_solar_window."""
    
    def test_find_best_window_clear_morning_afternoon(self):
        """Test finding best window when morning is better than afternoon."""
        conditions = [
            SolarCondition(
                timestamp="2026-01-18T08:00:00Z",
                latitude=40.0,
                longitude=-88.0,
                cloud_cover_percent=10,
                uv_index=4.0,
                solar_irradiance_watts_m2=700,
                visibility_km=15,
            ),
            SolarCondition(
                timestamp="2026-01-18T09:00:00Z",
                latitude=40.0,
                longitude=-88.0,
                cloud_cover_percent=15,
                uv_index=5.0,
                solar_irradiance_watts_m2=750,
                visibility_km=15,
            ),
            SolarCondition(
                timestamp="2026-01-18T10:00:00Z",
                latitude=40.0,
                longitude=-88.0,
                cloud_cover_percent=20,
                uv_index=6.0,
                solar_irradiance_watts_m2=800,
                visibility_km=15,
            ),
            SolarCondition(
                timestamp="2026-01-18T14:00:00Z",
                latitude=40.0,
                longitude=-88.0,
                cloud_cover_percent=80,
                uv_index=1.0,
                solar_irradiance_watts_m2=100,
                visibility_km=5,
            ),
        ]
        
        result = SolarForecastService.find_best_solar_window(conditions)
        
        assert result is not None
        assert result[0] == "2026-01-18T08:00:00Z"
        assert result[1] == "2026-01-18T10:00:00Z"
    
    def test_find_best_window_all_poor_conditions(self):
        """Test that no window is returned when all conditions are poor."""
        conditions = [
            SolarCondition(
                timestamp="2026-01-18T12:00:00Z",
                latitude=40.0,
                longitude=-88.0,
                cloud_cover_percent=100,
                uv_index=0.5,
                solar_irradiance_watts_m2=20,
                visibility_km=1,
            ),
            SolarCondition(
                timestamp="2026-01-18T13:00:00Z",
                latitude=40.0,
                longitude=-88.0,
                cloud_cover_percent=100,
                uv_index=0.5,
                solar_irradiance_watts_m2=20,
                visibility_km=1,
            ),
            SolarCondition(
                timestamp="2026-01-18T14:00:00Z",
                latitude=40.0,
                longitude=-88.0,
                cloud_cover_percent=100,
                uv_index=0.5,
                solar_irradiance_watts_m2=20,
                visibility_km=1,
            ),
        ]
        
        result = SolarForecastService.find_best_solar_window(conditions)
        
        assert result is None
    
    def test_insufficient_data_raises_error(self):
        """Test that insufficient data raises ValueError."""
        with pytest.raises(ValueError):
            conditions = [
                SolarCondition(
                    timestamp="2026-01-18T12:00:00Z",
                    latitude=40.0,
                    longitude=-88.0,
                    cloud_cover_percent=50,
                    uv_index=5.0,
                    solar_irradiance_watts_m2=500,
                    visibility_km=10,
                ),
            ]
            SolarForecastService.find_best_solar_window(conditions)


class TestGenerateSolarAdvisory:
    """Test suite for generate_solar_advisory."""
    
    ADVISORY_CASES = [
        ("terrible_conditions", 5.0, False, 95, "☁️"),
        ("heavy_cloud_cover", 15.0, False, 90, "☁️"),
        ("poor_conditions", 30.0, False, 70, "🌥️"),
        ("fair_conditions", 55.0, False, 45, "⛅"),
        ("good_conditions", 75.0, False, 20, "🌤️"),
        ("excellent_conditions", 85.0, True, 10, "☀️"),
    ]
    
    @pytest.mark.parametrize(
        "name,potential,is_favorable,cloud_cover,expected_emoji",
        ADVISORY_CASES,
        ids=[c[0] for c in ADVISORY_CASES],
    )
    def test_generate_advisory_content(
        self, name, potential, is_favorable, cloud_cover, expected_emoji
    ):
        """Test advisory generation with various conditions."""
        result = SolarForecastService.generate_solar_advisory(
            potential, is_favorable, cloud_cover
        )
        
        assert expected_emoji in result, (
            f"{name}: Expected emoji '{expected_emoji}' in advisory, "
            f"got: {result}"
        )
        assert isinstance(result, str) and len(result) > 0


class TestForecastForWaypoint:
    """Test suite for forecast_for_waypoint."""
    
    def test_forecast_structure_complete(self):
        """Test that forecast has all required fields."""
        condition = SolarCondition(
            timestamp="2026-01-18T12:00:00Z",
            latitude=40.0,
            longitude=-88.0,
            cloud_cover_percent=30,
            uv_index=6.0,
            solar_irradiance_watts_m2=700,
            visibility_km=12,
        )
        
        result = SolarForecastService.forecast_for_waypoint(condition)
        
        assert isinstance(result, SolarForecast)
        assert result.waypoint_lat == 40.0
        assert result.waypoint_lon == -88.0
        assert result.timestamp == "2026-01-18T12:00:00Z"
        assert 0 <= result.peak_solar_potential <= 100
        assert isinstance(result.advisory, str) and len(result.advisory) > 0
        assert isinstance(result.is_favorable_for_solar, bool)
    
    def test_forecast_consistency(self):
        """Test that same input produces same output (deterministic)."""
        condition = SolarCondition(
            timestamp="2026-01-18T12:00:00Z",
            latitude=40.0,
            longitude=-88.0,
            cloud_cover_percent=50,
            uv_index=5.0,
            solar_irradiance_watts_m2=500,
            visibility_km=10,
        )
        
        result1 = SolarForecastService.forecast_for_waypoint(condition)
        result2 = SolarForecastService.forecast_for_waypoint(condition)
        
        assert result1.peak_solar_potential == result2.peak_solar_potential
        assert result1.advisory == result2.advisory
        assert result1.is_favorable_for_solar == result2.is_favorable_for_solar


class TestForecastForWaypoints:
    """Test suite for forecast_for_waypoints (batch operation)."""
    
    def test_forecast_multiple_waypoints(self):
        """Test forecasting for multiple waypoints."""
        conditions = [
            SolarCondition(
                timestamp="2026-01-18T12:00:00Z",
                latitude=40.0,
                longitude=-88.0,
                cloud_cover_percent=20,
                uv_index=7.0,
                solar_irradiance_watts_m2=800,
                visibility_km=15,
            ),
            SolarCondition(
                timestamp="2026-01-18T13:00:00Z",
                latitude=41.0,
                longitude=-87.0,
                cloud_cover_percent=50,
                uv_index=5.0,
                solar_irradiance_watts_m2=500,
                visibility_km=10,
            ),
            SolarCondition(
                timestamp="2026-01-18T14:00:00Z",
                latitude=42.0,
                longitude=-86.0,
                cloud_cover_percent=80,
                uv_index=2.0,
                solar_irradiance_watts_m2=150,
                visibility_km=5,
            ),
        ]
        
        result = SolarForecastService.forecast_for_waypoints(conditions)
        
        assert len(result) == 3
        assert all(isinstance(f, SolarForecast) for f in result)
        
        # First waypoint should be most favorable
        assert result[0].is_favorable_for_solar
        
        # Last waypoint should be least favorable
        assert not result[2].is_favorable_for_solar
    
    def test_empty_conditions_raises_error(self):
        """Test that empty conditions list raises error."""
        with pytest.raises(ValueError):
            SolarForecastService.forecast_for_waypoints([])


class TestCalculateSunriseSunsetImpact:
    """Test suite for calculate_sunrise_sunset_impact."""
    
    def test_noon_peak_potential(self):
        """Test that solar noon has highest potential."""
        # Noon at equator
        noon_impact = calculate_sunrise_sunset_impact(
            latitude=0.0,
            longitude=0.0,
            timestamp="2026-06-21T12:00:00Z",  # Summer solstice
        )
        
        # Morning
        morning_impact = calculate_sunrise_sunset_impact(
            latitude=0.0,
            longitude=0.0,
            timestamp="2026-06-21T09:00:00Z",
        )
        
        # Evening
        evening_impact = calculate_sunrise_sunset_impact(
            latitude=0.0,
            longitude=0.0,
            timestamp="2026-06-21T15:00:00Z",
        )
        
        assert noon_impact > morning_impact, "Noon should be better than morning"
        assert noon_impact > evening_impact, "Noon should be better than evening"
        assert morning_impact == evening_impact, "Morning and evening at same distance from noon should be equal"
    
    def test_invalid_timestamp_returns_zero(self):
        """Test that invalid timestamp returns 0."""
        result = calculate_sunrise_sunset_impact(
            latitude=40.0,
            longitude=-88.0,
            timestamp="invalid-timestamp",
        )
        
        assert result == 0.0
    
    def test_winter_vs_summer_potential(self):
        """Test that summer has more solar potential than winter."""
        summer_impact = calculate_sunrise_sunset_impact(
            latitude=40.0,
            longitude=-88.0,
            timestamp="2026-06-21T12:00:00Z",  # Summer solstice
        )
        
        winter_impact = calculate_sunrise_sunset_impact(
            latitude=40.0,
            longitude=-88.0,
            timestamp="2026-12-21T12:00:00Z",  # Winter solstice
        )
        
        assert summer_impact > winter_impact
    
    SUNRISE_SUNSET_CASES = [
        (
            "equator_noon_summer",
            0.0,
            0.0,
            "2026-06-21T12:00:00Z",
            0.8,  # Should be high
        ),
        (
            "chicago_noon_summer",
            41.88,
            -87.62,
            "2026-06-21T12:00:00Z",
            0.7,
        ),
        (
            "chicago_midnight",
            41.88,
            -87.62,
            "2026-06-21T00:00:00Z",
            0.0,  # Midnight, no solar potential
        ),
        (
            "equator_early_morning",
            0.0,
            0.0,
            "2026-06-21T06:00:00Z",
            0.3,  # Should be low
        ),
    ]
    
    @pytest.mark.parametrize(
        "name,latitude,longitude,timestamp,expected_min",
        SUNRISE_SUNSET_CASES,
        ids=[c[0] for c in SUNRISE_SUNSET_CASES],
    )
    def test_sunrise_sunset_impact_reasonable(
        self, name, latitude, longitude, timestamp, expected_min
    ):
        """Test that sunrise/sunset impact is within reasonable bounds."""
        result = calculate_sunrise_sunset_impact(latitude, longitude, timestamp)
        
        assert 0.0 <= result <= 1.0, (
            f"{name}: Impact should be 0-1, got {result}"
        )
        assert result >= expected_min, (
            f"{name}: Expected at least {expected_min}, got {result}"
        )


class TestDeterminismAndPurity:
    """Tests ensuring all functions are pure and deterministic."""
    
    def test_same_input_same_output_100_times(self):
        """Test that function is deterministic (100 iterations)."""
        condition = SolarCondition(
            timestamp="2026-01-18T12:00:00Z",
            latitude=40.0,
            longitude=-88.0,
            cloud_cover_percent=50,
            uv_index=5.0,
            solar_irradiance_watts_m2=500,
            visibility_km=10,
        )
        
        results = [
            SolarForecastService.calculate_solar_potential(condition)
            for _ in range(100)
        ]
        
        # All should be identical
        assert len(set(results)) == 1, "All iterations should produce same result"
    
    def test_no_side_effects_on_condition_object(self):
        """Test that calculation doesn't modify input object."""
        condition = SolarCondition(
            timestamp="2026-01-18T12:00:00Z",
            latitude=40.0,
            longitude=-88.0,
            cloud_cover_percent=50,
            uv_index=5.0,
            solar_irradiance_watts_m2=500,
            visibility_km=10,
        )
        
        original_cloud_cover = condition.cloud_cover_percent
        
        SolarForecastService.calculate_solar_potential(condition)
        
        assert condition.cloud_cover_percent == original_cloud_cover


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
