"""
Unit Tests for Solar Forecast Service - Energy Generation Estimation

Tests pure deterministic functions for estimating daily solar energy (Wh/day).
Uses pytest + table-driven parametrized test approach.
"""

import pytest
import math
from solar_forecast_service import SolarForecastService, SolarForecastResult


class TestCalculateClearSkyBaseline:
    """Test clear-sky baseline calculation (Wh/day for 1000W panel)."""

    CASES = [
        # (name, lat, doy, expected_min, expected_max)
        ("equinox_equator", 0.0, 81, 4500, 6500),  # Spring equinox at equator
        ("summer_equator", 0.0, 172, 4000, 4500),  # Summer at equator (consistent)
        ("winter_equator", 0.0, 355, 4000, 4500),  # Winter at equator (consistent)
        ("summer_north", 40.0, 172, 5000, 6500),   # Summer in US mid-latitude
        ("winter_north", 40.0, 355, 1500, 2500),   # Winter - sun low, short day
        ("polar_summer", 80.0, 172, 4000, 6000),   # High latitude summer (long day)
        ("polar_winter", 80.0, 355, 0.0, 100.0),   # High latitude winter (no sun)
        ("south_summer", -40.0, 355, 5000, 6500),  # Summer in southern hemisphere (Jan)
        ("equinox_far_north", 70.0, 81, 1500, 2000),  # High latitude, spring equinox
        ("zero_latitude_zero_doy", 0.0, 1, 4000, 4500),  # Edge case: Jan 1 at equator
    ]

    @pytest.mark.parametrize(
        "name,lat,doy,expected_min,expected_max",
        CASES,
        ids=[c[0] for c in CASES],
    )
    def test_clear_sky_baseline_range(self, name, lat, doy, expected_min, expected_max):
        """Test baseline is in expected range for various locations/dates."""
        result = SolarForecastService.calculate_clear_sky_baseline(lat, doy)
        assert expected_min <= result <= expected_max, f"Failed on {name}: got {result}"

    def test_invalid_latitude_too_high(self):
        """Latitude > 90 should raise ValueError."""
        with pytest.raises(ValueError):
            SolarForecastService.calculate_clear_sky_baseline(91.0, 100)

    def test_invalid_latitude_too_low(self):
        """Latitude < -90 should raise ValueError."""
        with pytest.raises(ValueError):
            SolarForecastService.calculate_clear_sky_baseline(-91.0, 100)

    def test_invalid_doy_too_high(self):
        """Day of year > 366 should raise ValueError."""
        with pytest.raises(ValueError):
            SolarForecastService.calculate_clear_sky_baseline(0.0, 367)

    def test_invalid_doy_zero(self):
        """Day of year = 0 should raise ValueError."""
        with pytest.raises(ValueError):
            SolarForecastService.calculate_clear_sky_baseline(0.0, 0)

    def test_determinism_100_iterations(self):
        """Same inputs should produce identical output every time."""
        results = [
            SolarForecastService.calculate_clear_sky_baseline(35.0, 150)
            for _ in range(100)
        ]
        assert len(set(results)) == 1, "Results should be identical"


class TestCalculateCloudMultiplier:
    """Test cloud cover to output multiplier conversion."""

    CASES = [
        # (name, cloud_pct, expected_min, expected_max)
        ("clear", 0.0, 0.99, 1.01),  # Clear = 1.0
        ("partly_cloudy", 50.0, 0.59, 0.61),  # 50% cloud = ~0.6
        ("mostly_cloudy", 80.0, 0.30, 0.40),  # 80% cloud = ~0.2
        ("overcast", 100.0, 0.19, 0.21),  # 100% cloud = 0.2 (minimum)
        ("light_cloud", 10.0, 0.89, 0.95),  # 10% cloud = 0.8
        ("heavy_cloud", 95.0, 0.20, 0.25),  # 95% cloud = ~0.2
    ]

    @pytest.mark.parametrize(
        "name,cloud_pct,expected_min,expected_max",
        CASES,
        ids=[c[0] for c in CASES],
    )
    def test_cloud_multiplier_range(self, name, cloud_pct, expected_min, expected_max):
        """Test multiplier is in expected range."""
        result = SolarForecastService.calculate_cloud_multiplier(cloud_pct)
        assert expected_min <= result <= expected_max, f"Failed on {name}: got {result}"

    def test_invalid_cloud_negative(self):
        """Negative cloud cover should raise ValueError."""
        with pytest.raises(ValueError):
            SolarForecastService.calculate_cloud_multiplier(-5.0)

    def test_invalid_cloud_too_high(self):
        """Cloud cover > 100 should raise ValueError."""
        with pytest.raises(ValueError):
            SolarForecastService.calculate_cloud_multiplier(105.0)

    def test_cloud_range_clamping(self):
        """Multiplier should always be in [0.2, 1.0] range."""
        for cloud_pct in [0, 25, 50, 75, 100]:
            mult = SolarForecastService.calculate_cloud_multiplier(float(cloud_pct))
            assert 0.2 <= mult <= 1.0, f"Out of range at {cloud_pct}%: {mult}"

    def test_determinism_100_iterations(self):
        """Same cloud cover should produce identical multiplier."""
        results = [
            SolarForecastService.calculate_cloud_multiplier(65.0)
            for _ in range(100)
        ]
        assert len(set(results)) == 1, "Results should be identical"


