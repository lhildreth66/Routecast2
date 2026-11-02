"""
Smart Weather Rerouting Phase 3: Weather Exposure Comparison.

Pure, deterministic geometry/scoring helpers — no network calls, no FastAPI/pydantic
imports (keeps this independently unit-testable and decoupled from server.py, same
pattern as services/bridge_height_service.py).

Core idea: instead of counting alerts at sparse sampled points, compute the REAL
distance (in actual driving miles, not degree-space) a route spends inside each NWS
alert polygon, using Shapely for exact line/polygon intersection (handles polygons
that a route clips through narrowly, MultiPolygons, and polygons with holes), then
severity-weight that exposure into a score contribution.

Geographic accuracy note (critical): Shapely's LineString.project(point, normalized=True)
returns a position in the LineString's own coordinate-space parameterization (raw
longitude/latitude degrees here), which is NOT proportional to real driving miles —
a degree of longitude covers very different real distance depending on latitude, and
a route mixing north/south and east/west segments would get silently wrong mile
markers if normalized project() were used directly. To avoid this, every mile-marker
and exposure-distance computed here uses real haversine distance, interpolated
LOCALLY within a single short route segment (between two consecutive decoded polyline
vertices) — Shapely is used only to find the precise intersection geometry, never to
convert a position along it into a real-world distance.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from shapely.geometry import LineString, Point, shape as shapely_shape
from shapely.geometry.base import BaseGeometry
from shapely.validation import make_valid

# ── Severity weighting ──────────────────────────────────────────────────────────
SEVERITY_RANK = {"extreme": 4.0, "severe": 3.0, "moderate": 2.0, "minor": 1.0, "unknown": 1.0}
URGENCY_MULTIPLIER = {"immediate": 1.5, "expected": 1.0, "future": 0.5, "past": 0.25, "unknown": 1.0}
# A short, explicit, curated list — not exhaustive, not authoritative. Flagged as a
# heuristic in the design/limitations, not a claim of complete NWS event coverage.
DANGEROUS_EVENTS = {
    "tornado warning", "flash flood warning", "ice storm warning", "blizzard warning",
}
DANGEROUS_EVENT_MULTIPLIER = 1.5

# ── Exposure-distance scaling ────────────────────────────────────────────────────
# Strictly increasing (never flat/capped) but concave, so one extreme hazard doesn't
# totally dominate every comparison. 100mi of exposure always scores worse than 50mi
# (100**0.75 ≈ 31.6 vs 50**0.75 ≈ 18.8 — ~68% more penalty, not capped-equal).
HAZARD_EXPOSURE_EXPONENT = 0.75
HAZARD_PENALTY_SCALE = 6.0  # divides the weighted/scaled exposure before subtracting from 0-100

# ── Adaptive sampling budget (used by server.py to decide how many NWS fetch points
#    to request per route before any evaluation happens) ────────────────────────
SAMPLE_BASE_INTERVAL_MILES = 25.0
SAMPLE_MIN_PER_ROUTE = 8       # never regress below the original fixed baseline
SAMPLE_MAX_PER_ROUTE = 30
SAMPLE_MAX_TOTAL_PER_REQUEST = 100  # across every route evaluated together in one request
COVERAGE_GAP_WARN_MILES = 30.0  # anchor spacing above this can hide a hazard between samples


@dataclass(frozen=True)
class ExposureRun:
    """One contiguous stretch where the route is inside a hazard polygon."""
    entry_mile: float
    exit_mile: float

    @property
    def miles(self) -> float:
        return max(0.0, self.exit_mile - self.entry_mile)


@dataclass(frozen=True)
class HazardExposureResult:
    alert_id: str
    event: str
    severity: str
    exposure_miles: float          # 0.0 for zone-only/uncertain alerts — never fabricated
    exposure_minutes: int
    exposure_method: str           # "polygon_intersection" | "zone_only_uncertain"
    entry_mile: Optional[float]    # None for zone-only alerts
    temporally_relevant: bool      # False only when onset/expires definitively don't overlap
    scaled_penalty: float          # severity-weighted, exponent-scaled contribution (0 if excluded)
    weight: float = 1.0             # severity_weight(...) used to compute scaled_penalty — reused
    runs: Tuple[ExposureRun, ...] = field(default_factory=tuple)        # by cross-route delta comparisons so they needn't reconstitute it


def compute_cumulative_miles(coords_latlon: List[Tuple[float, float]]) -> List[float]:
    """Real haversine cumulative distance (miles) at every vertex of a decoded route."""
    if not coords_latlon:
        return []
    cumulative = [0.0]
    for i in range(1, len(coords_latlon)):
        lat1, lon1 = coords_latlon[i - 1]
        lat2, lon2 = coords_latlon[i]
        cumulative.append(cumulative[-1] + _haversine_miles(lat1, lon1, lat2, lon2))
    return cumulative


def _haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 3959.0
    lat1_r, lat2_r = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def build_route_line(coords_latlon: List[Tuple[float, float]]) -> Optional[LineString]:
    """Shapely LineString in (lon, lat) order — GeoJSON/Shapely convention, the OPPOSITE
    of the (lat, lon) tuples the rest of this codebase decodes routes into. Used only
    to compute exact intersection geometry; never used to measure real-world distance."""
    if not coords_latlon or len(coords_latlon) < 2:
        return None
    return LineString([(lon, lat) for lat, lon in coords_latlon])


def parse_alert_geometry(geometry: Optional[Dict[str, Any]]) -> Optional[BaseGeometry]:
    """Parse a raw NWS GeoJSON geometry (Polygon/MultiPolygon, possibly with holes) into
    a Shapely geometry. Returns None for zone-only alerts (geometry is null/missing) or
    on any parse/validity failure — callers must treat None as 'cannot be quantified',
    never as 'no hazard'."""
    if not geometry:
        return None
    try:
        geom = shapely_shape(geometry)
        if not geom.is_valid:
            geom = make_valid(geom)
        return geom
    except Exception:
        return None


def is_zone_only(geometry: Optional[Dict[str, Any]]) -> bool:
    return not geometry


def compute_segment_exposure(
    coords_latlon: List[Tuple[float, float]],
    cumulative_miles: List[float],
    route_line: LineString,
    alert_shape: BaseGeometry,
) -> List[ExposureRun]:
    """Exact real-mile entry/exit for every contiguous stretch where the route crosses
    alert_shape. Walks the route segment-by-segment (not vertex-by-vertex membership)
    so a narrow hazard polygon that slices between two vertices — with neither vertex
    itself inside it — is still detected and measured correctly. A cheap whole-route
    intersects() pre-check skips entirely irrelevant alerts without the per-segment walk."""
    if len(coords_latlon) < 2 or route_line is None or alert_shape is None or alert_shape.is_empty:
        return []
    if not route_line.envelope.intersects(alert_shape.envelope):
        return []
    if not route_line.intersects(alert_shape):
        return []

    runs: List[ExposureRun] = []
    open_run_start: Optional[float] = None
    last_exit_mile: Optional[float] = None

    for i in range(1, len(coords_latlon)):
        lat1, lon1 = coords_latlon[i - 1]
        lat2, lon2 = coords_latlon[i]
        seg_start_mile = cumulative_miles[i - 1]
        seg_end_mile = cumulative_miles[i]
        seg_len_miles = seg_end_mile - seg_start_mile

        seg_line = LineString([(lon1, lat1), (lon2, lat2)])
        if not seg_line.envelope.intersects(alert_shape.envelope):
            _close_open_run(runs, open_run_start, last_exit_mile)
            open_run_start = None
            continue

        inter = seg_line.intersection(alert_shape)
        if inter.is_empty:
            _close_open_run(runs, open_run_start, last_exit_mile)
            open_run_start = None
            continue

        # Find how far along THIS short segment the intersection starts/ends, in real
        # miles, by locally interpolating against the segment's own two endpoints —
        # never using normalized project() over the whole route.
        frac_start, frac_end = _segment_intersection_fraction_range(seg_line, inter)
        entry_mile = seg_start_mile + frac_start * seg_len_miles
        exit_mile = seg_start_mile + frac_end * seg_len_miles

        if open_run_start is None:
            open_run_start = entry_mile
        last_exit_mile = exit_mile

    _close_open_run(runs, open_run_start, last_exit_mile)
    return runs


def _close_open_run(runs: List[ExposureRun], start: Optional[float], end: Optional[float]) -> None:
    if start is not None and end is not None and end > start:
        runs.append(ExposureRun(entry_mile=start, exit_mile=end))


def _segment_intersection_fraction_range(seg_line: LineString, inter: BaseGeometry) -> Tuple[float, float]:
    """Returns (frac_start, frac_end) in [0,1] along seg_line for the intersection's extent.
    seg_line is always just 2 points, so plain (non-normalized) project() here is safe —
    it is only ever used across this one short, effectively-linear sub-segment."""
    points: List[Point] = []
    if inter.geom_type == "Point":
        points = [inter]
    elif inter.geom_type in ("LineString", "LinearRing"):
        coords = list(inter.coords)
        points = [Point(coords[0]), Point(coords[-1])]
    elif inter.geom_type.startswith("Multi") or inter.geom_type == "GeometryCollection":
        for geom in inter.geoms:
            if geom.is_empty:
                continue
            if geom.geom_type == "Point":
                points.append(geom)
            else:
                coords = list(geom.coords)
                if coords:
                    points.append(Point(coords[0]))
                    points.append(Point(coords[-1]))
    if not points:
        return 0.0, 0.0

    seg_length = seg_line.length or 1e-12
    fracs = [seg_line.project(p) / seg_length for p in points]
    fracs = [max(0.0, min(1.0, f)) for f in fracs]
    return min(fracs), max(fracs)


def severity_weight(severity: Optional[str], urgency: Optional[str], event: Optional[str]) -> float:
    sev = SEVERITY_RANK.get((severity or "unknown").strip().lower(), 1.0)
    urg = URGENCY_MULTIPLIER.get((urgency or "unknown").strip().lower(), 1.0)
    event_mult = DANGEROUS_EVENT_MULTIPLIER if (event or "").strip().lower() in DANGEROUS_EVENTS else 1.0
    return sev * urg * event_mult


def scaled_exposure_penalty(total_exposure_miles: float, weight: float) -> float:
    """Strictly increasing in exposure miles, never flat-capped. See module docstring
    and HAZARD_EXPOSURE_EXPONENT for why 100mi always outweighs 50mi."""
    if total_exposure_miles <= 0:
        return 0.0
    return weight * (total_exposure_miles ** HAZARD_EXPOSURE_EXPONENT) / HAZARD_PENALTY_SCALE


def allocate_sample_budgets(
    distances_miles: List[float],
    base_interval: float = SAMPLE_BASE_INTERVAL_MILES,
    min_per_route: int = SAMPLE_MIN_PER_ROUTE,
    max_per_route: int = SAMPLE_MAX_PER_ROUTE,
    max_total: int = SAMPLE_MAX_TOTAL_PER_REQUEST,
) -> List[int]:
    """How many NWS fetch points each route gets in one /route/weather request. Every
    route always gets at least min_per_route (never regresses below the original fixed
    baseline). If the sum of every route's own adaptive target would exceed max_total,
    every route's allocation is scaled down proportionally (fair sharing), but never
    below min_per_route — densification (Pass 2, see server.py) must be carved out of
    this same allocation, never added on top of it."""
    if not distances_miles:
        return []
    raw = [
        max(min_per_route, min(max_per_route, math.ceil(d / base_interval) if d > 0 else min_per_route))
        for d in distances_miles
    ]
    total = sum(raw)
    if total <= max_total:
        return raw
    scale = max_total / total
    return [max(min_per_route, math.floor(t * scale)) for t in raw]


def coverage_gap_miles(distance_miles: float, num_points: int) -> float:
    """Approximate worst-case spacing between evenly-distributed anchor points — used
    to decide whether a route's weather coverage is dense enough to trust, independent
    of whether every individual fetch happened to succeed (more sampling that is still
    too sparse must not be read as proof of safety)."""
    if num_points <= 1 or distance_miles <= 0:
        return distance_miles
    return distance_miles / (num_points - 1)


def temporal_relevance(
    entry_minutes: Optional[float],
    exit_minutes: Optional[float],
    onset_minutes: Optional[float],
    expires_minutes: Optional[float],
) -> bool:
    """All four are minutes-from-departure (None = unknown). Excludes a hazard from
    scoring ONLY when both the alert's window and the route's crossing window are known
    AND they provably do not overlap. Missing/ambiguous timing always defaults to
    relevant=True — never assume a hazard won't matter just because we can't tell."""
    if entry_minutes is None or exit_minutes is None:
        return True
    if onset_minutes is None or expires_minutes is None:
        return True
    return not (exit_minutes < onset_minutes or entry_minutes > expires_minutes)


def compute_hazard_exposure_for_route(
    coords_latlon: List[Tuple[float, float]],
    alerts: List[Dict[str, Any]],
    eta_minutes_fn,
) -> List[HazardExposureResult]:
    """Top-level orchestration for one route against its (already alert-id-deduplicated)
    list of candidate NWS alerts. Each alert dict: id, event, severity, urgency,
    geometry (raw GeoJSON or None), onset_minutes, expires_minutes (minutes-from-departure,
    already converted by the caller — this module has no notion of wall-clock time).
    eta_minutes_fn(mile) -> minutes-from-departure, reused from the caller (calculate_eta)
    so this module never duplicates that constant-speed assumption."""
    if not coords_latlon or len(coords_latlon) < 2:
        return []
    cumulative = compute_cumulative_miles(coords_latlon)
    route_line = build_route_line(coords_latlon)
    results: List[HazardExposureResult] = []

    for alert in alerts:
        alert_id = str(alert.get("id") or "")
        event = alert.get("event") or "Weather Event"
        severity = alert.get("severity") or "Unknown"
        urgency = alert.get("urgency")
        geometry = alert.get("geometry")
        weight = severity_weight(severity, urgency, event)

        if is_zone_only(geometry):
            # Never fabricate a precise distance for a zone/county-only alert — surfaced
            # for transparency, but excluded from the quantitative score entirely.
            results.append(HazardExposureResult(
                alert_id=alert_id, event=event, severity=severity,
                exposure_miles=0.0, exposure_minutes=0,
                exposure_method="zone_only_uncertain",
                entry_mile=None, temporally_relevant=True, scaled_penalty=0.0, weight=weight,
            ))
            continue

        alert_shape = parse_alert_geometry(geometry)
        if alert_shape is None:
            # Unparseable/invalid geometry — treat exactly like zone-only (can't quantify).
            results.append(HazardExposureResult(
                alert_id=alert_id, event=event, severity=severity,
                exposure_miles=0.0, exposure_minutes=0,
                exposure_method="zone_only_uncertain",
                entry_mile=None, temporally_relevant=True, scaled_penalty=0.0, weight=weight,
            ))
            continue

        runs = compute_segment_exposure(coords_latlon, cumulative, route_line, alert_shape)
        if not runs:
            continue  # genuinely does not intersect this route — not a hazard for it

        total_miles = sum(r.miles for r in runs)
        entry_mile = min(r.entry_mile for r in runs)
        exit_mile = max(r.exit_mile for r in runs)
        entry_min = eta_minutes_fn(entry_mile)
        exit_min = eta_minutes_fn(exit_mile)
        relevant = temporal_relevance(entry_min, exit_min, alert.get("onset_minutes"), alert.get("expires_minutes"))

        penalty = scaled_exposure_penalty(total_miles, weight) if relevant else 0.0
        exposure_minutes = max(0, int(round(exit_min - entry_min))) if (exit_min is not None and entry_min is not None) else 0

        results.append(HazardExposureResult(
            alert_id=alert_id, event=event, severity=severity,
            exposure_miles=round(total_miles, 2), exposure_minutes=exposure_minutes,
            exposure_method="polygon_intersection",
            entry_mile=round(entry_mile, 2), temporally_relevant=relevant,
            scaled_penalty=penalty, weight=weight, runs=tuple(runs),
        ))

    return results


def classify_shared_unique_exposure(
    route_hazards_by_index: Dict[int, List[HazardExposureResult]],
) -> Dict[int, Tuple[float, int, float, int]]:
    """Returns {route_index: (shared_miles, shared_minutes, unique_miles, unique_minutes)}.
    An alert is 'shared' if its id has real polygon-based exposure in EVERY evaluated route;
    otherwise it's 'unique' (avoidable by switching routes). Each route's OWN real exposure
    numbers are used for its own totals — never blended/averaged across routes — so a shared
    alert with very different exposure per route (e.g. one route clips a corner, another
    drives through the center of the same polygon) is still faithfully reflected in each
    route's own shared total, not collapsed into a single hidden number."""
    if not route_hazards_by_index:
        return {}
    ids_per_route = {
        idx: {h.alert_id for h in hazards if h.exposure_method == "polygon_intersection"}
        for idx, hazards in route_hazards_by_index.items()
    }
    common_ids = set.intersection(*ids_per_route.values()) if ids_per_route else set()

    result: Dict[int, Tuple[float, int, float, int]] = {}
    for idx, hazards in route_hazards_by_index.items():
        shared_miles = shared_minutes = unique_miles = unique_minutes = 0.0
        for h in hazards:
            if h.exposure_method != "polygon_intersection":
                continue
            if h.alert_id in common_ids:
                shared_miles += h.exposure_miles
                shared_minutes += h.exposure_minutes
            else:
                unique_miles += h.exposure_miles
                unique_minutes += h.exposure_minutes
        result[idx] = (round(shared_miles, 2), int(shared_minutes), round(unique_miles, 2), int(unique_minutes))
    return result


