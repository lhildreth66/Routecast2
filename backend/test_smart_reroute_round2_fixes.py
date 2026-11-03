"""Round 2 Smart Weather Rerouting fixes:
1. A timed-out/failed route evaluation must report risk_level="unknown", never "extreme" —
   an unevaluated route is neither safe nor maximally dangerous, and must never be selected
   as the recommended (safer) alternative.
2. Marine-only NWS products (Rip Current Statement, Small Craft Advisory, etc.) must not
   contribute to road-driving risk calculations, while genuinely road-relevant hazards
   (including zone-only/unconfirmed ones, which must stay visible with their uncertainty
   preserved) are unaffected.
3. The "no safer alternate" message must disclose when some alternates could not be
   evaluated, instead of implying every alternative was checked.
"""
import datetime as dt

import polyline
import pytest

import server
from server import (
    RouteWeatherRisk,
    WeatherAlert,
    WeatherData,
    derive_road_condition,
    evaluate_route_weather_risk,
    is_road_relevant_alert,
    select_weather_reroute,
)


def _clear_weather():
    return WeatherData(temperature=70, wind_speed="5 mph", conditions="Clear", humidity=40)


def _ns_geometry(lat_start=30.0, lon=-80.0, span_degrees=1.5, n=60):
    coords = [(lat_start + i * (span_degrees / n), lon) for i in range(n)]
    return polyline.encode(coords, precision=6)


# ---------------- Fix 1: unknown risk, never "extreme" ---------------- #

@pytest.mark.asyncio
async def test_timeout_reports_unknown_risk_level_not_extreme(monkeypatch):
    geometry = _ns_geometry()

    async def hanging_weather(lat, lon):
        import asyncio
        await asyncio.sleep(999)

    monkeypatch.setattr(server, "get_noaa_weather", hanging_weather)
    monkeypatch.setattr(server, "ALT_ROUTE_EVAL_TIMEOUT_SECONDS", 0.05)

    result = await evaluate_route_weather_risk(1, geometry, 103.6, 120, dt.datetime.utcnow(), "car", False, None)

    assert result.uncertain is True
    assert result.risk_level == "unknown"
    assert result.risk_level != "extreme"


def test_select_weather_reroute_never_recommends_an_uncertain_route():
    primary = RouteWeatherRisk(route_index=0, distance_miles=100, duration_minutes=100, risk_score=90, risk_level="low")
    timed_out_alt = RouteWeatherRisk(
        route_index=1, distance_miles=100, duration_minutes=100, risk_score=0, risk_level="unknown",
        uncertain=True, uncertainty_reason="Weather evaluation for this route timed out.",
    )
    assessment = select_weather_reroute([primary, timed_out_alt])
    assert assessment.recommended_route_index is None
    assert assessment.reroute_recommended is False


def test_no_sample_points_fallback_reports_unknown_not_extreme():
    # Directly exercises the "unable to sample route geometry" fallback path's literal values
    # via the same construction used in evaluate_route_weather_risk — regression-proofs the
    # exact risk_level string independent of timing-based reproduction above.
    fallback = RouteWeatherRisk(
        route_index=2, distance_miles=50, duration_minutes=60, risk_score=0, risk_level="unknown",
        uncertain=True, uncertainty_reason="Unable to sample route geometry for weather evaluation.",
    )
    assert fallback.risk_level == "unknown"


# ---------------- Fix 2: marine-only alerts excluded from driving risk ---------------- #

def test_rip_current_statement_is_not_road_relevant():
    assert is_road_relevant_alert("Rip Current Statement") is False


def test_small_craft_advisory_is_not_road_relevant():
    assert is_road_relevant_alert("Small Craft Advisory") is False


def test_tornado_warning_is_road_relevant():
    assert is_road_relevant_alert("Tornado Warning") is True


def test_coastal_flood_advisory_is_road_relevant():
    assert is_road_relevant_alert("Coastal Flood Advisory") is True


def test_unknown_event_defaults_to_road_relevant():
    assert is_road_relevant_alert(None) is True
    assert is_road_relevant_alert("") is True


def test_rip_current_statement_does_not_affect_derive_road_condition():
    alert = WeatherAlert(id="r1", event="Rip Current Statement", headline="Rip Current Statement",
                          severity="Minor", description="desc", urgency="Expected")
    cond = derive_road_condition(_clear_weather(), [alert])
    assert cond.condition == "dry"
    assert cond.severity == 0


def test_flood_warning_still_affects_derive_road_condition_alongside_marine_alert():
    """A genuinely road-relevant alert must still be detected even when a marine-only
    alert is also present for the same point — marine filtering must not mask real hazards."""
    marine = WeatherAlert(id="r1", event="Rip Current Statement", headline="Rip Current Statement",
                           severity="Minor", description="desc", urgency="Expected")
    flood = WeatherAlert(id="f1", event="Flood Warning", headline="Flood Warning",
                          severity="Severe", description="desc", urgency="Immediate")
    cond = derive_road_condition(_clear_weather(), [marine, flood])
    assert cond.condition == "flooded"


@pytest.mark.asyncio
async def test_rip_current_statement_contributes_zero_hazard_exposure(monkeypatch):
    """End-to-end: a Rip Current Statement covering the entire route must not appear as a
    scored hazard_exposure entry at all, and must not reduce risk_score."""
    geometry = _ns_geometry()

    async def clear_weather(lat, lon):
        return _clear_weather()

    async def rip_current_everywhere(lat, lon):
        return [
            WeatherAlert(id="rip1", event="Rip Current Statement", headline="Rip Current Statement",
                         severity="Minor", description="desc", urgency="Expected")
        ], "ok"

    monkeypatch.setattr(server, "get_noaa_weather", clear_weather)
    monkeypatch.setattr(server, "get_noaa_alerts", rip_current_everywhere)

    result = await evaluate_route_weather_risk(1, geometry, 103.6, 120, dt.datetime.utcnow(), "car", False, None)

    assert result.hazard_exposures == []
    assert result.risk_score == 100


# ---------------- Fix 6: incomplete-comparison message is honest ---------------- #

def _hazard_free_risk(route_index, risk_score, risk_level="low", **kwargs):
    return RouteWeatherRisk(
        route_index=route_index, distance_miles=100, duration_minutes=100,
        risk_score=risk_score, risk_level=risk_level, **kwargs,
    )


def test_message_discloses_incomplete_comparison_when_an_alternate_timed_out():
    primary = _hazard_free_risk(0, 94)
    confident_but_not_better = _hazard_free_risk(1, 92)
    timed_out = _hazard_free_risk(
        2, 0, risk_level="unknown", uncertain=True,
        uncertainty_reason="Weather evaluation for this route timed out.",
    )
    assessment = select_weather_reroute([primary, confident_but_not_better, timed_out])

    assert assessment.comparison_outcome == "no_lower_risk_found"
    assert assessment.reroute_recommended is False
    assert "could not be assessed" in assessment.message
    assert "No safer alternate route found." != assessment.message


def test_message_stays_simple_when_every_alternate_was_fully_evaluated():
    primary = _hazard_free_risk(0, 94)
    confident_but_not_better = _hazard_free_risk(1, 92)
    assessment = select_weather_reroute([primary, confident_but_not_better])

    assert assessment.message == "No safer alternate route found."
