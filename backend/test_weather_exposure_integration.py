"""Smart Weather Rerouting Phase 3 integration tests: verifies real NWS alert polygon
geometry flows correctly end-to-end through evaluate_route_weather_risk/select_weather_reroute
(wiring tests) — complements the pure geometry/scoring unit tests in
test_weather_exposure_service.py (narrow polygons, MultiPolygons, holes, long-distance
scaling are already exhaustively unit-tested there at the service-function level).
"""
import datetime as dt

import polyline
import pytest

import server
from server import RouteWeatherRisk, WeatherAlert, WeatherData, evaluate_route_weather_risk, select_weather_reroute


def _ns_geometry(lat_start=30.0, lon=-80.0, span_degrees=1.5, n=60):
    coords = [(lat_start + i * (span_degrees / n), lon) for i in range(n)]
    return polyline.encode(coords, precision=6)


def _square(lon_c, lat_c, half_w):
    return {
        "type": "Polygon",
        "coordinates": [[
            [lon_c - half_w, lat_c - half_w], [lon_c + half_w, lat_c - half_w],
            [lon_c + half_w, lat_c + half_w], [lon_c - half_w, lat_c + half_w],
            [lon_c - half_w, lat_c - half_w],
        ]],
    }


def _clear_weather(monkeypatch):
    async def fake_weather(lat, lon):
        return WeatherData(temperature=70, wind_speed="5 mph", conditions="Clear", humidity=40)

    monkeypatch.setattr(server, "get_noaa_weather", fake_weather)
    return fake_weather


# ---------------- Narrow polygon / MultiPolygon / holes (wiring) ---------------- #

@pytest.mark.asyncio
async def test_narrow_polygon_between_vertices_reduces_risk_score_via_real_exposure(monkeypatch):
    """A narrow hazard polygon crossed between two route points (not landing on either sampled
    point) must still be detected via the full decoded polyline and reduce the risk score."""
    geometry = _ns_geometry()
    _clear_weather(monkeypatch)
    poly = _square(-80.0, 30.75, half_w=0.05)  # narrow band across the N-S route's midpoint

    async def fake_alerts(lat, lon):
        return [
            WeatherAlert(
                id="narrow1", headline="Severe Thunderstorm Warning", severity="Severe",
                event="Severe Thunderstorm Warning", description="desc", urgency="Immediate",
                geometry=poly,
            )
        ], "ok"

    monkeypatch.setattr(server, "get_noaa_alerts", fake_alerts)

    result = await evaluate_route_weather_risk(1, geometry, 103.6, 120, dt.datetime.utcnow(), "car", False, None)

    assert result.uncertain is False
    exposures = [h for h in result.hazard_exposures if h.exposure_method == "polygon_intersection"]
    assert len(exposures) == 1
    assert exposures[0].exposure_miles > 0
    assert result.risk_score < 100


@pytest.mark.asyncio
async def test_multipolygon_alert_exposure_sums_across_disjoint_areas(monkeypatch):
    geometry = _ns_geometry()
    _clear_weather(monkeypatch)
    multi = {
        "type": "MultiPolygon",
        "coordinates": [
            [[[-80.1, 30.2], [-79.9, 30.2], [-79.9, 30.3], [-80.1, 30.3], [-80.1, 30.2]]],
            [[[-80.1, 31.0], [-79.9, 31.0], [-79.9, 31.1], [-80.1, 31.1], [-80.1, 31.0]]],
        ],
    }

    async def fake_alerts(lat, lon):
        return [
            WeatherAlert(id="multi1", headline="Flood Warning", severity="Severe", event="Flood Warning",
                         description="desc", geometry=multi)
        ], "ok"

    monkeypatch.setattr(server, "get_noaa_alerts", fake_alerts)

    result = await evaluate_route_weather_risk(1, geometry, 103.6, 120, dt.datetime.utcnow(), "car", False, None)
    exposures = [h for h in result.hazard_exposures if h.alert_id == "multi1"]
    assert len(exposures) == 1
    assert exposures[0].exposure_miles > 10  # both disjoint bands contribute


