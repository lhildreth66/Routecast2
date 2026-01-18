"""
Solar Forecast Service - Pure Deterministic Domain Logic

This module provides pure, side-effect-free functions for solar forecasting
along a route. All functions are deterministic and testable.

Following gold-standard principles:
- Pure functions with no side effects
- No external API calls (those belong in repository layer)
- Clear input/output contracts
- Comprehensive error handling
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple
from datetime import datetime, timedelta
import math


@dataclass(frozen=True)
class SolarCondition:
    """Immutable solar condition data point."""
    timestamp: str  # ISO format
    latitude: float
    longitude: float
    cloud_cover_percent: int  # 0-100
    uv_index: float  # 0-11+
    solar_irradiance_watts_m2: float  # W/m²
    visibility_km: float  # Affects solar potential


@dataclass(frozen=True)
class SolarForecast:
    """Result of solar forecasting calculation."""
    waypoint_lat: float
    waypoint_lon: float
    timestamp: str
    peak_solar_potential: float  # 0-100 (percentage)
    best_time_window: Optional[Tuple[str, str]]  # (start_time, end_time) ISO format
    advisory: str
    is_favorable_for_solar: bool


class SolarForecastService:
    """
    Pure domain service for solar forecasting.
    
    All methods are pure functions - same inputs always produce same outputs.
    No I/O, no external calls, no mutable state.
    """

    # Solar constant and atmospheric factors (constants)
    SOLAR_CONSTANT_W_M2 = 1361  # W/m² at top of atmosphere
    MIN_USABLE_IRRADIANCE = 100  # W/m² minimum for meaningful solar capture
    
    @staticmethod
    def calculate_solar_potential(
        conditions: SolarCondition,
    ) -> float:
        """
        Pure function: Calculate solar potential (0-100%) from weather conditions.
        
        Args:
            conditions: Solar condition data point
            
        Returns:
            Solar potential percentage (0-100)
            
        Raises:
            ValueError: If input values are out of valid ranges
        """
        # Validate inputs
        if not (-90 <= conditions.latitude <= 90):
            raise ValueError(f"Invalid latitude: {conditions.latitude}")
        if not (-180 <= conditions.longitude <= 180):
            raise ValueError(f"Invalid longitude: {conditions.longitude}")
        if not (0 <= conditions.cloud_cover_percent <= 100):
            raise ValueError(f"Invalid cloud cover: {conditions.cloud_cover_percent}")
        if not (0 <= conditions.uv_index <= 20):
            raise ValueError(f"Invalid UV index: {conditions.uv_index}")
        if conditions.solar_irradiance_watts_m2 < 0:
            raise ValueError(f"Invalid irradiance: {conditions.solar_irradiance_watts_m2}")
        if conditions.visibility_km < 0:
            raise ValueError(f"Invalid visibility: {conditions.visibility_km}")
        
        # Cloud cover impact (most significant)
        cloud_factor = (100 - conditions.cloud_cover_percent) / 100.0
        
        # Irradiance impact (normalized to solar constant)
        irradiance_factor = min(
            conditions.solar_irradiance_watts_m2 / SolarForecastService.SOLAR_CONSTANT_W_M2,
            1.0
        )
        
        # UV index impact (higher UV = better conditions)
        uv_factor = min(conditions.uv_index / 11.0, 1.0)
        
        # Visibility impact (aerosols and haze reduce solar capture)
        visibility_factor = min(conditions.visibility_km / 20.0, 1.0)
        
        # Weighted combination
        potential = (
            cloud_factor * 0.50 +  # Cloud cover is primary driver
            irradiance_factor * 0.25 +
            uv_factor * 0.15 +
            visibility_factor * 0.10
        ) * 100
        
        return max(0.0, min(100.0, potential))  # Clamp to 0-100
    
    @staticmethod
    def evaluate_solar_favorability(
        potential: float,
        irradiance: float,
    ) -> bool:
        """
        Pure function: Determine if conditions are favorable for solar capture.
        
        Args:
            potential: Solar potential percentage (0-100)
            irradiance: Solar irradiance (W/m²)
            
        Returns:
            True if conditions are favorable for solar energy capture
        """
        return (
            potential >= 60 and
            irradiance >= SolarForecastService.MIN_USABLE_IRRADIANCE
        )
    
    @staticmethod
    def find_best_solar_window(
        hourly_conditions: List[SolarCondition],
    ) -> Optional[Tuple[str, str]]:
        """
        Pure function: Find the best consecutive 3-hour window for solar capture.
        
        Args:
            hourly_conditions: List of hourly condition readings
            
        Returns:
            Tuple of (start_time, end_time) for best window, or None if no good window
            
        Raises:
            ValueError: If list is empty or has fewer than 3 elements
        """
        if len(hourly_conditions) < 3:
            raise ValueError("Need at least 3 hourly conditions to find window")
        
        best_window = None
        best_score = 0.0
        
        # Slide a 3-hour window through the data
        for i in range(len(hourly_conditions) - 2):
            window = hourly_conditions[i:i+3]
            
            # Calculate average potential for this window
            avg_potential = sum(
                SolarForecastService.calculate_solar_potential(c) for c in window
            ) / len(window)
            
            if avg_potential > best_score:
                best_score = avg_potential
                best_window = (window[0].timestamp, window[2].timestamp)
        
        # Only return window if it's good enough
        if best_score >= 50:
            return best_window
        return None
    
    @staticmethod
    def generate_solar_advisory(
        potential: float,
        is_favorable: bool,
        cloud_cover: int,
    ) -> str:
        """
        Pure function: Generate human-readable solar advisory.
        
        Args:
            potential: Solar potential percentage
            is_favorable: Whether conditions are favorable
            cloud_cover: Cloud cover percentage
            
        Returns:
            Advisory text for the user
        """
        if potential < 20:
            return "☁️ Heavy cloud cover. Poor solar conditions."
        elif potential < 40:
            return "🌥️ Moderate clouds. Mediocre solar capture."
        elif potential < 60:
            return "⛅ Partly cloudy. Fair solar conditions."
        elif is_favorable:
            return "☀️ Excellent solar conditions! Optimal for capture."
        else:
            return "🌤️ Good solar potential."
    
    @staticmethod
    def forecast_for_waypoint(
        conditions: SolarCondition,
    ) -> SolarForecast:
        """
        Pure function: Generate complete solar forecast for a waypoint.
        
        Args:
            conditions: Solar condition at waypoint
            
        Returns:
            Complete solar forecast with advisory
        """
        potential = SolarForecastService.calculate_solar_potential(conditions)
        is_favorable = SolarForecastService.evaluate_solar_favorability(
            potential,
            conditions.solar_irradiance_watts_m2
        )
        advisory = SolarForecastService.generate_solar_advisory(
            potential,
            is_favorable,
            conditions.cloud_cover_percent
        )
        
        return SolarForecast(
            waypoint_lat=conditions.latitude,
            waypoint_lon=conditions.longitude,
            timestamp=conditions.timestamp,
            peak_solar_potential=round(potential, 1),
            best_time_window=None,  # Single point, not a window
            advisory=advisory,
            is_favorable_for_solar=is_favorable
        )
    
    @staticmethod
    def forecast_for_waypoints(
        conditions_list: List[SolarCondition],
    ) -> List[SolarForecast]:
        """
        Pure function: Generate solar forecasts for multiple waypoints.
        
        Args:
            conditions_list: List of solar conditions
            
        Returns:
            List of solar forecasts
            
        Raises:
            ValueError: If list is empty
        """
        if not conditions_list:
            raise ValueError("Cannot forecast for empty conditions list")
        
        return [
            SolarForecastService.forecast_for_waypoint(c)
            for c in conditions_list
        ]


def calculate_sunrise_sunset_impact(
    latitude: float,
    longitude: float,
    timestamp: str,
) -> float:
    """
    Pure function: Calculate impact of time of day on solar potential (0-1).
    
    Uses simplified solar position calculation (not astronomical precision).
    
    Args:
        latitude: Location latitude
        longitude: Location longitude
        timestamp: ISO format timestamp
        
    Returns:
        Factor 0-1 indicating position in solar day
    """
    try:
        dt = datetime.fromisoformat(timestamp)
    except (ValueError, TypeError):
        return 0.0  # Invalid timestamp
    
    # Day of year (1-365)
    day_of_year = dt.timetuple().tm_yday
    
    # Hour of day (0-23)
    hour = dt.hour + dt.minute / 60.0
    
    # Simplified: Solar noon occurs around hour 12 + longitude correction
    solar_noon_hour = 12 + (longitude / 15.0)  # 15 degrees per hour
    
    # Peak solar potential around solar noon
    hours_from_noon = abs(hour - solar_noon_hour)
    
    # Gaussian-like curve: peak at noon, declining by afternoon
    if hours_from_noon > 12:
        hours_from_noon = 24 - hours_from_noon
    
    solar_potential = max(0.0, 1.0 - (hours_from_noon / 12.0) ** 2)
    
    # Seasonal variation (more hours of daylight in summer)
    # Simplified using day of year
    if 80 <= day_of_year <= 265:  # Approximate spring/summer/fall
        seasonal_factor = 1.0
    else:  # Winter
        seasonal_factor = 0.7
    
    return solar_potential * seasonal_factor
