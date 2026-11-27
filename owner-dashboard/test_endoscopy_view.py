import isolation  # noqa: F401  (clears credentials, blocks external network; keep first)
import socket
import threading
import time
import unittest
from unittest.mock import patch
import endoscopy_view as v

KEY = "unit-test-key-0123456789-abcdefghij"
SECRET_PREFIXES = isolation.SECRET_PREFIXES


def data():
    return {"schema": 1, "as_of": "2026-11-27T15:35:00+00:00",
            "counts": {k: 1 for k in (*v.LABELS, *v.WEEKS)},
            "modules": [{"title": "<example>", "completed_lessons": 1}]}


class EndoscopyTests(unittest.TestCase):
    def setUp(self):
        v.reset()

    def test_render(self):
        with patch.object(v, "fetch", return_value=v.validate(data())):
            output = v.render_endoscopy(v.PRODUCT)
            self.assertIn("Registered users", output)
            self.assertIn("&lt;example&gt;", output)
            self.assertNotIn("<example>", output)
            self.assertEqual(v.render_endoscopy("routecast"), "")

    def test_invalid_counts(self):
        d = data()
        d["counts"]["active"] = -1
        with self.assertRaises(ValueError):
            v.validate(d)

    def test_missing(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertIn("not connected", v.render_endoscopy(v.PRODUCT))

    def test_error_is_sanitized(self):
        with patch.object(v, "fetch", side_effect=RuntimeError("private-secret")):
            result = v.render_endoscopy(v.PRODUCT)
            self.assertIn("unavailable", result)
            self.assertNotIn("private-secret", result)

    def test_dashboard_product_isolation(self):
        import dashboard
        with patch.object(v, "fetch", return_value=v.validate(data())) as fetch, \
             patch.object(dashboard, "render_revenuecat", return_value=""), \
             patch.object(dashboard, "render_play", return_value=""), \
             patch.object(dashboard, "render_marketing", return_value=""), \
             patch.object(dashboard, "render_web", return_value=""):
            self.assertIn(b"Registered users", dashboard.render_portfolio(v.PRODUCT))
            for product in dashboard.APPS:
                if product != v.PRODUCT:
                    body = dashboard.render() if product == "routecast" else dashboard.render_portfolio(product)
                    self.assertNotIn(b"backend reporting", body)
            self.assertEqual(fetch.call_count, 1)


class DatabaseAdapterTests(unittest.TestCase):
    def setUp(self):
        v.reset()
        self.clock = [1000.0]
        self.calls = 0
        self.result = data()
        self.error = None
        self.delay = 0
        stack = [patch.object(v, "read_snapshot", self.read),
                 patch.object(v, "monotonic", lambda: self.clock[0]),
                 patch.dict("os.environ", {"ENDOSCOPY_MONGO_URL": "synthetic-uri",
                                          "ENDOSCOPY_DB_NAME": "testdb"})]
        for p in stack:
            p.start()
            self.addCleanup(p.stop)

    def read(self, uri, database):
        self.calls += 1
        self.assertEqual(uri, "synthetic-uri")
        self.assertEqual(database, "testdb")
        time.sleep(self.delay)
        if self.error:
            raise self.error
        return self.result

    def page(self):
        return v.render_endoscopy(v.PRODUCT)

    def test_incomplete_configuration(self):
        for key in ("ENDOSCOPY_MONGO_URL", "ENDOSCOPY_DB_NAME"):
            with patch.dict("os.environ", {key: ""}):
                self.assertIn("unavailable", self.page())
        self.assertEqual(self.calls, 0)

    def test_failure_cache_and_recovery(self):
        self.error = RuntimeError("synthetic-password")
        for _ in range(3):
            page = self.page()
            self.assertIn("unavailable", page)
            self.assertNotIn("synthetic-password", page)
        self.assertEqual(self.calls, 1)
        self.clock[0] += 59
        self.page()
        self.assertEqual(self.calls, 1)
        self.error = None
        self.clock[0] += 2
        self.assertIn("Registered users", self.page())
        self.assertEqual(self.calls, 2)

    def test_concurrent_loads_share_snapshot(self):
        self.delay = 0.1
        pages = []
        threads = [threading.Thread(target=lambda: pages.append(self.page())) for _ in range(8)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        self.assertEqual(len(pages), 8)
        self.assertTrue(all("Registered users" in p for p in pages))
        self.assertEqual(self.calls, 1)

    def test_concurrent_failures_share_attempt(self):
        self.delay = 0.1
        self.error = RuntimeError("private")
        pages = []
        threads = [threading.Thread(target=lambda: pages.append(self.page())) for _ in range(8)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        self.assertEqual(len(pages), 8)
        self.assertTrue(all("unavailable" in p for p in pages))
        self.assertEqual(self.calls, 1)

    def test_success_cached_five_minutes(self):
        self.page()
        self.clock[0] += 299
        self.page()
        self.assertEqual(self.calls, 1)
        self.clock[0] += 2
        self.page()
        self.assertEqual(self.calls, 2)

    def test_unavailable_shows_last_success_not_counts(self):
        self.page()
        self.error = RuntimeError("secret")
        self.clock[0] += 301
        page = self.page()
        self.assertIn("No counts are shown", page)
        self.assertIn("Last successful report: 2026-11-27T15:35:00+00:00", page)
        self.assertNotIn("<table", page)
        self.assertNotIn("Registered users", page)
        self.assertNotIn("secret", page)

    def test_presentation(self):
        self.result["counts"].update(registered=100, active=25, week_1=5, week_2=10, week_3=0, week_4=20)
        self.result["modules"] = [{"title": "A <b>", "completed_lessons": 9},
                                  {"title": "B", "completed_lessons": 9},
                                  {"title": "C", "completed_lessons": 2}]
        page = self.page()
        self.assertIn("Weekly registrations", page)
        self.assertIn("Days 28–21 before snapshot", page)
        self.assertIn('style="width:100.0%"', page)
        self.assertIn('style="width:0.0%"', page)
        self.assertIn('<td class="num">1</td><td>A &lt;b&gt;</td>', page)
        self.assertIn('<td class="num">3</td><td>C</td>', page)
        self.assertNotIn("A <b>", page)
        self.assertIn("25.00%", page)
        self.assertIn("5 minutes", page)
        self.assertIn("Verified paying subscribers", page)

    def test_zero_data_is_real_data(self):
        self.result["counts"] = {k: 0 for k in self.result["counts"]}
        self.result["modules"] = []
        page = self.page()
        self.assertIn("<small>Registered users</small><strong>0</strong>", page)
        self.assertIn("No completed lesson records", page)


class QueryTests(unittest.TestCase):
    def test_roles(self):
        from endoscopy_data import verify_roles
        for roles in ([{"role": "read", "db": "other"}], [{"role": "readWrite", "db": "testdb"}],
                      [], [{"role": "read", "db": "testdb"}, {"role": "readWrite", "db": "other"}]):
            with self.assertRaises(ValueError):
                verify_roles({"authInfo": {"authenticatedUsers": [{"user":"test"}],
                                          "authenticatedUserRoles": roles}}, "testdb")
        verify_roles({"authInfo": {"authenticatedUsers": [{"user":"test"}],
                                  "authenticatedUserRoles": [{"role":"read", "db":"testdb"}]}}, "testdb")

    def test_all_queries(self):
        from endoscopy_data import snapshot
        from datetime import datetime, timezone, timedelta
        from unittest.mock import MagicMock
        db = MagicMock()
        db.__getitem__.return_value.count_documents.return_value = 7
        db.__getitem__.return_value.aggregate.return_value.__enter__.return_value.__iter__.return_value = iter([{"_id":"mod-1", "count": 3}])
        now = datetime(2026, 11, 27, tzinfo=timezone.utc)
        result = snapshot(db, now)
        self.assertEqual(set(result["counts"]), set(v.LABELS) | set(v.WEEKS))
        self.assertEqual(set(result["counts"].values()), {7})
        self.assertEqual(db.__getitem__.return_value.count_documents.call_count, 17)
        self.assertEqual(result["modules"], [{"title":"Procedure Room Readiness","completed_lessons":3}])
        db.__getitem__.return_value.count_documents.assert_any_call(
            {"created_at": {"$gte": now-timedelta(days=28), "$lt": now-timedelta(days=21)}}, maxTimeMS=3000)

    def test_invalid_configuration_never_connects(self):
        from endoscopy_data import read_snapshot
        for uri, db in [("https://example.com", "testdb"), ("mongodb://example.com", "admin")]:
            with self.assertRaises(ValueError):
                read_snapshot(uri, db)


class IsolationTests(unittest.TestCase):
    def test_credentials_cleared_and_external_network_blocked(self):
        import os
        self.assertEqual([n for n in os.environ if n.startswith(SECRET_PREFIXES)], [])
        for host in ("example.com", "93.184.216.34", "2001:4860:4860::8888"):
            with self.subTest(host=host), self.assertRaises(isolation.NetworkBlocked):
                socket.create_connection((host, 443), timeout=1)
        with self.assertRaises(isolation.NetworkBlocked):
            socket.getaddrinfo("routecast-backend.onrender.com", 443)
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        socket.create_connection(listener.getsockname(), timeout=1).close()
        listener.close()
