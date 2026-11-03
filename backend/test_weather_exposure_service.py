"""Tests for services/weather_exposure_service.py (Smart Weather Rerouting Phase 3).

Covers: geographic distance accuracy (the normalized-project() bug this module avoids),
narrow-polygon-between-vertices detection, MultiPolygon, polygons with holes, long-distance
exposure scaling (never flat-capped), zone-only/uncertain handling, temporal relevance, and
adaptive sample-budget allocation across realistic trip lengths and route counts.
"""
import math

import pytest

from services.weather_exposure_service import (
    HAZARD_EXPOSURE_EXPONENT,
    SAMPLE_MAX_PER_ROUTE,
    SAMPLE_MAX_TOTAL_PER_REQUEST,
    SAMPLE_MIN_PER_ROUTE,
    HazardExposureResult,
    _haversine_miles,
    allocate_sample_budgets,
    apply_confirmed_hazard_risk_level_floor,
    build_route_line,
    classify_shared_unique_exposure,
    compute_ambient_weather_exposure,
    compute_cumulative_miles,
    compute_hazard_exposure_for_route,
    compute_segment_exposure,
    coverage_gap_miles,
    exposure_delta_vs_primary,
    is_zone_only,
    parse_alert_geometry,
    scaled_exposure_penalty,
    severity_weight,
    temporal_relevance,
)


def _ns_route(lat_start=30.0, lon=-80.0, step=0.02, n=101):
    return [(lat_start + i * step, lon) for i in range(n)]


def _ew_route(lat, lon_start=-100.0, step=0.02, n=101):
    return [(lat, lon_start + i * step) for i in range(n)]


def _square(lon_c, lat_c, half_w=0.1):
    return {
        "type": "Polygon",
        "coordinates": [[
            [lon_c - half_w, lat_c - half_w], [lon_c + half_w, lat_c - half_w],
            [lon_c + half_w, lat_c + half_w], [lon_c - half_w, lat_c + half_w],
            [lon_c - half_w, lat_c - half_w],
        ]],
    }


# ---------------- Geographic distance accuracy (item 1) ---------------- #

def test_north_south_exposure_matches_real_haversine_distance():
    coords = _ns_route()
    cum = compute_cumulative_miles(coords)
    line = build_route_line(coords)
    poly = _square(-80.0, 31.0, half_w=0.1)
    shape = parse_alert_geometry(poly)
    runs = compute_segment_exposure(coords, cum, line, shape)
    total = sum(r.miles for r in runs)
    expected = _haversine_miles(30.9, -80.0, 31.1, -80.0)
    assert abs(total - expected) < 0.01


@pytest.mark.parametrize("lat", [10.0, 28.0, 48.0, 65.0])
def test_east_west_exposure_accurate_at_different_latitudes(lat):
    """The regression this guards against: naive normalized-project() over raw lon/lat
    degrees would return the SAME exposure regardless of latitude for an identical
    degree-width polygon, which is wrong — real miles-per-degree-of-longitude shrinks
    at higher latitude. Our computed exposure must track the real haversine distance,
    not the degree width, at every latitude."""
    coords = _ew_route(lat)
    cum = compute_cumulative_miles(coords)
    line = build_route_line(coords)
    poly = _square(-99.0, lat, half_w=0.1)
    shape = parse_alert_geometry(poly)
    runs = compute_segment_exposure(coords, cum, line, shape)
    total = sum(r.miles for r in runs)
    expected = _haversine_miles(lat, -99.1, lat, -98.9)
    assert abs(total - expected) < 0.01


def test_identical_degree_width_polygon_yields_different_miles_at_different_latitudes():
    """Directly proves latitude-dependent longitude compression is respected: the exact
    same 0.2-degree-wide polygon must expose FEWER real miles at a higher latitude."""
    def exposure_at(lat):
        coords = _ew_route(lat)
        cum = compute_cumulative_miles(coords)
        line = build_route_line(coords)
        shape = parse_alert_geometry(_square(-99.0, lat, half_w=0.1))
        return sum(r.miles for r in compute_segment_exposure(coords, cum, line, shape))

    low_lat_exposure = exposure_at(10.0)
    high_lat_exposure = exposure_at(60.0)
    assert high_lat_exposure < low_lat_exposure


