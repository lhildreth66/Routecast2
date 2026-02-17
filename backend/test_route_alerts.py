from datetime import datetime, timezone, timedelta

import pytest

from notifications.route_alerts import (
    CriticalRouteAlertWorker,
    RouteAlertService,
    sample_route_points,
)


class FakeCursor:
    def __init__(self, docs):
        self.docs = list(docs)

    def limit(self, n):
        return FakeCursor(self.docs[:n])

    def __iter__(self):
        return iter(self.docs)


class FakeCollection:
    def __init__(self):
        self.docs = []

    def create_index(self, *args, **kwargs):
        return None

    def insert_one(self, doc):
        self.docs.append(doc)
        return type("Result", (), {"inserted_id": len(self.docs)})

    def update_many(self, query, update):
        matched = 0
        for doc in self.docs:
            if matches(doc, query):
                matched += 1
                if "$set" in update:
                    doc.update(update["$set"])
        return type("Result", (), {"modified_count": matched})

    def update_one(self, query, update, upsert=False):
        before = len(self.docs)
        self.update_many(query, update)
        if upsert and len(self.docs) == before:
            doc = {}
            if "$set" in update:
                doc.update(update["$set"])
            self.docs.append(doc)

    def find(self, query=None):
        query = query or {}
        return FakeCursor([d for d in self.docs if matches(d, query)])

    def find_one(self, query, projection=None):
        for d in self.docs:
            if matches(d, query):
                return d
        return None

    def delete_one(self, query):
        for idx, d in enumerate(self.docs):
            if matches(d, query):
                self.docs.pop(idx)
                return type("Result", (), {"deleted_count": 1})
        return type("Result", (), {"deleted_count": 0})

    def count_documents(self, query):
        return len([d for d in self.docs if matches(d, query)])


class FakeDB:
    def __init__(self):
        self.route_monitors = FakeCollection()
        self.sent_alerts = FakeCollection()
        self.sent_alert_keys = FakeCollection()
        self.push_tokens = FakeCollection()


class FakePushGateway:
    def __init__(self, succeed: bool = True):
        self.sent = []
        self.succeed = succeed

    def send(self, token: str, title: str, body: str, expanded_body=None, data=None) -> bool:  # noqa: ANN001
        self.sent.append({"token": token, "title": title, "body": body, "expanded_body": expanded_body, "data": data})
        return self.succeed


def matches(doc, query):  # noqa: ANN001
    for key, value in query.items():
        if key == "$or":
            if not any(matches(doc, sub) for sub in value):
                return False
            continue
        if isinstance(value, dict):
            if "$gte" in value:
                probe = doc.get(key)
                if probe is None or probe < value["$gte"]:
                    return False
            if "$nin" in value and doc.get(key) in value["$nin"]:
                return False
            continue
        if doc.get(key) != value:
            return False
    return True


def make_alert(event: str, alert_id: str, lon_offset: float, severity: str = "Severe"):
    base_lat = 40.0
    base_lon = -105.0
    poly = [
        [base_lon + lon_offset, base_lat],
        [base_lon + lon_offset + 0.01, base_lat],
        [base_lon + lon_offset + 0.01, base_lat + 0.01],
    ]
    return {
        "id": alert_id,
        "properties": {
            "id": alert_id,
            "event": event,
            "severity": severity,
            "headline": f"{event} nearby",
            "expires": datetime.now(timezone.utc).isoformat(),
        },
        "geometry": {"type": "Polygon", "coordinates": [poly]},
    }


def test_sample_points_include_endpoints_and_limit():
    route = [{"lat": 0.0, "lon": 0.0}, {"lat": 0.0, "lon": 1.0}]
    samples = sample_route_points(route, sample_miles=10, max_points=25)
    assert samples[0] == route[0]
    assert samples[-1] == route[-1]
    assert len(samples) <= 25


def test_worker_dedupes_and_applies_band_and_severity_filter():
    now = datetime.now(timezone.utc)
    db = FakeDB()
    push = FakePushGateway()
    service = RouteAlertService(db, push_gateway=push, now_fn=lambda: now)

    monitor = service.start_monitor(
        user_id="u1",
        push_token="token",
        route_points=[{"lat": 40.0, "lon": -105.0}, {"lat": 40.1, "lon": -105.1}],
        route_id="route-1",
        sample_miles=100,
        max_points=5,
    )

    db.sent_alerts.insert_one(
        {
            "monitor_id": monitor["monitor_id"],
            "alert_id": "alert-1",
            "band": "within_5",
            "sent_at": now,
        }
    )

    alerts = [
        make_alert("Tornado Warning", "alert-1", lon_offset=0.0, severity="Extreme"),
        make_alert("Severe Thunderstorm Warning", "alert-2", lon_offset=0.2, severity="Severe"),
        make_alert("Severe Thunderstorm Warning", "alert-3", lon_offset=0.05, severity="moderate"),
    ]

    worker = CriticalRouteAlertWorker(service, fetcher=lambda _lat, _lon: alerts, now_fn=lambda: now)
    result = worker.run_once()

    assert result["sent"] == 1
    assert "alert-2" in push.sent[0]["data"]["alertIds"]
    assert db.sent_alerts.count_documents({"alert_id": "alert-2"}) == 1


def test_worker_respects_hourly_cap_for_non_tornado():
    now = datetime.now(timezone.utc)
    db = FakeDB()
    push = FakePushGateway()
    service = RouteAlertService(db, push_gateway=push, now_fn=lambda: now)

    monitor = service.start_monitor(
        user_id="u1",
        push_token="token",
        route_points=[{"lat": 40.0, "lon": -105.0}, {"lat": 40.1, "lon": -105.1}],
        route_id="route-2",
        sample_miles=100,
        max_points=5,
    )

    db.sent_alerts.insert_one(
        {
            "monitor_id": monitor["monitor_id"],
            "alert_id": "old-1",
            "event": "Severe Thunderstorm Warning",
            "band": "within_5",
            "sent_at": now - timedelta(minutes=10),
        }
    )
    db.sent_alerts.insert_one(
        {
            "monitor_id": monitor["monitor_id"],
            "alert_id": "old-2",
            "event": "Severe Thunderstorm Warning",
            "band": "within_5",
            "sent_at": now - timedelta(minutes=5),
        }
    )

    alerts = [make_alert("Severe Thunderstorm Warning", "new-1", lon_offset=0.0, severity="Severe")]

    worker = CriticalRouteAlertWorker(service, fetcher=lambda _lat, _lon: alerts, now_fn=lambda: now)
    result = worker.run_once()

    assert result["sent"] == 0
    assert not push.sent
