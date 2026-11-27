import unittest
from unittest.mock import patch
import endoscopy_view as v


def data():
    return {"schema": 1, "as_of": "2026-11-27T15:35:00+00:00",
            "counts": {k: 1 for k in (*v.LABELS, *v.WEEKS)},
            "modules": [{"title": "<example>", "completed_lessons": 1}]}


class EndoscopyTests(unittest.TestCase):
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
