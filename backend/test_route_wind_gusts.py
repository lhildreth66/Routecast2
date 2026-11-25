from datetime import datetime, timezone
import unittest

from services.route_wind_gusts import (
    aware, interval, speed_mph, wind_at_eta, gust_severity,
    forecast_grid_url, sampled_distances,
)

class RouteWindGustTests(unittest.TestCase):
    def test_units(self):
        self.assertAlmostEqual(speed_mph(72.42048, "wmoUnit:km_h-1"), 45, places=3)
        self.assertAlmostEqual(speed_mph(20, "wmoUnit:m_s-1"), 44.7387, places=3)
        self.assertIsNone(speed_mph(None, "wmoUnit:km_h-1"))
        self.assertIsNone(speed_mph(45, "unknown"))
        self.assertIsNone(speed_mph(float("nan"), "wmoUnit:km_h-1"))

    def test_eta_uses_valid_forecast_interval_not_current_value(self):
        layers = {
            "windGust": {"uom": "wmoUnit:km_h-1", "values": [
                {"validTime": "2026-11-25T15:00:00+00:00/PT1H", "value": 25},
                {"validTime": "2026-11-25T16:00:00+00:00/PT2H", "value": 72.42048},
            ]},
            "windSpeed": {"uom": "wmoUnit:km_h-1", "values": [
                {"validTime": "2026-11-25T15:00:00+00:00/PT3H", "value": 28.968192},
            ]},
            "windDirection": {"values": [
                {"validTime": "2026-11-25T15:00:00+00:00/PT3H", "value": 270},
            ]},
        }
        at = wind_at_eta(layers, "2026-11-25T11:30:00-05:00")
        self.assertAlmostEqual(at["gust_mph"], 45, places=3)
        self.assertAlmostEqual(at["sustained_mph"], 18, places=3)
        self.assertEqual(at["direction_deg"], 270)
        self.assertEqual(gust_severity(at["gust_mph"]), "high")
        self.assertIsNone(wind_at_eta(layers, "2026-11-25T18:00:00Z")["gust_mph"])
        self.assertIsNone(wind_at_eta(layers, "2026-11-25T16:30:00")["gust_mph"])

    def test_missing_gust_not_estimated_from_sustained(self):
        layers = {"windSpeed": {"uom": "wmoUnit:km_h-1", "values": [
            {"validTime": "2026-11-25T15:00:00Z/PT3H", "value": 60},
        ]}}
        self.assertIsNone(wind_at_eta(layers, "2026-11-25T16:30:00Z")["gust_mph"])

    def test_thresholds(self):
        for value, expected in [(None,None), (29.9,None),(30,"medium"),(39.9,"medium"),(40,"high"),(45,"high")]:
            self.assertEqual(gust_severity(value), expected)

    def test_intervals(self):
        self.assertIsNone(interval("bad"))
        self.assertIsNone(interval("2026-11-25T15:00:00Z/PT0H"))
        self.assertIsNone(aware(datetime(2026,11,25)))
        self.assertEqual(interval("2026-11-25T15:00:00Z/P1DT2H")[1].day, 26)

    def test_url_allowlist(self):
        self.assertEqual(forecast_grid_url("https://api.weather.gov/gridpoints/CHS/10,20"), "https://api.weather.gov/gridpoints/CHS/10,20")
        self.assertIsNone(forecast_grid_url("https://example.org/gridpoints/CHS/10,20"))
        self.assertIsNone(forecast_grid_url("https://api.weather.gov@evil.example/gridpoints/CHS/10,20"))

    def test_route_distance_order(self):
        result = sampled_distances([{"lat":32,"lon":-81},{"lat":33,"lon":-81},{"lat":35,"lon":-81}], 210)
        self.assertAlmostEqual(result[0],0)
        self.assertAlmostEqual(result[1],70)
        self.assertAlmostEqual(result[-1],210)
        self.assertEqual(sampled_distances([],210),[])

if __name__ == "__main__":
    unittest.main()
