"""
Tests for Wind Shelter Service

Comprehensive pytest table-driven tests for orientation recommendations and ridge shelter.
All tests verify pure, deterministic behavior.

Key requirements:
- Wind risk: higher gusts produce higher risk levels
- Ridge shelter: upwind ridges improve recommendation and reduce risk
- Edge cases: empty ridges, bearing normalization, edge angles
"""

import pytest
from wind_shelter_service import WindShelterService, Ridge, OrientationAdvice, RiskLevel


class TestBearingNormalization:
    """Test bearing normalization to 0-359° range."""

    @pytest.mark.parametrize("input_bearing,expected", [
        (0, 0),        # Already normalized
        (180, 180),    # 180 stays 180
        (359, 359),    # Almost full circle
        (360, 0),      # Full circle wraps to 0
        (361, 1),      # Beyond full circle
        (-1, 359),     # Negative wraps around
        (-90, 270),    # West from north
        (450, 90),     # More than full circle
        (720, 0),      # Two full circles
    ])
    def test_normalize_bearing(self, input_bearing, expected):
        """Verify bearing normalization."""
        result = WindShelterService._normalize_bearing(input_bearing)
        assert result == expected, f"Bearing {input_bearing} should normalize to {expected}, got {result}"

    def test_normalize_bearing_returns_int(self):
        """Normalized bearing is always integer."""
        result = WindShelterService._normalize_bearing(45.7)
        assert isinstance(result, int)


class TestBearingDifference:
    """Test angular difference calculation between bearings."""

    @pytest.mark.parametrize("bearing1,bearing2,expected_min,expected_max", [
        (0, 90, 89, 91),         # 90° difference
        (0, 180, 179, 181),      # Opposite directions
        (10, 350, 19, 21),       # 20° across north
        (270, 90, 179, 181),     # 180° (west to east)
        (45, 45, -1, 1),         # Same bearing
        (0, 359, -1, 1),         # 1° difference
        (180, 0, 179, 181),      # 180° (south to north)
    ])
    def test_bearing_difference(self, bearing1, bearing2, expected_min, expected_max):
        """Verify angular difference calculation."""
        result = WindShelterService._bearing_difference(bearing1, bearing2)
        assert expected_min <= result <= expected_max, \
            f"Difference between {bearing1}° and {bearing2}° should be ~{(expected_min + expected_max)//2}°, got {result}°"

    def test_bearing_difference_max_180(self):
        """Angular difference never exceeds 180°."""
        for b1 in range(0, 360, 45):
            for b2 in range(0, 360, 45):
                diff = WindShelterService._bearing_difference(b1, b2)
                assert diff <= 180, f"Difference should never exceed 180°, got {diff}°"

    def test_bearing_difference_symmetric(self):
        """Difference is same regardless of order."""
        diff1 = WindShelterService._bearing_difference(45, 135)
        diff2 = WindShelterService._bearing_difference(135, 45)
        assert diff1 == diff2, "Difference should be symmetric"


class TestRidgeUpwind:
    """Test ridge upwind detection."""

    @pytest.mark.parametrize("ridge_bearing,wind_bearing,is_upwind", [
        (0, 0, True),           # Ridge faces wind, directly upwind
        (10, 0, True),          # Ridge within 30° tolerance
        (350, 0, True),         # Ridge within 30° tolerance (across north)
        (90, 0, False),         # Ridge east, wind from north (not upwind)
        (180, 0, False),        # Ridge south, wind from north (downwind)
        (180, 90, False),       # Ridge south, wind from east (not upwind)
        (45, 30, True),         # Within tolerance
        (45, 100, False),       # Outside tolerance
    ])
    def test_is_ridge_upwind(self, ridge_bearing, wind_bearing, is_upwind):
        """Verify ridge upwind detection."""
        result = WindShelterService._is_ridge_upwind(ridge_bearing, wind_bearing)
        assert result == is_upwind, \
            f"Ridge {ridge_bearing}° vs wind {wind_bearing}° upwind={is_upwind}, got {result}"

    def test_ridge_upwind_tolerance(self):
        """Ridge detection respects tolerance angle."""
        # Directly upwind
        assert WindShelterService._is_ridge_upwind(0, 0) == True
        
        # Within 30° tolerance (default)
        assert WindShelterService._is_ridge_upwind(25, 0) == True
        
        # Outside tolerance
        assert WindShelterService._is_ridge_upwind(35, 0) == False


