import pytest
from connectivity_prediction_service import (
    cell_bars_probability,
    obstruction_risk,
    CellProbabilityResult,
    StarlinkRiskResult,
)


class TestCellBarsProbability:
    """Test cellular signal probability prediction."""

    @pytest.mark.parametrize("distance,expect_lower", [
        (0, False),      # At tower: reference point
        (5, True),       # Reasonable distance: lower than at tower
        (15, True),      # Far: lower than 5km
        (30, True),      # Very far: even lower
    ])
    def test_increasing_distance_lowers_probability(self, distance, expect_lower):
        """Probability decreases as distance increases."""
        prob_near = cell_bars_probability("att", 0, 0).probability
        prob_far = cell_bars_probability("att", distance, 0).probability
        if expect_lower:
            assert prob_far < prob_near, f"Distance {distance}: prob should decrease"

    @pytest.mark.parametrize("obstruction,expect_lower", [
        (0, False),      # No obstruction: reference point
        (30, True),      # Moderate: lower than clear
        (70, True),      # High obstruction: even lower
        (100, True),     # Full obstruction: lowest
    ])
    def test_increasing_obstruction_lowers_probability(self, obstruction, expect_lower):
        """Probability decreases as terrain obstruction increases."""
        prob_clear = cell_bars_probability("att", 5, 0).probability
        prob_obstructed = cell_bars_probability("att", 5, obstruction).probability
        if expect_lower:
            assert prob_obstructed < prob_clear

    @pytest.mark.parametrize("carrier,distance,obstruction", [
        ("verizon", 0, 0),
        ("att", 10, 50),
        ("tmobile", 5, 30),
        ("unknown", 20, 80),
    ])
    def test_probability_clamped_0_to_1(self, carrier, distance, obstruction):
        """Probability is always [0.0, 1.0]."""
        result = cell_bars_probability(carrier, distance, obstruction)
        assert 0.0 <= result.probability <= 1.0

    @pytest.mark.parametrize("carrier,expect_multiplier", [
        ("verizon", "better"),
        ("att", "neutral"),
        ("tmobile", "worse"),
    ])
    def test_carrier_specific_curves(self, carrier, expect_multiplier):
        """Verizon slightly better, TMobile slightly worse than AT&T."""
        att_prob = cell_bars_probability("att", 10, 0).probability
        other_prob = cell_bars_probability(carrier, 10, 0).probability
        if expect_multiplier == "better":
            assert other_prob > att_prob
        elif expect_multiplier == "worse":
            assert other_prob < att_prob
        else:
            assert other_prob == att_prob

    @pytest.mark.parametrize("distance,obstruction", [
        (-5, -10),  # Negative inputs clamped
        (999, 999),  # Large inputs clamped
    ])
    def test_input_clamping(self, distance, obstruction):
        """Negative/large inputs are clamped safely."""
        result = cell_bars_probability("att", distance, obstruction)
        assert isinstance(result, CellProbabilityResult)
        assert 0.0 <= result.probability <= 1.0

    @pytest.mark.parametrize("probability,expect_bars", [
        (0.9, "3+ bars"),
        (0.7, "2-3 bars"),
        (0.4, "1-2 bars"),
        (0.1, "no signal"),
    ])
    def test_bar_estimate_mapping(self, probability, expect_bars):
        """Probability range maps to correct bar estimate."""
        # Create scenario with approximate probability
        # Using distance to reach desired prob range
        if probability >= 0.9:
            distance = 0
        elif probability >= 0.7:
            distance = 3
        elif probability >= 0.4:
            distance = 8
        else:
            distance = 25
        result = cell_bars_probability("att", distance, 0)
        assert result.bar_estimate == expect_bars


class TestObstructionRisk:
    """Test Starlink obstruction risk prediction."""

    @pytest.mark.parametrize("horizon,canopy,expect_low", [
        (0, 0, True),      # Clear: low risk
        (10, 5, True),     # Mostly clear
        (30, 30, False),   # Some obstruction
        (60, 60, False),   # Significant obstruction
        (80, 80, False),   # Very high obstruction
    ])
    def test_obstruction_combinations(self, horizon, canopy, expect_low):
        """Risk level matches expected thresholds."""
        result = obstruction_risk(horizon, canopy)
        if expect_low:
            assert result.risk_level == "low"
        else:
            assert result.risk_level in ("medium", "high")

    def test_low_risk_clear_conditions(self):
        """Canopy 0 + horizon 0 ⇒ low risk."""
        result = obstruction_risk(0, 0)
        assert result.risk_level == "low"
        assert result.obstruction_score < 0.3

    def test_high_canopy_increases_risk(self):
        """High canopy increases risk."""
        low_canopy = obstruction_risk(0, 10).risk_level
        high_canopy = obstruction_risk(0, 80).risk_level
        # high_canopy should be >= low_canopy in risk
        risk_order = {"low": 1, "medium": 2, "high": 3}
        assert risk_order.get(high_canopy, 0) >= risk_order.get(low_canopy, 0)

    def test_high_horizon_increases_risk(self):
        """High horizon obstruction increases risk."""
        clear_horizon = obstruction_risk(10, 0).risk_level
        obstructed_horizon = obstruction_risk(75, 0).risk_level
        risk_order = {"low": 1, "medium": 2, "high": 3}
        assert risk_order.get(obstructed_horizon, 0) >= risk_order.get(clear_horizon, 0)

    def test_combined_high_obstruction(self):
        """High canopy + high horizon ⇒ high risk."""
        result = obstruction_risk(75, 75)
        assert result.risk_level == "high"

    @pytest.mark.parametrize("horizon,canopy", [
        (-10, -20),  # Negative clamped
        (200, 200),  # Large values clamped
    ])
    def test_input_clamping_starlink(self, horizon, canopy):
        """Inputs are clamped safely."""
        result = obstruction_risk(horizon, canopy)
        assert isinstance(result, StarlinkRiskResult)
        assert result.risk_level in ("low", "medium", "high")
        assert 0.0 <= result.obstruction_score <= 1.0

    @pytest.mark.parametrize("horizon,canopy,expect_score_range", [
        (0, 0, (0.0, 0.3)),     # Low risk score
        (30, 30, (0.3, 0.6)),   # Medium risk score
        (80, 80, (0.6, 1.0)),   # High risk score
    ])
    def test_obstruction_score_ranges(self, horizon, canopy, expect_score_range):
        """Obstruction score maps correctly to risk levels."""
        result = obstruction_risk(horizon, canopy)
        assert expect_score_range[0] <= result.obstruction_score <= expect_score_range[1]

    def test_equal_weighting_horizon_canopy(self):
        """Horizon and canopy weighted equally in score."""
        # (h/90)*0.5 + (c/100)*0.5 = score
        # At h=45, c=50: (45/90)*0.5 + (50/100)*0.5 = 0.25 + 0.25 = 0.5
        result = obstruction_risk(45, 50)
        assert abs(result.obstruction_score - 0.5) < 0.01

    def test_explanation_includes_reasons(self):
        """High obstruction explanation includes reasons."""
        result = obstruction_risk(80, 80)
        assert "high risk" in result.explanation
        assert result.reasons is not None
        assert len(result.reasons) > 0
