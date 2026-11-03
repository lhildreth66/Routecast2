"""Smart Weather Rerouting Phase 4: HazardExposure.geometry field (map polygon overlay).

Reuses alert geometry already fetched for scoring (zero additional NWS requests). Only ever
attached to confirmed polygon_intersection hazards, never zone-only/uncertain ones, and only
after GeoJSON type/coordinate validation via the same Shapely parser used for scoring.
"""
import datetime as dt

import polyline
import pytest

import server
from server import (
    WeatherAlert,
    WeatherData,
    _sanitize_hazard_geometry,
    evaluate_route_weather_risk,
)


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


# ---------------- _sanitize_hazard_geometry unit tests ---------------- #

def test_valid_polygon_passes_through_for_confirmed_intersection():
    poly = _square(-80.0, 30.75, half_w=0.05)
    assert _sanitize_hazard_geometry(poly, "polygon_intersection") == poly


def test_valid_multipolygon_passes_through():
    multi = {"type": "MultiPolygon", "coordinates": [_square(-80.0, 30.75, 0.05)["coordinates"]]}
    assert _sanitize_hazard_geometry(multi, "polygon_intersection") == multi


def test_zone_only_uncertain_never_gets_geometry_even_if_present():
    poly = _square(-80.0, 30.75, half_w=0.05)
    assert _sanitize_hazard_geometry(poly, "zone_only_uncertain") is None


def test_missing_geometry_returns_none():
    assert _sanitize_hazard_geometry(None, "polygon_intersection") is None


def test_wrong_geojson_type_is_rejected():
    point = {"type": "Point", "coordinates": [-80.0, 30.0]}
    assert _sanitize_hazard_geometry(point, "polygon_intersection") is None


def test_malformed_coordinates_are_rejected_not_crashed():
    bad = {"type": "Polygon", "coordinates": "not-a-list-of-rings"}
    assert _sanitize_hazard_geometry(bad, "polygon_intersection") is None


def test_non_dict_geometry_is_rejected_not_crashed():
    assert _sanitize_hazard_geometry("garbage", "polygon_intersection") is None
    assert _sanitize_hazard_geometry(123, "polygon_intersection") is None


# ---------------- End-to-end wiring through evaluate_route_weather_risk ---------------- #

@pytest.mark.asyncio
async def test_confirmed_intersection_hazard_carries_its_geometry(monkeypatch):
    geometry = _ns_geometry()
    _clear_weather(monkeypatch)
    poly = _square(-80.0, 30.75, half_w=0.05)

    async def fake_alerts(lat, lon):
        return [
            WeatherAlert(
                id="geo1", headline="Severe Thunderstorm Warning", severity="Severe",
                event="Severe Thunderstorm Warning", description="desc", urgency="Immediate",
                geometry=poly,
            )
        ], "ok"

    monkeypatch.setattr(server, "get_noaa_alerts", fake_alerts)

    result = await evaluate_route_weather_risk(1, geometry, 103.6, 120, dt.datetime.utcnow(), "car", False, None)

    exposures = [h for h in result.hazard_exposures if h.exposure_method == "polygon_intersection"]
    assert len(exposures) == 1
    assert exposures[0].geometry == poly


@pytest.mark.asyncio
async def test_zone_only_hazard_never_carries_geometry_end_to_end(monkeypatch):
    """A county-wide Flood Watch with no usable polygon must never show a geometry field,
    even though the route genuinely passes through its zone."""
    geometry = _ns_geometry()
    _clear_weather(monkeypatch)

    async def fake_alerts(lat, lon):
        return [
            WeatherAlert(
                id="zone1", headline="Flood Watch", severity="Moderate",
                event="Flood Watch", description="desc", urgency="Expected",
                geometry=None,  # zone-only — no polygon available from NWS
            )
        ], "ok"

    monkeypatch.setattr(server, "get_noaa_alerts", fake_alerts)

    result = await evaluate_route_weather_risk(1, geometry, 103.6, 120, dt.datetime.utcnow(), "car", False, None)

    zone_only = [h for h in result.hazard_exposures if h.exposure_method == "zone_only_uncertain"]
    assert len(zone_only) == 1
    assert zone_only[0].geometry is None


@pytest.mark.asyncio
async def test_invalid_geometry_from_nws_is_dropped_not_crashed(monkeypatch):
    """Simulates a malformed/invalid NWS polygon (e.g. self-intersecting or malformed
    coordinates in a way Shapely cannot repair) — the route evaluation must still succeed,
    just without a geometry field on that hazard."""
    geometry = _ns_geometry()
    _clear_weather(monkeypatch)
    invalid_poly = {"type": "Polygon", "coordinates": [[[0, 0]]]}  # degenerate ring, too few points

    async def fake_alerts(lat, lon):
        return [
            WeatherAlert(
                id="bad1", headline="Severe Thunderstorm Warning", severity="Severe",
                event="Severe Thunderstorm Warning", description="desc", urgency="Immediate",
                geometry=invalid_poly,
            )
        ], "ok"

    monkeypatch.setattr(server, "get_noaa_alerts", fake_alerts)

    result = await evaluate_route_weather_risk(1, geometry, 103.6, 120, dt.datetime.utcnow(), "car", False, None)

    assert result.uncertain is False  # invalid geometry degrades to zone-only treatment, not a crash
    assert all(h.geometry is None for h in result.hazard_exposures)


@pytest.mark.asyncio
async def test_duplicate_alert_at_multiple_sample_points_yields_exactly_one_geometry_entry(monkeypatch):
    """The same NWS alert commonly appears at several consecutive sample points along its
    zone/polygon — must contribute exactly one hazard_exposures entry (and therefore exactly
    one geometry), never a duplicate per sample point."""
    geometry = _ns_geometry(span_degrees=3.0, n=80)  # long enough to cross many sample points
    _clear_weather(monkeypatch)
    poly = _square(-80.0, 31.0, half_w=1.0)  # wide polygon spanning many sample points

    async def fake_alerts(lat, lon):
        return [
            WeatherAlert(
                id="dup1", headline="Severe Thunderstorm Warning", severity="Severe",
                event="Severe Thunderstorm Warning", description="desc", urgency="Immediate",
                geometry=poly,
            )
        ], "ok"

    monkeypatch.setattr(server, "get_noaa_alerts", fake_alerts)

    result = await evaluate_route_weather_risk(1, geometry, 207.0, 240, dt.datetime.utcnow(), "car", False, None)

    matching = [h for h in result.hazard_exposures if h.alert_id == "dup1"]
    assert len(matching) == 1
    assert matching[0].geometry == poly