def test_diagonal_route_mixing_ns_and_ew_segments_is_accurate():
    """A route that turns from north-south to east-west must still get the correct
    real-mile exposure for a polygon crossed on the east-west leg."""
    ns_leg = [(30.0 + i * 0.02, -80.0) for i in range(51)]
    ew_leg = [(31.0, -80.0 + i * 0.02) for i in range(1, 51)]
    coords = ns_leg + ew_leg
    cum = compute_cumulative_miles(coords)
    line = build_route_line(coords)
    poly = _square(-79.5, 31.0, half_w=0.1)  # sits on the east-west leg only
    shape = parse_alert_geometry(poly)
    runs = compute_segment_exposure(coords, cum, line, shape)
    total = sum(r.miles for r in runs)
    expected = _haversine_miles(31.0, -79.6, 31.0, -79.4)
    assert abs(total - expected) < 0.05


# ---------------- Narrow polygon between vertices (prior-round regression) ---------------- #

def test_narrow_polygon_crossed_between_widely_spaced_vertices_is_detected():
    coords = [(30.0, -80.0), (30.0, -79.85)]  # ~14.5mi segment, sparse vertices
    poly = {
        "type": "Polygon",
        "coordinates": [[[-79.93, 29.9], [-79.92, 29.9], [-79.92, 30.1], [-79.93, 30.1], [-79.93, 29.9]]],
    }
    cum = compute_cumulative_miles(coords)
    line = build_route_line(coords)
    shape = parse_alert_geometry(poly)
    runs = compute_segment_exposure(coords, cum, line, shape)
    assert len(runs) == 1
    assert runs[0].miles > 0


def test_polygon_entirely_between_vertices_does_not_touch_either_vertex():
    """Explicitly confirms neither endpoint of the crossed segment is itself inside
    the polygon — proving detection does not rely on vertex membership."""
    from shapely.geometry import Point
    coords = [(30.0, -80.0), (30.0, -79.85)]
    poly = {
        "type": "Polygon",
        "coordinates": [[[-79.93, 29.9], [-79.92, 29.9], [-79.92, 30.1], [-79.93, 30.1], [-79.93, 29.9]]],
    }
    shape = parse_alert_geometry(poly)
    assert not shape.contains(Point(-80.0, 30.0))
    assert not shape.contains(Point(-79.85, 30.0))
    cum = compute_cumulative_miles(coords)
    line = build_route_line(coords)
    runs = compute_segment_exposure(coords, cum, line, shape)
    assert len(runs) == 1


# ---------------- MultiPolygon / holes ---------------- #

def test_multipolygon_produces_separate_runs_for_each_disjoint_area():
    coords = _ns_route()
    cum = compute_cumulative_miles(coords)
    line = build_route_line(coords)
    multi = {
        "type": "MultiPolygon",
        "coordinates": [
            [[[-80.1, 30.2], [-79.9, 30.2], [-79.9, 30.3], [-80.1, 30.3], [-80.1, 30.2]]],
            [[[-80.1, 31.5], [-79.9, 31.5], [-79.9, 31.6], [-80.1, 31.6], [-80.1, 31.5]]],
        ],
    }
    shape = parse_alert_geometry(multi)
    runs = compute_segment_exposure(coords, cum, line, shape)
    assert len(runs) == 2


def test_polygon_with_hole_excludes_the_hole_from_exposure():
    coords = _ns_route()
    cum = compute_cumulative_miles(coords)
    line = build_route_line(coords)
    donut = {
        "type": "Polygon",
        "coordinates": [
            [[-80.2, 30.8], [-79.8, 30.8], [-79.8, 31.2], [-80.2, 31.2], [-80.2, 30.8]],
            [[-80.05, 30.95], [-79.95, 30.95], [-79.95, 31.05], [-80.05, 31.05], [-80.05, 30.95]],
        ],
    }
    shape = parse_alert_geometry(donut)
    runs = compute_segment_exposure(coords, cum, line, shape)
    # Route through the center must cross the ring twice (entry + exit) and skip the hole.
    assert len(runs) == 2
    gap_start = runs[0].exit_mile
    gap_end = runs[1].entry_mile
    assert gap_end > gap_start  # a real gap (the hole) between the two ring crossings


