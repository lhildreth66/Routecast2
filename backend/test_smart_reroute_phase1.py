"""Smart Weather Rerouting Phase 1 tests: per-route risk evaluation + comparative recommendation.

Group A tests `select_weather_reroute` in isolation (pure function over pre-built
RouteWeatherRisk objects), so the recommendation/gating rules can be verified
deterministically without simulating weather data or async evaluation.

Group B tests `evaluate_route_weather_risk` itself by stubbing the underlying
NOAA weather/alerts/bridge-clearance calls, covering dynamic sampling bounds,
ETA-aware forecast selection, timeouts, and vehicle-restriction gating.
"""
import datetime as dt

import polyline
import pytest

import server
from server import (
    HourlyForecast,
    RouteWeatherRisk,
    WeatherAlert,
    WeatherData,
    evaluate_route_weather_risk,
    select_weather_reroute,
)


def _make_geometry(num_points: int = 20, span_degrees: float = 2.0) -> str:
    coords = [(40.0 + i * (span_degrees / num_points), -100.0) for i in range(num_points)]
    return polyline.encode(coords, precision=6)


def _primary(risk_score: int = 40, risk_level: str = "high") -> RouteWeatherRisk:
    return RouteWeatherRisk(
        route_index=0,
        distance_miles=100.0,
        duration_minutes=120,
        risk_score=risk_score,
        risk_level=risk_level,
        summary="primary route summary",
    )


def _risk(index: int, risk_score: int, **kwargs) -> RouteWeatherRisk:
    return RouteWeatherRisk(route_index=index, distance_miles=110.0, duration_minutes=130, risk_score=risk_score, risk_level="low", summary="x", **kwargs)


# ---------------- GROUP A: select_weather_reroute ---------------- #

def test_no_alternatives_returns_no_safer_route_message():
    primary = _primary(risk_score=80, risk_level="low")
    result = select_weather_reroute([primary])

    assert result.routes == [primary]
    assert result.recommended_route_index is None
    assert result.reroute_recommended is False
    assert result.message == "No safer alternate route found."
    assert result.uncertain is False


def test_meaningful_improvement_is_recommended():
    primary = _primary(risk_score=40, risk_level="high")
    alt = _risk(1, 90)

    result = select_weather_reroute([primary, alt])

    assert result.recommended_route_index == 1
    assert result.reroute_recommended is True
    assert "+50" in result.message
    assert result.uncertain is False


def test_marginal_improvement_is_not_recommended():
    primary = _primary(risk_score=70, risk_level="moderate")
    alt = _risk(1, 80)  # only +10; below ALT_ROUTE_MIN_RISK_IMPROVEMENT (15)

    result = select_weather_reroute([primary, alt])

    assert result.recommended_route_index is None
    assert result.reroute_recommended is False
    assert result.message == "No safer alternate route found."


def test_worse_alternate_is_not_recommended():
    primary = _primary(risk_score=80, risk_level="low")
    alt = _risk(1, 30)

    result = select_weather_reroute([primary, alt])

    assert result.recommended_route_index is None
    assert result.reroute_recommended is False


def test_uncertain_alternate_is_never_declared_safer():
    primary = _primary(risk_score=40, risk_level="high")
    alt = _risk(1, 95, uncertain=True, uncertainty_reason="incomplete data")

    result = select_weather_reroute([primary, alt])

    assert result.recommended_route_index is None
    assert result.reroute_recommended is False
    # The only alternate couldn't be reliably evaluated — this is "insufficient evidence",
    # distinct from "confidently evaluated, none were better".
    assert result.comparison_outcome == "insufficient_evidence"
    assert result.message == "Insufficient weather data to reliably compare alternate routes."
    assert result.uncertain is True


def test_unchecked_vehicle_restriction_blocks_recommendation():
    primary = _primary(risk_score=40, risk_level="high")
    alt = _risk(1, 95, vehicle_restriction_checked=False)

    result = select_weather_reroute([primary, alt])

    assert result.recommended_route_index is None
    assert result.reroute_recommended is False


