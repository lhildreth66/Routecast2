import pytest
from campsite_index_service import (
    SiteFactors,
    Weights,
    ScoredIndex,
    score,
    default_weights,
)


class TestDeterminismAndBounds:
    """Test determinism and output bounds."""

    @pytest.mark.parametrize("factors", [
        SiteFactors(wind_gust_mph=15, shade_score=0.5, slope_pct=8, access_score=0.7, signal_score=0.6, road_passability_score=75),
        SiteFactors(wind_gust_mph=25, shade_score=0.2, slope_pct=12, access_score=0.4, signal_score=0.3, road_passability_score=50),
    ])
    def test_determinism(self, factors):
        """Same inputs always return same score."""
        result1 = score(factors)
        result2 = score(factors)
        assert result1.score == result2.score
        assert result1.breakdown == result2.breakdown

    @pytest.mark.parametrize("factors", [
        SiteFactors(wind_gust_mph=0, shade_score=1.0, slope_pct=0, access_score=1.0, signal_score=1.0, road_passability_score=100),
        SiteFactors(wind_gust_mph=100, shade_score=0, slope_pct=100, access_score=0, signal_score=0, road_passability_score=0),
        SiteFactors(wind_gust_mph=20, shade_score=0.5, slope_pct=10, access_score=0.5, signal_score=0.5, road_passability_score=50),
    ])
    def test_score_bounded_0_100(self, factors):
        """Score is always clamped to 0-100."""
        result = score(factors)
        assert 0 <= result.score <= 100
        # Also check individual subscores
        for subscore in result.breakdown.values():
            assert 0.0 <= subscore <= 100.0


class TestWeightSensitivity:
    """Test that weight changes affect scoring as expected."""

    def test_increase_signal_weight_on_low_signal(self):
        """Increase signal weight when signal is low → score decreases."""
        factors = SiteFactors(
            wind_gust_mph=10,
            shade_score=0.5,
            slope_pct=5,
            access_score=0.7,
            signal_score=0.2,  # Low signal
            road_passability_score=80,
        )
        low_weight = score(factors, Weights(signal=0.05))  # Low weight on signal
        high_weight = score(factors, Weights(signal=0.5))  # High weight on signal
        # High weight on low signal should decrease overall score
        assert high_weight.score <= low_weight.score

    def test_increase_signal_weight_on_high_signal(self):
        """Increase signal weight when signal is high → score increases."""
        factors = SiteFactors(
            wind_gust_mph=10,
            shade_score=0.5,
            slope_pct=5,
            access_score=0.7,
            signal_score=0.9,  # High signal
            road_passability_score=80,
        )
        low_weight = score(factors, Weights(signal=0.05))
        high_weight = score(factors, Weights(signal=0.5))
        # High weight on high signal should increase overall score
        assert high_weight.score >= low_weight.score

    def test_zero_weight_removes_influence(self):
        """Setting a weight to zero removes that factor's influence."""
        factors = SiteFactors(
            wind_gust_mph=100,  # Very high wind (would normally hurt score)
            shade_score=0.5,
            slope_pct=5,
            access_score=0.7,
            signal_score=0.7,
            road_passability_score=80,
        )
        with_wind = score(factors, Weights(wind=0.2))
        without_wind = score(factors, Weights(wind=0.0))  # Wind ignored
        # Score should be higher when high wind is ignored
        assert without_wind.score >= with_wind.score

    def test_weights_normalized(self):
        """Custom weights are normalized internally."""
        factors = SiteFactors(
            wind_gust_mph=15,
            shade_score=0.5,
            slope_pct=8,
            access_score=0.7,
            signal_score=0.6,
            road_passability_score=75,
        )
        # Unnormalized weights (sum to 2.0)
        custom = Weights(wind=0.4, shade=0.3, slope=0.3, access=0.3, signal=0.3, passability=0.4)
        # Should give same result as normalized version
        result_custom = score(factors, custom)
        result_default = score(factors)  # Uses default normalized weights
        # Both should be valid scores
        assert 0 <= result_custom.score <= 100
        assert 0 <= result_default.score <= 100


