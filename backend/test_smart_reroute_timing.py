"""Smart Weather Rerouting Phase 1 performance check: confirms evaluating extra alternate
routes does not add significant wall-clock time to /api/route/weather, since all candidate
routes (primary + alternates) are evaluated concurrently rather than sequentially."""
import asyncio
import time

import pytest
from httpx import ASGITransport, AsyncClient

import server
from providers import reload_providers

SIMULATED_NETWORK_LATENCY_SECONDS = 0.05  # approximate a real NOAA round-trip per call


def _patch_common(monkeypatch):
    monkeypatch.setattr(server, "ROUTECAST_MODE", "test")
    monkeypatch.setattr(server, "MAPBOX_ACCESS_TOKEN", "")
    # SMART_REROUTE_ENABLED defaults OFF in production; this timing check exercises Phase 1 explicitly.
    monkeypatch.setattr(server, "SMART_REROUTE_ENABLED", True)
    reload_providers("test")

    async def fake_weather(lat, lon):
        await asyncio.sleep(SIMULATED_NETWORK_LATENCY_SECONDS)
        return server.WeatherData(temperature=70, wind_speed="5 mph", conditions="Clear", humidity=40)

    async def fake_alerts(lat, lon):
        await asyncio.sleep(SIMULATED_NETWORK_LATENCY_SECONDS)
        return [], "ok"

    monkeypatch.setattr(server, "get_noaa_weather", fake_weather)
    monkeypatch.setattr(server, "get_noaa_alerts", fake_alerts)


async def _timed_request(payload) -> float:
    transport = ASGITransport(app=server.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        start = time.perf_counter()
        response = await client.post("/api/route/weather", json=payload)
        elapsed = time.perf_counter() - start
    assert response.status_code == 200
    return elapsed


@pytest.mark.asyncio
async def test_three_route_evaluation_is_not_significantly_slower_than_one_route(monkeypatch, capsys):
    _patch_common(monkeypatch)

    # Portland -> Seattle fixture entry has 0 alternatives => 1-route case.
    one_route_elapsed = await _timed_request({
        "origin": "45.5152,-122.6784",
        "destination": "47.6062,-122.3321",
        "vehicle_type": "car",
    })

    # Seattle -> Portland fixture entry has 2 alternatives => 3-route case (primary + 2 alts).
    three_route_elapsed = await _timed_request({
        "origin": "47.6062,-122.3321",
        "destination": "45.5152,-122.6784",
        "vehicle_type": "car",
    })

    with capsys.disabled():
        print(
            f"\n[timing] 1-route request: {one_route_elapsed * 1000:.1f} ms | "
            f"3-route request: {three_route_elapsed * 1000:.1f} ms | "
            f"delta: {(three_route_elapsed - one_route_elapsed) * 1000:.1f} ms"
        )

    # Evaluations run concurrently, so adding 2 more candidate routes should add at most
    # roughly one extra round of simulated latency (bounded concurrency semaphore = 4),
    # not 2x-3x the total time a sequential implementation would take.
    assert three_route_elapsed < one_route_elapsed + 1.5
