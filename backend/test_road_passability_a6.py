import pytest
from road_passability_a6 import score, PassabilityResult

@pytest.mark.parametrize("precip,slope,temp,soil,expect_low,expect_mud,expect_4x4", [
    # Clay + heavy rain: low score, mud_risk=True, often 4x4 recommended
    (2.0, 12.0, 40, "clay", True, True, True),
    (3.5, 20.0, 45, "clay", True, True, True),
])
def test_clay_heavy_rain(precip, slope, temp, soil, expect_low, expect_mud, expect_4x4):
    res = score(precip, slope, temp, soil)
    assert isinstance(res, PassabilityResult)
    assert res.mud_risk is expect_mud
    assert res.score < 60 if expect_low else res.score >= 60
    assert res.four_by_four_recommended is expect_4x4
    assert any("Mud risk" in r for r in res.reasons)

@pytest.mark.parametrize("precip,slope,temp,soil", [
    # Freeze: ice_risk=True and score reduced
    (0.0, 5.0, 30, "loam"),
    (0.5, 10.0, 31, "sand"),
])
def test_freeze_ice_risk(precip, slope, temp, soil):
    res = score(precip, slope, temp, soil)
    assert res.ice_risk is True
    assert res.score <= 80
    assert any("Ice risk" in r for r in res.reasons)

@pytest.mark.parametrize("precip,slope,temp,soil", [
    # Dry sand on flat road: high score, low risks
    (0.0, 0.0, 60, "sand"),
    (0.1, 2.0, 70, "sand"),
])
def test_dry_sand_flat_high_score(precip, slope, temp, soil):
    res = score(precip, slope, temp, soil)
    assert res.score >= 85
    assert res.mud_risk is False
    assert res.ice_risk is False
    assert res.clearance_need in {"low", "medium"}

@pytest.mark.parametrize("precip,slope,temp,soil", [
    # Input clamping: negative precip/slope
    (-1.0, -5.0, 50, "loam"),
])
def test_input_clamping_negative_values(precip, slope, temp, soil):
    res = score(precip, slope, temp, soil)
    # Should clamp to non-negative precip/slope
    assert res.score >= 70
    assert res.clearance_need == "low"

@pytest.mark.parametrize("precip,slope,temp,soil", [
    # Slope capping behavior: very high slope should cap to 60%
    (0.0, 120.0, 65, "sand"),
])
def test_slope_capping_behavior(precip, slope, temp, soil):
    res = score(precip, slope, temp, soil)
    # Expect high clearance need due to capped slope
    assert res.clearance_need == "high"
    assert res.four_by_four_recommended is True