class TestCalculateShadeLoss:
    """Test shade percentage to loss factor conversion."""

    CASES = [
        # (name, shade_pct, expected_min, expected_max)
        ("no_shade", 0.0, 0.99, 1.01),  # 0% shade = 1.0 (no loss)
        ("partial_shade", 25.0, 0.74, 0.76),  # 25% shade = 0.75 usable
        ("half_shade", 50.0, 0.49, 0.51),  # 50% shade = 0.5 usable
        ("mostly_shaded", 75.0, 0.24, 0.26),  # 75% shade = 0.25 usable
        ("full_shade", 100.0, -0.01, 0.01),  # 100% shade = 0.0 (complete loss)
    ]

    @pytest.mark.parametrize(
        "name,shade_pct,expected_min,expected_max",
        CASES,
        ids=[c[0] for c in CASES],
    )
    def test_shade_loss_range(self, name, shade_pct, expected_min, expected_max):
        """Test loss factor is in expected range."""
        result = SolarForecastService.calculate_shade_loss(shade_pct)
        assert expected_min <= result <= expected_max, f"Failed on {name}: got {result}"

    def test_invalid_shade_negative(self):
        """Negative shade should raise ValueError."""
        with pytest.raises(ValueError):
            SolarForecastService.calculate_shade_loss(-10.0)

    def test_invalid_shade_too_high(self):
        """Shade > 100 should raise ValueError."""
        with pytest.raises(ValueError):
            SolarForecastService.calculate_shade_loss(105.0)

    def test_shade_range_clamping(self):
        """Loss factor should always be in [0.0, 1.0] range."""
        for shade_pct in [0, 25, 50, 75, 100]:
            loss = SolarForecastService.calculate_shade_loss(float(shade_pct))
            assert 0.0 <= loss <= 1.0, f"Out of range at {shade_pct}%: {loss}"

    def test_determinism_100_iterations(self):
        """Same shade should produce identical loss factor."""
        results = [
            SolarForecastService.calculate_shade_loss(40.0)
            for _ in range(100)
        ]
        assert len(set(results)) == 1, "Results should be identical"


class TestDateToDayOfYear:
    """Test ISO date to day-of-year conversion."""

    CASES = [
        # (name, date_str, expected_doy)
        ("jan_1", "2026-01-01", 1),
        ("jan_31", "2026-01-31", 31),
        ("feb_1", "2026-02-01", 32),
        ("mar_1_non_leap", "2026-03-01", 60),  # 2026 is not leap year
        ("jun_21_summer", "2026-06-21", 172),
        ("dec_31", "2026-12-31", 365),
        ("leap_year_feb_29", "2024-02-29", 60),  # 2024 is leap year
        ("leap_year_mar_1", "2024-03-01", 61),  # After leap day
    ]

    @pytest.mark.parametrize(
        "name,date_str,expected_doy",
        CASES,
        ids=[c[0] for c in CASES],
    )
    def test_date_to_day_of_year(self, name, date_str, expected_doy):
        """Test date string correctly converts to day of year."""
        result = SolarForecastService.date_to_day_of_year(date_str)
        assert result == expected_doy, f"Failed on {name}: expected {expected_doy}, got {result}"

    def test_invalid_date_format(self):
        """Invalid date format should raise ValueError."""
        with pytest.raises(ValueError):
            SolarForecastService.date_to_day_of_year("2026/01/01")  # Wrong format

    def test_invalid_date_month(self):
        """Invalid month should raise ValueError."""
        with pytest.raises(ValueError):
            SolarForecastService.date_to_day_of_year("2026-13-01")

    def test_invalid_date_day(self):
        """Invalid day should raise ValueError."""
        with pytest.raises(ValueError):
            SolarForecastService.date_to_day_of_year("2026-02-30")


