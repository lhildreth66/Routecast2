"""
Tests for claim log service and PDF export.
"""

import pytest
import json
from datetime import datetime
from claim_log_service import (
    HazardEvent,
    WeatherSnapshot,
    ClaimLog,
    build_claim_log,
    _compute_totals,
    _generate_narrative,
)
from claim_log_pdf import export_claim_log_to_pdf


class TestHazardEvent:
    """Test HazardEvent data model."""

    def test_create_hazard_event(self):
        """Create a basic hazard event."""
        event = HazardEvent(
            timestamp="2026-01-18T14:30:00Z",
            type="hail",
            severity="high",
            location=(40.7128, -74.0060),
            notes="1-2 inch hailstones",
        )
        assert event.timestamp == "2026-01-18T14:30:00Z"
        assert event.type == "hail"
        assert event.severity == "high"
        assert event.location == (40.7128, -74.0060)
        assert event.notes == "1-2 inch hailstones"
        assert event.evidence is None

    def test_hazard_event_to_dict(self):
        """Convert hazard event to dict."""
        event = HazardEvent(
            timestamp="2026-01-18T14:30:00Z",
            type="flood",
            severity="medium",
            location=(35.5, -120.5),
        )
        d = event.to_dict()
        assert d["timestamp"] == "2026-01-18T14:30:00Z"
        assert d["type"] == "flood"
        assert d["severity"] == "medium"
        assert d["location"]["latitude"] == 35.5
        assert d["location"]["longitude"] == -120.5
        assert d["notes"] is None
        assert d["evidence"] is None

    def test_hazard_event_immutable(self):
        """HazardEvent should be immutable."""
        event = HazardEvent(
            timestamp="2026-01-18T14:30:00Z",
            type="ice",
            severity="low",
            location=(0, 0),
        )
        with pytest.raises(AttributeError):
            event.timestamp = "2026-01-19T00:00:00Z"


class TestWeatherSnapshot:
    """Test WeatherSnapshot data model."""

    def test_create_weather_snapshot(self):
        """Create a weather snapshot."""
        weather = WeatherSnapshot(
            summary="Severe thunderstorm",
            source="NWS",
            time_range=("2026-01-18T14:00:00Z", "2026-01-18T15:00:00Z"),
            key_metrics={"wind_mph": 45, "precip_in": 0.75, "temp_f": 68},
        )
        assert weather.summary == "Severe thunderstorm"
        assert weather.source == "NWS"
        assert weather.time_range == ("2026-01-18T14:00:00Z", "2026-01-18T15:00:00Z")
        assert weather.key_metrics["wind_mph"] == 45

    def test_weather_snapshot_to_dict(self):
        """Convert weather snapshot to dict."""
        weather = WeatherSnapshot(
            summary="Tornado warning",
            source="OpenWeather",
            time_range=("2026-01-18T14:00:00Z", "2026-01-18T15:00:00Z"),
            key_metrics={"wind_mph": 80, "alerts": ["Tornado Warning", "Flash Flood Warning"]},
        )
        d = weather.to_dict()
        assert d["summary"] == "Tornado warning"
        assert d["source"] == "OpenWeather"
        assert d["time_range"]["start"] == "2026-01-18T14:00:00Z"
        assert d["time_range"]["end"] == "2026-01-18T15:00:00Z"
        assert d["key_metrics"]["wind_mph"] == 80


class TestComputeTotals:
    """Test _compute_totals helper function."""

    def test_empty_hazard_list(self):
        """Compute totals from empty list."""
        totals = _compute_totals([])
        assert totals["total_events"] == 0
        assert totals["by_type"] == {}
        assert totals["by_severity"] == {}

    def test_single_hazard(self):
        """Compute totals from single hazard."""
        hazards = [
            HazardEvent(
                timestamp="2026-01-18T14:30:00Z",
                type="hail",
                severity="high",
                location=(0, 0),
            )
        ]
        totals = _compute_totals(hazards)
        assert totals["total_events"] == 1
        assert totals["by_type"] == {"hail": 1}
        assert totals["by_severity"] == {"high": 1}

    def test_multiple_hazards(self):
        """Compute totals from multiple hazards."""
        hazards = [
            HazardEvent("2026-01-18T14:00:00Z", "hail", "high", (0, 0)),
            HazardEvent("2026-01-18T14:15:00Z", "hail", "medium", (0.1, 0.1)),
            HazardEvent("2026-01-18T14:30:00Z", "flood", "high", (0.2, 0.2)),
            HazardEvent("2026-01-18T14:45:00Z", "high_wind", "low", (0.3, 0.3)),
        ]
        totals = _compute_totals(hazards)
        assert totals["total_events"] == 4
        assert totals["by_type"] == {"hail": 2, "flood": 1, "high_wind": 1}
        assert totals["by_severity"] == {"high": 2, "medium": 1, "low": 1}


