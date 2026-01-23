"""
Weather Radar & Alerts Integration
Integrates weather-api submodule endpoints into Routecast2 backend
"""
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime, timedelta
import httpx
import logging
import uuid

logger = logging.getLogger(__name__)

# Create router for radar/alerts endpoints
radar_router = APIRouter(prefix="/radar")

# NWS API base URL
NWS_API_BASE = "https://api.weather.gov"

# 10-minute cache for alerts with geometry (expensive operation)
alerts_with_geo_cache = {
    "data": None,
    "last_updated": None,
    "ttl": 600  # 10 minutes
}

# 5-minute cache for basic alerts
alerts_cache = {
    "data": None,
    "last_updated": None,
    "ttl": 300  # 5 minutes
}

# Alert type colors and categories
ALERT_CATEGORIES = {
    "Tornado Warning": {"color": "#FF0000", "category": "tornado", "priority": 1},
    "Tornado Watch": {"color": "#FFFF00", "category": "tornado", "priority": 2},
    "Severe Thunderstorm Warning": {"color": "#FFA500", "category": "thunderstorm", "priority": 1},
    "Severe Thunderstorm Watch": {"color": "#DB7093", "category": "thunderstorm", "priority": 2},
    "Hurricane Warning": {"color": "#DC143C", "category": "hurricane", "priority": 1},
    "Hurricane Watch": {"color": "#FF00FF", "category": "hurricane", "priority": 2},
    "Tropical Storm Warning": {"color": "#B22222", "category": "hurricane", "priority": 3},
    "Tropical Storm Watch": {"color": "#F08080", "category": "hurricane", "priority": 4},
    "Flash Flood Warning": {"color": "#8B0000", "category": "rain", "priority": 1},
    "Flash Flood Watch": {"color": "#2E8B57", "category": "rain", "priority": 2},
    "Flood Warning": {"color": "#00FF00", "category": "rain", "priority": 3},
    "Flood Watch": {"color": "#2E8B57", "category": "rain", "priority": 4},
    "Winter Storm Warning": {"color": "#FF69B4", "category": "snow", "priority": 1},
    "Winter Storm Watch": {"color": "#4682B4", "category": "snow", "priority": 2},
    "Blizzard Warning": {"color": "#FF4500", "category": "snow", "priority": 1},
    "Ice Storm Warning": {"color": "#8B008B", "category": "ice", "priority": 1},
    "Freezing Rain Advisory": {"color": "#DA70D6", "category": "ice", "priority": 2},
    "Winter Weather Advisory": {"color": "#7B68EE", "category": "snow", "priority": 3},
    "Extreme Cold Warning": {"color": "#0000FF", "category": "ice", "priority": 1},
    "Extreme Cold Watch": {"color": "#5F9EA0", "category": "ice", "priority": 2},
    "Wind Chill Warning": {"color": "#B0C4DE", "category": "ice", "priority": 1},
    "Wind Chill Watch": {"color": "#5F9EA0", "category": "ice", "priority": 2},
    "Wind Chill Advisory": {"color": "#AFEEEE", "category": "ice", "priority": 3},
    "High Wind Warning": {"color": "#DAA520", "category": "thunderstorm", "priority": 3},
    "Wind Advisory": {"color": "#D2B48C", "category": "thunderstorm", "priority": 4},
    "Special Weather Statement": {"color": "#FFE4B5", "category": "other", "priority": 5},
}

# Models
class AlertFeature(BaseModel):
    id: str
    event: str
    headline: Optional[str] = ""
    description: str
    severity: str
    urgency: str
    areas: List[str]
    effective: Optional[str]
    expires: Optional[str]
    color: str
    category: str
    priority: int
    geometry: Optional[Dict[str, Any]]

class AlertsResponse(BaseModel):
    alerts: List[AlertFeature]
    last_updated: str
    total_count: int
    categories: Dict[str, int]

# Cache for zone geometries
zone_geometry_cache: Dict[str, Any] = {}

async def fetch_nws_data(endpoint: str) -> Dict:
    """Fetch data from NWS API with proper headers"""
    headers = {
        "User-Agent": "(Routecast/1.0 contact@routecast.app)",
        "Accept": "application/geo+json"
    }
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        response = await client.get(f"{NWS_API_BASE}{endpoint}", headers=headers)
        response.raise_for_status()
        return response.json()

async def fetch_zone_geometry(zone_url: str) -> Optional[Dict]:
    """Fetch geometry for a zone"""
    if zone_url in zone_geometry_cache:
        return zone_geometry_cache[zone_url]
    
    try:
        headers = {
            "User-Agent": "(Routecast/1.0 contact@routecast.app)",
            "Accept": "application/geo+json"
        }
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            response = await client.get(zone_url, headers=headers)
            if response.status_code == 200:
                data = response.json()
                geometry = data.get("geometry")
                if geometry:
                    zone_geometry_cache[zone_url] = geometry
                    return geometry
    except Exception as e:
        logger.debug(f"Failed to fetch zone geometry: {e}")
    return None

