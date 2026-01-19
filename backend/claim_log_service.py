"""
Claim Log service for generating insurance-ready claim documentation.

This module provides pure, deterministic functions to build and export claim logs
from hazard events and weather snapshots. Used for boondocking incidents that
need insurance documentation.

The ClaimLog structure includes:
- Metadata: route_id, generated_at, schema_version
- Events: list of HazardEvents (timestamp, type, severity, location, notes)
- Weather: WeatherSnapshot with summary and key metrics
- Totals: Summary counts by hazard type and severity
- Narrative: Insurance-ready paragraph describing the incident

All functions are pure (no I/O, no network calls, no state mutations).
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import json


# ==================== Data Models ====================

@dataclass(frozen=True)
class HazardEvent:
    """A single hazard event during a trip.
    
    Attributes:
        timestamp: ISO 8601 formatted datetime of event
        type: Hazard type (e.g., "hail", "flood", "high_wind", "ice", "tornado_warning")
        severity: Severity level ("low", "medium", "high")
        location: Tuple of (latitude, longitude)
        notes: Optional human-readable description
        evidence: Optional reference to evidence (URL, radar snapshot ID, etc.)
    """
    timestamp: str  # ISO 8601
    type: str
    severity: str  # "low", "medium", "high"
    location: tuple  # (lat, lon)
    notes: Optional[str] = None
    evidence: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "timestamp": self.timestamp,
            "type": self.type,
            "severity": self.severity,
            "location": {
                "latitude": self.location[0],
                "longitude": self.location[1],
            },
            "notes": self.notes,
            "evidence": self.evidence,
        }


@dataclass(frozen=True)
class WeatherSnapshot:
    """Weather conditions during the incident.
    
    Attributes:
        summary: Human-readable weather summary (e.g., "Severe thunderstorm")
        source: Data source (e.g., "NWS", "OpenWeather", "user_reported")
        time_range: Tuple of (start_iso, end_iso) for weather observation period
        key_metrics: Dict with metrics like wind_mph, precip_in, temp_f, alerts list
    """
    summary: str
    source: str
    time_range: tuple  # (start_iso, end_iso)
    key_metrics: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "summary": self.summary,
            "source": self.source,
            "time_range": {
                "start": self.time_range[0],
                "end": self.time_range[1],
            },
            "key_metrics": self.key_metrics,
        }


@dataclass(frozen=True)
class ClaimLog:
    """Insurance-ready claim log documenting an incident.
    
    This dataclass represents the complete claim documentation for an incident
    during a trip. It includes hazard events, weather conditions, and a narrative
    summary suitable for insurance filing.
    
    Attributes:
        schema_version: Version of ClaimLog schema (e.g., "1.0")
        route_id: Unique identifier for the trip/route
        generated_at: ISO 8601 timestamp when log was generated
        hazards: List of HazardEvent objects
        weather_snapshot: WeatherSnapshot object
        totals: Dict with summary counts (by type, by severity)
        narrative: Insurance-ready paragraph summarizing incident
    """
    schema_version: str
    route_id: str
    generated_at: str  # ISO 8601
    hazards: List[HazardEvent]
    weather_snapshot: WeatherSnapshot
    totals: Dict[str, Any]
    narrative: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "schema_version": self.schema_version,
            "route_id": self.route_id,
            "generated_at": self.generated_at,
            "hazards": [h.to_dict() for h in self.hazards],
            "weather_snapshot": self.weather_snapshot.to_dict(),
            "totals": self.totals,
            "narrative": self.narrative,
        }

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=2)


# ==================== Helper Functions ====================

def _compute_totals(hazards: List[HazardEvent]) -> Dict[str, Any]:
    """Compute summary statistics from hazard list.
    
    Args:
        hazards: List of HazardEvent objects
        
    Returns:
        Dict with keys:
        - total_events: int
        - by_type: dict mapping type -> count
        - by_severity: dict mapping severity -> count
    """
    by_type: Dict[str, int] = {}
    by_severity: Dict[str, int] = {}
    
    for hazard in hazards:
        by_type[hazard.type] = by_type.get(hazard.type, 0) + 1
        by_severity[hazard.severity] = by_severity.get(hazard.severity, 0) + 1
    
    return {
        "total_events": len(hazards),
        "by_type": by_type,
        "by_severity": by_severity,
    }


def _generate_narrative(
    hazards: List[HazardEvent],
    weather: WeatherSnapshot,
    route_id: str,
) -> str:
    """Generate insurance-ready narrative summary.
    
    Args:
        hazards: List of HazardEvent objects
        weather: WeatherSnapshot object
        route_id: Route identifier
        
    Returns:
        String narrative suitable for insurance claim documentation
    """
    if not hazards:
        return (
            f"No significant hazard events were recorded on route {route_id} "
            f"during the observation period. Weather conditions were {weather.summary.lower()}."
        )
    
    # Count hazards by severity
    high_severity = sum(1 for h in hazards if h.severity == "high")
    medium_severity = sum(1 for h in hazards if h.severity == "medium")
    low_severity = sum(1 for h in hazards if h.severity == "low")
    
    # List unique hazard types
    hazard_types = sorted(set(h.type for h in hazards))
    type_str = ", ".join(hazard_types)
    
    # Build narrative
    parts = [
        f"On route {route_id}, {len(hazards)} hazard event(s) were documented.",
        f"Event types included: {type_str}.",
        f"Severity breakdown: {high_severity} high, {medium_severity} medium, {low_severity} low.",
        f"Weather conditions: {weather.summary}.",
        "Detailed event log and weather metrics are provided below.",
    ]
    
    return " ".join(parts)


# ==================== Public API ====================

def build_claim_log(
    route_id: str,
    hazards: List[HazardEvent],
    weather_snapshot: WeatherSnapshot,
    generated_at: Optional[str] = None,
    schema_version: str = "1.0",
) -> ClaimLog:
    """Build a claim log from hazard events and weather data.
    
    This is the primary public function for creating claim logs. It's pure and
    deterministic: given the same inputs, it produces the same ClaimLog.
    
    Args:
        route_id: Unique identifier for the trip/route
        hazards: List of HazardEvent objects
        weather_snapshot: WeatherSnapshot object
        generated_at: ISO 8601 timestamp (defaults to current time if not provided)
        schema_version: Version string for the ClaimLog schema
        
    Returns:
        ClaimLog object suitable for export to JSON or PDF
        
    Raises:
        ValueError: If route_id is empty or hazards list is not valid
        
    Example:
        >>> hazards = [
        ...     HazardEvent(
        ...         timestamp="2026-01-18T14:30:00Z",
        ...         type="hail",
        ...         severity="high",
        ...         location=(40.7128, -74.0060),
        ...         notes="Hailstones 1-2 inches",
        ...     )
        ... ]
        >>> weather = WeatherSnapshot(
        ...     summary="Severe thunderstorm with large hail",
        ...     source="NWS",
        ...     time_range=("2026-01-18T14:00:00Z", "2026-01-18T15:00:00Z"),
        ...     key_metrics={"wind_mph": 45, "precip_in": 0.75, "temp_f": 68}
        ... )
        >>> log = build_claim_log("route_123", hazards, weather)
        >>> assert log.route_id == "route_123"
    """
    # Input validation
    if not route_id or not isinstance(route_id, str):
        raise ValueError("route_id must be a non-empty string")
    
    if not isinstance(hazards, list):
        raise ValueError("hazards must be a list")
    
    for idx, hazard in enumerate(hazards):
        if not isinstance(hazard, HazardEvent):
            raise ValueError(f"hazards[{idx}] must be a HazardEvent object")
    
    if not isinstance(weather_snapshot, WeatherSnapshot):
        raise ValueError("weather_snapshot must be a WeatherSnapshot object")
    
    # Default to current time if not provided (for testing, can override)
    if generated_at is None:
        generated_at = datetime.now(timezone.utc).isoformat()
    
    # Compute summary statistics
    totals = _compute_totals(hazards)
    
    # Generate narrative
    narrative = _generate_narrative(hazards, weather_snapshot, route_id)
    
    return ClaimLog(
        schema_version=schema_version,
        route_id=route_id,
        generated_at=generated_at,
        hazards=hazards,
        weather_snapshot=weather_snapshot,
        totals=totals,
        narrative=narrative,
    )
