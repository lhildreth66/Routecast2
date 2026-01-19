"""
Wind Shelter Service - RV Orientation & Wind Protection Recommendations

Pure domain logic for recommending optimal RV orientation based on wind patterns
and local terrain shelter (ridges, hills).

All functions are pure and deterministic (no I/O, no random state).

Physics Model:
- Wind load: Increases with gust speed (generally quadratic relationship)
  * Low gusts (< 20 mph): Minimal concern, any orientation acceptable
  * Medium gusts (20-40 mph): Start positioning to minimize broadside exposure
  * High gusts (> 40 mph): Critical to align nose into wind or find shelter
  
- Shelter effectiveness: Ridges block wind from specific directions
  * Ridge bearing: Direction ridge is oriented (0-360°)
  * Upwind position: Ridge on upwind side (within ±30° tolerance)
  * Strength: Determines how much wind reduction it provides
  
- Orientation strategy:
  * No shelter: Point nose into predominant wind
  * With shelter: Use ridge if upwind, adjust orientation accordingly
  * Risk assessment: Combines gust severity and shelter availability

Constants:
- CALM_WIND_THRESHOLD: < 15 mph (low risk, flexible orientation)
- MODERATE_WIND_THRESHOLD: < 35 mph (medium risk, recommend positioning)
- HIGH_WIND_THRESHOLD: >= 35 mph (high risk, critical positioning)
- SHELTER_TOLERANCE: ±30° bearing tolerance for upwind ridge detection
- BEARING_RESOLUTION: 360° circle, normalized 0-359
"""

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional


class RiskLevel(str, Enum):
    """Wind risk assessment levels"""
    LOW = "low"           # < 20 mph gusts, flexible orientation
    MEDIUM = "medium"     # 20-40 mph gusts, position matters
    HIGH = "high"         # > 40 mph gusts, critical positioning


@dataclass(frozen=True)
class Ridge:
    """
    Local terrain feature (ridge, hill, or rock formation) that can provide wind shelter.
    
    Attributes:
        bearing_deg: Direction ridge faces/blocks wind from (0-360°)
            0° = north, 90° = east, 180° = south, 270° = west
        strength: Shelter strength (low/med/high)
            low = minor obstacle, ~10-20% wind reduction
            med = moderate hill, ~30-50% wind reduction
            high = large ridge/mountain, ~60-80% wind reduction
        name: Optional human-readable name (e.g., "north ridge")
    """
    bearing_deg: int
    strength: str  # "low", "med", "high"
    name: Optional[str] = None
    
    def __post_init__(self):
        """Validate ridge attributes"""
        if not 0 <= self.bearing_deg < 360:
            raise ValueError(f"bearing_deg must be 0-359, got {self.bearing_deg}")
        if self.strength not in ("low", "med", "high"):
            raise ValueError(f"strength must be 'low'/'med'/'high', got {self.strength}")


@dataclass(frozen=True)
class OrientationAdvice:
    """
    Recommendation for RV orientation and wind shelter strategy.
    
    Attributes:
        recommended_bearing_deg: Direction RV nose should point (0-360°)
            0° = north, 90° = east, 180° = south, 270° = west
        rationale_text: Human-readable explanation of recommendation
        risk_level: Overall wind risk assessment (low/medium/high)
        shelter_available: Whether a nearby ridge can provide protection
        estimated_wind_reduction_pct: % wind load reduction from positioning + shelter
    """
    recommended_bearing_deg: int
    rationale_text: str
    risk_level: str
    shelter_available: bool
    estimated_wind_reduction_pct: int