def exposure_delta_vs_primary(
    primary_hazards: List[HazardExposureResult],
    candidate_hazards: List[HazardExposureResult],
) -> float:
    """Severity-weighted exposure-miles the candidate avoids (positive) or adds (negative)
    relative to the primary, across EVERY alert either might cross — whether 'shared' by id
    or not. A route that merely clips a shared polygon's corner while the primary drives
    through its center is correctly credited for the difference, never hidden just because
    the alert ID matches on both routes (this is the fix for 'shared hazard classification
    must not hide meaningful differences in exposure within the same warning polygon')."""
    primary_by_id = {
        h.alert_id: h for h in primary_hazards
        if h.exposure_method == "polygon_intersection" and h.temporally_relevant
    }
    candidate_by_id = {
        h.alert_id: h for h in candidate_hazards
        if h.exposure_method == "polygon_intersection" and h.temporally_relevant
    }
    all_ids = set(primary_by_id) | set(candidate_by_id)
    delta = 0.0
    for alert_id in all_ids:
        p = primary_by_id.get(alert_id)
        c = candidate_by_id.get(alert_id)
        weight = p.weight if p else (c.weight if c else 1.0)
        p_miles = p.exposure_miles if p else 0.0
        c_miles = c.exposure_miles if c else 0.0
        delta += weight * (p_miles - c_miles)
    return delta


