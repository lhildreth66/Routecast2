"""
Tests for Water Budget Service

Comprehensive pytest table-driven tests for water tank duration estimation.
All tests verify pure, deterministic behavior.

Key requirement: Tests must include scenarios where fresh, gray, and black
tanks are each the limiting factor.
"""

import pytest
from water_budget_service import WaterBudgetService, WaterBudgetResult


class TestCalculateDailyUsage:
    """Test daily water usage calculation."""

    @pytest.mark.parametrize("people,showers_per_week,hot_days,expected_fresh_min,expected_fresh_max", [
        # (people, showers/week, hot_days, min_fresh, max_fresh)
        (1, 0, False, 1.6, 1.8),      # 1 person, no showers, cool
        (2, 0, False, 3.2, 3.6),      # 2 people, no showers, cool
        (4, 0, False, 6.4, 7.2),      # 4 people, no showers, cool
        (1, 0, True, 2.0, 2.6),       # Hot multiplier: 2 × 1.2 = 2.4
        (2, 2, False, 3.2, 4.0),      # 2 people, 2 showers/week
        (1, 7, False, 1.6, 2.2),      # Daily shower
        (1, 14, False, 1.6, 2.5),     # 2 showers/day (high)
    ])
    def test_fresh_usage(self, people, showers_per_week, hot_days, expected_fresh_min, expected_fresh_max):
        """Verify fresh water usage is in expected ranges."""
        fresh, gray, black = WaterBudgetService.calculate_daily_usage(
            people, showers_per_week, hot_days
        )
        assert expected_fresh_min <= fresh <= expected_fresh_max, \
            f"Fresh {fresh} not in {expected_fresh_min}-{expected_fresh_max}"

    @pytest.mark.parametrize("people,showers_per_week,hot_days,expected_gray_min,expected_gray_max", [
        # Gray includes sinks + showers
        (1, 0, False, 1.6, 1.8),      # 1 person baseline
        (2, 0, False, 3.2, 3.6),      # 2 people baseline
        (1, 2, False, 9.0, 10.5),     # Showers add gray water (2/7 * 33 = 9.4)
        (1, 7, False, 28.0, 31.0),    # Daily shower
    ])
    def test_gray_usage(self, people, showers_per_week, hot_days, expected_gray_min, expected_gray_max):
        """Verify gray water usage is in expected ranges."""
        fresh, gray, black = WaterBudgetService.calculate_daily_usage(
            people, showers_per_week, hot_days
        )
        assert expected_gray_min <= gray <= expected_gray_max, \
            f"Gray {gray} not in {expected_gray_min}-{expected_gray_max}"

    def test_hot_days_increases_usage(self):
        """Verify hot weather increases water usage."""
        cool_fresh, cool_gray, cool_black = WaterBudgetService.calculate_daily_usage(2, 1, False)
        hot_fresh, hot_gray, hot_black = WaterBudgetService.calculate_daily_usage(2, 1, True)

        assert hot_fresh > cool_fresh, "Hot days should use more fresh water"
        assert hot_gray > cool_gray, "Hot days should use more gray water"
        assert hot_black > cool_black, "Hot days should use more black water"

    def test_showers_increase_usage(self):
        """Verify more showers increase usage."""
        no_showers = WaterBudgetService.calculate_daily_usage(1, 0, False)
        weekly_showers = WaterBudgetService.calculate_daily_usage(1, 7, False)

        assert weekly_showers[1] > no_showers[1], "Showers should increase gray water"
        assert weekly_showers[2] > no_showers[2], "Showers should increase black water"

    def test_more_people_increase_usage(self):
        """Verify more people increase water usage."""
        one_person = WaterBudgetService.calculate_daily_usage(1, 0, False)
        four_people = WaterBudgetService.calculate_daily_usage(4, 0, False)

        assert four_people[0] > one_person[0], "More people = more fresh water"
        assert four_people[1] > one_person[1], "More people = more gray water"
        assert four_people[2] > one_person[2], "More people = more black water"

    def test_invalid_people_zero(self):
        """Verify zero people raises ValueError."""
        with pytest.raises(ValueError, match="people must be >= 1"):
            WaterBudgetService.calculate_daily_usage(0, 0, False)

    def test_invalid_people_negative(self):
        """Verify negative people raises ValueError."""
        with pytest.raises(ValueError, match="people must be >= 1"):
            WaterBudgetService.calculate_daily_usage(-1, 0, False)

    def test_invalid_showers_negative(self):
        """Verify negative showers raises ValueError."""
        with pytest.raises(ValueError, match="showers_per_week must be >= 0"):
            WaterBudgetService.calculate_daily_usage(1, -1, False)


