import datetime

from backend.server import (
    TurnByTurnStep,
    Waypoint,
    WaypointWeather,
    WeatherData,
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
    steps = [
        TurnByTurnStep(
            instruction="Continue",
            distance_miles=30,
            duration_minutes=30,
            road_name="I-80",
            maneuver="straight",
            road_condition=None,
            weather_at_step=None,
            temperature=None,
            has_alert=False,
            start_distance_miles=0,
            end_distance_miles=30,
        )
    ]
    alerts = generate_hazard_alerts(
        waypoints,
        datetime.datetime.utcnow(),
        steps,
        total_route_miles=100,
        route_id="test-span",
    )
    ice_alerts = [a for a in alerts if a.type == "ice"]
    assert ice_alerts, "Expected ice alert from freezing temperatures"
    alert = ice_alerts[0]
    assert alert.road_name == "I-80"
    assert alert.span_miles and 19.5 <= alert.span_miles <= 20.5


def test_merge_adjacent_hazards():
    waypoints = [make_wp(10, temp=45, conditions="heavy rain"), make_wp(15, temp=45, conditions="heavy rain")]
    steps = [
        TurnByTurnStep(
            instruction="Continue",
            distance_miles=30,
            duration_minutes=30,
            road_name="US-50",
            maneuver="straight",
            road_condition=None,
            weather_at_step=None,
            temperature=None,
            has_alert=False,
            start_distance_miles=0,
            end_distance_miles=30,
        )
    ]
    alerts = generate_hazard_alerts(
        waypoints,
        datetime.datetime.utcnow(),
        steps,
        total_route_miles=100,
        route_id="test-merge",
    )
    rain_alerts = [a for a in alerts if a.type == "rain"]
    assert len(rain_alerts) == 1, "Adjacent rain hazards should merge"
    assert rain_alerts[0].span_miles and rain_alerts[0].span_miles >= 9.5


def test_road_name_fallback():
    waypoints = [make_wp(5)]
    steps = [
        TurnByTurnStep(
            instruction="Continue",
            distance_miles=10,
            duration_minutes=10,
            road_name="",
            maneuver="straight",
            road_condition=None,
            weather_at_step=None,
            temperature=None,
            has_alert=False,
            start_distance_miles=0,
            end_distance_miles=10,
        )
    ]
    alerts = generate_hazard_alerts(
        waypoints,
        datetime.datetime.utcnow(),
        steps,
        total_route_miles=50,
        route_id="test-road",
    )
    ice_alerts = [a for a in alerts if a.type == "ice"]
    assert ice_alerts, "Expected ice alert from freezing temp"
    assert ice_alerts[0].road_name == "Unnamed road"
