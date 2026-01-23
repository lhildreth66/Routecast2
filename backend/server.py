from fastapi import FastAPI, APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import uuid
import math
from io import BytesIO
from datetime import datetime, timedelta
import httpx
import polyline
import asyncio
from bridge_database import get_bridge_warnings
from providers import get_providers
from chat.camp_prep_dispatcher import dispatch as dispatch_camp_prep
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
from notifications import NotificationService, ExpoPushClient
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

# MongoDB connection (optional for testing)
mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
client = None
db = None

# We'll connect on app startup instead of during module import
async def connect_to_mongo():
    global client, db
    try:
        temp_client = AsyncIOMotorClient(mongo_url, serverSelectionTimeoutMS=5000)
        # Test connection
        await temp_client.admin.command('ping')
        client = temp_client
        db = client[os.environ.get('DB_NAME', 'routecast_test')]
        logger.info("MongoDB connection successful")
        return True
    except Exception as e:
        logger.warning(f"MongoDB connection failed: {e}. Running without database.")
        client = None
        db = None
        return False

# API Keys
MAPBOX_ACCESS_TOKEN = os.environ.get('MAPBOX_ACCESS_TOKEN', '')
GOOGLE_API_KEY = os.environ.get('GEMINI_API_KEY', '') or os.environ.get('GOOGLE_API_KEY', '')

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
    vehicle_type: Optional[str] = "car"  # car, suv, truck, semi, rv, motorcycle, trailer
    trucker_mode: Optional[bool] = False  # Enable trucker-specific warnings
    vehicle_height_ft: Optional[float] = None  # Vehicle height in feet for clearance warnings

class HazardAlert(BaseModel):
    type: str  # wind, ice, visibility, rain, snow, etc.
    severity: str  # low, medium, high, extreme
    distance_miles: float
    eta_minutes: int
    message: str
    recommendation: str
    countdown_text: str  # "Heavy rain in 27 minutes"
    location_name: Optional[str] = None  # Name/description of the location where alert occurs

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

class ChatMessage(BaseModel):
    message: str
    route_context: Optional[str] = None  # Optional route info for context

class ChatResponse(BaseModel):
    response: str
    suggestions: List[str] = []

class CampPrepChatRequest(BaseModel):
    message: str
    subscription_id: Optional[str] = None

class CampPrepChatResponse(BaseModel):
    mode: str
    command: str
    human: str
    payload: Optional[Dict[str, Any]] = None
    premium: Dict[str, Any]
    error: Optional[str] = None

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

class SavedRoute(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    origin: str
    destination: str
    stops: List[StopPoint] = []
    is_favorite: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)

class FavoriteRouteRequest(BaseModel):
    origin: str
    destination: str
    stops: Optional[List[StopPoint]] = []
    name: Optional[str] = None

class PushTokenRequest(BaseModel):
    push_token: str
    enabled: bool = True

class TestNotificationRequest(BaseModel):
    push_token: str

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
    website: Optional[str] = None

class LastChanceRequest(BaseModel):
    latitude: float
    longitude: float
    radius_miles: int
    subscription_id: Optional[str] = None

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

def extract_waypoints_from_route(encoded_polyline: str, interval_miles: float = 50, departure_time: Optional[datetime] = None) -> List[Waypoint]:
    """Extract waypoints along route at specified intervals with ETAs."""
    try:
        coords = polyline.decode(encoded_polyline)
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
        return await get_providers().geocode.geocode(location)
    except Exception as e:
        logger.error(f"Geocoding error for {location}: {e}")
        return None


async def get_mapbox_route(origin_coords: Dict, dest_coords: Dict, waypoints: List[Dict] = None) -> Optional[Dict]:
    """Get route using active directions provider (Mapbox in prod, fixtures in demo)."""
    try:
        return await get_providers().directions.route(origin_coords, dest_coords, waypoints)
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
        for alert in raw_alerts:
            alerts.append(
                WeatherAlert(
                    id=alert.get('id', str(uuid.uuid4())),
                    headline=alert.get('headline', 'Weather Alert'),
                    severity=alert.get('severity', 'Unknown'),
                    event=alert.get('event', 'Weather Event'),
                    description=alert.get('description', '')[:500],
                    areas=alert.get('areas'),
                )
            )
        return alerts
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

def generate_hazard_alerts(waypoints_weather: List[WaypointWeather], departure_time: datetime) -> List[HazardAlert]:
    """Generate proactive hazard alerts with countdown timers."""
    alerts = []
    
    for wp in waypoints_weather:
        if not wp.weather:
            continue
            
        distance = wp.waypoint.distance_from_start or 0
        eta_mins = wp.waypoint.eta_minutes or int(distance / 55 * 60)
        location_name = wp.waypoint.name or f"Mile {int(distance)}"
        
        # Wind hazards
        wind_str = wp.weather.wind_speed or "0 mph"
        try:
            wind_speed = int(''.join(filter(str.isdigit, wind_str.split()[0])))
        except:
            wind_speed = 0
            
        if wind_speed > 25:
            severity = "extreme" if wind_speed > 40 else "high" if wind_speed > 30 else "medium"
            alerts.append(HazardAlert(
                type="wind",
                severity=severity,
                distance_miles=distance,
                eta_minutes=eta_mins,
                message=f"Strong winds of {wind_speed} mph",
                recommendation=f"Reduce speed to {max(35, 65 - wind_speed + 25)} mph",
                countdown_text=f"High winds in {eta_mins} minutes" if eta_mins > 0 else "High winds at start",
                location_name=location_name
            ))
            
        # Rain/visibility hazards
        conditions = (wp.weather.conditions or "").lower()
        if "heavy rain" in conditions or "storm" in conditions:
            alerts.append(HazardAlert(
                type="rain",
                severity="high",
                distance_miles=distance,
                eta_minutes=eta_mins,
                message="Heavy rain expected",
                recommendation="Reduce speed, increase following distance to 4 seconds",
                countdown_text=f"Heavy rain in {eta_mins} minutes at mile {int(distance)}",
                location_name=location_name
            ))
        elif "rain" in conditions or "shower" in conditions:
            alerts.append(HazardAlert(
                type="rain",
                severity="medium",
                distance_miles=distance,
                eta_minutes=eta_mins,
                message="Rain expected",
                recommendation="Turn on headlights and wipers",
                countdown_text=f"Rain in {eta_mins} minutes",
                location_name=location_name
            ))
            
        # Snow/ice hazards
        if "snow" in conditions:
            alerts.append(HazardAlert(
                type="snow",
                severity="high",
                distance_miles=distance,
                eta_minutes=eta_mins,
                message="Snow conditions expected",
                recommendation="Reduce speed by 50%, use winter tires if available",
                countdown_text=f"Snow conditions in {eta_mins} minutes",
                location_name=location_name
            ))
            
        # Temperature-based ice warnings
        temp = wp.weather.temperature or 70
        if temp <= 32:
            alerts.append(HazardAlert(
                type="ice",
                severity="high",
                distance_miles=distance,
                eta_minutes=eta_mins,
                message=f"Freezing temperature ({temp}°F) - ice risk",
                recommendation="Watch for black ice on bridges and overpasses",
                countdown_text=f"Ice risk zone in {eta_mins} minutes",
                location_name=location_name
            ))
            
        # Fog warnings
        if "fog" in conditions:
            alerts.append(HazardAlert(
                type="visibility",
                severity="high",
                distance_miles=distance,
                eta_minutes=eta_mins,
                message="Fog reducing visibility",
                recommendation="Use low beams, reduce speed to match visibility",
                countdown_text=f"Fog in {eta_mins} minutes",
                location_name=location_name
            ))
            
        # Weather alerts from NOAA
        for alert in wp.alerts:
            severity_map = {"Extreme": "extreme", "Severe": "high", "Moderate": "medium"}
            alerts.append(HazardAlert(
                type="alert",
                severity=severity_map.get(alert.severity, "medium"),
                distance_miles=distance,
                eta_minutes=eta_mins,
                message=alert.event,
                recommendation=alert.headline[:100],
                countdown_text=f"{alert.event} in {eta_mins} minutes",
                location_name=location_name
            ))
    
    # Sort by distance and deduplicate similar alerts
    alerts.sort(key=lambda x: x.distance_miles)
    return alerts  # Return all alerts along route

