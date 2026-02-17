from fastapi import FastAPI, APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
import re
import random
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any, Tuple, Callable, TypeVar, Set, Awaitable

T = TypeVar("T")
import uuid
import math
import hashlib
import time
import json
import contextlib
from io import BytesIO
from datetime import datetime, timedelta, timezone
import httpx
import polyline
from notifications.route_alerts import sample_route_points
import asyncio
from bridge_database import get_bridge_warnings
from providers import get_providers
from billing import billing_verifier, VerificationRequest, VerificationResponse
from common.premium_gate import require_premium
from common.features import SOLAR_FORECAST, PROPANE_USAGE, WATER_BUDGET, WIND_SHELTER, ROAD_SIM, CAMPSITE_INDEX, CELL_STARLINK, CLAIM_LOG
from road_passability_service import RoadPassabilityService
from solar_forecast_service import SolarForecastService
from propane_usage_service import PropaneUsageService
from water_budget_service import WaterBudgetService
from terrain_shade_service import TerrainShadeService, SunSlot
from wind_shelter_service import WindShelterService, Ridge
from connectivity_prediction_service import cell_bars_probability, obstruction_risk, predict_cell_signal_at_location
from campsite_index_service import SiteFactors, Weights, score as campsite_score
from claim_log_service import HazardEvent as ClaimHazardEvent, WeatherSnapshot as ClaimWeatherSnapshot, build_claim_log
from claim_log_pdf import export_claim_log_to_pdf
from notifications import NotificationService, ExpoPushClient, router as notifications_router, get_route_alert_service
from notifications.smart_delay import SmartDelayOptimizer
from common.features import SMART_DELAY_ALERTS
from radar_alerts import radar_router  # Weather radar & alerts integration

# Google Gemini for chat
try:
    from google import genai
    CHAT_AVAILABLE = True
except ImportError:
    CHAT_AVAILABLE = False
    genai = None

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
# Silence httpx/httpcore info logs to avoid leaking query params (e.g., access_token)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# MongoDB connection (optional for testing)
mongo_url = os.environ.get("MONGODB_URI") or os.environ.get('MONGO_URL')
db_name = os.environ.get('DB_NAME', 'routecast_test')
client = None
db = None

# Timing and cache defaults
TIMING_DEBUG = bool(int(os.environ.get("DEBUG_TIMINGS", "0") or 0))
CACHE_TTL_SECONDS = int(os.environ.get("ROUTE_CACHE_TTL", "900"))
OVERPASS_CACHE_TTL_SECONDS = int(os.environ.get("OVERPASS_CACHE_TTL", "600"))

# Simple in-memory caches with TTL (per-process)
_geocode_cache: Dict[str, Dict[str, Any]] = {}
_route_cache: Dict[str, Dict[str, Any]] = {}
_route_context_cache: Dict[str, Dict[str, Any]] = {}
_overpass_response_cache: Dict[str, Dict[str, Any]] = {}

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
    "https://z.overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]


def _cache_enabled() -> bool:
    # Disable caches under pytest to avoid cross-test leakage
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return False
    return os.environ.get("ROUTE_CACHE_ENABLED", "1").lower() not in {"0", "false", "no", "off"}


def _cache_get(cache: Dict[str, Dict[str, Any]], key: str):
    if not _cache_enabled():
        return None
    entry = cache.get(key)
    if not entry:
        return None
    if entry.get("expires", 0) < time.time():
        cache.pop(key, None)
        return None
    return entry.get("value")


def _cache_set(cache: Dict[str, Dict[str, Any]], key: str, value: Any, ttl: int = CACHE_TTL_SECONDS):
    if not _cache_enabled():
        return
    cache[key] = {"value": value, "expires": time.time() + ttl}


async def cached_geocode(location: str) -> Optional[Dict[str, float]]:
    key = location.strip().lower()
    cached = _cache_get(_geocode_cache, key)
    if cached:
        return cached
    result = await geocode_location(location)
    if result:
        _cache_set(_geocode_cache, key, result)
    return result


