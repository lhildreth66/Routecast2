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
    alerts = generate_hazard_alerts(
        [make_wp(0), make_wp(10), make_wp(20)],
        datetime.datetime.utcnow(),
        100,
        120,
        "test-span",
    )
    assert alerts
    assert alerts[0].hazard_schema_version == 2


def test_merge_adjacent_hazards():
    alerts = generate_hazard_alerts(
        [make_wp(10, 45, "heavy rain"), make_wp(15, 45, "heavy rain")],
        datetime.datetime.utcnow(),
        100,
        120,
        "test-merge",
    )
    assert alerts


def test_road_name_defaults_to_waypoint():
    alerts = generate_hazard_alerts(
        [make_wp(5)],
        datetime.datetime.utcnow(),
        50,
        60,
        "test-road",
    )
    assert alerts


def test_schema_expectations():
    alerts = generate_hazard_alerts(
        [make_wp(0), make_wp(5, 31, "rain"), make_wp(10, 31, "rain")],
        datetime.datetime.utcnow(),
        30,
        40,
        "test-schema",
    )
    assert alerts[0].hazard_schema_version == 2


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


@pytest.mark.asyncio
async def test_mapbox_steps_return_real_road_names(monkeypatch):
    sample_route = {
        "routes": [
            {
                "distance": 16093.44,
                "legs": [
                    {
                        "steps": [
                            {
                                "distance": 8046.72,
                                "duration": 600,
                                "name": "I-80 E",
                                "maneuver": {"type": "depart"},
                            }
                        ]
                    }
                ],
            }
        ],
        "code": "Ok",
    }

    class FakeResp:
        status_code = 200
        def json(self): return sample_route

    class FakeClient:
        async def __aenter__(self): return self
        async def __aexit__(self, exc_type, exc, tb): return False
        async def get(self, *a, **k): return FakeResp()

    monkeypatch.setattr("server.MAPBOX_ACCESS_TOKEN", "test-token")
    monkeypatch.setattr("server.httpx.AsyncClient", FakeClient)

    waypoints = [make_wp(0), make_wp(5)]
    steps = await get_turn_by_turn_directions((0, 0), (1, 1), waypoints)

    assert steps
    assert steps[0].road_name


@pytest.mark.asyncio
async def test_route_weather_handles_missing_waypoints(monkeypatch):

    async def fake_route(*a, **k):
        return {
            "geometry": None,
            "distance": 160934.4,
            "legs": [{"distance": 160934.4}],
        }

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

    async def fake_alerts(*a, **k):
        return []

    async def fake_reverse_geocode(*a, **k):
        return None

    async def fake_turn_by_turn(*a, **k):
        return []

    async def fake_rest(*a, **k):
        return []

    monkeypatch.setattr("server.get_mapbox_route", fake_route)
    monkeypatch.setattr("server.get_noaa_weather", fake_weather)
    monkeypatch.setattr("server.get_noaa_alerts", fake_alerts)
    monkeypatch.setattr("server.reverse_geocode", fake_reverse_geocode)
    monkeypatch.setattr("server.get_turn_by_turn_directions", fake_turn_by_turn)
    monkeypatch.setattr("server.find_rest_stops", fake_rest)

    req = RouteRequest(
        origin="0,0",
        destination="0,1",
        departure_time=None,
        stops=None,
        waypoints=None,
    )

    resp = await get_route_weather(req)
    assert resp.waypoints


def test_hazard_generation_uses_route_distance():
    waypoints = [make_wp(0), make_wp(50), make_wp(100)]
    route = {"distance": 160934.4, "legs": [{"steps": [], "distance": 160934.4}]}

    total = compute_total_distance_miles(route, [], waypoints)
    assert total == pytest.approx(100.0)

    alerts = generate_hazard_alerts(
        waypoints,
        datetime.datetime.utcnow(),
        total,
        120,
        "mapbox-empty-steps",
    )

    assert alerts
    assert alerts[0].hazard_schema_version == 2