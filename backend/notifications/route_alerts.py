"""
Critical route alert monitoring and worker.

Key responsibilities:
- Persist route monitors with sampled route points.
- Poll NWS for critical alerts near the route.
- Deduplicate and rate-limit push notifications.
"""

import asyncio
import concurrent.futures
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


def utc_now() -> datetime:
    """Return current UTC time as an aware datetime."""
    return datetime.now(timezone.utc)


def to_aware_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Normalize datetime to timezone-aware UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


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


def _decode_polyline_safe(poly: Optional[str]) -> List[Dict[str, float]]:
    if not poly or not isinstance(poly, str):
        return []
    try:
        import polyline  # type: ignore

        coords = polyline.decode(poly, 6)
        return [{"lat": lat, "lon": lon} for lat, lon in coords]
    except Exception as exc:  # noqa: BLE001
        logger.warning("[route-alerts] failed to decode polyline: %s", exc)
        return []


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


def _span_miles(points: List[Dict[str, float]]) -> float:
    """Approximate route span using the first and last point."""
    if len(points) < 2:
        return 0.0
    start = points[0]
    end = points[-1]
    if not all(k in start and k in end for k in ("lat", "lon")):
        return 0.0
    try:
        return haversine_miles(start["lat"], start["lon"], end["lat"], end["lon"])
    except Exception:  # noqa: BLE001
        return 0.0


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
        expanded_body: Optional[str] = None,
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

                merged_data = {**{k: str(v) for k, v in (data or {}).items()}, "expandedBody": str(expanded_body or body)}
                msg = messaging.Message(
                    token=token,
                    data=merged_data,
                    notification=messaging.Notification(title=title, body=body),
                )
                messaging.send(msg, app=self._firebase_app)
                return True
            except Exception as exc:  # noqa: BLE001
                logger.warning("Firebase push failed: %s", exc)

        if self._provider == "expo" and self._expo_client:
            payload = data.copy() if data else {}
            if expanded_body:
                payload["expandedBody"] = expanded_body
            return self._expo_client.send_notification(token, title, body, payload)

        logger.warning("[route-alerts] No push gateway available; drop message")
        return False


