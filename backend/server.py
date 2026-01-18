from fastapi import FastAPI, APIRouter, HTTPException
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
from datetime import datetime, timedelta
import httpx
import polyline
import asyncio
from bridge_database import get_bridge_warnings
from road_passability_service import RoadPassabilityService
from solar_forecast_service import SolarForecastService
from propane_usage_service import PropaneUsageService
from water_budget_service import WaterBudgetService

# Google Gemini for chat
try:
    from google import genai
    CHAT_AVAILABLE = True
except ImportError:
    CHAT_AVAILABLE = False
    genai = None

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# API Keys
MAPBOX_ACCESS_TOKEN = os.environ.get('MAPBOX_ACCESS_TOKEN', '')
GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY', '')

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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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
    """Reverse geocode coordinates to get city, state name."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            url = f"https://api.mapbox.com/geocoding/v5/mapbox.places/{lon},{lat}.json"
            params = {
                'access_token': MAPBOX_ACCESS_TOKEN,
                'types': 'place,locality',
                'limit': 1
            }
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            if data.get('features') and len(data['features']) > 0:
                feature = data['features'][0]
                place_name = feature.get('text', '')
                
                # Extract state from context
                context = feature.get('context', [])
                state = ''
                for ctx in context:
                    if ctx.get('id', '').startswith('region'):
                        state = ctx.get('short_code', '').replace('US-', '')
                        break
                
                if place_name and state:
                    return f"{place_name}, {state}"
                return place_name or None
    except Exception as e:
        logger.error(f"Reverse geocoding error for {lat},{lon}: {e}")
    return None

async def geocode_location(location: str) -> Optional[Dict[str, float]]:
    """Geocode a location string to coordinates using Mapbox."""
    try:
        async with httpx.AsyncClient() as client:
            url = f"https://api.mapbox.com/geocoding/v5/mapbox.places/{location}.json"
            params = {
                'access_token': MAPBOX_ACCESS_TOKEN,
                'limit': 1,
                'country': 'US'
            }
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            if data.get('features') and len(data['features']) > 0:
                coords = data['features'][0]['center']
                return {'lon': coords[0], 'lat': coords[1]}
    except Exception as e:
        logger.error(f"Geocoding error for {location}: {e}")
    return None

async def get_mapbox_route(origin_coords: Dict, dest_coords: Dict, waypoints: List[Dict] = None) -> Optional[Dict]:
    """Get route from Mapbox Directions API with duration."""
    try:
        # Build coordinates string
        coords_list = [f"{origin_coords['lon']},{origin_coords['lat']}"]
        if waypoints:
            for wp in waypoints:
                coords_list.append(f"{wp['lon']},{wp['lat']}")
        coords_list.append(f"{dest_coords['lon']},{dest_coords['lat']}")
        coords_str = ";".join(coords_list)
        
        async with httpx.AsyncClient() as client:
            url = f"https://api.mapbox.com/directions/v5/mapbox/driving/{coords_str}"
            params = {
                'access_token': MAPBOX_ACCESS_TOKEN,
                'geometries': 'polyline',
                'overview': 'full'
            }
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            # Check for "no route" response
            if data.get('code') == 'NoRoute':
                logger.warning(f"No drivable route found between coordinates")
                return None
            
            if data.get('routes') and len(data['routes']) > 0:
                route = data['routes'][0]
                return {
                    'geometry': route['geometry'],
                    'duration': route.get('duration', 0) / 60,  # Convert to minutes
                    'distance': route.get('distance', 0) / 1609.34  # Convert to miles
                }
            else:
                logger.warning(f"No routes in Mapbox response: {data.get('code', 'unknown')}")
    except Exception as e:
        logger.error(f"Mapbox route error: {e}")
    return None

async def get_noaa_weather(lat: float, lon: float) -> Optional[WeatherData]:
    """Get weather data from NOAA for a location with sunrise/sunset."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # First get the grid point
            point_url = f"https://api.weather.gov/points/{lat:.4f},{lon:.4f}"
            point_response = await client.get(point_url, headers=NOAA_HEADERS)
            
            if point_response.status_code != 200:
                logger.warning(f"NOAA points API error for {lat},{lon}: {point_response.status_code}")
                return None
            
            point_data = point_response.json()
            props = point_data.get('properties', {})
            forecast_url = props.get('forecastHourly')
            
            if not forecast_url:
                return None
            
            # Get hourly forecast
            forecast_response = await client.get(forecast_url, headers=NOAA_HEADERS)
            
            if forecast_response.status_code != 200:
                logger.warning(f"NOAA forecast API error: {forecast_response.status_code}")
                return None
            
            forecast_data = forecast_response.json()
            periods = forecast_data.get('properties', {}).get('periods', [])
            
            # Get hourly forecasts for timeline
            hourly_forecast = []
            for period in periods[:12]:  # Next 12 hours
                hourly_forecast.append(HourlyForecast(
                    time=period.get('startTime', ''),
                    temperature=period.get('temperature', 0),
                    conditions=period.get('shortForecast', ''),
                    wind_speed=period.get('windSpeed', ''),
                    precipitation_chance=period.get('probabilityOfPrecipitation', {}).get('value')
                ))
            
            if periods:
                current = periods[0]
                
                # Calculate approximate sunrise/sunset based on time of day
                # This is simplified - in production, use a proper sun calculation library
                is_daytime = current.get('isDaytime', True)
                now = datetime.now()
                sunrise = now.replace(hour=6, minute=30).strftime("%I:%M %p")
                sunset = now.replace(hour=18, minute=30).strftime("%I:%M %p")
                
                return WeatherData(
                    temperature=current.get('temperature'),
                    temperature_unit=current.get('temperatureUnit', 'F'),
                    wind_speed=current.get('windSpeed'),
                    wind_direction=current.get('windDirection'),
                    conditions=current.get('shortForecast'),
                    icon=current.get('icon'),
                    humidity=current.get('relativeHumidity', {}).get('value'),
                    is_daytime=is_daytime,
                    sunrise=sunrise,
                    sunset=sunset,
                    hourly_forecast=hourly_forecast
                )
    except Exception as e:
        logger.error(f"NOAA weather error for {lat},{lon}: {e}")
    return None

