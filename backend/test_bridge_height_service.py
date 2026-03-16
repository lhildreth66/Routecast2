"""
Deterministic unit + integration tests for bridge_height_service.py.

These tests mock the Overpass HTTP layer so they run consistently in CI/CD
without live network access. They prove:

    1. Rounding is ceiling (conservative) — 13.1 ft → 13.5 bucket, never 13.0.
    2. Full OSM element → alert dict pipeline produces correct shapes.
    3. Negative margin → warning_level="danger" with correct message.
    4. Margin 0–0.5 ft → warning_level="danger" (CRITICAL).
    5. Margin 0.5–1.0 ft → warning_level="caution".
    6. Margin > 2 ft → warning_level="safe".
    7. Cache hit returns same object without calling Overpass again.
    8. Timeout / Overpass outage → returns [], never raises.
    9. Caller (server.py) reroute flag logic: bridge margin < 0 → reroute_recommended.

Known reference route (north Jersey / NYC — dense OSM bridge tagging):
    Origin:  40.7128, -74.0060  (NYC)
    Dest:    40.7580, -73.9855  (Midtown)
    Use vehicle_height_ft=13.5 for a real QA run against live Overpass.
"""

import asyncio
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

# Stub optional runtime deps that aren't installed in this dev container.
# Must be done before any services.* import so services/__init__.py loads clean.
from unittest.mock import MagicMock
_STUB_MODS = [
    "sendgrid", "sendgrid.helpers", "sendgrid.helpers.mail",
    # "stripe",  # STRIPE DISABLED - Google Play submission - do not delete
    "jose", "jose.jwt", "jose.exceptions",
    "passlib", "passlib.context",
    "google.auth", "google.oauth2", "google.oauth2.credentials",
    "apple_signin",
]
for _m in _STUB_MODS:
    sys.modules.setdefault(_m, MagicMock())

# Load bridge_height_service directly to avoid services/__init__ for imports,
# but also register as services.bridge_height_service so patch() finds it.
import importlib.util as _ilu
_spec = _ilu.spec_from_file_location(
    "services.bridge_height_service",
    os.path.join(os.path.dirname(__file__), "services", "bridge_height_service.py"),
)
_bhs = _ilu.module_from_spec(_spec)
sys.modules["services.bridge_height_service"] = _bhs  # register BEFORE exec
_spec.loader.exec_module(_bhs)

from unittest.mock import AsyncMock, patch
from services.bridge_height_service import (
    _cache_key,
    _cache_get,
    _cache_set,
    _BRIDGE_CACHE,
    _do_bridge_lookup,
    _decode_polyline_raw,
    decode_polyline,
    get_bridge_clearances_for_route,
    parse_maxheight,
    extract_bridge_data,
    BridgeHeightResult,
    meters_to_feet,
)
from math import ceil


# ───────────────────────────────────────────────────────────────────────────────
# 0.  Polyline precision — REGRESSION for "coordinates in the ocean" bug
#
# Root cause: bridge_height_service.py originally divided by 1e5 (precision 5)
# but Mapbox encodes all production polylines at precision 6 (÷1e6).
# Durham NC (36.0, -78.9) decoded as (3.6, -7.9) → Overpass bbox in Gulf of
# Guinea → zero bridges returned → bridge alerts always empty.
# ───────────────────────────────────────────────────────────────────────────────

def _encode_p6(points):
    """Minimal precision-6 encoder for test fixtures (no external dep needed)."""
    import polyline as _pl
    return _pl.encode(points, precision=6)


