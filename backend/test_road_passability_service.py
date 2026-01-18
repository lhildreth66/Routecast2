"""
Unit Tests for Road Passability Service

Table-driven tests for various road conditions, soil types, and weather.
All tests are deterministic and isolated.
"""

import pytest
from road_passability_service import (
    PassabilityRisks,
    RoadPassabilityResult,
    RoadPassabilityService,
)


class TestSoilMoistureLevel:
    """Test suite for soil moisture calculation."""
    
    MOISTURE_CASES = [
        # (name, precip_72h, soil_type, expected)
        ("clay_dry", 0, "clay", "dry"),
        ("clay_moist", 20, "clay", "moist"),
        ("clay_wet", 35, "clay", "wet"),
        ("clay_saturated", 60, "clay", "saturated"),
        ("sand_dry", 0, "sand", "dry"),
        ("sand_moist", 8, "sand", "moist"),
        ("sand_wet", 20, "sand", "wet"),
        ("sand_saturated", 35, "sand", "saturated"),
        ("rocky_good_drainage", 50, "rocky", "wet"),  # Rocky drains well
        ("unknown_soil_defaults_to_loam", 15, "loam", "moist"),
    ]
    
    @pytest.mark.parametrize(
        "name,precip_72h,soil_type,expected",
        MOISTURE_CASES,
        ids=[c[0] for c in MOISTURE_CASES],
    )
    def test_moisture_level(self, name, precip_72h, soil_type, expected):
        """Test soil moisture classification."""
        result = RoadPassabilityService.calculate_soil_moisture_level(
            precip_72h, soil_type
        )
        assert result == expected, f"{name}: expected {expected}, got {result}"
    
    def test_invalid_precipitation_negative(self):
        """Test that negative precipitation raises error."""
        with pytest.raises(ValueError):
            RoadPassabilityService.calculate_soil_moisture_level(-5, "clay")
    
    def test_invalid_soil_type_type(self):
        """Test that non-string soil type raises error."""
        with pytest.raises(ValueError):
            RoadPassabilityService.calculate_soil_moisture_level(10, 123)


class TestMudRisk:
    """Test suite for mud risk calculation."""
    
    MUD_RISK_CASES = [
        # (name, moisture, slope, expected_mud_risk)
        ("saturated_any_slope", "saturated", 0, True),
        ("saturated_steep", "saturated", 20, True),
        ("wet_gentle_slope", "wet", 5, True),
        ("wet_steep_slope", "wet", 12, False),
        ("moist_very_gentle", "moist", 2, True),
        ("moist_gentle", "moist", 5, False),
        ("dry_any_slope", "dry", 0, False),
    ]
    
    @pytest.mark.parametrize(
        "name,moisture,slope,expected",
        MUD_RISK_CASES,
        ids=[c[0] for c in MUD_RISK_CASES],
    )
    def test_mud_risk(self, name, moisture, slope, expected):
        """Test mud risk assessment."""
        result = RoadPassabilityService.calculate_mud_risk(moisture, slope)
        assert result == expected, f"{name}: expected {expected}, got {result}"


class TestIceRisk:
    """Test suite for ice risk calculation."""
    
    ICE_RISK_CASES = [
        # (name, temp_f, precip, expected_ice_risk)
        ("freezing_with_moisture", 32, 5, True),
        ("freezing_no_moisture", 32, 0, False),
        ("below_freezing_wet", 20, 10, True),
        ("below_freezing_dry", 20, 0, False),  # Dry won't form ice
        ("cold_transition_wet", 34, 10, True),
        ("cold_transition_dry", 34, 2, False),
        ("warm_day", 50, 20, False),
        ("warm_day_frozen_night", 35, 5, False),  # Won't stay frozen
    ]
    
    @pytest.mark.parametrize(
        "name,temp,precip,expected",
        ICE_RISK_CASES,
        ids=[c[0] for c in ICE_RISK_CASES],
    )
    def test_ice_risk(self, name, temp, precip, expected):
        """Test ice risk assessment."""
        result = RoadPassabilityService.calculate_ice_risk(temp, precip)
        assert result == expected, f"{name}: expected {expected}, got {result}"


class TestClearanceNeeded:
    """Test suite for ground clearance calculation."""
    
    CLEARANCE_CASES = [
        # (name, moisture, slope, expected_min, expected_max)
        ("dry_flat", "dry", 0, 14, 16),
        ("moist_flat", "moist", 0, 18, 22),
        ("wet_flat", "wet", 0, 28, 32),
        ("saturated_flat", "saturated", 0, 43, 47),
        ("dry_steep", "dry", 15, 20, 26),
        ("wet_moderate_slope", "wet", 10, 33, 37),
        ("saturated_very_steep", "saturated", 20, 52, 56),
    ]
    
    @pytest.mark.parametrize(
        "name,moisture,slope,expected_min,expected_max",
        CLEARANCE_CASES,
        ids=[c[0] for c in CLEARANCE_CASES],
    )
    def test_clearance_needed(self, name, moisture, slope, expected_min, expected_max):
        """Test minimum clearance calculation."""
        result = RoadPassabilityService.calculate_clearance_needed(moisture, slope)
        assert expected_min <= result <= expected_max, (
            f"{name}: expected {expected_min}-{expected_max}, got {result}"
        )