class TestForecastDailyWh:
    """Test end-to-end daily energy generation forecast."""

    def test_basic_sunny_day(self):
        """Basic sunny day forecast for Arizona."""
        result = SolarForecastService.forecast_daily_wh(
            lat=34.05,  # Phoenix
            lon=-111.03,
            date_range=["2026-01-20"],
            panel_watts=400.0,
            shade_pct=0.0,  # No shade
            cloud_cover=[0.0],  # Clear
        )
        
        assert isinstance(result, SolarForecastResult)
        assert len(result.daily_wh) == 1
        assert result.daily_wh[0] > 800.0, "Sunny day should produce significant energy"
        assert result.dates == ["2026-01-20"]
        assert result.panel_watts == 400.0
        assert "clear" in result.advisory.lower() or "good" in result.advisory.lower()

    def test_overcast_day(self):
        """Overcast day should reduce generation."""
        clear_result = SolarForecastService.forecast_daily_wh(
            lat=40.0,
            lon=-88.0,
            date_range=["2026-06-21"],
            panel_watts=500.0,
            shade_pct=0.0,
            cloud_cover=[0.0],
        )
        
        overcast_result = SolarForecastService.forecast_daily_wh(
            lat=40.0,
            lon=-88.0,
            date_range=["2026-06-21"],
            panel_watts=500.0,
            shade_pct=0.0,
            cloud_cover=[100.0],
        )
        
        # Overcast should produce significantly less
        assert overcast_result.daily_wh[0] < clear_result.daily_wh[0] * 0.3

    def test_shade_reduces_output(self):
        """Shade should reduce daily generation."""
        no_shade = SolarForecastService.forecast_daily_wh(
            lat=35.0,
            lon=-118.0,
            date_range=["2026-05-15"],
            panel_watts=300.0,
            shade_pct=0.0,
            cloud_cover=[20.0],
        )
        
        with_shade = SolarForecastService.forecast_daily_wh(
            lat=35.0,
            lon=-118.0,
            date_range=["2026-05-15"],
            panel_watts=300.0,
            shade_pct=50.0,  # 50% shade
            cloud_cover=[20.0],
        )
        
        # Shade should reduce output
        assert with_shade.daily_wh[0] < no_shade.daily_wh[0]
        # Should be roughly half (shade 50%)
        ratio = with_shade.daily_wh[0] / no_shade.daily_wh[0]
        assert 0.4 < ratio < 0.6, f"Shade ratio {ratio} should be ~0.5"

    def test_panel_watts_scales_linearly(self):
        """Double panels should double output."""
        result_400w = SolarForecastService.forecast_daily_wh(
            lat=35.0,
            lon=-118.0,
            date_range=["2026-05-15"],
            panel_watts=400.0,
            shade_pct=10.0,
            cloud_cover=[30.0],
        )
        
        result_800w = SolarForecastService.forecast_daily_wh(
            lat=35.0,
            lon=-118.0,
            date_range=["2026-05-15"],
            panel_watts=800.0,
            shade_pct=10.0,
            cloud_cover=[30.0],
        )
        
        # 800W should be 2x 400W
        ratio = result_800w.daily_wh[0] / result_400w.daily_wh[0]
        assert 1.99 < ratio < 2.01, f"Panel scaling ratio {ratio} should be ~2.0"

    def test_multiple_days(self):
        """Forecast multiple days with varying cloud cover."""
        result = SolarForecastService.forecast_daily_wh(
            lat=40.0,
            lon=-105.0,  # Denver
            date_range=["2026-03-20", "2026-03-21", "2026-03-22"],
            panel_watts=300.0,
            shade_pct=15.0,
            cloud_cover=[10.0, 50.0, 100.0],  # Progressively worse
        )
        
        assert len(result.daily_wh) == 3
        assert len(result.dates) == 3
        
        # Each day worse than previous
        assert result.daily_wh[0] > result.daily_wh[1]
        assert result.daily_wh[1] > result.daily_wh[2]

    def test_winter_vs_summer_same_location(self):
        """Summer should produce more than winter."""
        winter = SolarForecastService.forecast_daily_wh(
            lat=40.0,
            lon=-88.0,
            date_range=["2026-01-20"],  # Winter
            panel_watts=500.0,
            shade_pct=0.0,
            cloud_cover=[20.0],
        )
        
        summer = SolarForecastService.forecast_daily_wh(
            lat=40.0,
            lon=-88.0,
            date_range=["2026-06-20"],  # Summer
            panel_watts=500.0,
            shade_pct=0.0,
            cloud_cover=[20.0],
        )
        
        # Summer should be significantly more
        assert summer.daily_wh[0] > winter.daily_wh[0] * 2.0

    def test_invalid_latitude(self):
        """Latitude out of range should raise ValueError."""
        with pytest.raises(ValueError):
            SolarForecastService.forecast_daily_wh(
                lat=91.0,
                lon=0.0,
                date_range=["2026-05-15"],
                panel_watts=400.0,
                shade_pct=0.0,
                cloud_cover=[50.0],
            )

    def test_invalid_longitude(self):
        """Longitude out of range should raise ValueError."""
        with pytest.raises(ValueError):
            SolarForecastService.forecast_daily_wh(
                lat=0.0,
                lon=-181.0,
                date_range=["2026-05-15"],
                panel_watts=400.0,
                shade_pct=0.0,
                cloud_cover=[50.0],
            )

    def test_invalid_panel_watts(self):
        """Panel watts must be > 0."""
        with pytest.raises(ValueError):
            SolarForecastService.forecast_daily_wh(
                lat=35.0,
                lon=-118.0,
                date_range=["2026-05-15"],
                panel_watts=0.0,  # Invalid
                shade_pct=0.0,
                cloud_cover=[50.0],
            )

    def test_empty_date_range(self):
        """Empty date range should raise ValueError."""
        with pytest.raises(ValueError):
            SolarForecastService.forecast_daily_wh(
                lat=35.0,
                lon=-118.0,
                date_range=[],  # Empty
                panel_watts=400.0,
                shade_pct=0.0,
                cloud_cover=[],
            )

    def test_mismatched_cloud_cover_length(self):
        """Cloud cover array must match date range length."""
        with pytest.raises(ValueError):
            SolarForecastService.forecast_daily_wh(
                lat=35.0,
                lon=-118.0,
                date_range=["2026-05-15", "2026-05-16"],
                panel_watts=400.0,
                shade_pct=0.0,
                cloud_cover=[50.0],  # Only 1 value, need 2
            )

    def test_invalid_cloud_cover_percentage(self):
        """Cloud cover must be 0-100%."""
        with pytest.raises(ValueError):
            SolarForecastService.forecast_daily_wh(
                lat=35.0,
                lon=-118.0,
                date_range=["2026-05-15"],
                panel_watts=400.0,
                shade_pct=0.0,
                cloud_cover=[105.0],  # > 100%
            )

    def test_invalid_shade_percentage(self):
        """Shade must be 0-100%."""
        with pytest.raises(ValueError):
            SolarForecastService.forecast_daily_wh(
                lat=35.0,
                lon=-118.0,
                date_range=["2026-05-15"],
                panel_watts=400.0,
                shade_pct=-5.0,  # Negative
                cloud_cover=[50.0],
            )

    def test_determinism_100_iterations(self):
        """Same inputs should produce identical output."""
        results = []
        for _ in range(100):
            result = SolarForecastService.forecast_daily_wh(
                lat=35.0,
                lon=-118.0,
                date_range=["2026-05-15"],
                panel_watts=350.0,
                shade_pct=25.0,
                cloud_cover=[45.0],
            )
            results.append(result.daily_wh[0])
        
        # All results should be identical
        assert len(set(results)) == 1, "Results should be identical"

    def test_edge_case_full_overcast(self):
        """Full overcast (100% cloud) with heavy shade."""
        result = SolarForecastService.forecast_daily_wh(
            lat=40.0,
            lon=-88.0,
            date_range=["2026-01-15"],  # Winter
            panel_watts=400.0,
            shade_pct=80.0,
            cloud_cover=[100.0],
        )
        
        # Should be non-zero but very low
        assert 0 <= result.daily_wh[0] < 50.0
        assert "heavy cloud" in result.advisory.lower()

    def test_edge_case_perfect_conditions(self):
        """Perfect conditions: summer, clear, no shade."""
        result = SolarForecastService.forecast_daily_wh(
            lat=35.0,
            lon=-118.0,
            date_range=["2026-06-21"],  # Summer solstice
            panel_watts=500.0,
            shade_pct=0.0,
            cloud_cover=[0.0],
        )
        
        # Should be high
        assert result.daily_wh[0] > 2500.0
        assert "clear" in result.advisory.lower() or "excellent" in result.advisory.lower()

    def test_equator_year_round_consistency(self):
        """Equator has consistent sun year-round."""
        from datetime import datetime, timedelta
        results = []
        for doy in [1, 100, 200, 300]:
            base = datetime(2026, 1, 1)
            date = base + timedelta(days=doy-1)
            date_str = date.strftime("%Y-%m-%d")
            
            result = SolarForecastService.forecast_daily_wh(
                lat=0.0,  # Equator
                lon=0.0,
                date_range=[date_str],
                panel_watts=400.0,
                shade_pct=0.0,
                cloud_cover=[0.0],
            )
            results.append(result.daily_wh[0])
        
        # At equator, variance should be relatively small
        avg = sum(results) / len(results)
        for val in results:
            ratio = val / avg
            assert 0.85 < ratio < 1.15, f"Equator variance too high: {ratio}"