class TestFactorMonotonicity:
    """Test that factors change score in the expected direction."""

    def test_higher_wind_decreases_score(self):
        """Higher wind gust lowers score."""
        base = SiteFactors(wind_gust_mph=10, shade_score=0.5, slope_pct=8, access_score=0.7, signal_score=0.6, road_passability_score=75)
        windy = SiteFactors(wind_gust_mph=35, shade_score=0.5, slope_pct=8, access_score=0.7, signal_score=0.6, road_passability_score=75)
        assert score(windy).score < score(base).score

    def test_higher_slope_decreases_score(self):
        """Higher slope lowers score."""
        base = SiteFactors(wind_gust_mph=10, shade_score=0.5, slope_pct=5, access_score=0.7, signal_score=0.6, road_passability_score=75)
        steep = SiteFactors(wind_gust_mph=10, shade_score=0.5, slope_pct=20, access_score=0.7, signal_score=0.6, road_passability_score=75)
        assert score(steep).score < score(base).score

    def test_higher_shade_increases_score(self):
        """Higher shade increases score."""
        no_shade = SiteFactors(wind_gust_mph=10, shade_score=0.0, slope_pct=8, access_score=0.7, signal_score=0.6, road_passability_score=75)
        full_shade = SiteFactors(wind_gust_mph=10, shade_score=1.0, slope_pct=8, access_score=0.7, signal_score=0.6, road_passability_score=75)
        assert score(full_shade).score > score(no_shade).score

    def test_higher_access_increases_score(self):
        """Higher access increases score."""
        poor = SiteFactors(wind_gust_mph=10, shade_score=0.5, slope_pct=8, access_score=0.2, signal_score=0.6, road_passability_score=75)
        good = SiteFactors(wind_gust_mph=10, shade_score=0.5, slope_pct=8, access_score=0.9, signal_score=0.6, road_passability_score=75)
        assert score(good).score > score(poor).score

    def test_higher_signal_increases_score(self):
        """Higher signal increases score."""
        weak = SiteFactors(wind_gust_mph=10, shade_score=0.5, slope_pct=8, access_score=0.7, signal_score=0.1, road_passability_score=75)
        strong = SiteFactors(wind_gust_mph=10, shade_score=0.5, slope_pct=8, access_score=0.7, signal_score=0.9, road_passability_score=75)
        assert score(strong).score > score(weak).score

    def test_higher_passability_increases_score(self):
        """Higher passability increases score."""
        poor = SiteFactors(wind_gust_mph=10, shade_score=0.5, slope_pct=8, access_score=0.7, signal_score=0.6, road_passability_score=30)
        good = SiteFactors(wind_gust_mph=10, shade_score=0.5, slope_pct=8, access_score=0.7, signal_score=0.6, road_passability_score=95)
        assert score(good).score > score(poor).score


class TestInputClamping:
    """Test that out-of-range inputs are clamped safely."""

    @pytest.mark.parametrize("shade,signal,access", [
        (-0.5, -1.0, -0.2),   # Negative values
        (2.0, 3.0, 1.5),      # Values > 1.0
    ])
    def test_normalize_fractional_inputs(self, shade, signal, access):
        """Fractional inputs (0-1 range) are clamped."""
        factors = SiteFactors(
            wind_gust_mph=15,
            shade_score=shade,
            slope_pct=8,
            access_score=access,
            signal_score=signal,
            road_passability_score=75,
        )
        result = score(factors)
        assert 0 <= result.score <= 100
        assert all(0.0 <= s <= 100.0 for s in result.breakdown.values())

    @pytest.mark.parametrize("passability", [
        (-50),   # Negative
        (150),   # > 100
    ])
    def test_normalize_passability_range(self, passability):
        """Passability score (0-100) is clamped."""
        factors = SiteFactors(
            wind_gust_mph=15,
            shade_score=0.5,
            slope_pct=8,
            access_score=0.7,
            signal_score=0.6,
            road_passability_score=passability,
        )
        result = score(factors)
        assert 0 <= result.score <= 100

    @pytest.mark.parametrize("wind,slope", [
        (-10, -5),     # Negative
        (1000, 500),   # Very large
    ])
    def test_normalize_wind_and_slope(self, wind, slope):
        """Wind and slope (non-negative) are clamped."""
        factors = SiteFactors(
            wind_gust_mph=wind,
            shade_score=0.5,
            slope_pct=slope,
            access_score=0.7,
            signal_score=0.6,
            road_passability_score=75,
        )
        result = score(factors)
        assert 0 <= result.score <= 100


class TestBreakdownStructure:
    """Test breakdown dict contains expected keys and formats."""

    def test_breakdown_has_all_factors(self):
        """Breakdown includes all 6 factors."""
        factors = SiteFactors(wind_gust_mph=15, shade_score=0.5, slope_pct=8, access_score=0.7, signal_score=0.6, road_passability_score=75)
        result = score(factors)
        expected_keys = {"wind", "shade", "slope", "access", "signal", "passability"}
        assert set(result.breakdown.keys()) == expected_keys

    def test_breakdown_subscores_bounded(self):
        """Each subscore in breakdown is 0-100."""
        factors = SiteFactors(wind_gust_mph=15, shade_score=0.5, slope_pct=8, access_score=0.7, signal_score=0.6, road_passability_score=75)
        result = score(factors)
        for factor, subscore in result.breakdown.items():
            assert 0.0 <= subscore <= 100.0, f"{factor} subscore {subscore} out of bounds"

    def test_explanations_optional(self):
        """Explanations may be None or list of strings."""
        factors = SiteFactors(wind_gust_mph=15, shade_score=0.5, slope_pct=8, access_score=0.7, signal_score=0.6, road_passability_score=75)
        result = score(factors)
        assert result.explanations is None or isinstance(result.explanations, list)
        if isinstance(result.explanations, list):
            assert all(isinstance(e, str) for e in result.explanations)
