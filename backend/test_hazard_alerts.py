import datetime

import pytest

from backend.server import (
    analyze_route_conditions,
    derive_road_condition,
    TurnByTurnStep,
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
    assert alert.hazard_id, "Hazard ID should be populated"
    assert alert.rationale, "Rationale should be populated"
    assert alert.end_mile and alert.end_mile >= alert.distance_miles
    assert alert.hazard_schema_version == 1


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
    assert rain_alerts[0].hazard_id, "Hazard ID should exist for merged alert"
    assert rain_alerts[0].end_mile and rain_alerts[0].end_mile >= rain_alerts[0].distance_miles
    assert rain_alerts[0].hazard_schema_version == 1


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


def test_schema_expectations():
    waypoints = [make_wp(0), make_wp(5, temp=31, conditions="rain"), make_wp(10, temp=31, conditions="rain")]
    steps = [
        TurnByTurnStep(
            instruction="Continue",
            distance_miles=20,
            duration_minutes=20,
            road_name="I-5",
            maneuver="straight",
            road_condition=None,
            weather_at_step=None,
            temperature=None,
            has_alert=False,
            start_distance_miles=0,
            end_distance_miles=20,
        )
    ]
    alerts = generate_hazard_alerts(
        waypoints,
        datetime.datetime.utcnow(),
        steps,
        total_route_miles=30,
        route_id="test-schema",
    )
    assert alerts, "Expected at least one hazard alert"
    a = alerts[0]
    assert a.hazard_id
    assert a.type
    assert a.alert_level
    assert a.distance_miles is not None
    assert a.span_miles is None or a.span_miles >= 0
    assert a.road_name is not None
    assert a.rationale
    assert a.end_mile is not None
    assert a.hazard_schema_version == 1


def test_hazard_id_determinism():
    waypoints = [make_wp(0), make_wp(5, temp=31, conditions="rain"), make_wp(10, temp=31, conditions="rain")]
    steps = [
        TurnByTurnStep(
            instruction="Continue",
            distance_miles=20,
            duration_minutes=20,
            road_name=" I-5  ",
            maneuver="straight",
            road_condition=None,
            weather_at_step=None,
            temperature=None,
            has_alert=False,
            start_distance_miles=0,
            end_distance_miles=20,
        )
    ]
    alerts1 = generate_hazard_alerts(
        waypoints,
        datetime.datetime.utcnow(),
        steps,
        total_route_miles=30,
        route_id="test-hash-1",
    )
    alerts2 = generate_hazard_alerts(
        waypoints,
        datetime.datetime.utcnow(),
        steps,
        total_route_miles=30,
        route_id="test-hash-2",
    )
    ids1 = {a.hazard_id for a in alerts1}
    ids2 = {a.hazard_id for a in alerts2}
    assert ids1 == ids2, "Hazard IDs should be deterministic across runs"


def test_empty_steps_total_distance_fallback():
    waypoints = [make_wp(0), make_wp(5, temp=30, conditions="Snow")]
    steps = []  # simulate missing/empty turn-by-turn steps
    alerts = generate_hazard_alerts(
        waypoints,
        datetime.datetime.utcnow(),
        steps,
        total_route_miles=0,
        route_id="test-empty-steps",
    )
    # Should not crash and should return at least one hazard (ice/snow)
    assert alerts, "Expected hazard generation even when steps are empty"
    a = alerts[0]
    assert a.road_name is not None
    assert a.hazard_id
    assert a.hazard_schema_version == 1


def test_coverage_gaps_marked_out_of_coverage():
    waypoints = []
    for dist in [0, 50, 100, 150]:
        wp = Waypoint(
            lat=0.0,
            lon=0.0,
            name=f"Mile {dist}",
            distance_from_start=dist,
            eta_minutes=int(dist),
            arrival_time=datetime.datetime.utcnow().isoformat(),
        )
        waypoints.append(WaypointWeather(waypoint=wp, weather=None, alerts=[]))

    summary, worst_condition, reroute_needed, reroute_reason, coverage_segments, coverage_miles = analyze_route_conditions(waypoints)

    assert "limited hazard coverage" in summary.lower()
    assert "hazards detected" not in summary.lower()
    assert coverage_segments == len(waypoints)
    assert coverage_miles >= 149.9
    assert reroute_needed is False

    rc = derive_road_condition(None, [])
    assert rc.condition == "out_of_coverage"


def test_mapbox_route_empty_steps_distance_used():
    # Mapbox route shape: distance at route + leg, but steps empty
    waypoints = [make_wp(0), make_wp(50, temp=30, conditions="Snow"), make_wp(100, temp=28, conditions="Snow")]
    route = {"distance": 160934.4, "legs": [{"steps": [], "distance": 160934.4}]}
    turn_by_turn = []

    total_distance_miles = compute_total_distance_miles(route, turn_by_turn, waypoints)
    assert total_distance_miles == pytest.approx(100.0)

    alerts = generate_hazard_alerts(
        waypoints,
        datetime.datetime.utcnow(),
        turn_by_turn,
        total_route_miles=total_distance_miles,
        route_id="mapbox-empty-steps",
    )

    assert alerts, "Expected hazard generation with Mapbox-style empty steps"
    a = alerts[0]
    assert a.road_name is not None
    assert a.hazard_id
    assert a.hazard_schema_version == 1