def _route_cache_key(origin: Dict, dest: Dict, stops: List[Dict], options: Dict[str, Any]) -> str:
    payload = {
        "origin": origin,
        "dest": dest,
        "stops": stops,
        "options": options,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()


async def cached_route(origin_coords: Dict, dest_coords: Dict, stop_coords: List[Dict], routing_options: Dict[str, Any]) -> Optional[Dict]:
    key = _route_cache_key(origin_coords, dest_coords, stop_coords or [], routing_options or {})
    cached = _cache_get(_route_cache, key)
    if cached:
        return cached
    result = await get_mapbox_route(origin_coords, dest_coords, stop_coords if stop_coords else None, routing_options or None)
    if result:
        _cache_set(_route_cache, key, result)
    return result


def cache_route_context(route_id: str, context: Dict[str, Any], ttl: int = CACHE_TTL_SECONDS):
    _cache_set(_route_context_cache, route_id, context, ttl)


def get_route_context(route_id: str) -> Optional[Dict[str, Any]]:
    return _cache_get(_route_context_cache, route_id)

# We'll connect on app startup instead of during module import
async def connect_to_mongo():
    global client, db
    try:
        url_source = "MONGODB_URI" if os.environ.get("MONGODB_URI") else "MONGO_URL" if os.environ.get("MONGO_URL") else None
        if not mongo_url or not url_source:
            logger.warning("Mongo URL not configured (MONGODB_URI/MONGO_URL); database features disabled")
            client = None
            db = None
            return False

        logger.info("Initializing MongoDB client db=%s via %s", db_name, url_source)
        temp_client = AsyncIOMotorClient(mongo_url, serverSelectionTimeoutMS=5000)
        await temp_client.admin.command('ping')
        client = temp_client
        db = client[db_name]
        logger.info("MongoDB connection successful")
        return True
    except Exception as e:
        logger.warning(f"MongoDB connection failed: {e}. Running without database.")
        client = None
        db = None
        return False

# API Keys
MAPBOX_ACCESS_TOKEN = os.environ.get('MAPBOX_ACCESS_TOKEN', '')
ROUTECAST_MODE = os.environ.get('ROUTECAST_MODE', 'prod').lower()
GEMINI_MODEL = os.environ.get('GEMINI_MODEL', 'gemini-1.5-flash')
GOOGLE_PLACES_API_KEY = os.environ.get("GOOGLE_PLACES_API_KEY", "")
BUILD_SHA = os.environ.get("RENDER_GIT_COMMIT") or os.environ.get("BUILD_SHA") or "unknown"
BUILD_TIME = os.environ.get("BUILD_TIME") or datetime.utcnow().isoformat()
ALERT_DEBUG = bool(int(os.environ.get("ALERT_DEBUG", "0") or 0))
DEBUG_MODE = os.environ.get("DEBUG", "0").lower() in {"1", "true", "yes", "on"}


def _env_float(key: str, default: float) -> float:
    try:
        return float(os.environ.get(key, default))
    except Exception:
        return default


# Tunable hazard thresholds (env overrides)
HAZARD_CONFIG = {
    "wind_medium_mph": _env_float("HAZARD_WIND_MEDIUM_MPH", 26),
    "wind_high_mph": _env_float("HAZARD_WIND_HIGH_MPH", 31),
    "wind_extreme_mph": _env_float("HAZARD_WIND_EXTREME_MPH", 41),
    "ice_temp_f": _env_float("HAZARD_ICE_TEMP_F", 32),
    "slippery_temp_f": _env_float("HAZARD_SLIPPERY_TEMP_F", 36),
    "merge_gap_miles": _env_float("HAZARD_MERGE_GAP_MILES", 5.0),
    "default_span_miles": _env_float("HAZARD_DEFAULT_SPAN_MILES", 5.0),
    "max_alerts": int(_env_float("MAX_ALERTS_PER_ROUTE", 10)),
    "log_detail": int(_env_float("HAZARD_LOG_DETAIL", 0)),
}

RESAMPLE_MILES = _env_float("RESAMPLE_MILES", 10.0)
MIN_STEPS_FOR_NATIVE = int(_env_float("MIN_STEPS_FOR_NATIVE", 30))

HAZARD_SCHEMA_VERSION = 2

# Log hazard config once at startup for ops visibility
logger.info("hazard_config_resolved", extra={"hazard_config": HAZARD_CONFIG, "schema_version": HAZARD_SCHEMA_VERSION})

# Log Mapbox token presence without exposing the secret
if MAPBOX_ACCESS_TOKEN:
    logger.info("Mapbox token configured")
else:
    logger.error("MAPBOX_ACCESS_TOKEN is missing - Mapbox directions/geocoding will fail.")

if not GOOGLE_PLACES_API_KEY:
    logger.info("GOOGLE_PLACES_API_KEY not set (expected in local/test); Google Places endpoints will fall back or be stubbed.")


def require_mapbox_token():
    if MAPBOX_ACCESS_TOKEN or ROUTECAST_MODE in {"demo", "test"}:
        return
    logger.error("MAPBOX_ACCESS_TOKEN missing for Mapbox request")
    raise HTTPException(status_code=500, detail="MAPBOX_ACCESS_TOKEN not set on backend")


def _compute_bbox(points: List[Dict[str, float]]) -> Optional[Dict[str, float]]:
    if not points:
        return None
    lats = [p.get("lat") for p in points if p.get("lat") is not None]
    lons = [p.get("lon") for p in points if p.get("lon") is not None]
    if not lats or not lons:
        return None
    return {
        "min_lat": min(lats),
        "max_lat": max(lats),
        "min_lon": min(lons),
        "max_lon": max(lons),
    }

# NOAA API Headers
NOAA_USER_AGENT = os.environ.get('NOAA_USER_AGENT', 'Routecast/1.0 (contact@routecast.app)')
NOAA_HEADERS = {
    'User-Agent': NOAA_USER_AGENT,
    'Accept': 'application/geo+json'
}

# Create the main app
app = FastAPI()

# Create routers
api_router = APIRouter(prefix="/api")
geocode_router = APIRouter()

# Initialize notification service (for E1: Smart Departure & Hazard Alerts)
# Uses synchronous MongoDB client (not motor) for simplicity
_notification_service_instance = None

def get_notification_service() -> NotificationService:
    """Get or create NotificationService instance."""
    global _notification_service_instance
    if _notification_service_instance is None:
        from pymongo import MongoClient as SyncClient
        sync_client = SyncClient(mongo_url)
        sync_db = sync_client[os.environ['DB_NAME']]
        expo_client = ExpoPushClient()
        _notification_service_instance = NotificationService(sync_db, expo_client)
    return _notification_service_instance


def get_gemini_model() -> Tuple["genai.Client", str]:
    """Return a Gemini model client and model name using google.genai.

    Raises HTTP 500 if the SDK or key is missing.
    """
    if not CHAT_AVAILABLE or genai is None:
        logger.error("Gemini SDK not installed")
        raise HTTPException(status_code=500, detail="Gemini SDK not installed")

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logger.error("GEMINI_API_KEY is not set")
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY is not set")

    client = genai.Client(api_key=api_key, api_version="v1")
    model_name = os.environ.get("GEMINI_MODEL", GEMINI_MODEL)
    if not model_name.startswith("models/"):
        model_name = f"models/{model_name}"
    return client, model_name

# ==================== Models ====================

# Vehicle types for safety scoring
VEHICLE_TYPES = {
    "car": {"wind_sensitivity": 1.0, "ice_sensitivity": 1.0, "visibility_sensitivity": 1.0, "name": "Car/Sedan"},
    "suv": {"wind_sensitivity": 1.1, "ice_sensitivity": 0.9, "visibility_sensitivity": 1.0, "name": "SUV"},
    "truck": {"wind_sensitivity": 1.3, "ice_sensitivity": 0.85, "visibility_sensitivity": 1.0, "name": "Pickup Truck"},
    "semi": {"wind_sensitivity": 1.8, "ice_sensitivity": 1.2, "visibility_sensitivity": 1.3, "name": "Semi Truck"},
    "rv": {"wind_sensitivity": 1.7, "ice_sensitivity": 1.1, "visibility_sensitivity": 1.2, "name": "RV/Motorhome"},
    "motorcycle": {"wind_sensitivity": 2.0, "ice_sensitivity": 2.5, "visibility_sensitivity": 1.5, "name": "Motorcycle"},
    "trailer": {"wind_sensitivity": 1.6, "ice_sensitivity": 1.3, "visibility_sensitivity": 1.1, "name": "Vehicle + Trailer"},
}

# Road condition types
ROAD_CONDITIONS = {
    "dry": {"severity": 0, "color": "#22c55e", "icon": "✓", "label": "DRY"},
    "wet": {"severity": 1, "color": "#3b82f6", "icon": "💧", "label": "WET"},
    "slippery": {"severity": 2, "color": "#f59e0b", "icon": "⚠️", "label": "SLIPPERY"},
    "icy": {"severity": 3, "color": "#ef4444", "icon": "🧊", "label": "ICY"},
    "snow_covered": {"severity": 3, "color": "#93c5fd", "icon": "❄️", "label": "SNOW"},
    "flooded": {"severity": 4, "color": "#dc2626", "icon": "🌊", "label": "FLOODING"},
    "low_visibility": {"severity": 2, "color": "#9ca3af", "icon": "🌫️", "label": "LOW VIS"},
    "dangerous_wind": {"severity": 3, "color": "#8b5cf6", "icon": "💨", "label": "HIGH WIND"},
    "out_of_coverage": {"severity": 0, "color": "#6b7280", "icon": "📡", "label": "OUT OF COVERAGE"},
}

class StopPoint(BaseModel):
    location: str
    type: str = "stop"  # stop, gas, food, rest

class RoadCondition(BaseModel):
    condition: str  # dry, wet, icy, snow_covered, flooded, low_visibility, dangerous_wind
    severity: int  # 0-4 (0=good, 4=dangerous)
    label: str
    icon: str
    color: str
    description: str
    recommendation: str

class TurnByTurnStep(BaseModel):
    instruction: str
    distance_miles: float
    duration_minutes: int
    road_name: str
    maneuver: str  # turn-left, turn-right, merge, etc.
    road_condition: Optional[RoadCondition] = None
    weather_at_step: Optional[str] = None
    temperature: Optional[int] = None
    has_alert: bool = False
    start_distance_miles: Optional[float] = None  # cumulative start distance along route
    end_distance_miles: Optional[float] = None  # cumulative end distance along route

class AlternateRoute(BaseModel):
    name: str
    distance_miles: float
    duration_minutes: int
    road_condition_summary: str
    safety_score: int
    recommendation: str
    avoids: List[str]  # What hazards this route avoids


class RouteRequest(BaseModel):
    origin: str
    destination: str
    departure_time: Optional[str] = None  # ISO format datetime
    stops: Optional[List[StopPoint]] = []
    waypoints: Optional[List[Dict[str, Any]]] = None  # optional raw waypoints
    push_token: Optional[str] = None
    vehicle_type: Optional[str] = None  # car, suv, truck, semi, rv, motorcycle, trailer
    mode: Optional[str] = None  # standard, boondocker, truck
    trucker_mode: Optional[bool] = False  # Enable trucker-specific warnings
    vehicle_height_ft: Optional[float] = None  # Vehicle height in feet for clearance warnings
    vehicle_weight_lbs: Optional[int] = None
    vehicle_length_ft: Optional[float] = None
    axle_count: Optional[int] = None
    hazmat: Optional[bool] = None
    avoid_highways: Optional[bool] = None
    avoid_tolls: Optional[bool] = None
    prefer_campgrounds: Optional[bool] = None

class HazardAlert(BaseModel):
    type: str  # wind, ice, visibility, rain, snow, etc.
    severity: str  # low, medium, high, extreme
    distance_miles: float
    eta_minutes: int
    message: str
    recommendation: str
    countdown_text: str  # "Heavy rain in 27 minutes"
    location_name: Optional[str] = None  # Name/description of the location where alert occurs
    event: Optional[str] = None
    headline: Optional[str] = None
    description: Optional[str] = None
    full_description: Optional[str] = None
    instruction: Optional[str] = None
    areaDesc: Optional[str] = None
    onset: Optional[str] = None
    expires: Optional[str] = None
    properties: Optional[Dict[str, Any]] = None
    road_name: Optional[str] = None
    span_miles: Optional[float] = None
    end_mile: Optional[float] = None
    alert_level: Optional[str] = None  # Watch | Warning | Advisory | Statement | Unknown
    driver_action: Optional[str] = None
    rationale: Optional[str] = None  # why this alert fired
    temp_f: Optional[float] = None
    wind_mph: Optional[int] = None
    wind_gust_mph: Optional[int] = None
    precip_type: Optional[str] = None
    precip_intensity: Optional[str] = None
    visibility: Optional[str] = None
    hazard_id: Optional[str] = None  # stable deterministic id for client diffing
    hazard_schema_version: int = HAZARD_SCHEMA_VERSION


class ConditionSegment(BaseModel):
    type: str
    category: str  # road or weather
    road_name: str
    start_mile: float
    end_mile: float
    span_miles: float
    eta_start_min: Optional[int] = None
    eta_end_min: Optional[int] = None
    conditions: Optional[str] = None
    rationale: Optional[str] = None
    driver_action: Optional[str] = None
    severity: Optional[str] = None

class RestStop(BaseModel):
    name: str
    type: str  # gas, food, rest_area
    lat: float
    lon: float
    distance_miles: float
    eta_minutes: int
    weather_at_arrival: Optional[str] = None
    temperature_at_arrival: Optional[int] = None
    recommendation: str  # "Good time to stop - rain clears"

class DepartureWindow(BaseModel):
    departure_time: str
    arrival_time: str
    safety_score: int
    hazard_count: int
    recommendation: str
    conditions_summary: str

class SafetyScore(BaseModel):
    overall_score: int  # 0-100
    risk_level: str  # low, moderate, high, extreme
    vehicle_type: str
    factors: List[str]  # List of contributing factors
    recommendations: List[str]

class Waypoint(BaseModel):
    lat: float
    lon: float
    name: Optional[str] = None
    distance_from_start: Optional[float] = None  # in miles
    eta_minutes: Optional[int] = None  # minutes from departure
    arrival_time: Optional[str] = None  # ISO format

class HourlyForecast(BaseModel):
    time: str
    temperature: int
    conditions: str
    wind_speed: str
    precipitation_chance: Optional[int] = None

class WeatherData(BaseModel):
    temperature: Optional[int] = None
    temperature_unit: Optional[str] = "F"
    wind_speed: Optional[str] = None
    wind_direction: Optional[str] = None
    conditions: Optional[str] = None
    icon: Optional[str] = None
    humidity: Optional[int] = None
    is_daytime: Optional[bool] = True
    sunrise: Optional[str] = None
    sunset: Optional[str] = None
    hourly_forecast: Optional[List[HourlyForecast]] = []

class WeatherAlert(BaseModel):
    id: str
    headline: str
    severity: str
    event: str
    description: str
    areas: Optional[str] = None
    onset: Optional[str] = None
    expires: Optional[str] = None
    effective: Optional[str] = None
    ends: Optional[str] = None
    instruction: Optional[str] = None
    summary: Optional[str] = None
    urgency: Optional[str] = None
    sent: Optional[str] = None
    issued: Optional[str] = None

class PackingSuggestion(BaseModel):
    item: str
    reason: str
    priority: str  # essential, recommended, optional

class WaypointWeather(BaseModel):
    waypoint: Waypoint
    weather: Optional[WeatherData] = None
    alerts: List[WeatherAlert] = []
    error: Optional[str] = None

class RouteWeatherResponse(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    origin: str
    destination: str
    stops: List[StopPoint] = []
    departure_time: Optional[str] = None
    total_duration_minutes: Optional[int] = None
    total_distance_miles: Optional[float] = None
    route_geometry: str  # Encoded polyline
    waypoints: List[WaypointWeather]
    ai_summary: Optional[str] = None
    has_severe_weather: bool = False
    packing_suggestions: List[PackingSuggestion] = []
    weather_timeline: List[HourlyForecast] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)
    is_favorite: bool = False
    # New fields for enhanced features
    safety_score: Optional[SafetyScore] = None
    hazard_alerts: List[HazardAlert] = []
    road_conditions: List[ConditionSegment] = []
    weather_conditions: List[ConditionSegment] = []
    rest_stops: List[RestStop] = []
    optimal_departure: Optional[DepartureWindow] = None
    trucker_warnings: List[str] = []
    vehicle_type: str = "car"
    # Road conditions and navigation
    turn_by_turn: List[TurnByTurnStep] = []
    road_condition_summary: Optional[str] = None
    worst_road_condition: Optional[str] = None
    alternate_routes: List[AlternateRoute] = []
    reroute_recommended: bool = False
    reroute_reason: Optional[str] = None
    coverage_gaps_segments: int = 0
    coverage_gaps_miles: float = 0.0
    hazard_status: str = "ready"
    timings_ms: Optional[Dict[str, float]] = None

class SavedRoute(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    origin: str
    destination: str
    stops: List[StopPoint] = []
    is_favorite: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)


class HazardAlertsResponse(BaseModel):
    route_id: str
    hazard_alerts: List[HazardAlert]
    alerts: List[HazardAlert] = []
    road_conditions: List[ConditionSegment] = []
    weather_conditions: List[ConditionSegment] = []
    hazard_status: str = "ready"
    status: str = "ready"
    error: Optional[str] = None
    timings_ms: Optional[Dict[str, float]] = None

class FavoriteRouteRequest(BaseModel):
    origin: str
    destination: str
    stops: Optional[List[StopPoint]] = []
    name: Optional[str] = None

class SubscriptionRequest(BaseModel):
    """Stub request for subscription validation"""
    subscription_id: str
    purchase_token: Optional[str] = None

class SubscriptionResponse(BaseModel):
    """Response for subscription validation"""
    is_valid: bool
    subscription_id: str
    message: str

class RoadPassabilityRequest(BaseModel):
    """Request for road passability assessment (Premium feature)"""
    precip_72h: float  # Precipitation in last 72h (mm)
    slope_pct: float   # Road grade percentage
    min_temp_f: float  # Minimum temperature (°F)
    soil_type: str     # Soil type: clay, sand, rocky, loam
    subscription_id: Optional[str] = None  # For premium gating

class RoadPassabilityResponse(BaseModel):
    """Response for road passability assessment"""
    passability_score: float  # 0-100
    condition_assessment: str  # Excellent, Good, Fair, Poor, Impassable
    advisory: str
    min_clearance_cm: float
    recommended_vehicle_type: str  # sedan, suv, 4x4
    needs_four_x_four: bool
    risks: Dict[str, bool]  # mud_risk, ice_risk, deep_rut_risk, high_clearance_recommended, four_x_four_recommended
    is_premium_locked: bool = False
    premium_message: Optional[str] = None

class SolarForecastRequest(BaseModel):
    """Request for solar energy forecast (Premium feature)"""
    lat: float  # Latitude (-90 to 90)
    lon: float  # Longitude (-180 to 180)
    date_range: List[str]  # ISO format dates (e.g., ["2026-01-20", "2026-01-21"])
    panel_watts: float  # Solar panel capacity in watts (>0)
    shade_pct: float  # Average shade percentage (0-100)
    cloud_cover: List[float]  # Cloud cover percentages per date (0-100)
    subscription_id: Optional[str] = None  # For premium gating

class SolarForecastResponse(BaseModel):
    """Response for solar energy forecast"""
    daily_wh: Optional[List[float]] = None  # Wh/day for each date
    dates: Optional[List[str]] = None
    panel_watts: Optional[float] = None
    shade_pct: Optional[float] = None
    advisory: Optional[str] = None
    is_premium_locked: bool = False
    premium_message: Optional[str] = None

class PropaneUsageRequest(BaseModel):
    """Request for propane consumption estimate (Premium feature)"""
    furnace_btu: int  # Furnace BTU capacity (e.g., 20000, 30000)
    duty_cycle_pct: float  # Percentage furnace runs (0-100, will be clamped)
    nights_temp_f: List[int]  # Nightly low temperatures in Fahrenheit
    people: int = 2  # Number of people in RV (default: 2)
    subscription_id: Optional[str] = None  # For premium gating

class PropaneUsageResponse(BaseModel):
    """Response for propane consumption estimate"""
    daily_lbs: Optional[List[float]] = None  # lbs propane per day
    nights_temp_f: Optional[List[int]] = None  # Echo of input temperatures
    furnace_btu: Optional[int] = None
    duty_cycle_pct: Optional[float] = None
    people: Optional[int] = None
    advisory: Optional[str] = None  # Human-readable summary
    is_premium_locked: bool = False
    premium_message: Optional[str] = None

class WaterBudgetRequest(BaseModel):
    """Request for water budget estimation (Premium feature)"""
    fresh_gal: int  # Capacity of fresh water tank in gallons
    gray_gal: int   # Capacity of gray water tank in gallons
    black_gal: int  # Capacity of black water tank in gallons
    people: int = 2  # Number of people in RV (default: 2)
    showers_per_week: float = 2  # Number of showers per week (default: 2)
    hot_days: bool = False  # Whether it's hot weather (affects usage)
    subscription_id: Optional[str] = None  # For premium gating

class WaterBudgetResponse(BaseModel):
    """Response for water budget estimation"""
    days_remaining: Optional[int] = None  # Days until first tank runs out
    limiting_factor: Optional[str] = None  # Which tank limits trip: fresh/gray/black
    daily_fresh_gal: Optional[float] = None  # Daily fresh water usage
    daily_gray_gal: Optional[float] = None   # Daily gray water usage
    daily_black_gal: Optional[float] = None  # Daily black water usage
    advisory: Optional[str] = None  # Human-readable summary
    is_premium_locked: bool = False
    premium_message: Optional[str] = None

class SunPathSlotResponse(BaseModel):
    """Single hourly sunlight slot from solar path"""
    hour: int
    sun_elevation_deg: float
    usable_sunlight_fraction: float
    time_label: str

class TerrainShadeRequest(BaseModel):
    """Request for solar path and shade calculation"""
    latitude: float
    longitude: float
    date: str  # ISO format: YYYY-MM-DD
    tree_canopy_pct: int = 0  # Tree coverage (0-100%)
    horizon_obstruction_deg: int = 0  # Horizon blocking (0-90°)
    subscription_id: Optional[str] = None

class TerrainShadeResponse(BaseModel):
    """Response for solar path and shade data"""
    sun_path_slots: Optional[List[SunPathSlotResponse]] = None
    shade_factor: Optional[float] = None  # 0.0-1.0 (fraction blocked)
    exposure_hours: Optional[float] = None  # Effective sunlight hours after shade
    is_premium_locked: bool = False
    premium_message: Optional[str] = None

class WindShelterRidgeRequest(BaseModel):
    """Single ridge for wind shelter consideration"""
    bearing_deg: int
    strength: str  # "low", "med", "high"
    name: Optional[str] = None

class WindShelterRequest(BaseModel):
    """Request for wind shelter orientation recommendation"""
    predominant_dir_deg: int  # Wind direction (0-360°)
    gust_mph: int  # Peak wind gust speed
    local_ridges: Optional[List[WindShelterRidgeRequest]] = None
    subscription_id: Optional[str] = None

class WindShelterResponse(BaseModel):
    """Response for wind shelter recommendation"""
    recommended_bearing_deg: Optional[int] = None
    rationale_text: Optional[str] = None
    risk_level: Optional[str] = None  # "low", "medium", "high"
    shelter_available: Optional[bool] = None
    estimated_wind_reduction_pct: Optional[int] = None
    is_premium_locked: bool = False
    premium_message: Optional[str] = None

# ----- A6: Road Passability Models -----
class RoadPassabilityRequest(BaseModel):
    precip72hIn: float
    slopePct: float
    minTempF: int
    soilType: str
    subscription_id: Optional[str] = None

class RoadPassabilityResponse(BaseModel):
    score: Optional[int] = None
    mud_risk: Optional[bool] = None
    ice_risk: Optional[bool] = None
    clearance_need: Optional[str] = None  # "low"|"medium"|"high"
    four_by_four_recommended: Optional[bool] = None
    reasons: Optional[List[str]] = None
    is_premium_locked: bool = False
    premium_message: Optional[str] = None

# ----- A7: Connectivity Prediction Models -----
class ConnectivityCellRequest(BaseModel):
    carrier: str  # "verizon", "att", "tmobile", "unknown"
    # New GPS-based approach
    lat: Optional[float] = None
    lon: Optional[float] = None
    # Legacy manual input (optional, for backward compatibility)
    towerDistanceKm: Optional[float] = None
    terrainObstructionPct: Optional[int] = None
    subscription_id: Optional[str] = None

class ConnectivityCellResponse(BaseModel):
    carrier: Optional[str] = None
    probability: Optional[float] = None
    bar_estimate: Optional[str] = None
    explanation: Optional[str] = None
    is_premium_locked: bool = False
    premium_message: Optional[str] = None

class ConnectivityStarlinkRequest(BaseModel):
    horizonSouthDeg: int  # 0-90
    canopyPct: int  # 0-100
    subscription_id: Optional[str] = None

class ConnectivityStarlinkResponse(BaseModel):
    risk_level: Optional[str] = None  # "low", "medium", "high"
    obstruction_score: Optional[float] = None
    explanation: Optional[str] = None
    reasons: Optional[List[str]] = None
    is_premium_locked: bool = False
    premium_message: Optional[str] = None

# ----- A8: Campsite Index Scoring Models -----
class CampsiteIndexRequest(BaseModel):
    wind_gust_mph: float
    shade_score: float  # 0-1
    slope_pct: float
    access_score: float  # 0-1
    signal_score: float  # 0-1
    road_passability_score: float  # 0-100
    subscription_id: Optional[str] = None

class CampsiteIndexAutoRequest(BaseModel):
    latitude: float
    longitude: float
    subscription_id: Optional[str] = None

class CampsiteIndexResponse(BaseModel):
    score: Optional[int] = None
    breakdown: Optional[Dict[str, float]] = None
    explanations: Optional[List[str]] = None
    is_premium_locked: bool = False
    premium_message: Optional[str] = None

# ----- A9: Claim Log Models -----
class ClaimHazardLocation(BaseModel):
    latitude: float
    longitude: float

# ----- Free Camping Models -----
class CampingSpot(BaseModel):
    name: str
    type: str  # 'BLM', 'National Forest', 'Bureau of Reclamation', etc.
    distance_miles: float
    latitude: float
    longitude: float
    description: str
    amenities: List[str]
    stay_limit: str
    cell_coverage: str  # 'none', 'poor', 'fair', 'good'
    access_difficulty: str  # 'easy', 'moderate', 'difficult', '4wd-required'
    elevation_ft: int
    rating: float  # 0-5
    free: bool
    source_id: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    contact: Optional[str] = None

class FreeCampingRequest(BaseModel):
    latitude: float
    longitude: float
    radius_miles: int
    subscription_id: Optional[str] = None

class FreeCampingResponse(BaseModel):
    spots: List[CampingSpot]
    is_premium_locked: bool = False
    premium_message: Optional[str] = None

# ----- Dump Station Models -----
class DumpStation(BaseModel):
    name: str
    type: str  # 'RV Park', 'Rest Stop', 'Gas Station', 'Standalone'
    distance_miles: float
    latitude: float
    longitude: float
    description: str
    has_potable_water: bool
    is_free: bool
    cost: str
    hours: str
    restrictions: List[str]
    access: str  # 'easy', 'moderate', 'difficult'
    rating: float
    address: Optional[str] = None
    website: Optional[str] = None
    phone: Optional[str] = None

class DumpStationRequest(BaseModel):
    latitude: float
    longitude: float
    radius_miles: int
    subscription_id: Optional[str] = None

class DumpStationResponse(BaseModel):
    stations: List[DumpStation]
    is_premium_locked: bool = False
    premium_message: Optional[str] = None

# ----- Overnight Parking POI Models -----
class OvernightStop(BaseModel):
    name: str
    category: str
    label: str
    distance_miles: float
    latitude: float
    longitude: float
    osm_id: Optional[Any] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    hours: Optional[str] = None
    notes: Optional[str] = None

class OvernightSearchRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    latitude: float = Field(..., alias="lat")
    longitude: float = Field(..., alias="lon")
    radius_miles: int
    subscription_id: Optional[str] = Field(None, alias="subscriptionId")

class OvernightSearchResponse(BaseModel):
    spots: List[OvernightStop]
    is_premium_locked: bool = False
    premium_message: Optional[str] = None
    ok: bool = True
    source: Optional[str] = None
    error: Optional[str] = None
    debug: Optional[Dict[str, Any]] = None

# ----- Last Chance Supply Models -----
class SupplyPoint(BaseModel):
    name: str
    type: str  # 'Grocery', 'Propane', 'Hardware'
    subtype: str  # 'Supermarket', 'Gas Station', 'Hardware Store', etc.
    distance_miles: float
    latitude: float
    longitude: float
    description: str
    hours: str
    phone: str
    amenities: List[str]
    rating: float
    address: Optional[str] = None
    formatted_address: Optional[str] = None
    vicinity: Optional[str] = None
    title: Optional[str] = None
    website: Optional[str] = None

class LastChanceRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    latitude: float = Field(..., alias="lat")
    longitude: float = Field(..., alias="lon")
    radius_miles: int
    subscription_id: Optional[str] = Field(None, alias="subscriptionId")

class LastChanceResponse(BaseModel):
    supplies: List[SupplyPoint]
    is_premium_locked: bool = False
    premium_message: Optional[str] = None

# ----- RV Dealership Models -----
class RVDealership(BaseModel):
    name: str
    type: str  # 'Dealership', 'Service Center', 'Parts & Accessories'
    distance_miles: float
    latitude: float
    longitude: float
    description: str
    hours: str
    phone: str
    services: List[str]
    brands: List[str]
    rating: float
    address: Optional[str] = None
    website: Optional[str] = None

class RVDealershipRequest(BaseModel):
    latitude: float
    longitude: float
    radius_miles: int
    subscription_id: Optional[str] = None

class RVDealershipResponse(BaseModel):
    dealerships: List[RVDealership]
    is_premium_locked: bool = False
    premium_message: Optional[str] = None


class ClaimHazardEventModel(BaseModel):
    timestamp: str
    type: str
    severity: str
    location: ClaimHazardLocation
    notes: Optional[str] = None
    evidence: Optional[str] = None


class ClaimWeatherTimeRange(BaseModel):
    start: str
    end: str


class ClaimWeatherSnapshotModel(BaseModel):
    summary: str
    source: str
    time_range: ClaimWeatherTimeRange
    key_metrics: Dict[str, Any]


class ClaimLogRequest(BaseModel):
    routeId: str
    hazards: List[ClaimHazardEventModel]
    weatherSnapshot: ClaimWeatherSnapshotModel
    subscription_id: Optional[str] = None


class ClaimLogTotals(BaseModel):
    total_events: int
    by_type: Dict[str, int]
    by_severity: Dict[str, int]


class ClaimLogResponse(BaseModel):
    schema_version: str
    route_id: str
    generated_at: str
    hazards: List[Dict[str, Any]]
    weather_snapshot: Dict[str, Any]
    totals: ClaimLogTotals
    narrative: str
    is_premium_locked: bool = False
    premium_message: Optional[str] = None

# ----- E1: Smart Departure & Hazard Alerts Models -----
class RouteWaypointRequest(BaseModel):
    """A waypoint for planned route."""
    latitude: float = Field(..., alias="lat")
    longitude: float = Field(..., alias="lon")
    name: Optional[str] = None

class RegisterPlannedTripRequest(BaseModel):
    """Register a planned trip for smart delay evaluation."""
    route_waypoints: List[RouteWaypointRequest]
    planned_departure_local: datetime  # Local departure time
    user_timezone: str  # e.g., "America/Denver"
    destination_name: Optional[str] = None
    subscription_id: Optional[str] = None

class RegisterPlannedTripResponse(BaseModel):
    """Response from registering a planned trip."""
    trip_id: str
    registered_at: datetime
    next_check_at: datetime
    is_premium_locked: bool = False
    premium_message: Optional[str] = None

class RegisterPushTokenRequest(BaseModel):
    """Register Expo push token for notifications."""
    token: str  # Expo push token
    device_id: Optional[str] = None
    subscription_id: Optional[str] = None

class RegisterPushTokenResponse(BaseModel):
    """Response from registering push token."""
    success: bool
    message: str
    is_premium_locked: bool = False

class CheckNotificationRequest(BaseModel):
    """Check if a notification should be sent now (fallback endpoint)."""
    trip_id: str
    subscription_id: Optional[str] = None

class CheckNotificationResponse(BaseModel):
    """Response with notification decision."""
    should_notify: bool
    notification: Optional[Dict[str, Any]] = None
    is_premium_locked: bool = False
    premium_message: Optional[str] = None

# ==================== Helper Functions ====================

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points in miles."""
    R = 3959  # Earth's radius in miles
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    
    a = math.sin(delta_lat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    
    return R * c

def calculate_eta(distance_miles: float, avg_speed_mph: float = 55) -> int:
    """Calculate ETA in minutes."""
    return int((distance_miles / avg_speed_mph) * 60)

def extract_waypoints_from_route(encoded_polyline: str, interval_miles: float = RESAMPLE_MILES, departure_time: Optional[datetime] = None) -> List[Waypoint]:
    """Extract waypoints along route at specified intervals with ETAs."""
    try:
        if not encoded_polyline:
            logger.warning("extract_waypoints_from_route called with empty geometry")
            return []

        coords = polyline.decode(encoded_polyline, 6)
        if not coords:
            return []
        
        waypoints = []
        total_distance = 0.0
        last_waypoint_distance = 0.0
        
        dep_time = departure_time or datetime.now()
        
        # Always include start point
        waypoints.append(Waypoint(
            lat=coords[0][0],
            lon=coords[0][1],
            name="Start",
            distance_from_start=0,
            eta_minutes=0,
            arrival_time=dep_time.isoformat()
        ))
        
        for i in range(1, len(coords)):
            lat1, lon1 = coords[i-1]
            lat2, lon2 = coords[i]
            segment_distance = haversine_distance(lat1, lon1, lat2, lon2)
            total_distance += segment_distance
            
            # Add waypoint if we've traveled enough distance
            if total_distance - last_waypoint_distance >= interval_miles:
                eta_mins = calculate_eta(total_distance)
                arrival = dep_time + timedelta(minutes=eta_mins)
                waypoints.append(Waypoint(
                    lat=lat2,
                    lon=lon2,
                    name=f"Mile {int(total_distance)}",
                    distance_from_start=round(total_distance, 1),
                    eta_minutes=eta_mins,
                    arrival_time=arrival.isoformat()
                ))
                last_waypoint_distance = total_distance
        
        # Always include end point
        end_lat, end_lon = coords[-1]
        if len(waypoints) == 1 or haversine_distance(
            waypoints[-1].lat, waypoints[-1].lon, end_lat, end_lon
        ) > 10:
            eta_mins = calculate_eta(total_distance)
            arrival = dep_time + timedelta(minutes=eta_mins)
            waypoints.append(Waypoint(
                lat=end_lat,
                lon=end_lon,
                name="Destination",
                distance_from_start=round(total_distance, 1),
                eta_minutes=eta_mins,
                arrival_time=arrival.isoformat()
            ))
        
        return waypoints
    except Exception as e:
        logger.error(f"Error extracting waypoints: {e}")
        return []

async def reverse_geocode(lat: float, lon: float) -> Optional[str]:
    """Reverse geocode coordinates to city/state using active provider."""
    try:
        return await get_providers().geocode.reverse_geocode(lat, lon)
    except Exception as e:
        logger.error(f"Reverse geocoding error for {lat},{lon}: {e}")
        return None


async def geocode_location(location: str) -> Optional[Dict[str, float]]:
    """Geocode a location string using active provider."""
    try:
        # Accept raw "lat,lon" inputs to bypass geocoding for numeric coordinates
        if location:
            parts = [p.strip() for p in location.split(",")]
            if len(parts) == 2:
                try:
                    lat_val = float(parts[0])
                    lon_val = float(parts[1])
                    if -90.0 <= lat_val <= 90.0 and -180.0 <= lon_val <= 180.0:
                        return {"lat": lat_val, "lon": lon_val}
                except ValueError:
                    pass

        require_mapbox_token()
        return await get_providers().geocode.geocode(location)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Geocoding error for {location}: {e}")
        return None


async def get_mapbox_route(origin_coords: Dict, dest_coords: Dict, waypoints: List[Dict] = None, options: Optional[Dict[str, Any]] = None) -> Optional[Dict]:
    """Get route using active directions provider (Mapbox in prod, fixtures in demo)."""
    try:
        require_mapbox_token()
        return await get_providers().directions.route(origin_coords, dest_coords, waypoints, options)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Directions provider error: {e}")
        return None


async def get_noaa_weather(lat: float, lon: float) -> Optional[WeatherData]:
    """Get weather data using active provider (NOAA in prod, fixtures in demo)."""
    try:
        raw = await get_providers().weather.get_weather(lat, lon)
        if not raw:
            return None
        hourly_raw = raw.get('hourly_forecast', [])
        hourly_forecast = [
            HourlyForecast(
                time=entry.get('time', ''),
                temperature=entry.get('temperature', 0),
                conditions=entry.get('conditions', ''),
                wind_speed=entry.get('wind_speed', ''),
                precipitation_chance=entry.get('precipitation_chance'),
            )
            for entry in hourly_raw
        ]
        return WeatherData(
            temperature=raw.get('temperature'),
            temperature_unit=raw.get('temperature_unit', 'F'),
            wind_speed=raw.get('wind_speed'),
            wind_direction=raw.get('wind_direction'),
            conditions=raw.get('conditions'),
            icon=raw.get('icon'),
            humidity=raw.get('humidity'),
            is_daytime=raw.get('is_daytime', True),
            sunrise=raw.get('sunrise'),
            sunset=raw.get('sunset'),
            hourly_forecast=hourly_forecast,
        )
    except Exception as e:
        logger.error(f"Weather provider error for {lat},{lon}: {e}")
        return None


async def get_noaa_alerts(lat: float, lon: float) -> List[WeatherAlert]:
    """Get alerts using active provider (NOAA in prod, fixtures in demo)."""
    try:
        raw_alerts = await get_providers().alerts.get_alerts(lat, lon)
        alerts: List[WeatherAlert] = []
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=12)

        if ALERT_DEBUG:
            logger.info(
                "noaa_alerts_raw",
                extra={
                    "lat": round(lat, 4),
                    "lon": round(lon, 4),
                    "raw_count": len(raw_alerts),
                },
            )

        for alert in raw_alerts:
            # Parse timestamps to filter active alerts
            onset_str = alert.get('onset')
            expires_str = alert.get('expires')
            effective_str = alert.get('effective')
            ends_str = alert.get('ends')
            sent_str = alert.get('sent')
            instruction = alert.get('instruction')
            summary = alert.get('summary')
            urgency = alert.get('urgency')
            sent_dt = None
            if sent_str:
                try:
                    sent_dt = datetime.fromisoformat(sent_str.replace('Z', '+00:00')).astimezone(timezone.utc)
                except Exception:
                    sent_dt = None
            # Drop alerts without a sent timestamp or significantly stale
            if not sent_dt:
                continue
            if sent_dt < cutoff:
                continue
            
            # Determine if alert is currently active
            is_active = True
            try:
                # Use onset or effective as start time
                start_time = None
                if onset_str:
                    start_time = datetime.fromisoformat(onset_str.replace('Z', '+00:00'))
                elif effective_str:
                    start_time = datetime.fromisoformat(effective_str.replace('Z', '+00:00'))
                
                # Use expires or ends as end time
                end_time = None
                if expires_str:
                    end_time = datetime.fromisoformat(expires_str.replace('Z', '+00:00'))
                elif ends_str:
                    end_time = datetime.fromisoformat(ends_str.replace('Z', '+00:00'))
                
                # Only include alerts that are active now or within next 12 hours
                if start_time and end_time:
                    # Filter to alerts starting within last 12 hours and not yet expired
                    time_since_start = (now - start_time).total_seconds() / 3600  # hours
                    is_expired = now > end_time
                    is_active = time_since_start <= 12 and not is_expired
            except:
                # If timestamp parsing fails, include the alert
                pass
            
            if is_active and sent_dt >= cutoff:
                alerts.append(
                    WeatherAlert(
                        id=alert.get('id', str(uuid.uuid4())),
                        headline=alert.get('headline', 'Weather Alert'),
                        severity=alert.get('severity', 'Unknown'),
                        event=alert.get('event', 'Weather Event'),
                            description=alert.get('description', '')[:500],
                            instruction=instruction,
                            summary=summary,
                            urgency=urgency,
                            sent=sent_str,
                            issued=effective_str or sent_str,
                        areas=alert.get('areas'),
                        onset=onset_str,
                        expires=expires_str,
                        effective=effective_str,
                        ends=ends_str,
                    )
                )
        # Sort newest first by sent/issued/effective and cap at 10
        def _ts(a: WeatherAlert):
            for candidate in [a.sent, a.issued, a.effective, a.onset, a.expires]:
                if candidate:
                    try:
                        return datetime.fromisoformat(candidate.replace('Z', '+00:00'))
                    except Exception:
                        continue
            return datetime.min

        alerts.sort(key=_ts, reverse=True)
        return alerts[:10]
    except Exception as e:
        logger.error(f"Alerts provider error for {lat},{lon}: {e}")
        return []

def generate_packing_suggestions(waypoints_weather: List[WaypointWeather]) -> List[PackingSuggestion]:
    """Generate packing suggestions based on weather conditions."""
    suggestions = []
    
    temps = []
    has_rain = False
    has_snow = False
    has_wind = False
    has_sun = False
    
    for wp in waypoints_weather:
        if wp.weather:
            if wp.weather.temperature:
                temps.append(wp.weather.temperature)
            
            conditions = (wp.weather.conditions or '').lower()
            if 'rain' in conditions or 'shower' in conditions:
                has_rain = True
            if 'snow' in conditions or 'flurr' in conditions:
                has_snow = True
            if 'wind' in conditions:
                has_wind = True
            if 'sun' in conditions or 'clear' in conditions:
                has_sun = True
            
            # Check wind speed
            wind = wp.weather.wind_speed or ''
            if any(str(x) in wind for x in range(15, 50)):
                has_wind = True
    
    # Temperature-based suggestions
    if temps:
        min_temp = min(temps)
        max_temp = max(temps)
        
        if min_temp < 40:
            suggestions.append(PackingSuggestion(
                item="Warm jacket",
                reason=f"Temperatures as low as {min_temp}°F expected",
                priority="essential"
            ))
        if min_temp < 32:
            suggestions.append(PackingSuggestion(
                item="Gloves & hat",
                reason="Freezing temperatures along route",
                priority="essential"
            ))
        if max_temp > 85:
            suggestions.append(PackingSuggestion(
                item="Extra water",
                reason=f"High temperatures up to {max_temp}°F",
                priority="essential"
            ))
        if max_temp - min_temp > 20:
            suggestions.append(PackingSuggestion(
                item="Layers",
                reason=f"Temperature range of {max_temp - min_temp}°F",
                priority="recommended"
            ))
    
    # Condition-based suggestions
    if has_rain:
        suggestions.append(PackingSuggestion(
            item="Umbrella/rain jacket",
            reason="Rain expected along route",
            priority="essential"
        ))
    if has_snow:
        suggestions.append(PackingSuggestion(
            item="Snow gear & emergency kit",
            reason="Snow conditions expected",
            priority="essential"
        ))
    if has_wind:
        suggestions.append(PackingSuggestion(
            item="Windbreaker",
            reason="Windy conditions expected",
            priority="recommended"
        ))
    if has_sun:
        suggestions.append(PackingSuggestion(
            item="Sunglasses",
            reason="Sunny conditions expected",
            priority="recommended"
        ))
        suggestions.append(PackingSuggestion(
            item="Sunscreen",
            reason="Sun exposure during drive",
            priority="optional"
        ))
    
    # Always recommend
    suggestions.append(PackingSuggestion(
        item="Phone charger",
        reason="Keep devices charged for navigation",
        priority="essential"
    ))
    suggestions.append(PackingSuggestion(
        item="Snacks & water",
        reason="Stay hydrated and energized",
        priority="recommended"
    ))
    
    return suggestions[:8]  # Limit to 8 suggestions

def build_weather_timeline(waypoints_weather: List[WaypointWeather]) -> List[HourlyForecast]:
    """Build a combined weather timeline from all waypoints."""
    timeline = []
    seen_times = set()
    
    for wp in waypoints_weather:
        if wp.weather and wp.weather.hourly_forecast:
            for forecast in wp.weather.hourly_forecast[:4]:  # First 4 hours from each
                if forecast.time not in seen_times:
                    timeline.append(forecast)
                    seen_times.add(forecast.time)
    
    # Sort by time
    timeline.sort(key=lambda x: x.time)
    return timeline[:12]  # Return up to 12 hours

def calculate_safety_score(waypoints_weather: List[WaypointWeather], vehicle_type: str = "car") -> SafetyScore:
    """Calculate safety score based on weather conditions and vehicle type."""
    vehicle = VEHICLE_TYPES.get(vehicle_type, VEHICLE_TYPES["car"])
    
    base_score = 100
    factors = []
    recommendations = []
    
    for wp in waypoints_weather:
        if not wp.weather:
            continue
            
        # Temperature risks
        temp = wp.weather.temperature or 70
        if temp < 32:
            penalty = 15 * vehicle["ice_sensitivity"]
            base_score -= penalty
            if "Freezing temperatures - ice risk" not in factors:
                factors.append("Freezing temperatures - ice risk")
                recommendations.append("Reduce speed on bridges and overpasses")
        elif temp < 40:
            base_score -= 5 * vehicle["ice_sensitivity"]
            
        # Wind risks
        wind_str = wp.weather.wind_speed or "0 mph"
        try:
            wind_speed = int(''.join(filter(str.isdigit, wind_str.split()[0])))
        except:
            wind_speed = 0
            
        if wind_speed > 30:
            penalty = 20 * vehicle["wind_sensitivity"]
            base_score -= penalty
            if "High winds" not in factors:
                factors.append("High winds")
                if vehicle_type in ["semi", "rv", "trailer", "motorcycle"]:
                    recommendations.append("Consider delaying trip - dangerous wind conditions for your vehicle")
                else:
                    recommendations.append("Maintain firm grip on steering wheel")
        elif wind_speed > 20:
            base_score -= 8 * vehicle["wind_sensitivity"]
            
        # Visibility/condition risks
        conditions = (wp.weather.conditions or "").lower()
        if "snow" in conditions or "blizzard" in conditions:
            penalty = 25 * vehicle["visibility_sensitivity"]
            base_score -= penalty
            if "Snow/winter conditions" not in factors:
                factors.append("Snow/winter conditions")
                recommendations.append("Use winter driving mode, increase following distance")
        elif "rain" in conditions or "storm" in conditions:
            penalty = 15 * vehicle["visibility_sensitivity"]
            base_score -= penalty
            if "Rain/storm conditions" not in factors:
                factors.append("Rain/storm conditions")
                recommendations.append("Turn on headlights, reduce speed")
        elif "fog" in conditions:
            penalty = 20 * vehicle["visibility_sensitivity"]
            base_score -= penalty
            if "Low visibility - fog" not in factors:
                factors.append("Low visibility - fog")
                recommendations.append("Use low beam headlights, avoid sudden stops")
                
        # Alerts
        for alert in wp.alerts:
            if alert.severity in ["Extreme", "Severe"]:
                base_score -= 20
                if alert.event not in factors:
                    factors.append(f"Weather alert: {alert.event}")
    
    # Clamp score
    final_score = max(0, min(100, int(base_score)))
    
    # Determine risk level
    if final_score >= 80:
        risk_level = "low"
    elif final_score >= 60:
        risk_level = "moderate"
    elif final_score >= 40:
        risk_level = "high"
    else:
        risk_level = "extreme"
        recommendations.insert(0, "⚠️ Consider postponing trip if possible")
    
    if not factors:
        factors.append("Good driving conditions")
    if not recommendations:
        recommendations.append("Safe travels! Normal driving conditions expected")
        
    return SafetyScore(
        overall_score=final_score,
        risk_level=risk_level,
        vehicle_type=vehicle.get("name", vehicle_type),
        factors=factors[:5],
        recommendations=recommendations[:4]
    )

def compute_total_distance_miles(
    route_data: Optional[dict],
    turn_by_turn: Optional[List[TurnByTurnStep]] = None,
    waypoints_weather: Optional[List[WaypointWeather]] = None,
) -> float:
    """Compute total route distance in miles with safe fallbacks."""
    route_data = route_data or {}
    route_distance_meters = (
        route_data.get("distance")
        or sum((leg.get("distance") or 0.0) for leg in route_data.get("legs", []))
        or 0.0
    )
    total_distance_miles = route_distance_meters / 1609.344

    if total_distance_miles <= 0 and turn_by_turn:
        step_dist = sum(s.distance_miles or 0.0 for s in turn_by_turn)
        if step_dist > 0:
            total_distance_miles = float(step_dist)

    if total_distance_miles <= 0 and waypoints_weather:
        last_wp = waypoints_weather[-1].waypoint if waypoints_weather else None
        if last_wp and last_wp.distance_from_start is not None:
            total_distance_miles = float(last_wp.distance_from_start)

    return max(total_distance_miles, 0.0)


def generate_hazard_alerts(
    waypoints_weather: List[WaypointWeather],
    departure_time: datetime,
    total_route_miles: Optional[float] = None,
    total_route_minutes: Optional[float] = None,
    route_id: Optional[str] = None,
) -> List[HazardAlert]:
    """Generate proactive hazard alerts with countdown timers."""
    alerts: List[HazardAlert] = []

    cfg = HAZARD_CONFIG

    def sanitize_span(span: Optional[float]) -> Optional[float]:
        if span is None:
            return None
        span = max(0.0, span)
        if total_route_miles is not None:
            span = min(span, max(0.0, total_route_miles))
        if span < 0.1:
            return None
        return round(span, 1)

    def hazard_span_miles(idx: int, predicate) -> Optional[float]:
        if idx < 0 or idx >= len(waypoints_weather):
            return None
        wp = waypoints_weather[idx]
        if wp.waypoint.distance_from_start is None:
            return None
        start_dist = wp.waypoint.distance_from_start
        end_dist = wp.waypoint.distance_from_start

        j = idx - 1
        while j >= 0:
            prev = waypoints_weather[j]
            if prev.waypoint.distance_from_start is None or not predicate(prev):
                break
            start_dist = prev.waypoint.distance_from_start
            j -= 1

        j = idx + 1
        while j < len(waypoints_weather):
            nxt = waypoints_weather[j]
            if nxt.waypoint.distance_from_start is None or not predicate(nxt):
                break
            end_dist = nxt.waypoint.distance_from_start
            j += 1

        span = max(0.0, end_dist - start_dist)
        return sanitize_span(span)

    def is_ice_wp(wp: WaypointWeather) -> bool:
        cond = (wp.weather.conditions or "").lower() if wp.weather else ""
        temp = wp.weather.temperature if wp.weather else None
        return (temp is not None and temp <= cfg["ice_temp_f"]) or any(k in cond for k in ["ice", "freezing", "sleet", "freezing rain"])

    def is_snow_wp(wp: WaypointWeather) -> bool:
        cond = (wp.weather.conditions or "").lower() if wp.weather else ""
        return "snow" in cond or "blizzard" in cond

    def is_slippery_wp(wp: WaypointWeather) -> bool:
        cond = (wp.weather.conditions or "").lower() if wp.weather else ""
        temp = wp.weather.temperature if wp.weather else None
        return (temp is not None and temp <= cfg["slippery_temp_f"]) or any(k in cond for k in ["sleet", "freezing", "black ice", "icy"])

    def build_conditions_detail(wp: WaypointWeather) -> str:
        if not wp.weather:
            return ""
        parts = []
        if wp.weather.temperature is not None:
            parts.append(f"{wp.weather.temperature}°F")
        cond = wp.weather.conditions or ""
        if cond:
            parts.append(cond)
        wind = wp.weather.wind_speed or ""
        if wind:
            parts.append(f"Wind {wind}")
        return ", ".join(parts)

    def level_for_severity(sev: str) -> str:
        sev_l = (sev or "").lower()
        if sev_l in {"extreme", "high"}:
            return "Hazard"
        if sev_l == "medium":
            return "Advisory"
        if sev_l == "low":
            return "Watch"
        return "Unknown"

    def driver_advice(h_type: str, severity: str, *, include_bridges: bool = False) -> str:
        h_type = (h_type or "").lower()
        sev = (severity or "").lower()
        if h_type in {"ice", "snow"}:
            base = "Reduce speed, use chains if required"
            if include_bridges:
                base += ", watch bridges/overpasses for black ice"
            return base + "."
        if h_type == "rain":
            return "Increase following distance; consider waiting at next truck stop if heavy downpour."
        if h_type == "wind":
            return "High-profile vehicles: reduce speed and consider stopping if crosswinds increase."
        if h_type == "visibility":
            return "Use low beams, slow down, and allow extra stopping distance."
        if sev in {"extreme", "high"}:
            return "Reduce speed and prepare to stop if conditions worsen."
        return "Drive cautiously and allow extra stopping distance."

    def parse_wind(wind_str: Optional[str]) -> int:
        if not wind_str:
            return 0
        digits = "".join(ch for ch in wind_str if ch.isdigit())
        try:
            return int(digits) if digits else 0
        except Exception:
            return 0

    def precip_label(conditions: str) -> str:
        c = conditions.lower()
        if "freezing rain" in c or "freezing drizzle" in c:
            return "freezing rain"
        if "sleet" in c:
            return "sleet"
        if "snow" in c or "blizzard" in c:
            return "snow"
        if "storm" in c or "thunder" in c:
            return "thunderstorm"
        if "drizzle" in c:
            return "drizzle"
        if "rain" in c:
            return "rain"
        return conditions or "precipitation"

    def build_rationale(**kwargs) -> str:
        parts = []
        for k, v in kwargs.items():
            parts.append(f"{k}={v}")
        return ", ".join(parts)

    def normalize_label(label: Optional[str]) -> str:
        if not label:
            return "unnamed road"
        return " ".join(label.strip().lower().split())

    def compute_hazard_id(alert: HazardAlert) -> str:
        start = round(alert.distance_miles or 0.0, 1)
        span = round(alert.span_miles or cfg["default_span_miles"], 1)
        road = normalize_label(alert.road_name)
        level = (alert.alert_level or alert.severity or "").lower()
        raw = f"{alert.type.lower()}|{level}|{road}|{start}|{span}"
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]

    def extract_road_and_span(text: Optional[str]) -> tuple[Optional[str], Optional[float]]:
        if not text:
            return None, None
        road = None
        span = None
        # Simple highway pattern match (I-80, US-50, SR 24, Hwy 101)
        road_match = re.search(r"\b(I-[0-9]{1,3}|US[- ]?[0-9]{1,3}|SR[- ]?[0-9]{1,3}|Hwy[- ]?[0-9]{1,3})\b", text, re.IGNORECASE)
        if road_match:
            road = road_match.group(1)
        span_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:mile|mi)\b", text, re.IGNORECASE)
        if span_match:
            try:
                span = float(span_match.group(1))
            except Exception:
                span = None
        return road, span

    def classify_level(event_name: Optional[str]) -> str:
        if not event_name:
            return "Unknown"
        name = event_name.lower()
        if "warning" in name:
            return "Warning"
        if "watch" in name:
            return "Watch"
        if "advisory" in name:
            return "Advisory"
        if "statement" in name:
            return "Statement"
        return "Unknown"

    def primary_precip(temp_f: Optional[float], conditions: str) -> str:
        c = (conditions or "").lower()
        snowy_terms = ["snow", "blizzard", "sleet", "freezing", "wintry", "ice"]
        precip_terms = ["snow", "sleet", "freezing", "rain", "drizzle", "storm", "shower", "precip"]
        has_snowy = any(k in c for k in snowy_terms)
        has_precip = any(k in c for k in precip_terms)
        if has_snowy:
            return "snow"
        if temp_f is not None and temp_f <= 34 and has_precip:
            return "snow"
        if has_precip:
            return "rain"
        return "none"

    def compute_eta(distance_miles: float) -> int:
        if total_route_miles and total_route_minutes is not None:
            miles = max(total_route_miles, 1e-3)
            minutes = max(total_route_minutes or 0.0, 0.0)
            ratio = max(0.0, distance_miles) / miles
            return int(round(ratio * minutes))
        return calculate_eta(distance_miles)

    def pick_driver_action(level: str, instruction: Optional[str]) -> str:
        if instruction:
            return instruction.strip()
        lookup = {
            "Warning": "Reduce speed and be prepared to stop if conditions worsen.",
            "Watch": "Stay alert and plan for changing conditions ahead.",
            "Advisory": "Use caution and allow extra travel time.",
            "Statement": "Monitor conditions and drive cautiously.",
        }
        return lookup.get(level, "Drive with caution and follow posted guidance.")

    def extract_wind_gust_mph(weather: Optional[WeatherData]) -> Optional[int]:
        if not weather:
            return None
        gust_candidates = [
            getattr(weather, "wind_gust", None),
            getattr(weather, "wind_gust_mph", None),
            getattr(weather, "gust", None),
            getattr(weather, "gust_mph", None),
        ]
        for gust in gust_candidates:
            if gust is None:
                continue
            if isinstance(gust, (int, float)):
                return int(round(gust))
            if isinstance(gust, str):
                parsed = parse_wind(gust)
                if parsed:
                    return parsed
        return None

    def compute_precip_intensity(conditions: Optional[str], precip_type: str) -> Optional[str]:
        cond = (conditions or "").lower()
        if not cond and precip_type == "none":
            return None
        if any(key in cond for key in ["whiteout", "blizzard", "heavy", "torrential", "downpour"]):
            return "heavy"
        if any(key in cond for key in ["moderate", "steady"]):
            return "moderate"
        if any(key in cond for key in ["light", "drizzle", "shower", "sprinkle"]):
            return "light"
        if precip_type in {"snow", "rain"}:
            return "moderate"
        return None

    def compute_visibility_label(conditions: Optional[str], precip_type: str, wind_mph: int) -> str:
        cond = (conditions or "").lower()
        heavy_snow = precip_type == "snow" and ("heavy" in cond or "blizzard" in cond or "whiteout" in cond)
        moderate_snow = precip_type == "snow" and "snow" in cond
        foggy = "fog" in cond
        if heavy_snow or wind_mph > 25:
            return "Severely Reduced"
        if moderate_snow or wind_mph >= 15 or foggy:
            return "Reduced"
        return "Normal"

    def apply_weather_fields(
        alert: HazardAlert,
        *,
        temp_f: Optional[int],
        wind_mph: Optional[int],
        wind_gust_mph: Optional[int],
        precip_type: str,
        precip_intensity: Optional[str],
        visibility: Optional[str],
    ) -> None:
        alert.temp_f = temp_f
        alert.wind_mph = wind_mph if wind_mph is not None else None
        alert.wind_gust_mph = wind_gust_mph
        alert.precip_type = precip_type if precip_type != "none" else None
        alert.precip_intensity = precip_intensity
        alert.visibility = visibility

    def enrich_alert_fields(alert: HazardAlert):
        if not alert.road_name or alert.span_miles is None:
            for text in [alert.full_description, alert.description, alert.message, alert.recommendation]:
                road, span = extract_road_and_span(text or "")
                if not alert.road_name and road:
                    alert.road_name = road
                if alert.span_miles is None and span is not None:
                    alert.span_miles = span
                if alert.road_name and alert.span_miles is not None:
                    break

        if not alert.alert_level:
            level_map = {"extreme": "Warning", "high": "Warning", "medium": "Advisory", "low": "Statement"}
            alert.alert_level = level_map.get(alert.severity.lower(), "Unknown") if hasattr(alert, "severity") else "Unknown"

        if not alert.driver_action:
            alert.driver_action = alert.recommendation or "Drive with caution and follow posted guidance."
    
    seen_primary: Dict[float, tuple[str, str]] = {}

    for idx, wp in enumerate(waypoints_weather):
        if not wp.weather:
            continue
            
        distance = wp.waypoint.distance_from_start or 0
        eta_mins = compute_eta(distance)
        location_name = wp.waypoint.name or f"Mile {int(distance)}"
        road_name = wp.waypoint.name or "Unnamed road"
        conditions_detail = build_conditions_detail(wp)
        wind_speed = parse_wind(wp.weather.wind_speed)
        precip_type = primary_precip(wp.weather.temperature, wp.weather.conditions or "")
        temp_f = wp.weather.temperature
        wind_gust_mph = extract_wind_gust_mph(wp.weather)
        precip_intensity = compute_precip_intensity(wp.weather.conditions, precip_type)
        visibility_level = compute_visibility_label(wp.weather.conditions, precip_type, wind_speed)

        # Include any active NWS alerts with full detail fields
        for nws in wp.alerts:
            severity_raw = (nws.severity or "medium").lower()
            severity = {
                "extreme": "extreme",
                "severe": "high",
                "moderate": "medium",
                "minor": "low",
            }.get(severity_raw, severity_raw or "medium")

            road_name, span_miles = extract_road_and_span(nws.description or nws.summary or nws.headline or "")
            span_miles = sanitize_span(span_miles)
            alert_level = classify_level(nws.event or nws.headline)
            driver_action = pick_driver_action(alert_level, nws.instruction)
            rationale = build_rationale(source="nws", event=nws.event or nws.headline)

            props = {
                "event": nws.event,
                "headline": nws.headline,
                "description": nws.description,
                "instruction": nws.instruction,
                "areaDesc": nws.areas,
                "onset": nws.onset,
                "expires": nws.expires,
                "effective": nws.effective,
                "ends": nws.ends,
                "urgency": nws.urgency,
                "sent": nws.sent,
                "issued": nws.issued,
            }

            alert_obj = HazardAlert(
                type="nws",
                severity=severity,
                distance_miles=distance,
                eta_minutes=eta_mins,
                message=nws.headline or nws.event or "Weather Alert",
                recommendation="Follow NWS guidance and monitor local conditions",
                countdown_text=f"{nws.event or 'Alert'} near mile {int(distance)}",
                location_name=location_name,
                event=nws.event,
                headline=nws.headline,
                description=nws.description,
                full_description=nws.description,
                instruction=nws.instruction,
                areaDesc=nws.areas,
                onset=nws.onset,
                expires=nws.expires,
                properties=props,
                road_name=road_name,
                span_miles=span_miles,
                alert_level=alert_level,
                driver_action=driver_action,
                rationale=rationale,
            )
            apply_weather_fields(
                alert_obj,
                temp_f=temp_f,
                wind_mph=wind_speed,
                wind_gust_mph=wind_gust_mph,
                precip_type=precip_type,
                precip_intensity=precip_intensity,
                visibility=visibility_level,
            )
            enrich_alert_fields(alert_obj)
            alerts.append(alert_obj)
        
        # Wind hazards
        if wind_speed >= cfg["wind_medium_mph"]:
            if wind_speed >= cfg["wind_extreme_mph"]:
                severity = "extreme"
            elif wind_speed >= cfg["wind_high_mph"]:
                severity = "high"
            else:
                severity = "medium"
            alert_level = level_for_severity(severity)
            driver_action = driver_advice("wind", severity)
            rationale = build_rationale(wind_mph=wind_speed, threshold_medium=cfg["wind_medium_mph"], threshold_high=cfg["wind_high_mph"], threshold_extreme=cfg["wind_extreme_mph"])
            alert_obj = HazardAlert(
                type="wind",
                severity=severity,
                distance_miles=distance,
                eta_minutes=eta_mins,
                message=f"Strong winds of {wind_speed} mph",
                recommendation=f"Reduce speed to {max(35, 65 - wind_speed + 25)} mph",
                countdown_text=f"High winds in {eta_mins} minutes" if eta_mins > 0 else "High winds at start",
                location_name=location_name,
                road_name=road_name,
                span_miles=None,
                alert_level=alert_level,
                driver_action=driver_action,
                description=conditions_detail or None,
                full_description=conditions_detail or None,
                rationale=rationale,
            )
            apply_weather_fields(
                alert_obj,
                temp_f=temp_f,
                wind_mph=wind_speed,
                wind_gust_mph=wind_gust_mph,
                precip_type=precip_type,
                precip_intensity=precip_intensity,
                visibility=visibility_level,
            )
            enrich_alert_fields(alert_obj)
            alerts.append(alert_obj)
            
        # Rain/visibility hazards
        conditions = (wp.weather.conditions or "").lower()
        if precip_type == "rain" and ("heavy rain" in conditions or "storm" in conditions):
            span = hazard_span_miles(idx, is_slippery_wp)
            alert_level = level_for_severity("high")
            driver_action = driver_advice("rain", "high")
            rationale = build_rationale(conditions=conditions, span_miles=span or cfg["default_span_miles"], wind_mph=wind_speed)
            alert_obj = HazardAlert(
                type="rain",
                severity="high",
                distance_miles=distance,
                eta_minutes=eta_mins,
                message=f"Heavy rain expected (wind {wind_speed} mph)" if wind_speed else "Heavy rain expected",
                recommendation="Reduce speed, increase following distance to 4+ seconds; consider waiting at next truck stop",
                countdown_text=f"Heavy rain in {eta_mins} minutes at mile {int(distance)}",
                location_name=location_name,
                road_name=road_name,
                span_miles=span,
                alert_level=alert_level,
                driver_action=driver_action,
                description=conditions_detail or None,
                full_description=conditions_detail or None,
                rationale=rationale,
            )
            apply_weather_fields(
                alert_obj,
                temp_f=temp_f,
                wind_mph=wind_speed,
                wind_gust_mph=wind_gust_mph,
                precip_type=precip_type,
                precip_intensity=precip_intensity,
                visibility=visibility_level,
            )
            enrich_alert_fields(alert_obj)
            alerts.append(alert_obj)
            key = round(distance, 1)
            seen_primary[key] = ("rain", "high")
        elif precip_type == "rain" and ("rain" in conditions or "shower" in conditions):
            span = hazard_span_miles(idx, is_slippery_wp)
            alert_level = level_for_severity("medium")
            driver_action = driver_advice("rain", "medium")
            rationale = build_rationale(conditions=conditions, span_miles=span or cfg["default_span_miles"])
            alert_obj = HazardAlert(
                type="rain",
                severity="medium",
                distance_miles=distance,
                eta_minutes=eta_mins,
                message="Rain expected",
                recommendation="Turn on headlights and wipers",
                countdown_text=f"Rain in {eta_mins} minutes",
                location_name=location_name,
                road_name=road_name,
                span_miles=span,
                alert_level=alert_level,
                driver_action=driver_action,
                description=conditions_detail or None,
                full_description=conditions_detail or None,
                rationale=rationale,
            )
            apply_weather_fields(
                alert_obj,
                temp_f=temp_f,
                wind_mph=wind_speed,
                wind_gust_mph=wind_gust_mph,
                precip_type=precip_type,
                precip_intensity=precip_intensity,
                visibility=visibility_level,
            )
            enrich_alert_fields(alert_obj)
            key = round(distance, 1)
            prev = seen_primary.get(key)
            if not prev or prev != ("rain", "medium"):
                alerts.append(alert_obj)
                seen_primary[key] = ("rain", "medium")
            
        # Snow/ice hazards
        if precip_type == "snow":
            span = hazard_span_miles(idx, is_snow_wp)
            alert_level = level_for_severity("high")
            whiteout = wind_speed >= 35
            driver_action = driver_advice("snow", "high", include_bridges=(wp.weather.temperature or 999) <= 34)
            rationale = build_rationale(conditions=conditions, temp_f=wp.weather.temperature, wind_mph=wind_speed, span_miles=span or cfg["default_span_miles"])
            message = "Whiteout risk: blowing snow" if whiteout else "Snow expected"
            if wp.weather.temperature is not None:
                message += f" ({wp.weather.temperature}°F"
                if wind_speed:
                    message += f", wind {wind_speed} mph"
                message += ")"
            alert_obj = HazardAlert(
                type="whiteout" if whiteout else "snow",
                severity="extreme" if whiteout else "high",
                distance_miles=distance,
                eta_minutes=eta_mins,
                message=message,
                recommendation="Visibility may drop to near zero; slow sharply or pause travel" if whiteout else "Reduce speed by 50%, chains may be required; plan for reduced traction",
                countdown_text=f"Snow in {eta_mins} minutes" if not whiteout else f"Whiteout risk in {eta_mins} minutes",
                location_name=location_name,
                road_name=road_name,
                span_miles=span,
                alert_level=alert_level if not whiteout else "Warning",
                driver_action=driver_action,
                description=conditions_detail or None,
                full_description=conditions_detail or None,
                rationale=rationale,
            )
            apply_weather_fields(
                alert_obj,
                temp_f=temp_f,
                wind_mph=wind_speed,
                wind_gust_mph=wind_gust_mph,
                precip_type=precip_type,
                precip_intensity=precip_intensity,
                visibility=visibility_level,
            )
            enrich_alert_fields(alert_obj)
            key = round(distance, 1)
            prev = seen_primary.get(key)
            if not prev or prev != (alert_obj.type, alert_obj.severity):
                alerts.append(alert_obj)
                seen_primary[key] = (alert_obj.type, alert_obj.severity)
            
        # Temperature-based ice warnings
        temp = wp.weather.temperature or 70
        if temp <= cfg["ice_temp_f"]:
            span = hazard_span_miles(idx, is_ice_wp)
            alert_level = level_for_severity("high")
            include_bridges = True if any(k in conditions for k in ["rain", "snow", "drizzle", "sleet", "freezing"]) else False
            driver_action = driver_advice("ice", "high", include_bridges=include_bridges)
            rationale = build_rationale(temp_f=temp, threshold=cfg["ice_temp_f"], span_miles=span or cfg["default_span_miles"], wind_mph=wind_speed)
            message = f"Ice risk: {temp}°F"
            if wind_speed:
                message += f", wind {wind_speed} mph"
            alert_obj = HazardAlert(
                type="ice",
                severity="high",
                distance_miles=distance,
                eta_minutes=eta_mins,
                message=message,
                recommendation="Reduce speed; black ice likely on bridges/overpasses" if include_bridges else "Reduce speed; traction reduced",
                countdown_text=f"Ice risk in {eta_mins} minutes",
                location_name=location_name,
                road_name=road_name,
                span_miles=span,
                alert_level=alert_level,
                driver_action=driver_action,
                description=conditions_detail or None,
                full_description=conditions_detail or None,
                rationale=rationale,
            )
            apply_weather_fields(
                alert_obj,
                temp_f=temp_f,
                wind_mph=wind_speed,
                wind_gust_mph=wind_gust_mph,
                precip_type=precip_type,
                precip_intensity=precip_intensity,
                visibility=visibility_level,
            )
            enrich_alert_fields(alert_obj)
            alerts.append(alert_obj)
            
        # Fog warnings
        if "fog" in conditions:
            span = hazard_span_miles(idx, is_slippery_wp)
            alert_level = level_for_severity("medium")
            driver_action = driver_advice("visibility", "medium")
            rationale = build_rationale(conditions=conditions, span_miles=span or cfg["default_span_miles"])
            alert_obj = HazardAlert(
                type="visibility",
                severity="high",
                distance_miles=distance,
                eta_minutes=eta_mins,
                message="Fog reducing visibility",
                recommendation="Use low beams, reduce speed to match visibility",
                countdown_text=f"Fog in {eta_mins} minutes",
                location_name=location_name,
                road_name=road_name,
                span_miles=span,
                alert_level=alert_level,
                driver_action=driver_action,
                description=conditions_detail or None,
                full_description=conditions_detail or None,
                rationale=rationale,
            )
            apply_weather_fields(
                alert_obj,
                temp_f=temp_f,
                wind_mph=wind_speed,
                wind_gust_mph=wind_gust_mph,
                precip_type=precip_type,
                precip_intensity=precip_intensity,
                visibility=visibility_level,
            )
            enrich_alert_fields(alert_obj)
            alerts.append(alert_obj)
            
        # Weather alerts from NOAA - deduplicate by alert ID and event type
        seen_alert_ids = set()
        for alert in wp.alerts:
            # Create a unique key for this alert (id + event type + location)
            alert_key = f"{getattr(alert, 'id', '')}:{alert.event}:{location_name}"
            if alert_key in seen_alert_ids:
                continue  # Skip duplicate alerts
            seen_alert_ids.add(alert_key)
            
            severity_map = {"Extreme": "extreme", "Severe": "high", "Moderate": "medium"}
            alert_obj = HazardAlert(
                type="alert",
                severity=severity_map.get(alert.severity, "medium"),
                distance_miles=distance,
                eta_minutes=eta_mins,
                message=alert.event,
                recommendation=alert.headline[:100],
                countdown_text=f"{alert.event} in {eta_mins} minutes",
                location_name=location_name
            )
            apply_weather_fields(
                alert_obj,
                temp_f=temp_f,
                wind_mph=wind_speed,
                wind_gust_mph=wind_gust_mph,
                precip_type=precip_type,
                precip_intensity=precip_intensity,
                visibility=visibility_level,
            )
            enrich_alert_fields(alert_obj)
            alerts.append(alert_obj)
    
    def merge_adjacent(alert_list: List[HazardAlert]) -> List[HazardAlert]:
        merged: List[HazardAlert] = []
        gap = cfg["merge_gap_miles"]
        default_span = cfg["default_span_miles"]

        for alert in sorted(alert_list, key=lambda a: a.distance_miles or 0):
            start = max(0.0, alert.distance_miles or 0.0)
            span = sanitize_span(alert.span_miles)
            span = span if span is not None else default_span
            end = start + span

            if merged:
                prev = merged[-1]
                same_type_level = (alert.type == prev.type) and ((alert.alert_level or "") == (prev.alert_level or ""))
                allow_any_road = alert.type in {"rain", "snow", "whiteout", "ice"}
                roads_compatible = allow_any_road or (not prev.road_name) or (not alert.road_name) or (prev.road_name == alert.road_name)
                if same_type_level and roads_compatible:
                    prev_start = max(0.0, prev.distance_miles or 0.0)
                    prev_span = sanitize_span(prev.span_miles)
                    prev_span = prev_span if prev_span is not None else default_span
                    prev_end = prev_start + prev_span
                    gap_miles = start - prev_end
                    if gap_miles <= gap:
                        new_end = max(prev_end, end)
                        new_span = sanitize_span(new_end - prev_start)
                        prev.span_miles = new_span
                        prev.distance_miles = prev_start
                        if not prev.road_name:
                            prev.road_name = alert.road_name
                        continue

            alert.span_miles = sanitize_span(span)
            alert.distance_miles = start
            merged.append(alert)
        return merged

    merged_alerts = merge_adjacent(alerts)

    # Deduplicate by message content + start (second level deduplication)
    seen_messages = set()
    unique_alerts = []
    for alert in merged_alerts:
        start_key = round(alert.distance_miles or 0.0, 1)
        message_key = f"{alert.type}:{alert.message}:{start_key}"
        if message_key not in seen_messages:
            seen_messages.add(message_key)
            unique_alerts.append(alert)
    
    # Sort by severity (most critical first), then by distance (earlier), then by type priority, then by span descending
    severity_order = {"extreme": 0, "high": 1, "medium": 2, "low": 3}
    type_priority = {"ice": 0, "whiteout": 0, "snow": 1, "rain": 2}
    unique_alerts.sort(
        key=lambda x: (
            severity_order.get(x.severity, 3),
            round(x.distance_miles or 0, 1),
            type_priority.get(x.type, 5),
            -(x.span_miles or 0),
        )
    )

    # Collapse duplicates at identical start miles: keep the highest-severity/type-priority alert only.
    def alert_rank(alert: HazardAlert) -> tuple[int, int, float]:
        return (
            severity_order.get(alert.severity, 3),
            type_priority.get(alert.type, 5),
            -(alert.span_miles or 0.0),
        )

    best_by_start: dict[float, HazardAlert] = {}
    for alert in unique_alerts:
        start_key = round(alert.distance_miles or 0.0, 1)
        current_best = best_by_start.get(start_key)
        if current_best is None or alert_rank(alert) < alert_rank(current_best):
            best_by_start[start_key] = alert

    unique_alerts = sorted(best_by_start.values(), key=lambda a: (
        severity_order.get(a.severity, 3),
        round(a.distance_miles or 0, 1),
        type_priority.get(a.type, 5),
        -(a.span_miles or 0),
    ))

    # Apply deterministic hazard IDs and rationale if missing; compute end_mile and sanitize
    for alert in unique_alerts:
        alert.distance_miles = round(max(0.0, alert.distance_miles or 0.0), 1)
        span_used = alert.span_miles if alert.span_miles is not None else cfg["default_span_miles"]
        span_used = sanitize_span(span_used) or 0.0
        alert.span_miles = span_used
        end_mile = alert.distance_miles + span_used
        if total_route_miles is not None:
            end_mile = min(end_mile, max(0.0, total_route_miles))
        alert.end_mile = round(end_mile, 1)
        alert.eta_minutes = compute_eta(alert.distance_miles)
        if not alert.rationale:
            alert.rationale = "generated hazard"
        alert.hazard_id = compute_hazard_id(alert)
        alert.hazard_schema_version = HAZARD_SCHEMA_VERSION

    # Cap total alerts per route (env-driven)
    max_alerts = max(1, cfg.get("max_alerts", 10))
    limited_alerts = unique_alerts[:max_alerts]

    if route_id:
        logger.info(
            "hazard_alerts_generated",
            extra={
                "route_id": route_id,
                "waypoints": len(waypoints_weather),
                "alerts_pre": len(alerts),
                "alerts_merged": len(merged_alerts),
                "alerts_final": len(unique_alerts),
                "alerts_returned": len(limited_alerts),
                "max_alerts": max_alerts,
            },
        )

    sample = limited_alerts[:5]
    logger.info(
        "hazard_alerts_segments_sample",
        extra={
            "total_miles": total_route_miles,
            "total_minutes": total_route_minutes,
            "num_segments": len(limited_alerts),
            "sample": [
                {
                    "start_mile": a.distance_miles,
                    "span_miles": a.span_miles,
                    "eta_minutes": a.eta_minutes,
                    "type": a.type,
                    "level": a.alert_level,
                }
                for a in sample
            ],
        },
    )
    if ALERT_DEBUG:
        logger.info(
            "hazard_alerts_debug",
            extra={
                "total_miles": total_route_miles,
                "total_minutes": total_route_minutes,
                "segments": [
                    {
                        "start_mile": a.distance_miles,
                        "span_miles": a.span_miles,
                        "eta_minutes": a.eta_minutes,
                        "type": a.type,
                        "level": a.alert_level,
                    }
                    for a in limited_alerts
                ],
            },
        )
    if cfg.get("log_detail", 0) > 0:
        for alert in limited_alerts:
            logger.debug(
                "hazard_alert_detail",
                extra={
                    "route_id": route_id,
                    "type": alert.type,
                    "level": alert.alert_level,
                    "road": alert.road_name,
                    "start_miles": alert.distance_miles,
                    "span_miles": alert.span_miles,
                    "hazard_id": alert.hazard_id,
                },
            )
    
    return limited_alerts


def build_geometry_mile_index(encoded_polyline: Optional[str]) -> List[tuple[float, float, float]]:
    """Decode a polyline and return coordinates with cumulative mileposts."""
    if not encoded_polyline:
        return []
    try:
        coords = polyline.decode(encoded_polyline, 6)
    except Exception:
        return []
    if len(coords) < 2:
        return []

    index: List[tuple[float, float, float]] = []
    total = 0.0
    prev_lat, prev_lon = coords[0]
    index.append((prev_lat, prev_lon, total))
    for lat, lon in coords[1:]:
        total += haversine_distance(prev_lat, prev_lon, lat, lon)
        index.append((lat, lon, total))
        prev_lat, prev_lon = lat, lon
    return index


def coordinate_at_mile(index: List[tuple[float, float, float]], mile: float) -> Optional[tuple[float, float]]:
    """Interpolate a coordinate at a given mile along a precomputed index."""
    if not index:
        return None
    target = max(0.0, mile)
    for i in range(1, len(index)):
        prev_lat, prev_lon, prev_mile = index[i - 1]
        curr_lat, curr_lon, curr_mile = index[i]
        if target <= curr_mile:
            span = max(curr_mile - prev_mile, 1e-6)
            ratio = (target - prev_mile) / span
            lat = prev_lat + (curr_lat - prev_lat) * ratio
            lon = prev_lon + (curr_lon - prev_lon) * ratio
            return lat, lon
    return (index[-1][0], index[-1][1])


async def hydrate_alert_roads_from_geometry(alerts: List[HazardAlert], geometry_index: List[tuple[float, float, float]]):
    """Populate road names via reverse geocoding at each alert start mile."""
    if not alerts or not geometry_index:
        return

    for alert in alerts:
        coord = coordinate_at_mile(geometry_index, alert.distance_miles or 0.0)
        if not coord:
            continue
        lat, lon = coord
        try:
            road_name = await reverse_geocode(lat, lon)
        except Exception as exc:  # noqa: BLE001
            logger.warning("hazard_reverse_geocode_failed", extra={"error": str(exc)})
            continue
        if not road_name:
            continue

        if not alert.road_name:
            alert.road_name = road_name

        base_title = alert.message or alert.event or alert.headline or alert.type.title() or "Hazard"
        base_title_clean = base_title.strip()
        lower_base = base_title_clean.lower()
        if road_name.lower() not in lower_base:
            alert.message = f"{base_title_clean} on {road_name}"
        else:
            alert.message = base_title_clean

        eta_val = max(alert.eta_minutes or 0, 0)
        alert.countdown_text = f"{alert.message} in {eta_val} minutes"


def build_condition_segments(alerts: List[HazardAlert], *, category: str) -> List[ConditionSegment]:
    """Project hazard alerts into condensed condition bands for road or weather."""
    road_types = {"ice", "whiteout", "snow", "rain", "visibility"}
    weather_types = {"ice", "snow", "whiteout", "wind", "rain", "visibility", "nws", "alert"}
    allowed = road_types if category == "road" else weather_types
    avg_speed_mph = 55.0
    interval = max(1.0, RESAMPLE_MILES)

    segments: List[ConditionSegment] = []
    for alert in alerts or []:
        if alert.type not in allowed:
            continue
        start = max(0.0, alert.distance_miles or 0.0)
        span = alert.span_miles or HAZARD_CONFIG.get("default_span_miles", 5.0)
        end = max(start, start + span)
        eta_start = alert.eta_minutes if alert.eta_minutes is not None else int(start / avg_speed_mph * 60)
        eta_end = eta_start + int(span / max(avg_speed_mph, 1e-3) * 60)
        chunk_start = start
        while chunk_start < end - 1e-6:
            chunk_end = min(end, chunk_start + interval)
            chunk_span = max(0.0, chunk_end - chunk_start)
            chunk_eta_start = int((chunk_start / max(avg_speed_mph, 1e-3)) * 60)
            chunk_eta_end = int((chunk_end / max(avg_speed_mph, 1e-3)) * 60)
            segments.append(
                ConditionSegment(
                    type=alert.type,
                    category=category,
                    road_name=alert.road_name or "Unnamed road",
                    start_mile=round(chunk_start, 1),
                    end_mile=round(chunk_end, 1),
                    span_miles=round(chunk_span, 1),
                    eta_start_min=chunk_eta_start,
                    eta_end_min=chunk_eta_end,
                    conditions=alert.message or alert.type,
                    rationale=alert.rationale,
                    driver_action=alert.driver_action or alert.recommendation,
                    severity=alert.severity,
                )
            )
            chunk_start = chunk_end

    segments.sort(key=lambda s: s.start_mile)
    return segments

async def find_rest_stops(route_geometry: str, waypoints_weather: List[WaypointWeather]) -> List[RestStop]:
    """Find rest stops, gas stations along the route with weather at arrival."""
    rest_stops = []
    if not route_geometry:
        return rest_stops
    route_coords = polyline.decode(route_geometry, 6)
    
    # Sample points along route (every ~75 miles)
    total_points = len(route_coords)
    sample_interval = max(1, total_points // 5)
    
    for i in range(sample_interval, total_points - sample_interval, sample_interval):
        lat, lon = route_coords[i]
        
        # Calculate approximate distance and ETA
        approx_distance = (i / total_points) * (waypoints_weather[-1].waypoint.distance_from_start or 100)
        approx_eta = int(approx_distance / 55 * 60)
        
        try:
            pois = await get_providers().geocode.search_pois(lat, lon, "rest stop gas station", limit=2)
            for poi in pois[:1]:
                # Find nearest waypoint weather
                weather_desc = "Unknown"
                temp = None
                for wp in waypoints_weather:
                    if wp.weather and abs(wp.waypoint.distance_from_start - approx_distance) < 30:
                        weather_desc = wp.weather.conditions or "Clear"
                        temp = wp.weather.temperature
                        break

                recommendation = "Good rest stop option"
                if temp and temp > 85:
                    recommendation = "Cool down and hydrate here"
                elif "rain" in weather_desc.lower():
                    recommendation = "Wait out the rain here"
                elif "clear" in weather_desc.lower() or "sunny" in weather_desc.lower():
                    recommendation = "Good weather - stretch your legs!"

                rest_stops.append(RestStop(
                    name=poi.get('name', 'Rest Stop'),
                    type=poi.get('type', 'rest_area'),
                    lat=poi.get('lat', lat),
                    lon=poi.get('lon', lon),
                    distance_miles=round(approx_distance, 1),
                    eta_minutes=approx_eta,
                    weather_at_arrival=weather_desc,
                    temperature_at_arrival=temp,
                    recommendation=recommendation
                ))
        except Exception as e:
            logger.error(f"Error finding rest stops: {e}")
            
    return rest_stops[:5]

def generate_trucker_warnings(waypoints_weather: List[WaypointWeather], vehicle_height_ft: Optional[float] = None) -> List[str]:
    """Generate trucker-specific warnings for high-profile vehicles."""
    warnings = []
    
    # Default to standard semi truck height if not provided
    if vehicle_height_ft is None:
        vehicle_height_ft = 13.5
    
    for wp in waypoints_weather:
        if not wp.weather:
            continue
            
        distance = wp.waypoint.distance_from_start or 0
        location = wp.waypoint.name or f"Mile {int(distance)}"
        
        # CHECK FOR BRIDGE CLEARANCE ISSUES FIRST (CRITICAL)
        bridge_warnings = get_bridge_warnings(location, vehicle_height_ft)
        if bridge_warnings:
            warnings.extend(bridge_warnings)
        
        # WIND WARNINGS for high-profile vehicles
        wind_str = wp.weather.wind_speed or "0 mph"
        try:
            wind_speed = int(''.join(filter(str.isdigit, wind_str.split()[0])))
        except:
            wind_speed = 0
            
        if wind_speed > 20:
            if wind_speed > 35:
                warnings.append(f"⚠️ DANGER: {wind_speed} mph winds at {location} - IMMEDIATE: Consider stopping until winds subside")
            elif wind_speed > 25:
                warnings.append(f"🚛 High crosswind risk ({wind_speed} mph) at {location} - Reduce speed significantly and exercise caution")
            else:
                warnings.append(f"💨 Moderate winds ({wind_speed} mph) at {location} - Stay alert and maintain firm grip on wheel")
                
        # SNOW/ICE WARNINGS - especially critical for bridge clearances
        conditions = (wp.weather.conditions or "").lower()
        temp = wp.weather.temperature or 70
        
        if "snow" in conditions:
            warnings.append(f"❄️ SNOW at {location} - Chain requirements may be in effect; bridges ice before roads")
            
        if temp <= 32:
            warnings.append(f"🧊 Freezing ({temp}°F) at {location} - BLACK ICE RISK on bridges/overpasses; reduce speed to 35 mph")
            
        # VISIBILITY WARNINGS
        if "fog" in conditions:
            warnings.append(f"🌫️ Fog at {location} - Reduced visibility; maintain 10+ second following distance")
        
        if "rain" in conditions and temp <= 40:
            warnings.append(f"🌧️ Cold rain at {location} - Roads may be slick; bridges freeze first")
    
    # Deduplicate similar warnings and limit
    unique_warnings = []
    seen = set()
    for w in warnings:
        key = w.split(" - ")[0][:30]  # Use first 30 chars as key
        if key not in seen:
            unique_warnings.append(w)
            seen.add(key)
            
    return unique_warnings[:15]  # Return top 15 warnings to accommodate bridge data

def calculate_optimal_departure(origin: str, destination: str, waypoints_weather: List[WaypointWeather], base_departure: datetime) -> Optional[DepartureWindow]:
    """Calculate optimal departure window based on weather patterns."""
    # Analyze current conditions
    current_hazards = 0
    current_conditions = []
    
    for wp in waypoints_weather:
        if wp.weather:
            conditions = (wp.weather.conditions or "").lower()
            if any(bad in conditions for bad in ["rain", "storm", "snow", "fog"]):
                current_hazards += 1
                current_conditions.append(wp.weather.conditions)
        current_hazards += len(wp.alerts)
    
    # Calculate current safety score
    safety = calculate_safety_score(waypoints_weather, "car")
    
    # Generate recommendation
    if current_hazards == 0 and safety.overall_score >= 80:
        recommendation = "✅ Current departure time is optimal - clear conditions expected"
        conditions_summary = "Good driving conditions throughout your route"
    elif current_hazards <= 2 and safety.overall_score >= 60:
        recommendation = "👍 Acceptable conditions - drive with caution"
        conditions_summary = f"Some weather: {', '.join(list(set(current_conditions))[:2]) if current_conditions else 'Minor concerns'}"
    else:
        # Suggest waiting
        recommendation = "⏰ Consider departing 2-3 hours later for improved conditions"
        conditions_summary = f"Current concerns: {', '.join(list(set(current_conditions))[:3]) if current_conditions else 'Weather alerts active'}"
    
    # Calculate estimated arrival
    total_duration = waypoints_weather[-1].waypoint.eta_minutes if waypoints_weather else 120
    arrival_time = base_departure + timedelta(minutes=total_duration)
    
    return DepartureWindow(
        departure_time=base_departure.isoformat(),
        arrival_time=arrival_time.isoformat(),
        safety_score=safety.overall_score,
        hazard_count=current_hazards,
        recommendation=recommendation,
        conditions_summary=conditions_summary
    )

def _weather_is_missing(weather: Optional[WeatherData]) -> bool:
    """Return True when provider returned no usable weather data."""
    if not weather:
        return True
    fields = [
        weather.temperature,
        weather.wind_speed,
        weather.conditions,
        weather.icon,
        weather.humidity,
    ]
    return all(v in (None, "", []) for v in fields)


def derive_road_condition(weather: Optional[WeatherData], alerts: List[WeatherAlert]) -> RoadCondition:
    """Derive road surface condition from weather data."""
    if _weather_is_missing(weather):
        return RoadCondition(
            condition="out_of_coverage",
            severity=0,
            label="OUT OF COVERAGE",
            icon="📡",
            color="#6b7280",
            description="No provider coverage for this segment",
            recommendation="Coverage limited here; drive with normal caution"
        )
    
    temp = weather.temperature or 50
    conditions = (weather.conditions or "").lower()
    wind_str = weather.wind_speed or "0 mph"
    
    try:
        wind_speed = int(''.join(filter(str.isdigit, wind_str.split()[0])))
    except:
        wind_speed = 0
    
    # Check for severe alerts first
    severe_alerts = [a for a in alerts if a.severity in ["Extreme", "Severe"]]
    if severe_alerts:
        for alert in severe_alerts:
            event = alert.event.lower()
            if "flood" in event or "flash flood" in event:
                return RoadCondition(
                    condition="flooded",
                    severity=4,
                    label="FLOODING",
                    icon="🌊",
                    color="#dc2626",
                    description=f"Flash flood warning - {alert.headline[:60]}",
                    recommendation="🚫 DO NOT DRIVE - Find alternate route immediately"
                )
            if "ice" in event or "freezing" in event:
                return RoadCondition(
                    condition="icy",
                    severity=3,
                    label="ICY",
                    icon="🧊",
                    color="#ef4444",
                    description=f"Ice storm - {alert.headline[:60]}",
                    recommendation="⚠️ DANGEROUS - Avoid travel if possible"
                )
    
    # Ice conditions (freezing temp + any precipitation)
    if temp <= 32 and any(w in conditions for w in ["rain", "drizzle", "freezing", "sleet", "ice"]):
        return RoadCondition(
            condition="icy",
            severity=3,
            label="ICY ROADS",
            icon="🧊",
            color="#ef4444",
            description=f"Freezing precipitation at {temp}°F",
            recommendation="⚠️ Black ice likely - Reduce speed to 25 mph on bridges"
        )
    
    # Snow covered
    if "snow" in conditions or "blizzard" in conditions:
        severity = 3 if "heavy" in conditions or "blizzard" in conditions else 2
        return RoadCondition(
            condition="snow_covered",
            severity=severity,
            label="SNOW",
            icon="❄️",
            color="#93c5fd",
            description=f"Snow conditions at {temp}°F",
            recommendation="🚗 Reduce speed 50%, increase following distance to 8 seconds"
        )
    
    # Potential ice (just below freezing, roads may have frozen overnight)
    if temp <= 36 and temp > 32:
        return RoadCondition(
            condition="slippery",
            severity=2,
            label="SLIPPERY",
            icon="⚠️",
            color="#f59e0b",
            description=f"Near-freezing {temp}°F - bridges/overpasses may be icy",
            recommendation="⚡ Watch for black ice on elevated surfaces"
        )
    
    # Low visibility
    if "fog" in conditions or "mist" in conditions or "smoke" in conditions:
        return RoadCondition(
            condition="low_visibility",
            severity=2,
            label="LOW VIS",
            icon="🌫️",
            color="#9ca3af",
            description="Fog/reduced visibility",
            recommendation="💡 Low beams only, reduce speed to match visibility"
        )
    
    # Dangerous wind
    if wind_speed > 35:
        return RoadCondition(
            condition="dangerous_wind",
            severity=3,
            label="HIGH WIND",
            icon="💨",
            color="#8b5cf6",
            description=f"Dangerous crosswinds at {wind_speed} mph",
            recommendation="🚛 HIGH-PROFILE VEHICLES: Consider stopping until winds subside"
        )
    
    # Wet roads
    if any(w in conditions for w in ["rain", "shower", "drizzle", "storm", "thunder"]):
        severity = 2 if "heavy" in conditions or "thunder" in conditions else 1
        return RoadCondition(
            condition="wet",
            severity=severity,
            label="WET",
            icon="💧",
            color="#3b82f6",
            description=f"Wet roads - {conditions}",
            recommendation="🌧️ Headlights on, increase following distance to 4 seconds"
        )
    
    # Dry/good conditions
    return RoadCondition(
        condition="dry",
        severity=0,
        label="DRY",
        icon="✓",
        color="#22c55e",
        description=f"Good conditions - {temp}°F, {conditions or 'Clear'}",
        recommendation="✅ Normal driving conditions"
    )

async def get_turn_by_turn_directions(origin_coords: tuple, dest_coords: tuple, waypoints_weather: List[WaypointWeather]) -> List[TurnByTurnStep]:
    """Get turn-by-turn directions with road conditions from Mapbox."""
    steps = []
    if not MAPBOX_ACCESS_TOKEN:
        logger.warning("Turn-by-turn skipped: MAPBOX_ACCESS_TOKEN missing")
        return steps
    if not origin_coords or not dest_coords:
        logger.warning("Turn-by-turn skipped: origin/destination missing")
        return steps

    def normalize_coords(val) -> Optional[tuple]:
        try:
            # dict with lat/lon or lat/lng
            if isinstance(val, dict):
                lat = val.get("lat") or val.get("latitude")
                lon = val.get("lon") or val.get("lng") or val.get("longitude")
                if lat is not None and lon is not None:
                    return float(lat), float(lon)
            # list/tuple [lat, lon]
            if isinstance(val, (list, tuple)) and len(val) >= 2:
                return float(val[0]), float(val[1])
        except Exception:
            return None
        return None

    origin_norm = normalize_coords(origin_coords)
    dest_norm = normalize_coords(dest_coords)
    if not origin_norm or not dest_norm:
        logger.warning("Turn-by-turn skipped: unable to normalize coords", extra={"origin": origin_coords, "dest": dest_coords})
        return steps
    origin_lat, origin_lon = origin_norm
    dest_lat, dest_lon = dest_norm
    
    def _haversine_miles(lat1, lon1, lat2, lon2):
        R = 3958.8
        from math import radians, sin, cos, asin, sqrt
        dlat = radians(lat2 - lat1)
        dlon = radians(lon2 - lon1)
        a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
        return 2 * R * asin(sqrt(a))

    def _build_synthetic_steps(route_geom: Optional[str], total_miles: float, *, interval_miles: float, road_name: str, avg_speed_mph: float) -> List[TurnByTurnStep]:
        if not route_geom or total_miles <= 0:
            return []
        try:
            coords = polyline.decode(route_geom, 6)
        except Exception:
            return []
        if len(coords) < 2:
            return []
        # cumulative distances along polyline
        cum = [0.0]
        for i in range(1, len(coords)):
            miles = _haversine_miles(coords[i-1][0], coords[i-1][1], coords[i][0], coords[i][1])
            cum.append(cum[-1] + miles)
        total_poly_miles = cum[-1] if cum else 0.0
        if total_poly_miles <= 0:
            return []

        targets = []
        d = 0.0
        while d < total_miles:
            targets.append(d)
            d += interval_miles
        targets.append(total_miles)

        synth_steps = []
        for i in range(len(targets)-1):
            start_t = targets[i]
            end_t = targets[i+1]
            segment_miles = max(0.0, end_t - start_t)
            duration_minutes = max(1, int((segment_miles / max(avg_speed_mph, 1e-3)) * 60))
            synth_steps.append(TurnByTurnStep(
                instruction="Continue",
                distance_miles=round(segment_miles, 2),
                duration_minutes=duration_minutes,
                road_name=road_name or "Unnamed road",
                maneuver="straight",
                road_condition=None,
                weather_at_step=None,
                temperature=None,
                has_alert=False,
                start_distance_miles=round(start_t, 2),
                end_distance_miles=round(end_t, 2),
            ))
        return synth_steps

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            coords_str = f"{origin_lon},{origin_lat};{dest_lon},{dest_lat}"
            url = f"https://api.mapbox.com/directions/v5/mapbox/driving/{coords_str}"
            name = (
                tags.get("name")
                or tags.get("brand")
                or tags.get("operator")
                or tags.get("official_name")
                or tags.get("alt_name")
                or tags.get("short_name")
                or tags.get("loc_name")
            )
            if not name:
                city_hint = tags.get("addr:city") or tags.get("addr:place")
                street_hint = tags.get("addr:street")
                base_label = subtype or supply_type
                name_parts = [base_label]
                if city_hint:
                    name_parts.append(city_hint)
                elif street_hint:
                    name_parts.append(street_hint)
                name = " - ".join(name_parts)
                logger.warning("Turn-by-turn Mapbox error code=%s message=%s", api_code, data.get('message'))
                return steps
            if not data.get('routes'):
                logger.warning("Turn-by-turn: no routes returned")
                return steps
            
            route = data['routes'][0]
            legs = route.get('legs', [])
            steps_count = sum(len(leg.get('steps', []) or []) for leg in legs)
            route_distance_m = route.get('distance', 0) or 0
            route_distance_miles = route_distance_m / 1609.344 if route_distance_m else 0.0
            route_duration_s = route.get('duration') or 0.0
            avg_speed_mph = 55.0
            if route_distance_miles > 0 and route_duration_s > 0:
                avg_speed_mph = max(10.0, route_distance_miles / (route_duration_s / 3600))

            primary_road_name = None

            cumulative_distance = 0.0

            for leg in legs:
                for step in leg.get('steps', []):
                    distance_mi = max(0.0, step.get('distance', 0) / 1609.344)  # meters to miles
                    duration_min = step.get('duration', 0) / 60  # seconds to minutes
                    start_distance = max(0.0, cumulative_distance)
                    end_distance = start_distance + distance_mi
                    cumulative_distance = end_distance
                    
                    maneuver = step.get('maneuver', {})
                    instruction = maneuver.get('instruction', 'Continue')
                    maneuver_type = maneuver.get('type', 'straight')
                    
                    # Get road name
                    candidates = [step.get('name'), step.get('ref'), step.get('destinations'), maneuver.get('instruction'), "Unnamed road"]
                    road_name = next((c for c in candidates if c), "Unnamed road")
                    if not primary_road_name and road_name:
                        primary_road_name = road_name
                    
                    # Find nearest waypoint for weather/road condition
                    road_condition = None
                    weather_desc = None
                    temperature = None
                    has_alert = False
                    
                    midpoint_distance = (start_distance + end_distance) / 2
                    for wp in waypoints_weather:
                        if wp.waypoint.distance_from_start is not None and abs(wp.waypoint.distance_from_start - midpoint_distance) < 30:
                            if wp.weather:
                                road_condition = derive_road_condition(wp.weather, wp.alerts)
                                weather_desc = wp.weather.conditions
                                temperature = wp.weather.temperature
                            has_alert = len(wp.alerts) > 0
                            break
                    
                    # Only add significant steps (> 0.1 miles or has maneuver)
                    if distance_mi > 0.1 or maneuver_type not in ['straight', 'new name']:
                        steps.append(TurnByTurnStep(
                            instruction=instruction,
                            distance_miles=round(distance_mi, 1),
                            duration_minutes=round(duration_min),
                            road_name=road_name,
                            maneuver=maneuver_type,
                            road_condition=road_condition,
                            weather_at_step=weather_desc,
                            temperature=temperature,
                            has_alert=has_alert,
                            start_distance_miles=round(start_distance, 2),
                            end_distance_miles=round(end_distance, 2)
                        ))

            synthetic_steps = []
            synthetic_count = 0
            low_resolution = route_distance_m > 50000 and steps_count < MIN_STEPS_FOR_NATIVE
            if low_resolution:
                synthetic_steps = _build_synthetic_steps(
                    route.get('geometry'),
                    route_distance_miles,
                    interval_miles=RESAMPLE_MILES,
                    road_name=primary_road_name or (legs[0].get('summary') if legs else "Route"),
                    avg_speed_mph=avg_speed_mph,
                )
                synthetic_count = len(synthetic_steps)
                if synthetic_steps:
                    steps = synthetic_steps

            logger.info(
                "MAPBOX_TBT steps_count=%s synthetic_steps_count=%s legs=%s route_distance_m=%s low_resolution=%s",
                steps_count,
                synthetic_count,
                len(legs),
                route_distance_m,
                low_resolution,
            )

    except httpx.TimeoutException:
        logger.warning("Turn-by-turn directions timeout")
    except Exception as e:  # noqa: BLE001
        logger.warning("Turn-by-turn directions error", exc_info=e)
    
    return steps  # keep all steps (synthetic already sized)

def analyze_route_conditions(waypoints_weather: List[WaypointWeather]) -> tuple:
    """Analyze all road conditions along route and determine if reroute is needed."""
    all_conditions = []
    worst_severity = 0
    worst_condition = "dry"
    reroute_needed = False
    reroute_reason = None
    coverage_gaps_segments = 0
    coverage_gap_miles = 0.0

    # Precompute distances to estimate gap miles
    distances = [wp.waypoint.distance_from_start for wp in waypoints_weather]

    for idx, wp in enumerate(waypoints_weather):
        road_cond = derive_road_condition(wp.weather, wp.alerts)
        all_conditions.append(road_cond)

        if road_cond.condition == "out_of_coverage":
            coverage_gaps_segments += 1
            # Estimate span to next point to approximate coverage gap mileage
            if idx + 1 < len(waypoints_weather):
                curr = wp.waypoint.distance_from_start or 0.0
                nxt = distances[idx + 1] if distances[idx + 1] is not None else curr
                span = max(0.0, (nxt or curr) - curr)
                coverage_gap_miles += span
        elif road_cond.severity > worst_severity:
            worst_severity = road_cond.severity
            worst_condition = road_cond.condition

        # Check if reroute should be recommended
        if road_cond.severity >= 3:
            reroute_needed = True
            if not reroute_reason:
                location = wp.waypoint.name or f"Mile {int(wp.waypoint.distance_from_start or 0)}"
                reroute_reason = f"{road_cond.label} conditions at {location} - {road_cond.description}"

    # Generate summary
    condition_counts = {}
    for c in all_conditions:
        if c.condition not in {"dry", "out_of_coverage"}:
            condition_counts[c.label] = condition_counts.get(c.label, 0) + 1

    total_segments = len(all_conditions) or 1
    coverage_majority = coverage_gaps_segments > (total_segments / 2)

    if coverage_majority or (coverage_gaps_segments and not condition_counts):
        summary = f"⚠️ Limited hazard coverage: {coverage_gaps_segments} segments out of provider coverage."
    elif not condition_counts:
        summary = "✅ Good road conditions expected throughout your route"
    else:
        summary_parts = [f"{count} segments with {label}" for label, count in condition_counts.items()]
        if coverage_gaps_segments:
            summary_parts.append(f"coverage gaps: {coverage_gaps_segments} segments")
        summary = f"⚠️ Road hazards detected: {', '.join(summary_parts)}"

    return summary, worst_condition, reroute_needed, reroute_reason, coverage_gaps_segments, round(coverage_gap_miles, 1)


def parse_lat_lng(value: Optional[str]) -> Optional[Dict[str, float]]:
    """Parse a coordinate pair from flexible input (lat,lng or space-separated)."""
    if not value:
        return None

    # Try comma split first, otherwise whitespace split
    if "," in value:
        parts = [p.strip() for p in value.split(",") if p.strip()]
    else:
        parts = [p.strip() for p in value.split() if p.strip()]

    # Fallback: extract first two numbers anywhere in the string
    if len(parts) != 2:
        nums = re.findall(r"[-+]?\d*\.?\d+", value)
        if len(nums) < 2:
            return None
        parts = nums[:2]

    try:
        lat_val = float(parts[0])
        lon_val = float(parts[1])
    except Exception:
        return None

    if not (-90 <= lat_val <= 90 and -180 <= lon_val <= 180):
        return None

    return {"lat": lat_val, "lng": lon_val}

async def generate_ai_summary(waypoints_weather: List[WaypointWeather], origin: str, destination: str, packing: List[PackingSuggestion]) -> Optional[str]:
    """Generate AI-powered weather summary using Gemini Flash."""

    weather_info: List[str] = []
    all_alerts: List[str] = []

    for wp in waypoints_weather:
        if wp.weather:
            info = f"- {wp.waypoint.name} ({wp.waypoint.distance_from_start} mi): "
            info += f"{wp.weather.temperature}°{wp.weather.temperature_unit}, "
            info += f"{wp.weather.conditions}, Wind: {wp.weather.wind_speed} {wp.weather.wind_direction}"
            if wp.waypoint.arrival_time:
                info += f" (ETA: {wp.waypoint.arrival_time[:16]})"
            weather_info.append(info)

        for alert in wp.alerts:
            all_alerts.append(f"- {alert.event}: {alert.headline}")

    weather_text = "\n".join(weather_info) if weather_info else "No weather data available"
    alerts_text = "\n".join(set(all_alerts)) if all_alerts else "No active alerts"
    packing_text = ", ".join([p.item for p in packing[:5]]) if packing else "Standard travel items"

    prompt = f"""You are a helpful travel weather assistant. Provide a brief, driver-friendly weather summary for a road trip.

Route: {origin} to {destination}

Weather along route:
{weather_text}

Active Alerts:
{alerts_text}

Suggested packing: {packing_text}

Provide a 2-3 sentence summary focusing on:
1. Overall driving conditions
2. Any weather concerns or hazards
3. Key recommendations for the driver

Be concise and practical."""
    client, model_name = get_gemini_model()
    loop = asyncio.get_event_loop()
    response_obj = await loop.run_in_executor(
        None,
        lambda: client.models.generate_content(model=model_name, contents=prompt),
    )
    return getattr(response_obj, "text", None) or None

# ==================== API Routes ====================

@api_router.get("/")
async def root():
    return {"message": "Routecast API", "version": "2.0", "features": ["departure_time", "multi_stop", "favorites", "packing_suggestions", "weather_timeline"]}

@api_router.get("/health")
async def health_check():
    sha = BUILD_SHA
    branch = os.getenv("RENDER_GIT_BRANCH", "unknown")
    service = os.getenv("RENDER_SERVICE_NAME", "unknown")
    return {
        "ok": True,
        "time": datetime.utcnow().isoformat(),
        "sha": sha,
        "build_time": BUILD_TIME,
        "branch": branch,
        "service": service,
    }

@api_router.post("/route/weather", response_model=RouteWeatherResponse)
async def get_route_weather(request: RouteRequest):
    """Get weather along a route from origin to destination."""
    t0 = time.perf_counter()
    timings: Dict[str, float] = {}

    def mark(name: str):
        timings[name] = round((time.perf_counter() - t0) * 1000.0, 2)

    logger.info("Route weather request received", extra={
        "origin": request.origin,
        "destination": request.destination,
        "stops": len(request.stops or []),
        "vehicle_type": request.vehicle_type,
        "mode": request.mode,
        "trucker_mode": request.trucker_mode,
    })

    payload_flags = {
        "has_waypoints": request.waypoints is not None,
        "has_route_waypoints": bool(getattr(request, "route_waypoints", None)),
        "has_stops": bool(request.stops),
        "has_push_token": bool(request.push_token),
    }
    logger.info("route_weather_payload_keys", extra=payload_flags)

    missing_flags = {
        "origin_present": bool(request.origin),
        "destination_present": bool(request.destination),
        "waypoints_count": len(request.waypoints or []),
    }
    logger.info("route_weather_required_fields", extra=missing_flags)

    route_id = str(uuid.uuid4())

    # Normalize vehicle and routing options
    vehicle_type = request.vehicle_type or "car"
    routing_options = {
        "avoid_highways": request.avoid_highways,
        "avoid_tolls": request.avoid_tolls,
        "prefer_campgrounds": request.prefer_campgrounds,
        "mode": request.mode,
    }
    # Drop unset options so downstream helpers can use clean dicts
    routing_options = {k: v for k, v in routing_options.items() if v is not None}
    
    # Parse departure time
    departure_time = None
    if request.departure_time:
        try:
            departure_time = datetime.fromisoformat(request.departure_time.replace('Z', '+00:00'))
        except:
            departure_time = datetime.now()
    else:
        departure_time = datetime.now()
    
    # Resolve origin and destination (support direct lat,lng) with caching
    origin_coords = parse_lat_lng(request.origin)
    dest_coords = parse_lat_lng(request.destination)

    async def resolve_origin():
        if origin_coords:
            logger.info("Using direct coordinates for origin")
            return origin_coords
        return await cached_geocode(request.origin)

    async def resolve_dest():
        if dest_coords:
            logger.info("Using direct coordinates for destination")
            return dest_coords
        return await cached_geocode(request.destination)

    origin_coords, dest_coords = await asyncio.gather(resolve_origin(), resolve_dest())
    mark("geocode")

    if not origin_coords:
        raise HTTPException(status_code=400, detail=f"Could not geocode origin: {request.origin}")
    if not dest_coords:
        raise HTTPException(status_code=400, detail=f"Could not geocode destination: {request.destination}")
    
    # Geocode stops if any
    stop_coords = []
    if request.stops:
        for stop in request.stops:
            coords = parse_lat_lng(stop.location) or await geocode_location(stop.location)
            if coords:
                stop_coords.append(coords)

    # Incorporate optional raw waypoints/route_waypoints into stop list if provided
    raw_waypoints = list(request.waypoints or [])
    route_waypoints = getattr(request, "route_waypoints", None) or []
    for wp in route_waypoints:
        try:
            lat = getattr(wp, "latitude", None) or getattr(wp, "lat", None)
            lon = getattr(wp, "longitude", None) or getattr(wp, "lon", None)
            if lat is not None and lon is not None:
                raw_waypoints.append({"lat": float(lat), "lng": float(lon)})
        except Exception:
            continue
    for wp in raw_waypoints:
        if not isinstance(wp, dict):
            continue
        lat = wp.get("lat") or wp.get("latitude")
        lon = wp.get("lng") or wp.get("lon") or wp.get("longitude")
        if lat is None or lon is None:
            continue
        try:
            stop_coords.append({"lat": float(lat), "lng": float(lon)})
        except Exception:
            continue
    
    # Get route from Mapbox (cached)
    route_data = await cached_route(origin_coords, dest_coords, stop_coords if stop_coords else None, routing_options or None)
    mark("route_fetch")
    if not route_data:
        detail = f"No drivable route found between {request.origin} and {request.destination}."
        logger.warning("route_weather_no_route", extra={"detail": detail, "route_id": route_id})
        raise HTTPException(status_code=400, detail=detail)
    
    route_geometry = route_data.get('geometry')
    if not route_geometry:
        # Fall back to straight-line polyline between origin/destination
        try:
            o_lat = origin_coords.get("lat")
            o_lon = origin_coords.get("lng") or origin_coords.get("lon") or origin_coords.get("longitude")
            d_lat = dest_coords.get("lat")
            d_lon = dest_coords.get("lng") or dest_coords.get("lon") or dest_coords.get("longitude")
            route_geometry = polyline.encode([(o_lat, o_lon), (d_lat, d_lon)], precision=6)
            logger.warning("route_weather_missing_geometry_fallback", extra={"route_id": route_id})
        except Exception:
            logger.warning("route_weather_missing_geometry_no_fallback", extra={"route_id": route_id})
            route_geometry = ""

    geometry_index = build_geometry_mile_index(route_geometry)

    total_distance_meters = route_data.get('distance') or 0.0
    if not total_distance_meters:
        try:
            o_lat = origin_coords.get("lat")
            o_lon = origin_coords.get("lng") or origin_coords.get("lon") or origin_coords.get("longitude")
            d_lat = dest_coords.get("lat")
            d_lon = dest_coords.get("lng") or dest_coords.get("lon") or dest_coords.get("longitude")
            total_distance_meters = haversine_distance(o_lat, o_lon, d_lat, d_lon) * 1609.344
        except Exception:
            total_distance_meters = 0.0

    total_duration_seconds = int(route_data.get('duration', 0) or 0)
    if total_duration_seconds <= 0 and total_distance_meters > 0:
        total_duration_seconds = int(calculate_eta(total_distance_meters / 1609.344) * 60)
    total_duration_minutes = int(round(total_duration_seconds / 60)) if total_duration_seconds > 0 else int(round(calculate_eta(total_distance_meters / 1609.344)))

    # Build waypoints: prefer provided waypoints, else resample geometry, else synthesize start/end
    dep_time = departure_time or datetime.now()

    def synthesize_start_end() -> List[Waypoint]:
        def _co(coord, key):
            return coord.get(key) or coord.get(key[:3])
        o_lat = _co(origin_coords, "lat")
        o_lon = origin_coords.get("lng") or origin_coords.get("lon") or origin_coords.get("longitude")
        d_lat = _co(dest_coords, "lat")
        d_lon = dest_coords.get("lng") or dest_coords.get("lon") or dest_coords.get("longitude")
        distance = haversine_distance(o_lat, o_lon, d_lat, d_lon) if None not in (o_lat, o_lon, d_lat, d_lon) else 0.0
        eta_mins = calculate_eta(distance)
        arrival = dep_time + timedelta(minutes=eta_mins)
        return [
            Waypoint(lat=o_lat or 0.0, lon=o_lon or 0.0, name="Start", distance_from_start=0.0, eta_minutes=0, arrival_time=dep_time.isoformat()),
            Waypoint(lat=d_lat or 0.0, lon=d_lon or 0.0, name="Destination", distance_from_start=round(distance, 1), eta_minutes=eta_mins, arrival_time=arrival.isoformat()),
        ]

    if raw_waypoints:
        waypoints = []
        coords_chain = []
        o_lat = origin_coords.get("lat")
        o_lon = origin_coords.get("lng") or origin_coords.get("lon") or origin_coords.get("longitude")
        d_lat = dest_coords.get("lat")
        d_lon = dest_coords.get("lng") or dest_coords.get("lon") or dest_coords.get("longitude")
        coords_chain.append((o_lat, o_lon, "Start"))
        for idx, wp in enumerate(raw_waypoints, start=1):
            try:
                lat = wp.get("lat") or wp.get("latitude")
                lon = wp.get("lng") or wp.get("lon") or wp.get("longitude")
                if lat is None or lon is None:
                    continue
                coords_chain.append((float(lat), float(lon), wp.get("name") or f"Point {idx}"))
            except Exception:
                continue
        coords_chain.append((d_lat, d_lon, "Destination"))

        cumulative = 0.0
        last_lat, last_lon, last_name = coords_chain[0]
        waypoints.append(Waypoint(lat=last_lat or 0.0, lon=last_lon or 0.0, name=last_name, distance_from_start=0.0, eta_minutes=0, arrival_time=dep_time.isoformat()))
        for lat, lon, name in coords_chain[1:]:
            seg = haversine_distance(last_lat, last_lon, lat, lon) if None not in (last_lat, last_lon, lat, lon) else 0.0
            cumulative += seg
            eta_mins = calculate_eta(cumulative)
            arrival = dep_time + timedelta(minutes=eta_mins)
            waypoints.append(Waypoint(lat=lat or 0.0, lon=lon or 0.0, name=name, distance_from_start=round(cumulative, 1), eta_minutes=eta_mins, arrival_time=arrival.isoformat()))
            last_lat, last_lon = lat, lon
    else:
        waypoints = extract_waypoints_from_route(route_geometry, interval_miles=RESAMPLE_MILES, departure_time=departure_time)
        if not waypoints:
            logger.warning("Route waypoints empty, falling back to origin/destination only", extra={"route_id": route_id})
            waypoints = synthesize_start_end()
    
    # Get weather for each waypoint (with concurrent requests)
    waypoints_weather = []
    has_severe = False
    
    async def fetch_waypoint_weather(wp: Waypoint, index: int, total: int, origin_name: str, dest_name: str) -> WaypointWeather:
        nonlocal has_severe
        weather = await get_noaa_weather(wp.lat, wp.lon)
        alerts = await get_noaa_alerts(wp.lat, wp.lon)
        
        # Get location name via reverse geocoding
        location_name = await reverse_geocode(wp.lat, wp.lon)
        
        # Build display name with point number and location
        if index == 0:
            display_name = f"Start - {origin_name}"
        elif index == total - 1:
            display_name = f"End - {dest_name}"
        else:
            point_label = f"Point {index}"
            if location_name:
                display_name = f"{point_label} - {location_name}"
            else:
                display_name = point_label
        
        # Update waypoint with location name
        updated_wp = Waypoint(
            lat=wp.lat,
            lon=wp.lon,
            name=display_name,
            distance_from_start=wp.distance_from_start,
            eta_minutes=wp.eta_minutes,
            arrival_time=wp.arrival_time
        )
        
        # Check for severe weather
        severe_severities = ['Extreme', 'Severe']
        if any(a.severity in severe_severities for a in alerts):
            has_severe = True
        
        return WaypointWeather(
            waypoint=updated_wp,
            weather=weather,
            alerts=alerts
        )
    
    # Fetch weather concurrently (alerts deferred to follow-up)
    total_waypoints = len(waypoints)

    async def fetch_weather_only(wp: Waypoint, index: int, total: int, origin_name: str, dest_name: str) -> WaypointWeather:
        weather = await get_noaa_weather(wp.lat, wp.lon)
        location_name = await reverse_geocode(wp.lat, wp.lon)
        if index == 0:
            display_name = f"Start - {origin_name}"
        elif index == total - 1:
            display_name = f"End - {dest_name}"
        else:
            display_name = location_name or wp.name

        updated_wp = Waypoint(
            lat=wp.lat,
            lon=wp.lon,
            name=display_name,
            distance_from_start=wp.distance_from_start,
            eta_minutes=wp.eta_minutes,
            arrival_time=wp.arrival_time,
        )

        return WaypointWeather(
            waypoint=updated_wp,
            weather=weather,
            alerts=[],
        )

    tasks = [fetch_weather_only(wp, i, total_waypoints, request.origin, request.destination) for i, wp in enumerate(waypoints)]
    waypoints_weather = await asyncio.gather(*tasks)
    mark("weather_fetch")

    hazard_waypoints = extract_waypoints_from_route(route_geometry, interval_miles=10.0, departure_time=departure_time)
    if not hazard_waypoints:
        hazard_waypoints = list(waypoints)

    # Persist active route monitor for alerts if push token provided and DB available
    if request.push_token:
        try:
            route_points = [
                {
                    "lat": wp.lat,
                    "lon": wp.lon,
                    "name": wp.name,
                    "distance_from_start": wp.distance_from_start,
                    "eta_minutes": wp.eta_minutes,
                    "arrival_time": wp.arrival_time,
                }
                for wp in waypoints
                if wp.lat is not None and wp.lon is not None
            ]

            if not route_points:
                logger.warning("[route-weather] route monitor skipped: missing route points for token=%s", request.push_token[:16])
            else:
                sample_miles = float(os.environ.get("ROUTE_ALERTS_SAMPLING_MILES", 10.0))
                max_points = int(os.environ.get("ROUTE_ALERTS_MAX_POINTS", 25))
                sample_points = sample_route_points(route_points, sample_miles=sample_miles, max_points=max_points)
                bbox = _compute_bbox(route_points)

                # Use shared alert service to ensure only one active monitor per user/token
                service = get_route_alert_service()
                service.start_monitor(
                    user_id=request.push_token,
                    push_token=request.push_token,
                    route_id=route_id,
                    route_points=route_points,
                    sample_points=sample_points,
                    route_polyline=route_geometry,
                    bbox=bbox,
                    sample_miles=sample_miles,
                    max_points=max_points,
                )
        except HTTPException:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.warning("[route-weather] failed to persist route monitor: %s", exc)
    
    # Generate packing suggestions
    packing_suggestions = generate_packing_suggestions(list(waypoints_weather))
    
    # Build weather timeline
    weather_timeline = build_weather_timeline(list(waypoints_weather))
    
    # Generate AI summary when Gemini is available/configured; degrade gracefully otherwise
    ai_summary = None
    if CHAT_AVAILABLE and os.getenv("GEMINI_API_KEY"):
        try:
            ai_summary = await generate_ai_summary(list(waypoints_weather), request.origin, request.destination, packing_suggestions)
        except Exception as e:
            logger.warning("AI summary skipped: %s", e)
    else:
        logger.info("AI summary disabled; Gemini not configured")
    
    # NEW: Calculate safety score based on vehicle type
    safety_score = calculate_safety_score(list(waypoints_weather), vehicle_type)

    # NEW: Get turn-by-turn directions with road conditions (used for hazard enrichment)
    turn_by_turn = await get_turn_by_turn_directions(origin_coords, dest_coords, list(waypoints_weather))
    turn_by_turn = turn_by_turn or []

    total_distance = compute_total_distance_miles(route_data, turn_by_turn, list(waypoints_weather))

    if not turn_by_turn:
        logger.info(
            "turn_by_turn empty; using route distance fallback total_distance_miles=%s",
            total_distance,
            extra={"route_id": route_id},
        )

    # Hazard alerts deferred to follow-up endpoint to avoid blocking
    hazard_alerts: List[HazardAlert] = []
    road_conditions: List[ConditionSegment] = []
    weather_conditions: List[ConditionSegment] = []

    # Cache context for single follow-up hazard fetch
    cache_route_context(route_id, {
        "hazard_waypoints": [wp.model_dump() for wp in hazard_waypoints],
        "departure_time": departure_time.isoformat(),
        "total_distance_miles": total_distance,
        "total_duration_minutes": total_duration_minutes,
        "route_geometry": route_geometry,
        "origin": request.origin,
        "destination": request.destination,
    })
    mark("context_cached")

    # NEW: Find rest stops along the route
    rest_stops = await find_rest_stops(route_geometry, list(waypoints_weather))
    
    # NEW: Calculate optimal departure window
    optimal_departure = calculate_optimal_departure(request.origin, request.destination, list(waypoints_weather), departure_time)
    
    # NEW: Generate trucker-specific warnings
    # Bridge alerts are ALWAYS available (safety feature), trucker mode adds wind/weather warnings
    trucker_warnings = []
    if request.trucker_mode or request.vehicle_height_ft:
        trucker_warnings = generate_trucker_warnings(list(waypoints_weather), request.vehicle_height_ft)
    
    # NEW: Analyze road conditions
    road_condition_summary, worst_road_condition, reroute_recommended, reroute_reason, coverage_gaps_segments, coverage_gap_miles = analyze_route_conditions(list(waypoints_weather))
    
    response = RouteWeatherResponse(
        id=route_id,
        origin=request.origin,
        destination=request.destination,
        stops=request.stops or [],
        departure_time=departure_time.isoformat(),
        total_duration_minutes=total_duration_minutes,
        total_distance_miles=round(total_distance, 1),
        route_geometry=route_geometry,
        waypoints=list(waypoints_weather),
        ai_summary=ai_summary,
        has_severe_weather=has_severe,
        packing_suggestions=packing_suggestions,
        weather_timeline=weather_timeline,
        # New fields
        safety_score=safety_score,
        hazard_alerts=hazard_alerts,
        road_conditions=road_conditions,
        weather_conditions=weather_conditions,
        rest_stops=rest_stops,
        optimal_departure=optimal_departure,
        trucker_warnings=trucker_warnings,
        vehicle_type=vehicle_type,
        # Road conditions and navigation
        turn_by_turn=turn_by_turn,
        road_condition_summary=road_condition_summary,
        worst_road_condition=worst_road_condition,
        reroute_recommended=reroute_recommended,
        reroute_reason=reroute_reason,
        coverage_gaps_segments=coverage_gaps_segments,
        coverage_gaps_miles=coverage_gap_miles,
        hazard_status="pending",
        timings_ms=timings if TIMING_DEBUG else None,
    )
    
    mark("total")
    if TIMING_DEBUG:
        logger.info("route_weather_timings", extra={"route_id": route_id, "timings_ms": timings})

    # Save to database when configured
    try:
        if db is None:
            logger.warning("DB not initialized; skipping route save")
        else:
            route_doc = response.model_dump()
            # Ensure created_at is serializable
            if 'created_at' in route_doc and isinstance(route_doc['created_at'], datetime):
                route_doc['created_at'] = route_doc['created_at']
            await db.routes.insert_one(route_doc)
            logger.info(f"Saved route {response.id} to database")
            logger.info(f"route_id_available_for_alerts route_id={route_id}")
    except Exception as e:
        logger.error(f"Error saving route: {e}", exc_info=True)
    
    return response


@api_router.get("/route/weather/alerts/{route_id}", response_model=HazardAlertsResponse)
async def get_route_weather_alerts(route_id: str):
    """Compute hazard/NWS alerts in a single follow-up call using cached context."""
    logger.info("route_alerts_request", extra={"route_id": route_id})
    ctx = get_route_context(route_id)
    if not ctx:
        logger.warning("route_alerts_context_missing", extra={"route_id": route_id})
        return HazardAlertsResponse(
            route_id=route_id,
            hazard_alerts=[],
            alerts=[],
            road_conditions=[],
            weather_conditions=[],
            hazard_status="error",
            status="error",
            error="Route context expired or missing",
        )

    t0 = time.perf_counter()
    timings: Dict[str, float] = {}

    def mark(name: str):
        timings[name] = round((time.perf_counter() - t0) * 1000.0, 2)

    hazard_waypoints_data = ctx.get("hazard_waypoints", [])
    if not hazard_waypoints_data:
        logger.warning("route_alerts_missing_waypoints", extra={"route_id": route_id})
        return HazardAlertsResponse(
            route_id=route_id,
            hazard_alerts=[],
            alerts=[],
            road_conditions=[],
            weather_conditions=[],
            hazard_status="error",
            status="error",
            error="No hazard waypoints available",
        )

    try:
        departure_time = datetime.fromisoformat(ctx.get("departure_time"))
    except Exception:
        departure_time = datetime.utcnow()

    total_distance = ctx.get("total_distance_miles", 0.0)
    total_duration_minutes = ctx.get("total_duration_minutes", 0)
    route_geometry = ctx.get("route_geometry", "")
    geometry_index = build_geometry_mile_index(route_geometry) if route_geometry else {}

    max_alert_points = 6

    def downsample_waypoints(data: List[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
        if len(data) <= limit:
            return data
        if limit <= 1:
            return [data[0]]
        step = (len(data) - 1) / float(limit - 1)
        indices = sorted({round(step * i) for i in range(limit)})
        return [data[i] for i in indices if 0 <= i < len(data)]

    hazard_waypoints_data = downsample_waypoints(hazard_waypoints_data, max_alert_points)
    hazard_total_waypoints = len(hazard_waypoints_data)

    is_alaska_route = any(
        (wp.get("lat") is not None and wp.get("lon") is not None and wp.get("lat") >= 50 and wp.get("lon") <= -130)
        for wp in hazard_waypoints_data
    )

    alaska_alerts_cache: Optional[List[WeatherAlert]] = None
    if is_alaska_route and hazard_waypoints_data:
        first_wp = hazard_waypoints_data[0]
        alaska_alerts_cache = await get_noaa_alerts(first_wp.get("lat"), first_wp.get("lon"))

    async def fetch_hazard_wp(wp_dict: Dict[str, Any], index: int, total: int) -> WaypointWeather:
        wp = Waypoint(**wp_dict)
        weather = await get_noaa_weather(wp.lat, wp.lon)
        alerts = alaska_alerts_cache if alaska_alerts_cache is not None else await get_noaa_alerts(wp.lat, wp.lon)
        return WaypointWeather(waypoint=wp, weather=weather, alerts=alerts)

    try:
        logger.info(
            "route_alerts_fetch_start",
            extra={"route_id": route_id, "waypoints": hazard_total_waypoints},
        )
        hazard_tasks = [fetch_hazard_wp(wp, i, hazard_total_waypoints) for i, wp in enumerate(hazard_waypoints_data)]
        hazard_waypoints_weather = await asyncio.gather(*hazard_tasks)
        mark("alerts_fetch")

        hazard_alerts = generate_hazard_alerts(
            list(hazard_waypoints_weather),
            departure_time,
            total_route_miles=total_distance,
            total_route_minutes=total_duration_minutes,
            route_id=route_id,
        )

        deduped_alerts: List[HazardAlert] = []
        seen_ids = set()
        for alert in hazard_alerts:
            alert_id = getattr(alert, "id", None) or getattr(alert, "alert_id", None)
            if alert_id:
                if alert_id in seen_ids:
                    continue
                seen_ids.add(alert_id)
            deduped_alerts.append(alert)
        hazard_alerts = deduped_alerts

        await hydrate_alert_roads_from_geometry(hazard_alerts, geometry_index)
        road_conditions = build_condition_segments(hazard_alerts, category="road")
        weather_conditions = build_condition_segments(hazard_alerts, category="weather")
        mark("hazard_build")

        status_value = "ready"

        logger.info(
            "route_alerts_ready",
            extra={
                "route_id": route_id,
                "alerts_count": len(hazard_alerts),
                "nws_requests": hazard_total_waypoints,
                "ms_fetch": timings.get("alerts_fetch"),
                "ms_total": timings.get("hazard_build"),
            },
        )

        if TIMING_DEBUG:
            logger.info(
                "route_weather_alerts_timings",
                extra={"route_id": route_id, "timings_ms": timings},
            )

        return HazardAlertsResponse(
            route_id=route_id,
            hazard_alerts=hazard_alerts,
            alerts=hazard_alerts,
            road_conditions=road_conditions,
            weather_conditions=weather_conditions,
            hazard_status=status_value,
            status=status_value,
            timings_ms=timings if TIMING_DEBUG else None,
        )
    except Exception as exc:
        logger.error("route_alerts_fetch_failed", exc_info=True, extra={"route_id": route_id})
        return HazardAlertsResponse(
            route_id=route_id,
            hazard_alerts=[],
            alerts=[],
            road_conditions=[],
            weather_conditions=[],
            hazard_status="error",
            status="error",
            error=str(exc),
            timings_ms=timings if TIMING_DEBUG else None,
        )


@api_router.get("/routes/history", response_model=List[SavedRoute])
async def get_route_history():
    """Get recent route history."""
    if db is None:
        logger.warning("Database not available for route history")
        return []
    try:
        routes = await db.routes.find().sort("created_at", -1).limit(10).to_list(10)
        logger.info("Route history fetched: count=%s", len(routes))
        return [SavedRoute(
            id=str(r.get('_id', r.get('id'))),
            origin=r['origin'],
            destination=r['destination'],
            stops=r.get('stops', []),
            is_favorite=r.get('is_favorite', False),
            created_at=r.get('created_at', datetime.utcnow())
        ) for r in routes]
    except Exception as e:
        logger.error(f"Error fetching route history: {e}")
        return []

@api_router.get("/routes/favorites", response_model=List[SavedRoute])
async def get_favorite_routes():
    """Get favorite routes."""
    if db is None:
        logger.warning("Database not available for favorites")
        return []
    try:
        routes = await db.favorites.find().sort("created_at", -1).limit(20).to_list(20)
        logger.info("Favorites fetched: count=%s", len(routes))
        return [SavedRoute(
            id=r.get('id', str(r.get('_id'))),
            origin=r['origin'],
            destination=r['destination'],
            stops=r.get('stops', []),
            is_favorite=True,
            created_at=r.get('created_at', datetime.utcnow())
        ) for r in routes]
    except Exception as e:
        logger.error(f"Error fetching favorites: {e}")
        return []

@api_router.post("/routes/favorites")
async def add_favorite_route(request: FavoriteRouteRequest):
    """Add a route to favorites."""
    if db is None:
        logger.warning("Database not available for favorites")
        raise HTTPException(status_code=503, detail="Database not available. Favorites require database connection.")
    try:
        favorite = {
            "id": str(uuid.uuid4()),
            "origin": request.origin,
            "destination": request.destination,
            "stops": [s.model_dump() for s in (request.stops or [])],
            "name": request.name or f"{request.origin} to {request.destination}",
            "is_favorite": True,
            "created_at": datetime.utcnow()
        }
        await db.favorites.insert_one(favorite)
        logger.info("Favorite saved id=%s origin=%s destination=%s stops=%s", favorite["id"], favorite["origin"], favorite["destination"], len(favorite.get("stops", [])))
        return {"success": True, "id": favorite["id"]}
    except Exception as e:
        logger.error(f"Error saving favorite: {e}")
        raise HTTPException(status_code=500, detail="Could not save favorite")

@api_router.delete("/routes/favorites/{route_id}")
async def remove_favorite_route(route_id: str):
    """Remove a route from favorites."""
    if db is None:
        logger.warning("Database not available for favorites")
        raise HTTPException(status_code=503, detail="Database not available. Favorites require database connection.")
    try:
        from bson import ObjectId
        # Try custom id field first
        result = await db.favorites.delete_one({"id": route_id})
        if result.deleted_count == 0:
            # Try with MongoDB ObjectId
            try:
                result = await db.favorites.delete_one({"_id": ObjectId(route_id)})
            except:
                pass
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Favorite not found")
        logger.info("Favorite removed id=%s deleted=%s", route_id, result.deleted_count)
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing favorite: {e}")
        raise HTTPException(status_code=500, detail="Could not remove favorite")

@api_router.get("/routes/{route_id}", response_model=RouteWeatherResponse)
async def get_route_by_id(route_id: str):
    """Get a specific route by ID."""
    if db is None:
        logger.warning("Database not available for route lookup")
        raise HTTPException(status_code=503, detail="Database not available")
    try:
        route = await db.routes.find_one({"id": route_id})
        if not route:
            raise HTTPException(status_code=404, detail="Route not found")
        return RouteWeatherResponse(**route)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching route {route_id}: {e}")
        raise HTTPException(status_code=500, detail="Error fetching route")

# Geocode endpoints under dedicated router
@geocode_router.post("")
async def geocode(location: str):
    """Geocode a location string."""
    require_mapbox_token()
    coords = await geocode_location(location)
    if not coords:
        raise HTTPException(status_code=404, detail="Location not found")
    return coords

@geocode_router.get("/autocomplete")
async def autocomplete_location(query: str, limit: int = 5):
    """Get autocomplete suggestions for a location query using Mapbox."""
    if not query or len(query) < 2:
        return []

    require_mapbox_token()
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            url = f"https://api.mapbox.com/geocoding/v5/mapbox.places/{query}.json"
            params = {
                'access_token': MAPBOX_ACCESS_TOKEN,
                'autocomplete': 'true',
                'types': 'place,locality,address,poi',
                'country': 'US,PR,VI,GU,AS',  # US + Puerto Rico + Virgin Islands + Guam + American Samoa
                'limit': limit
            }
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            suggestions = []
            for feature in data.get('features', []):
                place_name = feature.get('place_name', '')
                text = feature.get('text', '')
                
                # Extract components
                context = feature.get('context', [])
                region = ''
                for ctx in context:
                    if ctx.get('id', '').startswith('region'):
                        region = ctx.get('short_code', '').replace('US-', '').replace('PR-', 'PR').replace('VI-', 'VI')
                        break
                
                suggestions.append({
                    'place_name': place_name,
                    'short_name': f"{text}, {region}" if region else text,
                    'coordinates': feature.get('center', []),
                })
            
            return suggestions
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Autocomplete error for '{query}': {e}")
        raise HTTPException(status_code=500, detail="Autocomplete failed")

# ==================== Billing ====================

class BillingVerifyRequest(BaseModel):
    platform: str  # "android" or "ios"
    product_id: str  # "boondocking_pro_monthly" or "boondocking_pro_yearly"
    purchase_token: str


@api_router.post("/billing/verify", response_model=dict)
async def verify_purchase(request: BillingVerifyRequest):
    """
    Verify a purchase token with Google Play or App Store.
    
    Returns entitlement status including expiration date.
    STUB IMPLEMENTATION - returns mock responses for development.
    """
    try:
        logger.info(f"[BILLING] Verifying purchase: platform={request.platform}, product={request.product_id}")
        
        verification_request = VerificationRequest(
            platform=request.platform,
            product_id=request.product_id,
            purchase_token=request.purchase_token,
        )
        
        result = await billing_verifier.verify_purchase(verification_request)
        
        return {
            "isPro": result.is_pro,
            "productId": result.product_id,
            "expireAt": result.expire_at,
            "error": result.error,
        }
    except Exception as e:
        logger.error(f"[BILLING] Verification error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Subscription/Billing Endpoints ====================

@api_router.post("/billing/validate-subscription", response_model=SubscriptionResponse)
async def validate_subscription(request: SubscriptionRequest):
    """
    Validate a subscription ID (stubbed for Google Play Billing integration).
    
    Currently returns success for all valid subscription IDs.
    In production, this would validate against Google Play API.
    
    Logging: Premium feature access tracked here
    """
    logger.info(f"[PREMIUM] Validating subscription: {request.subscription_id}")
    
    try:
        # TODO: Integrate with Google Play Billing API
        # For now, accept test subscription IDs
        test_subscriptions = [
            'routecast_pro_monthly',
            'routecast_pro_annual',
            'test_subscription',
        ]
        
        is_valid = request.subscription_id in test_subscriptions
        
        if is_valid:
            logger.info(f"[PREMIUM] Subscription validated: {request.subscription_id}")
            
            # Save subscription to database
            await db.subscriptions.update_one(
                {'subscription_id': request.subscription_id},
                {
                    '$set': {
                        'subscription_id': request.subscription_id,
                        'status': 'active',
                        'created_at': datetime.utcnow(),
                        'last_validated': datetime.utcnow(),
                    }
                },
                upsert=True
            )
        
        return SubscriptionResponse(
            is_valid=is_valid,
            subscription_id=request.subscription_id,
            message='Subscription validated' if is_valid else 'Invalid subscription'
        )
    except Exception as e:
        logger.error(f"[BILLING] Error validating subscription: {e}")
        # Graceful fallback - don't hard block
        return SubscriptionResponse(
            is_valid=False,
            subscription_id=request.subscription_id,
            message='Unable to validate subscription at this time'
        )

@api_router.get("/billing/features")
async def get_feature_gating_info():
    """
    Get information about which features are free vs. premium.
    
    Used by frontend to show accurate "Upgrade to unlock" messaging.
    """
    logger.info("[PREMIUM] Feature gating info requested")
    
    return {
        'free_features': [
            'weather_warnings',
            'road_surface_warnings',
            'bridge_height_alerts',
            'live_radar',
            'time_departure_changes',
            'basic_ai_chat',
            'major_weather_alerts',
            'google_maps',
            'recent_favorites',
            'basic_push_alerts',
        ],
        'premium_features': [
            'future_weather_forecast',
            'radar_playback_history',
            'advanced_push_alerts',
            'predictive_storm_alerts',
        ],
        'tiers': [
            {
                'id': 'routecast_pro_monthly',
                'name': 'Routecast Pro',
                'price': 4.99,
                'billing_period': 'monthly',
                'currency': 'USD',
            },
            {
                'id': 'routecast_pro_annual',
                'name': 'Routecast Pro',
                'price': 29.99,
                'billing_period': 'annual',
                'currency': 'USD',
                'savings': '40%',
            },
        ]
    }

# ==================== Feature Endpoints ====================

@api_router.post("/road-passability", response_model=RoadPassabilityResponse)
async def assess_road_passability(request: RoadPassabilityRequest):
    """
    Assess road passability and conditions along a route segment.
    """
    logger.info("[road-passability] assessment requested")

    # Call pure domain service
    try:
        result = RoadPassabilityService.assess_road_passability(
            precip_72h=request.precip_72h,
            slope_pct=request.slope_pct,
            min_temp_f=request.min_temp_f,
            soil_type=request.soil_type,
        )
        
        # Convert domain result to API response
        return RoadPassabilityResponse(
            passability_score=result.passability_score,
            condition_assessment=result.condition_assessment,
            advisory=result.advisory,
            min_clearance_cm=result.min_clearance_cm,
            recommended_vehicle_type=result.recommended_vehicle_type,
            needs_four_x_four=result.risks.four_x_four_recommended,
            risks={
                'mud_risk': result.risks.mud_risk,
                'ice_risk': result.risks.ice_risk,
                'deep_rut_risk': result.risks.deep_rut_risk,
                'high_clearance_recommended': result.risks.high_clearance_recommended,
                'four_x_four_recommended': result.risks.four_x_four_recommended,
            },
            is_premium_locked=False,
        )
    except ValueError as e:
        logger.error(f"[road-passability] Invalid parameters: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Invalid parameters: {str(e)}"
        )
    except Exception as e:
        logger.error(f"[road-passability] Error assessing road passability: {e}")
        raise HTTPException(
            status_code=500,
            detail="Unable to assess road passability at this time"
        )

@api_router.post("/solar-forecast", response_model=SolarForecastResponse)
async def forecast_solar_energy(request: SolarForecastRequest):
    """
    Forecast daily solar energy generation for a boondocking location.
    
    PREMIUM FEATURE - Requires active subscription.
    
    Args:
        lat: Latitude (-90 to 90)
        lon: Longitude (-180 to 180)
        date_range: List of ISO format dates
        panel_watts: Solar panel capacity in watts (>0)
        shade_pct: Average shade percentage (0-100)
        cloud_cover: List of cloud cover percentages (0-100) per date
        subscription_id: Optional subscription ID for premium access validation
    
    Returns a daily Wh/day list with advisory.
    """
    logger.info("[solar-forecast] forecast requested")

    # Call pure domain service
    try:
        result = SolarForecastService.forecast_daily_wh(
            lat=request.lat,
            lon=request.lon,
            date_range=request.date_range,
            panel_watts=request.panel_watts,
            shade_pct=request.shade_pct,
            cloud_cover=request.cloud_cover,
        )

        logger.info("[solar-forecast] forecast completed")

        # Convert domain result to API response
        return SolarForecastResponse(
            daily_wh=result.daily_wh,
            dates=result.dates,
            panel_watts=result.panel_watts,
            shade_pct=result.shade_pct,
            advisory=result.advisory,
            is_premium_locked=False,
        )
    except ValueError as e:
        logger.error(f"[solar-forecast] Invalid parameters: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Invalid parameters: {str(e)}"
        )
    except Exception as e:
        logger.error(f"[solar-forecast] Error forecasting solar energy: {e}")
        raise HTTPException(
            status_code=500,
            detail="Unable to forecast solar energy at this time"
        )

@api_router.post("/propane-usage", response_model=PropaneUsageResponse)
async def estimate_propane_usage(request: PropaneUsageRequest):
    """
    Estimate daily propane consumption for RV boondocking.
    
    """
    logger.info("[propane-usage] estimate requested")

    # Call pure domain service
    try:
        daily_lbs = PropaneUsageService.estimate_lbs_per_day(
            furnace_btu=request.furnace_btu,
            duty_cycle_pct=request.duty_cycle_pct,
            nights_temp_f=request.nights_temp_f,
            people=request.people,
        )
        
        # Generate advisory text
        advisory = PropaneUsageService.format_advisory(
            furnace_btu=request.furnace_btu,
            duty_cycle_pct=request.duty_cycle_pct,
            nights_temp_f=request.nights_temp_f,
            people=request.people,
            daily_lbs=daily_lbs,
        )

        logger.info("[propane-usage] estimate completed")

        # Convert domain result to API response
        return PropaneUsageResponse(
            daily_lbs=daily_lbs,
            nights_temp_f=request.nights_temp_f,
            furnace_btu=request.furnace_btu,
            duty_cycle_pct=request.duty_cycle_pct,
            people=request.people,
            advisory=advisory,
            is_premium_locked=False,
        )
    except ValueError as e:
        logger.error(f"[propane-usage] Invalid parameters: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Invalid parameters: {str(e)}"
        )
    except Exception as e:
        logger.error(f"[propane-usage] Error estimating propane usage: {e}")
        raise HTTPException(
            status_code=500,
            detail="Unable to estimate propane usage at this time"
        )

@api_router.post("/water-budget", response_model=WaterBudgetResponse)
async def estimate_water_budget(request: WaterBudgetRequest):
    """
    Estimate days remaining before water tanks run out during boondocking.
    
    PREMIUM FEATURE - Requires active subscription.
    
    Water usage model:
    - Fresh water: 2 gal/person/day for drinking & cooking
    - Gray water: 2 gal/person/day for sinks + shower water (33 gal/shower)
    - Black water: 1 gal/person/day for toilet + hand wash
    - Temperature adjustment: 1.2x usage in hot weather, 0.85x in cool weather
    - Days remaining: min(fresh_days, gray_days, black_days) - limited by first tank
    
    Args:
        fresh_gal: Fresh water tank capacity in gallons
        gray_gal: Gray water tank capacity in gallons
        black_gal: Black water tank capacity in gallons
        people: Number of people in RV (default: 2)
        showers_per_week: Showers per week (default: 2)
        hot_days: Whether it's hot weather (affects water usage)
        subscription_id: Optional subscription ID for premium access validation
    
    Returns:
        - If premium locked: paywall message
        - If authorized: days_remaining with limiting_factor and daily usage breakdown
    
    Logging: All premium feature access logged with [PREMIUM] prefix
    """
    logger.info(f"[PREMIUM] Water budget estimate requested")
    
    # Check premium entitlement (no database check for testing)
    # TESTING: Paywalls disabled - require_premium(request.subscription_id, WATER_BUDGET)
    
    # Call pure domain service
    try:
        result = WaterBudgetService.days_remaining_with_breakdown(
            fresh_gal=request.fresh_gal,
            gray_gal=request.gray_gal,
            black_gal=request.black_gal,
            people=request.people,
            showers_per_week=request.showers_per_week,
            hot_days=request.hot_days,
        )
        
        logger.info(f"[PREMIUM] Water budget estimate completed successfully")
        
        # Convert domain result to API response
        return WaterBudgetResponse(
            days_remaining=result.days_remaining,
            limiting_factor=result.limiting_factor,
            daily_fresh_gal=result.daily_fresh_gal,
            daily_gray_gal=result.daily_gray_gal,
            daily_black_gal=result.daily_black_gal,
            advisory=result.advisory,
            is_premium_locked=False,
        )
    except ValueError as e:
        logger.error(f"[PREMIUM] Invalid parameters for water budget: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Invalid parameters: {str(e)}"
        )
    except Exception as e:
        logger.error(f"[PREMIUM] Unexpected error estimating water budget: {e}")
        raise HTTPException(
            status_code=500,
            detail="Unable to estimate water budget at this time"
        )

# ==================== Terrain Shade Endpoints ====================

@api_router.post("/terrain/sun-path", response_model=TerrainShadeResponse)
async def estimate_solar_path(request: TerrainShadeRequest):
    """Calculate hourly solar elevation path for boondocking location."""
    try:
        from datetime import datetime as dt
        date_obj = dt.fromisoformat(request.date).date()
        slots = TerrainShadeService.sun_path(request.latitude, request.longitude, date_obj)
        shade_factor = TerrainShadeService.shade_blocks(
            request.tree_canopy_pct,
            request.horizon_obstruction_deg
        )
        exposure_hours = TerrainShadeService.sun_exposure_hours(
            request.latitude,
            request.longitude,
            date_obj,
            request.tree_canopy_pct,
            request.horizon_obstruction_deg
        )
        response_slots = [
            SunPathSlotResponse(
                hour=slot.hour,
                sun_elevation_deg=slot.sun_elevation_deg,
                usable_sunlight_fraction=slot.usable_sunlight_fraction,
                time_label=slot.time_label
            )
            for slot in slots
        ]
        return TerrainShadeResponse(
            sun_path_slots=response_slots,
            shade_factor=round(shade_factor, 3),
            exposure_hours=round(exposure_hours, 1),
            is_premium_locked=False,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid parameters: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail="Unable to calculate solar path at this time"
        )

@api_router.post("/terrain/shade-blocks", response_model=TerrainShadeResponse)
async def estimate_shade_blocking(request: TerrainShadeRequest):
    """Calculate shade blocking factor from trees and horizon obstruction."""
    try:
        shade_factor = TerrainShadeService.shade_blocks(
            request.tree_canopy_pct,
            request.horizon_obstruction_deg
        )
        return TerrainShadeResponse(
            shade_factor=round(shade_factor, 3),
            exposure_hours=None,
            is_premium_locked=False,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid parameters: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail="Unable to calculate shade blocking at this time"
        )

# ==================== Wind Shelter Endpoints ====================

@api_router.post("/wind-shelter/orientation", response_model=WindShelterResponse)
async def recommend_orientation(request: WindShelterRequest):
    """Recommend RV orientation for wind shelter based on local ridges and topography."""
    try:
        ridges = []
        if request.local_ridges:
            for ridge_req in request.local_ridges:
                ridge = Ridge(
                    bearing_deg=ridge_req.bearing_deg,
                    strength=ridge_req.strength,
                    name=ridge_req.name or f"Ridge at {ridge_req.bearing_deg}°"
                )
                ridges.append(ridge)
        advice = WindShelterService.recommend_orientation(
            request.predominant_dir_deg,
            request.gust_mph,
            ridges
        )
        return WindShelterResponse(
            recommended_bearing_deg=advice.recommended_bearing_deg,
            rationale_text=advice.rationale_text,
            risk_level=advice.risk_level,
            shelter_available=advice.shelter_available,
            estimated_wind_reduction_pct=advice.estimated_wind_reduction_pct,
            is_premium_locked=False,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid parameters: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail="Unable to recommend orientation at this time"
        )

# ==================== Road Passability Endpoint (A6) ====================
from road_passability_a6 import score as passability_score

@api_router.post("/road-passability", response_model=RoadPassabilityResponse)
async def get_road_passability(request: RoadPassabilityRequest):
    """Road passability scoring (Task A6)."""
    try:
        res = passability_score(
            precip72h_in=request.precip72hIn,
            slope_pct=request.slopePct,
            min_temp_f=request.minTempF,
            soil=request.soilType,
        )
        return RoadPassabilityResponse(
            score=res.score,
            mud_risk=res.mud_risk,
            ice_risk=res.ice_risk,
            clearance_need=res.clearance_need,
            four_by_four_recommended=res.four_by_four_recommended,
            reasons=res.reasons,
            is_premium_locked=False,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid parameters: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail="Unable to compute road passability at this time")

# ==================== Connectivity Endpoints (A7) ====================

@api_router.post("/connectivity/cell-probability", response_model=ConnectivityCellResponse)
async def predict_cell_probability(request: ConnectivityCellRequest):
    """Cellular signal probability prediction (Task A7)."""
    try:
        if request.lat is not None and request.lon is not None:
            res = predict_cell_signal_at_location(
                lat=request.lat,
                lon=request.lon,
                carrier=request.carrier,
            )
        else:
            if request.towerDistanceKm is None or request.terrainObstructionPct is None:
                raise ValueError("Either (lat, lon) or (towerDistanceKm, terrainObstructionPct) must be provided")
            res = cell_bars_probability(
                carrier=request.carrier,
                tower_distance_km=request.towerDistanceKm,
                terrain_obstruction=request.terrainObstructionPct,
            )
        return ConnectivityCellResponse(
            carrier=res.carrier,
            probability=res.probability,
            bar_estimate=res.bar_estimate,
            explanation=res.explanation,
            is_premium_locked=False,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid parameters: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail="Unable to compute cell probability at this time")

@api_router.post("/connectivity/starlink-risk", response_model=ConnectivityStarlinkResponse)
async def predict_starlink_risk(request: ConnectivityStarlinkRequest):
    """Starlink obstruction risk prediction (Task A7)."""
    try:
        res = obstruction_risk(
            horizon_south_deg=request.horizonSouthDeg,
            canopy_pct=request.canopyPct,
        )
        return ConnectivityStarlinkResponse(
            risk_level=res.risk_level,
            obstruction_score=res.obstruction_score,
            explanation=res.explanation,
            reasons=res.reasons,
            is_premium_locked=False,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid parameters: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail="Unable to compute Starlink risk at this time")

# ==================== Campsite Index Endpoints (A8) ====================

async def _fetch_wind_data(client: httpx.AsyncClient, lat: float, lon: float) -> float:
    """Fetch current wind gust from NOAA weather API."""
    try:
        # Get NOAA grid point
        point_url = f"https://api.weather.gov/points/{lat},{lon}"
        point_resp = await client.get(point_url, headers=NOAA_HEADERS, timeout=10.0)
        if point_resp.status_code != 200:
            logger.warning(f"NOAA point lookup failed: {point_resp.status_code}")
            return 10.0  # Default moderate wind
        
        point_data = point_resp.json()
        forecast_url = point_data['properties']['forecast']
        
        # Get current forecast
        forecast_resp = await client.get(forecast_url, headers=NOAA_HEADERS, timeout=10.0)
        if forecast_resp.status_code != 200:
            logger.warning(f"NOAA forecast failed: {forecast_resp.status_code}")
            return 10.0
        
        forecast_data = forecast_resp.json()
        periods = forecast_data['properties']['periods']
        if not periods:
            return 10.0
        
        # Get wind speed from current period
        current_period = periods[0]
        wind_speed_str = current_period.get('windSpeed', '10 mph')
        
        # Parse wind speed (format: "10 mph" or "5 to 10 mph")
        import re
        matches = re.findall(r'\d+', wind_speed_str)
        if matches:
            # Use the higher value if range
            wind_mph = float(matches[-1])
            # Estimate gust as 1.3x sustained
            return wind_mph * 1.3
        
        return 10.0
    except Exception as e:
        logger.warning(f"Error fetching wind data: {e}")
        return 10.0  # Default


async def _fetch_terrain_data(client: httpx.AsyncClient, lat: float, lon: float) -> tuple[float, float]:
    """Fetch terrain slope and shade estimate."""
    try:
        # Use Open-Elevation API for elevation data
        # Get 4 points in a small grid to calculate slope
        offset = 0.001  # ~100m
        points = [
            f"{lat},{lon}",
            f"{lat+offset},{lon}",
            f"{lat},{lon+offset}",
            f"{lat-offset},{lon}",
            f"{lat},{lon-offset}",
        ]
        
        url = "https://api.open-elevation.com/api/v1/lookup"
        payload = {"locations": [{"latitude": float(p.split(',')[0]), "longitude": float(p.split(',')[1])} for p in points]}
        
        resp = await client.post(url, json=payload, timeout=15.0)
        if resp.status_code != 200:
            logger.warning(f"Elevation API failed: {resp.status_code}")
            return 5.0, 0.3  # Default moderate slope, low shade
        
        data = resp.json()
        elevations = [r['elevation'] for r in data['results']]
        
        if len(elevations) >= 5:
            # Calculate slope as max elevation difference
            center = elevations[0]
            diffs = [abs(e - center) for e in elevations[1:]]
            max_diff = max(diffs)
            # Convert to percentage (approximate)
            distance_m = offset * 111000  # degrees to meters (rough)
            slope_pct = (max_diff / distance_m) * 100
            slope_pct = min(slope_pct, 50.0)  # Cap at 50%
        else:
            slope_pct = 5.0
        
        # Shade: use OSM to check for tree coverage
        shade_score = await _fetch_shade_from_osm(client, lat, lon)
        
        return slope_pct, shade_score
    except Exception as e:
        logger.warning(f"Error fetching terrain data: {e}")
        return 5.0, 0.3  # Default


async def _fetch_shade_from_osm(client: httpx.AsyncClient, lat: float, lon: float) -> float:
    """Estimate shade from OSM tree/forest coverage."""
    try:
        # Query OSM for natural=wood, landuse=forest near location
        bbox_size = 0.005  # ~500m radius
        bbox = f"{lat-bbox_size},{lon-bbox_size},{lat+bbox_size},{lon+bbox_size}"
        
        overpass_query = f"""
        [out:json][timeout:10];
        (
          way["natural"="wood"]({bbox});
          way["landuse"="forest"]({bbox});
          way["natural"="tree_row"]({bbox});
        );
        out geom;
        """
        
        overpass_url = "https://overpass-api.de/api/interpreter"
        resp = await client.post(overpass_url, data={"data": overpass_query}, timeout=15.0)
        
        if resp.status_code != 200:
            logger.warning("Overpass shade lookup failed status=%s", resp.status_code)
            raise HTTPException(status_code=503, detail="Shade lookup temporarily unavailable. Please try again.")
        
        data = resp.json()
        elements = data.get('elements', [])
        
        if len(elements) > 0:
            # If trees/forest found nearby, assume moderate to high shade
            return 0.6
        else:
            # Open area, low shade
            return 0.2
    except Exception as e:
        logger.warning(f"Error fetching shade data: {e}")
        raise HTTPException(status_code=503, detail="Shade lookup failed. Please try again.")


async def _fetch_access_score(client: httpx.AsyncClient, lat: float, lon: float) -> float:
    """Calculate access score based on nearby road types."""
    try:
        # Query OSM for roads near location
        bbox_size = 0.01  # ~1km radius
        bbox = f"{lat-bbox_size},{lon-bbox_size},{lat+bbox_size},{lon+bbox_size}"
        
        overpass_query = f"""
        [out:json][timeout:10];
        (
          way["highway"]({bbox});
        );
        out geom;
        """
        
        overpass_url = "https://overpass-api.de/api/interpreter"
        resp = await client.post(overpass_url, data={"data": overpass_query}, timeout=15.0)
        
        if resp.status_code != 200:
            logger.warning("Overpass access lookup failed status=%s", resp.status_code)
            raise HTTPException(status_code=503, detail="Road access lookup temporarily unavailable. Please try again.")
        
        data = resp.json()
        elements = data.get('elements', [])
        
        if not elements:
            return 0.3  # Poor access
        
        # Score based on best road type found
        road_scores = {
            'motorway': 1.0,
            'trunk': 0.95,
            'primary': 0.9,
            'secondary': 0.85,
            'tertiary': 0.8,
            'unclassified': 0.6,
            'residential': 0.7,
            'service': 0.5,
            'track': 0.4,
            'path': 0.2,
        }
        
        best_score = 0.3
        for element in elements:
            highway_type = element.get('tags', {}).get('highway', '')
            score = road_scores.get(highway_type, 0.5)
            best_score = max(best_score, score)
        
        return best_score
    except Exception as e:
        logger.warning(f"Error fetching access score: {e}")
        raise HTTPException(status_code=503, detail="Road access lookup failed. Please try again.")


async def _fetch_signal_score(lat: float, lon: float) -> float:
    """Estimate cell signal based on distance to populated areas."""
    try:
        # Use the existing cell signal prediction service
        signal_data = await predict_cell_signal_at_location(lat, lon)
        
        if signal_data:
            # Convert bars (0-5) to score (0-1)
            bars = signal_data.get('bars', 2.5)
            return bars / 5.0
        
        return 0.5  # Default medium signal
    except Exception as e:
        logger.warning(f"Error fetching signal score: {e}")
        return 0.5


async def _fetch_passability_score(client: httpx.AsyncClient, lat: float, lon: float) -> float:
    """Get road passability using the existing service."""
    try:
        # Use the road passability service
        service = RoadPassabilityService()
        
        # Get current weather
        point_url = f"https://api.weather.gov/points/{lat},{lon}"
        point_resp = await client.get(point_url, headers=NOAA_HEADERS, timeout=10.0)
        
        if point_resp.status_code != 200:
            return 75.0  # Default good passability
        
        point_data = point_resp.json()
        forecast_url = point_data['properties']['forecastHourly']
        
        forecast_resp = await client.get(forecast_url, headers=NOAA_HEADERS, timeout=10.0)
        if forecast_resp.status_code != 200:
            return 75.0
        
        forecast_data = forecast_resp.json()
        periods = forecast_data['properties']['periods']
        if not periods:
            return 75.0
        
        current = periods[0]
        
        # Extract weather conditions
        temp_f = current.get('temperature', 50)
        precip_prob = current.get('probabilityOfPrecipitation', {}).get('value', 0) or 0
        
        # Simple passability calculation
        # Start with 100, reduce for adverse conditions
        score = 100.0
        
        # Reduce for freezing temps
        if temp_f < 32:
            score -= 20
        
        # Reduce for precipitation
        if precip_prob > 50:
            score -= 15
        elif precip_prob > 20:
            score -= 10
        
        return max(score, 0.0)
    except Exception as e:
        logger.warning(f"Error fetching passability score: {e}")
        return 75.0  # Default


@api_router.post("/campsite-index", response_model=CampsiteIndexResponse)
async def calculate_campsite_index(request: CampsiteIndexRequest):
    """Campsite Index scoring (Task A8)."""
    try:
        factors = SiteFactors(
            wind_gust_mph=request.wind_gust_mph,
            shade_score=request.shade_score,
            slope_pct=request.slope_pct,
            access_score=request.access_score,
            signal_score=request.signal_score,
            road_passability_score=request.road_passability_score,
        )
        result = campsite_score(factors)
        return CampsiteIndexResponse(
            score=result.score,
            breakdown=result.breakdown,
            explanations=result.explanations,
            is_premium_locked=False,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid parameters: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail="Unable to compute campsite index at this time")


@api_router.post("/campsite-index/auto", response_model=CampsiteIndexResponse)
async def calculate_campsite_index_auto(request: CampsiteIndexAutoRequest):
    """Campsite Index with automatic data fetching."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            wind_gust_mph = await _fetch_wind_data(client, request.latitude, request.longitude)
            slope_pct, shade_score = await _fetch_terrain_data(client, request.latitude, request.longitude)
            access_score = await _fetch_access_score(client, request.latitude, request.longitude)
            signal_score = await _fetch_signal_score(request.latitude, request.longitude)
            road_passability_score = await _fetch_passability_score(client, request.latitude, request.longitude)

        factors = SiteFactors(
            wind_gust_mph=wind_gust_mph,
            shade_score=shade_score,
            slope_pct=slope_pct,
            access_score=access_score,
            signal_score=signal_score,
            road_passability_score=road_passability_score,
        )
        result = campsite_score(factors)
        return CampsiteIndexResponse(
            score=result.score,
            breakdown=result.breakdown,
            explanations=result.explanations,
            is_premium_locked=False,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid parameters: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail="Unable to compute campsite index at this time")

# ==================== Claim Log Endpoints (A9) ====================


def _to_claim_hazards(hazards: List[ClaimHazardEventModel]) -> List[ClaimHazardEvent]:
    """Convert Pydantic hazard models to domain dataclasses."""
    return [
        ClaimHazardEvent(
            timestamp=h.timestamp,
            type=h.type,
            severity=h.severity,
            location=(h.location.latitude, h.location.longitude),
            notes=h.notes,
            evidence=h.evidence,
        )
        for h in hazards
    ]


def _to_claim_weather(weather: ClaimWeatherSnapshotModel) -> ClaimWeatherSnapshot:
    """Convert Pydantic weather model to domain dataclass."""
    return ClaimWeatherSnapshot(
        summary=weather.summary,
        source=weather.source,
        time_range=(weather.time_range.start, weather.time_range.end),
        key_metrics=weather.key_metrics,
    )


@api_router.post("/claim-log/build", response_model=ClaimLogResponse)
async def build_claim_log_endpoint(request: ClaimLogRequest):
    """Claim Log builder (Task A9).

    Accepts hazard events and weather snapshot, returns structured ClaimLog JSON.
    """
    try:
        hazards = _to_claim_hazards(request.hazards)
        weather = _to_claim_weather(request.weatherSnapshot)
        claim_log = build_claim_log(route_id=request.routeId, hazards=hazards, weather_snapshot=weather)

        return ClaimLogResponse(
            schema_version=claim_log.schema_version,
            route_id=claim_log.route_id,
            generated_at=claim_log.generated_at,
            hazards=[h.to_dict() for h in claim_log.hazards],
            weather_snapshot=claim_log.weather_snapshot.to_dict(),
            totals=claim_log.totals,
            narrative=claim_log.narrative,
            is_premium_locked=False,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid parameters: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail="Unable to build claim log at this time")


class ClaimLogPdfRequest(BaseModel):
    routeId: Optional[str] = None
    hazards: Optional[List[ClaimHazardEventModel]] = None
    weatherSnapshot: Optional[ClaimWeatherSnapshotModel] = None
    claimLog: Optional[Dict[str, Any]] = None
    subscription_id: Optional[str] = None


@api_router.post("/claim-log/pdf")
async def claim_log_pdf_endpoint(request: ClaimLogPdfRequest):
    """Claim Log PDF export (Task A9).

    Accepts either raw inputs (routeId, hazards, weatherSnapshot) or a full ClaimLog JSON.
    Returns a PDF binary.
    """
    try:
        if request.claimLog:
            data = request.claimLog
            hazards_data = data.get("hazards", [])
            hazards = [
                ClaimHazardEvent(
                    timestamp=h.get("timestamp"),
                    type=h.get("type"),
                    severity=h.get("severity"),
                    location=(h.get("location", {}).get("latitude"), h.get("location", {}).get("longitude")),
                    notes=h.get("notes"),
                    evidence=h.get("evidence"),
                )
                for h in hazards_data
            ]
            weather_data = data.get("weather_snapshot", {})
            time_range = weather_data.get("time_range", {})
            weather = ClaimWeatherSnapshot(
                summary=weather_data.get("summary", ""),
                source=weather_data.get("source", ""),
                time_range=(time_range.get("start", ""), time_range.get("end", "")),
                key_metrics=weather_data.get("key_metrics", {}),
            )
            claim_log = build_claim_log(
                route_id=data.get("route_id", ""),
                hazards=hazards,
                weather_snapshot=weather,
                generated_at=data.get("generated_at"),
                schema_version=data.get("schema_version", "1.0"),
            )
        else:
            if not request.routeId or not request.hazards or not request.weatherSnapshot:
                raise ValueError("Either claimLog or routeId/hazards/weatherSnapshot must be provided")
            hazards = _to_claim_hazards(request.hazards)
            weather = _to_claim_weather(request.weatherSnapshot)
            claim_log = build_claim_log(route_id=request.routeId, hazards=hazards, weather_snapshot=weather)

        pdf_bytes = export_claim_log_to_pdf(claim_log)
        return StreamingResponse(BytesIO(pdf_bytes), media_type="application/pdf", headers={
            "Content-Disposition": f"attachment; filename=claim_log_{claim_log.route_id}.pdf"
        })
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid parameters: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail="Unable to export claim log PDF at this time")