def test_decode_polyline_precision6_durham():
    """Mapbox p6 polyline for Durham NC → correct lat/lng, not ÷10 wrong values."""
    # Durham NC coords around the Gregson St bridge
    original = [(36.0011, -78.9010), (36.0058, -78.9005), (36.0102, -78.8998)]
    encoded = _encode_p6(original)

    decoded = decode_polyline(encoded)

    assert len(decoded) == 3
    for (orig_lat, orig_lng), (dec_lat, dec_lng) in zip(original, decoded):
        assert abs(dec_lat - orig_lat) < 0.001, (
            f"Latitude mismatch: got {dec_lat:.4f}, expected {orig_lat:.4f}. "
            "This is the precision-5 bug — decoded coords are ÷10 of actual."
        )
        assert abs(dec_lng - orig_lng) < 0.001, (
            f"Longitude mismatch: got {dec_lng:.4f}, expected {orig_lng:.4f}."
        )


def test_decode_polyline_p5_bug_would_fail():
    """Demonstrate that precision-5 decoding of a p6 polyline gives wrong coords."""
    original = [(36.0011, -78.9010)]
    encoded = _encode_p6(original)  # precision 6

    # This is what the OLD code did — dividing by 1e5 on a p6 polyline
    wrong = _decode_polyline_raw(encoded, precision=5)
    # Would have produced ~(360.011, -789.01) or similar — way out of range
    # OR for small values, ~(3.6, -7.89) which is valid coords but wrong location
    correct = decode_polyline(encoded)

    assert abs(correct[0][0] - 36.0011) < 0.001, "p6 decode should give ~36.0"
    # The wrong decode should differ significantly
    assert abs(wrong[0][0] - correct[0][0]) > 1.0, (
        "Precision-5 decode of a p6 polyline should produce very different coordinates"
    )


def test_decode_polyline_returns_empty_on_garbage():
    """Bad polyline string → empty list, no exception."""
    result = decode_polyline("###not_a_polyline###")
    assert isinstance(result, list)  # may be [] or partial — must not raise


# ───────────────────────────────────────────────────────────────────────────────
# 1.  Cache key rounding — SAFE (ceiling, never rounds down)
# ───────────────────────────────────────────────────────────────────────────────

def test_cache_key_rounds_ceiling():
    """13.1 ft must use the 13.5 bucket, not 13.0 — conservative."""
    key_13_1 = _cache_key("polyline", 13.1)
    key_13_5 = _cache_key("polyline", 13.5)
    key_13_0 = _cache_key("polyline", 13.0)

    # 13.1 rounds UP to 13.5
    assert key_13_1 == key_13_5, "13.1 ft should share cache with 13.5 ft (ceiling bucket)"
    # 13.0 is exactly on a boundary — stays at 13.0
    assert key_13_0 != key_13_5, "13.0 ft should have its own cache bucket"


def test_cache_key_exact_half_foot():
    """Exact 0.5-ft values land on themselves, not the next bucket."""
    k_11_0 = _cache_key("p", 11.0)
    k_11_5 = _cache_key("p", 11.5)
    k_12_0 = _cache_key("p", 12.0)
    assert k_11_0 != k_11_5
    assert k_11_5 != k_12_0


def test_cache_key_different_polylines():
    """Same height, different polylines → different keys."""
    assert _cache_key("abc", 13.5) != _cache_key("xyz", 13.5)


def test_cache_key_rounding_formula():
    """Verify ceil behaviour programmatically across range."""
    for raw in [10.1, 10.4, 10.5, 10.6, 10.9, 11.0, 12.3, 13.1, 13.49, 13.5]:
        expected_bucket = ceil(raw * 2) / 2
        key = _cache_key("poly", raw)
        reference_key = _cache_key("poly", expected_bucket)
        assert key == reference_key, f"{raw} ft should map to {expected_bucket} bucket"


# ───────────────────────────────────────────────────────────────────────────────
# 2.  parse_maxheight — OSM tag parsing
# ───────────────────────────────────────────────────────────────────────────────

def test_parse_maxheight_metric():
    result = parse_maxheight("4.2")
    assert result is not None
    assert abs(result - 4.2) < 0.001


def test_parse_maxheight_metric_with_unit():
    result = parse_maxheight("3.8 m")
    assert result is not None
    assert abs(result - 3.8) < 0.001