def test_blocked_vehicle_restriction_disqualifies_route():
    primary = _primary(risk_score=40, risk_level="high")
    alt = _risk(1, 95, vehicle_restriction_checked=True, vehicle_restriction_blocked=True)

    result = select_weather_reroute([primary, alt])

    assert result.recommended_route_index is None
    assert result.reroute_recommended is False


def test_best_of_two_alternates_is_chosen():
    primary = _primary(risk_score=30, risk_level="extreme")
    alt1 = _risk(1, 70)
    alt2 = _risk(2, 95)

    result = select_weather_reroute([primary, alt1, alt2])

    assert result.recommended_route_index == 2
    assert result.reroute_recommended is True
    assert len(result.routes) == 3


def test_empty_routes_list_returns_default_assessment():
    result = select_weather_reroute([])
    assert result.recommended_route_index is None
    assert result.reroute_recommended is False
    assert result.message == "No safer alternate route found."


# ---------------- GROUP B: evaluate_route_weather_risk ---------------- #

def _clear_weather_fns(monkeypatch, hourly_forecast=None):
    async def fake_weather(lat, lon):
        return WeatherData(temperature=70, wind_speed="5 mph", conditions="Clear", humidity=40, hourly_forecast=hourly_forecast or [])

    async def fake_alerts(lat, lon):
        return [], "ok"

    monkeypatch.setattr(server, "get_noaa_weather", fake_weather)
    monkeypatch.setattr(server, "get_noaa_alerts", fake_alerts)


@pytest.mark.asyncio
async def test_empty_geometry_is_uncertain():
    result = await evaluate_route_weather_risk(1, "", 50.0, 60, dt.datetime.utcnow(), "car", False, None)

    assert result.uncertain is True
    assert result.route_index == 1


@pytest.mark.asyncio
async def test_clear_weather_yields_low_risk_score(monkeypatch):
    geometry = _make_geometry()

    async def fake_weather(lat, lon):
        return WeatherData(temperature=70, wind_speed="5 mph", conditions="Clear", humidity=40)

    async def fake_alerts(lat, lon):
        return [], "ok"

    monkeypatch.setattr(server, "get_noaa_weather", fake_weather)
    monkeypatch.setattr(server, "get_noaa_alerts", fake_alerts)

    result = await evaluate_route_weather_risk(1, geometry, 120.0, 150, dt.datetime.utcnow(), "car", False, None)

    assert result.uncertain is False
    assert result.risk_score >= 80
    assert result.risk_level == "low"


@pytest.mark.asyncio
async def test_severe_weather_yields_high_risk_and_severe_flag(monkeypatch):
    geometry = _make_geometry()

    async def fake_weather(lat, lon):
        return WeatherData(temperature=15, wind_speed="50 mph", conditions="Blizzard", humidity=80)

    async def fake_alerts(lat, lon):
        return [
            WeatherAlert(id="a1", headline="Winter Storm Warning", severity="Severe", event="Winter Storm Warning", description="desc"),
        ], "ok"

    monkeypatch.setattr(server, "get_noaa_weather", fake_weather)
    monkeypatch.setattr(server, "get_noaa_alerts", fake_alerts)

    result = await evaluate_route_weather_risk(1, geometry, 120.0, 150, dt.datetime.utcnow(), "car", False, None)

    assert result.uncertain is False
    assert result.severe_weather is True
    assert result.risk_score < 50
    assert result.hazard_count >= 1


@pytest.mark.asyncio
async def test_alert_fetch_failure_marks_uncertain(monkeypatch):
    geometry = _make_geometry()

    async def fake_weather(lat, lon):
        return WeatherData(temperature=70, wind_speed="5 mph", conditions="Clear", humidity=40)

    async def fake_alerts(lat, lon):
        return [], "timeout"

    monkeypatch.setattr(server, "get_noaa_weather", fake_weather)
    monkeypatch.setattr(server, "get_noaa_alerts", fake_alerts)

    result = await evaluate_route_weather_risk(1, geometry, 120.0, 150, dt.datetime.utcnow(), "car", False, None)

    assert result.uncertain is True
    assert result.uncertainty_reason