class RouteAlertService:
    """Persistence and utility helpers for critical alerts."""

    def __init__(
        self,
        db,
        push_gateway: Optional[PushGateway] = None,
        now_fn: Callable[[], datetime] = utc_now,
    ):
        self.db = db
        self.push_gateway = push_gateway or PushGateway()
        self.now = now_fn
        self.monitor_ttl_hours = float(os.environ.get("ROUTE_ALERTS_MONITOR_TTL_HOURS", "24"))
        self.alert_key_ttl_minutes = int(os.environ.get("ROUTE_ALERT_KEY_TTL_MIN", "120"))
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

        if hasattr(self.db, "sent_alert_keys"):
            ttl_seconds = int(self.alert_key_ttl_minutes * 60)
            self.db.sent_alert_keys.create_index([("monitor_id", 1), ("alert_key", 1)])
            self.db.sent_alert_keys.create_index("expires_at", expireAfterSeconds=ttl_seconds)

        if hasattr(self.db, "push_tokens"):
            self.db.push_tokens.create_index("push_token")
            self.db.push_tokens.create_index("user_id")
            self.db.push_tokens.create_index("current_route_id")

    def _persist_current_route(self, user_id: Optional[str], push_token: Optional[str], route_id: str, now: datetime) -> None:
        if not push_token or not hasattr(self.db, "push_tokens"):
            return
        try:
            self.db.push_tokens.update_one(
                {"push_token": push_token},
                {
                    "$set": {
                        "push_token": push_token,
                        "user_id": user_id or push_token,
                        "current_route_id": route_id,
                        "updated_at": now,
                    }
                },
                upsert=True,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("[route-alerts] failed to persist current_route_id for token=%s: %s", push_token[:12], exc)

    def get_current_route_id(self, user_id: Optional[str], push_token: Optional[str]) -> Optional[str]:
        if not hasattr(self.db, "push_tokens"):
            return None

        candidates = []
        if push_token:
            candidates.append({"push_token": push_token})
        if user_id:
            candidates.append({"user_id": user_id})

        for query in candidates:
            try:
                doc = self.db.push_tokens.find_one(query)
                if doc and doc.get("current_route_id"):
                    return doc.get("current_route_id")
            except Exception as exc:  # noqa: BLE001
                logger.warning("[route-alerts] failed to read current_route_id: %s", exc)
                return None
        return None

    def mark_alert_key(self, monitor_id: str, alert_key: str, route_id: str) -> None:
        if not alert_key or not hasattr(self.db, "sent_alert_keys"):
            return
        now = self.now()
        expires_at = now + timedelta(minutes=self.alert_key_ttl_minutes)
        try:
            self.db.sent_alert_keys.update_one(
                {"monitor_id": monitor_id, "alert_key": alert_key},
                {
                    "$set": {
                        "monitor_id": monitor_id,
                        "alert_key": alert_key,
                        "route_id": route_id,
                        "last_sent_at": now,
                        "expires_at": expires_at,
                    }
                },
                upsert=True,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("[route-alerts] failed to upsert alert_key %s for %s: %s", alert_key, monitor_id, exc)

    def alert_key_recent(self, monitor_id: str, alert_key: str, cooldown_minutes: int) -> bool:
        if not alert_key or not hasattr(self.db, "sent_alert_keys"):
            return False
        try:
            doc = self.db.sent_alert_keys.find_one({"monitor_id": monitor_id, "alert_key": alert_key})
            return bool(doc)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[route-alerts] failed to read alert_key for %s: %s", monitor_id, exc)
            return False

    def within_cooldown(self, monitor_id: str, event: str, cooldown_minutes: int) -> bool:
        if not event:
            return False
        cutoff = self.now() - timedelta(minutes=cooldown_minutes)
        try:
            doc = self.db.sent_alerts.find_one(
                {"monitor_id": monitor_id, "event": event, "sent_at": {"$gte": cutoff}}
            )
            return bool(doc)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[route-alerts] failed cooldown lookup for %s: %s", monitor_id, exc)
            return False

    def start_monitor(
        self,
        user_id: str,
        push_token: str,
        route_points: List[Dict[str, float]],
        route_id: str,
        sample_points: Optional[List[Dict[str, float]]] = None,
        route_polyline: Optional[str] = None,
        bbox: Optional[Dict[str, float]] = None,
        sample_miles: float = 10.0,
        max_points: int = 25,
    ) -> Dict[str, Any]:
        if sample_points:
            samples = sample_points
        else:
            samples = sample_route_points(route_points, sample_miles=sample_miles, max_points=max_points)

        if not samples:
            raise ValueError("route geometry required")

        route_signature = self._route_signature(route_id, samples)

        now = self.now()
        monitor_id = str(uuid.uuid4())
        expires_at = now + timedelta(hours=self.monitor_ttl_hours)

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
            "route_polyline": route_polyline,
            "bbox": bbox or _compute_bbox(samples) or _compute_bbox(route_points),
            "expo_push_token": push_token,
            "route_id": route_id,
            "current_route_id": route_id,
            "route_signature": route_signature,
            "active": True,
            "created_at": now,
            "expires_at": expires_at,
        }
        self.db.route_monitors.insert_one(doc)
        self._persist_current_route(user_id=user_id, push_token=push_token, route_id=route_id, now=now)
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
        query: Dict[str, Any] = {"active": True}
        now = self.now()
        query["$or"] = [
            {"expires_at": {"$gt": now}},
            {"expires_at": {"$exists": False}},
        ]
        return list(self.db.route_monitors.find(query).limit(limit))

    def has_sent(self, route_signature: str, route_id: str, alert_id: str, band: str, monitor_id: Optional[str] = None) -> bool:
        query: Dict[str, Any] = {"alert_id": alert_id, "band": band}
        if route_signature:
            query["route_signature"] = route_signature
        if route_id:
            query["route_id"] = route_id
        if monitor_id:
            query["monitor_id"] = monitor_id
        found = self.db.sent_alerts.find_one(query)
        if found:
            return True
        if monitor_id:
            legacy_query = {"alert_id": alert_id, "band": band, "monitor_id": monitor_id}
            legacy_found = self.db.sent_alerts.find_one(legacy_query)
            if legacy_found:
                return True
        return False

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
        alert_key: Optional[str] = None,
    ) -> None:
        doc = {
            "monitor_id": monitor_id,
            "route_signature": route_signature,
            "route_id": route_id,
            "alert_id": alert_id,
            "alert_key": alert_key,
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
        self.resend_ttl_minutes = int(os.environ.get("ROUTE_ALERTS_RESEND_TTL_MIN", "15"))
        self.cooldown_minutes = int(os.environ.get("ROUTE_ALERTS_COOLDOWN_MIN", "60"))
        self._current_run_id: Optional[str] = None
        self._recent_alert_cache: Dict[str, Dict[str, Any]] = {}

    def _recent_cache_key(
        self, monitor_id: str, route_signature: str, route_id: str, alert_id: str, band: str
    ) -> str:
        return f"{monitor_id}:{route_signature}:{route_id}:{alert_id}:{band}"

    def _alert_key(self, alert: Dict[str, Any]) -> str:
        props = alert.get("properties", {})
        candidate = props.get("id") or alert.get("id")
        if candidate:
            return str(candidate)

        payload = {
            "event": props.get("event"),
            "onset": props.get("onset"),
            "expires": props.get("expires"),
            "area": props.get("areaDesc"),
        }
        raw = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(raw.encode()).hexdigest()

    def _skip_for_recent(self, monitor_id: str, route_signature: str, route_id: str, alert_id: str, band: str) -> bool:
        now = self.now()
        expired = [key for key, entry in self._recent_alert_cache.items() if entry.get("expires_at") and entry["expires_at"] <= now]
        for key in expired:
            self._recent_alert_cache.pop(key, None)

        key = self._recent_cache_key(monitor_id, route_signature, route_id, alert_id, band)
        entry = self._recent_alert_cache.get(key)
        return bool(entry and entry.get("expires_at") and entry["expires_at"] > now)

    def run_once(self) -> Dict[str, Any]:
        run_id = uuid.uuid4().hex[:8]
        self._current_run_id = run_id
        monitors = self.service.get_active_monitors()
        logger.info(
            "[route-alerts] fetched active monitors count=%d filter=active=True",
            len(monitors),
        )
        monitors_considered_ids = [m.get("monitor_id") for m in monitors if m.get("monitor_id")]
        monitors_after_route_filter: List[str] = []
        summary = {
            "monitors": len(monitors),
            "sent": 0,
            "skipped": 0,
            "nws_calls": 0,
            "alerts_seen": 0,
            "alerts_found": 0,
            "skipped_type": 0,
            "skipped_distance": 0,
            "skipped_dedupe": 0,
            "skipped_cap": 0,
            "skipped_push": 0,
            "skipped_points": 0,
            "skipped_geometry": 0,
            "skipped_current_route": 0,
            "alerts_suppressed_already_sent": 0,
            "alerts_suppressed_cooldown": 0,
            "monitors_with_geometry": 0,
            "monitors_without_geometry": 0,
        }

        prepared: List[Dict[str, Any]] = []
        for monitor in monitors:
            prepared_monitor, prep_stats = self._prepare_monitor(monitor)
            for key in summary:
                if key in prep_stats:
                    summary[key] += prep_stats[key]
            if prepared_monitor:
                prepared.append(prepared_monitor)

        unique_points: Dict[str, Tuple[float, float]] = {}
        for item in prepared:
            for point in item["sample_points"]:
                lat = point.get("lat")
                lon = point.get("lon")
                if lat is None or lon is None:
                    continue
                key = self._point_cache_key(lat, lon)
                if key not in unique_points:
                    unique_points[key] = (lat, lon)

        alerts_cache = self._fetch_alerts_concurrent(unique_points)
        summary["nws_calls"] += len(unique_points)

        for item in prepared:
            result = self._process_monitor_with_cache(item, alerts_cache, run_id=run_id)
            if result.get("route_filter_passed"):
                monitors_after_route_filter.append(item.get("monitor_id"))
            for key in summary:
                if key in result:
                    summary[key] += result[key]

        summary["monitors_without_geometry"] = summary["monitors"] - summary["monitors_with_geometry"]

        logger.info(
            "[route-alerts] run complete monitors=%d with_geometry=%d nws_calls=%d alerts=%d sent=%d"
            " skipped=%d type=%d distance=%d dedupe=%d cap=%d push=%d points=%d geometry=%d no_geom=%d",
            summary["monitors"],
            summary["monitors_with_geometry"],
            summary["nws_calls"],
            summary["alerts_seen"],
            summary["sent"],
            summary["skipped"],
            summary["skipped_type"],
            summary["skipped_distance"],
            summary["skipped_dedupe"],
            summary["skipped_cap"],
            summary["skipped_push"],
            summary["skipped_points"],
            summary["skipped_geometry"],
            summary["monitors_without_geometry"],
        )

        logger.info(
            "[route-alerts] instrumentation",
            extra={
                "run_id": run_id,
                "monitors_considered": monitors_considered_ids,
                "monitors_after_current_route_filter": monitors_after_route_filter,
                "alerts_found": summary["alerts_found"],
                "alerts_sent": summary["sent"],
                "alerts_suppressed_already_sent": summary["alerts_suppressed_already_sent"],
                "alerts_suppressed_cooldown": summary["alerts_suppressed_cooldown"],
            },
        )
        return summary

    def _process_monitor(self, monitor: Dict[str, Any]) -> Dict[str, int]:
        prepared, stats = self._prepare_monitor(monitor)
        if not prepared:
            return stats

        # Fallback: sequential fetch if caller bypasses run_once concurrency
        cache: Dict[str, List[Dict[str, Any]]] = {}
        for point in prepared["sample_points"]:
            key = self._point_cache_key(point["lat"], point["lon"])
            cache[key] = list(self.fetcher(point["lat"], point["lon"]))
        stats["nws_calls"] += len(cache)

        result = self._process_monitor_with_cache(prepared, cache)
        for k, v in result.items():
            stats[k] = stats.get(k, 0) + v
        return stats

    def _prepare_monitor(self, monitor: Dict[str, Any]) -> tuple[Optional[Dict[str, Any]], Dict[str, int]]:
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
            "skipped_points": 0,
            "skipped_geometry": 0,
            "monitors_with_geometry": 0,
        }

        monitor_id = monitor.get("monitor_id")
        token = monitor.get("push_token")
        route_id = monitor.get("route_id") or "unknown"
        route_signature = monitor.get("route_signature")
        sample_points = monitor.get("sample_points") or []
        route_points = monitor.get("route_points") or []
        polyline_val = monitor.get("route_polyline") or monitor.get("route_geometry")
        legs_val = monitor.get("legs") or monitor.get("route_legs")
        explicit_points = monitor.get("points") or monitor.get("coords")

        sample_points_count = len(sample_points)
        first_three = sample_points[:3]
        last_three = sample_points[-3:] if sample_points_count >= 3 else sample_points
        sample_span_miles = _span_miles(sample_points)
        route_span_miles = _span_miles(route_points)
        coverage_ratio = None
        if route_span_miles > 0:
            coverage_ratio = sample_span_miles / route_span_miles if route_span_miles else None
        span_flagged = (
            coverage_ratio is not None
            and route_span_miles >= 5.0
            and coverage_ratio < 0.5
        )
        expires_at_raw = monitor.get("expires_at") or monitor.get("expires") or monitor.get("expiresAt")
        if isinstance(expires_at_raw, str):
            try:
                expires_at_raw = datetime.fromisoformat(expires_at_raw)
            except Exception:
                expires_at_raw = None

        expires_at = expires_at_raw if isinstance(expires_at_raw, datetime) else None
        expires_at_norm = to_aware_utc(expires_at)
        now_utc = to_aware_utc(self.now())

        logger.debug(
            "[route-alerts] expires_at normalized monitor=%s raw=%s raw_tzinfo=%s normalized=%s",
            monitor_id,
            expires_at_raw,
            getattr(expires_at_raw, "tzinfo", None),
            expires_at_norm.isoformat() if expires_at_norm else None,
        )

        if expires_at_norm and now_utc and expires_at_norm <= now_utc:
            stats["skipped"] += 1
            stats["skipped_geometry"] += 1
            return None, stats
        has_polyline = bool(route_points or polyline_val)
        token_prefix = (token or "")[:18]
        push_token_alt = monitor.get("expo_push_token") or monitor.get("pushToken") or monitor.get("fcm_token")
        token_alt_prefix = (push_token_alt or "")[:18]

        bbox = _compute_bbox(sample_points) or _compute_bbox(route_points) or _compute_bbox(explicit_points or [])

        logger.info(
            "[route-alerts] monitor inspect id=%s expires=%s active=%s has_polyline=%s sample_points=%d first3=%s last3=%s span_mi=%.2f route_span_mi=%.2f coverage=%s bbox=%s push_token_prefix=%s alt_token_prefix=%s legs=%s explicit_points=%s",
            monitor_id,
            expires_at,
            monitor.get("active"),
            has_polyline,
            sample_points_count,
            first_three,
            last_three,
            sample_span_miles,
            route_span_miles,
            f"{coverage_ratio:.2f}" if coverage_ratio is not None else "n/a",
            bbox,
            token_prefix,
            token_alt_prefix,
            bool(legs_val),
            bool(explicit_points),
        )

        if span_flagged:
            logger.warning(
                "WARNING [route-alerts] sample points clustered near start id=%s coverage=%.2f sample_span_mi=%.2f route_span_mi=%.2f first3=%s last3=%s",
                monitor_id,
                coverage_ratio,
                sample_span_miles,
                route_span_miles,
                first_three,
                last_three,
            )

        resample_needed = sample_points_count < 3

        if resample_needed and route_points:
            sample_miles = float(os.environ.get("ROUTE_ALERTS_SAMPLING_MILES", 10.0))
            max_points = int(os.environ.get("ROUTE_ALERTS_MAX_POINTS", 25))
            try:
                sample_points = sample_route_points(route_points, sample_miles=sample_miles, max_points=max_points)
                sample_points_count = len(sample_points)
                logger.info(
                    "[route-alerts] resampled monitor id=%s route_points=%d sample_points=%d",
                    monitor_id,
                    len(route_points),
                    sample_points_count,
                )
                try:
                    self.service.db.route_monitors.update_one(
                        {"monitor_id": monitor_id},
                        {"$set": {"sample_points": sample_points}},
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("[route-alerts] failed to persist resampled points for %s: %s", monitor_id, exc)
            except Exception as exc:  # noqa: BLE001
                logger.warning("[route-alerts] failed to resample points for %s: %s", monitor_id, exc)

        if sample_points_count == 0 and not route_points and polyline_val:
            decoded_points = _decode_polyline_safe(polyline_val)
            if decoded_points:
                sample_miles = float(os.environ.get("ROUTE_ALERTS_SAMPLING_MILES", 10.0))
                max_points = int(os.environ.get("ROUTE_ALERTS_MAX_POINTS", 25))
                try:
                    sample_points = sample_route_points(decoded_points, sample_miles=sample_miles, max_points=max_points)
                    sample_points_count = len(sample_points)
                    logger.info(
                        "[route-alerts] resampled from polyline id=%s decoded_points=%d sample_points=%d",
                        monitor_id,
                        len(decoded_points),
                        sample_points_count,
                    )
                    try:
                        self.service.db.route_monitors.update_one(
                            {"monitor_id": monitor_id},
                            {"$set": {"sample_points": sample_points, "route_points": decoded_points}},
                        )
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("[route-alerts] failed to persist decoded points for %s: %s", monitor_id, exc)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("[route-alerts] failed to sample decoded polyline for %s: %s", monitor_id, exc)

        if sample_points_count == 0:
            logger.warning(
                "WARNING [route-alerts] active monitor missing sample points; cannot query NWS id=%s route=%s",
                monitor_id,
                route_id,
            )
            stats["skipped"] += 1
            stats["skipped_points"] += 1
            stats["skipped_geometry"] += 1
            return None, stats

        stats["monitors_with_geometry"] += 1

        if route_signature is None:
            route_signature = self.service._route_signature(route_id, sample_points)

        prepared = {
            "monitor": monitor,
            "monitor_id": monitor_id,
            "token": token,
            "route_id": route_id,
            "route_signature": route_signature,
            "sample_points": sample_points,
        }
        return prepared, stats

    def _has_sent(self, route_signature: str, route_id: str, alert_id: str, band: str, monitor_id: Optional[str] = None) -> bool:
        try:
            return self.service.has_sent(route_signature, route_id, alert_id, band, monitor_id=monitor_id)
        except TypeError:
            return self.service.has_sent(route_signature, route_id, alert_id, band)

    def _send_notification(self, token: str, payload: Dict[str, Any]) -> bool:
        try:
            alert_id = payload.get("data", {}).get("alertId")
            collapse_id = f"routecast_alert_{alert_id}" if alert_id else None
            return self.service.push_gateway.send(
                token,
                title=payload["title"],
                body=payload["collapsed_body"],
                expanded_body=payload.get("expanded_body"),
                data=payload.get("data"),
                channel_id="route-alerts",
                collapse_id=collapse_id,
                sticky=True,
            )
        except TypeError:
            try:
                return self.service.push_gateway.send(
                    token,
                    payload["title"],
                    payload["collapsed_body"],
                    expanded_body=payload.get("expanded_body"),
                    data=payload.get("data"),
                )
            except TypeError:
                return self.service.push_gateway.send(token, payload["title"], payload["collapsed_body"])

    def _process_monitor_with_cache(
        self,
        prepared: Dict[str, Any],
        alerts_cache: Dict[str, List[Dict[str, Any]]],
        run_id: Optional[str] = None,
    ) -> Dict[str, int]:
        stats = {
            "sent": 0,
            "skipped": 0,
            "nws_calls": 0,
            "alerts_seen": 0,
            "alerts_found": 0,
            "skipped_type": 0,
            "skipped_distance": 0,
            "skipped_dedupe": 0,
            "skipped_cap": 0,
            "skipped_push": 0,
            "skipped_current_route": 0,
            "alerts_suppressed_already_sent": 0,
            "alerts_suppressed_cooldown": 0,
            "route_filter_passed": 0,
        }

        monitor_id = prepared["monitor_id"]
        token = prepared["token"]
        route_id = prepared["route_id"]
        route_signature = prepared["route_signature"]
        sample_points = prepared["sample_points"]
        monitor_doc = prepared.get("monitor") or {}
        user_id = monitor_doc.get("user_id") or token
        token_suffix = (token or "")[-6:]
        current_route_id = self.service.get_current_route_id(user_id=user_id, push_token=token) or monitor_doc.get("current_route_id")
        if not current_route_id and route_id:
            current_route_id = route_id  # fallback when no state is persisted

        run_label = run_id or self._current_run_id
        if not current_route_id or not route_id or route_id != current_route_id:
            stats["skipped"] += 1
            stats["skipped_current_route"] += 1
            logger.info(
                "[route-alerts] route gate suppressed",
                extra={
                    "run_id": run_label,
                    "monitor_id": monitor_id,
                    "user_id": user_id,
                    "push_token_suffix": token_suffix,
                    "route_id": route_id,
                    "current_route_id": current_route_id,
                },
            )
            return stats

        stats["route_filter_passed"] = 1
        logger.info(
            "[route-alerts] route gate passed",
            extra={
                "run_id": run_label,
                "monitor_id": monitor_id,
                "user_id": user_id,
                "push_token_suffix": token_suffix,
                "route_id": route_id,
                "current_route_id": current_route_id,
            },
        )

        per_point_alerts: List[Dict[str, Any]] = []
        union_alerts: Dict[str, Dict[str, Optional[str]]] = {}

        for idx, point in enumerate(sample_points):
            key = self._point_cache_key(point["lat"], point["lon"])
            alerts = alerts_cache.get(key, [])
            if alerts is None:
                per_point_alerts.append(
                    {
                        "index": idx,
                        "lat": round(point.get("lat", 0.0), 4),
                        "lon": round(point.get("lon", 0.0), 4),
                        "alert_ids": [],
                        "status": "fetch_failed",
                    }
                )
                continue
            stats["alerts_seen"] += len(alerts)
            point_union_ids: List[str] = []
            for alert in alerts:
                props = alert.get("properties", {})
                union_id = str(alert.get("id") or props.get("id") or self._alert_key(alert))
                union_alerts.setdefault(
                    union_id,
                    {
                        "event": props.get("event"),
                        "headline": props.get("headline") or props.get("event"),
                    },
                )
                point_union_ids.append(union_id)
                stats["alerts_found"] += 1
                if not self._is_critical(alert):
                    stats["skipped"] += 1
                    stats["skipped_type"] += 1
                    continue

                event = props.get("event", "Unknown")
                alert_id = union_id
                alert_key = self._alert_key(alert)

                distance = self._distance_to_alert(point, alert)
                band = self._band_for_distance(distance)
                if band is None:
                    stats["skipped"] += 1
                    stats["skipped_distance"] += 1
                    continue

                if self.service.alert_key_recent(monitor_id, alert_key, self.cooldown_minutes):
                    stats["skipped"] += 1
                    stats["skipped_dedupe"] += 1
                    stats["alerts_suppressed_already_sent"] += 1
                    continue

                if self._skip_for_recent(monitor_id, route_signature, route_id, alert_id, band):
                    stats["skipped"] += 1
                    stats["skipped_dedupe"] += 1
                    stats["alerts_suppressed_already_sent"] += 1
                    continue

                if band == "within_15" and self._has_sent(route_signature, route_id, alert_id, "within_5", monitor_id=monitor_id):
                    stats["skipped"] += 1
                    stats["skipped_dedupe"] += 1
                    stats["alerts_suppressed_already_sent"] += 1
                    continue

                if self._has_sent(route_signature, route_id, alert_id, band, monitor_id=monitor_id):
                    stats["skipped"] += 1
                    stats["skipped_dedupe"] += 1
                    stats["alerts_suppressed_already_sent"] += 1
                    continue

                if self.service.within_cooldown(monitor_id, event, self.cooldown_minutes):
                    stats["skipped"] += 1
                    stats["alerts_suppressed_cooldown"] += 1
                    continue

                if event != "Tornado Warning":
                    if self.service.count_recent(
                        monitor_id, minutes=60, exclude_events=["Tornado Warning"]
                    ) >= self.cap_per_hour:
                        stats["skipped"] += 1
                        stats["skipped_cap"] += 1
                        continue

                payload = self._build_notification_payload(
                    alert=alert,
                    alert_id=alert_id,
                    distance=distance,
                    band=band,
                    route_id=route_id,
                    sample_points=sample_points,
                )

                if self._send_notification(token, payload):
                    cache_key = self._recent_cache_key(monitor_id, route_signature, route_id, alert_id, band)
                    self._recent_alert_cache[cache_key] = {
                        "expires_at": self.now() + timedelta(minutes=self.resend_ttl_minutes),
                    }
                    self.service.mark_alert_key(monitor_id, alert_key, route_id)
                    self.service.record_sent(
                        monitor_id,
                        route_signature,
                        route_id,
                        alert_id,
                        event,
                        band,
                        distance,
                        payload["headline"],
                        payload["expires"],
                        alert_key=alert_key,
                    )
                    stats["sent"] += 1
                else:
                    stats["skipped"] += 1
                    stats["skipped_push"] += 1

            per_point_alerts.append(
                {
                    "index": idx,
                    "lat": round(point.get("lat", 0.0), 4),
                    "lon": round(point.get("lon", 0.0), 4),
                    "alert_ids": sorted(set(point_union_ids)),
                }
            )

        sorted_union_ids = sorted(union_alerts.keys())
        logger.info(
            "[route-alerts] union report",
            extra={
                "run_id": run_label,
                "monitor_id": monitor_id,
                "route_id": route_id,
                "points": len(sample_points),
                "union_alert_ids": sorted_union_ids,
                "union_alerts": [
                    {
                        "id": alert_id,
                        "event": union_alerts[alert_id].get("event"),
                        "headline": union_alerts[alert_id].get("headline"),
                    }
                    for alert_id in sorted_union_ids
                ],
                "per_point_alerts": per_point_alerts,
            },
        )

        return stats

    def _human_summary(self, event: str, onset: Optional[str], expires: Optional[str], where: str) -> str:
        window = self._format_time_window(onset, expires)
        parts = [event]
        if window:
            parts.append(window)
        if where:
            parts.append(where)
        return " • ".join([p for p in parts if p])

    def _build_notification_payload(
        self,
        *,
        alert: Dict[str, Any],
        alert_id: str,
        distance: float,
        band: str,
        route_id: str,
        sample_points: List[Dict[str, float]],
    ) -> Dict[str, Any]:
        props = alert.get("properties", {})
        event = props.get("event") or "Weather Alert"
        severity = (props.get("severity") or "").lower()
        severity_icon = {"extreme": "🔴", "severe": "🟠", "moderate": "🟡"}.get(severity, "🟢")
        title = f"{severity_icon} {event.upper()}"

        headline = props.get("headline") or event
        description = props.get("description") or ""
        area_desc = props.get("areaDesc") or ""
        onset = props.get("onset")
        expires = props.get("expires")

        sections = self._parse_nws_sections(description)
        what = props.get("headline") or sections.get("what") or event
        impacts = sections.get("impacts") or ""
        when_detail = sections.get("when") or self._format_time_window(onset, expires)
        where_detail = self._format_where(area_desc, alert.get("geometry"), sample_points, band)

        summary = self._human_summary(event, onset, expires, where_detail)

        time_range = self._format_time_range(onset, expires)
        collapsed_parts = [p for p in [time_range, where_detail] if p]
        collapsed_body = summary or (" · ".join(collapsed_parts) if collapsed_parts else headline)

        expanded_lines = []
        if what:
            expanded_lines.append(f"WHAT: {what}")
        if where_detail:
            expanded_lines.append(f"WHERE: {where_detail}")
        if when_detail:
            expanded_lines.append(f"WHEN: {when_detail}")
        if impacts:
            expanded_lines.append(f"IMPACTS: {impacts}")
        expanded_body = "\n".join(expanded_lines) if expanded_lines else headline

        data = {
            "type": "critical_route_alert",
            "event": event,
            "distanceMiles": f"{distance:.1f}",
            "band": band,
            "alertId": alert_id,
            "routeId": route_id,
            "collapsedBody": collapsed_body,
            "expandedBody": expanded_body,
            "what": what,
            "where": where_detail,
            "when": when_detail,
            "impacts": impacts,
            "longText": expanded_body,
        }

        return {
            "title": title,
            "headline": headline,
            "collapsed_body": collapsed_body,
            "expanded_body": expanded_body,
            "expires": expires,
            "data": data,
        }

    def _parse_iso(self, value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        try:
            normalized = value.replace("Z", "+00:00")
            return datetime.fromisoformat(normalized)
        except Exception:
            return None

    def _format_time_range(self, onset: Optional[str], expires: Optional[str]) -> Optional[str]:
        start = self._parse_iso(onset)
        end = self._parse_iso(expires)
        if not start and not end:
            return None
        if start and end:
            return f"{start:%a %-I:%M %p} to {end:%a %-I:%M %p}"
        if start:
            return f"{start:%a %-I:%M %p}"
        return f"Until {end:%a %-I:%M %p}"

    def _format_time_window(self, onset: Optional[str], expires: Optional[str]) -> Optional[str]:
        start = self._parse_iso(onset)
        end = self._parse_iso(expires)
        if start and end:
            return f"From {start:%a %-I:%M %p} through {end:%a %-I:%M %p}"
        if start:
            return f"From {start:%a %-I:%M %p}"
        if end:
            return f"Until {end:%a %-I:%M %p}"
        return None

    def _parse_nws_sections(self, description: str) -> Dict[str, str]:
        sections = {"what": "", "where": "", "when": "", "impacts": ""}
        lines = [line.strip() for line in description.splitlines() if line.strip()]
        for line in lines:
            lowered = line.lower()
            if lowered.startswith("what"):
                sections["what"] = line.split(":", 1)[-1].strip() if ":" in line else line
            elif lowered.startswith("where"):
                sections["where"] = line.split(":", 1)[-1].strip() if ":" in line else line
            elif lowered.startswith("when"):
                sections["when"] = line.split(":", 1)[-1].strip() if ":" in line else line
            elif "impact" in lowered:
                sections["impacts"] = line.split(":", 1)[-1].strip() if ":" in line else line
        return sections

    def _format_where(
        self,
        area_desc: str,
        geometry: Optional[Dict[str, Any]],
        sample_points: List[Dict[str, float]],
        band: str,
    ) -> Optional[str]:
        areas = [a.strip() for a in area_desc.split(";") if a.strip()]
        if not areas:
            return None
        filtered = self._filter_areas_by_geometry(areas, geometry, sample_points)
        display = filtered or areas
        display = display[:4]
        band_label = "within 5 miles" if band == "within_5" else "within 15 miles"
        return f"{', '.join(display)} ({band_label})"

    def _filter_areas_by_geometry(
        self,
        areas: List[str],
        geometry: Optional[Dict[str, Any]],
        sample_points: List[Dict[str, float]],
    ) -> List[str]:
        if not geometry or not sample_points:
            return []
        rings = list(self._iter_geojson_coordinates(geometry.get("coordinates")))
        if not rings:
            return []
        for point in sample_points:
            lat = point.get("lat")
            lon = point.get("lon")
            if lat is None or lon is None:
                continue
            if any(self._point_in_polygon(lat, lon, ring) for ring in rings):
                return areas
        return []

    def _point_in_polygon(self, lat: float, lon: float, ring: List[Tuple[float, float]]) -> bool:
        inside = False
        j = len(ring) - 1
        for i in range(len(ring)):
            xi, yi = ring[i]
            xj, yj = ring[j]
            intersect = ((yi > lat) != (yj > lat)) and (
                lon < (xj - xi) * (lat - yi) / ((yj - yi) + 1e-9) + xi
            )
            if intersect:
                inside = not inside
            j = i
        return inside

    def _is_critical(self, alert: Dict[str, Any]) -> bool:
        props = alert.get("properties", {})
        event = props.get("event", "")
        severity = (props.get("severity") or "").lower()
        # Accept all NWS alerts except explicitly minor/unknown/test levels; do not filter by event type.
        if not event:
            return False
        if severity in {"minor", "unknown", "test", "moderate"}:
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

    def _fetch_alerts(self, lat: float, lon: float) -> Optional[Iterable[Dict[str, Any]]]:
        url = f"https://api.weather.gov/alerts/active?point={lat},{lon}"
        headers = {
            "User-Agent": DEFAULT_NOAA_UA,
            "Accept": "application/geo+json",
        }
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(url, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                return data.get("features", [])
        except Exception as exc:  # noqa: BLE001
            logger.warning("NWS fetch failed for point %.3f,%.3f: %s", lat, lon, exc)
            return None

    def _point_cache_key(self, lat: float, lon: float, precision: int = 1) -> str:
        rounded_lat = round(lat, precision)
        rounded_lon = round(lon, precision)
        fmt = f"{{:.{precision}f}}"
        return f"{fmt.format(rounded_lat)},{fmt.format(rounded_lon)}"

    def _safe_fetch_alerts(self, lat: float, lon: float) -> Optional[List[Dict[str, Any]]]:
        try:
            result = self.fetcher(lat, lon)
            if result is None:
                return None
            return list(result)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[route-alerts] fetch failed for point %.3f,%.3f: %s", lat, lon, exc)
            return None

    def _fetch_alerts_concurrent(self, unique_points: Dict[str, Tuple[float, float]]) -> Dict[str, List[Dict[str, Any]]]:
        if not unique_points:
            return {}

        max_workers_env = int(os.environ.get("ROUTE_ALERTS_MAX_WORKERS", "32"))
        max_workers = max(1, min(32, min(max_workers_env, len(unique_points))))

        results: Dict[str, List[Dict[str, Any]]] = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map = {
                executor.submit(self._safe_fetch_alerts, lat, lon): key
                for key, (lat, lon) in unique_points.items()
            }

            for future in concurrent.futures.as_completed(future_map):
                key = future_map[future]
                try:
                    alerts = future.result()
                except Exception as exc:  # noqa: BLE001
                    logger.warning("[route-alerts] NWS fetch error for %s: %s", key, exc)
                    alerts = None
                results[key] = list(alerts) if alerts else None

        return results
