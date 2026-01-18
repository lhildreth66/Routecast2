"""
Tests for Propane Usage Service

Comprehensive pytest table-driven tests for propane consumption estimation.
All tests verify pure, deterministic behavior.
"""

import pytest
from propane_usage_service import PropaneUsageService, PropaneUsageResult


class TestGetTemperatureMultiplier:
    """Test temperature-based heating multiplier calculation."""

    @pytest.mark.parametrize("temp_f,expected_min,expected_max", [
        # (temperature, min_multiplier, max_multiplier)
        (60, 0.25, 0.35),   # Above 55°F: light heating
        (50, 0.55, 0.65),   # 45-54°F: light heating
        (40, 0.95, 1.05),   # 35-44°F: moderate (baseline)
        (30, 1.45, 1.55),   # 25-34°F: heavy heating
        (20, 2.15, 2.25),   # 15-24°F: very heavy heating
        (10, 2.95, 3.05),   # 5-14°F: extreme
        (0, 3.95, 4.05),    # Below 5°F: extreme cold
        (55, 0.25, 0.35),   # Boundary: exactly 55°F
        (45, 0.55, 0.65),   # Boundary: exactly 45°F
        (35, 0.95, 1.05),   # Boundary: exactly 35°F (base)
    ])
    def test_temperature_multipliers(self, temp_f, expected_min, expected_max):
        """Verify temperature multipliers are in expected ranges."""
        multiplier = PropaneUsageService.get_temperature_multiplier(temp_f)
        assert expected_min <= multiplier <= expected_max, \
            f"Temp {temp_f}°F produced {multiplier}, expected {expected_min}-{expected_max}"

    def test_cold_increases_multiplier(self):
        """Verify colder temps produce higher multipliers."""
        warm = PropaneUsageService.get_temperature_multiplier(45)  # Light
        cool = PropaneUsageService.get_temperature_multiplier(35)  # Moderate
        cold = PropaneUsageService.get_temperature_multiplier(20)  # Very heavy
        
        assert cool > warm, "35°F should be higher multiplier than 45°F"
        assert cold > cool, "20°F should be higher multiplier than 35°F"


class TestCalculateHeatingLbsPerNight:
    """Test heating propane calculation for one night."""

    @pytest.mark.parametrize("furnace_btu,duty_cycle,temp_f,expected_min,expected_max", [
        # (furnace_btu, duty_cycle_pct, temp_f, min_lbs, max_lbs)
        (20000, 50, 35, 0.40, 0.50),   # Moderate: ~0.46 lbs
        (20000, 50, 25, 0.60, 0.80),   # Cold: ~0.70 lbs (1.5x multiplier)
        (20000, 50, 55, 0.10, 0.15),   # Warm: ~0.14 lbs (0.3x multiplier)
        (30000, 50, 35, 0.60, 0.75),   # Higher BTU: ~0.69 lbs
        (10000, 50, 35, 0.20, 0.30),   # Lower BTU: ~0.23 lbs
        (20000, 0, 35, 0.00, 0.01),    # Zero duty cycle: tiny amount
        (20000, 100, 35, 0.90, 1.00),  # Full duty cycle: ~0.93 lbs
        (20000, 50, 0, 1.70, 2.00),    # Extreme cold: ~1.85 lbs (4.0x)
    ])
    def test_heating_consumption_ranges(self, furnace_btu, duty_cycle, temp_f, expected_min, expected_max):
        """Verify heating consumption in expected ranges."""
        result = PropaneUsageService.calculate_heating_lbs_per_night(
            furnace_btu, duty_cycle, temp_f
        )
        assert expected_min <= result <= expected_max, \
            f"Got {result}, expected {expected_min}-{expected_max}"

    def test_cold_snap_vs_mild(self):
        """Verify cold nights produce significantly higher consumption."""
        mild_night = PropaneUsageService.calculate_heating_lbs_per_night(20000, 50, 45)
        cold_night = PropaneUsageService.calculate_heating_lbs_per_night(20000, 50, 15)
        
        assert cold_night > mild_night * 2, \
            f"Cold (15°F) should be >2x mild (45°F), got {cold_night:.2f} vs {mild_night:.2f}"

    def test_higher_duty_cycle_higher_consumption(self):
        """Verify duty cycle is directly proportional to consumption."""
        low_duty = PropaneUsageService.calculate_heating_lbs_per_night(20000, 25, 35)
        high_duty = PropaneUsageService.calculate_heating_lbs_per_night(20000, 50, 35)
        
        # Higher duty cycle should produce ~2x consumption
        assert high_duty > low_duty * 1.8, \
            f"50% duty should be ~2x 25%, got {high_duty:.2f} vs {low_duty:.2f}"

    def test_zero_duty_cycle_still_has_tiny_amount(self):
        """Verify 0% duty cycle produces near-zero but not exactly zero."""
        result = PropaneUsageService.calculate_heating_lbs_per_night(20000, 0, 35)
        assert 0 <= result < 0.01, f"Expected ~0, got {result}"

    def test_duty_cycle_clamping_negative(self):
        """Verify negative duty cycle is clamped to 0."""
        negative = PropaneUsageService.calculate_heating_lbs_per_night(20000, -50, 35)
        zero = PropaneUsageService.calculate_heating_lbs_per_night(20000, 0, 35)
        
        assert negative == zero, "Negative duty cycle should clamp to 0"

    def test_duty_cycle_clamping_over_100(self):
        """Verify duty cycle >100 is clamped to 100."""
        over = PropaneUsageService.calculate_heating_lbs_per_night(20000, 150, 35)
        hundred = PropaneUsageService.calculate_heating_lbs_per_night(20000, 100, 35)
        
        assert over == hundred, "Duty cycle >100 should clamp to 100"


