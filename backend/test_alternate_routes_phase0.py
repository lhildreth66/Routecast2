"""Smart Weather Rerouting Phase 0 tests: Mapbox alternates request/parsing + fixture passthrough."""
import asyncio
import json
import time

import polyline
import pytest

from providers.real_providers import MapboxDirectionsProvider
from providers.fake_providers import FakeDirectionsProvider


def _line(lat1, lon1, lat2, lon2, offset_lon=0.0, n=30):
    """A simple straight-ish line of points between two coords, offset east/west for testing
    distinctness, encoded the same way Mapbox encodes geometry (polyline6)."""
    pts = []
    for i in range(n):
        t = i / (n - 1)
        lat = lat1 + (lat2 - lat1) * t
        lon = lon1 + (lon2 - lon1) * t + offset_lon
        pts.append((lat, lon))
    return polyline.encode(pts, precision=6)


OKEE = (27.2436, -80.8300)
ORL = (28.5421, -81.3790)
PRIMARY_GEOM = _line(*OKEE, *ORL)
NEAR_DUPLICATE_GEOM = _line(*OKEE, *ORL, offset_lon=0.001)  # ~0.06 mi offset — not distinct
DISTINCT_GEOM = _line(*OKEE, *ORL, offset_lon=0.08)  # ~4-5 mi offset — genuinely different corridor


def _mapbox_route_response(geometry, distance_m, duration_s, num_routes=1):
    """Builds a raw Mapbox Directions JSON payload with `num_routes` identical-shape routes."""
    route = {
        "geometry": geometry,
        "distance": distance_m,
        "duration": duration_s,
        "legs": [{"steps": []}],
    }
    return {"code": "Ok", "routes": [dict(route) for _ in range(num_routes)]}


class _FakeResp:
    def __init__(self, payload, status_code=200):
        self.status_code = status_code
        self._payload = payload
        self.text = json.dumps(payload)[:2000]

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def make_scripted_client(handlers, captured_calls=None):
    """handlers maps an `exclude` param value (or None for the standard/primary request) to
    either a JSON-serializable dict payload, an Exception to raise, or the string "HANG" to
    simulate a slow/unresponsive request (for timeout testing)."""

    class ScriptedClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url, params=None):
            if captured_calls is not None:
                captured_calls.append({"url": url, "params": dict(params or {})})
            exclude = (params or {}).get("exclude")
            handler = handlers.get(exclude, handlers.get("__default__"))
            if isinstance(handler, Exception):
                raise handler
            if handler == "HANG":
                await asyncio.sleep(999)
            return _FakeResp(handler)

    return ScriptedClient


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


# ---------------- Corridor generation (exclude=motorway / exclude=toll) ---------------- #

def _run_corridor_route(handlers, origin=None, dest=None, waypoints=None, captured_calls=None, monkeypatch=None):
    monkeypatch.setattr("providers.real_providers.MAPBOX_ACCESS_TOKEN", "x")
    monkeypatch.setattr("providers.real_providers.httpx.AsyncClient", make_scripted_client(handlers, captured_calls))
    provider = MapboxDirectionsProvider()
    return asyncio.run(provider.route(
        origin or {"lat": OKEE[0], "lon": OKEE[1]},
        dest or {"lat": ORL[0], "lon": ORL[1]},
        waypoints,
        {"generate_corridors": True},
    ))


def test_corridor_generation_dedupes_near_duplicate_routes(monkeypatch):
    """A near-duplicate Mapbox-native alternative and a near-duplicate exclude=toll result must
    both be filtered out; only the genuinely distinct exclude=motorway corridor should remain."""
    handlers = {
        None: _mapbox_route_response(PRIMARY_GEOM, 170000, 6300, num_routes=2),  # 2nd route is near-dup (same geom)
        "motorway": _mapbox_route_response(DISTINCT_GEOM, 175000, 9000),
        "toll": _mapbox_route_response(NEAR_DUPLICATE_GEOM, 171000, 6400),
    }
    # Make the primary's own "2nd route" a near-duplicate explicitly
    handlers[None]["routes"][1]["geometry"] = NEAR_DUPLICATE_GEOM

    result = _run_corridor_route(handlers, monkeypatch=monkeypatch)

    assert result is not None
    assert len(result["alternatives"]) == 1
    assert result["alternatives"][0]["geometry"] == DISTINCT_GEOM
    assert result["alternatives"][0]["generation_method"] == "exclude_motorway"