class WindShelterService:
    """
    Pure domain logic for wind orientation and shelter recommendations.
    
    All methods are static and deterministic.
    """
    
    # Wind speed thresholds (mph)
    CALM_WIND_THRESHOLD = 15
    MODERATE_WIND_THRESHOLD = 35
    HIGH_WIND_THRESHOLD = float('inf')  # Anything above MODERATE_WIND_THRESHOLD is high
    
    # Shelter detection
    SHELTER_TOLERANCE = 30  # ±30° bearing tolerance for upwind ridge
    
    @staticmethod
    def _normalize_bearing(bearing_deg: float) -> int:
        """
        Normalize bearing to 0-359° range.
        
        Handles negative bearings and values >= 360.
        
        Examples:
            -10 -> 350
            370 -> 10
            180 -> 180
        """
        bearing = float(bearing_deg)
        normalized = bearing % 360
        if normalized < 0:
            normalized += 360
        return int(round(normalized)) % 360
    
    @staticmethod
    def _bearing_difference(bearing1_deg: float, bearing2_deg: float) -> float:
        """
        Calculate shortest angular difference between two bearings (degrees).
        
        Returns value 0-180° (never > 180°, which would indicate opposite direction).
        
        Examples:
            _bearing_difference(10, 350) -> 20° (shortest path across north)
            _bearing_difference(45, 225) -> 180° (opposite directions)
            _bearing_difference(0, 90) -> 90° (east from north)
        """
        b1 = WindShelterService._normalize_bearing(bearing1_deg)
        b2 = WindShelterService._normalize_bearing(bearing2_deg)
        
        diff = abs(b1 - b2)
        # Take shortest path around circle
        if diff > 180:
            diff = 360 - diff
        
        return diff
    
    @staticmethod
    def _is_ridge_upwind(
        ridge_bearing_deg: float,
        wind_bearing_deg: float,
        tolerance_deg: float = SHELTER_TOLERANCE
    ) -> bool:
        """
        Check if a ridge is positioned upwind (provides shelter).
        
        A ridge is upwind if it faces within ±tolerance° of the wind direction.
        
        Args:
            ridge_bearing_deg: Direction ridge faces (0-360°)
            wind_bearing_deg: Direction wind is coming FROM (0-360°)
            tolerance_deg: Angle tolerance for detection (default 30°)
        
        Returns:
            True if ridge can block wind, False otherwise
        
        Example:
            Wind from north (0°), ridge facing north: ridge is upwind -> True
            Wind from north (0°), ridge facing south (180°): ridge is downwind -> False
        """
        diff = WindShelterService._bearing_difference(ridge_bearing_deg, wind_bearing_deg)
        return diff <= tolerance_deg
    
    @staticmethod
    def _assess_risk_level(gust_mph: int) -> str:
        """
        Assess wind risk based on gust speed.
        
        Args:
            gust_mph: Peak wind gust in miles per hour
        
        Returns:
            Risk level: "low", "medium", or "high"
        """
        if gust_mph < WindShelterService.CALM_WIND_THRESHOLD:
            return RiskLevel.LOW.value
        elif gust_mph < WindShelterService.MODERATE_WIND_THRESHOLD:
            return RiskLevel.MEDIUM.value
        else:
            return RiskLevel.HIGH.value
    
    @staticmethod
    def recommend_orientation(
        predominant_dir_deg: int,
        gust_mph: int,
        local_ridges: Optional[List[Ridge]] = None
    ) -> OrientationAdvice:
        """
        Recommend optimal RV orientation to minimize wind exposure.
        
        Strategy:
        1. Check for upwind ridges that can provide shelter
        2. If strong shelter available: recommend orientation that maximizes it
        3. If no good shelter: point nose into wind (minimizes broadside exposure)
        4. Assess overall risk and provide rationale
        
        Wind loading physics:
        - Broadside exposure = worst (maximum cross-sectional area)
        - Nose-on exposure = best (minimal frontal area, aerodynamic)
        - 45° angle = compromise, moderate exposure
        
        Args:
            predominant_dir_deg: Wind direction it's coming FROM (0-360°)
                0° = north wind, 90° = east wind, etc.
            gust_mph: Peak wind gust speed in mph
            local_ridges: List of nearby ridges that might provide shelter
                If None or empty, no shelter available
        
        Returns:
            OrientationAdvice with recommended bearing, risk level, and rationale
        
        Examples:
            Wind from north (0°), no shelter, gusts 30 mph:
            -> recommend_bearing = 0° (point nose north into wind)
            -> risk = "medium"
            -> rationale = "Point nose into wind to minimize broadside..."
            
            Wind from west (270°), ridge upwind from west, gusts 25 mph:
            -> recommend_bearing = 270° (align with ridge for shelter)
            -> risk = "medium"
            -> rationale = "Position behind western ridge for shelter..."
        """
        # Normalize input bearing
        wind_from = WindShelterService._normalize_bearing(predominant_dir_deg)
        
        # Validate gust speed
        gust_mph = max(0, int(gust_mph))
        
        # Initialize defaults
        local_ridges = local_ridges or []
        risk_level = WindShelterService._assess_risk_level(gust_mph)
        
        # Find best upwind ridge for shelter
        best_ridge = None
        best_shelter_bearing = None
        
        if local_ridges:
            for ridge in local_ridges:
                if WindShelterService._is_ridge_upwind(ridge.bearing_deg, wind_from):
                    # This ridge can provide shelter
                    if best_ridge is None or ridge.strength in ("high", "med") and best_ridge.strength == "low":
                        best_ridge = ridge
        
        # Determine recommended orientation and wind reduction
        shelter_available = best_ridge is not None
        wind_reduction_pct = 0
        
        if shelter_available and best_ridge:
            # Use shelter: position behind the ridge
            recommended_bearing = best_ridge.bearing_deg
            
            # Calculate wind reduction based on shelter strength
            strength_reduction = {
                "low": 15,   # 15% reduction from small shelter
                "med": 35,   # 35% reduction from medium ridge
                "high": 60,  # 60% reduction from large ridge
            }
            wind_reduction_pct = strength_reduction.get(best_ridge.strength, 0)
            
            rationale = (
                f"Position behind {best_ridge.name or 'upwind ridge'} "
                f"({best_ridge.strength.upper()} shelter) for ~{wind_reduction_pct}% wind reduction. "
                f"Gusts: {gust_mph} mph."
            )
        else:
            # No shelter: point nose into wind
            recommended_bearing = wind_from
            
            if gust_mph < WindShelterService.CALM_WIND_THRESHOLD:
                rationale = (
                    f"Low winds ({gust_mph} mph). Any orientation acceptable; "
                    f"recommend facing north for convenience."
                )
                wind_reduction_pct = 0
            elif gust_mph < WindShelterService.MODERATE_WIND_THRESHOLD:
                rationale = (
                    f"Point nose north into wind ({gust_mph} mph gusts) "
                    f"to minimize broadside exposure. No upwind shelter available."
                )
                wind_reduction_pct = 20  # Nose-on positioning reduces load vs broadside
            else:
                rationale = (
                    f"CRITICAL: Point nose directly into wind ({gust_mph} mph gusts). "
                    f"No upwind shelter available. Consider relocating to sheltered site."
                )
                wind_reduction_pct = 20
        
        return OrientationAdvice(
            recommended_bearing_deg=recommended_bearing,
            rationale_text=rationale,
            risk_level=risk_level,
            shelter_available=shelter_available,
            estimated_wind_reduction_pct=wind_reduction_pct,
        )
    
    @staticmethod
    def assess_ridge_effectiveness(
        ridge: Ridge,
        gust_mph: int
    ) -> dict:
        """
        Assess how effective a specific ridge is for wind shelter.
        
        Returns dict with:
        - effectiveness_pct: How much wind reduction this ridge provides
        - min_gust_to_matter: Below this wind speed, ridge doesn't help much
        - max_protection: Maximum benefit this ridge can provide
        
        Args:
            ridge: Ridge object to assess
            gust_mph: Wind gust speed in mph
        
        Returns:
            Dict with effectiveness metrics
        """
        # Ridge strength determines effectiveness
        strength_metrics = {
            "low": {"effectiveness_pct": 15, "min_gust": 20, "max_protection": 20},
            "med": {"effectiveness_pct": 35, "min_gust": 15, "max_protection": 45},
            "high": {"effectiveness_pct": 60, "min_gust": 10, "max_protection": 70},
        }
        
        metrics = strength_metrics.get(ridge.strength, {})
        
        # Effectiveness increases with gust speed (more impactful in strong wind)
        base_effectiveness = metrics.get("effectiveness_pct", 0)
        if gust_mph < metrics.get("min_gust", 15):
            # Below minimum threshold, ridge provides minimal benefit
            adjusted_effectiveness = base_effectiveness * (gust_mph / metrics.get("min_gust", 15))
        else:
            # Above minimum, full effectiveness
            adjusted_effectiveness = base_effectiveness
        
        return {
            "effectiveness_pct": min(metrics.get("max_protection", 100), int(adjusted_effectiveness)),
            "min_gust_to_matter": metrics.get("min_gust", 15),
            "max_protection": metrics.get("max_protection", 100),
            "ridge_name": ridge.name or f"{ridge.bearing_deg}° ridge",
        }