# ─────────────────────────────────────────────────────────────────────────────────
# Ambient weather exposure (general forecast conditions along a route: precipitation
# wording, wind, temperature) — a NEW, Smart-Weather-Rerouting-only calculation that
# does NOT touch the always-on calculate_safety_score() in server.py. That legacy
# function applies a flat per-sample-point penalty for ANY rain/storm mention with no
# distance-awareness or deduplication, so a single ordinary "Chance Showers And
# Thunderstorms" forecast persisting across 7-8 sample points (very common) adds up to
# 105-120 points and saturates every route to 0, destroying any ability to compare.
#
# This calculation instead: (1) allocates each sample point a real mile-share of the
# route (the midpoint-to-midpoint span to its neighbors — an honest, explicit
# approximation given weather is only known at discrete sampled points, never treated
# as more precise than that), (2) classifies conditions into an escalating severity
# ladder that distinguishes ordinary "chance/isolated/scattered" mentions from
# unqualified or explicitly severe ones, and (3) applies the SAME concave,
# never-flat-capped scaled_exposure_penalty() already used for NWS alert polygons, so
# an ordinary shower over the whole route scores a small, honest penalty instead of a
# saturating one, while genuinely severe/extensive conditions still score much worse.
# ─────────────────────────────────────────────────────────────────────────────────