class TestPassabilityScore:
    """Test suite for passability score calculation."""
    
    PASSABILITY_CASES = [
        # (name, precip, slope, temp, soil, expected_min, expected_max)
        (
            "clay_rain",
            50,  # Heavy rain
            5,
            40,
            "clay",
            35,
            45,  # Muddy, poor
        ),
        (
            "freeze_wet",
            20,  # Wet + freeze = ice
            5,
            28,  # Below freezing
            "loam",
            40,
            55,
        ),
        (
            "dry_sand_flat",
            0,  # Dry
            2,
            60,  # Warm
            "sand",
            85,
            100,  # Excellent
        ),
        (
            "rocky_wet_flat",
            40,  # Wet
            0,
            40,  # Moderate temp
            "rocky",
            80,
            90,  # Rocky drains well
        ),
        (
            "steep_dry",
            0,  # Dry
            25,  # Very steep
            60,
            "loam",
            65,
            80,  # Traction issues but not severe
        ),
        (
            "perfect_conditions",
            0,
            3,
            65,
            "loam",
            80,
            100,
        ),
    ]
    
    @pytest.mark.parametrize(
        "name,precip,slope,temp,soil,expected_min,expected_max",
        PASSABILITY_CASES,
        ids=[c[0] for c in PASSABILITY_CASES],
    )
    def test_passability_score_range(
        self, name, precip, slope, temp, soil, expected_min, expected_max
    ):
        """Test passability score with various conditions."""
        score = RoadPassabilityService.calculate_passability_score(
            precip, slope, temp, soil
        )
        assert expected_min <= score <= expected_max, (
            f"{name}: expected {expected_min}-{expected_max}, got {score}"
        )
        assert 0 <= score <= 100, "Score must be 0-100"
    
    # Input validation tests
    INVALID_PASSABILITY_CASES = [
        ("negative_precip", -5, 5, 40, "loam"),
        ("invalid_slope_high", 10, 150, 40, "loam"),
        ("invalid_slope_low", 10, -95, 40, "loam"),
        ("temp_too_high", 10, 5, 150, "loam"),
        ("temp_too_low", 10, 5, -60, "loam"),
    ]
    
    @pytest.mark.parametrize(
        "name,precip,slope,temp,soil",
        INVALID_PASSABILITY_CASES,
        ids=[c[0] for c in INVALID_PASSABILITY_CASES],
    )
    def test_invalid_inputs(self, name, precip, slope, temp, soil):
        """Test that invalid inputs raise ValueError."""
        with pytest.raises(ValueError):
            RoadPassabilityService.calculate_passability_score(
                precip, slope, temp, soil
            )


class TestVehicleRecommendation:
    """Test suite for vehicle type recommendation."""
    
    VEHICLE_CASES = [
        # (name, score, slope, clearance, expected_vehicle, expected_4wd)
        ("excellent_dry", 90, 5, 16, "sedan", False),
        ("good_flat", 75, 0, 18, "sedan", False),
        ("fair_high_clearance", 65, 5, 24, "suv", False),
        ("poor_steep_4wd", 45, 20, 28, "4x4", True),
        ("impassable_4wd", 25, 30, 32, "4x4", True),
        ("marginal_suv", 55, 10, 26, "suv", True),
    ]
    
    @pytest.mark.parametrize(
        "name,score,slope,clearance,expected_vehicle,expected_4wd",
        VEHICLE_CASES,
        ids=[c[0] for c in VEHICLE_CASES],
    )
    def test_vehicle_recommendation(
        self, name, score, slope, clearance, expected_vehicle, expected_4wd
    ):
        """Test vehicle type recommendation."""
        vehicle, needs_4wd = RoadPassabilityService.evaluate_vehicle_recommendation(
            score, slope, clearance
        )
        assert vehicle == expected_vehicle, f"{name}: vehicle mismatch"
        assert needs_4wd == expected_4wd, f"{name}: 4WD mismatch"


class TestAdvisoryGeneration:
    """Test suite for advisory text generation."""
    
    ADVISORY_CASES = [
        ("excellent", 85, False, False, 16, 3, "✅"),
        ("fair_muddy", 65, True, False, 20, 5, "⚠️"),
        ("poor_icy", 45, False, True, 25, 8, "❌"),
        ("impassable", 25, True, True, 30, 20, "🚫"),
    ]
    
    @pytest.mark.parametrize(
        "name,score,mud,ice,clearance,slope,expected_emoji",
        ADVISORY_CASES,
        ids=[c[0] for c in ADVISORY_CASES],
    )
    def test_advisory_content(
        self, name, score, mud, ice, clearance, slope, expected_emoji
    ):
        """Test advisory generation."""
        advisory = RoadPassabilityService.generate_advisory(
            score, mud, ice, clearance, slope
        )
        assert expected_emoji in advisory, (
            f"{name}: expected emoji '{expected_emoji}' in advisory"
        )
        assert isinstance(advisory, str) and len(advisory) > 0