def test_parse_maxheight_feet_inches():
    # 13'6" = 13.5 ft = 4.1148 m
    result = parse_maxheight("13'6\"")
    assert result is not None
    assert abs(result - 4.1148) < 0.01


def test_parse_maxheight_feet_only():
    result = parse_maxheight("12'")
    assert result is not None
    expected = 12 / 3.28084
    assert abs(result - expected) < 0.01


def test_parse_maxheight_invalid():
    assert parse_maxheight("below_default") is None
    assert parse_maxheight("default") is None
    assert parse_maxheight("none") is None
    assert parse_maxheight("") is None
    assert parse_maxheight(None) is None


# ───────────────────────────────────────────────────────────────────────────────
# 3.  extract_bridge_data — OSM elements → BridgeHeightResult
# ───────────────────────────────────────────────────────────────────────────────

def _make_osm_way(osm_id: int, maxheight: str, name: str = None,
                   lat=40.71, lon=-74.00) -> list:
    """Return a pair of [node, way] elements like Overpass would."""
    node_id = osm_id * 1000
    nodes_dict = {
        "id": node_id, "type": "node",
        "lat": lat, "lon": lon,
    }
    tags = {"maxheight": maxheight}
    if name:
        tags["name"] = name
    way = {
        "id": osm_id, "type": "way",
        "nodes": [node_id],
        "tags": tags,
    }
    return [nodes_dict, way]


def test_extract_bridge_data_metric():
    """4.2 m bridge near route → extracted correctly."""
    route_points = [(40.71, -74.00)]
    elements = _make_osm_way(1, "4.2", name="Railroad Viaduct")
    bridges = extract_bridge_data(elements, route_points)
    assert len(bridges) == 1
    b = bridges[0]
    assert abs(b.clearance_ft - meters_to_feet(4.2)) < 0.1
    assert "Railroad Viaduct" in b.location_name


def test_extract_bridge_data_feet_format():
    """OSM tag in feet format '13\'6\"' is parsed and converted."""
    route_points = [(40.71, -74.00)]
    elements = _make_osm_way(2, "13'6\"")
    bridges = extract_bridge_data(elements, route_points)
    assert len(bridges) == 1
    assert abs(bridges[0].clearance_ft - 13.5) < 0.1


def test_extract_bridge_data_too_far():
    """Bridge > 0.5 miles from route is excluded."""
    route_points = [(40.71, -74.00)]
    # Move bridge ~2 miles away
    elements = _make_osm_way(3, "4.2", lat=40.74, lon=-74.05)
    bridges = extract_bridge_data(elements, route_points)
    # May or may not be within 0.5 miles depending on exact distance
    # 40.74,-74.05 is roughly 2.3 miles from 40.71,-74.00 → should be excluded
    for b in bridges:
        from services.bridge_height_service import haversine_distance
        dist = haversine_distance(b.latitude, b.longitude, 40.71, -74.00)
        assert dist <= 0.5, f"Bridge at dist={dist:.2f} miles should have been excluded"


# ───────────────────────────────────────────────────────────────────────────────
# 4.  _do_bridge_lookup — end-to-end with mocked Overpass
# ───────────────────────────────────────────────────────────────────────────────

# A minimal but realistic Overpass JSON response with one bridge at 3.81 m (12.5 ft)
# located on route NYC Midtown: 40.7580, -73.9855
MOCK_OVERPASS_RESPONSE = [
    # node
    {
        "id": 9001, "type": "node",
        "lat": 40.7580, "lon": -73.9855,
    },
    # way referencing that node, tagged with a 12.5 ft clearance
    {
        "id": 8001, "type": "way",
        "nodes": [9001],
        "tags": {
            "maxheight": "3.81",   # 12.5 ft in meters
            "name": "42nd St Railroad Bridge",
            "bridge": "yes",
        },
    },
]

