"""NWS gridded wind-gust forecasts, independent of official weather alerts."""
from datetime import datetime, timedelta, timezone
import math
import re
from urllib.parse import urlparse

_DURATION = re.compile(r"P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?")

def aware(value):
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if not isinstance(value, datetime) or value.tzinfo is None:
        return None
    return value.astimezone(timezone.utc)

def interval(value):
    try:
        start, duration = value.split("/", 1)
        start = aware(start)
        match = _DURATION.fullmatch(duration)
        if not start or not match:
            return None
        d, h, m, s = (int(v or 0) for v in match.groups())
        end = start + timedelta(days=d, hours=h, minutes=m, seconds=s)
        return (start, end) if end > start else None
    except (ValueError, AttributeError, OverflowError):
        return None

def speed_mph(value, unit):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or value < 0:
        return None
    factor = {"km_h-1": 0.621371192, "m_s-1": 2.236936292, "mi_h-1": 1, "kt": 1.150779448}.get(str(unit).split(":")[-1])
    return value * factor if factor is not None else None

def layer_value(layer, target):
    target = aware(target)
    if target is None or not isinstance(layer, dict):
        return None
    for entry in layer.get("values") or []:
        bounds = interval(entry.get("validTime"))
        if bounds and bounds[0] <= target < bounds[1]:
            return entry.get("value")
    return None

def wind_at_eta(properties, target):
    gust = properties.get("windGust") or {}
    wind = properties.get("windSpeed") or {}
    peak = speed_mph(layer_value(gust, target), gust.get("uom") or gust.get("unitCode"))
    sustained = speed_mph(layer_value(wind, target), wind.get("uom") or wind.get("unitCode"))
    direction = layer_value(properties.get("windDirection"), target)
    if isinstance(direction, bool) or not isinstance(direction, (float, int)) or not math.isfinite(direction) or not 0 <= direction <= 360:
        direction = None
    return {"gust_mph": peak, "sustained_mph": sustained, "direction_deg": direction}

def gust_severity(gust):
    # Provisional screening levels, not universal vehicle handling limits.
    if gust is None or gust < 30:
        return None
    return "high" if gust >= 40 else "medium"

def forecast_grid_url(url):
    if not isinstance(url, str):
        return None
    p = urlparse(url)
    if p.scheme == "https" and p.netloc == "api.weather.gov" and re.fullmatch(r"/gridpoints/[A-Z]{3}/-?\d+,-?\d+", p.path) and not p.query and not p.fragment:
        return url
    return None

async def fetch_wind_at_eta(client, lat, lon, target, headers):
    """Fetch only from NWS, no fallback to guessed gusts."""
    if aware(target) is None:
        return None
    point = await client.get(f"https://api.weather.gov/points/{lat:.4f},{lon:.4f}", headers=headers)
    point.raise_for_status()
    grid = forecast_grid_url((point.json().get("properties") or {}).get("forecastGridData"))
    if not grid:
        return None
    response = await client.get(grid, headers=headers)
    response.raise_for_status()
    return wind_at_eta(response.json().get("properties") or {}, target)

def sampled_distances(points, route_miles):
    """Approximate route-mile position by scaling cumulative sampled geometry."""
    if not points or not isinstance(route_miles, (int, float)) or not math.isfinite(route_miles) or route_miles <= 0:
        return []
    distances = [0.0]
    for a, b in zip(points, points[1:]):
        lat1, lat2 = math.radians(a["lat"]), math.radians(b["lat"])
        dlat = lat2 - lat1
        dlon = math.radians(b["lon"] - a["lon"])
        v = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
        distances.append(distances[-1] + 3958.76 * 2 * math.asin(math.sqrt(min(1.0, max(0.0, v)))))
    if distances[-1] <= 0:
        return []
    return [route_miles * d / distances[-1] for d in distances]