async def find_rest_stops(route_geometry: str, waypoints_weather: List[WaypointWeather]) -> List[RestStop]:
    """Find rest stops, gas stations along the route with weather at arrival."""
    rest_stops = []
    route_coords = polyline.decode(route_geometry)
    
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

def derive_road_condition(weather: Optional[WeatherData], alerts: List[WeatherAlert]) -> RoadCondition:
    """Derive road surface condition from weather data."""
    if not weather:
        return RoadCondition(
            condition="unknown",
            severity=0,
            label="UNKNOWN",
            icon="❓",
            color="#6b7280",
            description="Weather data unavailable",
            recommendation="Drive with normal caution"
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
    
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            coords_str = f"{origin_coords[1]},{origin_coords[0]};{dest_coords[1]},{dest_coords[0]}"
            url = f"https://api.mapbox.com/directions/v5/mapbox/driving/{coords_str}"
            params = {
                'access_token': MAPBOX_ACCESS_TOKEN,
                'steps': 'true',
                'geometries': 'polyline',
                'overview': 'full',
                'annotations': 'distance,duration'
            }
            
            response = await client.get(url, params=params)
            if response.status_code != 200:
                return steps
                
            data = response.json()
            if not data.get('routes'):
                return steps
            
            route = data['routes'][0]
            legs = route.get('legs', [])
            
            cumulative_distance = 0
            
            for leg in legs:
                for step in leg.get('steps', []):
                    distance_mi = step.get('distance', 0) / 1609.34  # meters to miles
                    duration_min = step.get('duration', 0) / 60  # seconds to minutes
                    cumulative_distance += distance_mi
                    
                    maneuver = step.get('maneuver', {})
                    instruction = maneuver.get('instruction', 'Continue')
                    maneuver_type = maneuver.get('type', 'straight')
                    
                    # Get road name
                    road_name = step.get('name', 'Unnamed road')
                    if not road_name:
                        road_name = step.get('ref', 'Local road')
                    
                    # Find nearest waypoint for weather/road condition
                    road_condition = None
                    weather_desc = None
                    temperature = None
                    has_alert = False
                    
                    for wp in waypoints_weather:
                        if wp.waypoint.distance_from_start and abs(wp.waypoint.distance_from_start - cumulative_distance) < 30:
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
                            has_alert=has_alert
                        ))
    
    except Exception as e:
        logger.error(f"Turn-by-turn directions error: {e}")
    
    return steps[:50]  # Limit to 50 steps

def analyze_route_conditions(waypoints_weather: List[WaypointWeather]) -> tuple:
    """Analyze all road conditions along route and determine if reroute is needed."""
    all_conditions = []
    worst_severity = 0
    worst_condition = "dry"
    reroute_needed = False
    reroute_reason = None
    
    for wp in waypoints_weather:
        road_cond = derive_road_condition(wp.weather, wp.alerts)
        all_conditions.append(road_cond)
        
        if road_cond.severity > worst_severity:
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
        if c.condition != "dry":
            condition_counts[c.label] = condition_counts.get(c.label, 0) + 1
    
    if not condition_counts:
        summary = "✅ Good road conditions expected throughout your route"
    else:
        summary_parts = [f"{count} segments with {label}" for label, count in condition_counts.items()]
        summary = f"⚠️ Road hazards detected: {', '.join(summary_parts)}"
    
    return summary, worst_condition, reroute_needed, reroute_reason

async def generate_ai_summary(waypoints_weather: List[WaypointWeather], origin: str, destination: str, packing: List[PackingSuggestion]) -> str:
    """Generate AI-powered weather summary using Gemini Flash."""
    try:
        # Build weather context
        weather_info = []
        all_alerts = []
        
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

        # Use Gemini for summary if available
        if CHAT_AVAILABLE and GOOGLE_API_KEY:
            client = genai.Client(api_key=GOOGLE_API_KEY)
            loop = asyncio.get_event_loop()
            response_obj = await loop.run_in_executor(
                None,
                lambda: client.models.generate_content(
                    model='gemini-2.0-flash-exp',
                    contents=prompt
                )
            )
            return response_obj.text
        else:
            return "Weather summary unavailable. AI features require Google API key."
    except Exception as e:
        logger.error(f"AI summary error: {e}")
        return f"Weather summary unavailable. Check individual waypoints for conditions."

# ==================== API Routes ====================

@api_router.get("/")
async def root():
    return {"message": "Routecast API", "version": "2.0", "features": ["departure_time", "multi_stop", "favorites", "packing_suggestions", "weather_timeline"]}

@api_router.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