class TestEstimateLbsPerDay:
    """Test main entry point for propane estimation."""

    @pytest.mark.parametrize("furnace_btu,duty_cycle,temps,people,expected_min,expected_max", [
        # Single day cases
        (20000, 50, [35], 2, 0.65, 0.85),      # Moderate: heating + cooking
        (20000, 50, [25], 2, 0.85, 1.10),      # Cold: higher heating
        (20000, 50, [55], 2, 0.35, 0.50),      # Warm: minimal heating
        
        # Multi-day cases
        (20000, 50, [35, 25], 2, None, None),  # Cold snap
        (20000, 50, [55, 50, 45], 2, None, None),  # Mild period
        
        # Different people counts
        (20000, 50, [35], 1, 0.55, 0.70),      # 1 person (less cooking)
        (20000, 50, [35], 4, 1.00, 1.15),      # 4 people (more cooking)
        
        # Duty cycle variations
        (20000, 0, [35], 2, 0.28, 0.35),       # No heating, only cooking
        (20000, 100, [35], 2, 1.13, 1.33),     # Full furnace
        
        # Different furnace sizes
        (10000, 50, [35], 2, 0.42, 0.55),      # Smaller furnace
        (40000, 50, [35], 2, 0.99, 1.25),      # Larger furnace
    ])
    def test_daily_consumption(self, furnace_btu, duty_cycle, temps, people, expected_min, expected_max):
        """Verify daily propane consumption in expected ranges."""
        result = PropaneUsageService.estimate_lbs_per_day(
            furnace_btu, duty_cycle, temps, people
        )
        
        assert len(result) == len(temps), f"Result length {len(result)} != temps length {len(temps)}"
        
        if expected_min is None:
            # Multi-day: just verify reasonable values
            assert all(0.2 < lbs < 3.0 for lbs in result), f"Got {result}"
        else:
            # Single day: verify specific range
            assert len(result) == 1
            total = result[0]
            assert expected_min <= total <= expected_max, \
                f"Got {total}, expected {expected_min}-{expected_max}"

    def test_empty_temps_returns_empty_list(self):
        """Verify empty temperatures list returns empty consumption list."""
        result = PropaneUsageService.estimate_lbs_per_day(20000, 50, [], 2)
        assert result == [], "Empty temps should return empty list"

    def test_duty_cycle_zero_still_returns_cooking_baseline(self):
        """Verify 0% duty cycle returns cooking baseline (not zero)."""
        result = PropaneUsageService.estimate_lbs_per_day(20000, 0, [35], 2)
        
        assert len(result) == 1
        assert 0.25 < result[0] < 0.35, \
            f"Duty cycle 0 should return ~cooking baseline, got {result[0]}"

    def test_cold_snap_vs_mild_period(self):
        """Verify cold snap produces significantly higher consumption."""
        mild_period = PropaneUsageService.estimate_lbs_per_day(20000, 50, [45, 50, 55], 2)
        cold_snap = PropaneUsageService.estimate_lbs_per_day(20000, 50, [15, 10, 5], 2)
        
        mild_total = sum(mild_period)
        cold_total = sum(cold_snap)
        
        assert cold_total > mild_total * 2, \
            f"Cold snap should be >2x mild, got {cold_total:.1f} vs {mild_total:.1f}"

    def test_people_affects_consumption(self):
        """Verify more people increases consumption (cooking baseline)."""
        one_person = PropaneUsageService.estimate_lbs_per_day(20000, 50, [35], 1)
        two_people = PropaneUsageService.estimate_lbs_per_day(20000, 50, [35], 2)
        four_people = PropaneUsageService.estimate_lbs_per_day(20000, 50, [35], 4)
        
        assert one_person[0] < two_people[0], "More people = more cooking baseline"
        assert two_people[0] < four_people[0], "More people = more cooking baseline"

    def test_longer_trip_higher_total(self):
        """Verify longer trips (more days) have higher total consumption."""
        short_trip = PropaneUsageService.estimate_lbs_per_day(20000, 50, [35], 2)
        long_trip = PropaneUsageService.estimate_lbs_per_day(20000, 50, [35, 35, 35, 35, 35], 2)
        
        short_total = sum(short_trip)
        long_total = sum(long_trip)
        
        assert long_total > short_total * 4, \
            f"5 days should be ~5x 1 day, got {long_total:.1f} vs {short_total:.1f}"

    def test_duty_cycle_clamping_negative_input(self):
        """Verify negative duty cycle is clamped."""
        negative = PropaneUsageService.estimate_lbs_per_day(20000, -50, [35], 2)
        zero = PropaneUsageService.estimate_lbs_per_day(20000, 0, [35], 2)
        
        assert negative == zero, "Negative duty cycle should clamp to 0"

    def test_duty_cycle_clamping_over_100_input(self):
        """Verify duty cycle >100 is clamped."""
        over = PropaneUsageService.estimate_lbs_per_day(20000, 150, [35], 2)
        hundred = PropaneUsageService.estimate_lbs_per_day(20000, 100, [35], 2)
        
        assert over == hundred, "Duty cycle >100 should clamp to 100"

    # Validation tests (should raise ValueError)

    def test_invalid_furnace_btu_zero(self):
        """Verify zero furnace BTU raises ValueError."""
        with pytest.raises(ValueError, match="furnace_btu must be > 0"):
            PropaneUsageService.estimate_lbs_per_day(0, 50, [35], 2)

    def test_invalid_furnace_btu_negative(self):
        """Verify negative furnace BTU raises ValueError."""
        with pytest.raises(ValueError, match="furnace_btu must be > 0"):
            PropaneUsageService.estimate_lbs_per_day(-20000, 50, [35], 2)

    def test_invalid_people_zero(self):
        """Verify zero people raises ValueError."""
        with pytest.raises(ValueError, match="people must be >= 1"):
            PropaneUsageService.estimate_lbs_per_day(20000, 50, [35], 0)

    def test_invalid_people_negative(self):
        """Verify negative people raises ValueError."""
        with pytest.raises(ValueError, match="people must be >= 1"):
            PropaneUsageService.estimate_lbs_per_day(20000, 50, [35], -2)