# Precipitation/visibility text tiers — checked in this order (most specific/severe
# first); NOT exhaustive or authoritative, a heuristic over NWS shortForecast wording.
_PRECIP_DANGEROUS_PHRASES = (
    "severe thunderstorm", "tornado", "blizzard", "ice storm", "freezing rain",
    "dense fog", "zero visibility",
)
_PRECIP_ORDINARY_QUALIFIERS = ("chance", "isolated", "slight chance", "scattered")
_PRECIP_ORDINARY_KEYWORDS = ("shower", "rain", "thunderstorm", "snow", "flurries")
_PRECIP_MODERATE_PHRASES = ("thunderstorm", "heavy rain", "heavy snow", "snow", "fog")
_PRECIP_MILD_PHRASES = ("rain", "shower", "drizzle")

PRECIP_TIER_DANGEROUS = 4.0
PRECIP_TIER_MODERATE = 2.0
PRECIP_TIER_MILD = 1.0
PRECIP_TIER_ORDINARY = 0.5

WIND_TIER_EXTREME = 3.0
WIND_TIER_HIGH = 1.5
WIND_TIER_ELEVATED = 0.5
WIND_EXTREME_MPH = 41
WIND_HIGH_MPH = 30
WIND_ELEVATED_MPH = 20

TEMP_TIER_FREEZING = 3.0
TEMP_TIER_NEAR_FREEZING = 0.75
TEMP_FREEZING_F = 32
TEMP_NEAR_FREEZING_F = 40

