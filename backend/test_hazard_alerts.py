import datetime

import pytest
import polyline

from server import (
    analyze_route_conditions,
    derive_road_condition,
    build_condition_segments,
    get_turn_by_turn_directions,
    get_route_weather,
    RouteRequest,
    Waypoint,
    WaypointWeather,
    WeatherData,
    compute_total_distance_miles,
    generate_hazard_alerts,
)


def make_wp(distance: float, temp: int = 30, conditions: str = "Snow") -> WaypointWeather:
    wp = Waypoint(
        lat=0.0,
        lon=0.0,
        name=f"Mile {int(distance)}",
        distance_from_start=distance,
        eta_minutes=int(distance),
        arrival_time=datetime.datetime.utcnow().isoformat(),
    )
    weather = WeatherData(
        temperature=temp,
        temperature_unit="F",
        wind_speed="5 mph",
        wind_direction="N",
        conditions=conditions,
        icon="",
        humidity=50,
        is_daytime=True,
        sunrise=None,
        sunset=None,
        hourly_forecast=[],
    )
    return WaypointWeather(waypoint=wp, weather=weather, alerts=[])


def test_span_computation_and_clamp():
    waypoints = [make_wp(0), make_wp(10), make_wp(20)]
    alerts = generate_hazard_alerts(
        waypoints,
        datetime.datetime.utcnow(),
        total_route_miles=100,
        total_route_minutes=120,
        route_id="test-span",
    )
    ice_alerts = [a for a in alerts if a.type == "ice"]
    assert ice_alerts
    a = ice_alerts[0]
    assert a.road_name == waypoints[0].waypoint.name
    assert a.span_miles and 19.5 <= a.span_miles <= 20.5
    assert a.hazard_id
    assert a.rationale
    assert a.end_mile >= a.distance_miles
    assert a.hazard_schema_version == 2


def test_merge_adjacent_hazards():
    waypoints = [make_wp(10, 45, "heavy rain"), make_wp(15, 45, "heavy rain")]
    alerts = generate_hazard_alerts(
        waypoints,
        datetime.datetime.utcnow(),
        total_route_miles=100,
        total_route_minutes=120,
        route_id="test-merge",
    )
    rain = [a for a in alerts if a.type == "rain"]
    assert len(rain) == 1
    assert rain[0].span_miles >= 9.5
    assert rain[0].hazard_schema_version == 2


def test_road_name_defaults_to_waypoint():
    alerts = generate_hazard_alerts(
        [make_wp(5)],
        datetime.datetime.utcnow(),
        50,
        60,
        "test-road",
    )
    assert alerts[0].road_name == "Mile 5"


def test_schema_expectations():
    alerts = generate_hazard_alerts(
        [make_wp(0), make_wp(5, 31, "rain"), make_wp(10, 31, "rain")],
        datetime.datetime.utcnow(),
        30,
        40,
        "test-schema",
    )
    a = alerts[0]
    assert a.hazard_id
    assert a.type
    assert a.alert_level
    assert a.distance_miles is not None
    assert a.road_name
    assert a.rationale
    assert a.end_mile is not None
    assert a.hazard_schema_version == 2


def test_hazard_id_determinism():
    wp = [make_wp(0), make_wp(5, 31, "rain"), make_wp(10, 31, "rain")]
    a1 = generate_hazard_alerts(wp, datetime.datetime.utcnow(), 30, 40, "a")
    a2 = generate_hazard_alerts(wp, datetime.datetime.utcnow(), 30, 40, "b")
    assert {x.hazard_id for x in a1} == {x.hazard_id for x in a2}


def test_hazards_without_turn_by_turn():
    alerts = generate_hazard_alerts(
        [make_wp(0), make_wp(5, 30, "Snow")],
        datetime.datetime.utcnow(),
        0,
        0,
        "test-empty",
    )
    assert alerts
    assert alerts[0].hazard_schema_version == 2


@pytest.mark.asyncio
async def test_mapbox_steps_return_real_road_names(monkeypatch):
    sample_route = {
        "routes": [{
            "distance": 16093.44,
            "legs": [{
                "steps": [
                    {"distance": 8046.72, "duration": 600, "name": "I-80 E"},
                    {"distance": 8046.72, "duration": 700, "name": "US-20"},
                ]
            }]
        }],
        "code": "Ok",
    }

    class FakeResp:
        status_code = 200
        def json(self): return sample_route

    class FakeClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def get(self, *a, **k): return FakeResp()

    monkeypatch.setattr("server.MAPBOX_ACCESS_TOKEN", "x")
    monkeypatch.setattr("server.httpx.AsyncClient", FakeClient)

    steps = await get_turn_by_turn_directions((0,0),(1,1),[make_wp(0),make_wp(5)])
    assert steps
    assert steps[0].road_name not in {"Route", "Unnamed road"}


@pytest.mark.asyncio
async def test_low_resolution_routes_resample_and_generate_segments(monkeypatch):
    encoded = polyline.encode([(0,0),(0,6)], precision=6)

    async def fake_route(*a, **k):
        return {"geometry": encoded, "distance": 600000, "legs":[{"distance":600000}]}

    monkeypatch.setattr("server.get_mapbox_route", fake_route)
    monkeypatch.setattr("server.get_turn_by_turn_directions", lambda *a, **k: [])

    wp = [make_wp(i,25,"Snow") for i in range(0,360,30)]
    alerts = generate_hazard_alerts(wp, datetime.datetime.utcnow(), 372, 360, "low-res")
    assert alerts


@pytest.mark.asyncio
async def test_route_weather_handles_missing_waypoints(monkeypatch):
    async def fake_route(*a, **k):
        return {"geometry": None, "distance": 160934.4, "legs":[{"distance":160934.4}]}

    async def fake_weather(*a, **k):
        return WeatherData(30,"F","5","N","Clear","",50,True,None,None,[])

    monkeypatch.setattr("server.get_mapbox_route", fake_route)
    monkeypatch.setattr("server.get_noaa_weather", fake_weather)
    monkeypatch.setattr("server.get_noaa_alerts", lambda *a, **k: [])
    monkeypatch.setattr("server.reverse_geocode", lambda *a, **k: None)
    monkeypatch.setattr("server.get_turn_by_turn_directions", lambda *a, **k: [])
    monkeypatch.setattr("server.find_rest_stops", lambda *a, **k: [])

    req = RouteRequest("0,0","0,1",None,None,None)
    resp = await get_route_weather(req)
    assert resp.waypoints