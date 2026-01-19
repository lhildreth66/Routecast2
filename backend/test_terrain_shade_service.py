"""
Tests for Terrain Shade Service

Comprehensive pytest table-driven tests for solar path and shade blocking calculations.
All tests verify pure, deterministic behavior.

Key requirements:
- Shade blocks: canopy + obstruction combinations, clamping behavior
- Sun path: non-empty lists, deterministic values, valid ranges
"""

import pytest
from datetime import date
from terrain_shade_service import TerrainShadeService, SunSlot


class TestShadeBlocks:
    """Test shade factor calculation combining canopy and obstruction."""

    @pytest.mark.parametrize("canopy_pct,obstruction_deg,expected_min,expected_max", [
        # (canopy%, obstruction°, min_factor, max_factor)
        (0, 0, 0.0, 0.05),        # No trees, clear horizon -> minimal shade
        (20, 0, 0.10, 0.15),      # Light canopy, clear horizon
        (50, 0, 0.29, 0.31),      # Medium canopy, clear horizon -> 0.3
        (80, 0, 0.47, 0.49),      # Heavy canopy, clear horizon -> 0.48
        (100, 0, 0.59, 0.61),     # Dense canopy, clear horizon -> 0.6
        (0, 15, 0.06, 0.08),      # No canopy, light obstruction
        (0, 45, 0.19, 0.21),      # No canopy, medium obstruction -> 0.2
        (0, 90, 0.39, 0.41),      # No canopy, full horizon blocked -> 0.4
        (100, 90, 0.99, 1.01),    # Full canopy, full obstruction -> 1.0
    ])
    def test_shade_blocks_in_range(self, canopy_pct, obstruction_deg, expected_min, expected_max):
        """Verify shade blocks returns value in expected range."""
        result = TerrainShadeService.shade_blocks(canopy_pct, obstruction_deg)
        assert expected_min <= result <= expected_max, \
            f"Shade {result} not in {expected_min}-{expected_max}"

    def test_shade_blocks_zero_exposure(self):
        """No trees, clear horizon -> minimal shade (fully exposed)."""
        shade = TerrainShadeService.shade_blocks(0, 0)
        assert shade < 0.1, "Fully exposed site should have minimal shade"

    def test_shade_blocks_heavy_canopy(self):
        """Dense canopy produces strong shade blocking."""
        shade = TerrainShadeService.shade_blocks(80, 0)
        assert 0.45 < shade < 0.50, "Heavy canopy should block ~48%"

    def test_shade_blocks_horizon_obstruction(self):
        """Horizon obstruction produces shade blocking."""
        shade = TerrainShadeService.shade_blocks(0, 45)
        assert 0.19 < shade < 0.21, "45° obstruction should block ~20%"

    def test_shade_blocks_combined_effect(self):
        """Canopy and obstruction combine to block more light."""
        no_obstruction = TerrainShadeService.shade_blocks(50, 0)
        with_obstruction = TerrainShadeService.shade_blocks(50, 30)
        assert with_obstruction > no_obstruction, "Obstruction should increase shade"

    def test_shade_blocks_clamp_canopy_low(self):
        """Negative canopy clamped to 0."""
        result = TerrainShadeService.shade_blocks(-10, 0)
        expected = TerrainShadeService.shade_blocks(0, 0)
        assert result == expected, "Negative canopy should be clamped to 0"

    def test_shade_blocks_clamp_canopy_high(self):
        """Canopy > 100 clamped to 100."""
        result = TerrainShadeService.shade_blocks(150, 0)
        expected = TerrainShadeService.shade_blocks(100, 0)
        assert result == expected, "Canopy > 100 should be clamped to 100"

    def test_shade_blocks_clamp_obstruction_low(self):
        """Negative obstruction clamped to 0."""
        result = TerrainShadeService.shade_blocks(0, -30)
        expected = TerrainShadeService.shade_blocks(0, 0)
        assert result == expected, "Negative obstruction should be clamped to 0"

    def test_shade_blocks_clamp_obstruction_high(self):
        """Obstruction > 90 clamped to 90."""
        result = TerrainShadeService.shade_blocks(0, 120)
        expected = TerrainShadeService.shade_blocks(0, 90)
        assert result == expected, "Obstruction > 90 should be clamped to 90"

    def test_shade_blocks_result_in_range(self):
        """Shade factor always 0.0-1.0 regardless of input."""
        for canopy in [0, 50, 100, -50, 200]:
            for obstruction in [0, 45, 90, -30, 180]:
                result = TerrainShadeService.shade_blocks(canopy, obstruction)
                assert 0.0 <= result <= 1.0, f"Shade {result} out of range"

    def test_shade_blocks_deterministic(self):
        """Same inputs always produce same output."""
        for _ in range(10):
            result1 = TerrainShadeService.shade_blocks(65, 30)
            result2 = TerrainShadeService.shade_blocks(65, 30)
            assert result1 == result2, "Results should be deterministic"


