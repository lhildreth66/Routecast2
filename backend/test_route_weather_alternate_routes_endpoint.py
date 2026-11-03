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
        # Smart Weather Rerouting corridor-generation field: defaults to "mapbox_alternative"
        # when a provider (like the demo fixture) doesn't supply its own generation_method.
        assert alt["generation_method"] == "mapbox_alternative"

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
async def test_trucker_mode_reuses_primary_bridge_check_but_still_checks_each_alternate(monkeypatch):
    """End-to-end: with 1 primary + 2 alternates, the legacy bridge check plus Phase 1 should make
    exactly 3 Overpass calls (1 legacy primary + 2 independent alternates) — not 4 — because the
    primary's Phase 1 evaluation reuses the already-confirmed legacy result instead of repeating it.
    Every alternate must still receive its own real check."""
    _patch_common(monkeypatch)

    calls = []

    async def counting_bridge_check(route_geometry, vehicle_height_ft):
        calls.append(route_geometry)
        return [], True  # no conflicts found on any route in this scenario, genuinely checked

    monkeypatch.setattr(server, "_get_bridge_clearances", counting_bridge_check)

    payload = {**_route_payload(), "trucker_mode": True, "vehicle_height_ft": 12.5}
    transport = ASGITransport(app=server.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/route/weather", json=payload)

    assert response.status_code == 200
    data = response.json()

    assert len(calls) == 3  # 1 legacy primary + 2 alternates, no redundant 4th primary re-check

    wr = data["weather_reroute"]
    for r in wr["routes"]:
        assert r["vehicle_restriction_checked"] is True
        assert r["vehicle_restriction_blocked"] is False


@pytest.mark.asyncio
async def test_trucker_mode_blocked_primary_still_blocks_after_reuse(monkeypatch):
    """The reuse optimization must never hide a real clearance conflict found on the primary route."""
    _patch_common(monkeypatch)

    async def conflicting_bridge_check(route_geometry, vehicle_height_ft):
        return [{"bridge_name": "Low Overpass", "margin_ft": -1.5}], True

    monkeypatch.setattr(server, "_get_bridge_clearances", conflicting_bridge_check)

    payload = {**_route_payload(), "trucker_mode": True, "vehicle_height_ft": 12.5}
    transport = ASGITransport(app=server.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/route/weather", json=payload)

    assert response.status_code == 200
    data = response.json()

    assert data["reroute_recommended"] is True  # legacy flag still upgraded by the conflict
    primary_risk = next(r for r in data["weather_reroute"]["routes"] if r["route_index"] == 0)
    assert primary_risk["vehicle_restriction_blocked"] is True


@pytest.mark.asyncio
async def test_slow_but_successful_legacy_bridge_check_is_trusted_for_reuse(monkeypatch):
    """A legacy check that takes a while but genuinely succeeds (status=True) should now be
    trusted and reused for the primary route — correctness is driven by the real status the
    service reports, not by how long the call happened to take."""
    _patch_common(monkeypatch)

    calls = []

    async def slow_but_genuinely_successful(route_geometry, vehicle_height_ft):
        calls.append(route_geometry)
        await server.asyncio.sleep(0.05)
        return [], True

    monkeypatch.setattr(server, "_get_bridge_clearances", slow_but_genuinely_successful)

    payload = {**_route_payload(), "trucker_mode": True, "vehicle_height_ft": 12.5}
    transport = ASGITransport(app=server.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/route/weather", json=payload)

    assert response.status_code == 200
    data = response.json()

    # Legacy call (1) + 2 alternates = 3 — the primary's genuinely-successful result is reused,
    # not redundantly re-checked by Phase 1.
    assert len(calls) == 3
    primary_risk = next(r for r in data["weather_reroute"]["routes"] if r["route_index"] == 0)
    assert primary_risk["vehicle_restriction_checked"] is True
    assert primary_risk["uncertain"] is False


@pytest.mark.asyncio
async def test_legacy_bridge_check_reporting_failure_is_not_trusted_for_reuse(monkeypatch):
    """The real bug this guards against: a legacy check that returns quickly (well within any
    elapsed-time budget) but with succeeded=False — e.g. an Overpass outage or decode error that
    was internally swallowed — must never be reused as a confirmed 'checked, zero restrictions'
    result. Phase 1 must perform its own fresh check for the primary route instead."""
    _patch_common(monkeypatch)

    calls = []

    async def fast_but_failed(route_geometry, vehicle_height_ft):
        calls.append(route_geometry)
        return [], False  # fast, no exception/timeout, but genuinely failed internally

    monkeypatch.setattr(server, "_get_bridge_clearances", fast_but_failed)

    payload = {**_route_payload(), "trucker_mode": True, "vehicle_height_ft": 12.5}
    transport = ASGITransport(app=server.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/route/weather", json=payload)

    assert response.status_code == 200
    data = response.json()

    # Legacy call (1) + Phase 1's OWN fresh primary check (not reused) + 2 alternates = 4,
    # not 3 — proving the failed legacy result was not silently reused.
    assert len(calls) == 4
    primary_risk = next(r for r in data["weather_reroute"]["routes"] if r["route_index"] == 0)
    assert primary_risk["vehicle_restriction_checked"] is False
    assert primary_risk["uncertain"] is True


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