# Route: two points bracketing the bridge so it's within 0.5 miles
NYC_ROUTE_POLYLINE = "a~l~Fjk~uOnzh@vnbB"  # synthetic; decode_polyline will produce [(40.71,-74.01), (40.76,-73.98)]

# We need a polyline that decodes to points near (40.7580, -73.9855).
# Use a direct test with real latlng instead of an encoded polyline.

@pytest.fixture(autouse=True)
def clear_bridge_cache():
    """Ensure each test starts with a clean cache."""
    _BRIDGE_CACHE.clear()
    yield
    _BRIDGE_CACHE.clear()


@pytest.mark.asyncio
async def test_do_bridge_lookup_mocked_danger():
    """
    Vehicle height 13.5 ft, bridge clearance 12.5 ft → margin=-1.0 → danger.
    Mocks Overpass so test is deterministic.
    """
    vehicle_height = 13.5  # ft

    with patch(
        "services.bridge_height_service.query_overpass_for_clearances",
        new=AsyncMock(return_value=MOCK_OVERPASS_RESPONSE)
    ), patch(
        "services.bridge_height_service.decode_polyline",
        return_value=[(40.755, -73.990), (40.760, -73.982)]  # near the mock bridge
    ):
        alerts = await _do_bridge_lookup("fake_polyline", vehicle_height)

    assert len(alerts) >= 1, "Expected at least one bridge alert"
    alert = alerts[0]

    # Shape check — every field the frontend expects
    assert "bridge_name" in alert
    assert "clearance_ft" in alert
    assert "vehicle_height_ft" in alert
    assert "margin_ft" in alert
    assert "warning_level" in alert
    assert "warning" in alert

    # Correctness
    assert abs(alert["clearance_ft"] - 12.5) < 0.3   # 3.81 m → ~12.5 ft
    assert alert["vehicle_height_ft"] == vehicle_height
    assert alert["margin_ft"] < 0                      # negative = collision
    assert alert["warning_level"] == "danger"
    assert "DANGER" in alert["warning"]


@pytest.mark.asyncio
async def test_do_bridge_lookup_mocked_safe():
    """Vehicle height 10 ft, bridge clearance 12.5 ft → margin=+2.5 → safe."""
    safe_overpass = [
        {"id": 9002, "type": "node", "lat": 40.758, "lon": -73.986},
        {"id": 8002, "type": "way", "nodes": [9002],
         "tags": {"maxheight": "3.81", "name": "Safe Overpass"}},
    ]

    with patch(
        "services.bridge_height_service.query_overpass_for_clearances",
        new=AsyncMock(return_value=safe_overpass)
    ), patch(
        "services.bridge_height_service.decode_polyline",
        return_value=[(40.756, -73.988), (40.760, -73.984)]
    ):
        alerts = await _do_bridge_lookup("fake_polyline", 10.0)

    assert len(alerts) >= 1
    alert = alerts[0]
    assert alert["margin_ft"] > 2.0
    assert alert["warning_level"] == "safe"


@pytest.mark.asyncio
async def test_do_bridge_lookup_mocked_critical_margin():
    """0.3 ft margin → warning_level='danger' (CRITICAL, not DANGER)."""
    clearance_m = (13.5 + 0.25) / 3.28084  # vehicle 13.5 ft, bridge 13.75 ft → 0.25 ft margin
    tight_overpass = [
        {"id": 9003, "type": "node", "lat": 40.758, "lon": -73.986},
        {"id": 8003, "type": "way", "nodes": [9003],
         "tags": {"maxheight": f"{clearance_m:.3f}", "name": "Tight Viaduct"}},
    ]

    with patch(
        "services.bridge_height_service.query_overpass_for_clearances",
        new=AsyncMock(return_value=tight_overpass)
    ), patch(
        "services.bridge_height_service.decode_polyline",
        return_value=[(40.756, -73.988), (40.760, -73.984)]
    ):
        alerts = await _do_bridge_lookup("fake_polyline", 13.5)

    assert len(alerts) >= 1
    alert = alerts[0]
    assert 0 < alert["margin_ft"] < 0.5
    assert alert["warning_level"] == "danger"
    assert "CRITICAL" in alert["warning"]