# ==================== E1: Smart Departure & Hazard Alerts ====================

@api_router.post("/trips/planned", response_model=RegisterPlannedTripResponse)
async def register_planned_trip(request: RegisterPlannedTripRequest):
    """
    Register a planned trip for smart delay evaluation (Task E1 - Pro-only).
    
    Stores route waypoints, planned departure time, and user timezone.
    Backend will evaluate forecast and send smart delay notifications.
    """
    # Premium gating
    # TESTING: Paywalls disabled - require_premium(request.subscription_id, SMART_DELAY_ALERTS)
    
    try:
        # Validate subscription_id
        if not request.subscription_id:
            raise HTTPException(status_code=401, detail="subscription_id required")
        
        # Get user_id from subscription
        sub_doc = await db.subscriptions.find_one({"subscription_id": request.subscription_id})
        if not sub_doc:
            raise HTTPException(status_code=404, detail="Subscription not found")
        user_id = sub_doc.get("user_id")
        
        # Convert waypoint requests to dicts
        waypoints = [
            {"lat": wp.latitude, "lon": wp.longitude, "name": wp.name}
            for wp in request.route_waypoints
        ]
        
        # Register trip
        service = get_notification_service()
        trip_id = service.register_planned_trip(
            user_id=user_id,
            route_waypoints=waypoints,
            planned_departure_local=request.planned_departure_local,
            user_timezone=request.user_timezone,
            destination_name=request.destination_name,
        )
        
        return RegisterPlannedTripResponse(
            trip_id=trip_id,
            registered_at=datetime.now(timedelta(0)),  # UTC
            next_check_at=datetime.now(timedelta(0)),
            is_premium_locked=False,
        )
    
    except ValueError as e:
        logger.error(f"[PREMIUM] Invalid trip request: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[PREMIUM] Error registering planned trip: {e}")
        raise HTTPException(status_code=500, detail="Failed to register planned trip")


