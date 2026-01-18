"""
Water Budget Service - Pure Deterministic Water Tank Duration Estimation

This module provides pure, side-effect-free functions for estimating how many days
an RV's fresh, gray, and black water tanks will sustain a boondocking trip.

Following gold-standard principles:
- Pure functions with no side effects
- No external API calls
- Clear input/output contracts
- Comprehensive error handling
- Fully deterministic and testable

Water Physics:
- Fresh tank: drinking, cooking, washing
- Gray tank: sink, shower, washing machine
- Black tank: toilet only (conservative, realistic)
- Gray fills faster than black normally
- One tank running out limits trip duration
"""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class WaterBudgetResult:
    """Immutable result from water budget calculation."""
    days_remaining: int
    limiting_factor: Literal["fresh", "gray", "black"]
    fresh_days: float
    gray_days: float
    black_days: float
    daily_fresh_gal: float
    daily_gray_gal: float
    daily_black_gal: float
    advisory: str


class WaterBudgetService:
    """
    Pure deterministic water budget estimation service.
    
    Calculates how many days an RV's water tanks will support a boondocking trip
    based on:
    - Tank capacities (fresh, gray, black in gallons)
    - Number of people
    - Shower frequency
    - Temperature conditions (affects water usage)
    
    All methods are pure functions - same inputs always produce same outputs.
    No I/O, no external calls, no mutable state.
    
    Water Usage Assumptions:
    ========================
    
    BASELINE (per person per day, no showers):
    - Drinking & cooking: 2 gallons (fresh only)
    - Sink hygiene: 2 gallons (gray - hand wash, brushing teeth, etc.)
    - Toilet: 1 gallon (black - assuming low-flow RV toilet at 1 gal/flush × 1 flush/person/day)
    - TOTAL BASELINE: 2 fresh, 2 gray, 1 black = 5 gallons waste/person/day
    
    SHOWERS:
    - Average shower: 35 gallons
    - Distribution: 33 gal gray (shower drain), 2 gal black (hand wash after toilet)
    - Frequency: converted to per-day average (showers_per_week / 7)
    - Example: 2 showers/week = 0.286 showers/day = 10 gal/day waste
    
    TEMPERATURE MULTIPLIER (affects all usage):
    - Hot days (>80°F): 1.2× multiplier
      * Extra showers for cooling
      * More drinking water
      * More frequent hand washing
    - Normal/cool days: 0.85× multiplier
      * Less frequent showers
      * Less drinking (no cooling need)
      * Less water use overall
    
    TANK FILLING RATES:
    - Fresh: consumed directly, refills from external water
    - Gray: fills from showers/sinks, drains at slower rate in RVs
    - Black: fills from toilet only, drains at same rate as gray
    - One tank hitting 0 ends the trip (no overflow between tanks)
    """

    # ==================== Water Usage Constants ====================

    # Baseline per-person usage (gallons/day), no showers
    # Based on EPA water usage guidelines adapted for RV usage
    BASELINE_FRESH_GPD = 2.0      # Drinking, cooking (fresh only)
    BASELINE_GRAY_GPD = 2.0       # Sink, hand washing, hygiene (gray)
    BASELINE_BLACK_GPD = 1.0      # Toilet only (1 flush/person/day conservative)

    # Shower usage
    GALLONS_PER_SHOWER = 35.0     # Standard shower duration and RV showerhead
    SHOWER_GRAY_FRACTION = 33/35  # ~94% goes to gray, ~6% to black (hand wash)
    SHOWER_BLACK_FRACTION = 2/35

    # Temperature adjustment multipliers
    MULTIPLIER_HOT_DAYS = 1.2     # Hot weather increases water usage
    MULTIPLIER_NORMAL_DAYS = 0.85 # Cool weather decreases water usage

    @staticmethod
    def calculate_daily_usage(
        people: int,
        showers_per_week: float,
        hot_days: bool,
    ) -> tuple[float, float, float]:
        """
        Calculate daily water usage by tank type.

        Args:
            people: Number of people in RV (must be >= 1)
            showers_per_week: Weekly shower frequency (e.g., 2 = 2 showers/week)
            hot_days: True if temperature conditions favor high usage

        Returns:
            Tuple of (fresh_gal/day, gray_gal/day, black_gal/day)

        Raises:
            ValueError: If people < 1 or showers_per_week < 0
        """
        if people < 1:
            raise ValueError(f"people must be >= 1, got {people}")
        if showers_per_week < 0:
            raise ValueError(f"showers_per_week must be >= 0, got {showers_per_week}")

        # Baseline usage per person per day
        baseline_fresh = WaterBudgetService.BASELINE_FRESH_GPD * people
        baseline_gray = WaterBudgetService.BASELINE_GRAY_GPD * people
        baseline_black = WaterBudgetService.BASELINE_BLACK_GPD * people

        # Shower usage (convert weekly to daily average)
        showers_per_day = showers_per_week / 7.0
        shower_total_gal = showers_per_day * WaterBudgetService.GALLONS_PER_SHOWER
        shower_gray = shower_total_gal * WaterBudgetService.SHOWER_GRAY_FRACTION
        shower_black = shower_total_gal * WaterBudgetService.SHOWER_BLACK_FRACTION

        # Combine baseline + showers
        daily_fresh = baseline_fresh  # Fresh only in baseline
        daily_gray = baseline_gray + shower_gray
        daily_black = baseline_black + shower_black

        # Apply temperature multiplier
        temp_multiplier = (
            WaterBudgetService.MULTIPLIER_HOT_DAYS
            if hot_days
            else WaterBudgetService.MULTIPLIER_NORMAL_DAYS
        )

        daily_fresh *= temp_multiplier
        daily_gray *= temp_multiplier
        daily_black *= temp_multiplier

        return daily_fresh, daily_gray, daily_black

    @staticmethod
    def days_remaining(
        fresh_gal: int,
        gray_gal: int,
        black_gal: int,
        people: int,
        showers_per_week: int,
        hot_days: bool,
    ) -> int:
        """
        Estimate days remaining before a tank runs out.

        Main entry point for water budget estimation.

        Inputs:
            fresh_gal: Freshwater tank capacity in gallons (>= 0)
            gray_gal: Gray water tank capacity in gallons (>= 0)
            black_gal: Black water tank capacity in gallons (>= 0)
            people: Number of people in RV (>= 1)
            showers_per_week: Weekly shower frequency (>= 0)
            hot_days: True if hot weather, False if normal/cool

        Returns:
            Days remaining (integer >= 0) before first tank runs out
            Limited by whichever tank depletes first (fresh/gray/black)

        Behavior:
            - If any tank is 0, returns 0 (no water)
            - If all inputs valid, calculates which tank is limiting
            - Returns floored integer (conservative estimate)
            - Never returns negative (clamped to >= 0)

        Example:
            fresh_gal=50, gray_gal=40, black_gal=20, people=2,
            showers_per_week=2, hot_days=False
            
            Daily usage (estimated):
            - Fresh: ~3.2 gal
            - Gray: ~4.5 gal
            - Black: ~1.9 gal
            
            Tank depletion:
            - Fresh lasts: 50 / 3.2 = 15.6 days
            - Gray lasts: 40 / 4.5 = 8.9 days (LIMITING)
            - Black lasts: 20 / 1.9 = 10.5 days
            
            Result: 8 days (gray tank is limiting factor)
        """
        # Input validation
        if people < 1:
            raise ValueError(f"people must be >= 1, got {people}")
        if showers_per_week < 0:
            raise ValueError(f"showers_per_week must be >= 0, got {showers_per_week}")

        # Handle zero/negative tanks (clamp gracefully)
        fresh_gal = max(0, fresh_gal)
        gray_gal = max(0, gray_gal)
        black_gal = max(0, black_gal)

        # If any tank is 0, trip ends immediately
        if fresh_gal == 0 or gray_gal == 0 or black_gal == 0:
            return 0

        # Calculate daily usage
        daily_fresh, daily_gray, daily_black = WaterBudgetService.calculate_daily_usage(
            people, showers_per_week, hot_days
        )

        # Avoid division by zero (should not happen with our constants, but defensive)
        if daily_fresh <= 0 or daily_gray <= 0 or daily_black <= 0:
            return 0

        # Calculate days each tank lasts
        fresh_days = fresh_gal / daily_fresh
        gray_days = gray_gal / daily_gray
        black_days = black_gal / daily_black

        # Find limiting factor (whichever runs out first)
        days = min(fresh_days, gray_days, black_days)

        # Floor to integer and clamp to >= 0
        days_int = max(0, int(days))

        return days_int

    @staticmethod
    def days_remaining_with_breakdown(
        fresh_gal: int,
        gray_gal: int,
        black_gal: int,
        people: int,
        showers_per_week: int,
        hot_days: bool,
    ) -> WaterBudgetResult:
        """
        Estimate days remaining with detailed breakdown.

        Same as days_remaining() but returns full breakdown including:
        - Which tank is limiting
        - How long each tank would last individually
        - Daily usage rates

        Returns:
            WaterBudgetResult with all metrics
        """
        # Input validation
        if people < 1:
            raise ValueError(f"people must be >= 1, got {people}")
        if showers_per_week < 0:
            raise ValueError(f"showers_per_week must be >= 0, got {showers_per_week}")

        # Handle zero/negative tanks
        fresh_gal = max(0, fresh_gal)
        gray_gal = max(0, gray_gal)
        black_gal = max(0, black_gal)

        # If any tank is 0, trip ends immediately
        if fresh_gal == 0 or gray_gal == 0 or black_gal == 0:
            return WaterBudgetResult(
                days_remaining=0,
                limiting_factor="fresh",
                fresh_days=0.0,
                gray_days=0.0,
                black_days=0.0,
                daily_fresh_gal=0.0,
                daily_gray_gal=0.0,
                daily_black_gal=0.0,
                advisory="⚠️ One or more tanks are empty",
            )

        # Calculate daily usage
        daily_fresh, daily_gray, daily_black = WaterBudgetService.calculate_daily_usage(
            people, showers_per_week, hot_days
        )

        # Avoid division by zero
        if daily_fresh <= 0 or daily_gray <= 0 or daily_black <= 0:
            return WaterBudgetResult(
                days_remaining=0,
                limiting_factor="fresh",
                fresh_days=0.0,
                gray_days=0.0,
                black_days=0.0,
                daily_fresh_gal=daily_fresh,
                daily_gray_gal=daily_gray,
                daily_black_gal=daily_black,
                advisory="⚠️ Invalid usage calculation",
            )

        # Calculate days each tank lasts
        fresh_days = fresh_gal / daily_fresh
        gray_days = gray_gal / daily_gray
        black_days = black_gal / daily_black

        # Find limiting factor
        min_days = min(fresh_days, gray_days, black_days)

        if min_days == fresh_days:
            limiting = "fresh"
        elif min_days == gray_days:
            limiting = "gray"
        else:
            limiting = "black"

        # Floor to integer and clamp
        days_int = max(0, int(min_days))

        # Generate advisory
        if days_int == 0:
            advisory = "⚠️ Not enough water for this trip"
        elif days_int == 1:
            advisory = f"⏱️ {limiting.capitalize()} tank is limiting (1 day)"
        elif days_int <= 3:
            advisory = f"🚨 Short trip - {limiting.capitalize()} tank limits to {days_int} days"
        elif days_int <= 7:
            advisory = f"💧 {limiting.capitalize()} tank limits to ~{days_int} days"
        else:
            advisory = f"✅ Good for {days_int}+ days ({limiting.capitalize()} tank limits)"

        return WaterBudgetResult(
            days_remaining=days_int,
            limiting_factor=limiting,
            fresh_days=fresh_days,
            gray_days=gray_days,
            black_days=black_days,
            daily_fresh_gal=daily_fresh,
            daily_gray_gal=daily_gray,
            daily_black_gal=daily_black,
            advisory=advisory,
        )
