"""
Road Passability Service - Pure Deterministic Domain Logic

Evaluates road passability based on weather, terrain, and soil conditions.
All functions are pure, deterministic, and side-effect-free.

Inputs:
  - precip_72h: Precipitation in last 72 hours (mm)
  - slope_pct: Road grade/slope percentage
  - min_temp_f: Minimum temperature (°F)
  - soil_type: Type of soil ('clay', 'sand', 'loam', 'rocky', 'unknown')

Output:
  - passability_score: 0-100 (0=impassable, 100=excellent)
  - mud_risk: True if muddy conditions likely
  - ice_risk: True if icing conditions likely
  - four_x_four_recommended: True if 4WD/high-clearance advised
  - clearance_needed_cm: Minimum ground clearance needed (cm)
"""

from dataclasses import dataclass
from typing import Optional
import math


@dataclass(frozen=True)
class PassabilityRisks:
    """Immutable passability risk factors."""
    mud_risk: bool
    ice_risk: bool
    deep_rut_risk: bool
    high_clearance_recommended: bool
    four_x_four_recommended: bool


@dataclass(frozen=True)
class RoadPassabilityResult:
    """Complete road passability assessment."""
    passability_score: float  # 0-100
    condition_assessment: str  # descriptive text
    risks: PassabilityRisks
    min_clearance_cm: float  # minimum ground clearance needed
    recommended_vehicle_type: str  # 'sedan', 'suv', '4x4', 'high_clearance'
    advisory: str  # human-readable warning or OK message


