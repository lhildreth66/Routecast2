from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from .contracts import (
    AlertsProvider,
    CellCoverageProvider,
    DirectionsProvider,
    ElevationProvider,
    GeocodeProvider,
    PublicLandsProvider,
    RadarProvider,
    SoilProvider,
    WeatherProvider,
    WildfireProvider,
)

FIXTURES_ROOT = Path(__file__).parent.parent / "fixtures" / "demo"


class _FixtureLoader:
    def __init__(self, fixture_name: str):
        self.path = FIXTURES_ROOT / fixture_name / "data.json"
        with self.path.open("r", encoding="utf-8") as f:
            self.data = json.load(f)


class FakeGeocodeProvider(GeocodeProvider, _FixtureLoader):
    def __init__(self) -> None:
        _FixtureLoader.__init__(self, "geocode")

    async def geocode(self, location: str) -> Optional[Dict[str, float]]:
        key = location.strip().lower()
        entry = self.data.get("locations", {}).get(key)
        if entry:
            return {"lat": entry["lat"], "lon": entry["lon"]}
        return None

    async def reverse_geocode(self, lat: float, lon: float) -> Optional[str]:
        coord_key = f"{round(lat, 4)},{round(lon, 4)}"
        mapping = self.data.get("reverse", {})
        if coord_key in mapping:
            return mapping[coord_key]
        return None

    async def search_pois(
        self, lat: float, lon: float, query: str, limit: int = 2
    ) -> List[Dict[str, Any]]:
        pois = self.data.get("pois", [])
        return pois[:limit]


class FakeDirectionsProvider(DirectionsProvider, _FixtureLoader):
    def __init__(self) -> None:
        _FixtureLoader.__init__(self, "directions")

    async def route(
        self,
        origin_coords: Dict[str, float],
        dest_coords: Dict[str, float],
        waypoints: Optional[List[Dict[str, float]]],
    ) -> Optional[Dict[str, float]]:
        routes = self.data.get("routes", [])
        for route in routes:
            if route.get("origin_lat") is not None:
                if (
                    round(origin_coords.get("lat"), 4) == round(route["origin_lat"], 4)
                    and round(dest_coords.get("lat"), 4) == round(route["dest_lat"], 4)
                ):
                    return {
                        "geometry": route["geometry"],
                        "duration": route["duration_minutes"],
                        "distance": route["distance_miles"],
                    }
        if routes:
            fallback = routes[0]
            return {
                "geometry": fallback["geometry"],
                "duration": fallback["duration_minutes"],
                "distance": fallback["distance_miles"],
            }
        return None


class FakeWeatherProvider(WeatherProvider, _FixtureLoader):
    def __init__(self) -> None:
        _FixtureLoader.__init__(self, "weather")

    async def get_weather(self, lat: float, lon: float) -> Optional[Dict[str, Any]]:
        for point in self.data.get("points", []):
            if (
                abs(point["lat"] - lat) < 0.5
                and abs(point["lon"] - lon) < 0.5
            ):
                return point["weather"]
        return None


class FakeAlertsProvider(AlertsProvider, _FixtureLoader):
    def __init__(self) -> None:
        _FixtureLoader.__init__(self, "alerts")

    async def get_alerts(self, lat: float, lon: float) -> List[Dict[str, Any]]:
        for point in self.data.get("points", []):
            if (
                abs(point["lat"] - lat) < 0.5
                and abs(point["lon"] - lon) < 0.5
            ):
                return point.get("alerts", [])
        return []


class FakeElevationProvider(ElevationProvider, _FixtureLoader):
    def __init__(self) -> None:
        _FixtureLoader.__init__(self, "elevation")

    async def get_elevation(self, lat: float, lon: float) -> Optional[float]:
        for point in self.data.get("points", []):
            if (
                abs(point["lat"] - lat) < 0.5
                and abs(point["lon"] - lon) < 0.5
            ):
                return float(point["elevation_ft"])
        return None


class FakeSoilProvider(SoilProvider, _FixtureLoader):
    def __init__(self) -> None:
        _FixtureLoader.__init__(self, "soil")

    async def get_soil_type(self, lat: float, lon: float) -> Optional[str]:
        for point in self.data.get("points", []):
            if (
                abs(point["lat"] - lat) < 0.5
                and abs(point["lon"] - lon) < 0.5
            ):
                return point.get("soil_type")
        return None


class FakeCellCoverageProvider(CellCoverageProvider, _FixtureLoader):
    def __init__(self) -> None:
        _FixtureLoader.__init__(self, "cell_coverage")

    async def get_coverage(self, lat: float, lon: float) -> Dict[str, Any]:
        for point in self.data.get("points", []):
            if (
                abs(point["lat"] - lat) < 0.5
                and abs(point["lon"] - lon) < 0.5
            ):
                return point.get("coverage", {})
        return {"bars": None, "network": None}


class FakeWildfireProvider(WildfireProvider, _FixtureLoader):
    def __init__(self) -> None:
        _FixtureLoader.__init__(self, "wildfire")

    async def get_wildfire_risk(self, lat: float, lon: float) -> Dict[str, Any]:
        for point in self.data.get("points", []):
            if (
                abs(point["lat"] - lat) < 0.5
                and abs(point["lon"] - lon) < 0.5
            ):
                return point.get("wildfire", {})
        return {"risk": None, "advisory": None}


class FakePublicLandsProvider(PublicLandsProvider, _FixtureLoader):
    def __init__(self) -> None:
        _FixtureLoader.__init__(self, "public_lands")

    async def get_public_land(self, lat: float, lon: float) -> Dict[str, Any]:
        for point in self.data.get("points", []):
            if (
                abs(point["lat"] - lat) < 0.5
                and abs(point["lon"] - lon) < 0.5
            ):
                return point.get("public_land", {})
        return {"designation": None, "name": None}


class FakeRadarProvider(RadarProvider, _FixtureLoader):
    def __init__(self) -> None:
        _FixtureLoader.__init__(self, "radar")

    async def get_radar_tile(self, lat: float, lon: float) -> Dict[str, Any]:
        return self.data.get("tile", {"url": None})
