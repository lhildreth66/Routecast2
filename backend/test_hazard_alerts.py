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


# ---------------- BASIC HAZARD TESTS ---------------- #

def test_span_computation_and_clamp():
    waypoints = [make_wp(0), make_wp(10), make_wp(20)]
    alerts = generate_hazard_alerts(
        waypoints,
        datetime.datetime.utcnow(),
        100,
        120,
        "span",
    )
    assert alerts
    assert alerts[0].hazard_schema_version == 2


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


# ---------------- MAPBOX STEP TEST ---------------- #

@pytest.mark.asyncio
async def test_mapbox_steps_return_real_road_names(monkeypatch):
    sample_route = {
        "routes": [
            {
                "legs": [
                    {
                        "steps": [
                            {
                                "distance": 1000,
                                "duration": 60,
                                "name": "I-80 E",
                                "maneuver": {"type": "depart"},
                            }
                        ]
                    }
                ]
            }
        ],
        "code": "Ok",
    }

    class FakeResp:
        status_code = 200

        def json(self):
            return sample_route

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, *a, **k):
            return FakeResp()

    monkeypatch.setattr("server.MAPBOX_ACCESS_TOKEN", "x")
    monkeypatch.setattr("server.httpx.AsyncClient", FakeClient)

    # Make sure we pass WaypointWeather list (this function expects waypoint-weather objects)
    waypoints = [make_wp(0), make_wp(5)]
    steps = await get_turn_by_turn_directions((0, 0), (1, 1), waypoints)

    # Must not be empty
    assert steps, "Expected steps from mocked Mapbox response"
    assert steps[0].road_name


# ---------------- LOW RES ROUTE TEST ---------------- #

@pytest.mark.asyncio
async def test_low_resolution_routes_resample_and_generate_segments(monkeypatch):
    encoded = polyline.encode([(0, 0), (0, 6)], precision=6)

    sample_route = {
        "routes": [
            {
                "distance": 600000,
                "duration": 21600,
                "geometry": encoded,
                "legs": [{"steps": []}],
            }
        ],
        "code": "Ok",
    }

    class FakeResp:
        status_code = 200

        def json(self):
            return sample_route

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, *a, **k):
            return FakeResp()

    monkeypatch.setattr("server.MAPBOX_ACCESS_TOKEN", "x")
    monkeypatch.setattr("server.httpx.AsyncClient", FakeClient)

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

    # FIX: category is keyword-only
    road = build_condition_segments(alerts, category="road")
    weather = build_condition_segments(alerts, category="weather")
    assert road or weather


# ---------------- ROUTE WEATHER TEST ---------------- #

@pytest.mark.asyncio
async def test_route_weather_handles_missing_waypoints(monkeypatch):
    encoded = polyline.encode([(0.0, 0.0), (0.0, 1.0)], precision=6)

    async def fake_route(*args, **kwargs):
        return {
            "geometry": encoded,  # provide geometry so waypoint synthesis works cleanly
            "distance": 160934.4,
            "duration": 3600,
            "legs": [{"distance": 160934.4}],
        }

    async def fake_weather(*args, **kwargs):
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

    async def fake_alerts(*args, **kwargs):
        return []

    async def fake_reverse(*args, **kwargs):
        return None

    async def fake_turn(*args, **kwargs):
        return []

    # IMPORTANT: must be async because server awaits it
    async def fake_rest(*args, **kwargs):
        return []

    monkeypatch.setattr("server.get_mapbox_route", fake_route)
    monkeypatch.setattr("server.get_noaa_weather", fake_weather)
    monkeypatch.setattr("server.get_noaa_alerts", fake_alerts)
    monkeypatch.setattr("server.reverse_geocode", fake_reverse)
    monkeypatch.setattr("server.get_turn_by_turn_directions", fake_turn)
    monkeypatch.setattr("server.find_rest_stops", fake_rest)

    # FIX: RouteRequest should be constructed with keyword args only (Pydantic v2)
    req = RouteRequest(
        origin="0,0",
        destination="0,1",
        departure_time=None,
        stops=None,
        waypoints=None,
    )

    resp = await get_route_weather(req)

    assert resp.waypoints
    assert resp.total_distance_miles is not None