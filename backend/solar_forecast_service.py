"""
Solar Forecast Service - Pure Deterministic Daily Energy Generation Estimation

This module provides pure, side-effect-free functions for estimating daily solar
energy generation at a boondocking location.

Following gold-standard principles:
- Pure functions with no side effects
- No external API calls
- Clear input/output contracts
- Comprehensive error handling
- Fully deterministic and testable
"""

from dataclasses import dataclass
from typing import List
from datetime import datetime
import math


@dataclass(frozen=True)
class SolarForecastResult:
    """Immutable result from solar forecast calculation."""
    daily_wh: List[float]
    dates: List[str]
    panel_watts: float
    shade_pct: float
    cloud_cover: List[float]
    advisory: str


class SolarForecastService:
    """
    Pure deterministic solar energy forecasting service.
    
    Estimates daily solar energy generation (Wh/day) based on:
    - Geographic location (latitude affects sun angle)
    - Date (day of year affects sun height)
    - Solar panel capacity (watts)
    - Cloud cover forecast
    - Shade percentage
    
    All methods are pure functions - same inputs always produce same outputs.
    No I/O, no external calls, no mutable state.
    """

    # Solar constants
    PEAK_SUN_HOURS_EQUATOR = 5.5  # Average peak sun hours at equator on equinox
    DECLINATION_RANGE = 23.44  # Earth's axial tilt (degrees)
    CLOUD_MULTIPLIER_MIN = 0.2  # Minimum on fully overcast day
    CLOUD_MULTIPLIER_MAX = 1.0  # Maximum on clear day

    @staticmethod
    def calculate_clear_sky_baseline(lat: float, doy: int) -> float:
        """
        Calculate clear-sky baseline Wh/day for 1000W panel at location.

        Uses simplified solar irradiance model based on:
        - Latitude (affects sun elevation angle)
        - Day of year (affects declination and day length)

        Args:
            lat: Latitude in degrees (-90 to 90)
            doy: Day of year (1-366)

        Returns:
            Baseline Wh/day assuming 1000W panels with no losses

        Raises:
            ValueError: If latitude or doy out of range
        """
        if lat < -90 or lat > 90:
            raise ValueError(f"Latitude must be -90 to 90, got {lat}")
        if doy < 1 or doy > 366:
            raise ValueError(f"Day of year must be 1-366, got {doy}")

        # Solar declination (varies ±23.44° throughout year)
        declination = (
            SolarForecastService.DECLINATION_RANGE
            * math.sin(2 * math.pi * (doy - 81) / 365.0)
        )

        # Convert to radians
        lat_rad = math.radians(lat)
        decl_rad = math.radians(declination)

        # Solar elevation at noon: sin(elev) = sin(lat)×sin(decl) + cos(lat)×cos(decl)
        sin_elevation = (
            math.sin(lat_rad) * math.sin(decl_rad)
            + math.cos(lat_rad) * math.cos(decl_rad)
        )

        # Clamp to valid range
        sin_elevation = max(-1.0, min(1.0, sin_elevation))
        elevation_rad = math.asin(sin_elevation)
        elevation_deg = math.degrees(elevation_rad)

        # Elevation below horizon means no solar generation
        if elevation_deg <= 0:
            return 0.0

        # Day length (simplified): cos_hour = -tan(lat)×tan(decl)
        cos_hour = -math.tan(lat_rad) * math.tan(decl_rad)
        cos_hour = max(-1.0, min(1.0, cos_hour))

        if abs(cos_hour) >= 1.0:
            day_length = 0.0 if cos_hour >= 1.0 else 24.0
        else:
            hour_angle = math.acos(cos_hour)
            day_length = 2.0 * 24.0 * hour_angle / (2 * math.pi)

        # Peak sun hours based on elevation angle
        # Scale baseline by (elevation/90)^0.75 to account for atmosphere
        peak_sun_factor = (elevation_deg / 90.0) ** 0.75
        peak_sun_hours = (
            SolarForecastService.PEAK_SUN_HOURS_EQUATOR
            * peak_sun_factor
            * (day_length / 12.0)  # Normalized to 12-hour reference
        )

        # Baseline Wh for 1000W panel
        baseline_wh = peak_sun_hours * 1000.0

        return max(0.0, baseline_wh)

    @staticmethod
    def calculate_cloud_multiplier(cloud_cover: float) -> float:
        """
        Calculate cloud cover multiplier (0.2-1.0).

        Maps cloud cover % to output multiplier:
        - 0% cloud → 1.0 (clear, full sun)
        - 50% cloud → 0.6 (partly cloudy)
        - 100% cloud → 0.2 (fully overcast)

        Args:
            cloud_cover: Cloud cover percentage (0-100)

        Returns:
            Multiplier clamped to [0.2, 1.0]

        Raises:
            ValueError: If cloud_cover outside [0, 100]
        """
        if cloud_cover < 0 or cloud_cover > 100:
            raise ValueError(
                f"Cloud cover must be 0-100%, got {cloud_cover}"
            )

        # Linear: 0% → 1.0, 100% → 0.2
        multiplier = 1.0 - (cloud_cover / 100.0) * 0.8

        return max(0.2, min(1.0, multiplier))

    @staticmethod
    def calculate_shade_loss(shade_pct: float) -> float:
        """
        Calculate shade loss factor.

        Shade blocks direct sunlight from panels.

        Args:
            shade_pct: Average shade percentage (0-100)

        Returns:
            Usable sunlight factor (0.0-1.0)

        Raises:
            ValueError: If shade_pct outside [0, 100]
        """
        if shade_pct < 0 or shade_pct > 100:
            raise ValueError(f"Shade must be 0-100%, got {shade_pct}")

        return (100.0 - shade_pct) / 100.0

    @staticmethod
    def date_to_day_of_year(date_str: str) -> int:
        """
        Convert ISO date string to day of year.

        Args:
            date_str: ISO format (e.g., "2026-01-20")

        Returns:
            Day of year (1-366)

        Raises:
            ValueError: If date format invalid
        """
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            return dt.timetuple().tm_yday
        except ValueError as e:
            raise ValueError(f"Invalid date '{date_str}': {e}")

    @staticmethod
    def forecast_daily_wh(
        lat: float,
        lon: float,
        date_range: List[str],
        panel_watts: float,
        shade_pct: float,
        cloud_cover: List[float],
    ) -> SolarForecastResult:
        """
        Forecast daily solar energy generation.

        Args:
            lat: Latitude (-90 to 90)
            lon: Longitude (-180 to 180)
            date_range: List of ISO dates (e.g., ["2026-01-20", "2026-01-21"])
            panel_watts: Panel capacity in watts (>0)
            shade_pct: Average shade percentage (0-100)
            cloud_cover: List of cloud cover % per date (0-100), same length as date_range

        Returns:
            SolarForecastResult with daily_wh list

        Raises:
            ValueError: If any input invalid or inconsistent
        """
        # Input validation
        if lat < -90 or lat > 90:
            raise ValueError(f"Latitude must be -90 to 90, got {lat}")
        if lon < -180 or lon > 180:
            raise ValueError(f"Longitude must be -180 to 180, got {lon}")
        if panel_watts <= 0:
            raise ValueError(f"Panel watts must be >0, got {panel_watts}")
        if not date_range:
            raise ValueError("Date range cannot be empty")
        if len(date_range) != len(cloud_cover):
            raise ValueError(
                f"Cloud cover array length ({len(cloud_cover)}) must match "
                f"date range ({len(date_range)})"
            )

        # Validate shade
        if shade_pct < 0 or shade_pct > 100:
            raise ValueError(f"Shade must be 0-100%, got {shade_pct}")

        # Validate cloud cover array
        for i, cc in enumerate(cloud_cover):
            if cc < 0 or cc > 100:
                raise ValueError(
                    f"Cloud cover[{i}]={cc} must be 0-100%"
                )

        # Calculate fixed factors
        shade_loss = SolarForecastService.calculate_shade_loss(shade_pct)

        # Calculate daily values
        daily_wh = []
        for date_str, cloud_pct in zip(date_range, cloud_cover):
            doy = SolarForecastService.date_to_day_of_year(date_str)
            
            baseline = SolarForecastService.calculate_clear_sky_baseline(
                lat, doy
            )
            cloud_mult = SolarForecastService.calculate_cloud_multiplier(
                cloud_pct
            )

            # Final: baseline × cloud_mult × shade_loss × (panel_watts / 1000)
            wh = (
                baseline
                * cloud_mult
                * shade_loss
                * (panel_watts / 1000.0)
            )

            daily_wh.append(max(0.0, wh))

        # Generate advisory
        avg_cloud = sum(cloud_cover) / len(cloud_cover)
        if avg_cloud > 80:
            advisory = "☁️ Heavy cloud cover expected. Minimal solar generation."
        elif avg_cloud > 50:
            advisory = "🌥️ Partly cloudy forecast. Moderate solar generation."
        else:
            advisory = "☀️ Clear skies expected. Good solar conditions."

        return SolarForecastResult(
            daily_wh=daily_wh,
            dates=date_range,
            panel_watts=panel_watts,
            shade_pct=shade_pct,
            cloud_cover=cloud_cover,
            advisory=advisory,
        )
