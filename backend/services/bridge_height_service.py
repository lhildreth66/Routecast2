"""
Bridge Height Service for RouteCast
Provides low clearance warnings using OpenStreetMap Overpass API.
Architected for easy integration of commercial data sources (e.g., LCM API).
"""

import httpx
import asyncio
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from math import radians, sin, cos, sqrt, atan2
import os

# Overpass API endpoints (public, no key required)
OVERPASS_API_URL = "https://overpass-api.de/api/interpreter"
OVERPASS_BACKUP_URL = "https://overpass.kumi.systems/api/interpreter"

# LCM API placeholder (for future integration)
LCM_API_KEY = os.environ.get("LCM_API_KEY")
LCM_API_URL = "https://api.lowclearancemap.com/v1"  # Placeholder


@dataclass
class BridgeHeightResult:
    """Represents a low clearance obstacle."""
    location_name: str
    latitude: float
    longitude: float
    clearance_ft: float
    clearance_meters: float
    osm_id: Optional[int] = None
    highway_type: Optional[str] = None
    source: str = "osm"  # "osm", "lcm", or "dot"
    confidence: str = "estimated"  # "verified", "estimated", "reported"
    last_updated: Optional[str] = None


def meters_to_feet(meters: float) -> float:
    """Convert meters to feet."""
    return meters * 3.28084