def test_corridor_generation_respects_max_total_alternates(monkeypatch):
    """Even with 4 distinct candidates available, at most 3 are kept."""
    far1 = _line(*OKEE, *ORL, offset_lon=0.08)
    far2 = _line(*OKEE, *ORL, offset_lon=-0.08)
    far3 = _line(*OKEE, *ORL, offset_lon=0.15)
    primary_resp = _mapbox_route_response(PRIMARY_GEOM, 170000, 6300, num_routes=2)
    primary_resp["routes"][1]["geometry"] = far1
    handlers = {
        None: primary_resp,
        "motorway": _mapbox_route_response(far2, 175000, 9000),
        "toll": _mapbox_route_response(far3, 176000, 9100),
    }
    result = _run_corridor_route(handlers, monkeypatch=monkeypatch)

    assert result is not None
    assert len(result["alternatives"]) <= 3


def test_corridor_generation_handles_variant_timeout_gracefully(monkeypatch):
    """A hanging exclude=motorway request must not fail the whole response — it should simply
    contribute no corridor, while exclude=toll (which responds fine) still comes through."""
    handlers = {
        None: _mapbox_route_response(PRIMARY_GEOM, 170000, 6300),
        "motorway": "HANG",
        "toll": _mapbox_route_response(DISTINCT_GEOM, 176000, 9100),
    }
    monkeypatch.setattr("providers.real_providers.CORRIDOR_VARIANT_TIMEOUT_SECONDS", 0.05)
    result = _run_corridor_route(handlers, monkeypatch=monkeypatch)

    assert result is not None
    methods = [a["generation_method"] for a in result["alternatives"]]
    assert "exclude_toll" in methods
    assert "exclude_motorway" not in methods


def test_corridor_generation_handles_variant_http_error_gracefully(monkeypatch):
    """An exclude=toll request that raises must not crash the overall route() call."""
    handlers = {
        None: _mapbox_route_response(PRIMARY_GEOM, 170000, 6300),
        "motorway": _mapbox_route_response(DISTINCT_GEOM, 176000, 9100),
        "toll": RuntimeError("Overpass-style outage simulation"),
    }
    result = _run_corridor_route(handlers, monkeypatch=monkeypatch)

    assert result is not None
    methods = [a["generation_method"] for a in result["alternatives"]]
    assert "exclude_motorway" in methods
    assert "exclude_toll" not in methods


def test_primary_failure_returns_none_even_if_corridor_variants_would_succeed(monkeypatch):
    """The primary/standard request is required; if it fails, the whole call fails, regardless
    of whether the optional corridor variants would have worked."""
    handlers = {
        None: RuntimeError("primary request failed"),
        "motorway": _mapbox_route_response(DISTINCT_GEOM, 176000, 9100),
        "toll": _mapbox_route_response(NEAR_DUPLICATE_GEOM, 171000, 6400),
    }
    result = _run_corridor_route(handlers, monkeypatch=monkeypatch)
    assert result is None


def test_corridor_generation_discards_unreasonably_long_detour(monkeypatch):
    """A geometrically distinct but absurdly long detour must not be manufactured as an option."""
    # Primary ~106 mi; make the "distinct" exclude=motorway candidate ~4x longer (well beyond
    # the default max detour ratio) despite being geometrically far from the primary.
    handlers = {
        None: _mapbox_route_response(PRIMARY_GEOM, 170000, 6300),
        "motorway": _mapbox_route_response(DISTINCT_GEOM, 170000 * 4, 30000),
        "toll": _mapbox_route_response(NEAR_DUPLICATE_GEOM, 171000, 6400),
    }
    result = _run_corridor_route(handlers, monkeypatch=monkeypatch)

    assert result is not None
    methods = [a["generation_method"] for a in result["alternatives"]]
    assert "exclude_motorway" not in methods  # discarded for being an unreasonable detour


