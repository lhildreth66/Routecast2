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
        logger.info(
            "[route-alerts] fetched active monitors count=%d filter=active=True",
            len(monitors),
        )
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
            "skipped_points": 0,
            "skipped_geometry": 0,
            "monitors_with_geometry": 0,
            "monitors_without_geometry": 0,
        }

        for monitor in monitors:
            result = self._process_monitor(monitor)
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

        # Instrumentation for each monitor to understand sampling and token wiring
        sample_points_count = len(sample_points)
        first_points = sample_points[:2]
        expires_at = monitor.get("expires_at") or monitor.get("expires") or monitor.get("expiresAt")
        has_polyline = bool(route_points or polyline_val)
        token_prefix = (token or "")[:18]
        push_token_alt = monitor.get("expo_push_token") or monitor.get("pushToken") or monitor.get("fcm_token")
        token_alt_prefix = (push_token_alt or "")[:18]

        bbox = _compute_bbox(sample_points) or _compute_bbox(route_points) or _compute_bbox(explicit_points or [])

        logger.info(
            "[route-alerts] monitor inspect id=%s expires=%s active=%s has_polyline=%s sample_points=%d first_points=%s bbox=%s push_token_prefix=%s alt_token_prefix=%s legs=%s explicit_points=%s",
            monitor_id,
            expires_at,
            monitor.get("active"),
            has_polyline,
            sample_points_count,
            first_points,
            token_prefix,
            token_alt_prefix,
            bool(legs_val),
            bool(explicit_points),
            bbox,
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
                # Persist back so future runs have points
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
            return stats

        stats["monitors_with_geometry"] += 1

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
                if band == "within_15" and self.service.has_sent(route_signature, route_id, alert_id, "within_5", monitor_id=monitor_id):
                    stats["skipped"] += 1
                    stats["skipped_dedupe"] += 1
                    continue

                if self.service.has_sent(route_signature, route_id, alert_id, band, monitor_id=monitor_id) or self.service.has_sent(route_signature, route_id, alert_id, "within_5", monitor_id=monitor_id) or self.service.has_sent(route_signature, route_id, alert_id, "within_15", monitor_id=monitor_id):
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

                payload = self._build_notification_payload(
                    alert=alert,
                    alert_id=alert_id,
                    distance=distance,
                    band=band,
                    route_id=route_id,
                    sample_points=sample_points,
                )

                if self.service.push_gateway.send(
                    token,
                    title=payload["title"],
                    body=payload["collapsed_body"],
                    expanded_body=payload["expanded_body"],
                    data=payload["data"],
                ):
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
                    )
                    stats["sent"] += 1
                else:
                    stats["skipped"] += 1
                    stats["skipped_push"] += 1

        return stats

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

        time_range = self._format_time_range(onset, expires)
        collapsed_parts = [p for p in [time_range, where_detail] if p]
        collapsed_body = " · ".join(collapsed_parts) if collapsed_parts else headline

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