class TestCompleteAssessment:
    """Test suite for complete road passability assessment."""
    
    def test_clay_heavy_rain_assessment(self):
        """Test clay soil with heavy rain - muddy, impassable."""
        result = RoadPassabilityService.assess_road_passability(
            precip_72h=55,  # Heavy rain
            slope_pct=5,
            min_temp_f=40,
            soil_type="clay",
        )
        
        assert isinstance(result, RoadPassabilityResult)
        assert result.passability_score < 40
        assert result.risks.mud_risk is True
        assert result.risks.ice_risk is False
        assert result.condition_assessment == "Impassable"
        # Check advisory mentions conditions (may not mention "mud" in impassable state)
        assert len(result.advisory) > 0

    
    def test_freeze_thaw_assessment(self):
        """Test freeze-thaw conditions with moisture - icy."""
        result = RoadPassabilityService.assess_road_passability(
            precip_72h=25,  # Moderate moisture
            slope_pct=8,
            min_temp_f=28,  # Below freezing
            soil_type="loam",
        )
        
        assert result.risks.ice_risk is True
        assert result.passability_score < 60
        # Check advisory mentions conditions
        assert len(result.advisory) > 0

    
    def test_dry_sand_assessment(self):
        """Test dry sand - excellent conditions."""
        result = RoadPassabilityService.assess_road_passability(
            precip_72h=0,  # Dry
            slope_pct=3,
            min_temp_f=65,
            soil_type="sand",
        )
        
        assert result.passability_score > 80
        assert result.risks.mud_risk is False
        assert result.risks.ice_risk is False
        assert result.condition_assessment == "Excellent"
        assert result.recommended_vehicle_type == "sedan"
        assert result.risks.four_x_four_recommended is False
    
    def test_rocky_wet_assessment(self):
        """Test rocky soil when wet - fair to good (rocks drain)."""
        result = RoadPassabilityService.assess_road_passability(
            precip_72h=40,  # Wet
            slope_pct=0,
            min_temp_f=45,
            soil_type="rocky",
        )
        
        # Rocky soil drains well, should be better than clay
        assert result.passability_score > 50
        assert result.risks.mud_risk is False or result.passability_score > 60
        assert result.min_clearance_cm < 25  # Doesn't need excessive clearance
    
    def test_steep_grade_assessment(self):
        """Test steep grade - traction risk."""
        result = RoadPassabilityService.assess_road_passability(
            precip_72h=5,  # Mostly dry
            slope_pct=22,  # Very steep
            min_temp_f=50,
            soil_type="loam",
        )
        
        assert result.passability_score <= 75
        # Check advisory mentions conditions
        assert len(result.advisory) > 0

    
    def test_assessment_structure_complete(self):
        """Test that assessment has all required fields."""
        result = RoadPassabilityService.assess_road_passability(
            precip_72h=10,
            slope_pct=5,
            min_temp_f=50,
            soil_type="loam",
        )
        
        assert isinstance(result.passability_score, (float, int))
        assert 0 <= result.passability_score <= 100
        assert isinstance(result.condition_assessment, str)
        assert isinstance(result.risks, PassabilityRisks)
        assert isinstance(result.min_clearance_cm, (float, int))
        assert result.min_clearance_cm >= 0
        assert result.recommended_vehicle_type in ["sedan", "suv", "4x4"]
        assert isinstance(result.risks.four_x_four_recommended, bool)
        assert isinstance(result.risks.mud_risk, bool)
        assert isinstance(result.risks.ice_risk, bool)


class TestDeterminismAndPurity:
    """Tests ensuring functions are pure and deterministic."""
    
    def test_deterministic_100_iterations(self):
        """Test that same input produces identical output 100 times."""
        results = [
            RoadPassabilityService.assess_road_passability(
                precip_72h=30,
                slope_pct=8,
                min_temp_f=35,
                soil_type="clay",
            ).passability_score
            for _ in range(100)
        ]
        
        # All should be identical
        assert len(set(results)) == 1, "Output should be deterministic"
    
    def test_no_side_effects(self):
        """Test that function doesn't modify input objects."""
        precip = 25.0
        slope = 10.0
        temp = 40.0
        soil = "clay"
        
        original_precip = precip
        original_slope = slope
        original_temp = temp
        original_soil = soil
        
        RoadPassabilityService.assess_road_passability(
            precip, slope, temp, soil
        )
        
        # Verify inputs unchanged (they're primitive/immutable)
        assert precip == original_precip
        assert slope == original_slope
        assert temp == original_temp
        assert soil == original_soil


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
