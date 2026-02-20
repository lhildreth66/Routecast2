"""
Weight Restriction Service for RouteCast
Provides truck weight restriction data using OpenStreetMap Overpass API.
"""

import httpx
import asyncio
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from math import radians, sin, cos, sqrt, atan2
import logging

logger = logging.getLogger(__name__)

# Overpass API endpoints
OVERPASS_API_URL = "https://overpass-api.de/api/interpreter"
OVERPASS_BACKUP_URL = "https://overpass.kumi.systems/api/interpreter"


@dataclass
class WeightRestriction:
    """Represents a weight-restricted road segment."""
    location_name: str
    latitude: float
    longitude: float
    max_weight_tons: Optional[float]
    max_axle_weight_tons: Optional[float]
    restriction_type: str  # "bridge", "road", "seasonal", "posted"
    highway_type: Optional[str]
    osm_id: Optional[int]
    source: str = "osm"
    note: Optional[str] = None


def tons_to_lbs(tons: float) -> float:
    """Convert metric tons to pounds."""
    return tons * 2204.62


def lbs_to_tons(lbs: float) -> float:
    """Convert pounds to metric tons."""
    return lbs / 2204.62


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points in miles."""
    R = 3959  # Earth's radius in miles

    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))

    return R * c


def parse_weight_value(value: str) -> Optional[float]:
    """
    Parse OSM weight value to metric tons.

    Formats:
    - "7.5" -> 7.5 tons
    - "7.5 t" -> 7.5 tons
    - "16500 lb" or "16500 lbs" -> convert to tons
    - "16500#" -> pounds, convert to tons
    - "7500 kg" -> convert to tons
    """
    if not value:
        return None

    value = value.strip().lower()

    # Handle "none", "no", etc.
    if value in ["none", "no", "default", "unsigned"]:
        return None

    try:
        # Pounds format
        if "lb" in value or "#" in value:
            num = float(''.join(c for c in value if c.isdigit() or c == '.'))
            return lbs_to_tons(num)

        # Kilograms format
        if "kg" in value:
            num = float(''.join(c for c in value if c.isdigit() or c == '.'))
            return num / 1000

        # Short tons (US)
        if "st" in value and "short" not in value:
            num = float(''.join(c for c in value if c.isdigit() or c == '.'))
            return num * 0.907185  # Short ton to metric ton

        # Metric tons (default)
        num_str = ''.join(c for c in value if c.isdigit() or c == '.')
        if num_str:
            return float(num_str)

        return None

    except (ValueError, AttributeError):
        return None


async def query_overpass_weight_restrictions(
    bbox_points: List[Tuple[float, float]],
) -> List[Dict]:
    """
    Query Overpass API for weight restrictions.

    OSM tags for weight restrictions:
    - maxweight: Maximum total vehicle weight
    - maxaxleload: Maximum weight per axle
    - hgv (heavy goods vehicle): no/designated/delivery
    - goods: no/delivery
    """

    # Build bounding box
    lats = [p[0] for p in bbox_points]
    lons = [p[1] for p in bbox_points]

    min_lat, max_lat = min(lats), max(lats)
    min_lon, max_lon = min(lons), max(lons)

    buffer = 0.01
    bbox = f"{min_lat - buffer},{min_lon - buffer},{max_lat + buffer},{max_lon + buffer}"

    # Overpass query for weight restrictions
    query = f"""
    [out:json][timeout:30];
    (
      way["maxweight"]({bbox});
      way["maxaxleload"]({bbox});
      way["hgv"="no"]({bbox});
      way["hgv"="delivery"]({bbox});
      way["goods"="no"]({bbox});
      way["motor_vehicle"="no"]["highway"]({bbox});
      way["bridge"]["maxweight"]({bbox});
    );
    out body;
    >;
    out skel qt;
    """

    results = []

    async with httpx.AsyncClient(timeout=30.0) as client:
        for api_url in [OVERPASS_API_URL, OVERPASS_BACKUP_URL]:
            try:
                response = await client.post(
                    api_url,
                    data={"data": query},
                    headers={"Content-Type": "application/x-www-form-urlencoded"}
                )

                if response.status_code == 200:
                    data = response.json()
                    results = data.get("elements", [])
                    break

            except Exception as e:
                logger.error(f"Overpass API error ({api_url}): {e}")
                continue

    return results


def extract_weight_restrictions(
    elements: List[Dict],
    center_point: Tuple[float, float],
    radius_miles: float = 20
) -> List[WeightRestriction]:
    """Extract weight restriction data from Overpass response."""

    restrictions = []
    node_coords = {}

    # First pass: collect node coordinates
    for elem in elements:
        if elem.get("type") == "node":
            node_coords[elem["id"]] = (elem.get("lat"), elem.get("lon"))

    # Second pass: process ways with restrictions
    for elem in elements:
        if elem.get("type") != "way":
            continue

        tags = elem.get("tags", {})

        # Get weight values
        max_weight = parse_weight_value(tags.get("maxweight"))
        max_axle = parse_weight_value(tags.get("maxaxleload"))

        # Determine restriction type
        restriction_type = "posted"
        note = None

        if tags.get("bridge"):
            restriction_type = "bridge"

        if tags.get("hgv") == "no":
            restriction_type = "hgv_prohibited"
            note = "Heavy goods vehicles prohibited"
        elif tags.get("hgv") == "delivery":
            restriction_type = "hgv_delivery_only"
            note = "HGV delivery access only"

        if tags.get("goods") == "no":
            restriction_type = "goods_prohibited"
            note = "Goods vehicles prohibited"

        if tags.get("motor_vehicle") == "no":
            restriction_type = "no_motor_vehicles"
            note = "No motor vehicles"

        # Skip if no useful restriction info
        if not max_weight and not max_axle and restriction_type == "posted":
            continue

        # Get center point of the way
        nodes = elem.get("nodes", [])
        way_coords = [node_coords.get(n) for n in nodes if n in node_coords]
        way_coords = [c for c in way_coords if c and c[0] and c[1]]

        if not way_coords:
            continue

        center_lat = sum(c[0] for c in way_coords) / len(way_coords)
        center_lon = sum(c[1] for c in way_coords) / len(way_coords)

        # Check distance from search point
        distance = haversine_distance(center_point[0], center_point[1], center_lat, center_lon)
        if distance > radius_miles:
            continue

        # Build location name
        location_parts = []
        if tags.get("name"):
            location_parts.append(tags["name"])
        if tags.get("ref"):
            location_parts.append(tags["ref"])
        if tags.get("highway"):
            location_parts.append(f"({tags['highway']})")

        location_name = " ".join(location_parts) if location_parts else "Road segment"

        restrictions.append(WeightRestriction(
            location_name=location_name,
            latitude=center_lat,
            longitude=center_lon,
            max_weight_tons=max_weight,
            max_axle_weight_tons=max_axle,
            restriction_type=restriction_type,
            highway_type=tags.get("highway"),
            osm_id=elem.get("id"),
            source="osm",
            note=note
        ))

    return restrictions


async def get_weight_restrictions(
    latitude: float,
    longitude: float,
    vehicle_weight_lbs: float = 80000,
    radius_miles: int = 20
) -> Dict:
    """
    Get weight-restricted roads near a location.

    Args:
        latitude: Search center latitude
        longitude: Search center longitude
        vehicle_weight_lbs: Vehicle weight in pounds (default 80,000 for loaded semi)
        radius_miles: Search radius in miles

    Returns:
        Dict with results and metadata
    """

    vehicle_weight_tons = lbs_to_tons(vehicle_weight_lbs)

    # Create bounding box points
    buffer = radius_miles / 69.0
    bbox_points = [
        (latitude - buffer, longitude - buffer),
        (latitude - buffer, longitude + buffer),
        (latitude + buffer, longitude - buffer),
        (latitude + buffer, longitude + buffer),
        (latitude, longitude)
    ]

    try:
        # Query Overpass API
        osm_elements = await query_overpass_weight_restrictions(bbox_points)
        restrictions = extract_weight_restrictions(
            osm_elements,
            (latitude, longitude),
            radius_miles
        )

        results = []
        for r in restrictions:
            # Calculate distance
            distance = haversine_distance(latitude, longitude, r.latitude, r.longitude)

            # Determine if this is a problem for the vehicle
            is_restricted = False
            warning_message = None

            if r.max_weight_tons and vehicle_weight_tons > r.max_weight_tons:
                is_restricted = True
                max_lbs = tons_to_lbs(r.max_weight_tons)
                warning_message = f"Weight limit {max_lbs:,.0f} lbs - your vehicle exceeds by {vehicle_weight_lbs - max_lbs:,.0f} lbs"

            if r.restriction_type in ["hgv_prohibited", "goods_prohibited", "no_motor_vehicles"]:
                is_restricted = True
                warning_message = r.note

            results.append({
                "location": r.location_name,
                "latitude": r.latitude,
                "longitude": r.longitude,
                "distance_miles": round(distance, 1),
                "max_weight_tons": round(r.max_weight_tons, 1) if r.max_weight_tons else None,
                "max_weight_lbs": round(tons_to_lbs(r.max_weight_tons)) if r.max_weight_tons else None,
                "max_axle_weight_tons": round(r.max_axle_weight_tons, 1) if r.max_axle_weight_tons else None,
                "restriction_type": r.restriction_type,
                "highway_type": r.highway_type,
                "is_restricted": is_restricted,
                "warning_message": warning_message,
                "note": r.note,
                "source": r.source,
                "osm_id": r.osm_id
            })

        # Sort by distance
        results.sort(key=lambda x: x["distance_miles"])

        # Prioritize restricted roads at the top
        results.sort(key=lambda x: (not x["is_restricted"], x["distance_miles"]))

        return {
            "results": results[:30],  # Limit results
            "total": len(results),
            "vehicle_weight_lbs": vehicle_weight_lbs,
            "vehicle_weight_tons": round(vehicle_weight_tons, 1),
            "source": "OpenStreetMap Overpass API",
            "warning": "Always verify restrictions with posted signage. OSM data may not be complete."
        }

    except Exception as e:
        logger.error(f"Error fetching weight restrictions: {e}")
        return {
            "results": [],
            "total": 0,
            "error": str(e),
            "source": "OpenStreetMap Overpass API"
        }


async def get_weight_restrictions_for_route(
    route_polyline: str,
    vehicle_weight_lbs: float = 80000
) -> List[Dict]:
    """
    Get weight restrictions along a route.

    Args:
        route_polyline: Google-encoded polyline of the route
        vehicle_weight_lbs: Vehicle weight in pounds

    Returns:
        List of restrictions along the route
    """
    from services.bridge_height_service import decode_polyline, sample_route_points

    try:
        route_points = decode_polyline(route_polyline)
    except Exception as e:
        logger.error(f"Error decoding polyline: {e}")
        return []

    if not route_points:
        return []

    # Sample points along route
    sampled_points = sample_route_points(route_points, max_points=20)

    vehicle_weight_tons = lbs_to_tons(vehicle_weight_lbs)

    try:
        # Query for all sampled points
        osm_elements = await query_overpass_weight_restrictions(sampled_points)
        restrictions = extract_weight_restrictions(
            osm_elements,
            sampled_points[0],  # Use first point as reference
            radius_miles=100  # Wide radius since we're checking along route
        )

        # Filter to restrictions actually near the route
        route_restrictions = []
        for r in restrictions:
            # Check if near any route point
            min_distance = float('inf')
            for rp in route_points:
                dist = haversine_distance(r.latitude, r.longitude, rp[0], rp[1])
                min_distance = min(min_distance, dist)

            if min_distance > 0.5:  # Within 0.5 miles of route
                continue

            # Check if restricted for this vehicle
            is_problem = False
            message = None

            if r.max_weight_tons and vehicle_weight_tons > r.max_weight_tons:
                is_problem = True
                max_lbs = tons_to_lbs(r.max_weight_tons)
                message = f"WEIGHT LIMIT: {max_lbs:,.0f} lbs (your load: {vehicle_weight_lbs:,.0f} lbs)"

            if r.restriction_type in ["hgv_prohibited", "goods_prohibited"]:
                is_problem = True
                message = r.note or "Heavy vehicles prohibited"

            if is_problem:
                route_restrictions.append({
                    "location": r.location_name,
                    "latitude": r.latitude,
                    "longitude": r.longitude,
                    "max_weight_lbs": round(tons_to_lbs(r.max_weight_tons)) if r.max_weight_tons else None,
                    "restriction_type": r.restriction_type,
                    "warning_level": "danger",
                    "message": message
                })

        # Remove duplicates
        seen = set()
        unique = []
        for r in route_restrictions:
            key = (r["location"], round(r["latitude"], 3), round(r["longitude"], 3))
            if key not in seen:
                seen.add(key)
                unique.append(r)

        return unique

    except Exception as e:
        logger.error(f"Error getting route weight restrictions: {e}")
        return []