# A hazard-exposure weight at/above this is treated as "dangerous" for the purpose of
# suppressing a double-counted ambient precipitation-text penalty (see
# compute_ambient_weather_exposure's alert_covered_ranges parameter).
ALERT_DANGEROUS_WEIGHT_THRESHOLD = 3.0


@dataclass(frozen=True)
class AmbientWeatherResult:
    raw_penalty: float                       # unclamped — same scale as hazard scaled_penalty
    factors: Tuple[str, ...] = ()            # human-readable, deduplicated
    category_exposures: Dict[str, float] = field(default_factory=dict)  # "category:label" -> miles
    has_dangerous_tier: bool = False         # a sample hit the dangerous precip tier, unsuppressed


def _classify_precip_tier(conditions: Optional[str]) -> Tuple[float, str]:
    c = (conditions or "").lower()
    if not c:
        return 0.0, ""
    if any(p in c for p in _PRECIP_DANGEROUS_PHRASES):
        return PRECIP_TIER_DANGEROUS, "Severe/dangerous conditions"
    if any(q in c for q in _PRECIP_ORDINARY_QUALIFIERS) and any(k in c for k in _PRECIP_ORDINARY_KEYWORDS):
        return PRECIP_TIER_ORDINARY, "Scattered/chance precipitation"
    if any(p in c for p in _PRECIP_MODERATE_PHRASES):
        return PRECIP_TIER_MODERATE, "Steady precipitation or reduced visibility"
    if any(p in c for p in _PRECIP_MILD_PHRASES):
        return PRECIP_TIER_MILD, "Rain"
    return 0.0, ""


