import isolation  # noqa: F401  (clears credentials, blocks external network; keep first)
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

    def test_revenuecat_overview(self):
        from io import BytesIO
        import revenuecat_view as rc
        data = {"currency":"USD","metrics":[{"id":"active_subscriptions","value":3,"period":"P0D"},{"id":"revenue","value":12.5,"period":"P28D"},{"id":"ignored","value":999}]}
        rc.CACHE.clear()
        try:
            with patch.dict("os.environ", {"RC_EMERGENT_PROJECT_ID":"projtest","RC_EMERGENT_API_KEY":"sk_test_only"}):
                with patch.object(rc, "urlopen", return_value=BytesIO(json.dumps(data).encode())) as fetch:
                    page = dashboard.render_portfolio("emergent-vpn")
                    self.assertIn(b"Active paid subscriptions",page)
                    self.assertIn(b"$12.50",page)
                    self.assertIn(b"Last 28 days",page)
                    self.assertNotIn(b"sk_test_only",page)
                    self.assertNotIn(b"<strong>999</strong>",page)  # Do not match unrelated timestamp digits.
                    self.assertEqual(fetch.call_args.args[0].get_method(),"GET")
                    self.assertIn("/v2/projects/projtest/metrics/overview",fetch.call_args.args[0].full_url)
                    rc.render_revenuecat("emergent-vpn")
                    self.assertEqual(fetch.call_count,1)
        finally:
            rc.CACHE.clear()

    def test_revenuecat_error_diagnostics(self):
        from urllib.error import HTTPError
        import revenuecat_view as rc
        with patch.object(rc, "fetch_overview", side_effect=HTTPError("https://example.invalid",403,"private response",None,None)):
            result = rc.render_revenuecat("emergent-vpn")
            self.assertIn("HTTP 403", result)
            self.assertIn("Overview metrics read", result)
            self.assertNotIn("private response", result)
        with patch.object(rc, "fetch_overview", side_effect=ValueError("secret-example")):
            self.assertNotIn("secret-example", rc.render_revenuecat("emergent-vpn"))

    def test_play_earnings_diagnostics(self):
        from unittest.mock import Mock
        from play_earnings import check_response, previous_month_report, ReportError
        response = Mock(status_code=403)
        response.json.return_value = {"error":{"details":[{"reason":"SERVICE_DISABLED"}]}}
        with self.assertRaisesRegex(ReportError, "Cloud Storage API disabled"):
            check_response(response, "monthly file download")
        self.assertRegex(previous_month_report(), r"^earnings/earnings_[0-9]{6}\.zip$")

    def test_play_earnings_aggregation(self):
        from io import BytesIO
        import zipfile
        from decimal import Decimal
        from play_earnings import parse_earnings
        output = BytesIO()
        content = ("Package ID,Transaction Type,Merchant Currency,Amount (Merchant Currency)\n"
                   "com.routecast.app,Charge,USD,10\n"
                   "com.routecast.app,Charge refund,USD,-2\n"
                   "com.routecast.app,Google fee,USD,-1.2\n"
                   "com.emergentvpn,Charge,USD,5\n"
                   "other.app,Charge,USD,99\n")
        with zipfile.ZipFile(output,"w") as z:
            z.writestr("earnings.csv",content)
        data = parse_earnings(output.getvalue())
        self.assertEqual(data["com.routecast.app"]["USD"]["sales"],Decimal("8"))
        self.assertEqual(data["com.routecast.app"]["USD"]["fees"],Decimal("-1.2"))
        self.assertEqual(data["com.routecast.app"]["USD"]["total"],Decimal("6.8"))
        self.assertNotIn("other.app",data)
        self.assertEqual(data["com.emergentvpn"]["USD"]["total"],Decimal("5"))

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
