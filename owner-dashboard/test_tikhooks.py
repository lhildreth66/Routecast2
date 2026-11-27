import isolation
import unittest
from unittest.mock import patch
from datetime import datetime, timezone
import tikhooks_view as t
import dashboard

class TikHooksTests(unittest.TestCase):
    def data(self):
        data={k:0 for k in t.FIELDS}
        data.update(version=1,product="tikhooks2",fetched_at=datetime.now(timezone.utc).isoformat(),total_accounts=4,owner_entitlements=1,nonowner_accounts=3)
        return data
    def test_validate(self):
        self.assertEqual(t.validate(self.data())["nonowner_accounts"],3)
        with self.assertRaises(ValueError):
            t.validate(dict(self.data(),live_payment_events=-1))
        with self.assertRaises(ValueError):
            t.validate(dict(self.data(),active_nonowner_subscription_records=2))
    def test_zeros_and_no_ads(self):
        with patch.object(t,"report",return_value=(t.validate(self.data()),"")):
            page=dashboard.render_portfolio("tikhooks2").decode()
        self.assertIn("Non-owner accounts",page)
        self.assertIn("Live payment events",page)
        self.assertIn("Verified paying customer totals",page)
        self.assertNotIn("Advertising performance",page)
        self.assertIn("<strong>0</strong>",page)
    def test_funnel(self):
        with patch.object(t,"report",return_value=(None,"Unavailable")):
            page=t.render_tikhooks({"tikhooks_journey":{"checkout_started":[2,1]}})
        self.assertIn("Checkout started",page)
        self.assertIn("not a sequenced conversion funnel",page)
        self.assertIn("No customer counts assumed",page)
        self.assertIn("—",page)
    def test_not_configured(self):
        with patch.dict("os.environ",{},clear=True):
            self.assertIsNone(t.report()[0])