# ---------------- Long-distance exposure scaling (never flat-capped) ---------------- #

def test_100_miles_of_exposure_scores_strictly_worse_than_50_miles():
    weight = severity_weight("Severe", "Expected", "Winter Storm Warning")
    penalty_50 = scaled_exposure_penalty(50.0, weight)
    penalty_100 = scaled_exposure_penalty(100.0, weight)
    assert penalty_100 > penalty_50
    # Strictly increasing but sub-linear (concave) — not simply doubled.
    assert penalty_100 < penalty_50 * 2
    assert penalty_100 > penalty_50 * 1.5


def test_exposure_penalty_has_no_hard_cap():
    weight = 1.0
    penalties = [scaled_exposure_penalty(m, weight) for m in (50, 100, 200, 500)]
    assert penalties == sorted(penalties)
    assert len(set(penalties)) == len(penalties)  # strictly distinct, never flat


def test_zero_exposure_is_zero_penalty():
    assert scaled_exposure_penalty(0.0, 5.0) == 0.0


# ---------------- Zone-only alerts — never fabricate a distance ---------------- #

def test_zone_only_alert_detected():
    assert is_zone_only(None) is True
    assert is_zone_only({}) is True
    assert is_zone_only({"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]}) is False


def test_zone_only_alert_never_gets_a_fabricated_exposure_distance():
    coords = _ns_route()
    alerts = [{"id": "a1", "event": "Winter Weather Advisory", "severity": "Moderate", "geometry": None}]
    results = compute_hazard_exposure_for_route(coords, alerts, eta_minutes_fn=lambda m: m)
    assert len(results) == 1
    assert results[0].exposure_method == "zone_only_uncertain"
    assert results[0].exposure_miles == 0.0
    assert results[0].scaled_penalty == 0.0


def test_unparseable_geometry_treated_same_as_zone_only():
    coords = _ns_route()
    alerts = [{"id": "a2", "event": "Flood Watch", "severity": "Minor", "geometry": {"type": "Bogus"}}]
    results = compute_hazard_exposure_for_route(coords, alerts, eta_minutes_fn=lambda m: m)
    assert results[0].exposure_method == "zone_only_uncertain"
    assert results[0].exposure_miles == 0.0


def test_non_intersecting_real_polygon_produces_no_result():
    """A real polygon that the route never comes near should not appear at all —
    distinct from a zone-only/unparseable alert, which always appears as uncertain."""
    coords = _ns_route()
    far_away_poly = _square(40.0, 5.0, half_w=0.1)  # nowhere near the route
    alerts = [{"id": "a3", "event": "Dust Storm Warning", "severity": "Severe", "geometry": far_away_poly}]
    results = compute_hazard_exposure_for_route(coords, alerts, eta_minutes_fn=lambda m: m)
    assert results == []


# ---------------- Temporal relevance ---------------- #

def test_temporal_relevance_true_when_overlapping():
    assert temporal_relevance(entry_minutes=60, exit_minutes=90, onset_minutes=30, expires_minutes=120) is True


def test_temporal_relevance_false_when_alert_expires_before_route_arrives():
    assert temporal_relevance(entry_minutes=200, exit_minutes=220, onset_minutes=0, expires_minutes=100) is False


def test_temporal_relevance_false_when_alert_not_yet_active():
    assert temporal_relevance(entry_minutes=10, exit_minutes=20, onset_minutes=100, expires_minutes=200) is False


def test_temporal_relevance_defaults_true_when_timing_unknown():
    assert temporal_relevance(entry_minutes=10, exit_minutes=20, onset_minutes=None, expires_minutes=None) is True
    assert temporal_relevance(entry_minutes=None, exit_minutes=None, onset_minutes=0, expires_minutes=10) is True


def test_hazard_excluded_from_penalty_when_temporally_irrelevant():
    coords = _ns_route()
    poly = _square(-80.0, 31.0, half_w=0.1)
    alerts = [{
        "id": "a4", "event": "Flash Flood Warning", "severity": "Extreme", "geometry": poly,
        "onset_minutes": 0, "expires_minutes": 1,  # will have expired long before the route gets there
    }]
    results = compute_hazard_exposure_for_route(coords, alerts, eta_minutes_fn=lambda m: m * 2)
    assert len(results) == 1
    assert results[0].temporally_relevant is False
    assert results[0].scaled_penalty == 0.0
    assert results[0].exposure_miles > 0  # still measured/shown, just not scored


# ---------------- Severity weighting ---------------- #

def test_severity_weight_orders_extreme_above_severe_above_minor():
    extreme = severity_weight("Extreme", "Expected", "Flood Watch")
    severe = severity_weight("Severe", "Expected", "Flood Watch")
    minor = severity_weight("Minor", "Expected", "Flood Watch")
    assert extreme > severe > minor


def test_dangerous_event_multiplier_applied():
    base = severity_weight("Severe", "Expected", "Flood Watch")
    dangerous = severity_weight("Severe", "Expected", "Tornado Warning")
    assert dangerous > base


def test_unknown_severity_defaults_to_minimum_not_zero():
    assert severity_weight(None, None, None) > 0


# ---------------- Adaptive sample-budget allocation (item 2) ---------------- #

@pytest.mark.parametrize("distance", [100, 500, 1000, 2000])
def test_single_route_budget_never_below_floor_or_above_ceiling(distance):
    budget = allocate_sample_budgets([float(distance)])
    assert budget[0] >= SAMPLE_MIN_PER_ROUTE
    assert budget[0] <= SAMPLE_MAX_PER_ROUTE


@pytest.mark.parametrize("distance", [100, 500, 1000, 2000])
def test_four_route_budget_respects_total_request_ceiling(distance):
    budgets = allocate_sample_budgets([float(distance)] * 4)
    assert len(budgets) == 4
    assert sum(budgets) <= SAMPLE_MAX_TOTAL_PER_REQUEST
    assert all(b >= SAMPLE_MIN_PER_ROUTE for b in budgets)


def test_short_trips_get_full_adaptive_allocation_without_scaledown():
    """100mi and 500mi x4 routes are the common real-world case — both should fit
    under the total budget without any proportional scaledown."""
    for distance in (100.0, 500.0):
        budgets = allocate_sample_budgets([distance] * 4)
        raw_target = max(SAMPLE_MIN_PER_ROUTE, min(SAMPLE_MAX_PER_ROUTE, math.ceil(distance / 25.0)))
        assert budgets == [raw_target] * 4


def test_long_trips_trigger_proportional_scaledown_but_never_below_floor():
    budgets_1000 = allocate_sample_budgets([1000.0] * 4)
    budgets_2000 = allocate_sample_budgets([2000.0] * 4)
    assert sum(budgets_1000) <= SAMPLE_MAX_TOTAL_PER_REQUEST
    assert sum(budgets_2000) <= SAMPLE_MAX_TOTAL_PER_REQUEST
    assert all(b >= SAMPLE_MIN_PER_ROUTE for b in budgets_1000)
    assert all(b >= SAMPLE_MIN_PER_ROUTE for b in budgets_2000)


def test_budget_allocation_scales_proportionally_not_arbitrarily():
    """Two routes of very different lengths should not be allocated equally when
    scaledown is required — the longer route should still get more samples."""
    budgets = allocate_sample_budgets([2000.0, 100.0, 2000.0, 2000.0])
    assert budgets[1] < budgets[0]
    assert budgets[1] < budgets[2]


def test_empty_distance_list_returns_empty_budget():
    assert allocate_sample_budgets([]) == []


# ---------------- Coverage gap (item 2 / honesty — more sampling != proof of safety) ---------------- #

def test_coverage_gap_shrinks_as_points_increase():
    gap_sparse = coverage_gap_miles(1000.0, 8)
    gap_dense = coverage_gap_miles(1000.0, 24)
    assert gap_dense < gap_sparse


def test_coverage_gap_for_single_point_is_whole_distance():
    assert coverage_gap_miles(500.0, 1) == 500.0


@pytest.mark.parametrize("distance,num_points,expect_gap_over_30", [
    (100.0, 8, False),
    (500.0, 20, False),
    (1000.0, 24, True),   # realistic allocation for a long trip still exceeds the 30mi target
    (2000.0, 25, True),
])
def test_realistic_trip_coverage_gap_matches_expected_confidence_band(distance, num_points, expect_gap_over_30):
    gap = coverage_gap_miles(distance, num_points)
    assert (gap > 30.0) == expect_gap_over_30


# ---------------- End-to-end exposure orchestration ---------------- #

def test_compute_hazard_exposure_for_route_dedupes_by_alert_id_across_the_whole_route():
    """A single alert whose polygon spans many sample points must appear exactly once
    in the result, with its FULL exposure distance — never double-counted."""
    coords = _ns_route()
    poly = _square(-80.0, 31.0, half_w=0.3)  # wide hazard spanning several segments
    alerts = [{"id": "dup1", "event": "Severe Thunderstorm Warning", "severity": "Severe", "geometry": poly}]
    results = compute_hazard_exposure_for_route(coords, alerts, eta_minutes_fn=lambda m: m)
    assert len(results) == 1
    assert results[0].alert_id == "dup1"


def test_multiple_distinct_alerts_all_appear_independently():
    coords = _ns_route()
    poly_a = _square(-80.0, 30.3, half_w=0.05)
    poly_b = _square(-80.0, 31.5, half_w=0.05)
    alerts = [
        {"id": "x1", "event": "Wind Advisory", "severity": "Moderate", "geometry": poly_a},
        {"id": "x2", "event": "Winter Storm Warning", "severity": "Severe", "geometry": poly_b},
    ]
    results = compute_hazard_exposure_for_route(coords, alerts, eta_minutes_fn=lambda m: m)
    ids = {r.alert_id for r in results}
    assert ids == {"x1", "x2"}


# ---------------- Shared vs. route-specific hazards (item 5 / item 3-of-round-3) ---------------- #

def _mk(alert_id, miles, severity="Severe", weight=3.0, relevant=True):
    from services.weather_exposure_service import HazardExposureResult
    return HazardExposureResult(
        alert_id=alert_id, event="Severe Thunderstorm Warning", severity=severity,
        exposure_miles=miles, exposure_minutes=int(miles), exposure_method="polygon_intersection",
        entry_mile=10.0, temporally_relevant=relevant, scaled_penalty=1.0, weight=weight,
    )


def test_hazard_shared_by_every_route_is_classified_shared_not_unique():
    hazards_by_route = {
        0: [_mk("shared1", 20.0)],
        1: [_mk("shared1", 5.0)],
        2: [_mk("shared1", 40.0)],
    }
    result = classify_shared_unique_exposure(hazards_by_route)
    for idx, (shared_miles, _sm, unique_miles, _um) in result.items():
        assert unique_miles == 0.0
        assert shared_miles == hazards_by_route[idx][0].exposure_miles  # each route's OWN real miles


def test_hazard_unique_to_one_route_is_classified_unique():
    hazards_by_route = {
        0: [_mk("only_on_primary", 15.0)],
        1: [],
        2: [],
    }
    result = classify_shared_unique_exposure(hazards_by_route)
    assert result[0] == (0.0, 0, 15.0, 15)
    assert result[1] == (0.0, 0, 0.0, 0)


def test_shared_classification_preserves_each_routes_own_distinct_exposure_amount():
    """The exact concern raised: a shared alert must not be collapsed into one hidden
    number — route A clipping a corner (3mi) vs route B driving through the center
    (80mi) of the SAME polygon must both be preserved in each route's own shared total."""
    hazards_by_route = {
        0: [_mk("big_storm", 80.0)],
        1: [_mk("big_storm", 3.0)],
    }
    result = classify_shared_unique_exposure(hazards_by_route)
    assert result[0][0] == 80.0
    assert result[1][0] == 3.0
    assert result[0][0] != result[1][0]  # not hidden/averaged into equality


def test_exposure_delta_rewards_candidate_that_clips_less_of_the_same_shared_hazard():
    """Even though the alert ID is identical on both routes (i.e. 'shared'), the
    candidate crossing far less of it must register as a meaningful improvement."""
    primary = [_mk("big_storm", 80.0, weight=3.0)]
    candidate = [_mk("big_storm", 3.0, weight=3.0)]
    delta = exposure_delta_vs_primary(primary, candidate)
    assert delta > 0  # positive = candidate is better (less weighted exposure)


def test_exposure_delta_rewards_candidate_that_avoids_a_unique_hazard_entirely():
    primary = [_mk("tornado_path", 12.0, weight=6.0)]
    candidate = []
    delta = exposure_delta_vs_primary(primary, candidate)
    assert delta > 0


def test_exposure_delta_penalizes_candidate_that_adds_a_new_hazard():
    primary = []
    candidate = [_mk("new_hazard", 25.0, weight=3.0)]
    delta = exposure_delta_vs_primary(primary, candidate)
    assert delta < 0


def test_exposure_delta_ignores_temporally_irrelevant_hazards():
    primary = [_mk("expired_by_arrival", 50.0, relevant=False)]
    candidate = []
    delta = exposure_delta_vs_primary(primary, candidate)
    assert delta == 0.0


def test_exposure_delta_zero_when_routes_equally_exposed():
    primary = [_mk("same_everywhere", 10.0)]
    candidate = [_mk("same_everywhere", 10.0)]
    assert exposure_delta_vs_primary(primary, candidate) == 0.0


# ---------------- Ambient weather exposure (Phase 3 scoring fix) ---------------- #

def _ambient_samples(n, mile_span, conditions, temp=72, wind_speed="10 mph", missing=False):
    return [
        {
            "mile": i * (mile_span / max(1, n - 1)),
            "temp": temp,
            "wind_speed": wind_speed,
            "conditions": conditions,
            "missing": missing,
        }
        for i in range(n)
    ]


def test_seven_points_of_ordinary_scattered_thunderstorms_does_not_saturate():
    """The exact real-world regression this fix targets: the OLD calculate_safety_score
    applied 15 points PER sample point with no dedup (15*7=105, already over the 100-point
    scale). The new exposure-based calculation must produce a small, non-saturating penalty
    for an ordinary 'chance of showers' forecast persisting across the whole route."""
    samples = _ambient_samples(7, 107.2, "Chance Showers And Thunderstorms")
    result = compute_ambient_weather_exposure(samples, 107.2)
    assert result.raw_penalty < 10.0
    assert result.has_dangerous_tier is False


def test_eight_points_of_ordinary_scattered_thunderstorms_does_not_saturate():
    samples = _ambient_samples(8, 110.5, "Chance Showers And Thunderstorms")
    result = compute_ambient_weather_exposure(samples, 110.5)
    assert result.raw_penalty < 10.0


def test_genuinely_severe_weather_scores_far_worse_than_ordinary():
    ordinary = _ambient_samples(7, 107.2, "Chance Showers And Thunderstorms")
    severe = _ambient_samples(7, 107.2, "Severe Thunderstorms", temp=20, wind_speed="45 mph")

    ordinary_result = compute_ambient_weather_exposure(ordinary, 107.2)
    severe_result = compute_ambient_weather_exposure(severe, 107.2)

    assert severe_result.raw_penalty > ordinary_result.raw_penalty * 5
    assert severe_result.has_dangerous_tier is True
    assert ordinary_result.has_dangerous_tier is False


@pytest.mark.parametrize("dangerous_phrase", [
    "Severe Thunderstorms", "Tornado Warning in effect", "Blizzard conditions",
    "Ice Storm Warning", "Freezing Rain", "Dense Fog",
])
def test_dangerous_phrases_are_recognized(dangerous_phrase):
    samples = _ambient_samples(3, 30.0, dangerous_phrase)
    result = compute_ambient_weather_exposure(samples, 30.0)
    assert result.has_dangerous_tier is True


@pytest.mark.parametrize("ordinary_phrase", [
    "Chance Showers And Thunderstorms", "Isolated Thunderstorms", "Scattered Showers",
    "Slight Chance Of Rain",
])
def test_ordinary_qualified_phrases_are_not_dangerous(ordinary_phrase):
    samples = _ambient_samples(5, 50.0, ordinary_phrase)
    result = compute_ambient_weather_exposure(samples, 50.0)
    assert result.has_dangerous_tier is False
    assert result.raw_penalty < 5.0


def test_extreme_wind_and_freezing_temp_detected_independent_of_conditions_text():
    samples = _ambient_samples(5, 50.0, "Clear", temp=10, wind_speed="50 mph")
    result = compute_ambient_weather_exposure(samples, 50.0)
    assert any("Extreme winds" in f for f in result.factors)
    assert any("ice risk" in f for f in result.factors)


# ---------------- Exposure length/duration sensitivity ---------------- #

def test_longer_ambient_exposure_scores_strictly_worse_than_shorter():
    short = _ambient_samples(5, 50.0, "Thunderstorms")
    long_ = _ambient_samples(5, 100.0, "Thunderstorms")
    short_result = compute_ambient_weather_exposure(short, 50.0)
    long_result = compute_ambient_weather_exposure(long_, 100.0)
    assert long_result.raw_penalty > short_result.raw_penalty


def test_partial_route_exposure_scores_less_than_full_route_exposure():
    """Only some sample points show the hazardous condition — exposure miles (and
    therefore penalty) must be proportionally smaller than if it covered the whole route."""
    full_samples = _ambient_samples(10, 100.0, "Thunderstorms")
    partial_samples = [
        {"mile": i * 10.0, "temp": 72, "wind_speed": "10 mph",
         "conditions": "Thunderstorms" if i < 3 else "Clear", "missing": False}
        for i in range(10)
    ]
    full_result = compute_ambient_weather_exposure(full_samples, 100.0)
    partial_result = compute_ambient_weather_exposure(partial_samples, 100.0)
    assert partial_result.raw_penalty < full_result.raw_penalty


# ---------------- Missing/incomplete data never treated as clear ---------------- #

def test_missing_weather_samples_contribute_zero_not_clear():
    samples = [
        {"mile": 0.0, "temp": None, "wind_speed": None, "conditions": None, "missing": True},
        {"mile": 50.0, "temp": None, "wind_speed": None, "conditions": None, "missing": True},
        {"mile": 100.0, "temp": None, "wind_speed": None, "conditions": None, "missing": True},
    ]
    result = compute_ambient_weather_exposure(samples, 100.0)
    assert result.raw_penalty == 0.0
    assert result.factors == ()


def test_mix_of_missing_and_severe_samples_still_scores_the_known_severe_portion():
    samples = [
        {"mile": 0.0, "temp": None, "wind_speed": None, "conditions": None, "missing": True},
        {"mile": 50.0, "temp": 20, "wind_speed": "45 mph", "conditions": "Severe Thunderstorms", "missing": False},
        {"mile": 100.0, "temp": None, "wind_speed": None, "conditions": None, "missing": True},
    ]
    result = compute_ambient_weather_exposure(samples, 100.0)
    assert result.raw_penalty > 0.0
    assert result.has_dangerous_tier is True


# ---------------- Double-counting avoidance with the alert-polygon system ---------------- #

def test_dangerous_ambient_tier_suppressed_when_already_covered_by_a_real_alert():
    """A 'Severe Thunderstorms' forecast phrase at a point ALREADY covered by a real,
    temporally-relevant NWS severe-alert polygon must not be double-penalized by both
    systems — the ambient dangerous tier is suppressed there (wind/temp are untouched,
    since they're independent physical signals, not the same classified hazard)."""
    samples = _ambient_samples(5, 50.0, "Severe Thunderstorms")
    covered_result = compute_ambient_weather_exposure(samples, 50.0, alert_covered_ranges=[(0.0, 50.0)])
    uncovered_result = compute_ambient_weather_exposure(samples, 50.0, alert_covered_ranges=[])

    assert covered_result.has_dangerous_tier is False
    assert covered_result.raw_penalty < uncovered_result.raw_penalty


def test_partial_alert_coverage_only_suppresses_the_covered_portion():
    samples = _ambient_samples(10, 100.0, "Severe Thunderstorms")
    # Only the first half of the route is covered by a real alert polygon.
    result = compute_ambient_weather_exposure(samples, 100.0, alert_covered_ranges=[(0.0, 50.0)])
    assert result.has_dangerous_tier is True  # the UNcovered second half still registers
    assert result.raw_penalty > 0.0


# ---------------- Vehicle sensitivity multipliers ---------------- #

def test_higher_wind_sensitivity_increases_penalty():
    samples = _ambient_samples(5, 50.0, "Clear", wind_speed="35 mph")
    car_result = compute_ambient_weather_exposure(samples, 50.0, wind_sensitivity=1.0)
    semi_result = compute_ambient_weather_exposure(samples, 50.0, wind_sensitivity=1.8)
    assert semi_result.raw_penalty > car_result.raw_penalty


# ---------------- Empty/degenerate input ---------------- #

def test_empty_samples_returns_zero_penalty():
    result = compute_ambient_weather_exposure([], 100.0)
    assert result.raw_penalty == 0.0


def test_zero_distance_returns_zero_penalty():
    result = compute_ambient_weather_exposure(_ambient_samples(3, 0.0, "Severe Thunderstorms"), 0.0)
    assert result.raw_penalty == 0.0


# ---------------- Displayed risk-level floor (round-2 redesign fixes, item 6) ---------------- #

def _hazard(
    severity="Severe",
    exposure_miles=2.5,
    exposure_method="polygon_intersection",
    temporally_relevant=True,
) -> HazardExposureResult:
    return HazardExposureResult(
        alert_id="a1", event="Flood Warning", severity=severity,
        exposure_miles=exposure_miles, exposure_minutes=10,
        exposure_method=exposure_method, entry_mile=1.0 if exposure_method == "polygon_intersection" else None,
        temporally_relevant=temporally_relevant, scaled_penalty=0.9, weight=3.0,
    )


def test_confirmed_severe_exposure_floors_low_to_moderate():
    assert apply_confirmed_hazard_risk_level_floor("low", [_hazard(severity="Severe")]) == "moderate"


def test_confirmed_extreme_exposure_floors_low_to_high():
    assert apply_confirmed_hazard_risk_level_floor("low", [_hazard(severity="Extreme")]) == "high"


def test_floor_never_lowers_an_already_higher_computed_level():
    assert apply_confirmed_hazard_risk_level_floor("extreme", [_hazard(severity="Severe")]) == "extreme"
    assert apply_confirmed_hazard_risk_level_floor("high", [_hazard(severity="Severe")]) == "high"


def test_unknown_sentinel_is_never_touched_by_the_floor():
    """An unevaluated/uncertain route (risk_level == 'unknown') must never be silently
    promoted into the low/moderate/high/extreme numeric ladder, even alongside a confirmed
    severe hazard — its own uncertainty remains the more important, visible signal."""
    assert apply_confirmed_hazard_risk_level_floor("unknown", [_hazard(severity="Extreme")]) == "unknown"


def test_zone_only_uncertain_hazard_never_floors_the_level():
    """A geographic warning-zone overlap with no confirmed route intersection must never
    be treated as a confirmed dangerous roadway condition for this route."""
    hazard = _hazard(severity="Extreme", exposure_method="zone_only_uncertain", exposure_miles=0.0)
    assert apply_confirmed_hazard_risk_level_floor("low", [hazard]) == "low"


def test_temporally_irrelevant_hazard_never_floors_the_level():
    hazard = _hazard(severity="Extreme", temporally_relevant=False)
    assert apply_confirmed_hazard_risk_level_floor("low", [hazard]) == "low"


def test_zero_exposure_miles_never_floors_the_level():
    """Matched the alert's general area but never actually crossed its polygon along this
    specific path — must not be floored as if it had."""
    hazard = _hazard(severity="Extreme", exposure_miles=0.0)
    assert apply_confirmed_hazard_risk_level_floor("low", [hazard]) == "low"


def test_minor_or_moderate_severity_never_floors_the_level():
    assert apply_confirmed_hazard_risk_level_floor("low", [_hazard(severity="Moderate")]) == "low"
    assert apply_confirmed_hazard_risk_level_floor("low", [_hazard(severity="Minor")]) == "low"


def test_no_hazards_never_floors_the_level():
    assert apply_confirmed_hazard_risk_level_floor("low", []) == "low"


def test_realistic_calibration_bug_is_fixed_end_to_end():
    """Reproduces the exact reported bug: 2.5 miles of confirmed Flood Warning exposure,
    which the raw scaled_exposure_penalty formula alone scores as 'low' risk (~99/100)."""
    weight = severity_weight("Severe", "Expected", "Flood Warning")
    penalty = scaled_exposure_penalty(2.5, weight)
    raw_score = max(0, min(100, int(round(100 - penalty))))
    assert raw_score >= 80  # confirms the raw formula alone would say "low"
    hazard = _hazard(severity="Severe", exposure_miles=2.5)
    floored = apply_confirmed_hazard_risk_level_floor("low", [hazard])
    assert floored == "moderate"


