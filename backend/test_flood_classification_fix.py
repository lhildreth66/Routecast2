"""Flood alert classification fix: a Flood Watch must not be labeled "Flooding reported"
or scored at the same severity as a Flood Warning. derive_road_condition() now distinguishes
NWS product tiers (Watch/Warning/Emergency/Advisory/unrecognized-but-flood-related) instead of
matching the bare substring "flood" for every tier at once.

This system has no DOT/511 or similar road-closure feed — NWS alerts are zone-level forecasts,
not ground-truth confirmation that a specific road is flooded or closed. These tests only verify
the NWS *product tier* is reported accurately; "confirmed road flooding" and "verified closures"
are intentionally not claimed anywhere in derive_road_condition.
"""
from server import derive_road_condition, WeatherAlert, WeatherData


def _clear_weather():
    return WeatherData(temperature=70, wind_speed="5 mph", conditions="Clear", humidity=40)


def _alert(event, headline=None):
    return WeatherAlert(
        id="a1", event=event, headline=headline or event, severity="Severe",
        description="desc", urgency="Expected",
    )


def test_flood_watch_is_not_labeled_flooding_reported():
    cond = derive_road_condition(_clear_weather(), [_alert("Flood Watch")])
    assert cond.condition == "flood_watch"
    assert cond.label == "FLOOD WATCH"
    assert "reported" not in cond.description.lower()
    assert "not yet confirmed" in cond.description.lower() or "possible" in cond.description.lower()


def test_flood_watch_severity_is_lower_than_warning():
    watch = derive_road_condition(_clear_weather(), [_alert("Flood Watch")])
    warning = derive_road_condition(_clear_weather(), [_alert("Flood Warning")])
    assert watch.severity < warning.severity
    assert watch.severity < 3  # below the legacy reroute-trigger threshold
    assert warning.severity == 4


def test_flash_flood_watch_is_treated_as_watch_tier():
    cond = derive_road_condition(_clear_weather(), [_alert("Flash Flood Watch")])
    assert cond.condition == "flood_watch"
    assert cond.severity < 3


def test_flood_warning_is_not_weakened():
    cond = derive_road_condition(_clear_weather(), [_alert("Flood Warning")])
    assert cond.condition == "flooded"
    assert cond.severity == 4
    assert cond.label == "FLOOD WARNING"


def test_flash_flood_warning_is_not_weakened():
    cond = derive_road_condition(_clear_weather(), [_alert("Flash Flood Warning")])
    assert cond.severity == 4
    assert cond.condition == "flooded"


def test_flood_emergency_is_treated_as_warning_tier():
    cond = derive_road_condition(_clear_weather(), [_alert("Flash Flood Emergency")])
    assert cond.severity == 4


def test_flood_advisory_is_mildest_tier():
    cond = derive_road_condition(_clear_weather(), [_alert("Flood Advisory")])
    assert cond.condition == "flood_advisory"
    assert cond.severity == 1
    assert "reported" not in cond.description.lower()


def test_warning_takes_precedence_over_watch_when_both_present():
    cond = derive_road_condition(
        _clear_weather(),
        [_alert("Flood Watch"), _alert("Flood Warning")],
    )
    assert cond.severity == 4
    assert cond.condition == "flooded"


def test_unrecognized_flood_product_still_flagged_but_not_overclaimed():
    """A flood-related product that doesn't match Watch/Warning/Advisory wording exactly
    (e.g. a Flood Statement) must never be silently dropped, but also must not be treated
    as confirmed/imminent without more specific wording."""
    cond = derive_road_condition(_clear_weather(), [_alert("Flood Statement")])
    assert "flood" in cond.condition
    assert cond.severity < 4
    assert "reported" not in cond.description.lower()


def test_non_flood_alert_is_unaffected():
    cond = derive_road_condition(_clear_weather(), [_alert("Severe Thunderstorm Warning")])
    assert cond.condition != "flooded"
    assert cond.condition != "flood_watch"