@pytest.mark.asyncio
async def test_missing_weather_data_cannot_produce_perfect_score_or_confident_recommendation(monkeypatch):
    """Regression test: NWS can return a clean 'ok' alerts fetch with no usable weather (e.g. a
    points lookup missing forecastHourly). That must never be scored as if conditions were
    confirmed calm, and must never be good enough to recommend the route as a safer alternate."""
    geometry = _make_geometry()

    async def missing_weather(lat, lon):
        return None  # NWS succeeded but had no usable forecast for this point

    async def clean_alerts(lat, lon):
        return [], "ok"  # alerts fetch itself succeeded fine

    monkeypatch.setattr(server, "get_noaa_weather", missing_weather)
    monkeypatch.setattr(server, "get_noaa_alerts", clean_alerts)

    result = await evaluate_route_weather_risk(1, geometry, 120.0, 150, dt.datetime.utcnow(), "car", False, None)

    # calculate_safety_score would otherwise default to a perfect 100 when every waypoint's
    # weather is None (it simply skips them) — uncertain must catch that before it looks "safe".
    assert result.risk_score == 100
    assert result.uncertain is True
    assert result.uncertainty_reason

    # And critically: select_weather_reroute must never let that apparent perfect score win.
    primary = RouteWeatherRisk(route_index=0, distance_miles=100.0, duration_minutes=120, risk_score=40, risk_level="high", summary="risky primary")
    assessment = select_weather_reroute([primary, result])
    assert assessment.recommended_route_index is None
    assert assessment.reroute_recommended is False
    assert assessment.comparison_outcome == "insufficient_evidence"
    assert assessment.uncertain is True


@pytest.mark.asyncio
async def test_partial_missing_weather_among_otherwise_clear_points_still_marks_uncertain(monkeypatch):
    """Even a single missing-weather waypoint among otherwise-successful ones must not be
    smoothed over — the whole route stays uncertain rather than silently averaging it away."""
    geometry = _make_geometry(num_points=6, span_degrees=1.0)
    call_count = {"n": 0}

    async def mostly_clear_weather(lat, lon):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return None  # first point has no usable forecast
        return WeatherData(temperature=70, wind_speed="5 mph", conditions="Clear", humidity=40)

    async def clean_alerts(lat, lon):
        return [], "ok"

    monkeypatch.setattr(server, "get_noaa_weather", mostly_clear_weather)
    monkeypatch.setattr(server, "get_noaa_alerts", clean_alerts)

    result = await evaluate_route_weather_risk(1, geometry, 120.0, 150, dt.datetime.utcnow(), "car", False, None)

    assert result.uncertain is True


@pytest.mark.asyncio
async def test_bridge_check_failure_marks_uncertain_and_unchecked(monkeypatch):
    geometry = _make_geometry()
    _clear_weather_fns(monkeypatch)

    async def failing_bridge_check(geom, height):
        raise RuntimeError("overpass down")

    monkeypatch.setattr(server, "_get_bridge_clearances", failing_bridge_check)

    result = await evaluate_route_weather_risk(1, geometry, 120.0, 150, dt.datetime.utcnow(), "truck", True, 13.5)

    assert result.vehicle_restriction_checked is False
    assert result.uncertain is True


@pytest.mark.asyncio
async def test_bridge_check_reporting_failure_status_marks_uncertain_even_without_raising(monkeypatch):
    """The real bug this guards against: an internally swallowed Overpass outage/decode error
    returns normally (does not raise, does not time out) but with succeeded=False. This must
    NEVER be interpreted as a confirmed 'checked, zero restrictions found' result."""
    geometry = _make_geometry()
    _clear_weather_fns(monkeypatch)

    async def swallowed_failure_bridge_check(geom, height):
        return [], False  # fast, no exception, no timeout — but genuinely failed internally

    monkeypatch.setattr(server, "_get_bridge_clearances", swallowed_failure_bridge_check)

    result = await evaluate_route_weather_risk(1, geometry, 120.0, 150, dt.datetime.utcnow(), "truck", True, 13.5)

    assert result.vehicle_restriction_checked is False
    assert result.vehicle_restriction_blocked is False
    assert result.uncertain is True