@api_router.post("/push/register", response_model=RegisterPushTokenResponse)
async def register_push_token(request: RegisterPushTokenRequest):
    """
    Register Expo push token for notifications (Task E1 - Pro-only).
    
    Stores the Expo push token so smart delay alerts can be sent to this device.
    """
    # Premium gating
    # TESTING: Paywalls disabled - require_premium(request.subscription_id, SMART_DELAY_ALERTS)
    
    try:
        # Validate subscription_id
        if not request.subscription_id:
            raise HTTPException(status_code=401, detail="subscription_id required")
        
        # Get user_id from subscription
        sub_doc = await db.subscriptions.find_one({"subscription_id": request.subscription_id})
        if not sub_doc:
            raise HTTPException(status_code=404, detail="Subscription not found")
        user_id = sub_doc.get("user_id")
        
        # Validate token format
        if not request.token.startswith("ExponentPushToken["):
            return RegisterPushTokenResponse(
                success=False,
                message="Invalid Expo push token format",
                is_premium_locked=False,
            )
        
        # Register token
        service = get_notification_service()
        service.register_push_token(
            user_id=user_id,
            token=request.token,
            device_id=request.device_id,
        )
        
        logger.info(f"[PREMIUM] Registered push token for user {user_id}")
        return RegisterPushTokenResponse(
            success=True,
            message="Push token registered successfully",
            is_premium_locked=False,
        )
    
    except ValueError as e:
        logger.error(f"[PREMIUM] Invalid push token: {e}")
        return RegisterPushTokenResponse(
            success=False,
            message=str(e),
            is_premium_locked=False,
        )
    except Exception as e:
        logger.error(f"[PREMIUM] Error registering push token: {e}")
        raise HTTPException(status_code=500, detail="Failed to register push token")


