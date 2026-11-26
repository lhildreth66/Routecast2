import base64
import json
import threading
import unittest
from unittest.mock import patch
from urllib.request import urlopen, Request
from urllib.error import HTTPError
from http.server import ThreadingHTTPServer
import dashboard
from ga4_reports import property_id

class DashboardTests(unittest.TestCase):
    def test_all_products(self):
        self.assertEqual(len(dashboard.APPS), 8)
        for key in dashboard.APPS:
            body = dashboard.render() if key == "routecast" else dashboard.render_portfolio(key)
            self.assertIn(b"Dashboard", body)
        self.assertIn(b"HildrethTechnology.com", dashboard.render_portfolio())

    def test_provider_reconciliation(self):
        data = {"subscriptions_by_provider":{"apple":0,"google":3,"stripe":0,"admin":1},
                "trialing_users":12,"active_subscriptions":5,"total_users":20,"verified_users":19,"timestamp":"test"}
        self.assertEqual(dashboard.counts(data)["Provider not identified"], 1)
        self.assertIn(b"Provider not identified", dashboard.render(data))
        data["active_subscriptions"] = 4
        self.assertEqual(dashboard.counts(data)["Provider not identified"], 0)

    def test_marketing_snapshot(self):
        from marketing_view import render_marketing
        example = {"currency":"USD","start":"2026-01-01","as_of":"2026-01-02","products":{"routecast":{"spend":10,"installs":5,"purchases":None,"gross_revenue":20,"coverage":"<unsafe>"}}}
        with patch.dict("os.environ", {"DASHBOARD_MARKETING_SNAPSHOT":json.dumps(example)}):
            page = render_marketing("routecast")
            self.assertIn("$2.00",page)
            self.assertIn("$20.00",page)
            self.assertIn("saved report, not live",page)
            self.assertIn("&lt;unsafe&gt;",page)
            self.assertIn("Advertising",dashboard.render().decode())
        with patch.dict("os.environ", {"DASHBOARD_MARKETING_SNAPSHOT":"invalid"}):
            self.assertIn("snapshot unavailable",render_marketing("routecast"))

    def test_website_report(self):
        data = {"totals":{"totalUsers":"7","bounceRate":"0.25"}, "groups":{"Visitor Sources":[("search", 5)], "Recent Trends":[("20260102", 5)]}, "fetched":"test only"}
        page = dashboard.render_portfolio("patriot-news-us", data, "7")
        self.assertIn(b"25.0%", page)
        self.assertIn(b"search", page)
        self.assertIn(b"period=7", page)
        self.assertIn(b"Jan 02, 2026", page)
        self.assertEqual(page.count(b"<h2>Visitor Sources</h2>"), 1)
        self.assertNotIn(b"Visitors this month", page)
        self.assertIn(b"Additional metrics", page)

    def test_property_id(self):
        with patch.dict("os.environ", {"GA4_PATRIOT_PROPERTY_ID":"123456"}):
            self.assertEqual(property_id("patriot-news-us"), "123456")
        with patch.dict("os.environ", {"GA4_PATRIOT_PROPERTY_ID":"G-INVALID"}):
            self.assertIsNone(property_id("patriot-news-us"))

    def test_http_auth_and_assets(self):
        password = "test-only-not-production-password"
        server = ThreadingHTTPServer(("127.0.0.1",0), dashboard.handler("",password))
        thread = threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        base = "http://127.0.0.1:"+str(server.server_port)
        try:
            with self.assertRaises(HTTPError) as err:
                urlopen(base+"/",timeout=3)
            self.assertEqual(err.exception.code,401)
            with urlopen(base+"/manifest.webmanifest",timeout=3) as res:
                self.assertEqual(json.load(res)["display"],"standalone")
            auth = "Basic "+base64.b64encode(("owner:"+password).encode()).decode()
            with urlopen(Request(base+"/",headers={"Authorization":auth}),timeout=3) as res:
                self.assertIn(b"Business portfolio",res.read())
                self.assertEqual(res.headers["Cache-Control"],"no-store")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

if __name__ == "__main__":
    unittest.main()