@pytest.mark.asyncio
async def test_bridge_check_timeout_marks_uncertain_and_unchecked(monkeypatch):
    geometry = _make_geometry()
    _clear_weather_fns(monkeypatch)

    async def slow_bridge_check(geom, height):
        await server.asyncio.sleep(999)
        return [], True

    monkeypatch.setattr(server, "_get_bridge_clearances", slow_bridge_check)
    monkeypatch.setattr(server, "BRIDGE_CHECK_TRUST_SECONDS", 0.05)

    result = await evaluate_route_weather_risk(1, geometry, 120.0, 150, dt.datetime.utcnow(), "truck", True, 13.5)

    assert result.vehicle_restriction_checked is False
    assert result.uncertain is True


@pytest.mark.asyncio
async def test_bridge_conflict_blocks_route(monkeypatch):
    geometry = _make_geometry()
    _clear_weather_fns(monkeypatch)

    async def conflicting_bridge_check(geom, height):
        return [{"bridge_name": "Low Bridge", "margin_ft": -1.0}], True

    monkeypatch.setattr(server, "_get_bridge_clearances", conflicting_bridge_check)

    result = await evaluate_route_weather_risk(1, geometry, 120.0, 150, dt.datetime.utcnow(), "truck", True, 13.5)

    assert result.vehicle_restriction_checked is True
    assert result.vehicle_restriction_blocked is True


@pytest.mark.asyncio
async def test_bridge_check_success_with_no_conflicts_is_confirmed_suitable(monkeypatch):
    """A successful check that finds zero conflicts is a real, positive confirmation —
    distinct from a failed/skipped check, which must never be treated as 'suitable'."""
    geometry = _make_geometry()
    _clear_weather_fns(monkeypatch)

    async def clean_bridge_check(geom, height):
        return [], True

    monkeypatch.setattr(server, "_get_bridge_clearances", clean_bridge_check)

    result = await evaluate_route_weather_risk(1, geometry, 120.0, 150, dt.datetime.utcnow(), "truck", True, 13.5)

    assert result.vehicle_restriction_checked is True
    assert result.vehicle_restriction_blocked is False
    assert result.uncertain is False


# ---------------- known_bridge_alerts reuse optimization: must never bypass a restriction ---------------- #

@pytest.mark.asyncio
async def test_known_bridge_alerts_reuse_skips_redundant_overpass_call(monkeypatch):
    """When a confirmed-successful prior check is supplied, no new Overpass call is made."""
    geometry = _make_geometry()
    _clear_weather_fns(monkeypatch)
    call_count = {"n": 0}

    async def should_not_be_called(geom, height):
        call_count["n"] += 1
        return [], True

    monkeypatch.setattr(server, "_get_bridge_clearances", should_not_be_called)

    result = await evaluate_route_weather_risk(
        0, geometry, 120.0, 150, dt.datetime.utcnow(), "truck", True, 13.5,
        known_bridge_alerts=[],
    )

    assert call_count["n"] == 0
    assert result.vehicle_restriction_checked is True
    assert result.vehicle_restriction_blocked is False


@pytest.mark.asyncio
async def test_known_bridge_alerts_with_conflict_still_blocks_the_route(monkeypatch):
    """The reuse optimization must never let a real clearance conflict slip through."""
    geometry = _make_geometry()
    _clear_weather_fns(monkeypatch)

    async def should_not_be_called(geom, height):
        raise AssertionError("Overpass should not be called when a known result is supplied")

    monkeypatch.setattr(server, "_get_bridge_clearances", should_not_be_called)

    result = await evaluate_route_weather_risk(
        0, geometry, 120.0, 150, dt.datetime.utcnow(), "truck", True, 13.5,
        known_bridge_alerts=[{"bridge_name": "Low Bridge", "margin_ft": -2.0}],
    )

    assert result.vehicle_restriction_checked is True
    assert result.vehicle_restriction_blocked is True