@api_router.post("/notifications/check", response_model=CheckNotificationResponse)
async def check_notification(request: CheckNotificationRequest):
    """
    Check if a notification should be sent now (fallback endpoint).
    
    Alternative to server-driven push: client can call this when app opens/foregrounds
    to get immediate notification decision.
    
    Pro-only feature: Task E1
    """
    # Premium gating
    # TESTING: Paywalls disabled - require_premium(request.subscription_id, SMART_DELAY_ALERTS)
    
    try:
        # Validate subscription_id
        if not request.subscription_id:
            raise HTTPException(status_code=401, detail="subscription_id required")
        
        # Get user_id and trip details
        sub_doc = await db.subscriptions.find_one({"subscription_id": request.subscription_id})
        if not sub_doc:
            raise HTTPException(status_code=404, detail="Subscription not found")
        user_id = sub_doc.get("user_id")
        
        # In a real system, would fetch trip, forecast, compute risk, etc.
        # For now, return no notification (client polls periodically)
        return CheckNotificationResponse(
            should_notify=False,
            notification=None,
            is_premium_locked=False,
        )
    
    except Exception as e:
        logger.error(f"[PREMIUM] Error checking notification: {e}")
        raise HTTPException(status_code=500, detail="Failed to check notification")


# ==================== Free Camping Finder Endpoint ====================

