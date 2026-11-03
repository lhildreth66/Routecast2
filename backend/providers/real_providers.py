from __future__ import annotations

import asyncio
import math
import os
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
import logging

import httpx
import polyline

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

# Smart Weather Rerouting corridor generation: in addition to Mapbox's own alternatives=true
# routes, request these road-class exclusions to surface genuinely different corridors (e.g. an
# interstate/turnpike-heavy route vs. a US-highway/surface-road route) — nationwide, not tied to
# any specific road name. Best-effort only: a slow/failed variant just yields fewer corridors.
CORRIDOR_EXCLUDE_VARIANTS = ["motorway", "toll"]
CORRIDOR_VARIANT_TIMEOUT_SECONDS = float(os.environ.get("MAPBOX_CORRIDOR_TIMEOUT_SECONDS", "6.0"))
# A candidate corridor is discarded if it is more than this multiple of the primary route's
# distance — keeps "reasonable longer routes" in play without manufacturing absurd detours.
CORRIDOR_MAX_DETOUR_RATIO = float(os.environ.get("MAPBOX_CORRIDOR_MAX_DETOUR_RATIO", "1.75"))
# Distinctness check: a candidate must have at least this fraction of its sampled points more
# than CORRIDOR_DISTINCT_MIN_MILES away from every already-kept route to count as genuinely
# different, rather than a near-duplicate of an existing option.
CORRIDOR_DISTINCT_MIN_MILES = float(os.environ.get("MAPBOX_CORRIDOR_DISTINCT_MIN_MILES", "2.0"))
CORRIDOR_DISTINCT_MIN_FRACTION = float(os.environ.get("MAPBOX_CORRIDOR_DISTINCT_MIN_FRACTION", "0.3"))
CORRIDOR_MAX_TOTAL_ALTERNATES = int(os.environ.get("MAPBOX_CORRIDOR_MAX_ALTERNATES", "3"))

logger = logging.getLogger(__name__)
if not MAPBOX_ACCESS_TOKEN:
    logger.error("MAPBOX_ACCESS_TOKEN is missing - Mapbox providers will be offline.")


def _redact_token(value: str) -> str:
    if not value:
        return value
    return value.replace(MAPBOX_ACCESS_TOKEN, "<redacted>") if MAPBOX_ACCESS_TOKEN else value


def _haversine_miles(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    r = 3958.8
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(h)))


def _decode_polyline_safe(encoded: Optional[str]) -> List[Tuple[float, float]]:
    if not encoded:
        return []
    try:
        return polyline.decode(encoded, precision=6)
    except Exception:
        return []