@api_router.post("/route/weather", response_model=RouteWeatherResponse)
async def get_route_weather(request: RouteRequest):
    """Get weather along a route from origin to destination."""
    logger.info(f"Route weather request: {request.origin} -> {request.destination}")
    
    # Parse departure time
    departure_time = None
    if request.departure_time:
        try:
            departure_time = datetime.fromisoformat(request.departure_time.replace('Z', '+00:00'))
        except:
            departure_time = datetime.now()
    else:
        departure_time = datetime.now()
    
    # Geocode origin and destination
    origin_coords = await geocode_location(request.origin)
    if not origin_coords:
        raise HTTPException(status_code=400, detail=f"Could not geocode origin: {request.origin}")
    
    dest_coords = await geocode_location(request.destination)
    if not dest_coords:
        raise HTTPException(status_code=400, detail=f"Could not geocode destination: {request.destination}")
    
    # Geocode stops if any
    stop_coords = []
    if request.stops:
        for stop in request.stops:
            coords = await geocode_location(stop.location)
            if coords:
                stop_coords.append(coords)
    
    # Get route from Mapbox
    route_data = await get_mapbox_route(origin_coords, dest_coords, stop_coords if stop_coords else None)
    if not route_data:
        # Provide helpful error message for unreachable routes
        raise HTTPException(
            status_code=400, 
            detail=f"No drivable route found between {request.origin} and {request.destination}. These locations may not be connected by roads (e.g., Nome, Alaska is only accessible by air). Try different locations."
        )
    
    route_geometry = route_data['geometry']
    total_duration = int(route_data.get('duration', 0))
    
    # Extract waypoints along route
    waypoints = extract_waypoints_from_route(route_geometry, interval_miles=50, departure_time=departure_time)
    if not waypoints:
        raise HTTPException(status_code=500, detail="Could not extract waypoints from route")
    
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
    
    # Fetch weather concurrently
    total_waypoints = len(waypoints)
    tasks = [fetch_waypoint_weather(wp, i, total_waypoints, request.origin, request.destination) for i, wp in enumerate(waypoints)]
    waypoints_weather = await asyncio.gather(*tasks)
    
    # Generate packing suggestions
    packing_suggestions = generate_packing_suggestions(list(waypoints_weather))
    
    # Build weather timeline
    weather_timeline = build_weather_timeline(list(waypoints_weather))
    
    # Generate AI summary
    ai_summary = await generate_ai_summary(list(waypoints_weather), request.origin, request.destination, packing_suggestions)
    
    # NEW: Calculate safety score based on vehicle type
    vehicle_type = request.vehicle_type or "car"
    safety_score = calculate_safety_score(list(waypoints_weather), vehicle_type)
    
    # NEW: Generate hazard alerts with countdown
    hazard_alerts = generate_hazard_alerts(list(waypoints_weather), departure_time)
    
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
    road_condition_summary, worst_road_condition, reroute_recommended, reroute_reason = analyze_route_conditions(list(waypoints_weather))
    
    # NEW: Get turn-by-turn directions with road conditions
    turn_by_turn = await get_turn_by_turn_directions(origin_coords, dest_coords, list(waypoints_weather))
    
    # Calculate total distance
    total_distance = route_data.get('distance', 0) / 1609.34  # meters to miles
    
    response = RouteWeatherResponse(
        origin=request.origin,
        destination=request.destination,
        stops=request.stops or [],
        departure_time=departure_time.isoformat(),
        total_duration_minutes=total_duration,
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
        rest_stops=rest_stops,
        optimal_departure=optimal_departure,
        trucker_warnings=trucker_warnings,
        vehicle_type=vehicle_type,
        # Road conditions and navigation
        turn_by_turn=turn_by_turn,
        road_condition_summary=road_condition_summary,
        worst_road_condition=worst_road_condition,
        reroute_recommended=reroute_recommended,
        reroute_reason=reroute_reason
    )
    
    # Save to database
    try:
        route_doc = response.model_dump()
        # Ensure created_at is serializable
        if 'created_at' in route_doc and isinstance(route_doc['created_at'], datetime):
            route_doc['created_at'] = route_doc['created_at']
        await db.routes.insert_one(route_doc)
        logger.info(f"Saved route {response.id} to database")
    except Exception as e:
        logger.error(f"Error saving route: {e}", exc_info=True)
    
    return response

@api_router.get("/routes/history", response_model=List[SavedRoute])
async def get_route_history():
    """Get recent route history."""
    if db is None:
        logger.warning("Database not available for route history")
        return []
    try:
        routes = await db.routes.find().sort("created_at", -1).limit(10).to_list(10)
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
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing favorite: {e}")
        raise HTTPException(status_code=500, detail="Could not remove favorite")

@api_router.get("/routes/{route_id}", response_model=RouteWeatherResponse)
async def get_route_by_id(route_id: str):
    """Get a specific route by ID."""
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
    coords = await geocode_location(location)
    if not coords:
        raise HTTPException(status_code=404, detail="Location not found")
    return coords

@geocode_router.get("/autocomplete")
async def autocomplete_location(query: str, limit: int = 5):
    """Get autocomplete suggestions for a location query using Mapbox."""
    logger.info(f"Autocomplete request: query={query}, limit={limit}")
    if not query or len(query) < 2:
        return []
    
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
    except Exception as e:
        logger.error(f"Autocomplete error for '{query}': {e}")
        return []

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


@api_router.post("/chat/camp-prep", response_model=CampPrepChatResponse)
async def camp_prep_chat(request: CampPrepChatRequest):
    """Camp Prep mode chat - routes commands to domain functions with premium gating."""
    logger.info(f"[CAMP_PREP] Command: {request.message}")
    
    try:
        response = dispatch_camp_prep(request.message, request.subscription_id)
        result = response.to_dict()
        
        if result.get('error') == 'premium_locked':
            logger.info(f"[CAMP_PREP] Premium locked: {request.message}")
        else:
            logger.info(f"[CAMP_PREP] Success: {result.get('command')}")
        
        return CampPrepChatResponse(**result)
    except Exception as e:
        logger.error(f"[CAMP_PREP] Error: {e}")
        return CampPrepChatResponse(
            mode="camp_prep",
            command=request.message.split()[0] if request.message else "",
            human=f"Error processing command: {str(e)}",
            payload=None,
            premium={"required": False, "locked": False},
            error="server_error",
        )

@api_router.post("/chat", response_model=ChatResponse)
async def driver_chat(request: ChatMessage):
    """AI-powered chat for drivers to ask questions about weather, routes, and driving."""
    if not CHAT_AVAILABLE or not GOOGLE_API_KEY:
        return ChatResponse(
            response="Chat feature is not available. Please check your route conditions on the main screen or contact support.",
            suggestions=["Check road conditions", "View weather alerts", "Contact support"]
        )
    
    try:
        # Build the user message with optional route context and system instructions
        system_message = """You are Routecast AI, a helpful driving assistant that helps drivers with:
- Weather and road condition questions
- Safe driving tips based on weather
- Route planning advice
- What to pack for a trip
- Rest stop recommendations
- Understanding weather alerts and hazards

Keep responses concise (2-3 sentences max) and actionable. Use emojis sparingly.
If asked about specific locations, provide general advice since you don't have real-time data in this chat.
Always prioritize safety in your recommendations."""
        
        message_text = request.message
        if request.route_context:
            message_text = f"[Route context: {request.route_context}]\n\nUser question: {request.message}"
        
        # Use Gemini Flash for fast responses with new API
        client = genai.Client(api_key=GOOGLE_API_KEY)
        
        # Get response
        loop = asyncio.get_event_loop()
        response_obj = await loop.run_in_executor(
            None,
            lambda: client.models.generate_content(
                model='gemini-2.0-flash-exp',
                contents=system_message + "\n\n" + message_text
            )
        )
        response = response_obj.text
        
        # Generate quick suggestions based on the question
        suggestions = []
        question_lower = request.message.lower()
        
        if "ice" in question_lower or "snow" in question_lower:
            suggestions = ["What speed should I drive in snow?", "Do I need chains?", "Black ice tips"]
        elif "rain" in question_lower:
            suggestions = ["Hydroplaning prevention", "Following distance in rain", "When to pull over"]
        elif "wind" in question_lower:
            suggestions = ["Safe driving in high winds", "Should I delay my trip?"]
        elif "fog" in question_lower:
            suggestions = ["Fog driving tips", "What lights to use in fog"]
        elif "tired" in question_lower or "fatigue" in question_lower:
            suggestions = ["Rest stop tips", "Signs of drowsy driving", "Coffee vs. nap"]
        else:
            suggestions = ["Check road conditions", "Safest time to drive", "Packing tips"]
        
        return ChatResponse(
            response=response,
            suggestions=suggestions[:3]
        )
        
    except Exception as e:
        logger.error(f"Chat error: {type(e).__name__}: {str(e)}", exc_info=True)
        # More specific error message for debugging
        error_msg = f"I'm having trouble connecting right now. Error: {type(e).__name__}"
        if "API" in str(e) or "key" in str(e).lower():
            error_msg = "AI service authentication failed. Please contact support."
        return ChatResponse(
            response=error_msg,
            suggestions=["Check road conditions", "View weather alerts", "Contact support"]
        )

# ==================== Push Notification Endpoints ====================