@pytest.mark.asyncio
async def test_known_bridge_alerts_none_always_performs_a_fresh_independent_check(monkeypatch):
    """Every alternate route (and the primary, when no prior result exists) must always get its
    own real check — the optimization is opt-in per call, never a default skip."""
    geometry = _make_geometry()
    _clear_weather_fns(monkeypatch)
    call_count = {"n": 0}

    async def real_check(geom, height):
        call_count["n"] += 1
        return [], True

    monkeypatch.setattr(server, "_get_bridge_clearances", real_check)

    result = await evaluate_route_weather_risk(
        1, geometry, 120.0, 150, dt.datetime.utcnow(), "truck", True, 13.5,
        known_bridge_alerts=None,
    )

    assert call_count["n"] == 1
    assert result.vehicle_restriction_checked is True


@pytest.mark.asyncio
async def test_short_trip_samples_more_than_just_endpoints(monkeypatch):
    """A fixed 75-mile interval would only capture start/end on a short trip; the dynamic
    interval must still provide intermediate coverage."""
    geometry = _make_geometry(num_points=20, span_degrees=0.6)  # ~40 miles total
    sampled_lats = []

    async def fake_weather(lat, lon):
        sampled_lats.append(lat)
        return WeatherData(temperature=70, wind_speed="5 mph", conditions="Clear", humidity=40)

    async def fake_alerts(lat, lon):
        return [], "ok"

    monkeypatch.setattr(server, "get_noaa_weather", fake_weather)
    monkeypatch.setattr(server, "get_noaa_alerts", fake_alerts)

    await evaluate_route_weather_risk(1, geometry, 40.0, 50, dt.datetime.utcnow(), "car", False, None)

    assert len(sampled_lats) > 2


@pytest.mark.asyncio
async def test_long_trip_coverage_spans_full_distance_not_just_the_start(monkeypatch):
    """A fixed interval truncated to the sample cap would only cover the first N*interval miles
    of a long trip; samples must be spread across the FULL route instead."""
    geometry = _make_geometry(num_points=200, span_degrees=29.0)  # ~2000 miles
    sampled_distances = []

    async def fake_weather(lat, lon):
        return WeatherData(temperature=70, wind_speed="5 mph", conditions="Clear", humidity=40)

    async def fake_alerts(lat, lon):
        return [], "ok"

    monkeypatch.setattr(server, "get_noaa_weather", fake_weather)
    monkeypatch.setattr(server, "get_noaa_alerts", fake_alerts)

    original_extract = server.extract_waypoints_from_route

    def spying_extract(*args, **kwargs):
        wps = original_extract(*args, **kwargs)
        sampled_distances.extend(wp.distance_from_start or 0.0 for wp in wps)
        return wps

    monkeypatch.setattr(server, "extract_waypoints_from_route", spying_extract)

    # Realistic production allocation for a single ~2000mi route (see
    # weather_exposure.allocate_sample_budgets) instead of the old fixed 8-point default —
    # this test's purpose is verifying FULL-route coverage, not the new coverage-gap flag.
    budget = server.weather_exposure.allocate_sample_budgets([2000.0])[0]
    result = await evaluate_route_weather_risk(
        1, geometry, 2000.0, 1800, dt.datetime.utcnow(), "car", False, None, sample_budget=budget
    )

    # Even at the max per-route sample budget (30), a lone 2000mi route's anchor spacing
    # (~69mi) still exceeds the coverage-gap honesty threshold — this is the NEW, correct
    # behavior (point 2/4: more sampling must not manufacture an unsupported "safe" claim
    # for a trip this long), not a regression. The original intent of this test — that
    # sampling spans the FULL route rather than stopping after the first few hundred miles —
    # is still verified below.
    assert result.uncertain is True
    assert "coverage gap" in (result.uncertainty_reason or "").lower()
    # Coverage must reach near the end of the route, not stop after the first few hundred miles.
    assert max(sampled_distances) > 1500


