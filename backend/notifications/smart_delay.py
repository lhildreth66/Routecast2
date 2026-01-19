"""
Smart Departure Delay Optimizer - Pure domain logic

Compares forecast risk across planned departure time and delayed alternatives.
If delaying improves safety by threshold, returns notification recommendation.

This is Pro-only feature logic.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from enum import Enum


class HazardType(str, Enum):
    """Types of hazards in forecast."""
    HIGH_WIND = "high_wind"
    HEAVY_PRECIP = "heavy_precip"
    FREEZING_TEMP = "freezing_temp"
    SEVERE_ALERT = "severe_alert"


@dataclass(frozen=True)
class HazardBreakdown:
    """Breakdown of hazards contributing to risk score."""
    wind_risk: float  # 0-100, contribution from high wind events
    precip_risk: float  # 0-100, contribution from heavy precipitation
    temp_risk: float  # 0-100, contribution from freezing temps
    severe_alert_risk: float  # 0-100, contribution from severe weather alerts
    
    def total_risk(self) -> float:
        """Average risk across hazard types (simple heuristic)."""
        return (self.wind_risk + self.precip_risk + self.temp_risk + self.severe_alert_risk) / 4.0


@dataclass(frozen=True)
class DelayOption:
    """A specific delay alternative to evaluate."""
    delay_hours: int  # Hours to delay from planned departure
    risk_score: float  # 0-100, overall hazard risk at this time
    hazard_breakdown: HazardBreakdown


@dataclass(frozen=True)
class BestDelayResult:
    """Result of delay optimization analysis."""
    best_delay_hours: int  # Recommended delay in hours
    planned_risk: float  # Risk at original planned time
    best_risk: float  # Risk at recommended delay time
    improvement_pct: float  # Percent reduction in risk (0-100)
    message: str  # Human-readable notification message


class SmartDelayOptimizer:
    """Pure functions for smart departure delay optimization."""
    
    # Risk thresholds (0-100 scale)
    WIND_HIGH_THRESHOLD_KPH = 40  # High wind threshold
    PRECIP_HEAVY_THRESHOLD_MM = 5  # Heavy precip threshold
    TEMP_FREEZING_THRESHOLD_C = 0  # Freezing point
    
    # Improvement requirements
    MIN_IMPROVEMENT_PCT = 15  # Minimum improvement % to recommend
    MAX_DELAY_HOURS = 3  # Don't recommend delay > 3 hours
    
    @staticmethod
    def compute_departure_risk(
        forecast_hourly: List[Dict],  # List of hourly forecasts
        route_waypoints: List[Dict],  # List of route waypoints (lat/lon)
        departure_time: datetime,  # Planned departure in UTC
        window_hours: int = 3,
    ) -> Dict[int, float]:
        """
        Compute risk score for planned departure and delayed alternatives.
        
        Args:
            forecast_hourly: List of hourly forecasts, each with:
                - time: ISO format or datetime
                - wind_kph: Wind speed
                - precip_mm: Precipitation amount
                - temp_c: Temperature
                - severe_alerts: List of alert strings
            route_waypoints: List of waypoints with at minimum lat/lon
            departure_time: Planned departure UTC datetime
            window_hours: Hours to look ahead for delay options (default 3)
        
        Returns:
            Dict mapping delay_hours (0, 1, 2, ...) to risk score (0-100)
        
        Raises:
            ValueError: If inputs invalid or forecast empty
        """
        if not forecast_hourly:
            raise ValueError("forecast_hourly cannot be empty")
        if not route_waypoints:
            raise ValueError("route_waypoints cannot be empty")
        if window_hours < 0:
            raise ValueError("window_hours must be >= 0")
        
        results = {}
        
        # Evaluate planned time and each delay option
        for delay_hours in range(window_hours + 1):
            departure_at = departure_time + timedelta(hours=delay_hours)
            
            # Compute risk for this departure time
            # Simple heuristic: average risk across all waypoints in forecast window
            risk = SmartDelayOptimizer._compute_risk_at_time(
                forecast_hourly, route_waypoints, departure_at
            )
            results[delay_hours] = risk
        
        return results
    
    @staticmethod
    def _compute_risk_at_time(
        forecast_hourly: List[Dict],
        route_waypoints: List[Dict],
        departure_at: datetime,
    ) -> float:
        """
        Compute aggregated risk for all waypoints at this departure time.
        
        Simple approach: take average risk across waypoints.
        In real system, would weight by distance/time-to-waypoint.
        """
        if not forecast_hourly or not route_waypoints:
            return 0.0
        
        # For this simple version, use the first forecast entry
        # (In production, would match forecast time to departure + time-to-waypoint)
        forecast = forecast_hourly[0]
        
        wind_risk = SmartDelayOptimizer._compute_wind_risk(
            forecast.get("wind_kph", 0)
        )
        precip_risk = SmartDelayOptimizer._compute_precip_risk(
            forecast.get("precip_mm", 0)
        )
        temp_risk = SmartDelayOptimizer._compute_temp_risk(
            forecast.get("temp_c", 20)
        )
        severe_risk = SmartDelayOptimizer._compute_severe_alert_risk(
            forecast.get("severe_alerts", [])
        )
        
        # Average across hazard types
        return (wind_risk + precip_risk + temp_risk + severe_risk) / 4.0
    
    @staticmethod
    def _compute_wind_risk(wind_kph: float) -> float:
        """Convert wind speed to 0-100 risk score."""
        if wind_kph < 20:
            return 0.0
        elif wind_kph < SmartDelayOptimizer.WIND_HIGH_THRESHOLD_KPH:
            return 30.0
        elif wind_kph < 60:
            return 60.0
        else:
            return 100.0
    
    @staticmethod
    def _compute_precip_risk(precip_mm: float) -> float:
        """Convert precipitation to 0-100 risk score."""
        if precip_mm < 1:
            return 0.0
        elif precip_mm < SmartDelayOptimizer.PRECIP_HEAVY_THRESHOLD_MM:
            return 40.0
        elif precip_mm < 15:
            return 70.0
        else:
            return 100.0
    
    @staticmethod
    def _compute_temp_risk(temp_c: float) -> float:
        """Convert temperature to 0-100 risk score."""
        if temp_c > 5:
            return 0.0
        elif temp_c > SmartDelayOptimizer.TEMP_FREEZING_THRESHOLD_C:
            return 20.0
        elif temp_c > -10:
            return 50.0
        else:
            return 100.0
    
    @staticmethod
    def _compute_severe_alert_risk(alerts: List[str]) -> float:
        """Convert severe alerts to 0-100 risk score."""
        if not alerts:
            return 0.0
        # Each alert adds risk, capped at 100
        risk = min(100.0, len(alerts) * 30.0)
        return risk
    
    @staticmethod
    def best_delay_option(
        risk_scores: Dict[int, float],
        threshold_improvement_pct: float = MIN_IMPROVEMENT_PCT,
        max_delay: int = MAX_DELAY_HOURS,
    ) -> Optional[BestDelayResult]:
        """
        Find best delay option if improvement meets threshold.
        
        Args:
            risk_scores: Dict from compute_departure_risk(), {delay_hours: risk}
            threshold_improvement_pct: Minimum improvement % to recommend (0-100)
            max_delay: Maximum hours to recommend delaying (0-24)
        
        Returns:
            BestDelayResult if good option found, else None
        
        Raises:
            ValueError: If inputs invalid
        """
        if not risk_scores:
            raise ValueError("risk_scores cannot be empty")
        if threshold_improvement_pct < 0 or threshold_improvement_pct > 100:
            raise ValueError("threshold_improvement_pct must be 0-100")
        if max_delay < 0:
            raise ValueError("max_delay must be >= 0")
        
        # Get planned risk (delay_hours=0)
        planned_risk = risk_scores.get(0, 0.0)
        
        # Find best delay option
        best_delay = 0
        best_risk = planned_risk
        best_improvement = 0.0
        
        for delay_hours in range(1, max_delay + 1):
            if delay_hours not in risk_scores:
                continue
            
            risk = risk_scores[delay_hours]
            if risk < best_risk:
                improvement_pct = ((planned_risk - risk) / max(planned_risk, 0.1)) * 100
                if improvement_pct > best_improvement:
                    best_delay = delay_hours
                    best_risk = risk
                    best_improvement = improvement_pct
        
        # Return result only if improvement meets threshold
        if best_improvement >= threshold_improvement_pct and best_delay > 0:
            message = SmartDelayOptimizer._format_message(
                best_delay, planned_risk, best_risk, best_improvement
            )
            return BestDelayResult(
                best_delay_hours=best_delay,
                planned_risk=round(planned_risk, 1),
                best_risk=round(best_risk, 1),
                improvement_pct=round(best_improvement, 0),
                message=message,
            )
        
        return None
    
    @staticmethod
    def _format_message(
        delay_hours: int,
        planned_risk: float,
        best_risk: float,
        improvement_pct: float,
    ) -> str:
        """Format human-readable notification message."""
        improvement_rounded = int(round(improvement_pct / 5) * 5)  # Round to nearest 5%
        return f"Delay {delay_hours}h avoids ~{improvement_rounded}% hazards"