@pytest.mark.asyncio
async def test_polygon_with_hole_route_through_center_excludes_hole(monkeypatch):
    geometry = _ns_geometry()
    _clear_weather(monkeypatch)
    donut = {
        "type": "Polygon",
        "coordinates": [
            [[-80.2, 30.6], [-79.8, 30.6], [-79.8, 30.9], [-80.2, 30.9], [-80.2, 30.6]],
            [[-80.05, 30.7], [-79.95, 30.7], [-79.95, 30.8], [-80.05, 30.8], [-80.05, 30.7]],
        ],
    }

    async def fake_alerts(lat, lon):
        return [
            WeatherAlert(id="donut1", headline="Winter Storm Warning", severity="Severe", event="Winter Storm Warning",
                         description="desc", geometry=donut)
        ], "ok"

    monkeypatch.setattr(server, "get_noaa_alerts", fake_alerts)

    result = await evaluate_route_weather_risk(1, geometry, 103.6, 120, dt.datetime.utcnow(), "car", False, None)
    exposures = [h for h in result.hazard_exposures if h.alert_id == "donut1"]
    assert len(exposures) == 1
    # Ring is ~0.2deg (outer) minus ~0.1deg (hole) thick in each half — total crossing miles
    # should be well under the full outer-boundary span (~0.3deg * ~69mi/deg ≈ 20.7mi), proving
    # the hole was excluded rather than treating the whole outer boundary as solid.
    assert 0 < exposures[0].exposure_miles < 20.0


# ---------------- Long-distance exposure never flat-capped (wiring) ---------------- #

@pytest.mark.asyncio
async def test_longer_hazard_exposure_scores_strictly_worse_than_shorter(monkeypatch):
    """100mi vs 50mi of the SAME severity hazard must not score equivalently."""
    geometry = _ns_geometry(span_degrees=3.0, n=120)  # ~207mi route
    _clear_weather(monkeypatch)

    def make_alerts(exposure_half_width_deg):
        poly = _square(-80.0, 31.5, half_w=exposure_half_width_deg)

        async def fake_alerts(lat, lon):
            return [
                WeatherAlert(id="longhaz", headline="Winter Storm Warning", severity="Severe",
                             event="Winter Storm Warning", description="desc", geometry=poly)
            ], "ok"
        return fake_alerts

    monkeypatch.setattr(server, "get_noaa_alerts", make_alerts(0.36))  # ~50mi band
    result_50 = await evaluate_route_weather_risk(1, geometry, 207.0, 240, dt.datetime.utcnow(), "car", False, None)

    monkeypatch.setattr(server, "get_noaa_alerts", make_alerts(0.72))  # ~100mi band
    result_100 = await evaluate_route_weather_risk(1, geometry, 207.0, 240, dt.datetime.utcnow(), "car", False, None)

    assert result_100.raw_risk_penalty > result_50.raw_risk_penalty
    assert result_100.risk_score <= result_50.risk_score


# ---------------- Incomplete weather data stays uncertain regardless of hazard presence ---------------- #

@pytest.mark.asyncio
async def test_incomplete_weather_data_marks_uncertain_even_with_real_hazard_present(monkeypatch):
    geometry = _ns_geometry()
    call_count = {"n": 0}

    async def flaky_weather(lat, lon):
        call_count["n"] += 1
        if call_count["n"] == 2:
            return None  # one point silently has no usable forecast
        return WeatherData(temperature=70, wind_speed="5 mph", conditions="Clear", humidity=40)

    poly = _square(-80.0, 30.75, half_w=0.05)

    async def fake_alerts(lat, lon):
        return [
            WeatherAlert(id="hz1", headline="Flood Watch", severity="Moderate", event="Flood Watch",
                         description="desc", geometry=poly)
        ], "ok"

    monkeypatch.setattr(server, "get_noaa_weather", flaky_weather)
    monkeypatch.setattr(server, "get_noaa_alerts", fake_alerts)

    result = await evaluate_route_weather_risk(1, geometry, 103.6, 120, dt.datetime.utcnow(), "car", False, None)

    assert result.uncertain is True
    assert result.uncertainty_reason
    # The real hazard exposure is still measured/reported even though the route is uncertain —
    # uncertainty must never hide a detected hazard, only prevent a false "safe" conclusion.
    assert any(h.alert_id == "hz1" and h.exposure_miles > 0 for h in result.hazard_exposures)


# ---------------- Shared vs. route-specific hazard end-to-end wiring ---------------- #