def _parse_wind_mph(wind_speed: Optional[str]) -> Optional[float]:
    if not wind_speed:
        return None
    try:
        digits = "".join(filter(str.isdigit, wind_speed.split()[0]))
        return float(digits) if digits else None
    except Exception:
        return None


def _classify_wind_tier(wind_speed: Optional[str]) -> Tuple[float, str]:
    mph = _parse_wind_mph(wind_speed)
    if mph is None:
        return 0.0, ""
    if mph > WIND_EXTREME_MPH:
        return WIND_TIER_EXTREME, "Extreme winds"
    if mph > WIND_HIGH_MPH:
        return WIND_TIER_HIGH, "High winds"
    if mph > WIND_ELEVATED_MPH:
        return WIND_TIER_ELEVATED, "Elevated winds"
    return 0.0, ""


def _classify_temp_tier(temp_f: Optional[float]) -> Tuple[float, str]:
    if temp_f is None:
        return 0.0, ""
    if temp_f < TEMP_FREEZING_F:
        return TEMP_TIER_FREEZING, "Freezing temperatures - ice risk"
    if temp_f < TEMP_NEAR_FREEZING_F:
        return TEMP_TIER_NEAR_FREEZING, "Near-freezing temperatures"
    return 0.0, ""


def _allocate_mile_spans(sorted_miles: List[float], total_distance_miles: float) -> List[Tuple[float, float]]:
    """Midpoint-to-midpoint partition of the route among sample points — an explicit,
    honest approximation (weather is only known AT the sampled points, never treated as
    more precise than that), not a claim of continuous coverage between them."""
    n = len(sorted_miles)
    spans = []
    for i in range(n):
        start = 0.0 if i == 0 else (sorted_miles[i - 1] + sorted_miles[i]) / 2.0
        end = total_distance_miles if i == n - 1 else (sorted_miles[i] + sorted_miles[i + 1]) / 2.0
        spans.append((start, end))
    return spans