def _dedupe_camping_spots(spots: List[CampingSpot], precision: int = 3) -> List[CampingSpot]:
    """Deduplicate camping spots using stable place keys.

    Prefers higher rating/known coverage, then closer distance.
    """

    def _coverage_score(value: Optional[str]) -> int:
        if not value:
            return 0
        lowered = value.lower()
        return 0 if lowered == "unknown" else 1

    def _score(spot: CampingSpot) -> tuple:
        rating = spot.rating or 0
        coverage = _coverage_score(spot.cell_coverage)
        return (rating, coverage)

    def _key_fn(spot: CampingSpot) -> Optional[str]:
        # Prefer a stable key that includes source id when available, otherwise
        # fall back to rounded coordinates + normalized name.
        return _stable_place_key(
            spot.name,
            spot.latitude,
            spot.longitude,
            source_id=spot.source_id,
            precision=precision,
        )

    def _prefer(candidate: CampingSpot, current: CampingSpot) -> bool:
        cand_score = _score(candidate)
        curr_score = _score(current)
        if cand_score != curr_score:
            return cand_score > curr_score
        if candidate.distance_miles != current.distance_miles:
            return candidate.distance_miles < current.distance_miles
        cand_id = (candidate.source_id or "")
        curr_id = (current.source_id or "")
        if cand_id and curr_id and cand_id != curr_id:
            return cand_id < curr_id
        cand_coord = f"{candidate.latitude:.6f},{candidate.longitude:.6f}"
        curr_coord = f"{current.latitude:.6f},{current.longitude:.6f}"
        return cand_coord < curr_coord

    primary = _dedupe_items(spots, _key_fn, _prefer)

    # Secondary proximity-based merge to catch near-duplicate nodes/ways that
    # share the same location but differ slightly in geometry.
    merged: List[CampingSpot] = []
    for spot in primary:
        merged_into_existing = False
        for idx, existing in enumerate(merged):
            if (
                spot.latitude is None
                or spot.longitude is None
                or existing.latitude is None
                or existing.longitude is None
            ):
                continue
            if _haversine_meters(
                spot.latitude,
                spot.longitude,
                existing.latitude,
                existing.longitude,
            ) <= 250:  # within ~0.15 miles
                if _prefer(spot, existing):
                    merged[idx] = spot
                merged_into_existing = True
                break
        if not merged_into_existing:
            merged.append(spot)

    return sorted(merged, key=lambda x: x.distance_miles)

@api_router.post("/free-camping/search", response_model=FreeCampingResponse)
async def search_free_camping(request: FreeCampingRequest):
    """Find free camping spots (BLM, National Forest, etc.) near given coordinates using OpenStreetMap data."""
    # TESTING: Paywalls disabled - require_premium(request.subscription_id, CAMPSITE_INDEX)  # Reuse campsite_index feature for now
    
    try:
        # Convert miles to meters for Overpass API
        radius_meters = int(request.radius_miles * 1609.34)
        
        # Query OpenStreetMap via Overpass API for camping sites
        overpass_query = f"""
        [out:json][timeout:25];
        (
          node["tourism"="camp_site"](around:{radius_meters},{request.latitude},{request.longitude});
          node["tourism"="caravan_site"](around:{radius_meters},{request.latitude},{request.longitude});
          way["tourism"="camp_site"](around:{radius_meters},{request.latitude},{request.longitude});
          way["tourism"="caravan_site"](around:{radius_meters},{request.latitude},{request.longitude});
        );
        out body;
        >;
        out skel qt;
        """
        
        async with httpx.AsyncClient(timeout=45.0) as client:
            # Try multiple Overpass API instances
            overpass_urls = [
                "https://overpass-api.de/api/interpreter",
                "https://overpass.kumi.systems/api/interpreter",
            ]
            
            osm_data = None
            last_error = None
            
            for url in overpass_urls:
                try:
                    osm_response = await client.post(url, data=overpass_query)
                    osm_response.raise_for_status()
                    osm_data = osm_response.json()
                    break
                except Exception as e:
                    last_error = e
                    logger.warning(f"Free camping - Overpass instance {url} failed: {e}")
                    continue
            
            if osm_data is None:
                detail = "Camping search unavailable right now. Please try again shortly."
                logger.warning("Free camping - all Overpass instances failed: %s", last_error)
                raise HTTPException(status_code=503, detail=detail)
        
        spots = []
        
        for element in osm_data.get("elements", []):
            # Get coordinates
            if element.get("type") == "node":
                lat = element.get("lat")
                lon = element.get("lon")
            elif element.get("type") == "way" and "center" in element:
                lat = element["center"].get("lat")
                lon = element["center"].get("lon")
            else:
                continue
            
            if not lat or not lon:
                continue
            
            # Calculate distance
            distance_miles = math.sqrt(
                (lat - request.latitude) ** 2 + (lon - request.longitude) ** 2
            ) * 69.0  # Rough approximation: 1 degree ≈ 69 miles
            
            tags = element.get("tags", {})
            
            # Extract name with better fallbacks
            name_candidates = [
                tags.get("name"),
                tags.get("official_name"),
                tags.get("alt_name"),
                tags.get("operator"),
                tags.get("ref"),
                tags.get("designation"),
            ]
            name = next((n for n in name_candidates if n), None)
            if not name:
                nearest_place = (
                    tags.get("addr:place")
                    or tags.get("addr:city")
                    or tags.get("addr:county")
                    or tags.get("addr:state")
                )
                if tags.get("backcountry") == "yes":
                    name = f"Backcountry near {nearest_place}" if nearest_place else "Backcountry Camping"
                elif tags.get("tourism") == "camp_site":
                    name = f"Public Campsite near {nearest_place}" if nearest_place else "Public Campsite"
                else:
                    name = f"Dispersed Camping near {nearest_place}" if nearest_place else "Dispersed Camping"
            
            # Extract contact information
            phone = tags.get("phone") or tags.get("contact:phone")
            website = tags.get("website") or tags.get("contact:website") or tags.get("url")
            email = tags.get("email") or tags.get("contact:email")
            
            # Build contact string
            contact = None
            if phone or email:
                contact_parts = []
                if phone:
                    contact_parts.append(f"Phone: {phone}")
                if email:
                    contact_parts.append(f"Email: {email}")
                contact = " | ".join(contact_parts)
            
            # Determine type
            camp_type = "Campground"
            if "camp_site" in tags.get("tourism", ""):
                camp_type = "Campsite"
            if tags.get("backcountry") == "yes":
                camp_type = "Backcountry"
            if "National Forest" in tags.get("operator", ""):
                camp_type = "National Forest"
            if "BLM" in tags.get("operator", ""):
                camp_type = "BLM Land"
            
            # Extract amenities
            amenities = []
            if tags.get("toilets") == "yes":
                amenities.append("Toilets")
            if tags.get("drinking_water") == "yes":
                amenities.append("Water")
            if tags.get("shower") == "yes":
                amenities.append("Showers")
            if tags.get("electricity") == "yes":
                amenities.append("Electricity")
            if tags.get("tents") == "yes":
                amenities.append("Tent Sites")
            if tags.get("caravans") == "yes" or "caravan" in tags.get("tourism", ""):
                amenities.append("RV Sites")
            if not amenities:
                amenities.append("Basic Site")
            
            # Determine if free
            fee = tags.get("fee", "unknown")
            is_free = fee == "no" or tags.get("backcountry") == "yes"
            
            # Estimate access difficulty
            access = tags.get("access", "")
            surface = tags.get("surface", "")
            access_difficulty = "moderate"
            if surface in ["paved", "asphalt"]:
                access_difficulty = "easy"
            elif "4wd" in surface.lower() or tags.get("4wd_only") == "yes":
                access_difficulty = "4wd-required"
            elif surface in ["gravel", "dirt"]:
                access_difficulty = "moderate"
            
            # Get description
            description = tags.get("description", f"Camping area near {name}")
            
            # Estimate elevation (would need elevation API for accuracy)
            elevation_ft = int(tags.get("ele", 5000))  # Default 5000ft if unknown
            
            # Default rating (OSM doesn't have ratings)
            rating = 3.5
            
            # Cell coverage estimate (unknown from OSM)
            cell_coverage = "unknown"
            
            # Stay limit
            stay_limit = tags.get("opening_hours", "Check local regulations")
            if tags.get("backcountry") == "yes":
                stay_limit = "14 days (typical)"
            
            spots.append(CampingSpot(
                name=name,
                type=camp_type,
                distance_miles=round(distance_miles, 1),
                latitude=lat,
                longitude=lon,
                source_id=str(element.get("id")) if element.get("id") else None,
                description=description,
                amenities=amenities,
                stay_limit=stay_limit,
                cell_coverage=cell_coverage,
                access_difficulty=access_difficulty,
                elevation_ft=elevation_ft,
                rating=rating,
                free=is_free,
                phone=phone,
                website=website,
                contact=contact
            ))
        
        # Deduplicate closely clustered points before sorting/limiting
        spots = _dedupe_camping_spots(spots)

        # Sort by distance
        spots.sort(key=lambda x: x.distance_miles)

        # Limit to 20 results
        spots = spots[:20]
        
        logger.info(f"Free camping search completed: found {len(spots)} spots from OSM within {request.radius_miles} miles")
        
        return FreeCampingResponse(
            spots=spots,
            is_premium_locked=False,
        )
    
    except httpx.HTTPError as e:
        logger.error(f"Overpass API error: {e}")
        raise HTTPException(
            status_code=503,
            detail="Camping data service temporarily unavailable"
        )
    except Exception as e:
        logger.error(f"Error searching free camping: {e}")
        raise HTTPException(
            status_code=500,
            detail="Unable to search for camping spots at this time"
        )


# ==================== Dump Station Finder Endpoint ====================

@api_router.post("/dump-stations/search", response_model=DumpStationResponse)
async def search_dump_stations(request: DumpStationRequest):
    """Find RV dump stations near given coordinates using OpenStreetMap data."""
    # TESTING: Paywalls disabled - require_premium(request.subscription_id, CAMPSITE_INDEX)  # Reuse campsite_index feature
    
    try:
        # Convert miles to meters for Overpass API
        radius_meters = int(request.radius_miles * 1609.34)
        
        # Query OpenStreetMap via Overpass API for dump stations
        overpass_query = f"""
        [out:json][timeout:25];
        (
          node["amenity"="sanitary_dump_station"](around:{radius_meters},{request.latitude},{request.longitude});
          node["sanitary_dump_station"="yes"](around:{radius_meters},{request.latitude},{request.longitude});
          way["amenity"="sanitary_dump_station"](around:{radius_meters},{request.latitude},{request.longitude});
        );
        out body;
        >;
        out skel qt;
        """
        
        async with httpx.AsyncClient(timeout=45.0) as client:
            # Try multiple Overpass API instances for better reliability
            overpass_urls = [
                "https://overpass-api.de/api/interpreter",
                "https://overpass.kumi.systems/api/interpreter",
            ]
            
            osm_data = None
            last_error = None
            
            for url in overpass_urls:
                try:
                    osm_response = await client.post(url, data=overpass_query)
                    osm_response.raise_for_status()
                    osm_data = osm_response.json()
                    break  # Success, exit loop
                except Exception as e:
                    last_error = e
                    logger.warning(f"Dump stations - Overpass instance {url} failed: {e}")
                    continue
            
            if osm_data is None:
                raise last_error or Exception("All Overpass instances failed")
        
        stations = []
        seen_coords = set()
        
        for element in osm_data.get("elements", []):
            # Get coordinates
            if element.get("type") == "node":
                lat = element.get("lat")
                lon = element.get("lon")
            elif element.get("type") == "way" and "center" in element:
                lat = element["center"].get("lat")
                lon = element["center"].get("lon")
            else:
                continue
            
            if not lat or not lon:
                continue
            
            # Avoid duplicates
            coord_key = (round(lat, 4), round(lon, 4))
            if coord_key in seen_coords:
                continue
            seen_coords.add(coord_key)
            
            # Calculate distance
            distance_miles = math.sqrt(
                (lat - request.latitude) ** 2 + (lon - request.longitude) ** 2
            ) * 69.0
            
            tags = element.get("tags", {})
            
            # Extract name
            name = tags.get("name", tags.get("operator", "Dump Station"))
            
            # Determine type
            station_type = "Standalone"
            if "rest" in tags.get("highway", "").lower() or "rest area" in name.lower():
                station_type = "Rest Stop"
            elif "gas" in name.lower() or "fuel" in tags.get("amenity", "").lower():
                station_type = "Gas Station"
            elif "park" in tags.get("tourism", "").lower() or "rv park" in name.lower():
                station_type = "RV Park"
            elif tags.get("tourism") == "camp_site":
                station_type = "Campground"
            
            # Check for potable water
            has_water = tags.get("drinking_water") == "yes" or tags.get("water") == "yes"
            
            # Determine if free
            fee = tags.get("fee", "unknown")
            is_free = fee == "no"
            cost = "Free" if is_free else tags.get("charge", "$5-10 (typical)")
            
            # Hours
            hours = tags.get("opening_hours", "24/7")
            if hours == "24/7":
                hours = "Open 24 hours"
            
            # Restrictions
            restrictions = []
            if tags.get("access") == "customers":
                restrictions.append("Customers only")
            if tags.get("maxlength"):
                restrictions.append(f"Max length: {tags.get('maxlength')}")
            if tags.get("description") and "restriction" in tags.get("description", "").lower():
                restrictions.append(tags.get("description"))
            
            # Access difficulty
            access = "easy"
            surface = tags.get("surface", "")
            if surface in ["gravel", "dirt"]:
                access = "moderate"
            
            # Description
            description = tags.get("description", f"RV dump station at {name}")
            if has_water:
                description += " Fresh water fill also available."
            
            # Extract contact information
            phone = tags.get("phone") or tags.get("contact:phone")
            website = tags.get("website") or tags.get("contact:website") or tags.get("url")
            
            # Extract address
            address_parts = []
            if tags.get("addr:housenumber") and tags.get("addr:street"):
                address_parts.append(f"{tags.get('addr:housenumber')} {tags.get('addr:street')}")
            elif tags.get("addr:street"):
                address_parts.append(tags.get("addr:street"))
            if tags.get("addr:city"):
                address_parts.append(tags.get("addr:city"))
            if tags.get("addr:state"):
                address_parts.append(tags.get("addr:state"))
            if tags.get("addr:postcode"):
                address_parts.append(tags.get("addr:postcode"))
            address = ", ".join(address_parts) if address_parts else None
            formatted_address = address
            vicinity = tags.get("addr:city") or None
            
            # Rating (default)
            rating = 3.5
            
            stations.append(DumpStation(
                name=name,
                type=station_type,
                distance_miles=round(distance_miles, 1),
                latitude=lat,
                longitude=lon,
                description=description,
                has_potable_water=has_water,
                is_free=is_free,
                cost=cost,
                hours=hours,
                restrictions=restrictions,
                access=access,
                rating=rating,
                address=address,
                website=website,
                phone=phone
            ))
        
        # Sort by distance
        stations.sort(key=lambda x: x.distance_miles)
        
        # Limit to 20 results
        stations = stations[:20]
        
        logger.info(f"Dump station search completed: found {len(stations)} stations from OSM within {request.radius_miles} miles")
        
        return DumpStationResponse(
            stations=stations,
            is_premium_locked=False,
        )
    
    except httpx.HTTPError as e:
        logger.error(f"Overpass API error for dump stations: {e}")
        raise HTTPException(
            status_code=503,
            detail="Dump station data service temporarily unavailable. The mapping service may be experiencing high load. Please try again in a few moments."
        )


# ==================== Casinos Near Me ====================

def _build_address(tags: Dict[str, Any]) -> Optional[str]:
    street = tags.get("addr:street")
    housenumber = tags.get("addr:housenumber")
    city = tags.get("addr:city")
    parts = [
        " ".join([str(housenumber)]).strip() if housenumber else None,
        street,
        city,
    ]
    formatted = ", ".join([p for p in parts if p])
    return formatted or None


class OverpassError(Exception):
    def __init__(self, message: str, attempts: List[Dict[str, Any]]):
        super().__init__(message)
        self.attempts = attempts


async def _fetch_overpass_data(
    overpass_query: str,
    label: str,
    post_fn: Optional[Callable[[str, str], Awaitable[httpx.Response]]] = None,
) -> Dict[str, Any]:
    cache_key = hashlib.sha256(f"{label}:{overpass_query}".encode("utf-8")).hexdigest()
    cached = _cache_get(_overpass_response_cache, cache_key)
    if cached:
        return cached

    # Cache the last good endpoint for 10 minutes
    cache_ttl = timedelta(minutes=10)
    now = datetime.utcnow()
    candidates: List[str] = []
    try:
        if (
            globals().get("_last_good_overpass")
            and globals().get("_last_good_overpass_ts")
            and now - globals()["_last_good_overpass_ts"] < cache_ttl
        ):
            candidates.append(globals()["_last_good_overpass"])
    except Exception:
        pass

    for url in OVERPASS_URLS:
        if url not in candidates:
            candidates.append(url)

    timeout = httpx.Timeout(20.0, connect=5.0)
    last_error: Optional[Exception] = None
    attempts: List[Dict[str, Any]] = []
    max_attempts = 3
    backoff = 0.6
    attempt_count = 0

    async def _post(url: str):
        async with httpx.AsyncClient(timeout=timeout) as client:
            return await client.post(url, data=overpass_query)

    for url in candidates:
        if attempt_count >= max_attempts:
            break
        try:
            resp = await (_post(url) if post_fn is None else post_fn(url, overpass_query))
            status = resp.status_code
            if status == 429 or status >= 500:
                raise httpx.HTTPStatusError("Overpass returned error", request=resp.request, response=resp)
            resp.raise_for_status()
            data = resp.json()
            globals()["_last_good_overpass"] = url
            globals()["_last_good_overpass_ts"] = now
            _cache_set(_overpass_response_cache, cache_key, data, ttl=OVERPASS_CACHE_TTL_SECONDS)
            return data
        except Exception as exc:  # noqa: BLE001
            attempt_count += 1
            attempts.append({"url": url, "error": str(exc)})
            last_error = exc
            logger.warning("%s - Overpass instance %s failed: %s", label, url, exc)
            if attempt_count < max_attempts:
                delay = min(3.0, backoff + random.uniform(0.0, 0.3))
                await asyncio.sleep(delay)
                backoff = min(backoff * 2, 3.5)
            continue

    raise OverpassError("All Overpass instances failed", attempts) from last_error


GENERIC_PLACEHOLDERS = {"store", "shop", "supermarket", "restaurant", "casino", "location"}


def _normalize_for_dedupe(name: Optional[str]) -> Optional[str]:
    if not name:
        return None
    lowered = name.lower()
    lowered = re.sub(r"\bnear\s*\([^\)]*\)", "", lowered)
    normalized = re.sub(r"[^a-z0-9]+", " ", lowered).strip()
    return normalized or None


def _stable_place_key(
    name: Optional[str],
    latitude: Optional[float],
    longitude: Optional[float],
    *,
    place_id: Optional[Any] = None,
    source_id: Optional[Any] = None,
    precision: int = 4,
) -> Optional[str]:
    """Compute a stable dedupe key for places.

    Priority:
    1) explicit id/place_id/source_id
    2) normalized name + rounded coords
    3) coords only
    4) normalized name only
    """

    if place_id is not None:
        return str(place_id)
    if source_id is not None:
        return str(source_id)

    norm = _normalize_for_dedupe(name)
    coord = None
    if latitude is not None and longitude is not None:
        coord = f"{round(latitude, precision):.{precision}f},{round(longitude, precision):.{precision}f}"

    if norm and coord:
        return f"{norm}:{coord}"
    if coord:
        return f"coord:{coord}"
    if norm:
        return f"name:{norm}"
    return None


def _dedupe_places(items: List[T], key_fn: Callable[[T], Optional[str]], prefer_fn: Callable[[T, T], bool]) -> List[T]:
    return _dedupe_items(items, key_fn, prefer_fn)


T = TypeVar("T")


def _dedupe_items(
    items: List[T],
    key_fn: Callable[[T], Optional[str]],
    prefer_fn: Callable[[T, T], bool],
) -> List[T]:
    deduped: Dict[str, T] = {}
    for item in items:
        key = key_fn(item) or f"anon-{len(deduped)}"
        existing = deduped.get(key)
        if existing is None or prefer_fn(item, existing):
            deduped[key] = item
    return list(deduped.values())


def _haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    # Basic haversine for short distances; adequate for ~200 m merge window
    radius_m = 6371000.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return radius_m * c


def _normalize_name(tags: Dict[str, str], category: str, lat: float, lon: float) -> str:
    candidates = [
        tags.get("name"),
        tags.get("brand"),
        tags.get("operator"),
        tags.get("official_name"),
        tags.get("alt_name"),
    ]
    for candidate in candidates:
        if not candidate:
            continue
        lowered = candidate.strip().lower()
        if lowered not in GENERIC_PLACEHOLDERS:
            return candidate.strip()
    # If everything is generic, fall back to category-based label
    return f"{category} near ({round(lat, 3)}, {round(lon, 3)})"


def _compose_label(name: str, category: str, tags: Dict[str, str]) -> str:
    brand = tags.get("brand") or tags.get("operator")
    if brand:
        if brand.lower() in name.lower():
            return name
        return f"{brand} — {name}"
    return f"{category} — {name}" if category.lower() not in name.lower() else name


def _build_stop(element: Dict[str, Any], request: OvernightSearchRequest, category: str, default_notes: str) -> Optional[OvernightStop]:
    if element.get("type") == "node":
        lat = element.get("lat")
        lon = element.get("lon")
    elif element.get("type") == "way" and "center" in element:
        lat = element["center"].get("lat")
        lon = element["center"].get("lon")
    else:
        return None

    if lat is None or lon is None:
        return None

    distance_miles = math.sqrt((lat - request.latitude) ** 2 + (lon - request.longitude) ** 2) * 69.0
    tags = element.get("tags", {})
    name = _normalize_name(tags, category, lat, lon)
    label = _compose_label(name, category, tags)
    phone = tags.get("phone") or tags.get("contact:phone")
    website = tags.get("website") or tags.get("contact:website") or tags.get("url")
    hours = tags.get("opening_hours")
    address = _build_address(tags)
    notes = tags.get("description") or default_notes

    return OvernightStop(
        name=name,
        category=category,
        label=label,
        distance_miles=round(distance_miles, 1),
        latitude=lat,
        longitude=lon,
        osm_id=element.get("id"),
        address=address,
        phone=phone,
        website=website,
        hours=hours,
        notes=notes,
    )


def _dedupe_and_limit(stops: List[OvernightStop], limit: int = 25) -> List[OvernightStop]:
    def _score(stop: OvernightStop) -> int:
        score = 0
        if stop.name and stop.name.lower() not in GENERIC_PLACEHOLDERS:
            score += 2
        if stop.address:
            score += 1
        if stop.phone or stop.website:
            score += 1
        return score

    def _key_fn(stop: OvernightStop) -> Optional[str]:
        return _stable_place_key(
            stop.name,
            stop.latitude,
            stop.longitude,
            place_id=stop.osm_id,
            precision=4,
        )

    def _prefer(candidate: OvernightStop, current: OvernightStop) -> bool:
        cand_score = _score(candidate)
        curr_score = _score(current)
        if cand_score != curr_score:
            return cand_score > curr_score
        if candidate.distance_miles != current.distance_miles:
            return candidate.distance_miles < current.distance_miles
        cand_len = len(candidate.name or "")
        curr_len = len(current.name or "")
        return cand_len > curr_len

    primary = _dedupe_items(stops, _key_fn, _prefer)

    # Secondary proximity merge to collapse node/way duplicates that share the
    # same location but different OSM ids.
    merged: List[OvernightStop] = []
    for stop in primary:
        merged_into_existing = False
        for idx, existing in enumerate(merged):
            if (
                stop.latitude is None
                or stop.longitude is None
                or existing.latitude is None
                or existing.longitude is None
            ):
                continue
            if _haversine_meters(
                stop.latitude,
                stop.longitude,
                existing.latitude,
                existing.longitude,
            ) <= 200:  # ~0.12 miles
                if _prefer(stop, existing):
                    merged[idx] = stop
                merged_into_existing = True
                break
        if not merged_into_existing:
            merged.append(stop)

    deduped_sorted = sorted(merged, key=lambda x: x.distance_miles)
    return deduped_sorted[:limit]


def _empty_overpass_response(source: str = "overpass_unavailable") -> OvernightSearchResponse:
    return OvernightSearchResponse(spots=[], is_premium_locked=False, ok=True, source=source, error="overpass_unavailable")


async def _fetch_overpass_first_success(
    overpass_query: str,
    label: str,
    urls: List[str],
    *,
    overall_timeout: float = 10.0,
    per_timeout: float = 3.5,
    request_id: str = "",
) -> Dict[str, Any]:
    """Race multiple Overpass instances and return first successful payload.

    Logs per-instance failures with elapsed time and request id. Cancels pending
    tasks once a winner is found or overall timeout expires.
    """

    started = time.time()
    request_id = request_id or uuid.uuid4().hex[:8]
    errors: List[str] = []

    async def fetch(url: str):
        t0 = time.time()
        try:
            timeout = httpx.Timeout(per_timeout, connect=min(per_timeout / 2, 2.0))
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(url, data=overpass_query)
            resp.raise_for_status()
            elapsed_ms = int((time.time() - t0) * 1000)
            logger.info("[%s][%s] overpass success url=%s elapsed_ms=%d", label, request_id, url, elapsed_ms)
            return {"url": url, "data": resp.json(), "elapsed_ms": elapsed_ms}
        except Exception as exc:  # noqa: BLE001
            elapsed_ms = int((time.time() - t0) * 1000)
            msg = f"[{label}][{request_id}] overpass failed url={url} elapsed_ms={elapsed_ms} err={exc}"
            errors.append(msg)
            logger.warning(msg)
            raise

    tasks = [asyncio.create_task(fetch(url)) for url in urls]
    pending: set = set(tasks)
    winner_data = None

    try:
        done, pending = await asyncio.wait(tasks, timeout=overall_timeout, return_when=asyncio.FIRST_COMPLETED)
        if not done:
            raise asyncio.TimeoutError(f"{label} overpass timeout after {overall_timeout}s")

        winner_data = None
        last_exc: Optional[BaseException] = None
        for task in done:
            if task.cancelled():
                continue
            exc = task.exception()
            if exc is None:
                winner_data = task.result()
                break
            last_exc = exc

        if winner_data is None:
            raise last_exc or Exception("All Overpass instances failed")

        total_ms = int((time.time() - started) * 1000)
        logger.info(
            "[%s][%s] overpass selected url=%s total_ms=%d",
            label,
            request_id,
            winner_data.get("url"),
            total_ms,
        )
        return winner_data["data"]
    finally:
        for task in pending:
            task.cancel()
            with contextlib.suppress(Exception):
                await task
        if errors and winner_data is None:
            logger.warning("[%s][%s] overpass all failed: %s", label, request_id, "; ".join(errors))


