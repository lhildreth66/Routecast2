"""Smart Weather Rerouting Phase 0 tests: Mapbox alternates request/parsing + fixture passthrough."""
import asyncio

import pytest

from providers.real_providers import MapboxDirectionsProvider
from providers.fake_providers import FakeDirectionsProvider


def test_mapbox_provider_requests_alternatives(monkeypatch):
    """The directions request to Mapbox must ask for alternatives=true."""
    captured = {}

    class FakeResp:
        status_code = 200
        text = "{}"

        def json(self):
            return {
                "code": "Ok",
                "routes": [
                    {"geometry": "primary_geom", "distance": 1000.0, "duration": 600.0, "legs": []},
                ],
            }

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url, params=None):
            captured["params"] = params
            return FakeResp()

    monkeypatch.setattr("providers.real_providers.MAPBOX_ACCESS_TOKEN", "x")
    monkeypatch.setattr("providers.real_providers.httpx.AsyncClient", FakeClient)

    provider = MapboxDirectionsProvider()
    result = asyncio.run(provider.route({"lat": 0.0, "lon": 0.0}, {"lat": 1.0, "lon": 1.0}, None, None))

    assert captured["params"]["alternatives"] == "true"
    assert result is not None
    assert result["alternatives"] == []  # Mapbox returned only 1 route


def test_mapbox_provider_returns_up_to_two_alternatives(monkeypatch):
    class FakeResp:
        status_code = 200
        text = "{}"

        def json(self):
            return {
                "code": "Ok",
                "routes": [
                    {"geometry": "primary_geom", "distance": 1000.0, "duration": 600.0, "legs": []},
                    {"geometry": "alt1_geom", "distance": 1100.0, "duration": 650.0, "legs": []},
                    {"geometry": "alt2_geom", "distance": 1200.0, "duration": 700.0, "legs": []},
                    {"geometry": "alt3_geom", "distance": 1300.0, "duration": 750.0, "legs": []},
                ],
            }

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url, params=None):
            return FakeResp()

    monkeypatch.setattr("providers.real_providers.MAPBOX_ACCESS_TOKEN", "x")
    monkeypatch.setattr("providers.real_providers.httpx.AsyncClient", FakeClient)

    provider = MapboxDirectionsProvider()
    result = asyncio.run(provider.route({"lat": 0.0, "lon": 0.0}, {"lat": 1.0, "lon": 1.0}, None, None))

    # Capped at 2 even though Mapbox returned 3 alternates
    assert len(result["alternatives"]) == 2
    assert result["alternatives"][0]["geometry"] == "alt1_geom"
    assert result["alternatives"][1]["geometry"] == "alt2_geom"
    # Primary route fields unaffected
    assert result["geometry"] == "primary_geom"
    assert result["distance"] == 1000.0
    assert result["duration"] == 600.0


def test_fake_directions_provider_passes_through_alternatives():
    """Demo/test fixture provider should surface the fixture's alternatives (or empty list)."""
    provider = FakeDirectionsProvider()

    # Seattle -> Portland fixture entry has 2 alternatives defined
    result = asyncio.run(provider.route(
        {"lat": 47.6062, "lon": -122.3321},
        {"lat": 45.5152, "lon": -122.6784},
        None,
        None,
    ))
    assert result is not None
    assert len(result["alternatives"]) == 2
    assert result["alternatives"][0]["geometry"]

    # Portland -> Seattle fixture entry has no alternatives defined
    result2 = asyncio.run(provider.route(
        {"lat": 45.5152, "lon": -122.6784},
        {"lat": 47.6062, "lon": -122.3321},
        None,
        None,
    ))
    assert result2 is not None
    assert result2["alternatives"] == []


def test_mapbox_request_preserves_origin_destination_and_stops(monkeypatch):
    """Requesting alternatives must not change which coordinates are sent to Mapbox: the same
    origin/stops/destination chain must be present, with alternatives layered on top."""
    captured = {}

    class FakeResp:
        status_code = 200
        text = "{}"

        def json(self):
            return {
                "code": "Ok",
                "routes": [
                    {"geometry": "primary_geom", "distance": 1000.0, "duration": 600.0, "legs": []},
                    {"geometry": "alt1_geom", "distance": 1100.0, "duration": 650.0, "legs": []},
                ],
            }

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url, params=None):
            captured["url"] = url
            captured["params"] = params
            return FakeResp()

    monkeypatch.setattr("providers.real_providers.MAPBOX_ACCESS_TOKEN", "x")
    monkeypatch.setattr("providers.real_providers.httpx.AsyncClient", FakeClient)

    provider = MapboxDirectionsProvider()
    stops = [{"lat": 2.0, "lon": 2.0}, {"lat": 3.0, "lon": 3.0}]
    result = asyncio.run(provider.route({"lat": 0.0, "lon": 0.0}, {"lat": 1.0, "lon": 1.0}, stops, None))

    # URL coordinate chain must be origin -> stop1 -> stop2 -> destination, unchanged by alternatives=true.
    assert captured["url"].endswith("0.0,0.0;2.0,2.0;3.0,3.0;1.0,1.0")
    assert captured["params"]["alternatives"] == "true"
    assert result["alternatives"][0]["geometry"] == "alt1_geom"