@pytest.mark.asyncio
async def test_sampling_never_exceeds_max_points_regardless_of_distance(monkeypatch):
    geometry = _make_geometry(num_points=200, span_degrees=29.0)
    call_count = {"weather": 0}

    async def fake_weather(lat, lon):
        call_count["weather"] += 1
        return WeatherData(temperature=70, wind_speed="5 mph", conditions="Clear", humidity=40)

    async def fake_alerts(lat, lon):
        return [], "ok"

    monkeypatch.setattr(server, "get_noaa_weather", fake_weather)
    monkeypatch.setattr(server, "get_noaa_alerts", fake_alerts)

    await evaluate_route_weather_risk(1, geometry, 2000.0, 1800, dt.datetime.utcnow(), "car", False, None)

    assert call_count["weather"] <= server.ALT_ROUTE_MAX_SAMPLE_POINTS


@pytest.mark.asyncio
async def test_eta_aware_forecast_is_selected_over_current_conditions(monkeypatch):
    """A waypoint 3 hours out should be scored using the forecast period ~3 hours from now,
    not the immediate current-conditions snapshot."""
    now = dt.datetime.utcnow()
    hourly = [
        HourlyForecast(time=(now + dt.timedelta(hours=0)).isoformat(), temperature=70, conditions="Clear", wind_speed="5 mph"),
        HourlyForecast(time=(now + dt.timedelta(hours=3)).isoformat(), temperature=20, conditions="Blizzard", wind_speed="45 mph"),
    ]

    async def fake_weather(lat, lon):
        return WeatherData(temperature=70, wind_speed="5 mph", conditions="Clear", humidity=40, hourly_forecast=hourly)

    async def fake_alerts(lat, lon):
        return [], "ok"

    monkeypatch.setattr(server, "get_noaa_weather", fake_weather)
    monkeypatch.setattr(server, "get_noaa_alerts", fake_alerts)
    # Force a single sample point whose ETA lands ~3 hours out.
    monkeypatch.setattr(server, "extract_waypoints_from_route", lambda *a, **k: [
        server.Waypoint(lat=40.0, lon=-100.0, name="p", distance_from_start=150.0, eta_minutes=180, arrival_time=now.isoformat())
    ])

    geometry = _make_geometry(num_points=2, span_degrees=0.1)
    result = await evaluate_route_weather_risk(1, geometry, 150.0, 180, now, "car", False, None)

    assert result.eta_adjusted is True
    assert result.risk_score < 60  # scored against the blizzard period, not the clear "now" snapshot


@pytest.mark.asyncio
async def test_forecast_horizon_limited_when_eta_far_beyond_available_forecast(monkeypatch):
    now = dt.datetime.utcnow()
    hourly = [HourlyForecast(time=now.isoformat(), temperature=70, conditions="Clear", wind_speed="5 mph")]

    async def fake_weather(lat, lon):
        return WeatherData(temperature=70, wind_speed="5 mph", conditions="Clear", humidity=40, hourly_forecast=hourly)

    async def fake_alerts(lat, lon):
        return [], "ok"

    monkeypatch.setattr(server, "get_noaa_weather", fake_weather)
    monkeypatch.setattr(server, "get_noaa_alerts", fake_alerts)
    monkeypatch.setattr(server, "extract_waypoints_from_route", lambda *a, **k: [
        server.Waypoint(lat=40.0, lon=-100.0, name="p", distance_from_start=600.0, eta_minutes=600, arrival_time=now.isoformat())
    ])

    geometry = _make_geometry(num_points=2, span_degrees=0.1)
    result = await evaluate_route_weather_risk(1, geometry, 600.0, 600, now, "car", False, None)

    assert result.forecast_horizon_limited is True

