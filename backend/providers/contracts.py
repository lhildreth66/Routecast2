from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol


class GeocodeProvider(Protocol):
    async def geocode(self, location: str) -> Optional[Dict[str, float]]:
        ...

    async def reverse_geocode(self, lat: float, lon: float) -> Optional[str]:
        ...

    async def search_pois(
        self, lat: float, lon: float, query: str, limit: int = 2
    ) -> List[Dict[str, Any]]:
        ...


class DirectionsProvider(Protocol):
    async def route(
        self,
        origin_coords: Dict[str, float],
        dest_coords: Dict[str, float],
        waypoints: Optional[List[Dict[str, float]]],
    ) -> Optional[Dict[str, float]]:
        ...


class WeatherProvider(Protocol):
    async def get_weather(self, lat: float, lon: float) -> Optional[Dict[str, Any]]:
        ...


class AlertsProvider(Protocol):
    async def get_alerts(self, lat: float, lon: float) -> List[Dict[str, Any]]:
        ...


class ElevationProvider(Protocol):
    async def get_elevation(self, lat: float, lon: float) -> Optional[float]:
        ...


class SoilProvider(Protocol):
    async def get_soil_type(self, lat: float, lon: float) -> Optional[str]:
        ...


class CellCoverageProvider(Protocol):
    async def get_coverage(self, lat: float, lon: float) -> Dict[str, Any]:
        ...


class WildfireProvider(Protocol):
    async def get_wildfire_risk(self, lat: float, lon: float) -> Dict[str, Any]:
        ...


class PublicLandsProvider(Protocol):
    async def get_public_land(self, lat: float, lon: float) -> Dict[str, Any]:
        ...


class RadarProvider(Protocol):
    async def get_radar_tile(self, lat: float, lon: float) -> Dict[str, Any]:
        ...