def _sample_coords(coords: List[Tuple[float, float]], max_points: int = 50) -> List[Tuple[float, float]]:
    if len(coords) <= max_points:
        return coords
    step = max(1, len(coords) // max_points)
    return coords[::step]


def _is_reasonable_detour(candidate_distance_m: float, primary_distance_m: float) -> bool:
    if primary_distance_m <= 0:
        return True
    return candidate_distance_m <= primary_distance_m * CORRIDOR_MAX_DETOUR_RATIO


def _is_distinct_corridor(
    candidate_coords: List[Tuple[float, float]],
    kept_coords_list: List[List[Tuple[float, float]]],
) -> bool:
    """A candidate is distinct only if it stays meaningfully far from EVERY already-kept route
    for a large enough share of its length — not just momentarily diverging for a few miles."""
    if not candidate_coords:
        return False
    if not kept_coords_list:
        return True
    sample = _sample_coords(candidate_coords)
    for kept in kept_coords_list:
        kept_sample = _sample_coords(kept) if kept else []
        if not kept_sample:
            continue
        far_count = sum(
            1 for pt in sample
            if min(_haversine_miles(pt, k) for k in kept_sample) > CORRIDOR_DISTINCT_MIN_MILES
        )
        if (far_count / len(sample)) < CORRIDOR_DISTINCT_MIN_FRACTION:
            return False
    return True


def _select_distinct_corridors(
    primary_geometry: Optional[str],
    primary_distance_m: float,
    candidates: List[Dict[str, Any]],
    max_total: int = CORRIDOR_MAX_TOTAL_ALTERNATES,
) -> List[Dict[str, Any]]:
    """Filters candidate alternates down to genuinely distinct, reasonably-sized corridors.
    Never manufactures an alternate: if nothing qualifies, returns an empty list."""
    kept: List[Dict[str, Any]] = []
    kept_coords: List[List[Tuple[float, float]]] = []
    primary_coords = _decode_polyline_safe(primary_geometry)
    if primary_coords:
        kept_coords.append(primary_coords)

    for cand in candidates:
        if len(kept) >= max_total:
            break
        geometry = cand.get("geometry")
        cand_distance = cand.get("distance") or 0.0
        if not geometry or not _is_reasonable_detour(cand_distance, primary_distance_m):
            continue
        cand_coords = _decode_polyline_safe(geometry)
        if not cand_coords or not _is_distinct_corridor(cand_coords, kept_coords):
            continue
        kept.append(cand)
        kept_coords.append(cand_coords)

    return kept


class MapboxGeocodeProvider(GeocodeProvider):
    async def geocode(self, location: str) -> Optional[Dict[str, float]]:
        if not MAPBOX_ACCESS_TOKEN:
            logger.error("Mapbox geocode skipped - MAPBOX_ACCESS_TOKEN missing")
            return None
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                url = f"https://api.mapbox.com/geocoding/v5/mapbox.places/{location}.json"
                params = {
                    "access_token": MAPBOX_ACCESS_TOKEN,
                    "limit": 1,
                    "country": "US",
                }
                response = await client.get(url, params=params)
                if response.status_code >= 400:
                    logger.error("Mapbox geocode HTTP %s body=%s", response.status_code, response.text[:200])
                    response.raise_for_status()
                data = response.json()
                if data.get("features"):
                    coords = data["features"][0]["center"]
                    return {"lon": coords[0], "lat": coords[1]}
        except Exception as exc:
            logger.error("Mapbox geocode failed for %s: %s", location, exc)
            return None
        return None

    async def reverse_geocode(self, lat: float, lon: float) -> Optional[str]:
        if not MAPBOX_ACCESS_TOKEN:
            logger.error("Mapbox reverse geocode skipped - MAPBOX_ACCESS_TOKEN missing")
            return None
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                url = f"https://api.mapbox.com/geocoding/v5/mapbox.places/{lon},{lat}.json"
                params = {"access_token": MAPBOX_ACCESS_TOKEN, "types": "place,locality", "limit": 1}
                response = await client.get(url, params=params)
                if response.status_code >= 400:
                    logger.error("Mapbox reverse geocode HTTP %s body=%s", response.status_code, response.text[:200])
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
        except Exception as exc:
            logger.error("Mapbox reverse geocode failed for %s,%s: %s", lat, lon, exc)
            return None
        return None

    async def search_pois(
        self, lat: float, lon: float, query: str, limit: int = 2
    ) -> List[Dict[str, Any]]:
        if not MAPBOX_ACCESS_TOKEN:
            logger.error("Mapbox POI search skipped - MAPBOX_ACCESS_TOKEN missing")
            return []
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
                if response.status_code >= 400:
                    logger.error("Mapbox POI HTTP %s body=%s", response.status_code, response.text[:200])
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
        except Exception as exc:
            logger.error("Mapbox POI search failed query=%s: %s", query, exc)
            return []


class MapboxDirectionsProvider(DirectionsProvider):
    async def _fetch_route_variant(
        self,
        coords_str: str,
        exclude: Optional[str],
        timeout: float,
        with_alternatives: bool,
    ) -> Optional[Dict[str, Any]]:
        """One raw Mapbox Directions request. Returns the parsed primary route (+ its own
        Mapbox-native alternatives, when requested) or None on any failure — never raises."""
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                url = f"https://api.mapbox.com/directions/v5/mapbox/driving/{coords_str}"
                params = {
                    "access_token": MAPBOX_ACCESS_TOKEN,
                    "geometries": "polyline6",
                    "overview": "full",
                    "steps": "true",
                    "annotations": "distance,duration",
                }
                if with_alternatives:
                    # Smart Weather Rerouting Phase 0: ask Mapbox for its own extra route options.
                    params["alternatives"] = "true"
                if exclude:
                    params["exclude"] = exclude
                safe_params = {k: v for k, v in params.items() if k != "access_token"}
                safe_url = _redact_token(url)
                logger.info("MAPBOX_REQ directions url=%s params=%s", safe_url, safe_params)
                response = await client.get(url, params=params)
                redacted_body = _redact_token(response.text[:2000])
                logger.info("MAPBOX_RES directions status=%s body=%s", response.status_code, redacted_body)
                if response.status_code >= 400:
                    logger.error("Mapbox directions HTTP %s body=%s", response.status_code, response.text[:200])
                    response.raise_for_status()
                data = response.json()
                if data.get("code") == "NoRoute":
                    logger.warning("Mapbox returned NoRoute for coords=%s exclude=%s", coords_str[:120], exclude)
                    return None
                if not data.get("routes"):
                    return None

                route = data["routes"][0]
                legs = route.get("legs", []) or []
                steps_count = sum(len(l.get("steps", []) or []) for l in legs)
                route_distance = route.get("distance", 0)
                logger.info(
                    "MAPBOX steps_count=%s legs=%s route_distance_m=%s exclude=%s",
                    steps_count, len(legs), route_distance, exclude,
                )
                alternates = []
                if with_alternatives:
                    # Smart Weather Rerouting Phase 0: surface up to 2 Mapbox-native alternates.
                    for alt_route in data["routes"][1:3]:
                        if alt_route.get("geometry"):
                            alternates.append({
                                "geometry": alt_route.get("geometry"),
                                "duration": alt_route.get("duration", 0),
                                "distance": alt_route.get("distance", 0),
                            })
                return {
                    "geometry": route.get("geometry"),
                    # Mapbox returns duration in seconds; keep seconds so downstream conversions stay correct.
                    "duration": route.get("duration", 0),
                    "distance": route_distance,  # meters (per Mapbox)
                    "legs": legs,
                    "alternatives": alternates,
                }
        except Exception as exc:
            logger.error("Mapbox directions failed coords=%s exclude=%s: %s", coords_str[:120], exclude, exc)
            return None

    async def _fetch_corridor_variant_with_deadline(
        self, coords_str: str, exclude: str, timeout: float
    ) -> Optional[Dict[str, Any]]:
        """Corridor-generation variants are best-effort extras: enforce an explicit application-level
        deadline (on top of the HTTP client's own timeout) so a slow/unresponsive variant can never
        hold up the overall response beyond the configured budget."""
        try:
            return await asyncio.wait_for(
                self._fetch_route_variant(coords_str, exclude, timeout=timeout, with_alternatives=False),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            logger.warning("corridor_variant_timeout exclude=%s timeout=%ss", exclude, timeout)
            return None
        except Exception as exc:
            logger.error("corridor_variant_unexpected_error exclude=%s: %s", exclude, exc)
            return None

    async def route(
        self,
        origin_coords: Dict[str, float],
        dest_coords: Dict[str, float],
        waypoints: Optional[List[Dict[str, float]]],
        options: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, float]]:
        if not MAPBOX_ACCESS_TOKEN:
            logger.error("Mapbox directions skipped - MAPBOX_ACCESS_TOKEN missing")
            return None
        coords_list = [f"{origin_coords['lon']},{origin_coords['lat']}"]
        if waypoints:
            for wp in waypoints:
                coords_list.append(f"{wp['lon']},{wp['lat']}")
        coords_list.append(f"{dest_coords['lon']},{dest_coords['lat']}")
        coords_str = ";".join(coords_list)

        # Preserve the existing standard request exactly (same timeout, same alternatives=true).
        requested_exclude = (options or {}).get("exclude")
        primary_coro = self._fetch_route_variant(coords_str, requested_exclude, timeout=10.0, with_alternatives=True)
        generate_corridors = bool((options or {}).get("generate_corridors")) and not requested_exclude

        corridor_coros = []
        if generate_corridors:
            for exclude_value in CORRIDOR_EXCLUDE_VARIANTS:
                corridor_coros.append(
                    self._fetch_corridor_variant_with_deadline(
                        coords_str, exclude_value, CORRIDOR_VARIANT_TIMEOUT_SECONDS
                    )
                )

        gathered = await asyncio.gather(primary_coro, *corridor_coros, return_exceptions=True)
        primary_result, corridor_results = gathered[0], gathered[1:]

        if isinstance(primary_result, Exception) or not primary_result:
            return None

        # Candidate pool: Mapbox's own native alternates first (already computed, no extra cost),
        # then each successful corridor-exclusion variant's route — never manufactured, only ever
        # what Mapbox actually returned.
        candidates: List[Dict[str, Any]] = []
        for alt in primary_result.get("alternatives", []):
            candidates.append({**alt, "generation_method": "mapbox_alternative"})
        for exclude_value, result in zip(CORRIDOR_EXCLUDE_VARIANTS, corridor_results):
            if isinstance(result, Exception) or not result:
                logger.warning("corridor_variant_unavailable exclude=%s", exclude_value)
                continue
            candidates.append({**result, "generation_method": f"exclude_{exclude_value}"})

        if generate_corridors:
            distinct = _select_distinct_corridors(
                primary_result.get("geometry"), primary_result.get("distance") or 0.0, candidates
            )
        else:
            # Unchanged existing behavior when corridor generation wasn't requested.
            distinct = candidates[:2]

        primary_result["alternatives"] = distinct
        return primary_result



class NOAAWeatherProvider(WeatherProvider):
    async def get_weather(self, lat: float, lon: float) -> Optional[Dict[str, Any]]:
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
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
    async def get_alerts_area(self, area: str) -> List[Dict[str, Any]]:
        started = time.perf_counter()
        status_code: Optional[int] = None
        area_code = (area or "").upper() or "AK"
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                url = f"https://api.weather.gov/alerts/active?area={area_code}"
                response = await client.get(url, headers=NOAA_HEADERS)
                status_code = response.status_code
                elapsed_ms = round((time.perf_counter() - started) * 1000.0, 2)
                logger.info(
                    "nws_alerts_fetch",
                    extra={
                        "scope": f"area_{area_code}",
                        "status": status_code,
                        "elapsed_ms": elapsed_ms,
                    },
                )

                if response.status_code != 200:
                    logger.warning(
                        "nws_alerts_http_error",
                        extra={"scope": f"area_{area_code}", "status": status_code},
                    )
                    return []

                data = response.json()
                features = data.get("features", [])
                logger.info(
                    "nws_alerts_features",
                    extra={
                        "scope": f"area_{area_code}",
                        "status": status_code,
                        "features": len(features),
                        "first_event": (features[0].get("properties", {}).get("event") if features else None),
                    },
                )
                alerts: List[Dict[str, Any]] = []
                for feature in features:
                    props = feature.get("properties", {})
                    alerts.append(
                        {
                            "id": props.get("id", str(uuid.uuid4())),
                            "headline": props.get("headline", "Weather Alert"),
                            "severity": props.get("severity", "Unknown"),
                            "event": props.get("event", "Weather Event"),
                            "description": props.get("description", "")[:500],
                            "areas": props.get("areaDesc"),
                            "onset": props.get("onset"),
                            "expires": props.get("expires"),
                            "effective": props.get("effective"),
                            "ends": props.get("ends"),
                            "sent": props.get("sent"),
                            "instruction": props.get("instruction"),
                            "summary": props.get("headline"),
                            "urgency": props.get("urgency"),
                        }
                    )
                return alerts
        except Exception as exc:  # noqa: BLE001
            elapsed_ms = round((time.perf_counter() - started) * 1000.0, 2)
            logger.warning(
                "nws_alerts_fetch_failed",
                extra={
                    "scope": f"area_{area_code}",
                    "status": status_code,
                    "elapsed_ms": elapsed_ms,
                    "error": str(exc),
                },
            )
            return []

    async def get_alerts(self, lat: float, lon: float) -> List[Dict[str, Any]]:
        started = time.perf_counter()
        status_code: Optional[int] = None
        fetch_scope = "point"
        logger.info(f"nws_fetch_entered lat={lat} lon={lon}")
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                url = f"https://api.weather.gov/alerts/active?point={lat:.4f},{lon:.4f}"
                response = await client.get(url, headers=NOAA_HEADERS)
                status_code = response.status_code
                elapsed_ms = round((time.perf_counter() - started) * 1000.0, 2)
                logger.info(
                    "nws_alerts_fetch",
                    extra={
                        "lat": round(lat, 4),
                        "lon": round(lon, 4),
                        "status": status_code,
                        "elapsed_ms": elapsed_ms,
                    },
                )

                if response.status_code != 200:
                    logger.warning(
                        "nws_alerts_http_error",
                        extra={"lat": round(lat, 4), "lon": round(lon, 4), "status": status_code},
                    )
                    return []

                data = response.json()
                features = data.get("features", [])
                logger.info(
                    "nws_alerts_features",
                    extra={
                        "lat": round(lat, 4),
                        "lon": round(lon, 4),
                        "status": status_code,
                        "scope": fetch_scope,
                        "features": len(features),
                        "first_event": (features[0].get("properties", {}).get("event") if features else None),
                    },
                )

                # AK fallback: if point query returns no features and we are in Alaska lat/lon range, query by area=AK
                if not features and lat >= 50 and lat <= 72 and lon <= -130:
                    fetch_scope = "area_AK"
                    url = "https://api.weather.gov/alerts/active?area=AK"
                    response = await client.get(url, headers=NOAA_HEADERS)
                    status_code = response.status_code
                    elapsed_ms = round((time.perf_counter() - started) * 1000.0, 2)
                    logger.info(
                        "nws_alerts_fetch",
                        extra={
                            "lat": round(lat, 4),
                            "lon": round(lon, 4),
                            "status": status_code,
                            "elapsed_ms": elapsed_ms,
                            "scope": fetch_scope,
                        },
                    )
                    if response.status_code != 200:
                        logger.warning(
                            "nws_alerts_http_error",
                            extra={"lat": round(lat, 4), "lon": round(lon, 4), "status": status_code, "scope": fetch_scope},
                        )
                        return []
                    data = response.json()
                    features = data.get("features", [])
                    logger.info(
                        "nws_alerts_features",
                        extra={
                            "lat": round(lat, 4),
                            "lon": round(lon, 4),
                            "status": status_code,
                            "scope": fetch_scope,
                            "features": len(features),
                            "first_event": (features[0].get("properties", {}).get("event") if features else None),
                        },
                    )
                alerts: List[Dict[str, Any]] = []
                for feature in features:
                    props = feature.get("properties", {})
                    alerts.append(
                        {
                            "id": props.get("id", str(uuid.uuid4())),
                            "headline": props.get("headline", "Weather Alert"),
                            "severity": props.get("severity", "Unknown"),
                            "event": props.get("event", "Weather Event"),
                            "description": props.get("description", "")[:500],
                            "areas": props.get("areaDesc"),
                            "onset": props.get("onset"),
                            "expires": props.get("expires"),
                            "effective": props.get("effective"),
                            "ends": props.get("ends"),
                        }
                    )
                return alerts
        except Exception as exc:  # noqa: BLE001
            elapsed_ms = round((time.perf_counter() - started) * 1000.0, 2)
            logger.warning(
                "nws_alerts_fetch_failed",
                extra={
                    "lat": round(lat, 4),
                    "lon": round(lon, 4),
                    "status": status_code,
                    "elapsed_ms": elapsed_ms,
                    "error": str(exc),
                },
            )
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