def test_corridor_generation_preserves_stops_in_every_concurrent_request(monkeypatch):
    """Required user-entered stops must appear in the coordinate chain for the standard request
    AND both exclude variants — never dropped for corridor-generation calls."""
    handlers = {
        None: _mapbox_route_response(PRIMARY_GEOM, 170000, 6300),
        "motorway": _mapbox_route_response(DISTINCT_GEOM, 176000, 9100),
        "toll": _mapbox_route_response(NEAR_DUPLICATE_GEOM, 171000, 6400),
    }
    captured_calls = []
    stops = [{"lat": 27.8, "lon": -81.0}]
    result = _run_corridor_route(handlers, waypoints=stops, captured_calls=captured_calls, monkeypatch=monkeypatch)

    assert result is not None
    assert len(captured_calls) == 3  # standard + motorway + toll
    expected_chain = f"{OKEE[1]},{OKEE[0]};-81.0,27.8;{ORL[1]},{ORL[0]}"
    for call in captured_calls:
        assert call["url"].endswith(expected_chain)


def test_corridor_generation_opt_out_preserves_legacy_single_request(monkeypatch):
    """Without generate_corridors, behavior (and request count) is exactly as before — only the
    standard request fires, capped at Mapbox's own up to-2 native alternatives."""
    handlers = {None: _mapbox_route_response(PRIMARY_GEOM, 170000, 6300, num_routes=3)}
    captured_calls = []
    monkeypatch.setattr("providers.real_providers.MAPBOX_ACCESS_TOKEN", "x")
    monkeypatch.setattr("providers.real_providers.httpx.AsyncClient", make_scripted_client(handlers, captured_calls))
    provider = MapboxDirectionsProvider()
    result = asyncio.run(provider.route({"lat": OKEE[0], "lon": OKEE[1]}, {"lat": ORL[0], "lon": ORL[1]}, None, None))

    assert result is not None
    assert len(captured_calls) == 1  # no corridor-variant requests fired at all
    assert len(result["alternatives"]) == 2  # legacy cap preserved


def test_corridor_generation_runs_concurrently_not_sequentially(monkeypatch):
    """Measures actual wall-clock time: 3 requests each taking ~50ms should complete in
    roughly one request's worth of time, not three times that, confirming real concurrency."""
    delay = 0.05

    async def _delayed(payload):
        await asyncio.sleep(delay)
        return payload

    class DelayedScriptedClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url, params=None):
            exclude = (params or {}).get("exclude")
            payload = {
                None: _mapbox_route_response(PRIMARY_GEOM, 170000, 6300),
                "motorway": _mapbox_route_response(DISTINCT_GEOM, 176000, 9100),
                "toll": _mapbox_route_response(NEAR_DUPLICATE_GEOM, 171000, 6400),
            }[exclude]
            await asyncio.sleep(delay)
            return _FakeResp(payload)

    monkeypatch.setattr("providers.real_providers.MAPBOX_ACCESS_TOKEN", "x")
    monkeypatch.setattr("providers.real_providers.httpx.AsyncClient", DelayedScriptedClient)
    provider = MapboxDirectionsProvider()

    start = time.perf_counter()
    result = asyncio.run(provider.route(
        {"lat": OKEE[0], "lon": OKEE[1]}, {"lat": ORL[0], "lon": ORL[1]}, None, {"generate_corridors": True}
    ))
    elapsed = time.perf_counter() - start

    assert result is not None
    assert elapsed < delay * 2.5  # well under the ~0.15s a sequential run would take


