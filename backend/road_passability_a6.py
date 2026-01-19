"""
Task A6: Road Passability Scoring (Pure & Deterministic)

Implements a simple, explainable scoring model to assess backroad passability
based on recent precipitation, slope, minimum temperature, and soil type.

Function:
  score(precip72h_in: float, slope_pct: float, min_temp_f: int, soil: str) -> PassabilityResult

Heuristics:
- Mud risk increases with higher precip72h_in, especially for clay soil and higher slope.
- Ice risk when min_temp_f <= 32°F (more severe when precip72h_in > 0).
- Clearance need increases with slope and adverse conditions (mud/ice).
- Soil types: sand (best drainage), loam (neutral), clay (worst for mud).

Input sanitization:
- Precipitation and slope are clamped to non-negative values.
- Slope is capped to 0–60% (extreme grades above 60% treated as 60%).
- Soil values normalized to {'sand','loam','clay'}; unknown -> 'loam'.

The model is fully deterministic and side-effect-free.
"""
from dataclasses import dataclass
from typing import List, Optional

@dataclass(frozen=True)
class PassabilityResult:
    score: int  # 0–100
    mud_risk: bool
    ice_risk: bool
    clearance_need: str  # "low" | "medium" | "high"
    four_by_four_recommended: bool
    reasons: Optional[List[str]] = None


def _normalize_inputs(precip72h_in: float, slope_pct: float, min_temp_f: int, soil: str):
    # Clamp non-negatives
    p = max(0.0, float(precip72h_in))
    s = max(0.0, float(slope_pct))
    # Cap slope to sane range
    s = min(s, 60.0)
    # Normalize temperature to int range (no clamp unless extreme)
    t = int(min_temp_f)
    # Normalize soil
    soil_norm = (soil or "loam").strip().lower()
    if soil_norm not in {"sand", "loam", "clay"}:
        soil_norm = "loam"
    return p, s, t, soil_norm


def _mud_risk(precip72h_in: float, slope_pct: float, soil: str) -> bool:
    # Soil factor: clay 1.3, loam 1.0, sand 0.6
    soil_factor = {"clay": 1.3, "loam": 1.0, "sand": 0.6}[soil]
    # Slope factor increases mud risk per requirements (even though drainage helps)
    slope_factor = 1.0 + (slope_pct / 60.0) * 0.5  # up to +50% at 60%
    mud_index = precip72h_in * soil_factor * slope_factor
    # Thresholds: ~1.0in rain on loam gentle slope -> borderline
    return mud_index >= 1.0


def _ice_risk(min_temp_f: int, precip72h_in: float) -> bool:
    if min_temp_f <= 32:
        return True
    # Slight risk near-freezing with moisture
    if min_temp_f <= 34 and precip72h_in > 0:
        return True
    return False


def _clearance_need(slope_pct: float, mud: bool, ice: bool) -> str:
    # Base from slope
    if slope_pct < 8:
        level = "low"
    elif slope_pct < 15:
        level = "medium"
    else:
        level = "high"
    # Adverse conditions bump clearance one tier
    if (mud or ice) and level == "low":
        level = "medium"
    elif (mud or ice) and level == "medium":
        level = "high"
    return level


def _four_by_four_recommended(clearance: str, mud: bool, ice: bool, slope_pct: float) -> bool:
    if clearance == "high":
        return True
    if ice:
        return True
    if mud and slope_pct >= 10:
        return True
    return False


def _score(precip72h_in: float, slope_pct: float, min_temp_f: int, soil: str, mud: bool, ice: bool, clearance: str) -> int:
    # Start from ideal
    score = 100.0
    # Precipitation penalty, stronger for clay
    soil_penalty = {"clay": 25.0, "loam": 15.0, "sand": 8.0}[soil]
    if precip72h_in >= 2.0:
        score -= soil_penalty
    elif precip72h_in >= 1.0:
        score -= soil_penalty * 0.6
    elif precip72h_in >= 0.3:
        score -= soil_penalty * 0.3
    # Slope penalty
    if slope_pct >= 25:
        score -= 35
    elif slope_pct >= 15:
        score -= 20
    elif slope_pct >= 8:
        score -= 10
    # Ice penalty
    if ice:
        score -= 30 if precip72h_in > 0 else 20
    # Mud penalty (additional to precip)
    if mud:
        score -= 20
    # Clearance penalty
    if clearance == "high":
        score -= 20
    elif clearance == "medium":
        score -= 8
    # Soil base adjustment (sand slightly better, clay slightly worse when any rain)
    if precip72h_in > 0:
        score += {"sand": 5.0, "loam": 0.0, "clay": -5.0}[soil]
    # Clamp
    score = max(0.0, min(100.0, score))
    return int(round(score))


def score(precip72h_in: float, slope_pct: float, min_temp_f: int, soil: str) -> PassabilityResult:
    """Compute road passability.

    Deterministic heuristics:
    - Mud risk grows with rain, amplified by clay and higher slope.
    - Ice risk when freezing (<=32°F), especially if any rain occurred.
    - Clearance requirement increases with slope; mud/ice bumps the tier.
    - Soil normalization: unknown -> loam.

    Input handling:
    - Negative precipitation/slope are clamped to 0.
    - Slope capped to 60%.
    """
    p, s, t, soil_norm = _normalize_inputs(precip72h_in, slope_pct, min_temp_f, soil)
    mud = _mud_risk(p, s, soil_norm)
    ice = _ice_risk(t, p)
    clearance = _clearance_need(s, mud, ice)
    s_val = _score(p, s, t, soil_norm, mud, ice, clearance)

    reasons: List[str] = []
    if mud:
        reasons.append(f"Mud risk high due to {soil_norm} + {p:.1f}in rain")
    if ice:
        reasons.append(f"Ice risk at {t}F" + (" with recent moisture" if p > 0 else ""))
    if s >= 15:
        reasons.append(f"Steep grade {s:.0f}% increases clearance need")
    if not reasons:
        reasons.append("Conditions favorable; good drainage and gentle grade")

    return PassabilityResult(
        score=s_val,
        mud_risk=mud,
        ice_risk=ice,
        clearance_need=clearance,
        four_by_four_recommended=_four_by_four_recommended(clearance, mud, ice, s),
        reasons=reasons,
    )