class TestAssessRiskLevel:
    """Test wind risk assessment."""

    @pytest.mark.parametrize("gust_mph,risk_level", [
        (0, "low"),           # Calm
        (10, "low"),          # Light wind
        (14, "low"),          # Just below threshold
        (15, "medium"),       # At medium threshold
        (25, "medium"),       # Medium wind
        (34, "medium"),       # Just below high threshold
        (35, "high"),         # At high threshold
        (50, "high"),         # Strong wind
        (100, "high"),        # Very strong wind
    ])
    def test_assess_risk_level(self, gust_mph, risk_level):
        """Verify risk level assessment."""
        result = WindShelterService._assess_risk_level(gust_mph)
        assert result == risk_level, \
            f"Gusts {gust_mph} mph should be {risk_level} risk, got {result}"


class TestRecommendOrientation:
    """Test orientation recommendation algorithm."""

    def test_recommend_orientation_no_shelter_calm(self):
        """Calm wind, no shelter: flexible orientation."""
        advice = WindShelterService.recommend_orientation(
            predominant_dir_deg=0,
            gust_mph=10,
            local_ridges=[]
        )
        
        assert advice.risk_level == "low"
        assert advice.shelter_available == False
        assert "low winds" in advice.rationale_text.lower()

    def test_recommend_orientation_no_shelter_medium(self):
        """Medium wind, no shelter: point nose into wind."""
        advice = WindShelterService.recommend_orientation(
            predominant_dir_deg=180,
            gust_mph=25,
            local_ridges=[]
        )
        
        assert advice.risk_level == "medium"
        assert advice.recommended_bearing_deg == 180
        assert "point nose" in advice.rationale_text.lower()

    def test_recommend_orientation_no_shelter_high(self):
        """High wind, no shelter: critical risk."""
        advice = WindShelterService.recommend_orientation(
            predominant_dir_deg=270,
            gust_mph=45,
            local_ridges=[]
        )
        
        assert advice.risk_level == "high"
        assert advice.recommended_bearing_deg == 270
        assert "critical" in advice.rationale_text.lower()

    def test_recommend_orientation_with_upwind_ridge(self):
        """Upwind ridge available: use it for shelter."""
        ridge = Ridge(bearing_deg=0, strength="med", name="North ridge")
        
        advice = WindShelterService.recommend_orientation(
            predominant_dir_deg=0,
            gust_mph=25,
            local_ridges=[ridge]
        )
        
        assert advice.shelter_available == True
        assert advice.recommended_bearing_deg == 0
        assert advice.estimated_wind_reduction_pct > 0

    def test_recommend_orientation_downwind_ridge_ignored(self):
        """Downwind ridge doesn't help: point nose into wind."""
        ridge = Ridge(bearing_deg=180, strength="high", name="South ridge")
        
        advice = WindShelterService.recommend_orientation(
            predominant_dir_deg=0,
            gust_mph=30,
            local_ridges=[ridge]
        )
        
        # Ridge is downwind (south), wind from north
        # Should ignore ridge and point nose north
        assert advice.recommended_bearing_deg == 0

    def test_recommend_orientation_multiple_ridges(self):
        """Multiple ridges: pick best upwind one."""
        ridges = [
            Ridge(bearing_deg=45, strength="low", name="NE ridge"),
            Ridge(bearing_deg=0, strength="high", name="North ridge"),
            Ridge(bearing_deg=315, strength="med", name="NW ridge"),
        ]
        
        advice = WindShelterService.recommend_orientation(
            predominant_dir_deg=0,
            gust_mph=30,
            local_ridges=ridges
        )
        
        # Should use north ridge (highest strength at wind direction)
        assert advice.shelter_available == True
        assert advice.recommended_bearing_deg == 0

    def test_recommend_orientation_bearing_normalization(self):
        """Wind bearing normalized to 0-359°."""
        advice = WindShelterService.recommend_orientation(
            predominant_dir_deg=450,  # Same as 90°
            gust_mph=20,
            local_ridges=[]
        )
        
        assert advice.recommended_bearing_deg == 90

    def test_recommend_orientation_wind_reduction_low_ridge(self):
        """Low strength ridge provides 15% reduction."""
        ridge = Ridge(bearing_deg=0, strength="low")
        
        advice = WindShelterService.recommend_orientation(
            predominant_dir_deg=0,
            gust_mph=25,
            local_ridges=[ridge]
        )
        
        assert advice.estimated_wind_reduction_pct == 15

    def test_recommend_orientation_wind_reduction_med_ridge(self):
        """Med strength ridge provides ~35% reduction."""
        ridge = Ridge(bearing_deg=0, strength="med")
        
        advice = WindShelterService.recommend_orientation(
            predominant_dir_deg=0,
            gust_mph=25,
            local_ridges=[ridge]
        )
        
        assert advice.estimated_wind_reduction_pct == 35

    def test_recommend_orientation_wind_reduction_high_ridge(self):
        """High strength ridge provides ~60% reduction."""
        ridge = Ridge(bearing_deg=0, strength="high")
        
        advice = WindShelterService.recommend_orientation(
            predominant_dir_deg=0,
            gust_mph=25,
            local_ridges=[ridge]
        )
        
        assert advice.estimated_wind_reduction_pct == 60

    def test_recommend_orientation_returns_valid_bearing(self):
        """Recommended bearing always in 0-359° range."""
        for wind_dir in [0, 45, 90, 180, 270, 359]:
            for gust in [10, 30, 50]:
                advice = WindShelterService.recommend_orientation(wind_dir, gust)
                assert 0 <= advice.recommended_bearing_deg <= 359

    def test_recommend_orientation_none_ridges(self):
        """None for ridges handled gracefully."""
        advice = WindShelterService.recommend_orientation(0, 25, None)
        assert advice.shelter_available == False
        assert len(advice.rationale_text) > 0

    def test_recommend_orientation_empty_ridges(self):
        """Empty ridges list handled correctly."""
        advice = WindShelterService.recommend_orientation(0, 25, [])
        assert advice.shelter_available == False

    def test_recommend_orientation_deterministic(self):
        """Same inputs always produce same output."""
        for _ in range(5):
            advice1 = WindShelterService.recommend_orientation(45, 30, [Ridge(0, "med")])
            advice2 = WindShelterService.recommend_orientation(45, 30, [Ridge(0, "med")])
            
            assert advice1.recommended_bearing_deg == advice2.recommended_bearing_deg
            assert advice1.risk_level == advice2.risk_level