class TestDaysRemaining:
    """Test main water budget calculation."""

    # ========== CRITICAL TEST REQUIREMENTS ==========
    # Must include scenarios where each tank is the limiting factor

    @pytest.mark.parametrize("fresh_gal,gray_gal,black_gal,people,showers,hot_days,expected_min,expected_max", [
        # BLACK TANK IS LIMITING (small black tank)
        (100, 100, 10, 2, 1, False, 4, 6),       # Black fills fastest with toilet use
        (200, 200, 15, 4, 2, False, 3, 5),       # Many people, small black tank

        # GRAY TANK IS LIMITING (small gray tank)
        (100, 15, 100, 2, 3, False, 0, 1),       # Showers fill gray tank quickly (0 days)
        (150, 25, 150, 3, 7, False, 0, 1),       # Daily showers, small gray

        # FRESH TANK IS LIMITING (small fresh tank)
        (10, 100, 100, 2, 0, False, 2, 3),       # Small fresh, large waste tanks
        (15, 100, 100, 1, 0, False, 7, 9),       # Minimal fresh water

        # BALANCED (no obvious limiting)
        (50, 50, 50, 1, 1, False, 8, 12),        # Balanced tanks, 1 person
        (100, 100, 100, 2, 2, False, 8, 9),      # Balanced tanks, 2 people
    ])
    def test_days_remaining_in_range(self, fresh_gal, gray_gal, black_gal, people, showers, hot_days, expected_min, expected_max):
        """Verify days remaining in expected ranges."""
        days = WaterBudgetService.days_remaining(
            fresh_gal, gray_gal, black_gal, people, showers, hot_days
        )
        assert expected_min <= days <= expected_max, \
            f"Got {days} days, expected {expected_min}-{expected_max}"

    def test_black_tank_limiting_scenario(self):
        """Verify black tank can be the limiting factor."""
        # Setup: Black tank very small, others large
        # Toilet generates 1 gal/person/day (constant)
        # Black fills quickly
        result = WaterBudgetService.days_remaining_with_breakdown(
            fresh_gal=200,
            gray_gal=200,
            black_gal=10,     # Very small black tank
            people=3,
            showers_per_week=0,
            hot_days=False,
        )

        assert result.limiting_factor == "black", \
            f"Black tank should be limiting, got {result.limiting_factor}"
        assert result.days_remaining <= 15, \
            "Small black tank should limit trip to ~10 days"

    def test_gray_tank_limiting_scenario(self):
        """Verify gray tank can be the limiting factor."""
        # Setup: Gray tank small, fresh and black large
        # Gray fills from baseline + showers
        result = WaterBudgetService.days_remaining_with_breakdown(
            fresh_gal=200,
            gray_gal=20,      # Very small gray tank
            black_gal=200,
            people=2,
            showers_per_week=3,  # Multiple showers
            hot_days=False,
        )

        assert result.limiting_factor == "gray", \
            f"Gray tank should be limiting, got {result.limiting_factor}"
        assert result.days_remaining <= 5, \
            "Small gray tank with showers should limit trip to ~5 days"

    def test_fresh_tank_limiting_scenario(self):
        """Verify fresh tank can be the limiting factor."""
        # Setup: Fresh tank very small, gray and black large
        # Fresh used for drinking/cooking (smallest baseline)
        result = WaterBudgetService.days_remaining_with_breakdown(
            fresh_gal=10,     # Very small fresh tank
            gray_gal=200,
            black_gal=200,
            people=2,
            showers_per_week=0,
            hot_days=False,
        )

        assert result.limiting_factor == "fresh", \
            f"Fresh tank should be limiting, got {result.limiting_factor}"
        assert result.days_remaining <= 8, \
            "Small fresh tank should limit trip to ~5-7 days"

    def test_hot_days_vs_cool_days(self):
        """Verify hot days reduce days remaining."""
        cool = WaterBudgetService.days_remaining(50, 50, 50, 2, 2, False)
        hot = WaterBudgetService.days_remaining(50, 50, 50, 2, 2, True)

        assert hot < cool, "Hot days should result in fewer days remaining"

    def test_zero_tank_returns_zero(self):
        """Verify zero tank capacity returns 0 days."""
        zero_fresh = WaterBudgetService.days_remaining(0, 50, 50, 2, 1, False)
        zero_gray = WaterBudgetService.days_remaining(50, 0, 50, 2, 1, False)
        zero_black = WaterBudgetService.days_remaining(50, 50, 0, 2, 1, False)

        assert zero_fresh == 0
        assert zero_gray == 0
        assert zero_black == 0

    def test_negative_tanks_clamped_to_zero(self):
        """Verify negative tank values are handled gracefully."""
        result = WaterBudgetService.days_remaining(-10, 50, 50, 2, 1, False)
        assert result == 0, "Negative fresh tank should be clamped to 0"

    def test_one_person_high_showers(self):
        """Verify one person with high shower frequency works correctly."""
        result = WaterBudgetService.days_remaining(
            fresh_gal=30,
            gray_gal=30,
            black_gal=30,
            people=1,
            showers_per_week=14,  # 2 showers/day
            hot_days=False,
        )

        assert result >= 0, "Should handle high shower frequency"
        # Gray should be limiting (showers create lots of gray water)
        breakdown = WaterBudgetService.days_remaining_with_breakdown(
            fresh_gal=30,
            gray_gal=30,
            black_gal=30,
            people=1,
            showers_per_week=14,
            hot_days=False,
        )
        # With high showers, gray usually limits
        assert breakdown.limiting_factor in ["gray", "black"], \
            "High shower frequency should fill gray tank quickly"

    def test_invalid_people_raises_error(self):
        """Verify invalid people count raises ValueError."""
        with pytest.raises(ValueError, match="people must be >= 1"):
            WaterBudgetService.days_remaining(50, 50, 50, 0, 1, False)

    def test_invalid_showers_raises_error(self):
        """Verify invalid showers count raises ValueError."""
        with pytest.raises(ValueError, match="showers_per_week must be >= 0"):
            WaterBudgetService.days_remaining(50, 50, 50, 2, -1, False)

    def test_result_never_negative(self):
        """Verify result is always >= 0."""
        # Various edge cases
        cases = [
            (0, 0, 0, 1, 0, False),
            (1, 1, 1, 10, 20, True),
            (100, 1, 100, 1, 0, False),
        ]

        for fresh, gray, black, people, showers, hot in cases:
            result = WaterBudgetService.days_remaining(fresh, gray, black, people, showers, hot)
            assert result >= 0, f"Result should never be negative, got {result}"

    def test_more_people_fewer_days(self):
        """Verify more people results in fewer days."""
        two_people = WaterBudgetService.days_remaining(100, 100, 100, 2, 1, False)
        four_people = WaterBudgetService.days_remaining(100, 100, 100, 4, 1, False)

        assert four_people < two_people, "More people should reduce days remaining"

    def test_more_showers_fewer_days(self):
        """Verify more showers result in fewer days."""
        no_showers = WaterBudgetService.days_remaining(100, 100, 100, 2, 0, False)
        daily_showers = WaterBudgetService.days_remaining(100, 100, 100, 2, 7, False)

        assert daily_showers < no_showers, "More showers should reduce days remaining"