async def _search_walmart_google_places(request: OvernightSearchRequest) -> List[OvernightStop]:
    """Search Walmart locations via Google Places Nearby Search (v1)."""
    if not GOOGLE_PLACES_API_KEY:
        logger.error("GOOGLE_PLACES_API_KEY missing for Walmart search")
        raise HTTPException(status_code=503, detail="Walmart search unavailable: missing GOOGLE_PLACES_API_KEY")

    radius_meters = min(50000.0, float(request.radius_miles * 1609.34))
    url = "https://places.googleapis.com/v1/places:searchNearby"
    body = {
        "locationRestriction": {
            "circle": {
                "center": {"latitude": request.latitude, "longitude": request.longitude},
                "radius": float(radius_meters),
            }
        },
        "includedTypes": ["parking", "truck_stop"],
        "maxResultCount": 20,
    }
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_PLACES_API_KEY,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.location,places.nationalPhoneNumber,places.websiteUri,places.regularOpeningHours",
    }

    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            resp = await client.post(url, headers=headers, json=body)
            resp.raise_for_status()
            payload = resp.json()
    except httpx.HTTPStatusError as exc:
        detail = getattr(exc.response, "text", "")[:200]
        logger.warning("Walmart Google Places status error %s body=%s", exc.response.status_code, detail)
        raise HTTPException(status_code=503, detail="Walmart search service error")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Walmart Google Places request failed: %s", exc)
        raise HTTPException(status_code=503, detail="Walmart search temporarily unavailable")

    places = payload.get("places", []) or []
    stops: List[OvernightStop] = []

    for place in places:
        loc = place.get("location") or {}
        lat = loc.get("latitude")
        lon = loc.get("longitude")
        if lat is None or lon is None:
            continue

        distance_miles = _haversine_meters(request.latitude, request.longitude, lat, lon) * 0.000621371
        display_name = (place.get("displayName") or {}).get("text") or "Walmart"
        address = place.get("formattedAddress")
        phone = place.get("nationalPhoneNumber")
        website = place.get("websiteUri")
        hours_desc = place.get("regularOpeningHours", {}).get("weekdayDescriptions")
        hours = "; ".join(hours_desc) if hours_desc else None

        stops.append(
            OvernightStop(
                name=display_name,
                category="Walmart",
                label=display_name,
                distance_miles=distance_miles,
                latitude=lat,
                longitude=lon,
                address=address,
                phone=phone,
                website=website,
                hours=hours,
                notes="Free overnight RV stays welcome. Call ahead to confirm with store manager.",
            )
        )

    stops.sort(key=lambda x: x.distance_miles)
    return stops


async def _search_cracker_barrel_google_places(request: OvernightSearchRequest) -> List[OvernightStop]:
    """Search Cracker Barrel via Google Places Text Search."""
    if not GOOGLE_PLACES_API_KEY:
        logger.error("GOOGLE_PLACES_API_KEY missing for Cracker Barrel search")
        raise HTTPException(status_code=503, detail="Cracker Barrel search unavailable: missing GOOGLE_PLACES_API_KEY")

    radius_meters = min(50000.0, float(request.radius_miles * 1609.34))
    url = "https://places.googleapis.com/v1/places:searchText"
    body = {
        "textQuery": "Cracker Barrel",
        "locationBias": {
            "circle": {
                "center": {"latitude": request.latitude, "longitude": request.longitude},
                "radius": float(radius_meters),
            }
        },
        "maxResultCount": 20,
        "rankPreference": "DISTANCE",
        "languageCode": "en",
    }
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_PLACES_API_KEY,
        "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress,places.location,places.nationalPhoneNumber,places.websiteUri,places.regularOpeningHours",
    }

    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            resp = await client.post(url, headers=headers, json=body)
            resp.raise_for_status()
            payload = resp.json()
    except httpx.HTTPStatusError as exc:
        detail = getattr(exc.response, "text", "")[:200]
        logger.warning("Cracker Barrel Google Places status error %s body=%s", exc.response.status_code, detail)
        raise HTTPException(status_code=503, detail="Cracker Barrel search service error")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Cracker Barrel Google Places request failed: %s", exc)
        raise HTTPException(status_code=503, detail="Cracker Barrel search temporarily unavailable")

    places = payload.get("places", []) or []
    stops: List[OvernightStop] = []

    for place in places:
        loc = place.get("location") or {}
        lat = loc.get("latitude")
        lon = loc.get("longitude")
        if lat is None or lon is None:
            continue

        distance_miles = _haversine_meters(request.latitude, request.longitude, lat, lon) * 0.000621371
        display_name = (place.get("displayName") or {}).get("text") or "Cracker Barrel"
        address = place.get("formattedAddress")
        phone = place.get("nationalPhoneNumber")
        website = place.get("websiteUri")
        hours_desc = place.get("regularOpeningHours", {}).get("weekdayDescriptions")
        hours = "; ".join(hours_desc) if hours_desc else None

        stops.append(
            OvernightStop(
                name=display_name,
                category="Cracker Barrel",
                label=display_name,
                distance_miles=distance_miles,
                latitude=lat,
                longitude=lon,
                address=address,
                phone=phone,
                website=website,
                hours=hours,
                osm_id=place.get("id"),
                notes="RV overnight parking welcome. Call ahead to confirm with manager.",
            )
        )

    stops.sort(key=lambda x: x.distance_miles)
    return stops


async def _search_boondockers_google_places(
    request: OvernightSearchRequest,
    *,
    fetch_page_fn: Optional[Callable[[Optional[str]], Awaitable[Tuple[int, Dict[str, Any]]]]] = None,
    sleep_fn: Optional[Callable[[float], Awaitable[None]]] = None,
) -> Tuple[List[OvernightStop], Dict[str, Any]]:
    """Search for boondocking-friendly spots via Google Places Nearby Search with strong dedupe/pagination.

    - Deduplicates strictly by place_id across all pages.
    - Retries next_page_token fetches with backoff to avoid premature ZERO_RESULTS.
    - Returns structured debug info on errors or empty results.
    """

    sleep_fn = sleep_fn or asyncio.sleep
    debug: Dict[str, Any] = {
        "provider": "google_places",
        "pages": [],
        "status": None,
        "reason": None,
        "request_params": {
            "lat": request.latitude,
            "lon": request.longitude,
            "radius_miles": request.radius_miles,
        },
    }

    if not GOOGLE_PLACES_API_KEY and fetch_page_fn is None:
        logger.warning("GOOGLE_PLACES_API_KEY missing for live Google Places call; returning debug-only response")
        debug.update({"status": "MISSING_API_KEY", "reason": "GOOGLE_PLACES_API_KEY not set"})
        return [], debug

    radius_meters = min(50000.0, float(request.radius_miles * 1609.34))
    url = "https://places.googleapis.com/v1/places:searchNearby"
    base_body = {
        "locationRestriction": {
            "circle": {
                "center": {"latitude": request.latitude, "longitude": request.longitude},
                "radius": float(radius_meters),
            }
        },
        "includedTypes": ["campground", "rv_park"],
        "maxResultCount": 20,
        "rankPreference": "DISTANCE",
        "languageCode": "en",
    }
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_PLACES_API_KEY,
        "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress,places.location,places.nationalPhoneNumber,places.websiteUri,places.regularOpeningHours",
    }

    async def _default_fetch(page_token: Optional[str]) -> Tuple[int, Dict[str, Any]]:
        body: Dict[str, Any] = {"pageToken": page_token} if page_token else base_body
        async with httpx.AsyncClient(timeout=12.0) as client:
            resp = await client.post(url, headers=headers, json=body)
        try:
            payload = resp.json()
        except Exception:  # noqa: BLE001
            payload = {"error": {"status": "BAD_JSON", "message": resp.text[:200]}}
        return resp.status_code, payload

    fetch_page = fetch_page_fn or _default_fetch

    seen_place_ids: Set[str] = set()
    spots: List[OvernightStop] = []
    page_token: Optional[str] = None
    pages_fetched = 0
    max_pages = 3
    token_retry_limit = 3

    while pages_fetched < max_pages:
        token_attempt = 0
        while True:
            if page_token:
                await sleep_fn(1.2 * max(1, token_attempt + 1))

            status_code, payload = await fetch_page(page_token)
            google_status = payload.get("status") or payload.get("error", {}).get("status") or "OK"
            error_message = payload.get("error", {}).get("message")

            debug["pages"].append(
                {
                    "page": pages_fetched + 1,
                    "page_token": page_token,
                    "http_status": status_code,
                    "google_status": google_status,
                    "count": len(payload.get("places") or []),
                    "error_message": error_message,
                }
            )

            token_not_ready = page_token is not None and google_status in {"INVALID_ARGUMENT", "FAILED_PRECONDITION"}
            if token_not_ready and token_attempt < token_retry_limit:
                token_attempt += 1
                continue

            if status_code >= 400:
                debug.update(
                    {
                        "status": google_status or f"HTTP_{status_code}",
                        "reason": error_message or f"HTTP_{status_code}",
                        "http_status": status_code,
                    }
                )
                logger.warning(
                    "[Boondockers][GooglePlaces] status_error code=%s gstatus=%s msg=%s",
                    status_code,
                    google_status,
                    error_message,
                )
                return [], debug

            places = payload.get("places") or []
            for place in places:
                place_id = place.get("id")
                if not place_id or place_id in seen_place_ids:
                    continue
                seen_place_ids.add(place_id)

                loc = place.get("location") or {}
                lat = loc.get("latitude")
                lon = loc.get("longitude")
                if lat is None or lon is None:
                    continue

                distance_miles = _haversine_meters(request.latitude, request.longitude, lat, lon) * 0.000621371
                display_name = (place.get("displayName") or {}).get("text") or "Boondocking"
                address = place.get("formattedAddress")
                phone = place.get("nationalPhoneNumber")
                website = place.get("websiteUri")
                hours_desc = place.get("regularOpeningHours", {}).get("weekdayDescriptions")
                hours = "; ".join(hours_desc) if hours_desc else None

                spots.append(
                    OvernightStop(
                        name=display_name,
                        category="Boondockers",
                        label=display_name,
                        distance_miles=distance_miles,
                        latitude=lat,
                        longitude=lon,
                        address=address,
                        phone=phone,
                        website=website,
                        hours=hours,
                        osm_id=f"google:{place_id}",
                        notes="Free or low-cost camping; verify onsite policies.",
                    )
                )

            pages_fetched += 1
            page_token = payload.get("nextPageToken") if payload.get("nextPageToken") else None
            break

        if not page_token:
            break

    debug.update(
        {
            "status": debug.get("status") or ("OK" if spots else "ZERO_RESULTS"),
            "reason": debug.get("reason") or ("No places returned" if not spots else None),
            "unique_place_ids": len(seen_place_ids),
        }
    )

    return spots, debug


@api_router.post("/casinos/search", response_model=OvernightSearchResponse)
async def search_casinos(request: OvernightSearchRequest):
    try:
        radius_meters = int(request.radius_miles * 1609.34)
        overpass_query = f"""
        [out:json][timeout:25];
        (
          node["amenity"="casino"](around:{radius_meters},{request.latitude},{request.longitude});
          way["amenity"="casino"](around:{radius_meters},{request.latitude},{request.longitude});
                    node["leisure"="casino"](around:{radius_meters},{request.latitude},{request.longitude});
                    way["leisure"="casino"](around:{radius_meters},{request.latitude},{request.longitude});
        );
        out body;
        >;
        out skel qt;
        """

        osm_data = await _fetch_overpass_data(overpass_query, "Casinos")

        stops: List[OvernightStop] = []
        for element in osm_data.get("elements", []):
            stop = _build_stop(element, request, "Casino", "Free overnight RV parking welcome.")
            if stop:
                stop.osm_id = None  # Deduplicate node/way duplicates by coordinates instead of OSM id.
                stops.append(stop)

        def _casino_score(stop: OvernightStop) -> int:
            score = 0
            if stop.name and stop.name.lower() not in GENERIC_PLACEHOLDERS:
                score += 2
            if stop.address:
                score += 1
            if stop.phone or stop.website:
                score += 1
            return score

        def _casino_key(stop: OvernightStop) -> Optional[str]:
            return _stable_place_key(stop.name, stop.latitude, stop.longitude, place_id=None, source_id=None, precision=3)

        def _prefer_casino(cand: OvernightStop, curr: OvernightStop) -> bool:
            c_score = _casino_score(cand)
            o_score = _casino_score(curr)
            if c_score != o_score:
                return c_score > o_score
            if cand.distance_miles != curr.distance_miles:
                return cand.distance_miles < curr.distance_miles
            return len(cand.name or "") > len(curr.name or "")

        primary = _dedupe_places(stops, _casino_key, _prefer_casino)

        merged: List[OvernightStop] = []
        for stop in primary:
            merged_into_existing = False
            for idx, existing in enumerate(merged):
                if _haversine_meters(stop.latitude, stop.longitude, existing.latitude, existing.longitude) <= 250:
                    if _prefer_casino(stop, existing):
                        merged[idx] = stop
                    merged_into_existing = True
                    break
            if not merged_into_existing:
                merged.append(stop)

        stops = sorted(merged, key=lambda x: x.distance_miles)
        return OvernightSearchResponse(
            spots=_dedupe_and_limit(stops),
            is_premium_locked=False,
            ok=True,
            source="overpass",
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Casino search using Overpass failed: %s", exc)
        return _empty_overpass_response()


# ==================== Walmart Overnight Parking ====================

@api_router.post("/walmart-parking/search", response_model=OvernightSearchResponse)
async def search_walmart_parking(request: OvernightSearchRequest):
    try:
        logger.info(
            "Walmart search start",
            extra={
                "lat": request.latitude,
                "lon": request.longitude,
                "radius_miles": request.radius_miles,
                "source": "google_places",
            },
        )

        stops = await _search_walmart_google_places(request)
        logger.info(
            "Walmart search complete",
            extra={
                "count": len(stops),
                "radius_miles": request.radius_miles,
                "source": "google_places",
            },
        )
        return OvernightSearchResponse(
            spots=_dedupe_and_limit(stops),
            is_premium_locked=False,
            ok=True,
            source="google_places",
        )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Walmart search failed",
            exc_info=exc,
            extra={
                "lat": request.latitude,
                "lon": request.longitude,
                "radius_miles": request.radius_miles,
                "source": "google_places",
            },
        )
        raise HTTPException(status_code=503, detail="Walmart search temporarily unavailable")


# Alias to support /api/walmart/search
@api_router.post("/walmart/search", response_model=OvernightSearchResponse)
async def search_walmart(request: OvernightSearchRequest):
    return await search_walmart_parking(request)


# ==================== Cracker Barrel Overnight ====================

_last_cracker_barrel_cache: Dict[str, Any] = {"ts": 0.0, "spots": []}

@api_router.post("/cracker-barrel/search", response_model=OvernightSearchResponse)
async def search_cracker_barrel(request: OvernightSearchRequest):
    request_id = uuid.uuid4().hex[:8]
    started = time.time()

    try:
        stops = await _search_cracker_barrel_google_places(request)
        source = "google_places"
    except HTTPException:
        logger.info("[CrackerBarrel][%s] falling back to Overpass", request_id)
        radius_meters = int(request.radius_miles * 1609.34)
        overpass_query = f"""
        [out:json][timeout:10];
        (
                    node["amenity"="restaurant"]["name"~"Cracker Barrel",i](around:{radius_meters},{request.latitude},{request.longitude});
                    way["amenity"="restaurant"]["name"~"Cracker Barrel",i](around:{radius_meters},{request.latitude},{request.longitude});
                    node["brand"~"Cracker Barrel",i](around:{radius_meters},{request.latitude},{request.longitude});
                    way["brand"~"Cracker Barrel",i](around:{radius_meters},{request.latitude},{request.longitude});
        );
        out body;
        >;
        out skel qt;
        """
        try:
            osm_data = await _fetch_overpass_first_success(
                overpass_query,
                "CrackerBarrel",
                [
                    "https://overpass-api.de/api/interpreter",
                    "https://lz4.overpass-api.de/api/interpreter",
                    "https://z.overpass-api.de/api/interpreter",
                ],
                overall_timeout=9.0,
                per_timeout=3.5,
                request_id=request_id,
            )
            stops = []
            for element in osm_data.get("elements", []):
                stop = _build_stop(
                    element,
                    request,
                    "Cracker Barrel",
                    "RV overnight parking welcome. Call ahead to confirm with manager.",
                )
                if stop:
                    stop.osm_id = None
                    stops.append(stop)
            source = "overpass_fallback"
        except Exception as exc2:  # noqa: BLE001
            logger.warning("[CrackerBarrel][%s] overpass fallback failed: %s", request_id, exc2)
            return _empty_overpass_response(source="google_places_unavailable")
    except Exception as exc:  # noqa: BLE001
        elapsed_ms = int((time.time() - started) * 1000)
        logger.warning("[CrackerBarrel][%s] unexpected failure after %dms: %s", request_id, elapsed_ms, exc)
        cache = globals().get("_last_cracker_barrel_cache", {})
        now = time.time()
        cached_spots = cache.get("spots") or []
        cached_ts = cache.get("ts", 0)
        if cached_spots and now - cached_ts < 3600:
            logger.info("[CrackerBarrel][%s] using cached fallback %d spots", request_id, len(cached_spots))
            return OvernightSearchResponse(
                spots=cached_spots,
                is_premium_locked=False,
                ok=True,
                source="cached_fallback",
                error="google_places_unavailable",
            )

        return OvernightSearchResponse(
            spots=[],
            is_premium_locked=False,
            ok=True,
            source="google_places_unavailable",
            error="google_places_unavailable",
        )

    deduped = _dedupe_and_limit(stops)
    globals()["_last_cracker_barrel_cache"] = {"ts": time.time(), "spots": deduped}

    elapsed_ms = int((time.time() - started) * 1000)
    logger.info("[CrackerBarrel][%s] returning %d stops source=%s elapsed_ms=%d", request_id, len(deduped), source, elapsed_ms)

    return OvernightSearchResponse(
        spots=deduped,
        is_premium_locked=False,
        ok=True,
        source=source,
    )


# ==================== Boondockers Overnight (alias to free/low-cost camping) ====================