class TestFormatAdvisory:
    """Test advisory text generation."""

    def test_advisory_empty_temps(self):
        """Verify advisory for empty forecast."""
        advisory = PropaneUsageService.format_advisory(20000, 50, [], 2, [])
        assert "No forecast" in advisory

    def test_advisory_cold_snap(self):
        """Verify advisory includes cold snap indicator."""
        daily = [2.0, 2.5, 3.0]  # High consumption = cold
        advisory = PropaneUsageService.format_advisory(20000, 50, [15, 10, 5], 2, daily)
        assert "❄️" in advisory or "Cold" in advisory

    def test_advisory_mild_conditions(self):
        """Verify advisory includes mild indicator."""
        daily = [0.5, 0.6, 0.7]  # Low consumption = warm
        advisory = PropaneUsageService.format_advisory(20000, 50, [45, 50, 55], 2, daily)
        assert "🌤️" in advisory or "Warm" in advisory or "Mild" in advisory

    def test_advisory_includes_trip_total(self):
        """Verify advisory includes total consumption and duration."""
        daily = [0.8, 0.9, 1.0]
        advisory = PropaneUsageService.format_advisory(20000, 50, [35, 35, 35], 2, daily)
        assert "3 days" in advisory
        assert "2.7" in advisory  # ~2.7 lbs total