class RoadPassabilityService:
    """
    Pure domain service for evaluating road passability.
    
    All methods are pure functions - deterministic, no side effects.
    """
    
    # Soil type moisture saturation points
    SOIL_MOISTURE_THRESHOLDS = {
        'clay': {
            'dry': 0,
            'moist': 15,
            'wet': 30,
            'saturated': 50,  # mm in 72h
        },
        'sandy_loam': {
            'dry': 0,
            'moist': 10,
            'wet': 25,
            'saturated': 40,
        },
        'sand': {
            'dry': 0,
            'moist': 5,
            'wet': 15,
            'saturated': 30,
        },
        'loam': {
            'dry': 0,
            'moist': 12,
            'wet': 28,
            'saturated': 45,
        },
        'rocky': {
            'dry': 0,
            'moist': 20,
            'wet': 40,
            'saturated': 60,  # Rocky soil drains well
        },
    }
    
    @staticmethod
    def calculate_soil_moisture_level(
        precip_72h: float,
        soil_type: str,
    ) -> str:
        """
        Pure function: Determine soil moisture level from precipitation.
        
        Args:
            precip_72h: Precipitation in last 72 hours (mm)
            soil_type: Type of soil ('clay', 'sand', 'loam', 'rocky', 'unknown')
            
        Returns:
            Moisture level: 'dry', 'moist', 'wet', or 'saturated'
            
        Raises:
            ValueError: If inputs are invalid
        """
        if precip_72h < 0:
            raise ValueError(f"Precipitation cannot be negative: {precip_72h}")
        if not isinstance(soil_type, str):
            raise ValueError(f"Soil type must be string: {soil_type}")
        
        # Default to loam if soil type unknown
        normalized_soil = soil_type.lower().strip()
        if normalized_soil not in RoadPassabilityService.SOIL_MOISTURE_THRESHOLDS:
            normalized_soil = 'loam'
        
        thresholds = RoadPassabilityService.SOIL_MOISTURE_THRESHOLDS[normalized_soil]
        
        if precip_72h <= thresholds['moist']:
            return 'dry'
        elif precip_72h <= thresholds['wet']:
            return 'moist'
        elif precip_72h <= thresholds['saturated']:
            return 'wet'
        else:
            return 'saturated'
    
    @staticmethod
    def calculate_mud_risk(
        moisture_level: str,
        slope_pct: float,
    ) -> bool:
        """
        Pure function: Determine if mud risk is present.
        
        Args:
            moisture_level: 'dry', 'moist', 'wet', or 'saturated'
            slope_pct: Road grade/slope percentage
            
        Returns:
            True if mud risk is significant
        """
        # Mud risk increases with moisture and decreases with slope (water drains)
        if moisture_level == 'saturated':
            return True  # Always muddy when saturated
        elif moisture_level == 'wet':
            return slope_pct < 8  # Muddy on gentle slopes
        elif moisture_level == 'moist':
            return slope_pct < 3  # Only on very gentle slopes
        else:
            return False  # Dry conditions
    
    @staticmethod
    def calculate_ice_risk(
        min_temp_f: float,
        precip_72h: float,
    ) -> bool:
        """
        Pure function: Determine if icing risk is present.
        
        Args:
            min_temp_f: Minimum temperature in °F
            precip_72h: Precipitation in last 72 hours (mm)
            
        Returns:
            True if icing risk is significant
        """
        # Freezing point is 32°F
        if min_temp_f > 35:
            return False  # Too warm for ice
        elif min_temp_f <= 32:
            return precip_72h > 0  # Any moisture at freezing = ice risk
        else:
            # Between 32-35°F: risk increases with moisture
            return precip_72h > 5
    
    @staticmethod
    def calculate_clearance_needed(
        moisture_level: str,
        slope_pct: float,
    ) -> float:
        """
        Pure function: Calculate minimum ground clearance needed (cm).
        
        Args:
            moisture_level: 'dry', 'moist', 'wet', or 'saturated'
            slope_pct: Road grade/slope percentage
            
        Returns:
            Minimum ground clearance in cm
        """
        base_clearance = 15  # cm - normal road
        
        # Moisture adds rut depth
        moisture_clearance = {
            'dry': 0,
            'moist': 5,
            'wet': 15,
            'saturated': 30,
        }
        clearance = base_clearance + moisture_clearance.get(moisture_level, 0)
        
        # Steep slopes create erosion ruts
        if slope_pct > 12:
            clearance += 10
        elif slope_pct > 8:
            clearance += 5
        
        return clearance
    
    @staticmethod
    def calculate_passability_score(
        precip_72h: float,
        slope_pct: float,
        min_temp_f: float,
        soil_type: str,
    ) -> float:
        """
        Pure function: Calculate passability score (0-100).
        
        Args:
            precip_72h: Precipitation in last 72 hours (mm)
            slope_pct: Road grade/slope percentage (0-100+)
            min_temp_f: Minimum temperature (°F)
            soil_type: Type of soil
            
        Returns:
            Passability score: 0=impassable, 100=excellent
            
        Raises:
            ValueError: If inputs are invalid
        """
        if precip_72h < 0:
            raise ValueError(f"Precipitation cannot be negative: {precip_72h}")
        if not (-90 <= slope_pct <= 100):
            raise ValueError(f"Slope must be -90 to 100%: {slope_pct}")
        if not (-50 <= min_temp_f <= 130):
            raise ValueError(f"Temperature out of realistic range: {min_temp_f}°F")
        
        # Start with ideal conditions
        score = 100.0
        
        # Precipitation impact (increases mud risk)
        moisture_level = RoadPassabilityService.calculate_soil_moisture_level(
            precip_72h, soil_type
        )
        
        if moisture_level == 'saturated':
            score -= 60  # Severe reduction
        elif moisture_level == 'wet':
            score -= 40
        elif moisture_level == 'moist':
            score -= 15
        else:
            score -= 0  # Dry is fine
        
        # Temperature impact (ice/traction)
        if min_temp_f <= 32:
            if precip_72h > 0:
                score -= 40  # Ice is serious
            else:
                score -= 15  # Cold but no ice
        elif min_temp_f <= 35:
            score -= 20  # Risk of freezing
        
        # Slope impact (too steep is harder)
        if slope_pct > 25:
            score -= 50  # Very steep, traction issues
        elif slope_pct > 15:
            score -= 30
        elif slope_pct > 8:
            score -= 15
        elif slope_pct < -15:
            score -= 40  # Steep downhill
        elif slope_pct < -8:
            score -= 20
        
        # Soil type bearing capacity
        soil_scores = {
            'clay': -20,  # Clay is worst when wet
            'sandy_loam': -10,
            'loam': 0,  # Neutral reference
            'sand': 5,  # Drains well
            'rocky': 10,  # Drains and provides traction
        }
        normalized_soil = soil_type.lower().strip()
        if normalized_soil in soil_scores:
            soil_penalty = soil_scores[normalized_soil]
        else:
            soil_penalty = 0
        
        # Apply soil penalty especially if wet
        if moisture_level in ['wet', 'saturated']:
            score += soil_penalty
        
        return max(0.0, min(100.0, score))  # Clamp to 0-100
    
    @staticmethod
    def evaluate_vehicle_recommendation(
        score: float,
        slope_pct: float,
        clearance_needed: float,
    ) -> tuple[str, bool]:
        """
        Pure function: Recommend vehicle type and 4WD need.
        
        Args:
            score: Passability score (0-100)
            slope_pct: Road grade percentage
            clearance_needed: Minimum ground clearance (cm)
            
        Returns:
            Tuple of (recommended_vehicle_type, four_x_four_recommended)
        """
        # Standard sedan has ~15cm clearance
        # SUV has ~20-25cm clearance
        # High-clearance 4x4 has ~30cm+ clearance
        
        needs_high_clearance = clearance_needed > 22
        is_steep = abs(slope_pct) > 15
        is_very_poor = score < 40
        is_poor = score < 60
        
        # Decision tree
        if is_very_poor or (is_steep and needs_high_clearance):
            return ('4x4', True)
        elif is_poor or (needs_high_clearance and slope_pct > 8):
            return ('suv', True)
        elif needs_high_clearance:
            return ('suv', False)
        else:
            return ('sedan', False)
    
    @staticmethod
    def generate_advisory(
        score: float,
        mud_risk: bool,
        ice_risk: bool,
        clearance_needed: float,
        slope_pct: float,
    ) -> str:
        """
        Pure function: Generate human-readable advisory.
        
        Args:
            score: Passability score
            mud_risk: Whether muddy conditions
            ice_risk: Whether icy conditions
            clearance_needed: Minimum ground clearance
            slope_pct: Road grade
            
        Returns:
            Advisory text with emoji
        """
        if score >= 80:
            return "✅ Road appears well-maintained and passable"
        elif score >= 60:
            advisory = "⚠️ Road passable but conditions degraded."
            issues = []
            if mud_risk:
                issues.append("muddy sections")
            if ice_risk:
                issues.append("icy patches")
            if clearance_needed > 25:
                issues.append("deep ruts")
            if abs(slope_pct) > 15:
                issues.append("steep grade")
            if issues:
                advisory += f" Watch for: {', '.join(issues)}."
            return advisory
        elif score >= 40:
            return "❌ Road challenging. High-clearance vehicle recommended. Muddy/rutted."
        else:
            return "🚫 Road impassable. Extreme conditions. Do not attempt."
    
    @staticmethod
    def assess_road_passability(
        precip_72h: float,
        slope_pct: float,
        min_temp_f: float,
        soil_type: str,
    ) -> RoadPassabilityResult:
        """
        Pure function: Complete road passability assessment.
        
        Args:
            precip_72h: Precipitation in last 72 hours (mm)
            slope_pct: Road grade/slope percentage
            min_temp_f: Minimum temperature (°F)
            soil_type: Type of soil
            
        Returns:
            Complete passability assessment
            
        Raises:
            ValueError: If inputs are invalid
        """
        # Validate inputs
        score = RoadPassabilityService.calculate_passability_score(
            precip_72h, slope_pct, min_temp_f, soil_type
        )
        
        moisture_level = RoadPassabilityService.calculate_soil_moisture_level(
            precip_72h, soil_type
        )
        
        mud_risk = RoadPassabilityService.calculate_mud_risk(
            moisture_level, slope_pct
        )
        ice_risk = RoadPassabilityService.calculate_ice_risk(
            min_temp_f, precip_72h
        )
        
        clearance_needed = RoadPassabilityService.calculate_clearance_needed(
            moisture_level, slope_pct
        )
        
        deep_rut_risk = moisture_level in ['wet', 'saturated'] and clearance_needed > 25
        
        vehicle_type, needs_4wd = RoadPassabilityService.evaluate_vehicle_recommendation(
            score, slope_pct, clearance_needed
        )
        
        risks = PassabilityRisks(
            mud_risk=mud_risk,
            ice_risk=ice_risk,
            deep_rut_risk=deep_rut_risk,
            high_clearance_recommended=clearance_needed > 22,
            four_x_four_recommended=needs_4wd,
        )
        
        advisory = RoadPassabilityService.generate_advisory(
            score, mud_risk, ice_risk, clearance_needed, slope_pct
        )
        
        # Determine condition assessment
        if score >= 80:
            condition = "Excellent"
        elif score >= 60:
            condition = "Fair"
        elif score >= 40:
            condition = "Poor"
        else:
            condition = "Impassable"
        
        return RoadPassabilityResult(
            passability_score=round(score, 1),
            condition_assessment=condition,
            risks=risks,
            min_clearance_cm=round(clearance_needed, 1),
            recommended_vehicle_type=vehicle_type,
            advisory=advisory,
        )
