import isolation
import unittest
from unittest.mock import patch
from time import monotonic
import dashboard
import portfolio_view as p
from traffic_trend import render_trend

class PortfolioDesignTests(unittest.TestCase):
    def test_overview(self):
        with patch.object(p,"snapshot",return_value=([],[])):
            result=dashboard.render_portfolio().decode()
        self.assertEqual(result.count('class="portfolio-card"'),8)
        self.assertIn("Mobile applications",result)
        self.assertIn("Websites &amp; SaaS".replace("&amp;","&"),result)
        self.assertNotIn("Subscriber API prepared",result)
        self.assertNotIn("Portfolio totals",result)
        for key in dashboard.APPS:
            self.assertIn(f'href="/apps/{key}"',result)
    def test_config_and_cache(self):
        with patch.dict("os.environ",{"GA4_HILDRETH_PROPERTY_ID":"12345"},clear=True),patch.object(p.ga4,"CACHE",{("hildreth-technology","12345","30"):(monotonic(),{"totals":{"totalUsers":"12","sessions":"13"}})}):
            metrics,sources=p.snapshot("hildreth-technology")
            self.assertEqual(metrics,[("Visitors · 30 days","12"),("Sessions · 30 days","13")])
            self.assertEqual(sources,["Google Analytics"])
        with patch.dict("os.environ",{},clear=True):
            self.assertEqual(p.snapshot("hildreth-technology"),([],[]))
    def test_no_network(self):
        with patch.object(p.ga4,"report",side_effect=AssertionError("no fetch")),patch.object(p.rc,"fetch_overview",side_effect=AssertionError("no fetch")),patch.object(p.endo,"fetch",side_effect=AssertionError("no fetch")):
            self.assertIn(b"Business portfolio",dashboard.render_portfolio())
    def test_trend(self):
        page=render_trend([("20261118",6),("20261119",7),("20261121",6)])
        self.assertIn("19</div>",page)
        self.assertIn("Nov 19: ",page.replace(", 2026",""))
        self.assertIn("View daily numbers",page)
        self.assertIn("Missing days are not reported",page)
        self.assertNotIn("Nov 20, 2026",page)
        self.assertIn("unavailable",render_trend(None))
        self.assertIn("does not establish zero",render_trend([]))