def feet_to_meters(feet: float) -> float:
    """Convert feet to meters."""
    return feet / 3.28084


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points in miles."""
    R = 3959  # Earth's radius in miles

    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))

    return R * c


def decode_polyline(encoded: str) -> List[Tuple[float, float]]:
    """Decode Google polyline format to list of (lat, lng) tuples."""
    points = []
    index = 0
    lat = 0
    lng = 0

    while index < len(encoded):
        # Decode latitude
        shift = 0
        result = 0
        while True:
            b = ord(encoded[index]) - 63
            index += 1
            result |= (b & 0x1f) << shift
            shift += 5
            if b < 0x20:
                break
        dlat = ~(result >> 1) if result & 1 else result >> 1
        lat += dlat

        # Decode longitude
        shift = 0
        result = 0
        while True:
            b = ord(encoded[index]) - 63
            index += 1
            result |= (b & 0x1f) << shift
            shift += 5
            if b < 0x20:
                break
        dlng = ~(result >> 1) if result & 1 else result >> 1
        lng += dlng

        points.append((lat / 1e5, lng / 1e5))

    return points


def sample_route_points(points: List[Tuple[float, float]], max_points: int = 50) -> List[Tuple[float, float]]:
    """Sample points along route to avoid excessive API calls."""
    if len(points) <= max_points:
        return points

    step = len(points) / max_points
    return [points[int(i * step)] for i in range(max_points)]


async def query_overpass_for_clearances(
    bbox_or_points: List[Tuple[float, float]],
    search_radius_meters: int = 100
) -> List[Dict]:
    """
    Query Overpass API for maxheight tags near route points.

    OpenStreetMap uses maxheight tag for bridge/tunnel clearances.
    Common tags: maxheight, maxheight:physical, maxheight:legal
    """

    # Build bounding box from route points
    lats = [p[0] for p in bbox_or_points]
    lons = [p[1] for p in bbox_or_points]

    min_lat, max_lat = min(lats), max(lats)
    min_lon, max_lon = min(lons), max(lons)

    # Add small buffer
    buffer = 0.01  # ~1km buffer
    bbox = f"{min_lat - buffer},{min_lon - buffer},{max_lat + buffer},{max_lon + buffer}"

    # Overpass QL query for structures with maxheight
    query = f"""
    [out:json][timeout:30];
    (
      way["maxheight"]({bbox});
      way["maxheight:physical"]({bbox});
      node["maxheight"]({bbox});
      way["bridge"]["maxheight"]({bbox});
      way["tunnel"]["maxheight"]({bbox});
      way["man_made"="bridge"]["maxheight"]({bbox});
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
                print(f"Overpass API error ({api_url}): {e}")
                continue

    return results


def parse_maxheight(value: str) -> Optional[float]:
    """
    Parse OSM maxheight value to meters.

    Formats:
    - "4.2" -> 4.2 meters
    - "4.2 m" -> 4.2 meters
    - "13'6\"" or "13' 6\"" -> feet/inches to meters
    - "13.5'" -> feet to meters
    - "below_default" -> None
    """
    if not value or value in ["default", "none", "below_default"]:
        return None

    value = value.strip().lower()

    # Handle feet/inches format (e.g., 13'6" or 13' 6")
    if "'" in value:
        try:
            # Remove quotes and normalize
            value = value.replace('"', '').replace("'", "'")
            parts = value.split("'")
            feet = float(parts[0].strip())
            inches = 0
            if len(parts) > 1 and parts[1].strip():
                inches = float(parts[1].strip())
            total_feet = feet + inches / 12
            return feet_to_meters(total_feet)
        except (ValueError, IndexError):
            return None

    # Handle metric format
    try:
        # Remove unit suffixes
        value = value.replace("m", "").replace("meter", "").replace("meters", "").strip()
        return float(value)
    except ValueError:
        return None


def extract_bridge_data(elements: List[Dict], route_points: List[Tuple[float, float]]) -> List[BridgeHeightResult]:
    """
    Extract bridge clearance data from Overpass response.
    """
    bridges = []
    node_coords = {}

    # First pass: collect node coordinates
    for elem in elements:
        if elem.get("type") == "node":
            node_coords[elem["id"]] = (elem.get("lat"), elem.get("lon"))

    # Second pass: process ways with maxheight
    for elem in elements:
        if elem.get("type") != "way":
            continue

        tags = elem.get("tags", {})

        # Get maxheight value (try multiple tag variants)
        maxheight_str = (
            tags.get("maxheight") or
            tags.get("maxheight:physical") or
            tags.get("maxheight:legal")
        )

        if not maxheight_str:
            continue

        clearance_m = parse_maxheight(maxheight_str)
        if clearance_m is None or clearance_m <= 0:
            continue

        # Get center point of the way
        nodes = elem.get("nodes", [])
        way_coords = [node_coords.get(n) for n in nodes if n in node_coords]
        way_coords = [c for c in way_coords if c and c[0] and c[1]]

        if not way_coords:
            continue

        # Calculate center point
        center_lat = sum(c[0] for c in way_coords) / len(way_coords)
        center_lon = sum(c[1] for c in way_coords) / len(way_coords)

        # Check if this bridge is near our route
        min_distance = float('inf')
        for rp in route_points:
            dist = haversine_distance(center_lat, center_lon, rp[0], rp[1])
            min_distance = min(min_distance, dist)

        # Only include bridges within 0.5 miles of route
        if min_distance > 0.5:
            continue

        # Build location name
        location_parts = []
        if tags.get("name"):
            location_parts.append(tags["name"])
        if tags.get("highway"):
            location_parts.append(f"({tags['highway']})")
        if tags.get("ref"):
            location_parts.append(tags["ref"])

        location_name = " ".join(location_parts) if location_parts else "Bridge/Overpass"

        # Determine confidence level
        confidence = "estimated"
        if tags.get("source:maxheight") == "survey":
            confidence = "verified"
        elif tags.get("maxheight:physical"):
            confidence = "verified"

        bridges.append(BridgeHeightResult(
            location_name=location_name,
            latitude=center_lat,
            longitude=center_lon,
            clearance_meters=clearance_m,
            clearance_ft=meters_to_feet(clearance_m),
            osm_id=elem.get("id"),
            highway_type=tags.get("highway"),
            source="osm",
            confidence=confidence
        ))

    return bridges


async def get_bridge_clearances_for_route(
    route_polyline: str,
    vehicle_height_ft: float = 13.5
) -> List[Dict]:
    """
    Get bridge clearance alerts for a route.

    Returns list of alerts for bridges where clearance may be an issue.

    Architecture:
    1. Try LCM API first (commercial, more accurate) - if API key available
    2. Fall back to OSM/Overpass data
    3. Return merged results sorted by distance along route
    """

    # Decode route polyline
    try:
        route_points = decode_polyline(route_polyline)
    except Exception as e:
        print(f"Error decoding polyline: {e}")
        return []

    if not route_points:
        return []

    # Sample points to avoid overloading API
    sampled_points = sample_route_points(route_points, max_points=30)

    all_bridges: List[BridgeHeightResult] = []

    # LAYER 1: Try LCM API if available (future integration)
    if LCM_API_KEY:
        try:
            lcm_bridges = await query_lcm_api(sampled_points, vehicle_height_ft)
            all_bridges.extend(lcm_bridges)
        except Exception as e:
            print(f"LCM API error: {e}")

    # LAYER 2: OpenStreetMap Overpass API (always available)
    try:
        osm_elements = await query_overpass_for_clearances(sampled_points)
        osm_bridges = extract_bridge_data(osm_elements, route_points)

        # Merge with existing results, avoiding duplicates
        existing_coords = {(b.latitude, b.longitude) for b in all_bridges}
        for bridge in osm_bridges:
            # Check for nearby existing entries (within ~50 meters)
            is_duplicate = False
            for existing in existing_coords:
                if haversine_distance(bridge.latitude, bridge.longitude, existing[0], existing[1]) < 0.03:
                    is_duplicate = True
                    break

            if not is_duplicate:
                all_bridges.append(bridge)

    except Exception as e:
        print(f"Overpass API error: {e}")

    # Convert to alert format
    alerts = []
    for bridge in all_bridges:
        margin = bridge.clearance_ft - vehicle_height_ft

        # Determine warning level
        if margin < 0:
            warning_level = "danger"
            message = f"DANGER: {bridge.clearance_ft:.1f}' clearance - {abs(margin):.1f}' BELOW your vehicle height!"
        elif margin < 0.5:
            warning_level = "danger"
            message = f"CRITICAL: Only {margin:.1f}' margin - DO NOT ATTEMPT"
        elif margin < 1.0:
            warning_level = "caution"
            message = f"CAUTION: Tight clearance - only {margin:.1f}' margin"
        elif margin < 2.0:
            warning_level = "caution"
            message = f"Low clearance ahead: {bridge.clearance_ft:.1f}' ({margin:.1f}' margin)"
        else:
            warning_level = "safe"
            message = f"Clearance OK: {bridge.clearance_ft:.1f}' ({margin:.1f}' margin)"

        # Calculate approximate distance from start
        distance_from_start = 0
        for i, rp in enumerate(route_points):
            if i > 0:
                distance_from_start += haversine_distance(
                    route_points[i-1][0], route_points[i-1][1],
                    rp[0], rp[1]
                )
            if haversine_distance(rp[0], rp[1], bridge.latitude, bridge.longitude) < 0.1:
                break

        alerts.append({
            "location": bridge.location_name,
            "latitude": bridge.latitude,
            "longitude": bridge.longitude,
            "clearance_ft": round(bridge.clearance_ft, 1),
            "vehicle_height_ft": vehicle_height_ft,
            "margin_ft": round(margin, 1),
            "warning_level": warning_level,
            "distance_miles": round(distance_from_start, 1),
            "highway": bridge.highway_type,
            "direction": None,  # Could be enhanced with bearing calculation
            "message": message,
            "source": bridge.source,
            "confidence": bridge.confidence
        })

    # Sort by distance along route
    alerts.sort(key=lambda x: x["distance_miles"])

    # Deduplicate: group alerts within 0.1 miles of each other with same name
    deduplicated = []
    for alert in alerts:
        is_dup = False
        for existing in deduplicated:
            # Same name and within 0.1 miles
            if (existing["location"] == alert["location"] and
                abs(existing["distance_miles"] - alert["distance_miles"]) < 0.1):
                is_dup = True
                break
            # Same coordinates (within ~100 meters)
            if (abs(existing["latitude"] - alert["latitude"]) < 0.001 and
                abs(existing["longitude"] - alert["longitude"]) < 0.001):
                is_dup = True
                break
        if not is_dup:
            deduplicated.append(alert)

    alerts = deduplicated

    # Filter to only show concerning clearances (< 3ft margin) unless very few results
    if len(alerts) > 10:
        alerts = [a for a in alerts if a["margin_ft"] < 3.0 or a["warning_level"] != "safe"]

    return alerts


async def query_lcm_api(
    route_points: List[Tuple[float, float]],
    vehicle_height_ft: float
) -> List[BridgeHeightResult]:
    """
    Query Low Clearance Map API (placeholder for future integration).

    LCM API would provide:
    - DOT-verified clearance data
    - Real-time updates from user reports
    - More accurate positioning

    To integrate:
    1. Get API key from lowclearancemap.com
    2. Set LCM_API_KEY environment variable
    3. Implement actual API calls below
    """

    if not LCM_API_KEY:
        return []

    # Placeholder - implement when API key is available
    # Example request structure:
    # POST /v1/route/clearances
    # {
    #   "route": [[lat, lon], ...],
    #   "vehicle_height_ft": 13.5
    # }

    return []


# Convenience function for direct testing
async def test_bridge_service():
    """Test the bridge height service with a sample route."""
    # Sample polyline (short route for testing)
    test_polyline = "a~l~Fjk~uOnzh@vlbBtc@fxmA"

    results = await get_bridge_clearances_for_route(test_polyline, vehicle_height_ft=13.5)
    print(f"Found {len(results)} bridge clearances")
    for r in results:
        print(f"  {r['location']}: {r['clearance_ft']}' - {r['warning_level']}")

    return results


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_bridge_service())