async def send_expo_notification(push_token: str, title: str, body: str, data: Dict[str, Any] = None) -> bool:
    """Send a push notification via Expo Push Service."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                'https://exp.host/--/api/v2/push/send',
                json={
                    'to': push_token,
                    'sound': 'default',
                    'title': title,
                    'body': body,
                    'data': data or {},
                    'badge': 1,
                    'priority': 'high',
                },
                headers={'Accept': 'application/json', 'Accept-Encoding': 'gzip, deflate'},
            )
            return response.status_code == 200
    except Exception as e:
        logger.error(f"Error sending Expo notification: {e}")
        return False

@api_router.post("/notifications/register")
async def register_push_token(request: PushTokenRequest):
    """Register or update user's push notification token."""
    try:
        # Save token to MongoDB if available
        if db is not None:
            result = await db.push_tokens.update_one(
                {'push_token': request.push_token},
                {
                    '$set': {
                        'push_token': request.push_token,
                        'enabled': request.enabled,
                        'created_at': datetime.utcnow(),
                        'last_used': datetime.utcnow(),
                    }
                },
                upsert=True
            )
        else:
            logger.warning("[NOTIFICATIONS] Database not available, token not persisted")
        
        return {
            'success': True,
            'message': 'Push token registered successfully',
            'token': request.push_token[:20] + '...',
        }
    except Exception as e:
        logger.error(f"Error registering push token: {e}")
        return {
            'success': False,
            'message': f'Error registering token: {str(e)}',
        }

@api_router.post("/notifications/test")
async def send_test_notification(request: TestNotificationRequest):
    """Send a test push notification to verify setup."""
    try:
        success = await send_expo_notification(
            push_token=request.push_token,
            title='🚛 Routecast Test Alert',
            body='Push notifications are working! You\'ll receive weather alerts for your routes.',
            data={
                'type': 'test',
                'timestamp': datetime.utcnow().isoformat(),
            }
        )
        
        if success:
            # Update last_used timestamp if database available
            if db is not None:
                await db.push_tokens.update_one(
                    {'push_token': request.push_token},
                    {'$set': {'last_used': datetime.utcnow()}},
                    upsert=True
                )
            
            return {
                'success': True,
                'message': 'Test notification sent successfully',
            }
        else:
            return {
                'success': False,
                'message': 'Failed to send notification via Expo service',
            }
    except Exception as e:
        logger.error(f"Error sending test notification: {e}")
        return {
            'success': False,
            'message': f'Error sending test notification: {str(e)}',
        }

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

# ==================== Premium Features Endpoints ====================

@api_router.post("/pro/road-passability", response_model=RoadPassabilityResponse)
async def assess_road_passability(request: RoadPassabilityRequest):
    """
    Assess road passability and conditions along a route segment.
    
    PREMIUM FEATURE - Requires active subscription.
    
    Args:
        precip_72h: Precipitation in last 72 hours (mm)
        slope_pct: Road grade/slope percentage
        min_temp_f: Minimum temperature (°F)
        soil_type: Soil type classification
        subscription_id: Optional subscription ID for premium access validation
    
    Returns:
        - If premium locked: 403 with paywall message
        - If authorized: Complete passability assessment with score, risks, recommendations
    
    Logging: All premium feature access logged with [PREMIUM] prefix
    """
    logger.info(f"[PREMIUM] Road passability assessment requested")
    
    # Check premium entitlement
    is_premium = False
    if request.subscription_id:
        # Verify subscription is active
        try:
            sub = await db.subscriptions.find_one(
                {'subscription_id': request.subscription_id, 'status': 'active'}
            )
            is_premium = sub is not None
            
            if is_premium:
                logger.info(f"[PREMIUM] Road passability accessed by: {request.subscription_id}")
        except Exception as e:
            logger.error(f"[PREMIUM] Error checking subscription: {e}")
            is_premium = False
    
    # Return premium-locked response if not authorized
    if not is_premium:
        logger.info(f"[PREMIUM] Road passability access denied - premium required")
        return RoadPassabilityResponse(
            passability_score=0,
            condition_assessment="Unavailable",
            advisory="Upgrade to Routecast Pro to assess road conditions by soil type and weather",
            min_clearance_cm=0,
            recommended_vehicle_type="unknown",
            needs_four_x_four=False,
            risks={},
            is_premium_locked=True,
            premium_message="This feature requires Routecast Pro. Upgrade to unlock mud/ice/grade analysis."
        )
    
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
        logger.error(f"[PREMIUM] Invalid parameters for road passability: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Invalid parameters: {str(e)}"
        )
    except Exception as e:
        logger.error(f"[PREMIUM] Error assessing road passability: {e}")
        raise HTTPException(
            status_code=500,
            detail="Unable to assess road passability at this time"
        )

@api_router.post("/pro/solar-forecast", response_model=SolarForecastResponse)
async def forecast_solar_energy(request: SolarForecastRequest):
    """
    Forecast daily solar energy generation for a boondocking location.
    
    PREMIUM FEATURE - Requires active Boondocking Pro subscription.
    
    Args:
        lat: Latitude (-90 to 90)
        lon: Longitude (-180 to 180)
        date_range: List of ISO format dates
        panel_watts: Solar panel capacity in watts (>0)
        shade_pct: Average shade percentage (0-100)
        cloud_cover: List of cloud cover percentages (0-100) per date
        subscription_id: Optional subscription ID for premium access validation
    
    Returns:
        - If premium locked: paywall message
        - If authorized: daily Wh/day list with advisory
    
    Logging: All premium feature access logged with [PREMIUM] prefix
    """
    logger.info(f"[PREMIUM] Solar forecast requested")
    
    # Check premium entitlement
    require_premium(request.subscription_id, SOLAR_FORECAST)
    
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
        
        logger.info(f"[PREMIUM] Solar forecast completed successfully")
        
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
        logger.error(f"[PREMIUM] Invalid parameters for solar forecast: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Invalid parameters: {str(e)}"
        )
    except Exception as e:
        logger.error(f"[PREMIUM] Error forecasting solar energy: {e}")
        raise HTTPException(
            status_code=500,
            detail="Unable to forecast solar energy at this time"
        )

@api_router.post("/pro/propane-usage", response_model=PropaneUsageResponse)
async def estimate_propane_usage(request: PropaneUsageRequest):
    """
    Estimate daily propane consumption for RV boondocking.
    
    PREMIUM FEATURE - Requires active Boondocking Pro subscription.
    
    Args:
        furnace_btu: Furnace heating capacity in BTU (e.g., 20000, 30000)
        duty_cycle_pct: Percentage of time furnace runs (0-100, will be clamped)
        nights_temp_f: List of nightly low temperatures in Fahrenheit
        people: Number of people in RV (default: 2)
        subscription_id: Optional subscription ID for premium access validation
    
    Returns:
        - If premium locked: paywall message
        - If authorized: daily lbs/day list with advisory
    
    Logging: All premium feature access logged with [PREMIUM] prefix
    """
    logger.info(f"[PREMIUM] Propane usage estimate requested")
    
    # Check premium entitlement
    require_premium(request.subscription_id, PROPANE_USAGE)
    
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
        
        logger.info(f"[PREMIUM] Propane usage estimate completed successfully")
        
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
        logger.error(f"[PREMIUM] Invalid parameters for propane usage: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Invalid parameters: {str(e)}"
        )
    except Exception as e:
        logger.error(f"[PREMIUM] Error estimating propane usage: {e}")
        raise HTTPException(
            status_code=500,
            detail="Unable to estimate propane usage at this time"
        )

