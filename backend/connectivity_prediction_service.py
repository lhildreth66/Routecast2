"""
Task A7: Connectivity Prediction (Pure & Deterministic)

Predicts cellular signal strength and Starlink obstruction risk based on
tower distance, terrain, horizon obstruction, and canopy coverage.

Functions:
  cell_bars_probability(carrier: str, tower_distance_km: float, terrain_obstruction: int) -> float
  obstruction_risk(horizon_south_deg: int, canopy_pct: int) -> str

All functions are pure, deterministic, and side-effect-free.
No external APIs are called.
"""
from dataclasses import dataclass
from typing import List, Optional

# Supported carriers
CARRIERS = {"verizon", "att", "tmobile", "unknown"}

# Risk level strings
RISK_LEVELS = {"low", "medium", "high"}


@dataclass(frozen=True)
class CellProbabilityResult:
    """Cell signal probability assessment."""
    carrier: str
    probability: float  # 0.0-1.0
    bar_estimate: str  # "no signal", "1-2 bars", "2-3 bars", "3+ bars"
    explanation: str


@dataclass(frozen=True)
class StarlinkRiskResult:
    """Starlink obstruction risk assessment."""
    risk_level: str  # "low", "medium", "high"
    obstruction_score: float  # 0.0-1.0 internal score
    explanation: str
    reasons: Optional[List[str]] = None


def _normalize_inputs_cell(carrier: str, tower_distance_km: float, terrain_obstruction: int):
    """Normalize and validate cell inputs."""
    # Normalize carrier
    carrier_norm = (carrier or "unknown").strip().lower()
    if carrier_norm not in CARRIERS:
        carrier_norm = "unknown"
    # Clamp distance to non-negative
    distance = max(0.0, float(tower_distance_km))
    # Clamp obstruction to 0-100
    obstruction = max(0, min(100, int(terrain_obstruction)))
    return carrier_norm, distance, obstruction


def _normalize_inputs_starlink(horizon_south_deg: int, canopy_pct: int):
    """Normalize and validate Starlink inputs."""
    # Clamp horizon to 0-90 degrees
    horizon = max(0, min(90, int(horizon_south_deg)))
    # Clamp canopy to 0-100
    canopy = max(0, min(100, int(canopy_pct)))
    return horizon, canopy


def cell_bars_probability(
    carrier: str,
    tower_distance_km: float,
    terrain_obstruction: int,
) -> CellProbabilityResult:
    """
    Predict cellular signal bar probability.

    Heuristics:
    - Base probability starts at 1.0 (perfect signal at tower).
    - Probability decreases with distance: penalty = sqrt(distance_km) * 0.15.
    - Probability decreases with terrain obstruction: penalty = (obstruction / 100) * 0.5.
    - Carrier-specific curve multipliers (verizon +5%, tmobile -5%, others neutral).
    - Final probability clamped to [0.0, 1.0].

    Args:
        carrier: "verizon", "att", "tmobile", or "unknown"
        tower_distance_km: Distance to nearest tower (km, clamped ≥0)
        terrain_obstruction: Terrain obstruction factor 0-100 (hills/mountains/dense vegetation)

    Returns:
        CellProbabilityResult with probability [0.0-1.0], bar estimate, and explanation
    """
    carrier_norm, distance, obstruction = _normalize_inputs_cell(carrier, tower_distance_km, terrain_obstruction)

    # Base probability degradation with distance
    # sqrt() models radio attenuation more realistically than linear
    distance_penalty = (distance ** 0.5) * 0.15  # sqrt scale, 15% per sqrt(km)
    
    # Terrain obstruction penalty
    obstruction_penalty = (obstruction / 100.0) * 0.5  # max 50% penalty
    
    # Carrier-specific multiplier
    carrier_multiplier = {
        "verizon": 1.05,  # Slightly better coverage
        "att": 1.0,
        "tmobile": 0.95,  # Slightly less coverage
        "unknown": 1.0,
    }[carrier_norm]
    
    # Compute probability
    prob = 1.0 - distance_penalty - obstruction_penalty
    prob = prob * carrier_multiplier
    prob = max(0.0, min(1.0, prob))  # Clamp to [0.0, 1.0]
    
    # Estimate bar count from probability
    if prob >= 0.8:
        bar_estimate = "3+ bars"
    elif prob >= 0.6:
        bar_estimate = "2-3 bars"
    elif prob >= 0.3:
        bar_estimate = "1-2 bars"
    else:
        bar_estimate = "no signal"
    
    # Explanation
    reasons = []
    if distance > 5:
        reasons.append(f"tower {distance:.1f} km away")
    if obstruction >= 50:
        reasons.append(f"significant terrain obstruction {obstruction}%")
    
    explanation = f"{bar_estimate} ({carrier_norm})" + (f"; {', '.join(reasons)}" if reasons else "")
    
    return CellProbabilityResult(
        carrier=carrier_norm,
        probability=round(prob, 3),
        bar_estimate=bar_estimate,
        explanation=explanation,
    )


def obstruction_risk(horizon_south_deg: int, canopy_pct: int) -> StarlinkRiskResult:
    """
    Assess Starlink satellite obstruction risk.

    Heuristics:
    - Starlink satellites are visible 30-60° above southern horizon.
    - Southern horizon obstruction (trees, mountains) blocks view.
    - Canopy also blocks satellite signals.
    - Obstruction score = (horizon_deg / 90) * 0.5 + (canopy_pct / 100) * 0.5.
    - Thresholds: score < 0.3 → low, 0.3-0.6 → medium, ≥ 0.6 → high.

    Args:
        horizon_south_deg: Degrees of southern horizon obstruction (0-90°, clamped)
        canopy_pct: Tree canopy coverage (0-100%, clamped)

    Returns:
        StarlinkRiskResult with risk level ("low"/"medium"/"high"), score, and explanation
    """
    horizon, canopy = _normalize_inputs_starlink(horizon_south_deg, canopy_pct)
    
    # Compute obstruction score
    # Horizon and canopy weighted equally
    horizon_component = (horizon / 90.0) * 0.5
    canopy_component = (canopy / 100.0) * 0.5
    obstruction_score = horizon_component + canopy_component
    
    # Map to risk level
    if obstruction_score < 0.3:
        risk_level = "low"
    elif obstruction_score < 0.6:
        risk_level = "medium"
    else:
        risk_level = "high"
    
    # Explanation with reasons
    reasons = []
    if horizon >= 30:
        reasons.append(f"southern horizon obstructed {horizon}°")
    if canopy >= 60:
        reasons.append(f"canopy {canopy}%")
    
    explanation = f"{risk_level} risk"
    if reasons:
        explanation += f" ({', '.join(reasons)})"
    
    return StarlinkRiskResult(
        risk_level=risk_level,
        obstruction_score=round(obstruction_score, 3),
        explanation=explanation,
        reasons=reasons if reasons else None,
    )
