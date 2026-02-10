"""
Critical route alert monitoring and worker.

Key responsibilities:
- Persist route monitors with sampled route points.
- Poll NWS for critical alerts near the route.
- Deduplicate and rate-limit push notifications.
"""

import hashlib
import json
import logging
import math
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

import httpx

logger = logging.getLogger(__name__)

DEFAULT_NOAA_UA = os.environ.get(
    "NOAA_USER_AGENT",
    "Routecast/1.0 (contact: lisaaanehildreth@gmail.com)",
)


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compute great-circle distance between two points in miles."""
    radius_km = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = phi2 - phi1
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return (radius_km * c) * 0.621371


def _downsample(points: List[Dict[str, float]], limit: int) -> List[Dict[str, float]]:
    """Evenly downsample a list to the requested limit while keeping endpoints."""
    if len(points) <= limit:
        return points
    if limit <= 2:
        return [points[0], points[-1]]
    keep = [points[0]]
    inner = points[1:-1]
    stride = max(1, math.floor(len(inner) / (limit - 2)))
    keep.extend(inner[::stride][: limit - 2])
    keep.append(points[-1])
    return keep


def sample_route_points(
    route_points: List[Dict[str, float]],
    sample_miles: float = 10.0,
    max_points: int = 25,
) -> List[Dict[str, float]]:
    """Sample route geometry every `sample_miles`, including endpoints.

    Args:
        route_points: Ordered list of dicts with lat/lon keys.
        sample_miles: Target spacing between samples.
        max_points: Hard cap to avoid oversized monitors.
    """
    if not route_points or len(route_points) < 2:
        raise ValueError("At least start and end points are required")

    samples: List[Dict[str, float]] = [route_points[0]]
    carry = 0.0

    for idx in range(len(route_points) - 1):
        start = route_points[idx]
        end = route_points[idx + 1]
        seg_dist = haversine_miles(start["lat"], start["lon"], end["lat"], end["lon"])
        if seg_dist == 0:
            continue

        walked = carry
        while walked + seg_dist >= sample_miles and len(samples) < max_points - 1:
            ratio = (sample_miles - walked) / seg_dist
            lat = start["lat"] + ratio * (end["lat"] - start["lat"])
            lon = start["lon"] + ratio * (end["lon"] - start["lon"])
            samples.append({"lat": lat, "lon": lon})
            seg_dist -= (sample_miles - walked)
            start = {"lat": lat, "lon": lon}
            walked = 0.0

        carry = walked + seg_dist

    if len(samples) < max_points:
        if samples[-1] != route_points[-1]:
            samples.append(route_points[-1])
    else:
        samples[-1] = route_points[-1]

    if len(samples) > max_points:
        samples = _downsample(samples, max_points)

    return samples


class PushGateway:
    """Push gateway supporting Firebase (preferred) and Expo fallback."""

    def __init__(self):
        self._expo_client = None
        self._firebase_app = None
        self._provider = (os.environ.get("PUSH_PROVIDER", "expo") or "expo").lower()
        self._disabled = False
        self._fallback_expo = (os.environ.get("PUSH_FALLBACK", "expo") or "expo").lower() == "expo"

        if self._provider == "firebase":
            self._init_firebase()
            if self._firebase_app is None:
                logger.warning("[route-alerts] push disabled (firebase config missing)")
                self._disabled = True
        elif self._provider == "expo":
            self._init_expo()
            if self._expo_client is None:
                logger.warning("[route-alerts] push disabled (expo client unavailable)")
                self._disabled = True
        else:
            logger.warning("[route-alerts] unknown PUSH_PROVIDER=%s; disabling push", self._provider)
            self._disabled = True

        if self._provider == "firebase" and self._firebase_app is None and self._fallback_expo:
            self._init_expo()
            if self._expo_client:
                logger.info("[route-alerts] Falling back to Expo push")
                self._provider = "expo"
                self._disabled = False

    def _init_firebase(self) -> None:
        try:
            import firebase_admin
            from firebase_admin import credentials, initialize_app

            service_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON")
            service_path = os.environ.get("FIREBASE_SERVICE_ACCOUNT_PATH")

            cred = None
            if service_json:
                cred = credentials.Certificate(json.loads(service_json))
            elif service_path and os.path.exists(service_path):
                cred = credentials.Certificate(service_path)

            if cred is None:
                logger.warning("[route-alerts] FIREBASE service account not configured")
                return

            if not firebase_admin._apps:
                initialize_app(cred)
            self._firebase_app = firebase_admin.get_app()
            logger.info("[route-alerts] Firebase push initialized")
        except Exception as exc:  # noqa: BLE001
            logger.warning("[route-alerts] Firebase init failed: %s", exc)
            self._firebase_app = None

    def _init_expo(self) -> None:
        try:
            from .expo_push import ExpoPushClient

            self._expo_client = ExpoPushClient()
        except Exception as exc:  # noqa: BLE001
            logger.warning("[route-alerts] Expo init failed: %s", exc)
            self._expo_client = None

    def send(
        self,
        token: str,
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        if self._disabled:
            logger.warning("[route-alerts] push disabled; dropping message")
            return False

        if not token:
            return False
        if self._provider == "firebase" and self._firebase_app:
            try:
                from firebase_admin import messaging

                msg = messaging.Message(
                    token=token,
                    data={k: str(v) for k, v in (data or {}).items()},
                    notification=messaging.Notification(title=title, body=body),
                )
                messaging.send(msg, app=self._firebase_app)
                return True
            except Exception as exc:  # noqa: BLE001
                logger.warning("Firebase push failed: %s", exc)

        if self._provider == "expo" and self._expo_client:
            return self._expo_client.send_notification(token, title, body, data)

        logger.warning("[route-alerts] No push gateway available; drop message")
        return False


class RouteAlertService:
    """Persistence and utility helpers for critical alerts."""

    def __init__(
        self,
        db,
        push_gateway: Optional[PushGateway] = None,
        now_fn: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ):
        self.db = db
        self.push_gateway = push_gateway or PushGateway()
        self.now = now_fn
        self._ensure_indexes()

    def _ensure_indexes(self):
        self.db.route_monitors.create_index("user_id")
        self.db.route_monitors.create_index("push_token")
        self.db.route_monitors.create_index("active")
        self.db.route_monitors.create_index("created_at")

        self.db.sent_alerts.create_index(
            [
                ("route_signature", 1),
                ("alert_id", 1),
                ("band", 1),
                ("route_id", 1),
            ],
            unique=True,
        )
        self.db.sent_alerts.create_index("sent_at")

    def start_monitor(
        self,
        user_id: str,
        push_token: str,
        route_points: List[Dict[str, float]],
        route_id: str,
        sample_miles: float = 10.0,
        max_points: int = 25,
    ) -> Dict[str, Any]:
        samples = sample_route_points(route_points, sample_miles=sample_miles, max_points=max_points)
        route_signature = self._route_signature(route_id, samples)

        now = self.now()
        monitor_id = str(uuid.uuid4())

        self.db.route_monitors.update_many(
            {"$or": [{"user_id": user_id}, {"push_token": push_token}], "active": True},
            {"$set": {"active": False, "stopped_at": now}},
        )

        doc = {
            "monitor_id": monitor_id,
            "user_id": user_id,
            "push_token": push_token,
            "route_points": route_points,
            "sample_points": samples,
            "route_id": route_id,
            "route_signature": route_signature,
            "active": True,
            "created_at": now,
        }
        self.db.route_monitors.insert_one(doc)
        return {
            "monitor_id": monitor_id,
            "sample_points": samples,
            "route_signature": route_signature,
        }

    def stop_monitor(self, user_id: Optional[str] = None, monitor_id: Optional[str] = None, push_token: Optional[str] = None) -> int:
        if not any([user_id, monitor_id, push_token]):
            raise ValueError("At least one identifier required")
        query: Dict[str, Any] = {"active": True}
        if user_id:
            query["user_id"] = user_id
        if monitor_id:
            query["monitor_id"] = monitor_id
        if push_token:
            query["push_token"] = push_token
        result = self.db.route_monitors.update_many(query, {"$set": {"active": False, "stopped_at": self.now()}})
        return getattr(result, "modified_count", 0)

    def get_active_monitors(self, limit: int = 200) -> List[Dict[str, Any]]:
        return list(self.db.route_monitors.find({"active": True}).limit(limit))

    def has_sent(self, route_signature: str, route_id: str, alert_id: str, band: str) -> bool:
        return (
            self.db.sent_alerts.find_one(
                {
                    "route_signature": route_signature,
                    "route_id": route_id,
                    "alert_id": alert_id,
                    "band": band,
                }
            )
            is not None
        )

    def count_recent(self, monitor_id: str, minutes: int = 60, exclude_events: Optional[List[str]] = None) -> int:
        cutoff = self.now() - timedelta(minutes=minutes)
        query: Dict[str, Any] = {"monitor_id": monitor_id, "sent_at": {"$gte": cutoff}}
        if exclude_events:
            query["event"] = {"$nin": exclude_events}
        return self.db.sent_alerts.count_documents(query)

    def record_sent(
        self,
        monitor_id: str,
        route_signature: str,
        route_id: str,
        alert_id: str,
        event: str,
        band: str,
        distance_miles: float,
        headline: str,
        expires: Optional[str],
    ) -> None:
        doc = {
            "monitor_id": monitor_id,
            "route_signature": route_signature,
            "route_id": route_id,
            "alert_id": alert_id,
            "event": event,
            "band": band,
            "distance_miles": distance_miles,
            "headline": headline,
            "expires": expires,
            "sent_at": self.now(),
        }
        self.db.sent_alerts.insert_one(doc)

    def _route_signature(self, route_id: str, sample_points: List[Dict[str, float]]) -> str:
        payload = {"route_id": route_id, "points": sample_points}
        raw = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(raw.encode()).hexdigest()


class CriticalRouteAlertWorker:
    """Polls NWS for critical alerts near active monitors."""

    CRITICAL_EVENTS = {
        "Tornado Warning",
        "Tornado Emergency",
        "Extreme Wind Warning",
        "Severe Thunderstorm Warning",
    }

    def __init__(
        self,
        service: RouteAlertService,
        fetcher: Optional[Callable[[float, float], Iterable[Dict[str, Any]]]] = None,
        now_fn: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ):
        self.service = service
        self.fetcher = fetcher or self._fetch_alerts
        self.now = now_fn
        self.cap_per_hour = int(os.environ.get("ROUTE_ALERTS_CAP_PER_HOUR", "2"))

    def run_once(self) -> Dict[str, Any]:
        monitors = self.service.get_active_monitors()
        summary = {
            "monitors": len(monitors),
            "sent": 0,
            "skipped": 0,
            "nws_calls": 0,
            "alerts_seen": 0,
            "skipped_type": 0,
            "skipped_distance": 0,
            "skipped_dedupe": 0,
            "skipped_cap": 0,
            "skipped_push": 0,
        }

        for monitor in monitors:
            result = self._process_monitor(monitor)
            for key in summary:
                if key in result:
                    summary[key] += result[key]

        logger.info(
            "[route-alerts] run complete monitors=%d nws_calls=%d alerts=%d sent=%d"
            " skipped=%d type=%d distance=%d dedupe=%d cap=%d push=%d",
            summary["monitors"],
            summary["nws_calls"],
            summary["alerts_seen"],
            summary["sent"],
            summary["skipped"],
            summary["skipped_type"],
            summary["skipped_distance"],
            summary["skipped_dedupe"],
            summary["skipped_cap"],
            summary["skipped_push"],
        )
        return summary

    def _process_monitor(self, monitor: Dict[str, Any]) -> Dict[str, int]:
        stats = {
            "sent": 0,
            "skipped": 0,
            "nws_calls": 0,
            "alerts_seen": 0,
            "skipped_type": 0,
            "skipped_distance": 0,
            "skipped_dedupe": 0,
            "skipped_cap": 0,
            "skipped_push": 0,
        }

        monitor_id = monitor.get("monitor_id")
        token = monitor.get("push_token")
        route_id = monitor.get("route_id") or "unknown"
        route_signature = monitor.get("route_signature")
        sample_points = monitor.get("sample_points") or []

        if route_signature is None:
            # Backfill signature for legacy monitors
            route_signature = self.service._route_signature(route_id, sample_points)

        for point in sample_points:
            alerts = list(self.fetcher(point["lat"], point["lon"]))
            stats["nws_calls"] += 1
            for alert in alerts:
                stats["alerts_seen"] += 1
                if not self._is_critical(alert):
                    stats["skipped"] += 1
                    stats["skipped_type"] += 1
                    continue

                event = alert.get("properties", {}).get("event", "Unknown")
                alert_id = alert.get("id") or alert.get("properties", {}).get("id") or str(uuid.uuid4())

                distance = self._distance_to_alert(point, alert)
                band = self._band_for_distance(distance)
                if band is None:
                    stats["skipped"] += 1
                    stats["skipped_distance"] += 1
                    continue

                # If we already sent within-5, suppress later within-15 for same alert
                if band == "within_15" and self.service.has_sent(route_signature, route_id, alert_id, "within_5"):
                    stats["skipped"] += 1
                    stats["skipped_dedupe"] += 1
                    continue

                if self.service.has_sent(route_signature, route_id, alert_id, band):
                    stats["skipped"] += 1
                    stats["skipped_dedupe"] += 1
                    continue

                if event != "Tornado Warning":
                    if self.service.count_recent(
                        monitor_id, minutes=60, exclude_events=["Tornado Warning"]
                    ) >= self.cap_per_hour:
                        stats["skipped"] += 1
                        stats["skipped_cap"] += 1
                        continue

                title = f"{event} {band.replace('_', '-')}"
                headline = alert.get("properties", {}).get("headline") or event
                expires = alert.get("properties", {}).get("expires")

                if self.service.push_gateway.send(
                    token,
                    title=title,
                    body=headline,
                    data={
                        "type": "critical_route_alert",
                        "event": event,
                        "distanceMiles": f"{distance:.1f}",
                        "band": band,
                        "alertId": alert_id,
                        "routeId": route_id,
                    },
                ):
                    self.service.record_sent(
                        monitor_id,
                        route_signature,
                        route_id,
                        alert_id,
                        event,
                        band,
                        distance,
                        headline,
                        expires,
                    )
                    stats["sent"] += 1
                else:
                    stats["skipped"] += 1
                    stats["skipped_push"] += 1

        return stats

    def _is_critical(self, alert: Dict[str, Any]) -> bool:
        props = alert.get("properties", {})
        event = props.get("event", "")
        severity = (props.get("severity") or "").lower()
        if event not in self.CRITICAL_EVENTS:
            return False
        if event == "Severe Thunderstorm Warning" and severity not in {"severe", "extreme"}:
            return False
        if severity in {"minor", "unknown"}:
            return False
        return True

    def _band_for_distance(self, distance_miles: float) -> Optional[str]:
        if distance_miles <= 5.0:
            return "within_5"
        if distance_miles <= 15.0:
            return "within_15"
        return None

    def _distance_to_alert(self, point: Dict[str, float], alert: Dict[str, Any]) -> float:
        geometry = alert.get("geometry")
        if not geometry:
            return 0.0
        coords = geometry.get("coordinates") or []
        min_dist = float("inf")
        for ring in self._iter_geojson_coordinates(coords):
            for lon, lat in ring:
                d = haversine_miles(point["lat"], point["lon"], lat, lon)
                if d < min_dist:
                    min_dist = d
        if min_dist == float("inf"):
            return 0.0
        return min_dist

    def _iter_geojson_coordinates(self, coordinates: Any) -> Iterable[List[Tuple[float, float]]]:
        """Yield linear rings from GeoJSON polygon or multipolygon coordinates."""
        if not coordinates:
            return []

        first = coordinates[0]
        if isinstance(first, (list, tuple)) and first:
            # Handle Polygon with coordinates shaped as [ [ [lon, lat], ... ] ]
            if isinstance(first[0], (float, int)):
                return [coordinates]
            if isinstance(first[0], (list, tuple)):
                if first[0] and isinstance(first[0][0], (float, int)):
                    return coordinates  # Already list of rings
                # MultiPolygon: flatten rings
                rings: List[Tuple[float, float]] = []
                for poly in coordinates:
                    rings.extend(poly)
                return rings
        return []

    def _fetch_alerts(self, lat: float, lon: float) -> Iterable[Dict[str, Any]]:
        url = f"https://api.weather.gov/alerts/active?point={lat},{lon}"
        headers = {
            "User-Agent": DEFAULT_NOAA_UA,
            "Accept": "application/geo+json",
        }
        try:
            with httpx.Client(timeout=15.0) as client:
                resp = client.get(url, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                return data.get("features", [])
        except Exception as exc:  # noqa: BLE001
            logger.warning("NWS fetch failed for point %.3f,%.3f: %s", lat, lon, exc)
            return []
