"""Legacy "REROUTE RECOMMENDED" banner fix: the top-level reroute_recommended/reroute_reason
fields must never claim a reroute is recommended unless a confirmed, meaningfully-lower-risk
alternative route actually exists (bridge-clearance conflicts remain a separate, always-valid
hard physical constraint and are unaffected by this fix). Raw hazard severity alone — the old
behavior — is no longer sufficient. Hazard severity itself remains fully visible via
road_condition_summary/worst_road_condition regardless of this flag, so no safety information is
hidden; only the specific "a safer route exists" claim must be truthful.
"""
import pytest
from httpx import ASGITransport, AsyncClient

import server
from providers import reload_providers


def _route_payload():
    return {
        "origin": "47.6062,-122.3321",
        "destination": "45.5152,-122.6784",
        "vehicle_type": "car",
    }


def _patch_common(monkeypatch, smart_reroute_enabled: bool):
    monkeypatch.setattr(server, "ROUTECAST_MODE", "test")
    monkeypatch.setattr(server, "MAPBOX_ACCESS_TOKEN", "")
    monkeypatch.setattr(server, "SMART_REROUTE_ENABLED", smart_reroute_enabled)
    reload_providers("test")


async def _post(payload):
    transport = ASGITransport(app=server.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.post("/api/route/weather", json=payload)


@pytest.mark.asyncio
async def test_severe_weather_alone_no_longer_triggers_banner_when_flag_disabled(monkeypatch):
    """Heavy snow (severity 3 — previously enough, alone, to set reroute_recommended=True)
    must no longer trigger the banner when Smart Weather Rerouting isn't even running, since
    there is no way to confirm a safer alternative exists without it."""
    _patch_common(monkeypatch, smart_reroute_enabled=False)

    async def heavy_snow(lat, lon):
        return server.WeatherData(temperature=20, wind_speed="5 mph", conditions="Heavy Snow", humidity=60)

    async def no_alerts(lat, lon):
        return [], "ok"

    monkeypatch.setattr(server, "get_noaa_weather", heavy_snow)
    monkeypatch.setattr(server, "get_noaa_alerts", no_alerts)

    response = await _post(_route_payload())
    assert response.status_code == 200
    data = response.json()

    assert data["weather_reroute"] is None  # flag off, Phase 1 doesn't run
    assert data["reroute_recommended"] is False
    # Severity is still visible elsewhere, nothing is hidden:
    assert data["road_condition_summary"] and data["road_condition_summary"] != "✅ Good road conditions expected throughout your route"


@pytest.mark.asyncio
async def test_same_severe_weather_on_every_route_does_not_trigger_banner_when_no_safer_alternative(monkeypatch):
    """Mirrors the real Okeechobee -> Buckhead Ridge finding: identical severe conditions
    sampled on every route (no route is actually safer) must not claim a reroute exists,
    even with Smart Weather Rerouting fully enabled."""
    _patch_common(monkeypatch, smart_reroute_enabled=True)

    async def heavy_snow(lat, lon):
        return server.WeatherData(temperature=20, wind_speed="5 mph", conditions="Heavy Snow", humidity=60)

    async def no_alerts(lat, lon):
        return [], "ok"

    monkeypatch.setattr(server, "get_noaa_weather", heavy_snow)
    monkeypatch.setattr(server, "get_noaa_alerts", no_alerts)

    response = await _post(_route_payload())
    assert response.status_code == 200
    data = response.json()

    assert data["weather_reroute"] is not None
    assert data["weather_reroute"]["comparison_outcome"] != "lower_risk_found"
    assert data["reroute_recommended"] is False


@pytest.mark.asyncio
async def test_confirmed_lower_risk_alternative_does_trigger_banner_with_matching_reason(monkeypatch):
    """When Smart Weather Rerouting positively confirms a meaningfully-lower-risk alternative,
    the legacy banner fields must mirror that confirmed result exactly (same message)."""
    _patch_common(monkeypatch, smart_reroute_enabled=True)

    async def clear_weather(lat, lon):
        return server.WeatherData(temperature=70, wind_speed="5 mph", conditions="Clear", humidity=40)

    async def no_alerts(lat, lon):
        return [], "ok"

    monkeypatch.setattr(server, "get_noaa_weather", clear_weather)
    monkeypatch.setattr(server, "get_noaa_alerts", no_alerts)

    fake_assessment = server.WeatherRerouteAssessment(
        routes=[],
        recommended_route_index=1,
        reroute_recommended=True,
        message="Alternate route 1 has lower calculated weather exposure (+15 weather-exposure points).",
        uncertain=False,
        comparison_outcome="lower_risk_found",
    )
    monkeypatch.setattr(server, "select_weather_reroute", lambda evaluated_routes: fake_assessment)

    response = await _post(_route_payload())
    assert response.status_code == 200
    data = response.json()

    assert data["reroute_recommended"] is True
    assert data["reroute_reason"] == fake_assessment.message


@pytest.mark.asyncio
async def test_insufficient_evidence_outcome_does_not_trigger_banner(monkeypatch):
    """An uncertain/insufficient-evidence comparison must not be treated as a confirmed
    safer alternative either — only "lower_risk_found" may set the banner."""
    _patch_common(monkeypatch, smart_reroute_enabled=True)

    async def clear_weather(lat, lon):
        return server.WeatherData(temperature=70, wind_speed="5 mph", conditions="Clear", humidity=40)

    async def no_alerts(lat, lon):
        return [], "ok"

    monkeypatch.setattr(server, "get_noaa_weather", clear_weather)
    monkeypatch.setattr(server, "get_noaa_alerts", no_alerts)

    fake_assessment = server.WeatherRerouteAssessment(
        routes=[],
        recommended_route_index=None,
        reroute_recommended=False,
        message="Unable to reliably compare routes.",
        uncertain=True,
        comparison_outcome="insufficient_evidence",
    )
    monkeypatch.setattr(server, "select_weather_reroute", lambda evaluated_routes: fake_assessment)

    response = await _post(_route_payload())
    assert response.status_code == 200
    data = response.json()

    assert data["reroute_recommended"] is False
