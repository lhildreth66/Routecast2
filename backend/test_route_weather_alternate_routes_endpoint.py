"""Smart Weather Rerouting Phase 0/1 end-to-end test: verifies the /api/route/weather
response carries the new additive fields while remaining backward compatible with the
existing response shape (older Android/iOS clients ignore unknown JSON fields)."""
import os

import pytest
from httpx import ASGITransport, AsyncClient

import server
from providers import reload_providers


def _route_payload():
    return {
        # Direct lat,lng strings bypass geocoding and match the Seattle->Portland demo fixture,
        # which now carries one alternate route geometry.
        "origin": "47.6062,-122.3321",
        "destination": "45.5152,-122.6784",
        "vehicle_type": "car",
    }


def _patch_common(monkeypatch):
    monkeypatch.setattr(server, "ROUTECAST_MODE", "test")
    monkeypatch.setattr(server, "MAPBOX_ACCESS_TOKEN", "")  # skip real turn-by-turn Mapbox call
    # SMART_REROUTE_ENABLED defaults OFF in production; these tests exercise Phase 1 explicitly.
    monkeypatch.setattr(server, "SMART_REROUTE_ENABLED", True)
    reload_providers("test")

    async def fake_weather(lat, lon):
        return server.WeatherData(temperature=70, wind_speed="5 mph", conditions="Clear", humidity=40)

    async def fake_alerts(lat, lon):
        return [], "ok"

    monkeypatch.setattr(server, "get_noaa_weather", fake_weather)
    monkeypatch.setattr(server, "get_noaa_alerts", fake_alerts)


@pytest.mark.asyncio
async def test_route_weather_includes_phase0_and_phase1_and_stays_backward_compatible(monkeypatch):
    _patch_common(monkeypatch)

    transport = ASGITransport(app=server.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/route/weather", json=_route_payload())

    assert response.status_code == 200
    data = response.json()

    # --- Backward compatibility: pre-existing fields are untouched ---
    assert data["route_geometry"]
    assert "reroute_recommended" in data
    assert "safety_score" in data
    assert data["alternate_routes"] == []  # legacy unused field stays empty

    # --- Phase 0: alternate geometries surfaced from the fixture (capped at 2) ---
    assert len(data["route_alternatives"]) == 2
    for expected_index, alt in enumerate(data["route_alternatives"], start=1):
        assert alt["index"] == expected_index
        assert alt["route_geometry"]
        assert alt["distance_miles"] > 0
        assert alt["duration_minutes"] > 0

    # --- Phase 1: comparative assessment present, covering primary + both alternates ---
    assert data["weather_reroute"] is not None
    assert len(data["weather_reroute"]["routes"]) == 3
    assert data["weather_reroute"]["message"]


@pytest.mark.asyncio
async def test_phase1_can_be_disabled_independently_of_phase0(monkeypatch):
    _patch_common(monkeypatch)
    monkeypatch.setattr(server, "SMART_REROUTE_ENABLED", False)

    transport = ASGITransport(app=server.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/route/weather", json=_route_payload())

    assert response.status_code == 200
    data = response.json()
    assert len(data["route_alternatives"]) == 2  # Phase 0 unaffected by the Phase 1 flag
    assert data["weather_reroute"] is None


def test_smart_reroute_defaults_off_without_env_override():
    """Production safety: Phase 1 must stay disabled until explicitly turned on via env var.
    Imports server fresh in a subprocess with a clean environment, since this process's own
    `server` module was already imported once (with whatever env existed at collection time)."""
    import subprocess
    import sys

    env = {k: v for k, v in os.environ.items() if k != "SMART_REROUTE_ENABLED"}
    result = subprocess.run(
        [sys.executable, "-c", "import server; print(server.SMART_REROUTE_ENABLED)"],
        cwd=os.path.dirname(__file__),
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "False"


@pytest.mark.asyncio
async def test_route_with_no_fixture_alternatives_returns_empty_list(monkeypatch):
    _patch_common(monkeypatch)

    transport = ASGITransport(app=server.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Portland -> Seattle fixture entry has no alternatives defined
        response = await client.post("/api/route/weather", json={
            "origin": "45.5152,-122.6784",
            "destination": "47.6062,-122.3321",
            "vehicle_type": "car",
        })

    assert response.status_code == 200
    data = response.json()
    assert data["route_alternatives"] == []
    assert data["weather_reroute"]["recommended_route_index"] is None
    assert data["weather_reroute"]["message"] == "No safer alternate route found."