def parse_alert_feature_sync(feature: Dict) -> AlertFeature:
    """Parse NWS alert feature into our format (sync version)"""
    props = feature.get("properties", {})
    event = props.get("event", "Unknown")
    
    alert_info = ALERT_CATEGORIES.get(event, {
        "color": "#808080",
        "category": "other",
        "priority": 10
    })
    
    areas = []
    if props.get("areaDesc"):
        areas = [a.strip() for a in props["areaDesc"].split(";")]
    
    headline = props.get("headline") or ""
    description = props.get("description", "") or ""
    if len(description) > 500:
        description = description[:500] + "..."
    
    return AlertFeature(
        id=props.get("id", str(uuid.uuid4())),
        event=event,
        headline=headline,
        description=description,
        severity=props.get("severity", "Unknown") or "Unknown",
        urgency=props.get("urgency", "Unknown") or "Unknown",
        areas=areas,
        effective=props.get("effective"),
        expires=props.get("expires"),
        color=alert_info["color"],
        category=alert_info["category"],
        priority=alert_info["priority"],
        geometry=feature.get("geometry")
    )

@radar_router.get("/alerts/map")
async def get_alerts_with_geometry(force_refresh: bool = Query(False, description="Force cache refresh")):
    """Get weather alerts WITH zone geometry for map display (10-minute cache)"""
    global alerts_with_geo_cache
    
    now = datetime.utcnow()
    if (not force_refresh and 
        alerts_with_geo_cache["data"] is not None and 
        alerts_with_geo_cache["last_updated"] is not None and
        (now - alerts_with_geo_cache["last_updated"]).total_seconds() < alerts_with_geo_cache["ttl"]):
        return alerts_with_geo_cache["data"]
    
    try:
        # Fetch active alerts from NWS
        data = await fetch_nws_data("/alerts/active")
        features = data.get("features", [])
        
        alerts = []
        categories = {}
        
        # Process alerts and fetch zone geometries for those without geometry
        # Limit to first 200 alerts to avoid timeout
        for feature in features[:200]:
            try:
                props = feature.get("properties", {})
                event = props.get("event", "Unknown")
                
                alert_info = ALERT_CATEGORIES.get(event, {
                    "color": "#808080",
                    "category": "other",
                    "priority": 10
                })
                
                areas = []
                if props.get("areaDesc"):
                    areas = [a.strip() for a in props["areaDesc"].split(";")]
                
                headline = props.get("headline") or ""
                description = props.get("description", "") or ""
                if len(description) > 500:
                    description = description[:500] + "..."
                
                # Get geometry - first from alert, then try to fetch from first affected zone
                geometry = feature.get("geometry")
                
                if not geometry:
                    affected_zones = props.get("affectedZones", [])
                    if affected_zones and len(affected_zones) > 0:
                        # Try to get geometry from first zone
                        geo = await fetch_zone_geometry(affected_zones[0])
                        if geo:
                            geometry = geo
                
                alert = AlertFeature(
                    id=props.get("id", str(uuid.uuid4())),
                    event=event,
                    headline=headline,
                    description=description,
                    severity=props.get("severity", "Unknown") or "Unknown",
                    urgency=props.get("urgency", "Unknown") or "Unknown",
                    areas=areas,
                    effective=props.get("effective"),
                    expires=props.get("expires"),
                    color=alert_info["color"],
                    category=alert_info["category"],
                    priority=alert_info["priority"],
                    geometry=geometry
                )
                
                alerts.append(alert)
                
                if alert.category not in categories:
                    categories[alert.category] = 0
                categories[alert.category] += 1
                
            except Exception as e:
                logger.warning(f"Failed to parse alert: {e}")
                continue
        
        alerts.sort(key=lambda x: x.priority)
        
        # Filter to only include alerts with geometry
        alerts_with_geo = [a for a in alerts if a.geometry is not None]
        
        response = {
            "alerts": alerts_with_geo,
            "last_updated": now.isoformat(),
            "total_count": len(alerts_with_geo),
            "total_alerts": len(alerts),
            "categories": categories
        }
        
        alerts_with_geo_cache["data"] = response
        alerts_with_geo_cache["last_updated"] = now
        
        return response
        
    except httpx.HTTPError as e:
        logger.error(f"Failed to fetch alerts from NWS: {e}")
        if alerts_with_geo_cache["data"] is not None:
            return alerts_with_geo_cache["data"]
        raise HTTPException(status_code=503, detail="Unable to fetch weather alerts")

@radar_router.get("/tiles")
async def get_radar_tile_info():
    """Get radar tile URL template for overlay on maps"""
    # RainViewer provides free radar tiles
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get("https://api.rainviewer.com/public/weather-maps.json")
            response.raise_for_status()
            data = response.json()
            
            # Get latest radar timestamp
            radar = data.get("radar", {})
            past_frames = radar.get("past", [])
            
            if past_frames:
                latest_frame = past_frames[-1]
                timestamp = latest_frame.get("path", "")
                
                return {
                    "tile_url": f"https://tilecache.rainviewer.com{timestamp}/512/{{z}}/{{x}}/{{y}}/2/1_1.png",
                    "timestamp": latest_frame.get("time"),
                    "frames": [{
                        "path": f"https://tilecache.rainviewer.com{f['path']}/512/{{z}}/{{x}}/{{y}}/2/1_1.png",
                        "time": f["time"]
                    } for f in past_frames[-6:]],  # Last 6 frames for animation
                    "coverage_url": "https://tilecache.rainviewer.com/v2/coverage/0/512/{z}/{x}/{y}/0/0_1.png"
                }
    except Exception as e:
        logger.warning(f"Failed to fetch radar tiles: {e}")
    
    return {
        "tile_url": None,
        "message": "Radar tiles temporarily unavailable"
    }

@radar_router.get("/alert-types")
async def get_alert_types():
    """Get all supported alert types with their colors and categories"""
    return {
        "alert_types": ALERT_CATEGORIES,
        "categories": ["tornado", "hurricane", "thunderstorm", "rain", "snow", "ice", "other"]
    }
