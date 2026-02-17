from datetime import datetime, timezone, timedelta
import hashlib
import json
import httpx

from notifications.route_alerts import (
    CriticalRouteAlertWorker,
    haversine_miles,
    sample_route_points,
)


class FakePushGateway:
    def __init__(self, should_send: bool = True):
        self.should_send = should_send
        self.sent = 0

    def send(self, token, title, body, data=None):
        if self.should_send:
            self.sent += 1
            return True
        return False


def route_signature(route_id: str, points):
    payload = {"route_id": route_id, "points": points}
    raw = json.dumps(payload, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()


class InMemoryService:
    def __init__(self, now_fn=datetime.now, push_gateway=None):
        self.now = now_fn
        self.push_gateway = push_gateway or FakePushGateway()
        self.sent = []
        self.monitors = []
        self.current_route_id: str | None = None

    def get_active_monitors(self):
        return self.monitors

    def has_sent(self, route_signature_val, route_id, alert_id, band):
        return any(
            s["route_signature"] == route_signature_val
            and s["route_id"] == route_id
            and s["alert_id"] == alert_id
            and s["band"] == band
            for s in self.sent
        )

    def count_recent(self, monitor_id, minutes=60, exclude_events=None):
        cutoff = self.now(timezone.utc) - timedelta(minutes=minutes)
        events = exclude_events or []
        return sum(
            1
            for s in self.sent
            if s["monitor_id"] == monitor_id
            and s["sent_at"] >= cutoff
            and s["event"] not in events
        )

    def record_sent(self, monitor_id, route_signature_val, route_id, alert_id, event, band, distance, headline, expires, alert_key=None):
        self.sent.append(
            {
                "monitor_id": monitor_id,
                "route_signature": route_signature_val,
                "route_id": route_id,
                "alert_id": alert_id,
                "band": band,
                "event": event,
                "sent_at": self.now(timezone.utc),
                "alert_key": alert_key,
            }
        )

    def get_current_route_id(self, user_id=None, push_token=None):  # noqa: ANN001
        return self.current_route_id

    def mark_alert_key(self, monitor_id, alert_key, route_id):  # noqa: ANN001
        return None

    def alert_key_recent(self, monitor_id, alert_key, cooldown_minutes):  # noqa: ANN001
        return False

    def within_cooldown(self, monitor_id, event, cooldown_minutes):  # noqa: ANN001
        return False

    def monitor_within_cooldown(self, monitor_id, cooldown_minutes):  # noqa: ANN001
        return False, None


def make_monitor(route_id: str = "r1"):
    points = [{"lat": 0.0, "lon": 0.0}]
    sig = route_signature(route_id, points)
    return {
        "monitor_id": "m1",
        "push_token": "token",
        "sample_points": points,
        "route_id": route_id,
        "route_signature": sig,
    }


def make_alert(event: str = "Severe Thunderstorm Warning", alert_id: str = "a1"):
    return {
        "id": alert_id,
        "properties": {
            "event": event,
            "severity": "Severe",
            "headline": f"{event} headline",
        },
        "geometry": {"coordinates": [[[0.0, 0.0]]]},
    }


def test_sampling_includes_endpoints_and_spacing():
    route = [{"lat": 0.0, "lon": 0.0}, {"lat": 1.0, "lon": 0.0}]
    samples = sample_route_points(route, sample_miles=10.0, max_points=25)

    assert samples[0] == route[0]
    assert samples[-1] == route[-1]
    assert len(samples) <= 25

    for a, b in zip(samples, samples[1:]):
        assert haversine_miles(a["lat"], a["lon"], b["lat"], b["lon"]) <= 11.0


def test_sampling_caps_max_points():
    route = [{"lat": i * 0.05, "lon": 0.0} for i in range(200)]
    samples = sample_route_points(route, sample_miles=1.0, max_points=25)
    assert len(samples) == 25
    assert samples[0] == route[0]
    assert samples[-1] == route[-1]


def test_band_logic():
    service = InMemoryService(now_fn=lambda tz=None: datetime.now(timezone.utc))
    worker = CriticalRouteAlertWorker(service, fetcher=lambda lat, lon: [])
    assert worker._band_for_distance(0) == "within_5"
    assert worker._band_for_distance(5) == "within_5"
    assert worker._band_for_distance(10) == "within_15"
    assert worker._band_for_distance(15) == "within_15"
    assert worker._band_for_distance(16) is None


def test_dedupe_allows_b_then_a(monkeypatch):
    now = datetime(2024, 1, 1, tzinfo=timezone.utc)

    def now_fn(tz=None):
        return now

    service = InMemoryService(now_fn=now_fn)
    monitor = make_monitor()
    service.monitors = [monitor]
    service.current_route_id = monitor["route_id"]

    alert = make_alert()

    # First pass at 10 miles (within_15)
    worker = CriticalRouteAlertWorker(service, fetcher=lambda lat, lon: [alert])
    monkeypatch.setattr(worker, "_distance_to_alert", lambda p, a: 10.0)
    result1 = worker._process_monitor(monitor)
    assert result1["sent"] == 1

    # Second pass closer (within_5) should send again
    monkeypatch.setattr(worker, "_distance_to_alert", lambda p, a: 3.0)
    result2 = worker._process_monitor(monitor)
    assert result2["sent"] == 1


def test_dedupe_blocks_a_then_b(monkeypatch):
    now = datetime(2024, 1, 1, tzinfo=timezone.utc)

    def now_fn(tz=None):
        return now

    service = InMemoryService(now_fn=now_fn)
    monitor = make_monitor()
    service.monitors = [monitor]
    service.current_route_id = monitor["route_id"]
    alert = make_alert()

    worker = CriticalRouteAlertWorker(service, fetcher=lambda lat, lon: [alert])
    monkeypatch.setattr(worker, "_distance_to_alert", lambda p, a: 3.0)
    result1 = worker._process_monitor(monitor)
    assert result1["sent"] == 1

    # Now at 10 miles (within_15) should skip because within_5 already sent
    monkeypatch.setattr(worker, "_distance_to_alert", lambda p, a: 10.0)
    result2 = worker._process_monitor(monitor)
    assert result2["sent"] == 0
    assert result2["skipped_dedupe"] >= 1


def test_hourly_cap_and_tornado(monkeypatch):
    now = datetime(2024, 1, 1, tzinfo=timezone.utc)

    def now_fn(tz=None):
        return now

    service = InMemoryService(now_fn=now_fn)
    monitor = make_monitor()
    service.monitors = [monitor]
    service.current_route_id = monitor["route_id"]

    alerts = [make_alert(alert_id=f"a{i}") for i in range(3)]
    worker = CriticalRouteAlertWorker(service, fetcher=lambda lat, lon: alerts)
    monkeypatch.setattr(worker, "_distance_to_alert", lambda p, a: 4.0)

    result = worker._process_monitor(monitor)
    assert result["sent"] == 2  # third blocked by cap
    assert result["skipped_cap"] == 1

    # Tornado should bypass cap
    tornado_alert = make_alert(event="Tornado Warning", alert_id="tw1")
    worker.fetcher = lambda lat, lon: [tornado_alert]
    result2 = worker._process_monitor(monitor)
    assert result2["sent"] == 1


def test_dedupe_shared_bucket(monkeypatch):
    now = datetime(2024, 1, 1, tzinfo=timezone.utc)

    def now_fn(tz=None):
        return now

    service = InMemoryService(now_fn=now_fn)

    points_a = [{"lat": 0.04, "lon": 0.06}]
    points_b = [{"lat": 0.03, "lon": 0.07}]  # same 0.1° bucket as points_a

    monitor_a = {
        "monitor_id": "m1",
        "push_token": "token1",
        "sample_points": points_a,
        "route_id": "r1",
        "route_signature": route_signature("r1", points_a),
    }
    monitor_b = {
        "monitor_id": "m2",
        "push_token": "token2",
        "sample_points": points_b,
        "route_id": "r2",
        "route_signature": route_signature("r2", points_b),
    }
    service.monitors = [monitor_a, monitor_b]

    fetch_calls = {"count": 0}

    def fetcher(lat, lon):
        fetch_calls["count"] += 1
        return [make_alert(alert_id="shared")]

    worker = CriticalRouteAlertWorker(service, fetcher=fetcher)
    monkeypatch.setattr(worker, "_distance_to_alert", lambda p, a: 4.0)

    result = worker.run_once()

    assert fetch_calls["count"] == 1  # shared bucket yields single network call
    assert result["nws_calls"] == 1
    assert result["sent"] == 2  # both monitors still notified


def test_timeout_is_skipped(monkeypatch):
    now = datetime(2024, 1, 1, tzinfo=timezone.utc)

    def now_fn(tz=None):
        return now

    service = InMemoryService(now_fn=now_fn)
    points = [{"lat": 1.23, "lon": 4.56}]
    monitor = {
        "monitor_id": "m1",
        "push_token": "token1",
        "sample_points": points,
        "route_id": "r-timeout",
        "route_signature": route_signature("r-timeout", points),
    }
    service.monitors = [monitor]

    fetch_calls = {"count": 0}

    def fetcher(lat, lon):
        fetch_calls["count"] += 1
        raise httpx.ReadTimeout("timeout")

    worker = CriticalRouteAlertWorker(service, fetcher=fetcher)
    monkeypatch.setattr(worker, "_distance_to_alert", lambda p, a: 4.0)

    result = worker.run_once()

    assert fetch_calls["count"] == 1
    assert result["nws_calls"] == 1
    assert result["alerts_seen"] == 0
    assert result["sent"] == 0