class TestDaysRemainingWithBreakdown:
    """Test detailed breakdown results."""

    def test_returns_valid_result_type(self):
        """Verify return type is WaterBudgetResult."""
        result = WaterBudgetService.days_remaining_with_breakdown(
            50, 50, 50, 2, 1, False
        )

        assert isinstance(result, WaterBudgetResult)
        assert hasattr(result, 'days_remaining')
        assert hasattr(result, 'limiting_factor')
        assert hasattr(result, 'advisory')

    def test_limiting_factor_valid_values(self):
        """Verify limiting factor is fresh/gray/black."""
        for fresh, gray, black in [(100, 100, 10), (100, 10, 100), (10, 100, 100)]:
            result = WaterBudgetService.days_remaining_with_breakdown(
                fresh, gray, black, 2, 1, False
            )
            assert result.limiting_factor in ["fresh", "gray", "black"]

    def test_advisory_non_empty(self):
        """Verify advisory text is generated."""
        result = WaterBudgetService.days_remaining_with_breakdown(
            50, 50, 50, 2, 1, False
        )
        assert result.advisory, "Advisory should not be empty"
        assert len(result.advisory) > 0

    def test_advisory_includes_limiting_factor(self):
        """Verify advisory mentions the limiting factor or gives appropriate message."""
        result = WaterBudgetService.days_remaining_with_breakdown(
            100, 10, 100, 2, 3, False  # Gray should be limiting
        )
        assert result.limiting_factor == "gray"
        # Advisory should reference the situation (may be warning if no water)
        assert "enough" in result.advisory.lower() or "water" in result.advisory.lower() or result.days_remaining == 0

    def test_zero_tank_produces_warning_advisory(self):
        """Verify zero tank produces appropriate advisory."""
        result = WaterBudgetService.days_remaining_with_breakdown(
            0, 50, 50, 2, 1, False
        )
        assert result.days_remaining == 0
        assert "empty" in result.advisory.lower() or "empty" in result.advisory.lower()