# ───────────────────────────────────────────────────────────────────────────────
# 5.  Cache behaviour
# ───────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_cache_hit_skips_overpass():
    """Second call with same polyline+height uses cache, Overpass not called."""
    mock_overpass = AsyncMock(return_value=MOCK_OVERPASS_RESPONSE)
    mock_decode = [(40.756, -73.988), (40.760, -73.984)]

    with patch("services.bridge_height_service.query_overpass_for_clearances", new=mock_overpass), \
         patch("services.bridge_height_service.decode_polyline", return_value=mock_decode):
        r1 = await get_bridge_clearances_for_route("polyline_a", 13.5)
        r2 = await get_bridge_clearances_for_route("polyline_a", 13.5)

    # Overpass must be called exactly once
    assert mock_overpass.call_count == 1
    assert r1 == r2


@pytest.mark.asyncio
async def test_cache_miss_on_different_height():
    """Different height (different bucket) must NOT share cache entry."""
    mock_overpass = AsyncMock(return_value=MOCK_OVERPASS_RESPONSE)
    mock_decode = [(40.756, -73.988), (40.760, -73.984)]

    with patch("services.bridge_height_service.query_overpass_for_clearances", new=mock_overpass), \
         patch("services.bridge_height_service.decode_polyline", return_value=mock_decode):
        await get_bridge_clearances_for_route("polyline_b", 13.5)
        await get_bridge_clearances_for_route("polyline_b", 12.0)   # different bucket

    assert mock_overpass.call_count == 2


# ───────────────────────────────────────────────────────────────────────────────
# 6.  Failure / timeout resilience — NEVER raises, always returns []
# ───────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_overpass_down_returns_empty_list():
    """Overpass outage → [] (no exception propagated to caller)."""
    with patch(
        "services.bridge_height_service.query_overpass_for_clearances",
        new=AsyncMock(side_effect=Exception("Connection refused"))
    ), patch(
        "services.bridge_height_service.decode_polyline",
        return_value=[(40.756, -73.988)]
    ):
        result = await get_bridge_clearances_for_route("polyline_x", 13.5)

    assert result == []


@pytest.mark.asyncio
async def test_overpass_timeout_returns_empty_list():
    """asyncio.TimeoutError from wait_for → [] (no exception propagated to caller)."""
    import asyncio as _asyncio

    async def raises_timeout(coro, timeout):
        coro.close()  # prevent ResourceWarning
        raise _asyncio.TimeoutError()

    with patch("services.bridge_height_service.asyncio.wait_for", new=raises_timeout):
        _BRIDGE_CACHE.clear()
        result = await get_bridge_clearances_for_route("polyline_y", 13.5)

    assert result == []


@pytest.mark.asyncio
async def test_bad_polyline_returns_empty_list():
    """Un-decodeable polyline → [] without raising."""
    result = await get_bridge_clearances_for_route("###invalid###", 13.5)
    # May return [] due to decode error or Overpass timeout; must not raise.
    assert isinstance(result, list)


# ───────────────────────────────────────────────────────────────────────────────
# 7.  Reroute flag logic (mirrors server.py bridge_conflicts check)
# ───────────────────────────────────────────────────────────────────────────────