async def get_noaa_alerts(lat: float, lon: float) -> List[WeatherAlert]:
    """Get weather alerts from NOAA for a location."""
    alerts = []
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            url = f"https://api.weather.gov/alerts?point={lat:.4f},{lon:.4f}"
            response = await client.get(url, headers=NOAA_HEADERS)
            
            if response.status_code == 200:
                data = response.json()
                features = data.get('features', [])
                
                for feature in features[:5]:  # Limit to 5 alerts
                    props = feature.get('properties', {})
                    alerts.append(WeatherAlert(
                        id=props.get('id', str(uuid.uuid4())),
                        headline=props.get('headline', 'Weather Alert'),
                        severity=props.get('severity', 'Unknown'),
                        event=props.get('event', 'Weather Event'),
                        description=props.get('description', '')[:500],
                        areas=props.get('areaDesc')
                    ))
    except Exception as e:
        logger.error(f"NOAA alerts error for {lat},{lon}: {e}")
    return alerts

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
                countdown_text=f"High winds in {eta_mins} minutes" if eta_mins > 0 else "High winds at start"
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
                countdown_text=f"Heavy rain in {eta_mins} minutes at mile {int(distance)}"
            ))
        elif "rain" in conditions or "shower" in conditions:
            alerts.append(HazardAlert(
                type="rain",
                severity="medium",
                distance_miles=distance,
                eta_minutes=eta_mins,
                message="Rain expected",
                recommendation="Turn on headlights and wipers",
                countdown_text=f"Rain in {eta_mins} minutes"
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
                countdown_text=f"Snow conditions in {eta_mins} minutes"
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
                countdown_text=f"Ice risk zone in {eta_mins} minutes"
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
                countdown_text=f"Fog in {eta_mins} minutes"
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
                countdown_text=f"{alert.event} in {eta_mins} minutes"
            ))
    
    # Sort by distance and deduplicate similar alerts
    alerts.sort(key=lambda x: x.distance_miles)
    return alerts[:10]  # Return top 10 alerts

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
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Search for POIs near this point
                url = f"https://api.mapbox.com/geocoding/v5/mapbox.places/rest+stop+gas+station.json"
                params = {
                    'access_token': MAPBOX_ACCESS_TOKEN,
                    'proximity': f"{lon},{lat}",
                    'types': 'poi',
                    'limit': 2
                }
                response = await client.get(url, params=params)
                
                if response.status_code == 200:
                    data = response.json()
                    for feature in data.get('features', [])[:1]:
                        place_name = feature.get('text', 'Rest Stop')
                        coords = feature.get('center', [lon, lat])
                        
                        # Find nearest waypoint weather
                        weather_desc = "Unknown"
                        temp = None
                        for wp in waypoints_weather:
                            if wp.weather and abs(wp.waypoint.distance_from_start - approx_distance) < 30:
                                weather_desc = wp.weather.conditions or "Clear"
                                temp = wp.weather.temperature
                                break
                        
                        # Generate recommendation
                        recommendation = "Good rest stop option"
                        if temp and temp > 85:
                            recommendation = "Cool down and hydrate here"
                        elif "rain" in weather_desc.lower():
                            recommendation = "Wait out the rain here"
                        elif "clear" in weather_desc.lower() or "sunny" in weather_desc.lower():
                            recommendation = "Good weather - stretch your legs!"
                            
                        rest_stops.append(RestStop(
                            name=place_name,
                            type="rest_area",
                            lat=coords[1],
                            lon=coords[0],
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
    
    # NEW: Generate trucker-specific warnings if enabled
    trucker_warnings = []
    if request.trucker_mode:
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
        logger.error(f"Chat error: {e}")
        return ChatResponse(
            response="I'm having trouble connecting right now. Please check your route conditions on the main screen or try again in a moment.",
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
        # Save token to MongoDB
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
            # Update last_used timestamp
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
    is_premium = False
    if request.subscription_id:
        # Verify subscription is active
        try:
            sub = await db.subscriptions.find_one(
                {'subscription_id': request.subscription_id, 'status': 'active'}
            )
            is_premium = sub is not None
            
            if is_premium:
                logger.info(f"[PREMIUM] Solar forecast accessed by: {request.subscription_id}")
        except Exception as e:
            logger.error(f"[PREMIUM] Error checking subscription: {e}")
            is_premium = False
    
    # Return premium-locked response if not authorized
    if not is_premium:
        logger.info(f"[PREMIUM] Solar forecast access denied - premium required")
        return SolarForecastResponse(
            is_premium_locked=True,
            premium_message="Upgrade to Routecast Pro to forecast solar energy generation and plan your boondocking power needs."
        )
    
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
    is_premium = False
    if request.subscription_id:
        # Verify subscription is active
        try:
            sub = await db.subscriptions.find_one(
                {'subscription_id': request.subscription_id, 'status': 'active'}
            )
            is_premium = sub is not None
            
            if is_premium:
                logger.info(f"[PREMIUM] Propane usage accessed by: {request.subscription_id}")
        except Exception as e:
            logger.error(f"[PREMIUM] Error checking subscription: {e}")
            is_premium = False
    
    # Return premium-locked response if not authorized
    if not is_premium:
        logger.info(f"[PREMIUM] Propane usage access denied - premium required")
        return PropaneUsageResponse(
            is_premium_locked=True,
            premium_message="Upgrade to Routecast Pro to estimate propane consumption for boondocking trips."
        )
    
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
                logger.info(f"[PREMIUM] Water budget accessed by: {request.subscription_id}")
        except Exception as e:
            logger.error(f"[PREMIUM] Error checking subscription: {e}")
            is_premium = False
    
    # Return premium-locked response if not authorized
    if not is_premium:
        logger.info(f"[PREMIUM] Water budget access denied - premium required")
        return WaterBudgetResponse(
            is_premium_locked=True,
            premium_message="Upgrade to Routecast Pro to plan water usage for boondocking trips."
        )
    
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
app.include_router(api_router)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