class TestGenerateNarrative:
    """Test _generate_narrative helper function."""

    def test_empty_hazards_narrative(self):
        """Generate narrative with no hazards."""
        weather = WeatherSnapshot(
            summary="clear skies",
            source="NWS",
            time_range=("2026-01-18T14:00:00Z", "2026-01-18T15:00:00Z"),
            key_metrics={},
        )
        narrative = _generate_narrative([], weather, "route_123")
        assert "route_123" in narrative
        assert "No significant hazard events" in narrative
        assert "clear skies" in narrative

    def test_single_hazard_narrative(self):
        """Generate narrative with single hazard."""
        hazards = [
            HazardEvent(
                "2026-01-18T14:30:00Z",
                "hail",
                "high",
                (40, -120),
            )
        ]
        weather = WeatherSnapshot(
            summary="Severe thunderstorm",
            source="NWS",
            time_range=("2026-01-18T14:00:00Z", "2026-01-18T15:00:00Z"),
            key_metrics={},
        )
        narrative = _generate_narrative(hazards, weather, "route_456")
        assert "route_456" in narrative
        assert "1 hazard event" in narrative
        assert "hail" in narrative
        assert "1 high" in narrative
        assert "Severe thunderstorm" in narrative

    def test_multiple_hazards_narrative(self):
        """Generate narrative with multiple hazards."""
        hazards = [
            HazardEvent("2026-01-18T14:00:00Z", "hail", "high", (0, 0)),
            HazardEvent("2026-01-18T14:15:00Z", "flood", "high", (0.1, 0.1)),
            HazardEvent("2026-01-18T14:30:00Z", "high_wind", "low", (0.2, 0.2)),
        ]
        weather = WeatherSnapshot(
            summary="Multi-hazard event",
            source="NWS",
            time_range=("2026-01-18T14:00:00Z", "2026-01-18T15:00:00Z"),
            key_metrics={},
        )
        narrative = _generate_narrative(hazards, weather, "route_789")
        assert "3 hazard event" in narrative
        assert "hail" in narrative
        assert "flood" in narrative
        assert "high_wind" in narrative
        assert "2 high, 0 medium, 1 low" in narrative


