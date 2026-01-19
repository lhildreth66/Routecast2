"""
Terrain Shade Service - Solar Path & Shade Blocking Calculations

Pure domain logic for estimating shade and sunlight at RV boondocking sites.
Implements simplified but deterministic solar path calculations and shade factor
estimation based on tree canopy and horizon obstructions.

All functions are pure and deterministic (no I/O, no random state).

Physics Model:
- Sun path: Simplified hourly solar elevation angles across daylight hours
  * Uses simple geometric approximation (not full ephemeris)
  * Assumes typical sunrise/sunset times based on latitude and month
  * Returns hourly sunlight slots from 6 AM to 6 PM local time
  
- Shade blocking: Combines canopy coverage and horizon obstruction
  * Canopy: Tree coverage percentage (0-100%)
  * Horizon obstruction: Terrain/ridges blocking degrees (0-90°)
  * Result: Shade factor 0.0 (fully exposed) to 1.0 (fully shaded)

Constants:
- HOURS_PER_DAY: 24 hours in a day
- DAYLIGHT_START: 6 AM (sunrise approximation)
- DAYLIGHT_END: 18 (6 PM, sunset approximation)
- MAX_OBSTRUCTION_ANGLE: 90 degrees (max horizon blockage)
- MAX_CANOPY_PCT: 100% (max tree coverage)
- ALTITUDE_ADJUSTMENT: Elevation affects sunrise/sunset ~4 min per 1000 ft
"""

from dataclasses import dataclass
from datetime import date, time
from math import sin, cos, radians, degrees, asin
from typing import List


@dataclass(frozen=True)
class SunSlot:
    """
    Represents a hourly sunlight slot in the daylight timeline.
    
    Attributes:
        hour: Hour of day (6-18 for typical daylight hours)
        sun_elevation_deg: Sun elevation angle above horizon (0-90°)
        usable_sunlight_fraction: Fraction of sunlight after obstruction (0.0-1.0)
        time_label: Human-readable time label (e.g., "6 AM", "12 PM")
    """
    hour: int
    sun_elevation_deg: float
    usable_sunlight_fraction: float
    time_label: str