@pytest.mark.asyncio
async def test_shared_and_unique_hazard_classification_end_to_end(monkeypatch):
    """Exercises the exact cross-route wiring used in get_route_weather: evaluate two routes
    independently, classify shared-vs-unique via weather_exposure.classify_shared_unique_exposure,
    and confirm each route's OWN real exposure numbers are preserved (not blended)."""
    primary_geom = _ns_geometry(lon=-80.0)
    alt_geom = _ns_geometry(lon=-80.5)  # a parallel, distinct corridor
    _clear_weather(monkeypatch)

    shared_poly = _square(-80.25, 30.75, half_w=0.3)  # wide enough to clip BOTH corridors
    unique_poly = _square(-80.0, 30.3, half_w=0.05)   # only on the primary's corridor

    async def fake_alerts(lat, lon):
        alerts = [
            WeatherAlert(id="shared1", headline="Winter Storm Warning", severity="Severe",
                         event="Winter Storm Warning", description="desc", geometry=shared_poly),
        ]
        if lon > -80.25:  # only the primary corridor is near the unique hazard
            alerts.append(
                WeatherAlert(id="unique1", headline="Tornado Warning", severity="Extreme",
                             event="Tornado Warning", description="desc", urgency="Immediate",
                             geometry=unique_poly)
            )
        return alerts, "ok"

    monkeypatch.setattr(server, "get_noaa_alerts", fake_alerts)

    primary = await evaluate_route_weather_risk(0, primary_geom, 103.6, 120, dt.datetime.utcnow(), "car", False, None)
    alt = await evaluate_route_weather_risk(1, alt_geom, 103.6, 120, dt.datetime.utcnow(), "car", False, None)

    hazards_by_index = {0: primary.hazard_exposures, 1: alt.hazard_exposures}
    classified = server.weather_exposure.classify_shared_unique_exposure({
        idx: [
            server.weather_exposure.HazardExposureResult(
                alert_id=h.alert_id, event=h.event, severity=h.severity,
                exposure_miles=h.exposure_miles, exposure_minutes=h.exposure_minutes,
                exposure_method=h.exposure_method, entry_mile=h.entry_mile,
                temporally_relevant=h.temporally_relevant, scaled_penalty=0.0, weight=h.weight,
            )
            for h in hazards
        ]
        for idx, hazards in hazards_by_index.items()
    })

    primary_shared_miles, _sm, primary_unique_miles, _um = classified[0]
    alt_shared_miles, _sm2, alt_unique_miles, _um2 = classified[1]

    assert primary_unique_miles > 0  # the tornado warning is unique to the primary
    assert alt_unique_miles == 0.0   # the alternate never saw it
    assert primary_shared_miles > 0 and alt_shared_miles > 0  # both cross the wide shared storm


# ---------------- Ambient weather scoring fix: end-to-end regressions ---------------- #

@pytest.mark.asyncio
async def test_okeechobee_style_ordinary_scattered_thunderstorms_does_not_saturate_risk_score(monkeypatch):
    """The exact real-world bug this round fixes: 7+ sample points all reporting an ordinary
    'Chance Showers And Thunderstorms' forecast must no longer saturate risk_score to 0."""
    geometry = _ns_geometry(span_degrees=1.6, n=60)  # ~110mi, comparable to the real trip

    async def ordinary_weather(lat, lon):
        return WeatherData(temperature=73, wind_speed="10 mph", conditions="Chance Showers And Thunderstorms", humidity=70)

    async def no_alerts(lat, lon):
        return [], "ok"

    monkeypatch.setattr(server, "get_noaa_weather", ordinary_weather)
    monkeypatch.setattr(server, "get_noaa_alerts", no_alerts)

    result = await evaluate_route_weather_risk(1, geometry, 110.0, 130, dt.datetime.utcnow(), "car", False, None)

    assert result.uncertain is False
    assert result.risk_score > 85  # previously saturated to 0 under the old flat per-point penalty
    assert result.risk_level == "low"


@pytest.mark.asyncio
async def test_two_routes_both_saturated_to_zero_still_distinguishable_via_raw_penalty(monkeypatch):
    """Genuinely severe, widespread conditions can still legitimately saturate risk_score to 0
    for multiple routes — the saturated-comparison fallback must still distinguish them via the
    UNCLAMPED raw_risk_penalty/exposure_delta, per requirement 5. Pure-function coverage of the
    saturated-comparison DECISION logic itself (distinguishing unequal exposure once both floor
    out) lives in test_smart_reroute_phase1.py; this test just proves genuinely catastrophic,
    identical-severity conditions over a realistic distance can legitimately floor BOTH routes —
    i.e. zero is still reachable when truly warranted, not impossible under the new scoring."""
    heavy_geom = _ns_geometry(lon=-80.0, span_degrees=3.0, n=120)
    light_geom = _ns_geometry(lon=-80.8, span_degrees=3.0, n=120)
    tornado_poly = _square(-80.4, 31.5, half_w=1.0)  # wide enough to cover both parallel corridors

    async def catastrophic_weather(lat, lon):
        return WeatherData(temperature=5, wind_speed="70 mph", conditions="Severe Thunderstorms", humidity=95)

    async def tornado_alert(lat, lon):
        return [
            WeatherAlert(id="tornado1", headline="Tornado Warning", severity="Extreme", event="Tornado Warning",
                         description="desc", urgency="Immediate", geometry=tornado_poly)
        ], "ok"

    monkeypatch.setattr(server, "get_noaa_weather", catastrophic_weather)
    monkeypatch.setattr(server, "get_noaa_alerts", tornado_alert)

    primary = await evaluate_route_weather_risk(0, heavy_geom, 207.0, 240, dt.datetime.utcnow(), "car", False, None)
    alt = await evaluate_route_weather_risk(1, light_geom, 207.0, 240, dt.datetime.utcnow(), "car", False, None)

    assert primary.risk_score == 0
    assert alt.risk_score == 0
    # Both legitimately floored, but the UNCLAMPED raw_risk_penalty remains a real, large,
    # comparable number rather than being lost — this is what the saturated-comparison
    # fallback in select_weather_reroute reads from in the recommendation decision.
    assert primary.raw_risk_penalty > 100.0
    assert alt.raw_risk_penalty > 100.0