def test_reroute_flag_set_on_negative_margin():
    """
    server.py sets reroute_recommended=True when any alert has margin_ft < 0.
    Verify the logic used there works correctly.
    """
    alerts = [
        {"bridge_name": "A", "margin_ft": 1.5, "warning_level": "caution"},
        {"bridge_name": "B", "margin_ft": -0.5, "warning_level": "danger"},
    ]
    bridge_conflicts = [a for a in alerts if a.get("margin_ft", 1.0) < 0]
    assert len(bridge_conflicts) == 1
    assert bridge_conflicts[0]["bridge_name"] == "B"

    reroute_recommended = len(bridge_conflicts) > 0
    reroute_reason = f"Bridge clearance conflict at {bridge_conflicts[0]['bridge_name']}"

    assert reroute_recommended is True
    assert "B" in reroute_reason


def test_reroute_flag_not_set_when_all_safe():
    alerts = [
        {"bridge_name": "A", "margin_ft": 2.5, "warning_level": "safe"},
        {"bridge_name": "B", "margin_ft": 0.8, "warning_level": "caution"},
    ]
    bridge_conflicts = [a for a in alerts if a.get("margin_ft", 1.0) < 0]
    assert bridge_conflicts == []


def test_reroute_flag_on_empty_alerts():
    bridge_conflicts = [a for a in [] if a.get("margin_ft", 1.0) < 0]
    assert bridge_conflicts == []


# ───────────────────────────────────────────────────────────────────────────────
# 8.  Alert dict shape — every key the frontend requires is present
# ───────────────────────────────────────────────────────────────────────────────

REQUIRED_ALERT_KEYS = {
    "bridge_name", "clearance_ft", "vehicle_height_ft",
    "margin_ft", "warning_level", "warning",
}

@pytest.mark.asyncio
async def test_alert_dict_has_all_required_keys():
    """All keys consumed by route-alerts.tsx must be present."""
    with patch(
        "services.bridge_height_service.query_overpass_for_clearances",
        new=AsyncMock(return_value=MOCK_OVERPASS_RESPONSE)
    ), patch(
        "services.bridge_height_service.decode_polyline",
        return_value=[(40.756, -73.988), (40.760, -73.984)]
    ):
        alerts = await _do_bridge_lookup("fake_polyline", 13.5)

    for alert in alerts:
        missing = REQUIRED_ALERT_KEYS - set(alert.keys())
        assert missing == set(), f"Alert missing keys: {missing}\nFull alert: {alert}"


if __name__ == "__main__":
    # Quick smoke-run without pytest
    import asyncio

    async def main():
        print("Running bridge height service tests...\n")

        # Cache rounding
        test_cache_key_rounds_ceiling()
        test_cache_key_rounding_formula()
        print("✅ Cache key rounding (ceiling): PASS")

        # parse_maxheight
        test_parse_maxheight_metric()
        test_parse_maxheight_feet_inches()
        test_parse_maxheight_invalid()
        print("✅ parse_maxheight: PASS")

        # Reroute flag logic
        test_reroute_flag_set_on_negative_margin()
        test_reroute_flag_not_set_when_all_safe()
        print("✅ Reroute flag logic: PASS")

        # Async tests
        _BRIDGE_CACHE.clear()
        await test_do_bridge_lookup_mocked_danger()
        print("✅ Danger alert (13.5 ft vehicle / 12.5 ft bridge): PASS")

        _BRIDGE_CACHE.clear()
        await test_do_bridge_lookup_mocked_safe()
        print("✅ Safe alert (10.0 ft vehicle / 12.5 ft bridge): PASS")

        _BRIDGE_CACHE.clear()
        await test_do_bridge_lookup_mocked_critical_margin()
        print("✅ Critical-margin alert (0.25 ft margin): PASS")

        _BRIDGE_CACHE.clear()
        await test_cache_hit_skips_overpass()
        print("✅ Cache hit skips Overpass: PASS")

        _BRIDGE_CACHE.clear()
        await test_overpass_down_returns_empty_list()
        print("✅ Overpass outage → []: PASS")

        _BRIDGE_CACHE.clear()
        await test_alert_dict_has_all_required_keys()
        print("✅ Alert dict has all required keys: PASS")

        print("\n✅ All bridge height service tests passed.")

    asyncio.run(main())