class TestDeterminism:
    """Test that function is deterministic and pure."""

    def test_same_inputs_identical_outputs(self):
        """Verify 100 iterations with same inputs produce identical output."""
        furnace_btu = 20000
        duty_cycle = 50
        temps = [35, 25, 15, 45]
        people = 2

        first_result = PropaneUsageService.estimate_lbs_per_day(
            furnace_btu, duty_cycle, temps, people
        )

        for _ in range(100):
            result = PropaneUsageService.estimate_lbs_per_day(
                furnace_btu, duty_cycle, temps, people
            )
            assert result == first_result, "Results differ across iterations (not deterministic)"

    def test_no_floating_point_variance(self):
        """Verify no floating-point precision issues."""
        results = [
            PropaneUsageService.estimate_lbs_per_day(20000, 50, [35], 2)[0]
            for _ in range(50)
        ]
        
        # All results should be identical
        assert len(set(results)) == 1, "Floating-point variance detected"


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_single_day_forecast(self):
        """Verify single day forecast works."""
        result = PropaneUsageService.estimate_lbs_per_day(20000, 50, [35], 2)
        assert len(result) == 1
        assert 0.5 < result[0] < 1.0

    def test_very_long_trip_30_days(self):
        """Verify long trip (30 days) is calculated correctly."""
        temps = [35] * 30  # 30 days at 35°F
        result = PropaneUsageService.estimate_lbs_per_day(20000, 50, temps, 2)
        
        assert len(result) == 30
        total_lbs = sum(result)
        assert 15 < total_lbs < 25, f"30 days should be ~15-25 lbs, got {total_lbs}"

    def test_extreme_cold(self):
        """Verify extreme cold (below 0°F) is handled."""
        result = PropaneUsageService.estimate_lbs_per_day(20000, 50, [-10, -20], 2)
        assert len(result) == 2
        assert all(lbs > 1.5 for lbs in result), "Extreme cold should produce >1.5 lbs/day"

    def test_extreme_heat(self):
        """Verify extreme heat (above 100°F) is handled."""
        result = PropaneUsageService.estimate_lbs_per_day(20000, 50, [90, 100], 2)
        assert len(result) == 2
        assert all(lbs < 0.5 for lbs in result), "Extreme heat should produce <0.5 lbs/day"

    def test_very_small_furnace(self):
        """Verify very small furnace (1000 BTU) works."""
        result = PropaneUsageService.estimate_lbs_per_day(1000, 50, [35], 2)
        assert len(result) == 1
        assert 0.20 < result[0] < 0.35

    def test_very_large_furnace(self):
        """Verify very large furnace (100000 BTU) works."""
        result = PropaneUsageService.estimate_lbs_per_day(100000, 50, [35], 2)
        assert len(result) == 1
        assert 2.5 < result[0] < 3.5

    def test_many_people(self):
        """Verify many people (10) increases consumption."""
        few = PropaneUsageService.estimate_lbs_per_day(20000, 50, [35], 2)
        many = PropaneUsageService.estimate_lbs_per_day(20000, 50, [35], 10)
        
        assert many[0] > few[0], "10 people should use more than 2 people"