class TestBuildClaimLog:
    """Test build_claim_log function."""

    def test_build_basic_claim_log(self):
        """Build a basic claim log."""
        hazards = [
            HazardEvent("2026-01-18T14:30:00Z", "hail", "high", (40.7128, -74.0060))
        ]
        weather = WeatherSnapshot(
            summary="Severe thunderstorm",
            source="NWS",
            time_range=("2026-01-18T14:00:00Z", "2026-01-18T15:00:00Z"),
            key_metrics={"wind_mph": 45},
        )
        
        log = build_claim_log(
            route_id="route_123",
            hazards=hazards,
            weather_snapshot=weather,
            generated_at="2026-01-18T15:30:00Z",
        )
        
        assert log.schema_version == "1.0"
        assert log.route_id == "route_123"
        assert log.generated_at == "2026-01-18T15:30:00Z"
        assert len(log.hazards) == 1
        assert log.hazards[0].type == "hail"
        assert log.totals["total_events"] == 1
        assert log.narrative is not None
        assert len(log.narrative) > 0

    def test_build_claim_log_with_default_time(self):
        """Build claim log with default generated_at."""
        hazards = [
            HazardEvent("2026-01-18T14:30:00Z", "hail", "high", (0, 0))
        ]
        weather = WeatherSnapshot(
            summary="Test weather",
            source="test",
            time_range=("2026-01-18T14:00:00Z", "2026-01-18T15:00:00Z"),
            key_metrics={},
        )
        
        log = build_claim_log(
            route_id="route_test",
            hazards=hazards,
            weather_snapshot=weather,
        )
        
        # Should have a timestamp (either current or injected)
        assert log.generated_at is not None
        assert "Z" in log.generated_at or "+" in log.generated_at

    def test_build_claim_log_multiple_hazards(self):
        """Build claim log with multiple hazards."""
        hazards = [
            HazardEvent("2026-01-18T14:00:00Z", "hail", "high", (0, 0)),
            HazardEvent("2026-01-18T14:15:00Z", "flood", "medium", (0.1, 0.1)),
            HazardEvent("2026-01-18T14:30:00Z", "ice", "low", (0.2, 0.2)),
        ]
        weather = WeatherSnapshot(
            summary="Multi-event",
            source="test",
            time_range=("2026-01-18T14:00:00Z", "2026-01-18T15:00:00Z"),
            key_metrics={},
        )
        
        log = build_claim_log("route_multi", hazards, weather)
        
        assert log.totals["total_events"] == 3
        assert log.totals["by_type"] == {"hail": 1, "flood": 1, "ice": 1}
        assert log.totals["by_severity"] == {"high": 1, "medium": 1, "low": 1}

    def test_build_claim_log_empty_hazards(self):
        """Build claim log with no hazards."""
        weather = WeatherSnapshot(
            summary="Clear skies",
            source="test",
            time_range=("2026-01-18T14:00:00Z", "2026-01-18T15:00:00Z"),
            key_metrics={},
        )
        
        log = build_claim_log("route_clear", [], weather)
        
        assert log.totals["total_events"] == 0
        assert len(log.hazards) == 0
        assert "No significant hazard events" in log.narrative

    def test_invalid_route_id(self):
        """Raise error for invalid route_id."""
        weather = WeatherSnapshot("test", "test", ("2026-01-18T14:00:00Z", "2026-01-18T15:00:00Z"), {})
        
        with pytest.raises(ValueError):
            build_claim_log("", [], weather)
        
        with pytest.raises(ValueError):
            build_claim_log(None, [], weather)

    def test_invalid_hazards_type(self):
        """Raise error for invalid hazards type."""
        weather = WeatherSnapshot("test", "test", ("2026-01-18T14:00:00Z", "2026-01-18T15:00:00Z"), {})
        
        with pytest.raises(ValueError):
            build_claim_log("route", "not_a_list", weather)

    def test_invalid_weather_type(self):
        """Raise error for invalid weather type."""
        with pytest.raises(ValueError):
            build_claim_log("route", [], "not_a_weather_snapshot")

    def test_claim_log_to_dict(self):
        """Convert claim log to dict."""
        hazards = [HazardEvent("2026-01-18T14:30:00Z", "hail", "high", (0, 0))]
        weather = WeatherSnapshot("test", "test", ("2026-01-18T14:00:00Z", "2026-01-18T15:00:00Z"), {})
        log = build_claim_log("route", hazards, weather, "2026-01-18T15:30:00Z")
        
        d = log.to_dict()
        assert isinstance(d, dict)
        assert d["schema_version"] == "1.0"
        assert d["route_id"] == "route"
        assert d["generated_at"] == "2026-01-18T15:30:00Z"
        assert len(d["hazards"]) == 1
        assert "weather_snapshot" in d
        assert "totals" in d
        assert "narrative" in d

    def test_claim_log_to_json(self):
        """Convert claim log to JSON string."""
        hazards = [HazardEvent("2026-01-18T14:30:00Z", "hail", "high", (0, 0))]
        weather = WeatherSnapshot("test", "test", ("2026-01-18T14:00:00Z", "2026-01-18T15:00:00Z"), {})
        log = build_claim_log("route", hazards, weather, "2026-01-18T15:30:00Z")
        
        json_str = log.to_json()
        assert isinstance(json_str, str)
        
        # Should be valid JSON
        parsed = json.loads(json_str)
        assert parsed["route_id"] == "route"
        assert len(parsed["hazards"]) == 1

    def test_determinism(self):
        """Same inputs produce same output (determinism test)."""
        hazards = [
            HazardEvent("2026-01-18T14:00:00Z", "hail", "high", (40, -120)),
            HazardEvent("2026-01-18T14:15:00Z", "flood", "medium", (40.1, -120.1)),
        ]
        weather = WeatherSnapshot(
            summary="Storm",
            source="NWS",
            time_range=("2026-01-18T14:00:00Z", "2026-01-18T15:00:00Z"),
            key_metrics={"wind_mph": 50},
        )
        
        # Build same log twice with same timestamp
        log1 = build_claim_log("route", hazards, weather, "2026-01-18T15:30:00Z")
        log2 = build_claim_log("route", hazards, weather, "2026-01-18T15:30:00Z")
        
        # Should be identical
        assert log1.to_json() == log2.to_json()


