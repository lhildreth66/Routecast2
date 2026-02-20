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
    assert a.road_name
    assert a.span_miles is None or a.span_miles >= 0
    assert a.hazard_id
    assert a.rationale
    assert a.end_mile is not None
    assert a.hazard_schema_version == 2


def test_merge_adjacent_hazards():
    waypoints = [make_wp(10, 45, "heavy rain"), make_wp(15, 45, "heavy rain")]
    alerts = generate_hazard_alerts(
        waypoints,
        datetime.datetime.utcnow(),
        100,
        120,
        "merge",
    )
    rain = [a for a in alerts if a.type == "rain"]
    assert len(rain) == 1
    assert rain[0].hazard_schema_version == 2


def test_road_name_defaults_to_waypoint():
    waypoints = [make_wp(5)]
    alerts = generate_hazard_alerts(
        waypoints,
        datetime.datetime.utcnow(),
        50,
        60,
        "road-name",
    )
    assert alerts
    assert alerts[0].road_name == waypoints[0].waypoint.name


def test_schema_expectations():
    waypoints = [make_wp(0), make_wp(5, 31, "rain"), make_wp(10, 31, "rain")]
    alerts = generate_hazard_alerts(
        waypoints,
        datetime.datetime.utcnow(),
        30,
        40,
        "schema",
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
    waypoints = [make_wp(0), make_wp(5, 31, "rain"), make_wp(10, 31, "rain")]
    ids1 = {a.hazard_id for a in generate_hazard_alerts(
        waypoints, datetime.datetime.utcnow(), 30, 40, "a")}
    ids2 = {a.hazard_id for a in generate_hazard_alerts(
        waypoints, datetime.datetime.utcnow(), 30, 40, "b")}
    assert ids1 == ids2


def test_hazards_without_turn_by_turn():
    waypoints = [make_wp(0), make_wp(5)]
    alerts = generate_hazard_alerts(
        waypoints,
        datetime.datetime.utcnow(),
        0,
        0,
        "no-steps",
    )
    assert alerts
    assert alerts[0].hazard_schema_version == 2


@pytest.mark.asyncio
async def test_mapbox_steps_return_real_road_names(monkeypatch):
    sample_route = {
        "routes": [{
            "legs": [{
                "steps": [{
                    "distance": 1000,
                    "duration": 60,
                    "name": "I-80 E",
                    "maneuver": {"type": "depart"},
                }]
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

    steps = await get_turn_by_turn_directions((0, 0), (1, 1), [make_wp(0)])
    assert isinstance(steps, list)
    if steps:
        assert steps[0].road_name


@pytest.mark.asyncio
async def test_low_resolution_routes_resample_and_generate_segments(monkeypatch):
    encoded = polyline.encode([(0, 0), (0, 6)], precision=6)

    async def fake_route(*a, **k):
        return {
            "geometry": encoded,
            "distance": 600000,
            "duration": 21600,
            "legs": [{"steps": []}],
        }

    monkeypatch.setattr("server.get_mapbox_route", fake_route)

    waypoints = [make_wp(d) for d in range(0, 360, 30)]
    steps = await get_turn_by_turn_directions((0, 0), (6, 0), waypoints)
    assert isinstance(steps, list)

    alerts = generate_hazard_alerts(
        waypoints,
        datetime.datetime.utcnow(),
        372,
        360,
        "low-res",
    )

    road = build_condition_segments(alerts, "road")
    weather = build_condition_segments(alerts, "weather")

    assert road
    assert weather


@pytest.mark.asyncio
async def test_route_weather_handles_missing_waypoints(monkeypatch):
    async def fake_route(*a, **k):
        return {"geometry": None, "distance": 160934.4, "legs": [{"distance": 160934.4}]}

    async def fake_weather(*a, **k):
        return WeatherData(
            temperature=30,
            temperature_unit="F",
            wind_speed="5 mph",
            wind_direction="N",
            conditions="Clear",
            icon="",
            humidity=50,
            is_daytime=True,
            sunrise=None,
            sunset=None,
            hourly_forecast=[],
        )

    monkeypatch.setattr("server.get_mapbox_route", fake_route)
    monkeypatch.setattr("server.get_noaa_weather", fake_weather)
    monkeypatch.setattr("server.get_noaa_alerts", lambda *a, **k: [])
    monkeypatch.setattr("server.reverse_geocode", lambda *a, **k: None)
    monkeypatch.setattr("server.get_turn_by_turn_directions", lambda *a, **k: [])
    monkeypatch.setattr("server.find_rest_stops", lambda *a, **k: [])

    req = RouteRequest(origin="0,0", destination="0,1", departure_time=None, stops=None, waypoints=None)
    resp = await get_route_weather(req)

    assert resp.waypoints
    assert resp.total_distance_miles is not None


def test_hazard_generation_uses_route_distance():
    waypoints = [make_wp(0), make_wp(50), make_wp(100)]
    route = {"distance": 160934.4, "legs": [{"steps": []}]}

    miles = compute_total_distance_miles(route, [], waypoints)
    assert miles == pytest.approx(100.0)

    alerts = generate_hazard_alerts(
        waypoints,
        datetime.datetime.utcnow(),
        miles,
        120,
        "distance",
    )
    assert alerts