@api_router.post("/pro/water-budget", response_model=WaterBudgetResponse)
async def estimate_water_budget(request: WaterBudgetRequest):
    """
    Estimate days remaining before water tanks run out during boondocking.
    
    PREMIUM FEATURE - Requires active Boondocking Pro subscription.
    
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
    require_premium(request.subscription_id, WATER_BUDGET)
    
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

@api_router.post("/pro/terrain/sun-path", response_model=TerrainShadeResponse)
async def estimate_solar_path(request: TerrainShadeRequest):
    """Calculate hourly solar elevation path for boondocking location."""
    # Check premium subscription
    if not request.subscription_id:
        logger.warning("[PREMIUM] Attempted solar path without subscription")
        return TerrainShadeResponse(
            is_premium_locked=True,
            premium_message="Upgrade to Routecast Pro to plan around sunlight availability for solar and shade needs."
        )
    
    sub = await db.subscriptions.find_one({"_id": request.subscription_id, "status": "active"})
    if not sub:
        logger.warning(f"[PREMIUM] Invalid subscription {request.subscription_id}")
        return TerrainShadeResponse(
            is_premium_locked=True,
            premium_message="Upgrade to Routecast Pro to plan around sunlight availability for solar and shade needs."
        )
    
    # Call pure domain service
    try:
        # Parse date from ISO format
        from datetime import datetime as dt
        date_obj = dt.fromisoformat(request.date).date()
        
        slots = TerrainShadeService.sun_path(request.latitude, request.longitude, date_obj)
        
        # Calculate shade blocking
        shade_factor = TerrainShadeService.shade_blocks(
            request.tree_canopy_pct,
            request.horizon_obstruction_deg
        )
        
        # Calculate effective sunlight hours after shade
        exposure_hours = TerrainShadeService.sun_exposure_hours(
            request.latitude,
            request.longitude,
            date_obj,
            request.tree_canopy_pct,
            request.horizon_obstruction_deg
        )
        
        logger.info(f"[PREMIUM] Solar path calculation completed for lat={request.latitude}, lon={request.longitude}")
        
        # Convert domain slots to response format
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
        logger.error(f"[PREMIUM] Invalid parameters for solar path: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Invalid parameters: {str(e)}"
        )
    except Exception as e:
        logger.error(f"[PREMIUM] Unexpected error calculating solar path: {e}")
        raise HTTPException(
            status_code=500,
            detail="Unable to calculate solar path at this time"
        )

@api_router.post("/pro/terrain/shade-blocks", response_model=TerrainShadeResponse)
async def estimate_shade_blocking(request: TerrainShadeRequest):
    """Calculate shade blocking factor from trees and horizon obstruction."""
    # Check premium subscription
    if not request.subscription_id:
        logger.warning("[PREMIUM] Attempted shade blocking without subscription")
        return TerrainShadeResponse(
            is_premium_locked=True,
            premium_message="Upgrade to Routecast Pro to plan around sunlight availability for solar and shade needs."
        )
    
    sub = await db.subscriptions.find_one({"_id": request.subscription_id, "status": "active"})
    if not sub:
        logger.warning(f"[PREMIUM] Invalid subscription {request.subscription_id}")
        return TerrainShadeResponse(
            is_premium_locked=True,
            premium_message="Upgrade to Routecast Pro to plan around sunlight availability for solar and shade needs."
        )
    
    # Call pure domain service
    try:
        shade_factor = TerrainShadeService.shade_blocks(
            request.tree_canopy_pct,
            request.horizon_obstruction_deg
        )
        
        # Generate advisory
        if shade_factor < 0.2:
            advisory = "Excellent solar exposure! Good for solar generators."
        elif shade_factor < 0.5:
            advisory = "Good solar exposure with moderate shade. Solar viable."
        elif shade_factor < 0.8:
            advisory = "Significant shade. Solar generation will be limited."
        else:
            advisory = "Heavy shade blocks most sunlight. Solar not recommended."
        
        logger.info(f"[PREMIUM] Shade blocking calculation completed: shade_factor={shade_factor}")
        
        return TerrainShadeResponse(
            shade_factor=round(shade_factor, 3),
            exposure_hours=None,
            is_premium_locked=False,
        )
    except ValueError as e:
        logger.error(f"[PREMIUM] Invalid parameters for shade blocking: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Invalid parameters: {str(e)}"
        )
    except Exception as e:
        logger.error(f"[PREMIUM] Unexpected error calculating shade blocking: {e}")
        raise HTTPException(
            status_code=500,
            detail="Unable to calculate shade blocking at this time"
        )

# ==================== Wind Shelter Endpoints ====================

@api_router.post("/pro/wind-shelter/orientation", response_model=WindShelterResponse)
async def recommend_orientation(request: WindShelterRequest):
    """Recommend RV orientation for wind shelter based on local ridges and topography."""
    # Check premium subscription
    require_premium(request.subscription_id, WIND_SHELTER)
    
    # Call pure domain service
    try:
        # Convert request ridges to domain objects
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
        
        logger.info(f"[PREMIUM] Wind shelter recommendation completed: bearing={advice.recommended_bearing_deg}, risk={advice.risk_level}")
        
        return WindShelterResponse(
            recommended_bearing_deg=advice.recommended_bearing_deg,
            rationale_text=advice.rationale_text,
            risk_level=advice.risk_level,
            shelter_available=advice.shelter_available,
            estimated_wind_reduction_pct=advice.estimated_wind_reduction_pct,
            is_premium_locked=False,
        )
    except ValueError as e:
        logger.error(f"[PREMIUM] Invalid parameters for wind orientation: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Invalid parameters: {str(e)}"
        )
    except Exception as e:
        logger.error(f"[PREMIUM] Unexpected error recommending orientation: {e}")
        raise HTTPException(
            status_code=500,
            detail="Unable to recommend orientation at this time"
        )

# ==================== Road Passability Endpoint (A6) ====================
from road_passability_a6 import score as passability_score

@api_router.post("/pro/road-passability", response_model=RoadPassabilityResponse)
async def get_road_passability(request: RoadPassabilityRequest):
    """Premium-gated road passability scoring (Task A6)."""
    # Premium gating
    if not request.subscription_id:
        logger.warning("[PREMIUM] Attempted road passability without subscription")
        raise HTTPException(
            status_code=402,
            detail={
                "code": "PREMIUM_LOCKED",
                "message": "Upgrade to Routecast Pro to assess backroad passability (mud/ice/clearance)."
            }
        )
    sub = await db.subscriptions.find_one({"_id": request.subscription_id, "status": "active"})
    if not sub:
        logger.warning(f"[PREMIUM] Invalid subscription {request.subscription_id}")
        raise HTTPException(
            status_code=402,
            detail={
                "code": "PREMIUM_LOCKED",
                "message": "Upgrade to Routecast Pro to assess backroad passability (mud/ice/clearance)."
            }
        )

    try:
        res = passability_score(
            precip72h_in=request.precip72hIn,
            slope_pct=request.slopePct,
            min_temp_f=request.minTempF,
            soil=request.soilType,
        )
        logger.info(f"[PREMIUM] Road passability computed: score={res.score} mud={res.mud_risk} ice={res.ice_risk}")
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
        logger.error(f"[PREMIUM] Invalid parameters for road passability: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid parameters: {str(e)}")
    except Exception as e:
        logger.error(f"[PREMIUM] Unexpected error computing road passability: {e}")
        raise HTTPException(status_code=500, detail="Unable to compute road passability at this time")

# ==================== Connectivity Endpoints (A7) ====================

@api_router.post("/pro/connectivity/cell-probability", response_model=ConnectivityCellResponse)
async def predict_cell_probability(request: ConnectivityCellRequest):
    """Premium-gated cellular signal probability prediction (Task A7)."""
    # Premium gating
    require_premium(request.subscription_id, CELL_STARLINK)

    try:
        # Check if GPS coordinates provided (new approach)
        if request.lat is not None and request.lon is not None:
            # Use GPS-based tower lookup
            res = predict_cell_signal_at_location(
                lat=request.lat,
                lon=request.lon,
                carrier=request.carrier,
            )
            logger.info(f"[PREMIUM] Cell probability computed via GPS: lat={request.lat} lon={request.lon} carrier={res.carrier} probability={res.probability}")
        else:
            # Fallback to manual tower distance input (legacy)
            if request.towerDistanceKm is None or request.terrainObstructionPct is None:
                raise ValueError("Either (lat, lon) or (towerDistanceKm, terrainObstructionPct) must be provided")
            
            res = cell_bars_probability(
                carrier=request.carrier,
                tower_distance_km=request.towerDistanceKm,
                terrain_obstruction=request.terrainObstructionPct,
            )
            logger.info(f"[PREMIUM] Cell probability computed via manual input: carrier={res.carrier} probability={res.probability}")
        
        return ConnectivityCellResponse(
            carrier=res.carrier,
            probability=res.probability,
            bar_estimate=res.bar_estimate,
            explanation=res.explanation,
            is_premium_locked=False,
        )
    except ValueError as e:
        logger.error(f"[PREMIUM] Invalid parameters for cell probability: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid parameters: {str(e)}")
    except Exception as e:
        logger.error(f"[PREMIUM] Unexpected error computing cell probability: {e}")
        raise HTTPException(status_code=500, detail="Unable to compute cell probability at this time")

@api_router.post("/pro/connectivity/starlink-risk", response_model=ConnectivityStarlinkResponse)
async def predict_starlink_risk(request: ConnectivityStarlinkRequest):
    """Premium-gated Starlink obstruction risk prediction (Task A7)."""
    # Premium gating
    require_premium(request.subscription_id, CELL_STARLINK)

    try:
        res = obstruction_risk(
            horizon_south_deg=request.horizonSouthDeg,
            canopy_pct=request.canopyPct,
        )
        logger.info(f"[PREMIUM] Starlink risk computed: risk_level={res.risk_level} score={res.obstruction_score}")
        return ConnectivityStarlinkResponse(
            risk_level=res.risk_level,
            obstruction_score=res.obstruction_score,
            explanation=res.explanation,
            reasons=res.reasons,
            is_premium_locked=False,
        )
    except ValueError as e:
        logger.error(f"[PREMIUM] Invalid parameters for Starlink risk: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid parameters: {str(e)}")
    except Exception as e:
        logger.error(f"[PREMIUM] Unexpected error computing Starlink risk: {e}")
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
            return 0.2  # Low shade default
        
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
        return 0.3  # Default moderate


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
            return 0.5  # Medium access default
        
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
        return 0.5  # Default


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


@api_router.post("/pro/campsite-index", response_model=CampsiteIndexResponse)
async def calculate_campsite_index(request: CampsiteIndexRequest):
    """Premium-gated Campsite Index scoring (Task A8)."""
    logger.info(f"[PREMIUM] Campsite index calculation requested")
    
    # Check premium entitlement
    require_premium(request.subscription_id, CAMPSITE_INDEX)

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
        logger.info(f"[PREMIUM] Campsite index computed: score={result.score}")
        return CampsiteIndexResponse(
            score=result.score,
            breakdown=result.breakdown,
            explanations=result.explanations,
            is_premium_locked=False,
        )
    except ValueError as e:
        logger.error(f"[PREMIUM] Invalid parameters for campsite index: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid parameters: {str(e)}")
    except Exception as e:
        logger.error(f"[PREMIUM] Unexpected error computing campsite index: {e}")
        raise HTTPException(status_code=500, detail="Unable to compute campsite index at this time")


@api_router.post("/pro/campsite-index/auto", response_model=CampsiteIndexResponse)
async def calculate_campsite_index_auto(request: CampsiteIndexAutoRequest):
    """Premium-gated Campsite Index with automatic data fetching."""
    logger.info(f"[PREMIUM] Auto campsite index for lat={request.latitude}, lon={request.longitude}")
    
    # Check premium entitlement
    require_premium(request.subscription_id, CAMPSITE_INDEX)

    try:
        # Fetch real data from various sources
        async with httpx.AsyncClient(timeout=30.0) as client:
            # 1. Get current weather for wind
            wind_gust_mph = await _fetch_wind_data(client, request.latitude, request.longitude)
            
            # 2. Get terrain data for slope and shade
            slope_pct, shade_score = await _fetch_terrain_data(client, request.latitude, request.longitude)
            
            # 3. Get road access score from OSM
            access_score = await _fetch_access_score(client, request.latitude, request.longitude)
            
            # 4. Get cell signal estimate
            signal_score = await _fetch_signal_score(request.latitude, request.longitude)
            
            # 5. Get road passability
            road_passability_score = await _fetch_passability_score(client, request.latitude, request.longitude)

        # Calculate the score using the real data
        factors = SiteFactors(
            wind_gust_mph=wind_gust_mph,
            shade_score=shade_score,
            slope_pct=slope_pct,
            access_score=access_score,
            signal_score=signal_score,
            road_passability_score=road_passability_score,
        )
        result = campsite_score(factors)
        
        logger.info(f"[PREMIUM] Auto campsite index computed: score={result.score}")
        return CampsiteIndexResponse(
            score=result.score,
            breakdown=result.breakdown,
            explanations=result.explanations,
            is_premium_locked=False,
        )
    except ValueError as e:
        logger.error(f"[PREMIUM] Invalid parameters for auto campsite index: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid parameters: {str(e)}")
    except Exception as e:
        logger.error(f"[PREMIUM] Unexpected error computing auto campsite index: {e}")
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


@api_router.post("/pro/claim-log/build", response_model=ClaimLogResponse)
async def build_claim_log_endpoint(request: ClaimLogRequest):
    """Premium-gated Claim Log builder (Task A9).

    Accepts hazard events and weather snapshot, returns structured ClaimLog JSON.
    """
    # Premium gating
    require_premium(request.subscription_id, CLAIM_LOG)

    try:
        hazards = _to_claim_hazards(request.hazards)
        weather = _to_claim_weather(request.weatherSnapshot)
        claim_log = build_claim_log(route_id=request.routeId, hazards=hazards, weather_snapshot=weather)

        # Build response dict via dataclass helper
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
        logger.error(f"[PREMIUM] Invalid parameters for claim log: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid parameters: {str(e)}")
    except Exception as e:
        logger.error(f"[PREMIUM] Unexpected error building claim log: {e}")
        raise HTTPException(status_code=500, detail="Unable to build claim log at this time")


class ClaimLogPdfRequest(BaseModel):
    routeId: Optional[str] = None
    hazards: Optional[List[ClaimHazardEventModel]] = None
    weatherSnapshot: Optional[ClaimWeatherSnapshotModel] = None
    claimLog: Optional[Dict[str, Any]] = None
    subscription_id: Optional[str] = None


@api_router.post("/pro/claim-log/pdf")
async def claim_log_pdf_endpoint(request: ClaimLogPdfRequest):
    """Premium-gated Claim Log PDF export (Task A9).

    Accepts either raw inputs (routeId, hazards, weatherSnapshot) or a full ClaimLog JSON.
    Returns a PDF binary.
    """
    # Premium gating
    require_premium(request.subscription_id, CLAIM_LOG)

    try:
        # Determine source of ClaimLog
        if request.claimLog:
            # Build from provided ClaimLog JSON
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
            # Build from raw inputs
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
        logger.error(f"[PREMIUM] Invalid parameters for claim log PDF: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid parameters: {str(e)}")
    except Exception as e:
        logger.error(f"[PREMIUM] Unexpected error exporting claim log PDF: {e}")
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
    require_premium(request.subscription_id, SMART_DELAY_ALERTS)
    
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
    require_premium(request.subscription_id, SMART_DELAY_ALERTS)
    
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
    require_premium(request.subscription_id, SMART_DELAY_ALERTS)
    
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

@api_router.post("/pro/free-camping/search", response_model=FreeCampingResponse)
async def search_free_camping(request: FreeCampingRequest):
    """Find free camping spots (BLM, National Forest, etc.) near given coordinates using OpenStreetMap data."""
    require_premium(request.subscription_id, CAMPSITE_INDEX)  # Reuse campsite_index feature for now
    
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
                raise last_error or Exception("All Overpass instances failed")
        
        spots = []
        seen_coords = set()  # Avoid duplicates
        
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
            
            # Avoid duplicate locations
            coord_key = (round(lat, 4), round(lon, 4))
            if coord_key in seen_coords:
                continue
            seen_coords.add(coord_key)
            
            # Calculate distance
            distance_miles = math.sqrt(
                (lat - request.latitude) ** 2 + (lon - request.longitude) ** 2
            ) * 69.0  # Rough approximation: 1 degree ≈ 69 miles
            
            tags = element.get("tags", {})
            
            # Extract name with better fallbacks
            name = tags.get("name")
            if not name:
                # Try to use operator or location as name
                operator = tags.get("operator", "")
                if operator:
                    name = f"{operator} Camping Area"
                elif tags.get("backcountry") == "yes":
                    name = "Dispersed Camping Area"
                elif tags.get("tourism") == "camp_site":
                    name = "Public Campsite"
                else:
                    name = f"Camping near ({round(lat, 3)}, {round(lon, 3)})"
            
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
        
        # Sort by distance
        spots.sort(key=lambda x: x.distance_miles)
        
        # Limit to 20 results
        spots = spots[:20]
        
        logger.info(f"[PREMIUM] Free camping search completed: found {len(spots)} spots from OSM within {request.radius_miles} miles")
        
        return FreeCampingResponse(
            spots=spots,
            is_premium_locked=False,
        )
    
    except httpx.HTTPError as e:
        logger.error(f"[PREMIUM] Overpass API error: {e}")
        raise HTTPException(
            status_code=503,
            detail="Camping data service temporarily unavailable"
        )
    except Exception as e:
        logger.error(f"[PREMIUM] Error searching free camping: {e}")
        raise HTTPException(
            status_code=500,
            detail="Unable to search for camping spots at this time"
        )


# ==================== Dump Station Finder Endpoint ====================

@api_router.post("/pro/dump-stations/search", response_model=DumpStationResponse)
async def search_dump_stations(request: DumpStationRequest):
    """Find RV dump stations near given coordinates using OpenStreetMap data."""
    require_premium(request.subscription_id, CAMPSITE_INDEX)  # Reuse campsite_index feature
    
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
        
        logger.info(f"[PREMIUM] Dump station search completed: found {len(stations)} stations from OSM within {request.radius_miles} miles")
        
        return DumpStationResponse(
            stations=stations,
            is_premium_locked=False,
        )
    
    except httpx.HTTPError as e:
        logger.error(f"[PREMIUM] Overpass API error for dump stations: {e}")
        raise HTTPException(
            status_code=503,
            detail="Dump station data service temporarily unavailable. The mapping service may be experiencing high load. Please try again in a few moments."
        )
    except Exception as e:
        logger.error(f"[PREMIUM] Error searching dump stations: {e}")
        raise HTTPException(
            status_code=500,
            detail="Unable to search for dump stations. Please check your internet connection and try again."
        )


# ==================== Last Chance Supply Finder Endpoint ====================

@api_router.post("/pro/last-chance/search", response_model=LastChanceResponse)
async def search_last_chance_supplies(request: LastChanceRequest):
    """Find grocery stores, propane refill, and hardware stores near given coordinates using OpenStreetMap data."""
    require_premium(request.subscription_id, CAMPSITE_INDEX)  # Reuse campsite_index feature
    
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
            name = tags.get("name") or tags.get("brand")
            if not name:
                # Use operator if available
                operator = tags.get("operator", "")
                if operator:
                    name = operator
                else:
                    # Use descriptive type-based name
                    if subtype:
                        name = f"{subtype}"
                    else:
                        name = f"{supply_type} Store"
            
            # Add propane indicator if applicable
            if supply_type == "Propane" and "Propane" not in name and "LPG" not in name:
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
                name=name,
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
                website=website
            ))
        
        # Sort by distance
        supplies.sort(key=lambda x: x.distance_miles)
        
        # Limit to 30 results
        supplies = supplies[:30]
        
        logger.info(f"[PREMIUM] Last chance supply search completed: found {len(supplies)} locations from OSM within {request.radius_miles} miles")
        
        return LastChanceResponse(
            supplies=supplies,
            is_premium_locked=False,
        )
    
    except httpx.HTTPError as e:
        logger.error(f"[PREMIUM] Overpass API error for last chance supplies: {e}")
        raise HTTPException(
            status_code=503,
            detail="Supply data service temporarily unavailable. The mapping service may be experiencing high load. Please try again in a few moments."
        )
    except Exception as e:
        logger.error(f"[PREMIUM] Error searching last chance supplies: {e}")
        raise HTTPException(
            status_code=500,
            detail="Unable to search for supply points. Please check your internet connection and try again."
        )


# ==================== RV Dealership Finder Endpoint ====================

@api_router.post("/pro/rv-dealerships/search", response_model=RVDealershipResponse)
async def search_rv_dealerships(request: RVDealershipRequest):
    """Find RV dealerships, service centers, and parts stores near given coordinates using OpenStreetMap data."""
    require_premium(request.subscription_id, CAMPSITE_INDEX)  # Reuse campsite_index feature
    
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
            
            # Extract name with better fallbacks
            name = tags.get("name") or tags.get("brand")
            if not name:
                # Use operator if available
                operator = tags.get("operator", "")
                if operator:
                    name = operator
                else:
                    # Use craft or shop tag for descriptive name
                    craft = tags.get("craft", "")
                    shop = tags.get("shop", "")
                    if "caravan" in craft or "caravan" in shop:
                        name = "RV Service Center"
                    elif tags.get("amenity") == "car_repair":
                        name = "RV Repair Shop"
                    else:
                        # Last resort: use coordinates
                        name = f"RV Service ({round(lat, 3)}, {round(lon, 3)})"
            
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
        
        logger.info(f"[PREMIUM] RV dealership search completed: found {len(dealerships)} dealerships from OSM within {request.radius_miles} miles")
        
        return RVDealershipResponse(
            dealerships=dealerships,
            is_premium_locked=False,
        )
    
    except httpx.HTTPError as e:
        logger.error(f"[PREMIUM] Overpass API error for RV dealerships: {e}")
        raise HTTPException(
            status_code=503,
            detail="RV dealership data service temporarily unavailable. The mapping service may be experiencing high load. Please try again in a few moments."
        )
    except Exception as e:
        logger.error(f"[PREMIUM] Error searching RV dealerships: {e}")
        raise HTTPException(
            status_code=500,
            detail="Unable to search for RV dealerships. Please check your internet connection and try again."
        )


# ==================== TRACTOR TRAILER PRO ENDPOINTS ====================

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
    radius_miles: int = 15

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

@api_router.post("/pro/truck-stops/search", response_model=TruckStopResponse)
async def search_truck_stops(request: TruckStopRequest):
    """Find truck stops with fuel and amenities using OpenStreetMap."""
    try:
        radius_meters = int(request.radius_miles * 1609.34)
        
        # Expanded query to include all fuel stations, prioritizing truck-friendly ones
        overpass_query = f"""
        [out:json][timeout:25];
        (
          node["amenity"="fuel"]["hgv"="yes"](around:{radius_meters},{request.latitude},{request.longitude});
          node["amenity"="fuel"]["name"~"Flying J|Love's|TA|Pilot|Petro|Truck|Travel",i](around:{radius_meters},{request.latitude},{request.longitude});
          node["amenity"="fuel"](around:{radius_meters},{request.latitude},{request.longitude});
        );
        out body;
        """
        
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post("https://overpass-api.de/api/interpreter", data=overpass_query)
            response.raise_for_status()
            data = response.json()
        
        logger.info(f"Overpass returned {len(data.get('elements', []))} fuel stations")
        
        stops = []
        for element in data.get('elements', []):
            if element['type'] != 'node':
                continue
            
            tags = element.get('tags', {})
            lat = element.get('lat', 0)
            lon = element.get('lon', 0)
            
            distance = haversine_miles(request.latitude, request.longitude, lat, lon)
            
            # Extract amenities
            amenities = []
            if tags.get('shop'):
                amenities.append('Convenience Store')
            if tags.get('toilets') == 'yes' or 'restroom' in tags.get('name', '').lower():
                amenities.append('Restrooms')
            if tags.get('shower') == 'yes':
                amenities.append('Showers')
            if tags.get('food') or tags.get('restaurant'):
                amenities.append('Food')
            if tags.get('repair') == 'yes':
                amenities.append('Repair')
            if tags.get('parking:truck') or tags.get('capacity:hgv'):
                amenities.append('Truck Parking')
            
            # Fuel types
            fuel_types = []
            if tags.get('fuel:diesel') == 'yes':
                fuel_types.append('Diesel')
            if tags.get('fuel:diesel:class1') == 'yes':
                fuel_types.append('DEF')
            if tags.get('fuel:lpg') == 'yes':
                fuel_types.append('Propane')
            if not fuel_types:
                fuel_types.append('Diesel')  # Assume diesel if truck stop
            
            # Services
            services = []
            if 'scales' in tags.get('name', '').lower() or tags.get('amenity:scale'):
                services.append('CAT Scale')
            if tags.get('truck_wash') == 'yes' or 'wash' in tags.get('name', '').lower():
                services.append('Truck Wash')
            if tags.get('wifi') == 'yes':
                services.append('WiFi')
            
            # Detect brand
            name = tags.get('name', 'Unknown Truck Stop')
            brand = tags.get('brand')
            if not brand:
                for b in ['Flying J', "Love's", 'TA Travel', 'Pilot', 'Petro']:
                    if b.lower() in name.lower():
                        brand = b
                        break
            
            stops.append(TruckStop(
                name=name,
                brand=brand,
                distance_miles=round(distance, 1),
                latitude=lat,
                longitude=lon,
                amenities=amenities,
                fuel_types=fuel_types,
                services=services,
                phone=tags.get('phone'),
                website=tags.get('website'),
                hours=tags.get('opening_hours'),
            ))
        
        stops.sort(key=lambda x: x.distance_miles)
        stops = stops[:20]
        
        logger.info(f"Found {len(stops)} truck stops within {request.radius_miles} miles")
        return TruckStopResponse(stops=stops)
    
    except Exception as e:
        logger.error(f"Error searching truck stops: {e}")
        raise HTTPException(status_code=500, detail=f"Error searching truck stops: {str(e)}")


# Truck Parking
class TruckParkingRequest(BaseModel):
    latitude: float
    longitude: float
    radius_miles: int = 15  # Reduce default radius to prevent timeout

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

@api_router.post("/pro/truck-parking/search", response_model=TruckParkingResponse)
async def search_truck_parking(request: TruckParkingRequest):
    """Find truck parking including rest areas and safe parking zones."""
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
        
        async with httpx.AsyncClient(timeout:30.0) as client:
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

@api_router.post("/pro/truck-services/search", response_model=TruckServiceResponse)
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

@api_router.post("/pro/weigh-stations/search", response_model=WeighStationResponse)
async def search_weigh_stations(request: WeighStationRequest):
    """Find weigh stations along highways."""
    try:
        radius_meters = int(request.radius_miles * 1609.34)
        
        overpass_query = f"""
        [out:json][timeout:25];
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
        
        async with httpx.AsyncClient(timeout=45.0) as client:
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