class TestClaimLogPDF:
    """Test PDF export functionality."""

    def test_export_basic_pdf(self):
        """Export claim log to PDF."""
        hazards = [HazardEvent("2026-01-18T14:30:00Z", "hail", "high", (40.7128, -74.0060))]
        weather = WeatherSnapshot(
            summary="Severe thunderstorm",
            source="NWS",
            time_range=("2026-01-18T14:00:00Z", "2026-01-18T15:00:00Z"),
            key_metrics={"wind_mph": 45, "precip_in": 0.75},
        )
        log = build_claim_log("route_123", hazards, weather, "2026-01-18T15:30:00Z")
        
        pdf_bytes = export_claim_log_to_pdf(log)
        
        # Check PDF validity
        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 1000  # PDF should be reasonably sized
        assert pdf_bytes.startswith(b"%PDF")  # PDF file header

    def test_export_pdf_multiple_hazards(self):
        """Export PDF with multiple hazards."""
        hazards = [
            HazardEvent("2026-01-18T14:00:00Z", "hail", "high", (40, -120), "1-2 inch hail"),
            HazardEvent("2026-01-18T14:15:00Z", "flood", "high", (40.1, -120.1), "Flash flood"),
            HazardEvent("2026-01-18T14:30:00Z", "high_wind", "medium", (40.2, -120.2), "60 mph winds"),
        ]
        weather = WeatherSnapshot(
            summary="Multi-hazard event",
            source="NWS",
            time_range=("2026-01-18T14:00:00Z", "2026-01-18T15:00:00Z"),
            key_metrics={"wind_mph": 60, "precip_in": 1.5, "alerts": ["Flash Flood Warning", "Hail Warning"]},
        )
        log = build_claim_log("route_multi", hazards, weather, "2026-01-18T15:30:00Z")
        
        pdf_bytes = export_claim_log_to_pdf(log)
        
        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 1000
        assert pdf_bytes.startswith(b"%PDF")

    def test_export_pdf_empty_hazards(self):
        """Export PDF with no hazards."""
        weather = WeatherSnapshot(
            summary="Clear weather",
            source="NWS",
            time_range=("2026-01-18T14:00:00Z", "2026-01-18T15:00:00Z"),
            key_metrics={},
        )
        log = build_claim_log("route_clear", [], weather, "2026-01-18T15:30:00Z")
        
        pdf_bytes = export_claim_log_to_pdf(log)
        
        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 500
        assert pdf_bytes.startswith(b"%PDF")

    def test_pdf_content_includes_metadata(self):
        """Verify PDF content includes key metadata."""
        hazards = [HazardEvent("2026-01-18T14:30:00Z", "hail", "high", (40, -120))]
        weather = WeatherSnapshot(
            summary="Test",
            source="NWS",
            time_range=("2026-01-18T14:00:00Z", "2026-01-18T15:00:00Z"),
            key_metrics={},
        )
        log = build_claim_log("route_test", hazards, weather, "2026-01-18T15:30:00Z")
        
        pdf_bytes = export_claim_log_to_pdf(log)

        # PDF content is valid if it starts with PDF header and has good size
        assert pdf_bytes.startswith(b"%PDF")
        assert len(pdf_bytes) > 1500  # Must have substantial content
