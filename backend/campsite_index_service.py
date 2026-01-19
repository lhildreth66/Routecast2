"""
Task A8: Campsite Index Scoring (Pure & Deterministic)

Scores a boondocking campsite on multiple factors: wind, shade, slope, access, 
signal strength, and road passability. Produces a 0–100 index with detailed breakdown.

Function:
  score(site_factors: SiteFactors, weights: Weights = default_weights()) -> ScoredIndex

All functions are pure, deterministic, and side-effect-free.
"""
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class SiteFactors:
    """Input factors for campsite scoring."""
    wind_gust_mph: float  # Wind gust speed (mph)
    shade_score: float  # 0.0-1.0 (0=no shade, 1=full shade)
    slope_pct: float  # Slope percentage
    access_score: float  # 0.0-1.0 (0=poor, 1=excellent access)
    signal_score: float  # 0.0-1.0 (0=no signal, 1=strong signal)
    road_passability_score: float  # 0-100 (passability from Task A6)


@dataclass(frozen=True)
class Weights:
    """Named weights for each factor. Internally normalized to sum to 1.0."""
    wind: float = 0.2
    shade: float = 0.15
    slope: float = 0.15
    access: float = 0.15
    signal: float = 0.15
    passability: float = 0.2

    def normalize(self) -> "Weights":
        """Return a normalized copy where all weights sum to 1.0."""
        total = self.wind + self.shade + self.slope + self.access + self.signal + self.passability
        if total == 0:
            total = 1  # Avoid division by zero
        return Weights(
            wind=self.wind / total,
            shade=self.shade / total,
            slope=self.slope / total,
            access=self.access / total,
            signal=self.signal / total,
            passability=self.passability / total,
        )


@dataclass(frozen=True)
class ScoredIndex:
    """Campsite scoring result."""
    score: int  # 0-100
    breakdown: Dict[str, float]  # Factor subscores 0-100
    explanations: Optional[List[str]] = None  # Human-readable reasons


def default_weights() -> Weights:
    """Return default balanced weights."""
    return Weights(
        wind=0.2,
        shade=0.15,
        slope=0.15,
        access=0.15,
        signal=0.15,
        passability=0.2,
    )


def _clamp(value: float, min_val: float, max_val: float) -> float:
    """Clamp value to [min_val, max_val]."""
    return max(min_val, min(max_val, value))


def _normalize_inputs(site_factors: SiteFactors) -> SiteFactors:
    """Normalize and clamp inputs to valid ranges."""
    return SiteFactors(
        wind_gust_mph=max(0.0, float(site_factors.wind_gust_mph)),
        shade_score=_clamp(float(site_factors.shade_score), 0.0, 1.0),
        slope_pct=max(0.0, float(site_factors.slope_pct)),
        access_score=_clamp(float(site_factors.access_score), 0.0, 1.0),
        signal_score=_clamp(float(site_factors.signal_score), 0.0, 1.0),
        road_passability_score=_clamp(float(site_factors.road_passability_score), 0.0, 100.0),
    )


def _subscore_wind(wind_gust_mph: float) -> float:
    """
    Convert wind gust to subscore (higher wind → lower score).
    
    Heuristic:
    - 0 mph → 100 (perfect, no wind)
    - 10 mph → 75 (light, tolerable)
    - 20 mph → 50 (moderate, uncomfortable)
    - 30 mph → 25 (strong, poor camping)
    - 40+ mph → 0 (severe, unusable)
    
    Linear degradation with cliff at 40 mph.
    """
    if wind_gust_mph <= 0:
        return 100.0
    elif wind_gust_mph >= 40:
        return 0.0
    else:
        # Linear: 100 at 0 mph, 0 at 40 mph
        return 100.0 - (wind_gust_mph / 40.0) * 100.0


def _subscore_shade(shade_score: float) -> float:
    """
    Convert shade to subscore (higher shade → higher score, but not linearly).
    
    Heuristic:
    - shade_score is 0.0-1.0
    - At 0 (no shade): subscore 40 (bare sun, less comfortable)
    - At 0.5 (moderate shade): subscore 80 (good balance)
    - At 1.0 (full shade): subscore 90 (great for hot days)
    
    Curve: subscore = 40 + 50 * sqrt(shade_score)
    """
    return 40.0 + 50.0 * (shade_score ** 0.5)