class TestSunPath:
    """Test solar path calculation across daylight hours."""

    @pytest.mark.parametrize("latitude,month,day", [
        (0, 3, 20),      # Equator, spring equinox (Mar 20)
        (40, 6, 21),     # Temperate, summer solstice (Jun 21)
        (-35, 12, 21),   # Southern hemisphere, summer (Dec 21)
        (70, 3, 20),     # Far north, spring (Mar 20)
    ])
    def test_sun_path_non_empty(self, latitude, month, day):
        """Sun path returns non-empty list of slots."""
        observation_date = date(2024, month, day)
        slots = TerrainShadeService.sun_path(latitude, 0, observation_date)
        assert len(slots) > 0, "Sun path should return at least one slot"

    def test_sun_path_hourly_slots(self):
        """Sun path returns hourly slots from 6 AM to 6 PM."""
        slots = TerrainShadeService.sun_path(40, -105, date(2024, 6, 21))
        
        assert len(slots) == 13, "Should have 13 hourly slots (6 AM to 6 PM inclusive)"
        assert slots[0].hour == 6, "First slot at 6 AM"
        assert slots[-1].hour == 18, "Last slot at 6 PM"

    def test_sun_path_elevation_range(self):
        """All sun elevations in valid range (0-90°)."""
        slots = TerrainShadeService.sun_path(40, 0, date(2024, 6, 21))
        
        for slot in slots:
            assert 0 <= slot.sun_elevation_deg <= 90, \
                f"Elevation {slot.sun_elevation_deg}° out of range"

    def test_sun_path_elevation_peaks_at_solar_noon(self):
        """Sun elevation is highest at noon (12 PM)."""
        slots = TerrainShadeService.sun_path(40, 0, date(2024, 6, 21))
        
        elevations = {slot.hour: slot.sun_elevation_deg for slot in slots}
        noon_elevation = elevations[12]
        
        # Noon should be highest
        for hour, elevation in elevations.items():
            if hour != 12:
                assert elevation <= noon_elevation, \
                    f"Elevation at {hour} ({elevation}°) > noon ({noon_elevation}°)"

    def test_sun_path_symmetric_morning_evening(self):
        """Morning and evening elevations are approximately symmetric."""
        slots = TerrainShadeService.sun_path(40, 0, date(2024, 6, 21))
        
        elevations = {slot.hour: slot.sun_elevation_deg for slot in slots}
        
        # 6 AM should match 6 PM, 7 AM should match 5 PM, etc.
        for morning_hour in range(6, 12):
            evening_hour = 24 - morning_hour
            if evening_hour in elevations:
                diff = abs(elevations[morning_hour] - elevations[evening_hour])
                assert diff < 5, f"Morning/evening asymmetry at {morning_hour}°"

    def test_sun_path_winter_lower_than_summer(self):
        """Winter sun elevation lower than summer at same latitude/time."""
        winter_slots = TerrainShadeService.sun_path(40, 0, date(2024, 12, 21))
        summer_slots = TerrainShadeService.sun_path(40, 0, date(2024, 6, 21))
        
        winter_noon = next(s for s in winter_slots if s.hour == 12).sun_elevation_deg
        summer_noon = next(s for s in summer_slots if s.hour == 12).sun_elevation_deg
        
        assert winter_noon < summer_noon, \
            f"Winter noon ({winter_noon}°) should be lower than summer ({summer_noon}°)"

    def test_sun_path_equator_high_elevation(self):
        """Equator has high sun elevation year-round."""
        slots = TerrainShadeService.sun_path(0, 0, date(2024, 6, 21))
        noon_elevation = next(s for s in slots if s.hour == 12).sun_elevation_deg
        
        assert noon_elevation > 60, "Equator should have high sun elevation"

    def test_sun_path_high_latitude_lower_elevation(self):
        """High latitudes have lower sun elevation."""
        equator_slots = TerrainShadeService.sun_path(0, 0, date(2024, 6, 21))
        far_north_slots = TerrainShadeService.sun_path(70, 0, date(2024, 6, 21))
        
        equator_noon = next(s for s in equator_slots if s.hour == 12).sun_elevation_deg
        far_north_noon = next(s for s in far_north_slots if s.hour == 12).sun_elevation_deg
        
        assert far_north_noon < equator_noon, \
            f"Far north ({far_north_noon}°) should be lower than equator ({equator_noon}°)"

    def test_sun_path_usable_fraction_range(self):
        """Usable sunlight fraction in valid range (0-1)."""
        slots = TerrainShadeService.sun_path(40, 0, date(2024, 6, 21))
        
        for slot in slots:
            assert 0.0 <= slot.usable_sunlight_fraction <= 1.0, \
                f"Fraction {slot.usable_sunlight_fraction} out of range"

    def test_sun_path_peak_at_noon(self):
        """Usable sunlight fraction peaks at noon."""
        slots = TerrainShadeService.sun_path(40, 0, date(2024, 6, 21))
        
        fractions = {slot.hour: slot.usable_sunlight_fraction for slot in slots}
        noon_fraction = fractions[12]
        
        for hour, fraction in fractions.items():
            if hour != 12:
                assert fraction <= noon_fraction, \
                    f"Fraction at {hour} ({fraction}) > noon ({noon_fraction})"

    def test_sun_path_time_labels(self):
        """Time labels are properly formatted."""
        slots = TerrainShadeService.sun_path(40, 0, date(2024, 6, 21))
        
        expected_labels = {
            6: "6 AM", 9: "9 AM", 12: "12 PM", 15: "3 PM", 18: "6 PM"
        }
        
        for slot in slots:
            if slot.hour in expected_labels:
                assert expected_labels[slot.hour] in slot.time_label, \
                    f"Wrong label for {slot.hour}: {slot.time_label}"

    def test_sun_path_deterministic(self):
        """Same lat/lon/date always produces same path."""
        paths = [
            TerrainShadeService.sun_path(40, -105, date(2024, 6, 21))
            for _ in range(5)
        ]
        
        # All paths should be identical
        for i in range(1, len(paths)):
            for slot1, slot2 in zip(paths[0], paths[i]):
                assert slot1.hour == slot2.hour
                assert slot1.sun_elevation_deg == slot2.sun_elevation_deg
                assert slot1.usable_sunlight_fraction == slot2.usable_sunlight_fraction

    def test_sun_path_latitude_clamp(self):
        """Invalid latitude clamped to valid range."""
        over_90 = TerrainShadeService.sun_path(95, 0, date(2024, 6, 21))
        at_90 = TerrainShadeService.sun_path(90, 0, date(2024, 6, 21))
        
        # Both should return valid results
        assert len(over_90) > 0
        assert len(at_90) > 0


