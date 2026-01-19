from __future__ import annotations

import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

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

MAPBOX_ACCESS_TOKEN = os.environ.get("MAPBOX_ACCESS_TOKEN", "")
NOAA_USER_AGENT = os.environ.get(
    "NOAA_USER_AGENT", "Routecast/1.0 (contact@routecast.app)"
)
NOAA_HEADERS = {"User-Agent": NOAA_USER_AGENT, "Accept": "application/geo+json"}


class MapboxGeocodeProvider(GeocodeProvider):
    async def geocode(self, location: str) -> Optional[Dict[str, float]]:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                url = f"https://api.mapbox.com/geocoding/v5/mapbox.places/{location}.json"
                params = {
                    "access_token": MAPBOX_ACCESS_TOKEN,
                    "limit": 1,
                    "country": "US",
                }
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                if data.get("features"):
                    coords = data["features"][0]["center"]
                    return {"lon": coords[0], "lat": coords[1]}
        except Exception:
            return None
        return None

    async def reverse_geocode(self, lat: float, lon: float) -> Optional[str]:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                url = f"https://api.mapbox.com/geocoding/v5/mapbox.places/{lon},{lat}.json"
                params = {"access_token": MAPBOX_ACCESS_TOKEN, "types": "place,locality", "limit": 1}
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                if data.get("features"):
                    feature = data["features"][0]
                    place_name = feature.get("text", "")
                    state = ""
                    for ctx in feature.get("context", []):
                        if ctx.get("id", "").startswith("region"):
                            state = ctx.get("short_code", "").replace("US-", "")
                            break
                    if place_name and state:
                        return f"{place_name}, {state}"
                    return place_name or None
        except Exception:
            return None
        return None

    async def search_pois(
        self, lat: float, lon: float, query: str, limit: int = 2
    ) -> List[Dict[str, Any]]:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                url = f"https://api.mapbox.com/geocoding/v5/mapbox.places/{query}.json"
                params = {
                    "access_token": MAPBOX_ACCESS_TOKEN,
                    "proximity": f"{lon},{lat}",
                    "types": "poi",
                    "limit": limit,
                }
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                pois: List[Dict[str, Any]] = []
                for feature in data.get("features", [])[:limit]:
                    coords = feature.get("center", [lon, lat])
                    pois.append(
                        {
                            "name": feature.get("text", "POI"),
                            "lat": coords[1],
                            "lon": coords[0],
                            "type": feature.get("properties", {}).get("category", "poi"),
                        }
                    )
                return pois
        except Exception:
            return []


class MapboxDirectionsProvider(DirectionsProvider):
    async def route(
        self,
        origin_coords: Dict[str, float],
        dest_coords: Dict[str, float],
        waypoints: Optional[List[Dict[str, float]]],
    ) -> Optional[Dict[str, float]]:
        try:
            coords_list = [f"{origin_coords['lon']},{origin_coords['lat']}"]
            if waypoints:
                for wp in waypoints:
                    coords_list.append(f"{wp['lon']},{wp['lat']}")
            coords_list.append(f"{dest_coords['lon']},{dest_coords['lat']}")
            coords_str = ";".join(coords_list)
            async with httpx.AsyncClient(timeout=10.0) as client:
                url = f"https://api.mapbox.com/directions/v5/mapbox/driving/{coords_str}"
                params = {"access_token": MAPBOX_ACCESS_TOKEN, "geometries": "polyline", "overview": "full"}
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                if data.get("code") == "NoRoute":
                    return None
                if data.get("routes"):
                    route = data["routes"][0]
                    return {
                        "geometry": route.get("geometry"),
                        "duration": route.get("duration", 0) / 60,
                        "distance": route.get("distance", 0) / 1609.34,
                    }
        except Exception:
            return None
        return None