class TerrainShadeService:
    """
    Pure domain logic for terrain shade and solar calculations.
    
    All methods are static and deterministic.
    """
    
    # Constants
    DAYLIGHT_START = 6        # 6 AM sunrise approximation
    DAYLIGHT_END = 18         # 6 PM (18:00) sunset approximation
    MAX_ELEVATION = 90        # Maximum sun elevation angle (degrees)
    MAX_OBSTRUCTION_ANGLE = 90  # Maximum horizon obstruction angle
    MAX_CANOPY_PCT = 100      # Maximum canopy coverage percentage
    
    @staticmethod
    def sun_path(
        latitude: float,
        longitude: float,
        observation_date: date
    ) -> List[SunSlot]:
        """
        Calculate hourly solar elevation path across daylight hours.
        
        Uses simplified geometric approximation to estimate sun elevation angle
        at each hour during typical daylight (6 AM to 6 PM local time).
        
        Latitude variation:
        - Equator (0°): Sun passes nearly overhead; elevation peaks ~90°
        - Temperate (40°): Sun elevation peaks ~50-60° depending on season
        - Far north (70°): Sun elevation peaks ~20° or lower in winter
        
        Seasonal variation (via day-of-year):
        - Winter solstice (day ~355): Sun lowest, elevation reduced ~20°
        - Equinox (day ~80, ~265): Medium elevation
        - Summer solstice (day ~172): Sun highest, elevation increased ~20°
        
        Args:
            latitude: Observer latitude in degrees (-90 to +90)
            longitude: Observer longitude in degrees (-180 to +180, unused but kept for future)
            observation_date: Date for which to calculate sun path
        
        Returns:
            List of SunSlot objects (one per hour from 6 AM to 6 PM)
            Guaranteed non-empty. Hours listed chronologically.
        
        Notes:
            - Time is local solar time (simplified, ignoring timezone offsets)
            - Elevation angles are clamped to 0-90°
            - Does not account for atmospheric refraction
            - Does not use external APIs (purely geometric approximation)
        """
        # Validate latitude
        latitude = float(latitude)
        if latitude < -90 or latitude > 90:
            latitude = max(-90, min(90, latitude))
        
        day_of_year = observation_date.timetuple().tm_yday
        
        slots = []
        
        for hour in range(TerrainShadeService.DAYLIGHT_START, TerrainShadeService.DAYLIGHT_END + 1):
            # Hour angle: -180 to +180 degrees relative to solar noon (12 PM)
            # At 6 AM: -90°, 9 AM: -45°, 12 PM: 0°, 3 PM: +45°, 6 PM: +90°
            hour_angle_deg = (hour - 12) * 15  # 15° per hour
            hour_angle_rad = radians(hour_angle_deg)
            
            # Declination: angle of sun relative to equatorial plane
            # Varies ±23.44° over the year (Earth's axial tilt)
            # Day 0 = Jan 1 (winter), Day ~172 = Jun 21 (summer)
            declination_deg = 23.44 * sin(radians((day_of_year - 81) * 360 / 365.25))
            declination_rad = radians(declination_deg)
            
            lat_rad = radians(latitude)
            
            # Solar altitude angle (elevation above horizon)
            # sin(alt) = sin(lat) × sin(dec) + cos(lat) × cos(dec) × cos(h)
            sin_elevation = (
                sin(lat_rad) * sin(declination_rad) +
                cos(lat_rad) * cos(declination_rad) * cos(hour_angle_rad)
            )
            
            # Clamp to -1 to +1 to handle floating-point edge cases
            sin_elevation = max(-1, min(1, sin_elevation))
            elevation_rad = asin(sin_elevation)
            elevation_deg = degrees(elevation_rad)
            
            # Clamp elevation to 0-90° (below horizon = 0)
            elevation_deg = max(0, min(TerrainShadeService.MAX_ELEVATION, elevation_deg))
            
            # Usable sunlight fraction (preliminary, before obstruction)
            # Linear approximation: full light at 30°+, ramps up from 0-30°
            if elevation_deg < 5:
                usable_fraction = 0.0  # Below 5°, too low for useful light
            elif elevation_deg < 30:
                usable_fraction = (elevation_deg - 5) / 25  # Ramp from 0 to 1
            else:
                usable_fraction = 1.0
            
            # Convert hour to 12-hour AM/PM format for label
            if hour < 12:
                hour_12 = hour if hour > 0 else 12
                period = "AM"
            elif hour == 12:
                hour_12 = 12
                period = "PM"
            else:
                hour_12 = hour - 12
                period = "PM"
            
            time_label = f"{hour_12} {period}"
            
            slot = SunSlot(
                hour=hour,
                sun_elevation_deg=round(elevation_deg, 1),
                usable_sunlight_fraction=round(usable_fraction, 2),
                time_label=time_label,
            )
            slots.append(slot)
        
        return slots
    
    @staticmethod
    def shade_blocks(
        tree_canopy_pct: int,
        horizon_obstruction_deg: int
    ) -> float:
        """
        Calculate combined shade blocking factor from canopy and horizon obstruction.
        
        Shade factor represents the fraction of sunlight blocked (0.0 = fully exposed,
        1.0 = fully shaded).
        
        Model:
        - Canopy effect: Percentage of sky covered by trees (0-100%)
            * 0% = no trees, full sunlight
            * 100% = dense canopy, maximum blocking
        
        - Horizon obstruction: Degrees of horizon blocked by terrain/ridges (0-90°)
            * 0° = flat horizon, no obstructions
            * 90° = vertical cliff/mountain blocks all sunlight
            * Typically < 45° in most boondocking sites
        
        Combined formula (weighted average):
            shade_factor = (canopy_pct / 100) × 0.6 + (obstruction_deg / 90) × 0.4
        
        Weighting rationale:
            - Tree canopy is local and controllable (choose site with/without trees)
            - Horizon obstruction is geographic and fixed (can't change terrain)
            - Empirically, trees matter more for typical RV sites
            - 60/40 split balances both factors reasonably
        
        Args:
            tree_canopy_pct: Percentage of sky covered by tree canopy (0-100)
                Clamped to 0-100 if outside range
            horizon_obstruction_deg: Degrees of horizon blocked (0-90)
                Clamped to 0-90 if outside range
        
        Returns:
            Shade factor (0.0 = no shade, 1.0 = full shade)
            Always clamped to 0.0-1.0
        
        Examples:
            - No trees, clear horizon: shade_blocks(0, 0) -> 0.0 (fully exposed)
            - Heavy canopy, clear horizon: shade_blocks(80, 0) -> 0.48 (48% blocked)
            - No trees, horizon obstructed: shade_blocks(0, 45) -> 0.2 (20% blocked)
            - Dense trees, hills: shade_blocks(100, 90) -> 1.0 (fully shaded)
        
        Notes:
            - Input validation: Both inputs are clamped to valid ranges
            - Floating-point: Returns float for precision, not integer percentage
            - Deterministic: Same inputs always produce same output
        """
        # Clamp canopy to 0-100%
        canopy_pct = max(0, min(100, int(tree_canopy_pct)))
        
        # Clamp obstruction to 0-90°
        obstruction_deg = max(0, min(90, int(horizon_obstruction_deg)))
        
        # Calculate shade factor using weighted average
        # Canopy contributes 60%, obstruction contributes 40%
        shade_factor = (canopy_pct / 100.0) * 0.6 + (obstruction_deg / 90.0) * 0.4
        
        # Ensure result is in valid range (should already be due to clamping, but be safe)
        shade_factor = max(0.0, min(1.0, shade_factor))
        
        return round(shade_factor, 3)
    
    @staticmethod
    def sun_exposure_hours(
        latitude: float,
        longitude: float,
        observation_date: date,
        tree_canopy_pct: int,
        horizon_obstruction_deg: int
    ) -> float:
        """
        Calculate total effective sunlight hours after shade obstruction.
        
        Combines sun_path() and shade_blocks() to estimate how many hours of useful
        sunlight reach the RV site after accounting for local obstructions.
        
        Args:
            latitude: Observer latitude (degrees)
            longitude: Observer longitude (degrees)
            observation_date: Date for calculation
            tree_canopy_pct: Tree canopy coverage (0-100%)
            horizon_obstruction_deg: Horizon obstruction (0-90°)
        
        Returns:
            Effective sunlight hours (0.0-12.0 for typical daylight window)
            Rounded to 1 decimal place
        
        Example:
            Sun path shows 8 hours of usable light.
            Shade blocks 40% of it (shade_factor = 0.4).
            Effective hours: 8 × (1 - 0.4) = 4.8 hours
        """
        # Get sun path
        slots = TerrainShadeService.sun_path(latitude, longitude, observation_date)
        
        # Calculate shade blocking
        shade_factor = TerrainShadeService.shade_blocks(tree_canopy_pct, horizon_obstruction_deg)
        
        # Sum usable sunlight, then apply shade blocking
        total_unblocked_hours = sum(slot.usable_sunlight_fraction for slot in slots)
        effective_hours = total_unblocked_hours * (1.0 - shade_factor)
        
        return round(effective_hours, 1)
