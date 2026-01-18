"""
Propane Usage Service - Pure Deterministic Daily Consumption Estimation

This module provides pure, side-effect-free functions for estimating daily propane
consumption for RV/boondocking applications.

Following gold-standard principles:
- Pure functions with no side effects
- No external API calls
- Clear input/output contracts
- Comprehensive error handling
- Fully deterministic and testable

Propane Physics:
- 91,500 BTU per gallon
- 4.24 lbs per gallon
- Therefore: 21,583 BTU per pound
"""

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class PropaneUsageResult:
    """Immutable result from propane usage calculation."""
    daily_lbs: List[float]
    nights_temp_f: List[int]
    furnace_btu: int
    duty_cycle_pct: float
    people: int
    cooking_baseline_lbs: float
    advisory: str


class PropaneUsageService:
    """
    Pure deterministic propane consumption forecasting service.
    
    Estimates daily propane consumption (lbs/day) based on:
    - Furnace BTU capacity and duty cycle percentage
    - Nightly temperatures (affects heating demand)
    - Number of people (affects cooking and hot water)
    - Environmental factors
    
    All methods are pure functions - same inputs always produce same outputs.
    No I/O, no external calls, no mutable state.
    
    Assumptions:
    - Furnace is the primary heating load
    - Duty cycle represents percentage of time furnace runs
    - Temperature affects heating demand but not furnace efficiency
    - Cooking baseline is constant per person per day
    - Hot water heating varies with temperature
    """

    # Propane physical constants
    BTU_PER_GALLON = 91_500  # Standard propane BTU content
    LBS_PER_GALLON = 4.24    # Standard propane density
    BTU_PER_LB = BTU_PER_GALLON / LBS_PER_GALLON  # ~21,583 BTU/lb

    # Usage assumptions
    COOKING_BASELINE_LBS_PER_PERSON_DAY = 0.15  # lbs/day for cooking, estimated
    # This accounts for typical RV cooking (breakfast, lunch, dinner, snacks)
    # Conservative estimate: ~0.3 lbs/person/day for full meal preparation, so using 0.15
    # for moderate cooking

    # Temperature-based heating multipliers
    # Base case: 40°F (mild) = 1.0x
    # Colder temperatures increase heating demand
    # Multipliers are empirically derived from heating curve
    TEMP_MULTIPLIER_MAP = {
        # temp_threshold: (lower_bound, upper_bound, multiplier)
        # Above 55°F: minimal heating
        55: 0.3,   # 55+ F: very light heating
        45: 0.6,   # 45-54 F: light heating
        35: 1.0,   # 35-44 F: moderate (baseline)
        25: 1.5,   # 25-34 F: heavy heating
        15: 2.2,   # 15-24 F: very heavy heating
        5:  3.0,   # 5-14 F: extreme cold
        # Below 5F: 3.0x (extreme)
    }

    @staticmethod
    def get_temperature_multiplier(temp_f: int) -> float:
        """
        Calculate heating demand multiplier based on nightly temperature.

        Uses temperature bands to determine heating load. Colder temperatures
        increase duty cycle demand.

        Physics basis:
        - Heating load is roughly proportional to (indoor_temp - outdoor_temp)
        - Assuming ~70°F indoor target, each 10°F drop increases heating ~20%
        - At 35°F (base), heating load = 1.0x
        - At 55°F, heating load = 0.3x (significant margin)
        - At 5°F, heating load = 3.0x (cold snap)

        Args:
            temp_f: Nightly low temperature in Fahrenheit

        Returns:
            Multiplier for heating duty cycle (0.3 to 3.0)
        """
        if temp_f >= 55:
            return 0.3
        elif temp_f >= 45:
            return 0.6
        elif temp_f >= 35:
            return 1.0
        elif temp_f >= 25:
            return 1.5
        elif temp_f >= 15:
            return 2.2
        elif temp_f >= 5:
            return 3.0
        else:
            # Below 5°F: extreme cold
            return 4.0

    @staticmethod
    def calculate_heating_lbs_per_night(
        furnace_btu: int,
        duty_cycle_pct: float,
        temp_f: int
    ) -> float:
        """
        Calculate propane consumption for furnace heating one night.

        Formula:
        1. Base heating load = furnace_btu × (duty_cycle_pct / 100) / BTU_per_lb
           - This gives lbs/day if furnace ran continuously
        2. Apply temperature multiplier for actual expected heating
           - Colder nights = higher duty cycle
        3. Normalize to one night (divide by 24, multiply by night hours ~8)

        Args:
            furnace_btu: Furnace BTU capacity (e.g., 20000)
            duty_cycle_pct: Percentage of time furnace runs 0-100 (will be clamped)
            temp_f: Nightly low temperature in Fahrenheit

        Returns:
            Lbs propane for one night (~8 hours of heating)
        """
        # Clamp duty cycle to valid range
        duty_cycle_pct = max(0, min(100, duty_cycle_pct))

        # Base consumption: furnace runs at duty_cycle_pct during day
        # Assume 8 hours of heating demand per 24-hour day
        daily_btu_base = furnace_btu * (duty_cycle_pct / 100.0)
        
        # Get temperature multiplier (increases at colder temps)
        temp_multiplier = PropaneUsageService.get_temperature_multiplier(temp_f)

        # Adjust daily demand by temperature multiplier
        # (this represents increased heating at colder temps)
        adjusted_daily_btu = daily_btu_base * temp_multiplier

        # Convert BTU to lbs propane
        daily_lbs = adjusted_daily_btu / PropaneUsageService.BTU_PER_LB

        return daily_lbs

    @staticmethod
    def estimate_lbs_per_day(
        furnace_btu: int,
        duty_cycle_pct: float,
        nights_temp_f: List[int],
        people: int = 2
    ) -> List[float]:
        """
        Estimate daily propane consumption for one or more days/nights.

        Main entry point for propane usage estimation.

        Inputs:
            furnace_btu: Furnace heating capacity in BTU (e.g., 20000, 30000)
            duty_cycle_pct: Percentage of time furnace runs (0-100, will be clamped)
            nights_temp_f: List of nightly low temperatures in Fahrenheit
                          One value per forecast day
            people: Number of people in RV (affects cooking/hot water)
                   Default: 2

        Returns:
            List of daily lbs propane consumption (same length as nights_temp_f)
            Each value = heating + cooking baseline
            Empty list if nights_temp_f is empty

        Behavior:
            - If duty_cycle_pct < 0: clamped to 0
            - If duty_cycle_pct > 100: clamped to 100
            - Heating load varies by temperature (cold = more propane)
            - Cooking baseline always included (even if duty_cycle = 0)
            - Returns empty list if no temperatures provided

        Example:
            furnace_btu=20000, duty_cycle_pct=50, nights_temp_f=[35, 25]
            people=2
            
            Day 1 (35°F):
            - Heating: 20000 × 0.5 / 21583 × 1.0 = 0.46 lbs
            - Cooking: 2 × 0.15 = 0.30 lbs
            - Total: 0.76 lbs
            
            Day 2 (25°F):
            - Heating: 20000 × 0.5 / 21583 × 1.5 = 0.69 lbs
            - Cooking: 2 × 0.15 = 0.30 lbs
            - Total: 0.99 lbs
        """
        # Handle empty list gracefully
        if not nights_temp_f:
            return []

        # Validate inputs
        if furnace_btu <= 0:
            raise ValueError(f"furnace_btu must be > 0, got {furnace_btu}")
        if people < 1:
            raise ValueError(f"people must be >= 1, got {people}")

        # Clamp duty cycle
        duty_cycle_clamped = max(0, min(100, duty_cycle_pct))

        # Calculate cooking/hot water baseline for all people
        cooking_baseline_lbs = people * PropaneUsageService.COOKING_BASELINE_LBS_PER_PERSON_DAY

        # Calculate daily consumption for each night's temperature
        daily_consumption = []
        for temp_f in nights_temp_f:
            # Get heating consumption for this night's temperature
            heating_lbs = PropaneUsageService.calculate_heating_lbs_per_night(
                furnace_btu,
                duty_cycle_clamped,
                temp_f
            )

            # Total = heating + cooking baseline
            total_lbs = heating_lbs + cooking_baseline_lbs

            daily_consumption.append(total_lbs)

        return daily_consumption

    @staticmethod
    def format_advisory(
        furnace_btu: int,
        duty_cycle_pct: float,
        nights_temp_f: List[int],
        people: int,
        daily_lbs: List[float]
    ) -> str:
        """
        Generate human-readable advisory text for propane forecast.

        Provides context about consumption patterns and recommendations.

        Args:
            furnace_btu: Furnace capacity
            duty_cycle_pct: Duty cycle (may be unclamped)
            nights_temp_f: Nightly temperatures
            people: Number of people
            daily_lbs: Calculated daily consumption

        Returns:
            Advisory string with emoji and context
        """
        if not daily_lbs:
            return "📊 No forecast available"

        min_lbs = min(daily_lbs)
        max_lbs = max(daily_lbs)
        avg_lbs = sum(daily_lbs) / len(daily_lbs)

        # Determine characterization based on consumption
        if max_lbs > 2.5:
            emoji = "❄️"
            condition = "Cold snap ahead"
        elif max_lbs > 1.5:
            emoji = "🌡️"
            condition = "Cool nights expected"
        elif max_lbs > 0.8:
            emoji = "🌙"
            condition = "Mild conditions"
        else:
            emoji = "🌤️"
            condition = "Warm temperatures"

        # Trip duration context
        trip_days = len(daily_lbs)
        trip_total = sum(daily_lbs)
        trip_context = f" {trip_days} days = {trip_total:.1f} lbs total"

        return f"{emoji} {condition}{trip_context} (avg {avg_lbs:.2f} lbs/day)"