class NOAAWeatherProvider(WeatherProvider):
    async def get_weather(self, lat: float, lon: float) -> Optional[Dict[str, Any]]:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                point_url = f"https://api.weather.gov/points/{lat:.4f},{lon:.4f}"
                point_response = await client.get(point_url, headers=NOAA_HEADERS)
                if point_response.status_code != 200:
                    return None
                point_data = point_response.json()
                forecast_url = point_data.get("properties", {}).get("forecastHourly")
                if not forecast_url:
                    return None
                forecast_response = await client.get(forecast_url, headers=NOAA_HEADERS)
                if forecast_response.status_code != 200:
                    return None
                forecast_data = forecast_response.json()
                periods = forecast_data.get("properties", {}).get("periods", [])
                hourly: List[Dict[str, Any]] = []
                for period in periods[:12]:
                    hourly.append(
                        {
                            "time": period.get("startTime", ""),
                            "temperature": period.get("temperature", 0),
                            "conditions": period.get("shortForecast", ""),
                            "wind_speed": period.get("windSpeed", ""),
                            "precipitation_chance": period.get("probabilityOfPrecipitation", {}).get("value"),
                        }
                    )
                if periods:
                    current = periods[0]
                    is_daytime = current.get("isDaytime", True)
                    now = datetime.now()
                    sunrise = now.replace(hour=6, minute=30).strftime("%I:%M %p")
                    sunset = now.replace(hour=18, minute=30).strftime("%I:%M %p")
                    return {
                        "temperature": current.get("temperature"),
                        "temperature_unit": current.get("temperatureUnit", "F"),
                        "wind_speed": current.get("windSpeed"),
                        "wind_direction": current.get("windDirection"),
                        "conditions": current.get("shortForecast"),
                        "icon": current.get("icon"),
                        "humidity": current.get("relativeHumidity", {}).get("value"),
                        "is_daytime": is_daytime,
                        "sunrise": sunrise,
                        "sunset": sunset,
                        "hourly_forecast": hourly,
                    }
        except Exception:
            return None
        return None


class NOAAAlertsProvider(AlertsProvider):
    async def get_alerts(self, lat: float, lon: float) -> List[Dict[str, Any]]:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                url = f"https://api.weather.gov/alerts?point={lat:.4f},{lon:.4f}"
                response = await client.get(url, headers=NOAA_HEADERS)
                if response.status_code != 200:
                    return []
                data = response.json()
                alerts: List[Dict[str, Any]] = []
                for feature in data.get("features", [])[:5]:
                    props = feature.get("properties", {})
                    alerts.append(
                        {
                            "id": props.get("id", str(uuid.uuid4())),
                            "headline": props.get("headline", "Weather Alert"),
                            "severity": props.get("severity", "Unknown"),
                            "event": props.get("event", "Weather Event"),
                            "description": props.get("description", "")[:500],
                            "areas": props.get("areaDesc"),
                        }
                    )
                return alerts
        except Exception:
            return []


class DefaultElevationProvider(ElevationProvider):
    async def get_elevation(self, lat: float, lon: float) -> Optional[float]:
        return None


class DefaultSoilProvider(SoilProvider):
    async def get_soil_type(self, lat: float, lon: float) -> Optional[str]:
        return None


class DefaultCellCoverageProvider(CellCoverageProvider):
    async def get_coverage(self, lat: float, lon: float) -> Dict[str, Any]:
        return {"bars": None, "network": None}


class DefaultWildfireProvider(WildfireProvider):
    async def get_wildfire_risk(self, lat: float, lon: float) -> Dict[str, Any]:
        return {"risk": None, "advisory": None}


class DefaultPublicLandsProvider(PublicLandsProvider):
    async def get_public_land(self, lat: float, lon: float) -> Dict[str, Any]:
        return {"designation": None, "name": None}


class DefaultRadarProvider(RadarProvider):
    async def get_radar_tile(self, lat: float, lon: float) -> Dict[str, Any]:
        return {"url": None}