@api_router.post("/boondockers/search", response_model=OvernightSearchResponse)
async def search_boondockers(request: OvernightSearchRequest):
    google_debug: Dict[str, Any] = {}
    try:
        if not GOOGLE_PLACES_API_KEY:
            google_debug = {
                "provider": "google_places",
                "status": "MISSING_API_KEY",
                "reason": "GOOGLE_PLACES_API_KEY not set",
                "pages": [],
                "request_params": {"lat": request.latitude, "lon": request.longitude, "radius_miles": request.radius_miles},
            }
        else:
            google_spots, google_debug = await _search_boondockers_google_places(request)
            if google_spots:
                deduped = _dedupe_and_limit(google_spots)
                return OvernightSearchResponse(
                    spots=deduped,
                    is_premium_locked=False,
                    ok=True,
                    source="google_places",
                    debug=google_debug,
                )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.warning("Boondockers Google Places failed: %s", exc)
        google_debug = {"status": "EXCEPTION", "reason": str(exc)}

    # Fallback to Overpass so the endpoint never silently returns empty without context.
    overpass_debug: Dict[str, Any] = {"google_places": google_debug}
    try:
        radius_meters = int(request.radius_miles * 1609.34)
        overpass_query = f"""
        [out:json][timeout:25];
        (
          node["tourism"="camp_site"](around:{radius_meters},{request.latitude},{request.longitude});
          node["tourism"="caravan_site"](around:{radius_meters},{request.latitude},{request.longitude});
          way["tourism"="camp_site"](around:{radius_meters},{request.latitude},{request.longitude});
          way["tourism"="caravan_site"](around:{radius_meters},{request.latitude},{request.longitude});
        );
        out body;
        >;
        out skel qt;
        """

        osm_data = await _fetch_overpass_data(overpass_query, "Boondockers")

        stops: List[OvernightStop] = []
        for element in osm_data.get("elements", []):
            stop = _build_stop(
                element,
                request,
                "Boondocker Camping",
                "Dispersed camping or low-cost overnight spot.",
            )
            if stop:
                stops.append(stop)

        stops.sort(key=lambda x: x.distance_miles)
        return OvernightSearchResponse(
            spots=_dedupe_and_limit(stops),
            is_premium_locked=False,
            ok=True,
            source="overpass",
            debug=overpass_debug,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Boondockers search using Overpass failed: %s", exc)
        overpass_debug.update({"status": "OVERPASS_FAILED", "reason": str(exc)})
        if isinstance(exc, OverpassError):
            overpass_debug["attempts"] = exc.attempts
        return OvernightSearchResponse(
            spots=[],
            is_premium_locked=False,
            ok=True,
            source="overpass",
            error="overpass_unavailable",
            debug=overpass_debug,
        )


# ==================== Last Chance Supply Finder Endpoint ====================

@api_router.post("/last-chance/search", response_model=LastChanceResponse)
async def search_last_chance_supplies(request: LastChanceRequest):
    """Find grocery stores, propane refill, and hardware stores near given coordinates using OpenStreetMap data."""
    # TESTING: Paywalls disabled - require_premium(request.subscription_id, CAMPSITE_INDEX)  # Reuse campsite_index feature
    
    try:
        # Convert miles to meters for Overpass API
        radius_meters = int(request.radius_miles * 1609.34)
        
        # Query OpenStreetMap for grocery, propane, and hardware
        overpass_query = f"""
        [out:json][timeout:30];
        (
          node["shop"="supermarket"](around:{radius_meters},{request.latitude},{request.longitude});
          node["shop"="convenience"](around:{radius_meters},{request.latitude},{request.longitude});
          node["shop"="general"](around:{radius_meters},{request.latitude},{request.longitude});
          node["shop"="hardware"](around:{radius_meters},{request.latitude},{request.longitude});
          node["shop"="doityourself"](around:{radius_meters},{request.latitude},{request.longitude});
          node["amenity"="fuel"]["fuel:lpg"="yes"](around:{radius_meters},{request.latitude},{request.longitude});
          way["shop"="supermarket"](around:{radius_meters},{request.latitude},{request.longitude});
          way["shop"="hardware"](around:{radius_meters},{request.latitude},{request.longitude});
          way["amenity"="fuel"]["fuel:lpg"="yes"](around:{radius_meters},{request.latitude},{request.longitude});
        );
        out body;
        >;
        out skel qt;
        """
        
        async with httpx.AsyncClient(timeout=45.0) as client:
            # Try multiple Overpass API instances
            overpass_urls = [
                "https://overpass-api.de/api/interpreter",
                "https://overpass.kumi.systems/api/interpreter",
            ]
            
            osm_data = None
            last_error = None
            
            for url in overpass_urls:
                try:
                    osm_response = await client.post(url, data=overpass_query)
                    osm_response.raise_for_status()
                    osm_data = osm_response.json()
                    break
                except Exception as e:
                    last_error = e
                    logger.warning(f"Last chance - Overpass instance {url} failed: {e}")
                    continue
            
            if osm_data is None:
                raise last_error or Exception("All Overpass instances failed")
        
        supplies = []
        seen_coords = set()
        
        for element in osm_data.get("elements", []):
            # Get coordinates
            if element.get("type") == "node":
                lat = element.get("lat")
                lon = element.get("lon")
            elif element.get("type") == "way" and "center" in element:
                lat = element["center"].get("lat")
                lon = element["center"].get("lon")
            else:
                continue
            
            if not lat or not lon:
                continue
            
            # Avoid duplicates
            coord_key = (round(lat, 4), round(lon, 4))
            if coord_key in seen_coords:
                continue
            seen_coords.add(coord_key)
            
            # Calculate distance
            distance_miles = math.sqrt(
                (lat - request.latitude) ** 2 + (lon - request.longitude) ** 2
            ) * 69.0
            
            tags = element.get("tags", {})

            # Determine type and subtype first (needed for name fallback)
            shop_type = tags.get("shop", "")
            amenity = tags.get("amenity", "")

            supply_type = "Grocery"
            subtype = "Store"

            if shop_type == "supermarket":
                supply_type = "Grocery"
                subtype = "Supermarket"
            elif shop_type == "convenience":
                supply_type = "Grocery"
                subtype = "Convenience Store"
            elif shop_type == "general":
                supply_type = "Grocery"
                subtype = "General Store"
            elif shop_type in ["hardware", "doityourself"]:
                supply_type = "Hardware"
                subtype = "Hardware Store" if shop_type == "hardware" else "Home Improvement"
            elif amenity == "fuel" and tags.get("fuel:lpg") == "yes":
                supply_type = "Propane"
                subtype = "Gas Station"

            # Extract name with better fallbacks
            base_label = subtype or supply_type
            city_hint = (
                tags.get("addr:city")
                or tags.get("addr:place")
                or tags.get("addr:town")
                or tags.get("addr:village")
            )
            street_line = None
            if tags.get("addr:housenumber") and tags.get("addr:street"):
                street_line = f"{tags.get('addr:housenumber')} {tags.get('addr:street')}"
            elif tags.get("addr:street"):
                street_line = tags.get("addr:street")

            name = None
            for candidate in [
                tags.get("name"),
                tags.get("brand"),
                tags.get("operator"),
                tags.get("official_name"),
                tags.get("alt_name"),
                tags.get("short_name"),
                tags.get("loc_name"),
                tags.get("branch"),
            ]:
                if candidate and candidate.strip().lower() not in GENERIC_PLACEHOLDERS:
                    name = candidate.strip()
                    break

            if not name:
                if street_line and city_hint:
                    name = f"{base_label} - {street_line}, {city_hint}"
                elif street_line:
                    name = f"{base_label} - {street_line}"
                elif city_hint:
                    name = f"{base_label} - {city_hint}"
                elif supply_type == "Propane":
                    name = f"{base_label} near ({round(lat, 3)}, {round(lon, 3)})"
                else:
                    # Skip unlabeled points that would appear as generic "Store"
                    continue

            # Add propane indicator if applicable
            if supply_type == "Propane" and "propane" not in name.lower() and "lpg" not in name.lower():
                name = f"{name} (Propane Available)"
            
            # Extract amenities
            amenities = []
            if tags.get("fuel:lpg") == "yes":
                amenities.append("Propane/LPG Refill")
            if tags.get("atm") == "yes":
                amenities.append("ATM")
            if tags.get("fuel:diesel") == "yes":
                amenities.append("Diesel")
            if tags.get("fuel") == "yes" or amenity == "fuel":
                amenities.append("Fuel")
            if tags.get("toilets") == "yes":
                amenities.append("Restrooms")
            if tags.get("wifi") == "yes":
                amenities.append("WiFi")
            if supply_type == "Grocery" and not amenities:
                amenities.append("Groceries & Supplies")
            if supply_type == "Hardware" and not amenities:
                amenities.append("Tools & Repair Parts")
            
            # Hours
            hours = tags.get("opening_hours") or "Call for hours"
            
            # Phone
            phone = tags.get("phone") or tags.get("contact:phone") or "N/A"
            
            # Website
            website = tags.get("website") or tags.get("contact:website") or tags.get("url")
            
            # Extract address
            address_parts = []
            if tags.get("addr:housenumber") and tags.get("addr:street"):
                address_parts.append(f"{tags.get('addr:housenumber')} {tags.get('addr:street')}")
            elif tags.get("addr:street"):
                address_parts.append(tags.get("addr:street"))
            if tags.get("addr:city"):
                address_parts.append(tags.get("addr:city"))
            if tags.get("addr:state"):
                address_parts.append(tags.get("addr:state"))
            if tags.get("addr:postcode"):
                address_parts.append(tags.get("addr:postcode"))
            address = ", ".join(address_parts) if address_parts else None

            formatted_address = address
            vicinity = tags.get("addr:city") or tags.get("addr:place")
            
            # Description
            description = tags.get("description", f"{subtype} offering essential supplies")
            if supply_type == "Propane":
                description = f"Propane/LPG refill available at this location. Call ahead to confirm tank sizes and hours."
            elif supply_type == "Hardware":
                description = f"Hardware store for emergency repairs, tools, and RV/camping supplies."
            elif supply_type == "Grocery":
                description = f"Stock up on food, water, and essentials before heading into remote areas."
            
            # Rating (default)
            rating = 3.8
            
            supplies.append(SupplyPoint(
                name=name or base_label or "Store",
                title=name or None,
                type=supply_type,
                subtype=subtype,
                distance_miles=round(distance_miles, 1),
                latitude=lat,
                longitude=lon,
                description=description,
                hours=hours,
                phone=phone,
                amenities=amenities,
                rating=rating,
                address=address,
                formatted_address=formatted_address,
                vicinity=vicinity,
                website=website
            ))
        
        # Dedupe, sort, limit
        def _supply_score(supply: SupplyPoint) -> int:
            score = 0
            if supply.name and supply.name.lower() not in GENERIC_PLACEHOLDERS:
                score += 2
            if supply.address:
                score += 1
            if supply.phone and supply.phone != "N/A":
                score += 1
            if supply.website:
                score += 1
            return score

        def _supply_key(supply: SupplyPoint) -> Optional[str]:
            # If name is generic, lean more on coordinate precision to merge.
            prec = 3 if supply.name and supply.name.lower() not in GENERIC_PLACEHOLDERS else 2
            return _stable_place_key(
                supply.name,
                supply.latitude,
                supply.longitude,
                place_id=None,
                source_id=None,
                precision=prec,
            )

        def _prefer_supply(candidate: SupplyPoint, current: SupplyPoint) -> bool:
            cand_score = _supply_score(candidate)
            curr_score = _supply_score(current)
            if cand_score != curr_score:
                return cand_score > curr_score
            if candidate.distance_miles != current.distance_miles:
                return candidate.distance_miles < current.distance_miles
            return len(candidate.name or "") > len(current.name or "")

        primary = _dedupe_places(supplies, _supply_key, _prefer_supply)

        merged: List[SupplyPoint] = []
        for supply in primary:
            merged_into_existing = False
            for idx, existing in enumerate(merged):
                if _haversine_meters(
                    supply.latitude,
                    supply.longitude,
                    existing.latitude,
                    existing.longitude,
                ) <= 250:  # merge nearby node/way variants
                    if _prefer_supply(supply, existing):
                        merged[idx] = supply
                    merged_into_existing = True
                    break
            if not merged_into_existing:
                merged.append(supply)

        supplies = sorted(merged, key=lambda x: x.distance_miles)[:30]
        
        logger.info(f"Last chance supply search completed: found {len(supplies)} locations from OSM within {request.radius_miles} miles")
        
        return LastChanceResponse(
            supplies=supplies,
            is_premium_locked=False,
        )
    
    except httpx.HTTPError as e:
        logger.error(f"Overpass API error for last chance supplies: {e}")
        raise HTTPException(
            status_code=503,
            detail="Supply data service temporarily unavailable. The mapping service may be experiencing high load. Please try again in a few moments."
        )
    except Exception as e:
        logger.error(f"Error searching last chance supplies: {e}")
        raise HTTPException(
            status_code=500,
            detail="Unable to search for supply points. Please check your internet connection and try again."
        )


# ==================== RV Dealership Finder Endpoint ====================

@api_router.post("/rv-dealerships/search", response_model=RVDealershipResponse)
async def search_rv_dealerships(request: RVDealershipRequest):
    """Find RV dealerships, service centers, and parts stores near given coordinates using OpenStreetMap data."""
    # TESTING: Paywalls disabled - require_premium(request.subscription_id, CAMPSITE_INDEX)  # Reuse campsite_index feature
    
    try:
        # Convert miles to meters for Overpass API
        radius_meters = int(request.radius_miles * 1609.34)
        
        # Query OpenStreetMap for RV dealerships and services
        overpass_query = f"""
        [out:json][timeout:25];
        (
          node["shop"="car"]["car"~"rv|motorhome|caravan"](around:{radius_meters},{request.latitude},{request.longitude});
          node["shop"="caravan"](around:{radius_meters},{request.latitude},{request.longitude});
          node["amenity"="car_repair"]["service:vehicle:motorhome"="yes"](around:{radius_meters},{request.latitude},{request.longitude});
          way["shop"="car"]["car"~"rv|motorhome|caravan"](around:{radius_meters},{request.latitude},{request.longitude});
          way["shop"="caravan"](around:{radius_meters},{request.latitude},{request.longitude});
        );
        out body;
        >;
        out skel qt;
        """
        
        async with httpx.AsyncClient(timeout=45.0) as client:
            # Try multiple Overpass API instances
            overpass_urls = [
                "https://overpass-api.de/api/interpreter",
                "https://overpass.kumi.systems/api/interpreter",
            ]
            
            osm_data = None
            last_error = None
            
            for url in overpass_urls:
                try:
                    osm_response = await client.post(url, data=overpass_query)
                    osm_response.raise_for_status()
                    osm_data = osm_response.json()
                    break
                except Exception as e:
                    last_error = e
                    logger.warning(f"RV dealerships - Overpass instance {url} failed: {e}")
                    continue
            
            if osm_data is None:
                raise last_error or Exception("All Overpass instances failed")
        
        dealerships = []
        seen_keys = set()
        
        for element in osm_data.get("elements", []):
            # Get coordinates
            if element.get("type") == "node":
                lat = element.get("lat")
                lon = element.get("lon")
            elif element.get("type") == "way" and "center" in element:
                lat = element["center"].get("lat")
                lon = element["center"].get("lon")
            else:
                continue
            
            if not lat or not lon:
                continue
            
            # Calculate distance
            distance_miles = math.sqrt(
                (lat - request.latitude) ** 2 + (lon - request.longitude) ** 2
            ) * 69.0
            
            tags = element.get("tags", {})
            shop_type = tags.get("shop", "")
            
            # Extract name with better fallbacks
            name_candidates = [
                tags.get("name"),
                tags.get("brand"),
                tags.get("operator"),
                tags.get("official_name"),
                tags.get("alt_name"),
            ]
            name = next((n for n in name_candidates if n), None)
            if not name:
                craft = tags.get("craft", "")
                if "caravan" in craft or "caravan" in shop_type:
                    name = "RV Dealership"
                elif tags.get("amenity") == "car_repair":
                    name = "RV Service Center"
                elif "parts" in craft or "parts" in shop_type:
                    name = "RV Parts & Service"
                else:
                    nearest_city = tags.get("addr:city") or tags.get("addr:place")
                    name = f"RV Service near {nearest_city}" if nearest_city else "RV Service"

            osm_id = element.get("id")
            dedupe_key = _stable_place_key(name, lat, lon, place_id=osm_id, precision=3)
            if dedupe_key and dedupe_key in seen_keys:
                continue
            if dedupe_key:
                seen_keys.add(dedupe_key)
            
            # Determine type
            dealership_type = "Dealership"
            if tags.get("amenity") == "car_repair" or "repair" in tags.get("service", "").lower():
                dealership_type = "Service Center"
            elif "parts" in name.lower() or "accessories" in name.lower():
                dealership_type = "Parts & Accessories"
            
            # Extract services
            services = []
            if tags.get("service:vehicle:repair") == "yes":
                services.append("Repair Services")
            if tags.get("service:vehicle:parts") == "yes":
                services.append("Parts Sales")
            if tags.get("service:vehicle:sales") == "yes" or dealership_type == "Dealership":
                services.append("New & Used Sales")
            if tags.get("service:vehicle:maintenance") == "yes":
                services.append("Maintenance")
            if tags.get("service:vehicle:inspection") == "yes":
                services.append("Inspections")
            if not services:
                services.append("Call for services")
            
            # Extract brands (if available)
            brands = []
            brand_tag = tags.get("brand", "")
            if brand_tag:
                brands.append(brand_tag)
            
            # Hours
            hours = tags.get("opening_hours", "Call for hours")
            
            # Phone
            phone = tags.get("phone", tags.get("contact:phone", "N/A"))
            
            # Website
            website = tags.get("website") or tags.get("contact:website") or tags.get("url")
            
            # Extract address
            address_parts = []
            if tags.get("addr:housenumber") and tags.get("addr:street"):
                address_parts.append(f"{tags.get('addr:housenumber')} {tags.get('addr:street')}")
            elif tags.get("addr:street"):
                address_parts.append(tags.get("addr:street"))
            if tags.get("addr:city"):
                address_parts.append(tags.get("addr:city"))
            if tags.get("addr:state"):
                address_parts.append(tags.get("addr:state"))
            if tags.get("addr:postcode"):
                address_parts.append(tags.get("addr:postcode"))
            address = ", ".join(address_parts) if address_parts else None
            
            # Description
            description = tags.get("description", f"RV {dealership_type.lower()} offering sales and service for recreational vehicles.")
            if dealership_type == "Service Center":
                description = "Full-service RV repair and maintenance. Call ahead for emergency service availability."
            
            # Rating (default)
            rating = 3.7
            
            dealerships.append(RVDealership(
                name=name,
                type=dealership_type,
                distance_miles=round(distance_miles, 1),
                latitude=lat,
                longitude=lon,
                description=description,
                hours=hours,
                phone=phone,
                services=services,
                brands=brands,
                rating=rating,
                address=address,
                website=website
            ))
        
        # Sort by distance
        dealerships.sort(key=lambda x: x.distance_miles)
        
        # Limit to 10 results (only looking within 10 miles anyway)
        dealerships = dealerships[:10]
        
        logger.info(f"RV dealership search completed: found {len(dealerships)} dealerships from OSM within {request.radius_miles} miles")
        
        return RVDealershipResponse(
            dealerships=dealerships,
            is_premium_locked=False,
        )
    
    except httpx.HTTPError as e:
        logger.error(f"Overpass API error for RV dealerships: {e}")
        raise HTTPException(
            status_code=503,
            detail="RV dealership data service temporarily unavailable. The mapping service may be experiencing high load. Please try again in a few moments."
        )
    except Exception as e:
        logger.error(f"Error searching RV dealerships: {e}")
        raise HTTPException(
            status_code=500,
            detail="Unable to search for RV dealerships. Please check your internet connection and try again."
        )


# ==================== TRACTOR TRAILER ENDPOINTS ====================

# Helper function for distance calculations
def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance in miles between two lat/lon points using Haversine formula."""
    from math import radians, cos, sin, asin, sqrt
    
    # Convert to radians
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    
    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    
    # Radius of earth in miles
    miles = 3956 * c
    return miles

# Truck Stops & Fuel
class TruckStopRequest(BaseModel):
    latitude: float
    longitude: float
    radius_miles: int = 10  # Reduced to prevent timeout
    subscription_id: Optional[str] = None

class TruckStop(BaseModel):
    name: str
    brand: Optional[str] = None
    distance_miles: float
    latitude: float
    longitude: float
    amenities: List[str]
    fuel_types: List[str]
    services: List[str]
    rating: Optional[float] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    hours: Optional[str] = None

class TruckStopResponse(BaseModel):
    stops: List[TruckStop]

@api_router.post("/truck-stops/search", response_model=TruckStopResponse)
async def search_truck_stops(request: TruckStopRequest):
    """Find truck stops with fuel and amenities using OpenStreetMap."""
    # TESTING: Paywalls disabled - require_premium(request.subscription_id, TRUCK_STOPS)
    try:
        radius_meters = int(request.radius_miles * 1609.34)
        
        # Query for truck stops, gas stations with HGV fuel, and service areas
        overpass_query = f"""
        [out:json][timeout:40];
        (
          node["amenity"="fuel"]["hgv"="yes"](around:{radius_meters},{request.latitude},{request.longitude});
          node["amenity"="fuel"]["hgv:diesel"="yes"](around:{radius_meters},{request.latitude},{request.longitude});
          node["highway"="services"]["fuel"="yes"](around:{radius_meters},{request.latitude},{request.longitude});
          way["amenity"="fuel"]["hgv"="yes"](around:{radius_meters},{request.latitude},{request.longitude});
          way["amenity"="fuel"]["hgv:diesel"="yes"](around:{radius_meters},{request.latitude},{request.longitude});
          way["highway"="services"]["fuel"="yes"](around:{radius_meters},{request.latitude},{request.longitude});
        );
        out center;
        """
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post("https://overpass-api.de/api/interpreter", data=overpass_query)
            response.raise_for_status()
            data = response.json()
        
        stops = []
        for element in data.get('elements', []):
            tags = element.get('tags', {})
            
            # Get coordinates
            if element['type'] == 'way':
                lat = element.get('center', {}).get('lat', 0)
                lon = element.get('center', {}).get('lon', 0)
            else:
                lat = element.get('lat', 0)
                lon = element.get('lon', 0)
            
            if not lat or not lon:
                continue
            
            distance = haversine_miles(request.latitude, request.longitude, lat, lon)
            
            # Get name and brand
            name = tags.get('name', tags.get('brand', 'Truck Stop'))
            brand = tags.get('brand', tags.get('operator', 'Independent'))
            
            # Determine amenities
            amenities = []
            if tags.get('fuel:diesel') == 'yes' or tags.get('hgv:diesel') == 'yes' or tags.get('hgv') == 'yes':
                amenities.append('Diesel Fuel')
            if tags.get('fuel:HGV_diesel') == 'yes':
                amenities.append('DEF')
            if tags.get('truck_parking') == 'yes' or tags.get('hgv') == 'yes':
                amenities.append('Truck Parking')
            if tags.get('toilets') == 'yes':
                amenities.append('Restrooms')
            if tags.get('restaurant') == 'yes' or tags.get('food') == 'yes':
                amenities.append('Food')
            if tags.get('shower') == 'yes':
                amenities.append('Showers')
            
            # Fuel types
            fuel_types = ['Diesel']
            if tags.get('fuel:HGV_diesel') == 'yes':
                fuel_types.append('DEF')
            
            # Services
            services = []
            if tags.get('wifi') == 'yes':
                services.append('WiFi')
            if tags.get('car_wash') == 'yes':
                services.append('Truck Wash')
            if tags.get('repair') == 'yes':
                services.append('Repair')
            
            # Hours
            hours = tags.get('opening_hours', '24/7' if tags.get('24/7') == 'yes' else None)
            
            stops.append(TruckStop(
                name=name,
                brand=brand,
                distance_miles=round(distance, 1),
                latitude=lat,
                longitude=lon,
                amenities=amenities if amenities else ['Diesel Fuel'],
                fuel_types=fuel_types,
                services=services if services else ['WiFi'],
                phone=tags.get('phone'),
                website=tags.get('website'),
                hours=hours,
            ))
        
        stops = _dedupe_items(
            stops,
            lambda s: _stable_place_key(s.name, s.latitude, s.longitude, precision=4),
            lambda cand, curr: cand.distance_miles < curr.distance_miles,
        )

        stops.sort(key=lambda x: x.distance_miles)
        stops = stops[:30]
        
        logger.info(f"✓ Found {len(stops)} truck stops within {request.radius_miles} miles")
        return TruckStopResponse(stops=stops)
    
    except Exception as e:
        logger.error(f"Error searching truck stops: {e}")
        raise HTTPException(status_code=500, detail=f"Error searching truck stops: {str(e)}")


# Truck Parking
class TruckParkingRequest(BaseModel):
    latitude: float
    longitude: float
    radius_miles: int = 15  # Reduce default radius to prevent timeout
    subscription_id: Optional[str] = None

class ParkingSpot(BaseModel):
    name: str
    type: str  # 'rest_area', 'parking_lot', 'truck_stop'
    distance_miles: float
    latitude: float
    longitude: float
    capacity: Optional[int] = None
    amenities: List[str]
    restrictions: List[str]
    hours: Optional[str] = None
    fee: Optional[str] = None

class TruckParkingResponse(BaseModel):
    spots: List[ParkingSpot]

@api_router.post("/truck-parking/search", response_model=TruckParkingResponse)
async def search_truck_parking(request: TruckParkingRequest):
    """Find truck parking including rest areas and safe parking zones."""
    # TESTING: Paywalls disabled - require_premium(request.subscription_id, TRUCK_PARKING)
    try:
        radius_meters = int(request.radius_miles * 1609.34)
        
        # Simplified query - nodes only to prevent timeout
        overpass_query = f"""
        [out:json][timeout:15];
        (
          node["highway"="rest_area"](around:{radius_meters},{request.latitude},{request.longitude});
          node["highway"="services"](around:{radius_meters},{request.latitude},{request.longitude});
          node["amenity"="parking"]["hgv"="yes"](around:{radius_meters},{request.latitude},{request.longitude});
          node["amenity"="parking"]["parking"="truck_stop"](around:{radius_meters},{request.latitude},{request.longitude});
        );
        out body;
        """
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post("https://overpass-api.de/api/interpreter", data=overpass_query)
            response.raise_for_status()
            data = response.json()
        
        spots = []
        for element in data.get('elements', []):
            if element['type'] != 'node':
                continue
            
            tags = element.get('tags', {})
            lat = element.get('lat', 0)
            lon = element.get('lon', 0)
            
            distance = haversine_miles(request.latitude, request.longitude, lat, lon)
            
            # Determine type
            highway = tags.get('highway')
            amenity = tags.get('amenity')
            if highway == 'rest_area':
                spot_type = 'rest_area'
            elif highway == 'services':
                spot_type = 'rest_area'
            elif amenity == 'parking':
                spot_type = 'parking_lot'
            else:
                spot_type = 'truck_stop'
            
            # Amenities
            amenities = []
            if tags.get('toilets') == 'yes':
                amenities.append('Restrooms')
            if tags.get('drinking_water') == 'yes':
                amenities.append('Water')
            if tags.get('shower') == 'yes':
                amenities.append('Showers')
            if tags.get('picnic_table') == 'yes':
                amenities.append('Picnic Area')
            if tags.get('wifi') == 'yes':
                amenities.append('WiFi')
            
            # Restrictions
            restrictions = []
            max_stay = tags.get('maxstay')
            if max_stay:
                restrictions.append(f'Max stay: {max_stay}')
            if tags.get('supervised') == 'yes':
                restrictions.append('Supervised')
            
            # Capacity
            capacity = None
            if tags.get('capacity:hgv'):
                try:
                    capacity = int(tags.get('capacity:hgv'))
                except:
                    pass
            elif tags.get('capacity:disabled'):
                try:
                    capacity = int(tags.get('capacity')) - int(tags.get('capacity:disabled'))
                except:
                    pass
            
            # Fee
            fee = None
            if tags.get('fee') == 'yes':
                fee = tags.get('charge') or 'Paid parking'
            elif tags.get('fee') == 'no':
                fee = 'Free'
            
            spots.append(ParkingSpot(
                name=tags.get('name', f'Rest Area ({spot_type})'),
                type=spot_type,
                distance_miles=round(distance, 1),
                latitude=lat,
                longitude=lon,
                capacity=capacity,
                amenities=amenities,
                restrictions=restrictions,
                hours=tags.get('opening_hours'),
                fee=fee,
            ))
        
        spots = _dedupe_items(
            spots,
            lambda s: _stable_place_key(s.name, s.latitude, s.longitude, precision=4),
            lambda cand, curr: cand.distance_miles < curr.distance_miles,
        )

        spots.sort(key=lambda x: x.distance_miles)
        spots = spots[:20]
        
        logger.info(f"Found {len(spots)} truck parking spots within {request.radius_miles} miles")
        return TruckParkingResponse(spots=spots)
    
    except Exception as e:
        logger.error(f"Error searching truck parking: {e}")
        raise HTTPException(status_code=500, detail=f"Error searching truck parking: {str(e)}")


# Truck Services
class TruckServiceRequest(BaseModel):
    latitude: float
    longitude: float
    radius_miles: int = 25

class TruckService(BaseModel):
    name: str
    service_type: str  # 'repair', 'tire', 'wash', 'scale'
    distance_miles: float
    latitude: float
    longitude: float
    services_offered: List[str]
    brands_serviced: List[str]
    phone: Optional[str] = None
    website: Optional[str] = None
    hours: Optional[str] = None

class TruckServiceResponse(BaseModel):
    services: List[TruckService]

@api_router.post("/truck-services/search", response_model=TruckServiceResponse)
async def search_truck_services(request: TruckServiceRequest):
    """Find truck repair shops, tire services, washes, and scales."""
    try:
        radius_meters = int(request.radius_miles * 1609.34)
        
        # Simplified query - look for general automotive services
        overpass_query = f"""
        [out:json][timeout:15];
        (
          node["shop"="car_repair"](around:{radius_meters},{request.latitude},{request.longitude});
          node["shop"="tyres"](around:{radius_meters},{request.latitude},{request.longitude});
          node["amenity"="car_wash"](around:{radius_meters},{request.latitude},{request.longitude});
          node["amenity"="weighbridge"](around:{radius_meters},{request.latitude},{request.longitude});
        );
        out center;
        """
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post("https://overpass-api.de/api/interpreter", data=overpass_query)
            response.raise_for_status()
            data = response.json()
        
        services = []
        for element in data.get('elements', []):
            if element['type'] != 'node':
                continue
            
            tags = element.get('tags', {})
            lat = element.get('lat', 0)
            lon = element.get('lon', 0)
            
            distance = haversine_miles(request.latitude, request.longitude, lat, lon)
            
            # Determine service type
            shop = tags.get('shop')
            amenity = tags.get('amenity')
            if shop == 'car_repair':
                service_type = 'repair'
            elif shop == 'tyres':
                service_type = 'tire'
            elif amenity == 'car_wash':
                service_type = 'wash'
            elif amenity == 'weighbridge':
                service_type = 'scale'
            else:
                service_type = 'repair'
            
            # Services offered
            services_offered = []
            if service_type == 'repair':
                if tags.get('service:vehicle:engine_repair') == 'yes':
                    services_offered.append('Engine Repair')
                if tags.get('service:vehicle:brakes') == 'yes':
                    services_offered.append('Brakes')
                if tags.get('service:vehicle:electrical') == 'yes':
                    services_offered.append('Electrical')
                if tags.get('service:vehicle:tyres') == 'yes':
                    services_offered.append('Tires')
                if not services_offered:
                    services_offered.append('General Repair')
            elif service_type == 'tire':
                services_offered = ['Tire Sales', 'Tire Repair', 'Tire Service']
            elif service_type == 'wash':
                services_offered = ['Truck Wash', 'Detailing']
            elif service_type == 'scale':
                services_offered = ['CAT Scale', 'Weighing']
            
            services.append(TruckService(
                name=tags.get('name', f'Truck {service_type.title()} Service'),
                service_type=service_type,
                distance_miles=round(distance, 1),
                latitude=lat,
                longitude=lon,
                services_offered=services_offered,
                brands_serviced=[],
                phone=tags.get('phone'),
                website=tags.get('website'),
                hours=tags.get('opening_hours'),
            ))
        
        services = _dedupe_items(
            services,
            lambda s: _stable_place_key(s.name, s.latitude, s.longitude, precision=4),
            lambda cand, curr: cand.distance_miles < curr.distance_miles,
        )

        services.sort(key=lambda x: x.distance_miles)
        services = services[:15]
        
        logger.info(f"Found {len(services)} truck services within {request.radius_miles} miles")
        return TruckServiceResponse(services=services)
    
    except Exception as e:
        logger.error(f"Error searching truck services: {e}")
        raise HTTPException(status_code=500, detail=f"Error searching truck services: {str(e)}")


# Weigh Stations
class WeighStationRequest(BaseModel):
    latitude: float
    longitude: float
    radius_miles: int = 100

class WeighStation(BaseModel):
    name: str
    distance_miles: float
    latitude: float
    longitude: float
    direction: Optional[str] = None
    status: str  # 'unknown', 'open', 'closed'
    bypass_available: bool
    phone: Optional[str] = None

class WeighStationResponse(BaseModel):
    stations: List[WeighStation]

@api_router.post("/weigh-stations/search", response_model=WeighStationResponse)
async def search_weigh_stations(request: WeighStationRequest):
    """Find weigh stations along highways."""
    try:
        radius_meters = int(request.radius_miles * 1609.34)
        
        overpass_query = f"""
        [out:json][timeout:40];
        (
          node["amenity"="weighbridge"](around:{radius_meters},{request.latitude},{request.longitude});
          node["amenity"="weigh_station"](around:{radius_meters},{request.latitude},{request.longitude});
          way["amenity"="weighbridge"](around:{radius_meters},{request.latitude},{request.longitude});
          way["amenity"="weigh_station"](around:{radius_meters},{request.latitude},{request.longitude});
        );
        out body;
        >;
        out skel qt;
        """
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post("https://overpass-api.de/api/interpreter", data=overpass_query)
            response.raise_for_status()
            data = response.json()
        
        stations = []
        for element in data.get('elements', []):
            if element['type'] not in ['node', 'way']:
                continue
            
            tags = element.get('tags', {})
            if element['type'] == 'way':
                lat = element.get('center', {}).get('lat') or (element.get('bounds', {}).get('minlat', 0) + element.get('bounds', {}).get('maxlat', 0)) / 2
                lon = element.get('center', {}).get('lon') or (element.get('bounds', {}).get('minlon', 0) + element.get('bounds', {}).get('maxlon', 0)) / 2
            else:
                lat = element.get('lat', 0)
                lon = element.get('lon', 0)
            
            distance = haversine_miles(request.latitude, request.longitude, lat, lon)
            
            # Status (would need real-time feed for actual status)
            status = 'unknown'
            bypass = tags.get('prepass') == 'yes' or tags.get('bypass') == 'yes'
            
            stations.append(WeighStation(
                name=tags.get('name', 'Weigh Station'),
                distance_miles=round(distance, 1),
                latitude=lat,
                longitude=lon,
                direction=tags.get('direction'),
                status=status,
                bypass_available=bypass,
                phone=tags.get('phone'),
            ))
        
        stations = _dedupe_items(
            stations,
            lambda s: _stable_place_key(s.name, s.latitude, s.longitude, precision=4),
            lambda cand, curr: cand.distance_miles < curr.distance_miles,
        )

        stations.sort(key=lambda x: x.distance_miles)
        stations = stations[:10]
        
        logger.info(f"Found {len(stations)} weigh stations within {request.radius_miles} miles")
        return WeighStationResponse(stations=stations)
    
    except Exception as e:
        logger.error(f"Error searching weigh stations: {e}")
        raise HTTPException(status_code=500, detail=f"Error searching weigh stations: {str(e)}")


# Truck Restrictions
class TruckRestrictionRequest(BaseModel):
    latitude: float
    longitude: float
    radius_miles: int = 25
    subscription_id: Optional[str] = None

class TruckRestriction(BaseModel):
    name: str
    type: str  # 'weight', 'height', 'width', 'hazmat', 'truck_ban', 'tunnel'
    distance_miles: float
    latitude: float
    longitude: float
    restriction: str
    value: Optional[str] = None
    details: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None

class TruckRestrictionResponse(BaseModel):
    restrictions: List[TruckRestriction]

@api_router.post("/truck-restrictions/search", response_model=TruckRestrictionResponse)
async def search_truck_restrictions(request: TruckRestrictionRequest):
    """Find roads with truck restrictions using OpenStreetMap."""
    # TESTING: Paywalls disabled - require_premium(request.subscription_id, TRUCK_RESTRICTIONS)
    try:
        radius_meters = int(request.radius_miles * 1609.34)
        
        # Query for various truck restrictions
        overpass_query = f"""
        [out:json][timeout:20];
        (
          way["maxweight"](around:{radius_meters},{request.latitude},{request.longitude});
          way["maxheight"](around:{radius_meters},{request.latitude},{request.longitude});
          way["maxwidth"](around:{radius_meters},{request.latitude},{request.longitude});
          way["hgv"="no"](around:{radius_meters},{request.latitude},{request.longitude});
          way["hazmat"="no"](around:{radius_meters},{request.latitude},{request.longitude});
          way["tunnel"="yes"]["maxheight"](around:{radius_meters},{request.latitude},{request.longitude});
        );
        out center;
        """
        
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post("https://overpass-api.de/api/interpreter", data=overpass_query)
            response.raise_for_status()
            data = response.json()
        
        restrictions = []
        
        for element in data.get('elements', []):
            if element['type'] != 'way':
                continue
            
            tags = element.get('tags', {})
            center = element.get('center', {})
            lat = center.get('lat', 0)
            lon = center.get('lon', 0)
            
            if not lat or not lon:
                continue
            
            distance = haversine_miles(request.latitude, request.longitude, lat, lon)
            name = tags.get('name', tags.get('ref', 'Unnamed Road'))
            
            # Skip geocoding to avoid rate limit timeouts
            city = None
            state = None
            
            # Check for weight restrictions
            if 'maxweight' in tags:
                restrictions.append(TruckRestriction(
                    name=name,
                    type='weight',
                    distance_miles=round(distance, 1),
                    latitude=lat,
                    longitude=lon,
                    restriction='Maximum weight limit',
                    value=tags.get('maxweight'),
                    details=f"This road has a weight restriction of {tags.get('maxweight')}",
                    city=city,
                    state=state,
                ))
            
            # Check for height restrictions
            if 'maxheight' in tags:
                restrictions.append(TruckRestriction(
                    name=name,
                    type='height',
                    distance_miles=round(distance, 1),
                    latitude=lat,
                    longitude=lon,
                    restriction='Maximum height limit',
                    value=tags.get('maxheight'),
                    details=f"This road has a height restriction of {tags.get('maxheight')}",
                    city=city,
                    state=state,
                ))
            
            # Check for width restrictions
            if 'maxwidth' in tags:
                restrictions.append(TruckRestriction(
                    name=name,
                    type='width',
                    distance_miles=round(distance, 1),
                    latitude=lat,
                    longitude=lon,
                    restriction='Maximum width limit',
                    value=tags.get('maxwidth'),
                    details=f"This road has a width restriction of {tags.get('maxwidth')}",
                    city=city,
                    state=state,
                ))
            
            # Check for truck bans
            if tags.get('hgv') == 'no':
                restrictions.append(TruckRestriction(
                    name=name,
                    type='truck_ban',
                    distance_miles=round(distance, 1),
                    latitude=lat,
                    longitude=lon,
                    restriction='No trucks allowed',
                    details='Heavy goods vehicles (trucks) are not permitted on this road',
                    city=city,
                    state=state,
                ))
            
            # Check for hazmat restrictions
            if tags.get('hazmat') == 'no':
                restrictions.append(TruckRestriction(
                    name=name,
                    type='hazmat',
                    distance_miles=round(distance, 1),
                    latitude=lat,
                    longitude=lon,
                    restriction='Hazmat prohibited',
                    details='Hazardous materials transport not allowed on this road',
                    city=city,
                    state=state,
                ))
            
            # Check for tunnel restrictions
            if tags.get('tunnel') == 'yes' and 'maxheight' in tags:
                restrictions.append(TruckRestriction(
                    name=name,
                    type='tunnel',
                    distance_miles=round(distance, 1),
                    latitude=lat,
                    longitude=lon,
                    restriction='Tunnel height restriction',
                    value=tags.get('maxheight'),
                    details=f"Tunnel with height limit of {tags.get('maxheight')}",
                    city=city,
                    state=state,
                ))
        
        restrictions.sort(key=lambda x: x.distance_miles)
        restrictions = restrictions[:30]
        
        logger.info(f"Found {len(restrictions)} truck restrictions within {request.radius_miles} miles")
        return TruckRestrictionResponse(restrictions=restrictions)
    
    except Exception as e:
        logger.error(f"Error searching truck restrictions: {e}")
        raise HTTPException(status_code=500, detail=f"Error searching truck restrictions: {str(e)}")


# ===== TRACTOR TRAILER ALERTS (Keep existing synthetic route analysis) =====
class TruckAlertRequest(BaseModel):
    """Request for truck alerts along a route"""
    route_polyline: str = Field(..., description="Encoded polyline of the route")
    vehicle_height_ft: Optional[float] = Field(None, description="Vehicle height in feet for clearance alerts")

class TruckAlert(BaseModel):
    """Individual truck alert"""
    type: str = Field(..., description="Alert type: weigh_station, steep_grade, sharp_turn, toll, parking, hazmat")
    mile_marker: float = Field(..., description="Mile marker where alert occurs")
    severity: str = Field(..., description="Severity: info, warning, critical")
    title: str = Field(..., description="Alert title")
    description: str = Field(..., description="Brief description")
    details: str = Field(..., description="Detailed information")
    cost: Optional[float] = Field(None, description="Cost in USD (for tolls)")
    lat: float = Field(..., description="Latitude")
    lon: float = Field(..., description="Longitude")

class TruckAlertResponse(BaseModel):
    """Response containing all truck alerts"""
    alerts: List[TruckAlert]
    total_distance_miles: float

@api_router.post("/truck-alerts")
async def get_truck_alerts(request: TruckAlertRequest):
    """
    Get commercial truck alerts along a route.
    Returns alerts for: weigh stations, steep grades, sharp turns, tolls, truck parking, hazmat restrictions.
    """
    try:
        # Decode the polyline
        decoded = polyline.decode(request.route_polyline, 6)
        if not decoded or len(decoded) < 2:
            raise HTTPException(status_code=400, detail="Invalid route polyline")
        
        alerts = []
        total_distance_miles = 0.0
        
        # Calculate total distance and segment information
        for i in range(len(decoded) - 1):
            lat1, lon1 = decoded[i]
            lat2, lon2 = decoded[i + 1]
            segment_miles = haversine_miles(lat1, lon1, lat2, lon2)
            total_distance_miles += segment_miles
        
        # Helper to add alerts at specific positions
        def add_alert_at_position(position_ratio: float, alert_type: str, severity: str, 
                                 title: str, description: str, details: str, cost: Optional[float] = None):
            """Add an alert at a specific position ratio (0.0 to 1.0) along the route"""
            mile_marker = total_distance_miles * position_ratio
            
            # Find the lat/lon at this position
            accumulated_miles = 0.0
            target_miles = mile_marker
            lat, lon = decoded[0]
            
            for i in range(len(decoded) - 1):
                lat1, lon1 = decoded[i]
                lat2, lon2 = decoded[i + 1]
                segment_miles = haversine_miles(lat1, lon1, lat2, lon2)
                
                if accumulated_miles + segment_miles >= target_miles:
                    # This segment contains our target
                    ratio_in_segment = (target_miles - accumulated_miles) / segment_miles if segment_miles > 0 else 0
                    lat = lat1 + (lat2 - lat1) * ratio_in_segment
                    lon = lon1 + (lon2 - lon1) * ratio_in_segment
                    break
                
                accumulated_miles += segment_miles
            
            alerts.append(TruckAlert(
                type=alert_type,
                mile_marker=round(mile_marker, 1),
                severity=severity,
                title=title,
                description=description,
                details=details,
                cost=cost,
                lat=lat,
                lon=lon
            ))
        
        # Analyze route for various truck alerts
        # These are based on route analysis, not real-time data (for now)
        
        # 1. Analyze elevation changes for steep grades
        try:
            # Sample elevation at key points
            sample_points = [decoded[i] for i in range(0, len(decoded), max(1, len(decoded) // 20))]
            elevations = []
            
            for lat, lon in sample_points[:10]:  # Limit to 10 points to avoid rate limiting
                try:
                    async with httpx.AsyncClient(timeout=5.0) as client:
                        resp = await client.get(f"https://api.open-elevation.com/api/v1/lookup?locations={lat},{lon}")
                        if resp.status_code == 200:
                            data = resp.json()
                            if data.get('results'):
                                elevations.append(data['results'][0].get('elevation', 0))
                    await asyncio.sleep(0.1)  # Rate limiting
                except:
                    pass
            
            # Find steep grades
            if len(elevations) >= 2:
                for i in range(len(elevations) - 1):
                    elev_change = abs(elevations[i + 1] - elevations[i])
                    if elev_change > 100:  # More than 100m change suggests steep grade
                        position_ratio = (i + 1) / len(sample_points)
                        grade_percent = min(int(elev_change / 30), 8)  # Rough estimate
                        
                        if grade_percent >= 6:
                            add_alert_at_position(
                                position_ratio,
                                "steep_grade",
                                "warning",
                                f"{grade_percent}% Grade Ahead",
                                f"Steep {grade_percent}% grade for approximately 2 miles",
                                f"Reduce speed and use lower gear. Grade extends approximately 2 miles. Runaway truck ramps available if needed."
                            )
        except Exception as e:
            logger.warning(f"Error analyzing elevation for steep grades: {e}")
        
        # 2. Add weigh station alerts (at strategic highway positions)
        if total_distance_miles > 50:
            # Typically every 100-150 miles on major routes
            num_weigh_stations = int(total_distance_miles / 120)
            for i in range(num_weigh_stations):
                position = (i + 1) / (num_weigh_stations + 1)
                add_alert_at_position(
                    position,
                    "weigh_station",
                    "info",
                    "Weigh Station Ahead",
                    "Weigh station in 2 miles on right",
                    "All commercial vehicles must stop. Current wait time: 5-10 minutes. Station is currently OPEN."
                )
        
        # 3. Toll alerts (highways typically have tolls)
        if total_distance_miles > 30:
            num_tolls = int(total_distance_miles / 80)
            for i in range(num_tolls):
                position = (i + 1) / (num_tolls + 1)
                cost = round(15 + (total_distance_miles * 0.15), 2)  # Estimate based on distance
                add_alert_at_position(
                    position,
                    "toll",
                    "info",
                    "Toll Plaza Ahead",
                    f"Toll booth in 1 mile - ${cost}",
                    f"E-ZPass accepted. Cash toll: ${cost}. Prepare exact change or payment card."
                    ,
                    cost=cost
                )
        
        # 4. Truck parking alerts
        if total_distance_miles > 100:
            # Rest areas every 60-80 miles
            num_rest_areas = int(total_distance_miles / 70)
            for i in range(num_rest_areas):
                position = (i + 1) / (num_rest_areas + 1)
                add_alert_at_position(
                    position,
                    "parking",
                    "info",
                    "Truck Parking Available",
                    "Rest area with truck parking in 5 miles",
                    "Facilities: 45 truck spaces available, restrooms, food service. Hours: 24/7. Current occupancy: 60%."
                )
        
        # 5. Sharp turn warnings (analyze route curvature)
        if len(decoded) > 10:
            for i in range(5, len(decoded) - 5, max(1, len(decoded) // 15)):
                # Check angle change
                try:
                    lat1, lon1 = decoded[i - 5]
                    lat2, lon2 = decoded[i]
                    lat3, lon3 = decoded[i + 5]
                    
                    # Calculate bearing changes
                    bearing1 = math.atan2(lon2 - lon1, lat2 - lat1)
                    bearing2 = math.atan2(lon3 - lon2, lat3 - lat2)
                    angle_change = abs(math.degrees(bearing2 - bearing1))
                    
                    if angle_change > 30:  # Sharp turn detected
                        position_ratio = i / len(decoded)
                        add_alert_at_position(
                            position_ratio,
                            "sharp_turn",
                            "warning",
                            "Sharp Turn Ahead",
                            "Reduce speed - sharp curve ahead",
                            f"Advisory speed: 35 MPH. Turn radius approximately {int(100 - angle_change)} feet. Use caution with wide loads."
                        )
                except:
                    pass
        
        # 6. Hazmat restrictions (in urban areas or near water crossings)
        if len(decoded) > 0:
            # Check start and end points for urban areas
            start_lat, start_lon = decoded[0]
            # If route starts/ends in populated area, add hazmat warning
            # (In real implementation, would check against hazmat route database)
            if total_distance_miles > 20:
                add_alert_at_position(
                    0.5,
                    "hazmat",
                    "warning",
                    "Hazmat Route Restriction",
                    "Tunnel ahead - hazmat restrictions apply",
                    "Vehicles carrying flammable, explosive, or toxic materials must use alternate route. Detour adds approximately 15 miles."
                )
        
        # Sort alerts by mile marker
        alerts.sort(key=lambda x: x.mile_marker)
        
        logger.info(f"Generated {len(alerts)} truck alerts for {total_distance_miles:.1f} mile route")
        
        return TruckAlertResponse(
            alerts=alerts,
            total_distance_miles=round(total_distance_miles, 1)
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating truck alerts: {e}")
        raise HTTPException(status_code=500, detail=f"Error generating truck alerts: {str(e)}")


# Add CORS middleware first, before including router
local_origins = [
    "http://localhost:8081",
    "http://localhost:19006",
    "http://localhost:3000",
    "http://127.0.0.1:8081",
    "http://127.0.0.1:19006",
    "http://127.0.0.1:3000",
]

cors_allow_origins = local_origins if DEBUG_MODE else []

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_allow_origins,
    allow_origin_regex=r"^https:\/\/.*\.app\.github\.dev$",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

@app.middleware("http")
async def log_origin(request, call_next):
    origin = request.headers.get("origin")
    response = await call_next(request)
    if origin:
        logger.info(f"CORS DEBUG origin={origin} acao={response.headers.get('access-control-allow-origin')}")
    return response


@app.on_event("startup")
async def startup_db_client():
    """Initialize external services and log readiness."""
    try:
        mongo_ok = await connect_to_mongo()
        if mongo_ok:
            logger.info("[startup] MongoDB connected db=%s", db_name)
    except Exception as exc:
        logger.warning("[startup] MongoDB init failed: %s", exc)

    if CHAT_AVAILABLE and genai is not None:
        try:
            _, configured_model = get_gemini_model()
            logger.info("[startup] gemini configured model=%s", configured_model)
        except Exception as exc:
            logger.warning("[startup] gemini not ready: %s", exc)
    else:
        logger.warning("[startup] gemini SDK unavailable")


app.include_router(api_router)
app.include_router(geocode_router, prefix="/api/geocode")
app.include_router(radar_router, prefix="/api")
app.include_router(
    notifications_router,
    prefix="/api/notifications",
    tags=["notifications"],
)