def _subscore_slope(slope_pct: float) -> float:
    """
    Convert slope to subscore (higher slope → lower score).
    
    Heuristic:
    - 0% slope → 100 (flat, ideal)
    - 5% slope → 80 (gentle, comfortable)
    - 10% slope → 60 (moderate, possible)
    - 15% slope → 40 (steep, uncomfortable)
    - 25%+ slope → 0 (very steep, difficult)
    
    Linear degradation with cliff at 25%.
    """
    if slope_pct <= 0:
        return 100.0
    elif slope_pct >= 25:
        return 0.0
    else:
        # Linear: 100 at 0%, 0 at 25%
        return 100.0 - (slope_pct / 25.0) * 100.0


def _subscore_access(access_score: float) -> float:
    """
    Convert access to subscore (higher access → higher score).
    
    Heuristic:
    - access_score is 0.0-1.0 (0=poor, 1=excellent)
    - Direct mapping: subscore = access_score * 100
    """
    return access_score * 100.0


def _subscore_signal(signal_score: float) -> float:
    """
    Convert signal to subscore (higher signal → higher score).
    
    Heuristic:
    - signal_score is 0.0-1.0 (0=no signal, 1=strong signal)
    - Direct mapping: subscore = signal_score * 100
    """
    return signal_score * 100.0


def _subscore_passability(road_passability_score: float) -> float:
    """
    Convert road passability to subscore.
    
    Heuristic:
    - road_passability_score is 0-100
    - Direct mapping: subscore = road_passability_score
    """
    return float(road_passability_score)


def score(
    site_factors: SiteFactors,
    weights: Optional[Weights] = None,
) -> ScoredIndex:
    """
    Score a campsite on multiple factors.
    
    Args:
        site_factors: SiteFactors with wind, shade, slope, access, signal, passability
        weights: Optional custom weights (default balanced). Automatically normalized.
    
    Returns:
        ScoredIndex with overall score 0-100, breakdown per factor, and explanations
    """
    # Normalize inputs
    factors = _normalize_inputs(site_factors)
    
    # Use default if no weights provided
    if weights is None:
        weights = default_weights()
    
    # Normalize weights
    w = weights.normalize()
    
    # Calculate subscores for each factor (each 0-100)
    wind_sub = _subscore_wind(factors.wind_gust_mph)
    shade_sub = _subscore_shade(factors.shade_score)
    slope_sub = _subscore_slope(factors.slope_pct)
    access_sub = _subscore_access(factors.access_score)
    signal_sub = _subscore_signal(factors.signal_score)
    passability_sub = _subscore_passability(factors.road_passability_score)
    
    # Weighted sum
    overall = (
        wind_sub * w.wind
        + shade_sub * w.shade
        + slope_sub * w.slope
        + access_sub * w.access
        + signal_sub * w.signal
        + passability_sub * w.passability
    )
    
    # Clamp to 0-100
    overall = _clamp(overall, 0.0, 100.0)
    
    # Breakdown
    breakdown = {
        "wind": round(wind_sub, 1),
        "shade": round(shade_sub, 1),
        "slope": round(slope_sub, 1),
        "access": round(access_sub, 1),
        "signal": round(signal_sub, 1),
        "passability": round(passability_sub, 1),
    }
    
    # Generate explanations based on factor strengths
    explanations = []
    
    # Wind comment
    if factors.wind_gust_mph <= 10:
        explanations.append("Excellent wind conditions")
    elif factors.wind_gust_mph >= 30:
        explanations.append(f"Wind {factors.wind_gust_mph} mph: poor comfort")
    
    # Shade comment
    if factors.shade_score >= 0.7:
        explanations.append("Good shade coverage")
    elif factors.shade_score == 0:
        explanations.append("Fully exposed (no shade)")
    
    # Slope comment
    if factors.slope_pct <= 5:
        explanations.append("Flat or gently sloped terrain")
    elif factors.slope_pct >= 15:
        explanations.append(f"Steep slope {factors.slope_pct}%: setup challenge")
    
    # Access comment
    if factors.access_score >= 0.8:
        explanations.append("Excellent road access")
    elif factors.access_score <= 0.3:
        explanations.append("Poor access: difficult approach")
    
    # Signal comment
    if factors.signal_score >= 0.7:
        explanations.append("Strong cellular signal")
    elif factors.signal_score <= 0.2:
        explanations.append("Weak signal: limited connectivity")
    
    # Passability comment
    if factors.road_passability_score >= 80:
        explanations.append("Road passable in all conditions")
    elif factors.road_passability_score <= 40:
        explanations.append("Road passability limited")
    
    return ScoredIndex(
        score=int(round(overall)),
        breakdown=breakdown,
        explanations=explanations if explanations else None,
    )