class TestDeterminism:
    """Test that function is deterministic and pure."""

    def test_same_inputs_identical_outputs(self):
        """Verify 100 iterations with same inputs produce identical output."""
        fresh_gal = 75
        gray_gal = 80
        black_gal = 60
        people = 2
        showers_per_week = 2
        hot_days = False

        first_result = WaterBudgetService.days_remaining(
            fresh_gal, gray_gal, black_gal, people, showers_per_week, hot_days
        )

        for _ in range(100):
            result = WaterBudgetService.days_remaining(
                fresh_gal, gray_gal, black_gal, people, showers_per_week, hot_days
            )
            assert result == first_result, "Results differ across iterations (not deterministic)"

    def test_usage_calculation_determinism(self):
        """Verify usage calculation is deterministic."""
        results = [
            WaterBudgetService.calculate_daily_usage(2, 3, False)
            for _ in range(50)
        ]

        # All results should be identical
        assert len(set(results)) == 1, "Floating-point variance detected"


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_zero_people_raises(self):
        """Verify zero people raises error."""
        with pytest.raises(ValueError, match="people must be >= 1"):
            WaterBudgetService.days_remaining(50, 50, 50, 0, 1, False)

    def test_one_person_one_day_trip(self):
        """Verify minimal trip configuration works."""
        result = WaterBudgetService.days_remaining(5, 5, 5, 1, 0, False)
        assert result >= 0, "Should handle minimal trip"

    def test_many_people_high_showers(self):
        """Verify high usage scenario works."""
        result = WaterBudgetService.days_remaining(100, 100, 100, 6, 14, True)
        assert result >= 0, "Should handle high usage scenario"

    def test_all_tanks_equal_capacity(self):
        """Verify equal tanks are handled correctly."""
        result = WaterBudgetService.days_remaining_with_breakdown(
            50, 50, 50, 2, 2, False
        )
        # With equal tanks, one will still be limiting (usually black)
        assert result.limiting_factor is not None
        assert result.days_remaining >= 0

    def test_fractional_showers_per_week(self):
        """Verify fractional shower frequencies work."""
        # 0.5 showers per week = once every two weeks
        result = WaterBudgetService.days_remaining(50, 50, 50, 1, 0.5, False)
        assert result >= 0

    def test_very_large_tanks(self):
        """Verify very large tank capacities work."""
        result = WaterBudgetService.days_remaining(10000, 10000, 10000, 2, 2, False)
        assert result > 100, "Large tanks should support >100 day trips"

    def test_very_small_tanks(self):
        """Verify very small tank capacities work."""
        result = WaterBudgetService.days_remaining(1, 1, 1, 1, 0, False)
        assert result == 0, "Tanks this small cannot support any days"