# ---------------- Legacy field preservation (requirement 11) ---------------- #

@pytest.mark.asyncio
async def test_legacy_safety_score_field_unaffected_by_new_ambient_scoring(monkeypatch):
    """calculate_safety_score() (the always-on, non-Phase-3 safety_score field) must keep
    producing its EXACT old behavior — still saturating to 0 for the same ordinary scattered
    thunderstorm forecast — proving the new ambient calculation is additive, Phase-3-only, and
    does not touch the legacy scoring path existing Android/iOS clients depend on."""
    from server import WaypointWeather, Waypoint, calculate_safety_score

    waypoints_weather = [
        WaypointWeather(
            waypoint=Waypoint(lat=30.0, lon=-80.0, distance_from_start=float(i) * 15, eta_minutes=i * 15),
            weather=WeatherData(temperature=73, wind_speed="10 mph", conditions="Chance Showers And Thunderstorms", humidity=70),
            alerts=[], alerts_status="ok",
        )
        for i in range(7)
    ]
    legacy_score = calculate_safety_score(waypoints_weather, "car")
    # This is the OLD, UNCHANGED behavior (flat 15pts * 7 points = 105 > 100) — still saturates,
    # confirming the legacy function (and therefore the always-on safety_score field) is untouched.
    assert legacy_score.overall_score == 0


# ---------------- Risk-level floor consistency (round-2 redesign fixes, item 6) ---------------- #

@pytest.mark.asyncio
async def test_confirmed_flood_warning_exposure_never_displays_as_low_risk_end_to_end(monkeypatch):
    """Reproduces the exact reported bug end-to-end: a route confirmed to cross a real Flood
    Warning polygon for several miles must never show risk_level == 'low', even though the raw
    scaled_exposure_penalty formula alone would score it near 100/100. risk_score (used for
    route-to-route comparison/recommendation) is intentionally left unclamped/unchanged."""
    geometry = _ns_geometry(span_degrees=0.15, n=20)  # short route, narrow flood warning crossing
    _clear_weather(monkeypatch)
    poly = _square(-80.0, 30.07, half_w=0.03)

    async def fake_alerts(lat, lon):
        return [
            WeatherAlert(
                id="flood1", headline="Flood Warning", severity="Severe",
                event="Flood Warning", description="desc", urgency="Expected",
                geometry=poly,
            )
        ], "ok"

    monkeypatch.setattr(server, "get_noaa_alerts", fake_alerts)

    result = await evaluate_route_weather_risk(1, geometry, 10.4, 15, dt.datetime.utcnow(), "car", False, None)

    confirmed = [h for h in result.hazard_exposures if h.exposure_method == "polygon_intersection" and h.exposure_miles > 0]
    assert len(confirmed) == 1  # sanity: the hazard genuinely, measurably overlaps this route
    assert result.risk_score >= 80  # the raw formula alone would still call this "low"
    assert result.risk_level != "low"  # the displayed label must not contradict the confirmed exposure
    assert result.risk_level == "moderate"


