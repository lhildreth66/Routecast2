import isolation
import unittest
from datetime import datetime, timezone
from unittest.mock import patch
import google_ads_view as ads


class AdsTests(unittest.TestCase):
    def setUp(self):
        ads.CACHE.clear()
        self.addCleanup(ads.CACHE.clear)
        self.now = datetime(2026, 11, 27, 17, tzinfo=timezone.utc)

    def query(self, q):
        if "FROM customer" in q:
            return [{"customer":{"id":ads.ACCOUNT,"currencyCode":"USD","timeZone":"America/New_York"}}]
        if "FROM conversion_action" in q:
            return [{"conversionAction":{"id":i,"status":"ENABLED","type":t}}
                    for _, install, purchase in ads.PRODUCTS.values()
                    for i,t in [(install,"GOOGLE_PLAY_DOWNLOAD"),(purchase,"GOOGLE_PLAY_IN_APP_PURCHASE")]]
        row = lambda app, m, **seg: {"campaign":{"appCampaignSetting":{"appId":app}},
                                     "segments":{"date":"2026-11-27",**seg},"metrics":m}
        if "metrics.cost_micros" in q:
            return [row("com.endoscopynursepro.app",{"costMicros":"5000000","impressions":"100","clicks":"10"}),
                    row("com.routecast.app",{"costMicros":"99000000"})]
        return [row("com.endoscopynursepro.app",{"allConversions":4},conversionAction="customers/4858810197/conversionActions/7658461636"),
                row("com.endoscopynursepro.app",{"allConversions":1,"allConversionsValue":12},conversionAction="customers/4858810197/conversionActions/7919001775"),
                row("com.endoscopynursepro.app",{"allConversions":99},conversionAction="customers/4858810197/conversionActions/7609511939")]

    def test_aggregation(self):
        result = ads.retrieve(self.query, ads.ACCOUNT, self.now)
        self.assertEqual(result["start"],"2026-10-29")
        t = ads.totals(list(result["products"]["endoscopy-nurse-pro"].values()))
        self.assertEqual(t,{"spend":5,"impressions":100,"clicks":10,"installs":4,"purchases":1,"value":12})
        self.assertEqual(ads.totals(list(result["products"]["routecast"].values()))["spend"],99)

    def test_missing_actions_unknown_not_zero(self):
        result = ads.retrieve(lambda q: [] if "FROM conversion_action" in q else self.query(q), ads.ACCOUNT, self.now)
        t = ads.totals(list(result["products"]["endoscopy-nurse-pro"].values()))
        self.assertIsNone(t["purchases"])
        self.assertIsNone(t["installs"])
        self.assertEqual(t["spend"],5)

    def test_cache_and_render(self):
        result = ads.retrieve(self.query, ads.ACCOUNT, self.now)
        with patch.dict("os.environ", {"GOOGLE_ADS_CUSTOMER_ID":ads.ACCOUNT}), patch.object(ads,"fetch",return_value=result) as fetch:
            page = ads.render_ads("endoscopy-nurse-pro")
            self.assertIn("$5.00",page)
            self.assertIn("$1.25",page)
            self.assertIn("2.40x",page)
            self.assertIn("not unique paying subscribers",page)
            self.assertIn("Today (partial)",page)
            self.assertNotIn("$99.00",page)
            self.assertIn("$99.00",ads.render_ads("routecast"))
            self.assertEqual(fetch.call_count,1)
            self.assertEqual(ads.render_ads("patriot-news-us"),"")

    def test_failure_sanitized_and_cached(self):
        with patch.dict("os.environ",{"GOOGLE_ADS_CUSTOMER_ID":ads.ACCOUNT}), patch.object(ads,"fetch",side_effect=RuntimeError("secret")) as fetch:
            page = ads.render_ads("endoscopy-nurse-pro")
            self.assertIn("No live figures assumed",page)
            self.assertNotIn("secret",page)
            self.assertNotIn("$0.00",page)
            ads.render_ads("routecast")
            self.assertEqual(fetch.call_count,1)

    def test_disabled(self):
        with patch.dict("os.environ",{},clear=True), patch.object(ads,"fetch") as fetch:
            self.assertEqual(ads.render_ads("endoscopy-nurse-pro"),"")
            fetch.assert_not_called()

    def test_account_mismatch(self):
        with patch.dict("os.environ",{"GOOGLE_ADS_CUSTOMER_ID":"1234567890"}), patch.object(ads,"fetch") as fetch:
            self.assertIn("does not match",ads.render_ads("routecast"))
            fetch.assert_not_called()