def compute_ambient_weather_exposure(
    samples: List[Dict[str, Any]],
    total_distance_miles: float,
    alert_covered_ranges: Optional[List[Tuple[float, float]]] = None,
    wind_sensitivity: float = 1.0,
    ice_sensitivity: float = 1.0,
    visibility_sensitivity: float = 1.0,
) -> AmbientWeatherResult:
    """Each sample: {"mile": float, "temp": Optional[float], "wind_speed": Optional[str],
    "conditions": Optional[str], "missing": bool}. A missing sample contributes NOTHING
    (never treated as clear/good conditions) — the caller's existing uncertain-flagging
    stays the authority on whether the whole route can be trusted.

    alert_covered_ranges: real mile-ranges already scored by the NWS alert-polygon
    exposure system (compute_hazard_exposure_for_route) for a DANGEROUS event. A sample
    landing in one of these ranges has its dangerous-tier precipitation-text penalty
    suppressed, so the same real event is never counted by both systems — wind/temp
    tiers are left untouched since they measure independent physical signals (general
    forecast wind/temperature), not the same alert-classified hazard."""
    if not samples or total_distance_miles <= 0:
        return AmbientWeatherResult(raw_penalty=0.0)

    sorted_samples = sorted(samples, key=lambda s: s.get("mile", 0.0))
    sorted_miles = [s.get("mile", 0.0) for s in sorted_samples]
    spans = _allocate_mile_spans(sorted_miles, total_distance_miles)
    alert_covered_ranges = alert_covered_ranges or []

    precip_miles: Dict[float, float] = {}
    precip_labels: Dict[float, str] = {}
    wind_miles: Dict[float, float] = {}
    wind_labels: Dict[float, str] = {}
    temp_miles: Dict[float, float] = {}
    temp_labels: Dict[float, str] = {}
    has_dangerous_tier = False

    for sample, (start, end) in zip(sorted_samples, spans):
        if sample.get("missing"):
            continue
        span_miles = max(0.0, end - start)
        if span_miles <= 0:
            continue
        mid = (start + end) / 2.0
        covered_by_dangerous_alert = any(r0 <= mid <= r1 for r0, r1 in alert_covered_ranges)

        precip_weight, precip_label = _classify_precip_tier(sample.get("conditions"))
        if precip_weight >= PRECIP_TIER_DANGEROUS:
            if covered_by_dangerous_alert:
                precip_weight, precip_label = 0.0, ""
            else:
                has_dangerous_tier = True
        if precip_weight > 0:
            scaled_weight = precip_weight * visibility_sensitivity
            precip_miles[scaled_weight] = precip_miles.get(scaled_weight, 0.0) + span_miles
            precip_labels[scaled_weight] = precip_label

        wind_weight, wind_label = _classify_wind_tier(sample.get("wind_speed"))
        if wind_weight > 0:
            scaled_weight = wind_weight * wind_sensitivity
            wind_miles[scaled_weight] = wind_miles.get(scaled_weight, 0.0) + span_miles
            wind_labels[scaled_weight] = wind_label

        temp_weight, temp_label = _classify_temp_tier(sample.get("temp"))
        if temp_weight > 0:
            scaled_weight = temp_weight * ice_sensitivity
            temp_miles[scaled_weight] = temp_miles.get(scaled_weight, 0.0) + span_miles
            temp_labels[scaled_weight] = temp_label

    total_penalty = 0.0
    factors: List[str] = []
    category_exposures: Dict[str, float] = {}
    for miles_by_weight, labels_by_weight, category in (
        (precip_miles, precip_labels, "precipitation"),
        (wind_miles, wind_labels, "wind"),
        (temp_miles, temp_labels, "temperature"),
    ):
        for weight, miles in miles_by_weight.items():
            if miles <= 0:
                continue
            total_penalty += scaled_exposure_penalty(miles, weight)
            label = labels_by_weight[weight]
            factors.append(f"{label} ({miles:.0f} mi)")
            category_exposures[f"{category}:{label}"] = round(miles, 1)

    return AmbientWeatherResult(
        raw_penalty=round(total_penalty, 2),
        factors=tuple(factors),
        category_exposures=category_exposures,
        has_dangerous_tier=has_dangerous_tier,
    )