class TestSunExposureHours:
    """Test effective sunlight hours calculation."""

    def test_sun_exposure_hours_no_shade(self):
        """No shade -> maximum exposure hours."""
        hours = TerrainShadeService.sun_exposure_hours(
            latitude=40,
            longitude=0,
            observation_date=date(2024, 6, 21),
            tree_canopy_pct=0,
            horizon_obstruction_deg=0,
        )
        assert hours > 8, "Summer solstice at 40° should have ~8+ hours sun"

    def test_sun_exposure_hours_full_shade(self):
        """Full shade -> minimal exposure hours."""
        hours = TerrainShadeService.sun_exposure_hours(
            latitude=40,
            longitude=0,
            observation_date=date(2024, 6, 21),
            tree_canopy_pct=100,
            horizon_obstruction_deg=90,
        )
        assert hours < 1, "Full shade should block most light"

    def test_sun_exposure_hours_shade_reduces_hours(self):
        """Adding shade reduces exposure hours."""
        no_shade = TerrainShadeService.sun_exposure_hours(40, 0, date(2024, 6, 21), 0, 0)
        with_shade = TerrainShadeService.sun_exposure_hours(40, 0, date(2024, 6, 21), 50, 30)
        
        assert with_shade < no_shade, "Shade should reduce exposure hours"

    def test_sun_exposure_hours_non_negative(self):
        """Exposure hours never negative."""
        for canopy in [0, 50, 100]:
            for obstruction in [0, 45, 90]:
                hours = TerrainShadeService.sun_exposure_hours(
                    40, 0, date(2024, 6, 21), canopy, obstruction
                )
                assert hours >= 0, f"Hours should never be negative, got {hours}"


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_latitude_at_extremes(self):
        """Extreme latitudes handled correctly."""
        north_pole = TerrainShadeService.sun_path(90, 0, date(2024, 6, 21))
        south_pole = TerrainShadeService.sun_path(-90, 0, date(2024, 12, 21))
        
        assert len(north_pole) > 0
        assert len(south_pole) > 0

    def test_different_months_affect_elevation(self):
        """Different months produce different elevations."""
        jan = TerrainShadeService.sun_path(40, 0, date(2024, 1, 15))
        jul = TerrainShadeService.sun_path(40, 0, date(2024, 7, 15))
        
        jan_noon = next(s for s in jan if s.hour == 12).sun_elevation_deg
        jul_noon = next(s for s in jul if s.hour == 12).sun_elevation_deg
        
        assert jan_noon != jul_noon, "Different months should have different elevations"

    def test_shade_blocks_float_inputs(self):
        """Shade blocks accepts float inputs and converts."""
        result = TerrainShadeService.shade_blocks(50.7, 30.2)
        assert isinstance(result, float)
        assert 0.0 <= result <= 1.0

    def test_sun_path_with_all_longitude_values(self):
        """Sun path works with various longitude values."""
        for lon in [-180, -90, 0, 90, 180]:
            slots = TerrainShadeService.sun_path(40, lon, date(2024, 6, 21))
            assert len(slots) > 0, f"Should work with longitude {lon}"