@pytest.mark.asyncio
async def test_zone_only_warning_overlap_still_displays_as_low_when_score_says_so(monkeypatch):
    """A county-wide/zone-only (unconfirmed) advisory — geographic overlap only, never a
    confirmed route intersection — must NOT trigger the floor, distinguishing a geographic
    warning-zone overlap from a confirmed on-road hazard."""
    geometry = _ns_geometry(span_degrees=0.15, n=20)
    _clear_weather(monkeypatch)

    async def fake_alerts(lat, lon):
        return [
            WeatherAlert(
                id="zonewarn1", headline="Flood Warning", severity="Severe",
                event="Flood Warning", description="desc", urgency="Expected",
                geometry=None,  # zone-only — no polygon to confirm actual route intersection
            )
        ], "ok"

    monkeypatch.setattr(server, "get_noaa_alerts", fake_alerts)

    result = await evaluate_route_weather_risk(1, geometry, 10.4, 15, dt.datetime.utcnow(), "car", False, None)

    zone_only = [h for h in result.hazard_exposures if h.exposure_method == "zone_only_uncertain"]
    assert len(zone_only) == 1
    assert result.risk_level == "low"  # unconfirmed overlap never floors the displayed level


@pytest.mark.asyncio
async def test_recommended_route_risk_label_never_contradicts_its_own_confirmed_exposure(monkeypatch):
    """Cross-field consistency: whichever route select_weather_reroute recommends, its OWN
    displayed risk_level must never claim 'low' while its own hazard_exposures confirm a
    severe/extreme polygon overlap — the recommendation message and the risk label shown on
    that same card must never contradict each other."""
    primary_geom = _ns_geometry(lon=-80.0, span_degrees=0.15, n=20)
    alt_geom = _ns_geometry(lon=-80.8, span_degrees=0.15, n=20)  # clear corridor, no hazard
    poly = _square(-80.0, 30.07, half_w=0.03)  # only intersects the primary's corridor
    _clear_weather(monkeypatch)

    async def fake_alerts(lat, lon):
        if lon > -80.4:
            return [
                WeatherAlert(id="flood2", headline="Flood Warning", severity="Severe",
                             event="Flood Warning", description="desc", urgency="Expected", geometry=poly)
            ], "ok"
        return [], "ok"

    monkeypatch.setattr(server, "get_noaa_alerts", fake_alerts)

    primary = await evaluate_route_weather_risk(0, primary_geom, 10.4, 15, dt.datetime.utcnow(), "car", False, None)
    alt = await evaluate_route_weather_risk(1, alt_geom, 10.4, 15, dt.datetime.utcnow(), "car", False, None)

    assessment = select_weather_reroute([primary, alt])

    if assessment.recommended_route_index == 1:
        # The alternate was recommended specifically because it avoids confirmed exposure the
        # primary has — its own risk_level must reflect that it is in fact the less-exposed one.
        assert alt.risk_level == "low"
        assert primary.risk_level != "low"
    else:
        # Whatever was recommended, it must never be a route whose own confirmed exposure says
        # otherwise — its displayed label and its own hazard data must agree.
        recommended = primary if assessment.recommended_route_index == 0 else alt
        recommended_confirmed_severe = any(
            h.exposure_method == "polygon_intersection" and h.exposure_miles > 0
            and (h.severity or "").lower() in ("severe", "extreme") and h.temporally_relevant
            for h in recommended.hazard_exposures
        )
        if recommended_confirmed_severe:
            assert recommended.risk_level != "low"


@pytest.mark.asyncio
async def test_floor_still_applies_correctly_when_the_route_is_also_marked_uncertain(monkeypatch):
    """`uncertain` (incomplete data elsewhere on the route) and the confirmed-hazard risk-level
    floor are independent signals \u2014 a route can be both uncertain AND have one fully confirmed
    severe hazard; the floor must still apply to whatever numeric risk_level was computed, and
    must never be confused by uncertain=True into skipping or double-penalizing."""
    geometry = _ns_geometry(span_degrees=0.15, n=20)
    poly = _square(-80.0, 30.07, half_w=0.03)
    call_count = {"n": 0}

    async def mostly_missing_weather(lat, lon):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return WeatherData(temperature=70, wind_speed="5 mph", conditions="Clear", humidity=40)
        return None  # subsequent points missing -> data_incomplete -> uncertain=True

    async def fake_alerts(lat, lon):
        return [
            WeatherAlert(id="flood3", headline="Flood Warning", severity="Severe",
                         event="Flood Warning", description="desc", urgency="Expected", geometry=poly)
        ], "ok"

    monkeypatch.setattr(server, "get_noaa_weather", mostly_missing_weather)
    monkeypatch.setattr(server, "get_noaa_alerts", fake_alerts)

    result = await evaluate_route_weather_risk(1, geometry, 10.4, 15, dt.datetime.utcnow(), "car", False, None)

    assert result.uncertain is True
    confirmed = [h for h in result.hazard_exposures if h.exposure_method == "polygon_intersection" and h.exposure_miles > 0]
    assert len(confirmed) == 1
    assert result.risk_level != "low"