@api_router.post("/pro/truck-restrictions/search", response_model=TruckRestrictionResponse)
async def search_truck_restrictions(request: TruckRestrictionRequest):
    """Find roads with truck restrictions using OpenStreetMap."""
    try:
        radius_meters = int(request.radius_miles * 1609.34)
        
        # Query for various truck restrictions
        overpass_query = f"""
        [out:json][timeout:15];
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
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post("https://overpass-api.de/api/interpreter", data=overpass_query)
            response.raise_for_status()
            data = response.json()
        
        restrictions = []
        processed_locations = {}  # Cache geocoding results
        
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
            
            # Reverse geocode to get city/state (cached by rounded coords)
            loc_key = f"{round(lat, 2)},{round(lon, 2)}"
            if loc_key not in processed_locations:
                try:
                    async with httpx.AsyncClient(timeout=5.0) as geo_client:
                        geo_resp = await geo_client.get(
                            f"https://nominatim.openstreetmap.org/reverse",
                            params={'lat': lat, 'lon': lon, 'format': 'json'},
                            headers={'User-Agent': 'Routecast/1.0'}
                        )
                        if geo_resp.status_code == 200:
                            geo_data = geo_resp.json()
                            address = geo_data.get('address', {})
                            city = address.get('city') or address.get('town') or address.get('village') or address.get('county')
                            state = address.get('state')
                            processed_locations[loc_key] = (city, state)
                        else:
                            processed_locations[loc_key] = (None, None)
                except:
                    processed_locations[loc_key] = (None, None)
            
            city, state = processed_locations[loc_key]
            
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


# ===== TRACTOR TRAILER PRO ALERTS (Keep existing synthetic route analysis) =====
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
        decoded = polyline.decode(request.route_polyline)
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
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers in the main app
app.include_router(geocode_router, prefix="/api/geocode")
app.include_router(radar_router, prefix="/api/radar")  # Weather radar & alerts
app.include_router(api_router)

@app.on_event("startup")
async def startup_db_client():
    await connect_to_mongo()

@app.on_event("shutdown")
async def shutdown_db_client():
    if client is not None:
        client.close()