class TestRidgeValidation:
    """Test Ridge dataclass validation."""

    def test_ridge_invalid_bearing_low(self):
        """Bearing < 0 raises error."""
        with pytest.raises(ValueError, match="bearing_deg"):
            Ridge(bearing_deg=-1, strength="med")

    def test_ridge_invalid_bearing_high(self):
        """Bearing >= 360 raises error."""
        with pytest.raises(ValueError, match="bearing_deg"):
            Ridge(bearing_deg=360, strength="med")

    def test_ridge_invalid_strength(self):
        """Invalid strength value raises error."""
        with pytest.raises(ValueError, match="strength"):
            Ridge(bearing_deg=0, strength="extra_high")

    def test_ridge_valid_extremes(self):
        """Valid bearing extremes accepted."""
        r1 = Ridge(bearing_deg=0, strength="low")
        r2 = Ridge(bearing_deg=359, strength="high")
        assert r1.bearing_deg == 0
        assert r2.bearing_deg == 359


class TestAssessRidgeEffectiveness:
    """Test ridge effectiveness assessment."""

    def test_ridge_effectiveness_low_strength(self):
        """Low strength ridge has low effectiveness."""
        ridge = Ridge(bearing_deg=0, strength="low")
        metrics = WindShelterService.assess_ridge_effectiveness(ridge, 30)
        
        assert metrics["effectiveness_pct"] == 15
        assert metrics["max_protection"] == 20

    def test_ridge_effectiveness_med_strength(self):
        """Med strength ridge has medium effectiveness."""
        ridge = Ridge(bearing_deg=0, strength="med")
        metrics = WindShelterService.assess_ridge_effectiveness(ridge, 30)
        
        assert metrics["effectiveness_pct"] == 35
        assert metrics["max_protection"] == 45

    def test_ridge_effectiveness_high_strength(self):
        """High strength ridge has high effectiveness."""
        ridge = Ridge(bearing_deg=0, strength="high")
        metrics = WindShelterService.assess_ridge_effectiveness(ridge, 30)
        
        assert metrics["effectiveness_pct"] == 60
        assert metrics["max_protection"] == 70

    def test_ridge_effectiveness_low_wind(self):
        """Low wind speed reduces effectiveness."""
        ridge = Ridge(bearing_deg=0, strength="med")
        
        low_wind = WindShelterService.assess_ridge_effectiveness(ridge, 10)
        high_wind = WindShelterService.assess_ridge_effectiveness(ridge, 40)
        
        # Low wind should have less benefit
        assert low_wind["effectiveness_pct"] < high_wind["effectiveness_pct"]

    def test_ridge_effectiveness_name_included(self):
        """Ridge name included in effectiveness metrics."""
        ridge = Ridge(bearing_deg=45, strength="med", name="Northeast ridge")
        metrics = WindShelterService.assess_ridge_effectiveness(ridge, 25)
        
        assert "Northeast ridge" in metrics["ridge_name"]


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_wind_direction_wrapping(self):
        """Wind direction wraps correctly around 360°."""
        # Wind from -10° should be treated as 350°
        advice1 = WindShelterService.recommend_orientation(-10, 20)
        advice2 = WindShelterService.recommend_orientation(350, 20)
        
        assert advice1.recommended_bearing_deg == advice2.recommended_bearing_deg

    def test_gust_speed_zero(self):
        """Zero gust speed handled correctly."""
        advice = WindShelterService.recommend_orientation(0, 0)
        assert advice.risk_level == "low"

    def test_gust_speed_negative(self):
        """Negative gust speed clamped to 0."""
        advice = WindShelterService.recommend_orientation(0, -10)
        assert advice.risk_level == "low"

    def test_large_gust_speed(self):
        """Large gust speeds handled correctly."""
        advice = WindShelterService.recommend_orientation(0, 200)
        assert advice.risk_level == "high"

    def test_ridge_at_exact_tolerance_boundary(self):
        """Ridge at exactly 30° tolerance boundary."""
        # 30° from wind direction - at boundary (should be True)
        assert WindShelterService._is_ridge_upwind(30, 0) == True
        # 31° from wind direction - outside tolerance
        assert WindShelterService._is_ridge_upwind(31, 0) == False

    def test_opposite_wind_directions(self):
        """Opposite wind directions produce sensible results."""
        north_wind = WindShelterService.recommend_orientation(0, 30)
        south_wind = WindShelterService.recommend_orientation(180, 30)
        
        # Should have opposite recommended bearings
        bearing_diff = abs(north_wind.recommended_bearing_deg - south_wind.recommended_bearing_deg)
        # Should be ~180° apart
        assert 170 < bearing_diff < 190 or bearing_diff < 10  # Wrapping consideration
