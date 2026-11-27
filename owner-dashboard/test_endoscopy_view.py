import isolation  # noqa: F401  (clears credentials, blocks external network; keep first)
import json
import socket
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch
import endoscopy_view as v

KEY = "unit-test-key-0123456789-abcdefghij"
SECRET_PREFIXES = isolation.SECRET_PREFIXES


def data():
    return {"schema": 1, "as_of": "2026-11-27T15:35:00+00:00",
            "counts": {k: 1 for k in (*v.LABELS, *v.WEEKS)},
            "modules": [{"title": "<example>", "completed_lessons": 1}]}


class EndoscopyTests(unittest.TestCase):
    def test_standalone_reporting_target(self):
        self.assertEqual(v.URL, "https://endoscopy-owner-reporting.onrender.com/api/owner/reporting")
        self.assertNotIn("endoscopy-nurse-pro-api", v.URL)

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


class Upstream:
    """Scriptable loopback stand-in for the reporting API."""

    def __init__(self):
        self.status, self.body, self.delay, self.location, self.requests = 200, b"{}", 0, None, []
        self.reply()
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                outer.requests.append(self.headers.get("X-Reporting-Key"))
                time.sleep(outer.delay)
                self.send_response(outer.status)
                if outer.location:
                    self.send_header("Location", outer.location)
                self.send_header("Content-Length", str(len(outer.body)))
                self.end_headers()
                self.wfile.write(outer.body)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_port}/api/owner/reporting"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def reply(self, status=200, body=None, delay=0):
        self.status, self.delay = status, delay
        self.body = json.dumps(data() if body is None else body).encode()
        self.requests.clear()


class UpstreamTests(unittest.TestCase):
    def setUp(self):
        v.reset()
        self.up = Upstream()
        self.clock = [1000.0]
        stack = [patch.object(v, "URL", self.up.url), patch.object(v, "monotonic", lambda: self.clock[0]),
                 patch.dict("os.environ", {"ENDOSCOPY_REPORTING_KEY": KEY})]
        for p in stack:
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(self.up.server.shutdown)
        self.addCleanup(self.up.server.server_close)

    def page(self):
        return v.render_endoscopy(v.PRODUCT)

    def test_key_is_trimmed_before_validation_and_sent(self):
        with patch.dict("os.environ", {"ENDOSCOPY_REPORTING_KEY": "  " + KEY + "\n"}):
            self.assertIn("Registered users", self.page())
        self.assertEqual(self.up.requests, [KEY])

    def test_invalid_key_makes_no_request(self):
        for bad in ("short", "x" * 31, "a" * 20 + " " + "b" * 20, "é" * 40, "   "):
            with self.subTest(bad=bad), patch.dict("os.environ", {"ENDOSCOPY_REPORTING_KEY": bad}):
                page = self.page()
                self.assertTrue("unavailable" in page or "not connected" in page)
                self.assertNotIn("Registered users", page)
        self.assertEqual(self.up.requests, [])

    def test_failure_cache_for_sixty_seconds(self):
        self.up.reply(503)
        for _ in range(3):
            self.assertIn("unavailable", self.page())
        self.assertEqual(len(self.up.requests), 1)
        self.clock[0] += 59
        self.page()
        self.assertEqual(len(self.up.requests), 1)
        self.clock[0] += 2
        self.page()
        self.assertEqual(len(self.up.requests), 2)
        self.up.reply()
        self.clock[0] += 61
        self.assertIn("Registered users", self.page())
        self.assertEqual(len(self.up.requests), 1)

    def test_concurrent_loads_share_one_failed_attempt(self):
        self.up.reply(503, delay=0.4)
        start, pages = time.time(), []
        threads = [threading.Thread(target=lambda: pages.append(self.page())) for _ in range(8)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        self.assertEqual(len(self.up.requests), 1)
        self.assertTrue(all("unavailable" in p for p in pages))
        self.assertLess(time.time() - start, 2)

    def test_concurrent_loads_share_one_success(self):
        self.up.reply(delay=0.3)
        pages = []
        threads = [threading.Thread(target=lambda: pages.append(self.page())) for _ in range(8)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        self.assertEqual(len(self.up.requests), 1)
        self.assertTrue(all("Registered users" in p for p in pages))

    def test_success_cached_five_minutes(self):
        self.page()
        self.clock[0] += 299
        self.page()
        self.assertEqual(len(self.up.requests), 1)
        self.clock[0] += 2
        self.page()
        self.assertEqual(len(self.up.requests), 2)

    def test_unavailable_shows_no_counts_and_last_success(self):
        self.page()
        self.up.reply(500, body={"detail": KEY})
        self.clock[0] += 301
        page = self.page()
        self.assertIn("No counts are shown", page)
        self.assertIn("Last successful report: 2026-11-27T15:35:00+00:00", page)
        for fragment in ("<strong>", "<table", "Registered users", KEY):
            self.assertNotIn(fragment, page)
        v.reset()
        self.assertIn("No successful report since this dashboard started", self.page())

    def test_redirect_is_not_followed(self):
        sink = Upstream()
        self.addCleanup(sink.server.shutdown)
        self.addCleanup(sink.server.server_close)
        self.up.location, self.up.status = sink.url, 302
        self.assertIn("unavailable", self.page())
        self.assertEqual(sink.requests, [])

    def test_other_products_never_call_upstream(self):
        import dashboard
        self.up.reply(503, delay=0.2)
        for product in dashboard.APPS:
            if product not in (v.PRODUCT, "routecast"):
                with patch.object(dashboard, "render_web", return_value=""):
                    self.assertNotIn(b"backend reporting", dashboard.render_portfolio(product))
        self.assertEqual(self.up.requests, [])

    def test_presentation(self):
        body = data()
        body["counts"].update(registered=100, active=25, week_1=5, week_2=10, week_3=0, week_4=20)
        body["modules"] = [{"title": "A <b>", "completed_lessons": 9}, {"title": "B", "completed_lessons": 9},
                           {"title": "C", "completed_lessons": 2}]
        self.up.reply(body=body)
        page = self.page()
        self.assertIn("Weekly registrations", page)
        self.assertIn("Days 28–21 before snapshot</td><td class=\"num\">5</td>", page)
        self.assertIn("Days 7–0 before snapshot</td><td class=\"num\">20</td>", page)
        self.assertIn('style="width:100.0%"', page)
        self.assertIn('style="width:0.0%"', page)
        self.assertIn('<td class="num">1</td><td>A &lt;b&gt;</td><td class="num">9</td>', page)
        self.assertIn('<td class="num">1</td><td>B</td>', page)
        self.assertIn('<td class="num">3</td><td>C</td>', page)
        self.assertNotIn("A <b>", page)
        self.assertLess(page.index("Registered users"), page.index("Active subscription records"))
        self.assertLess(page.index("Active subscription records"), page.index("Verified paying subscribers"))
        self.assertIn("Not connected. Requires verified App Store", page)
        self.assertIn("25.00%", page)
        self.assertIn("up to about 6 minutes old", page)
        self.assertIn("Last successful report: <strong>2026-11-27T15:35:00+00:00</strong>", page)

    def test_zero_data_is_real_data(self):
        body = data()
        body["counts"] = {k: 0 for k in body["counts"]}
        body["modules"] = []
        self.up.reply(body=body)
        page = self.page()
        self.assertIn("<small>Registered users</small><strong>0</strong>", page)
        self.assertIn("No completed lesson records", page)


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
