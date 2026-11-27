import isolation
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock
import acquisition_view as a
import dashboard
import pwa


class AcquisitionTests(unittest.TestCase):
    def row(self, label, *values):
        return NS(dimension_values=[NS(value=label)], metric_values=[NS(value=str(v)) for v in values])

    def response(self, rows, threshold=False):
        return NS(rows=rows, metadata=NS(subject_to_thresholding=threshold))

    def test_referrers_strip_sensitive_paths(self):
        spec = a.SPECS[-1]
        r = self.response([self.row("https://example.com/private?email=person@example.com", 2),
                           self.row("https://example.com/other?token=secret", 3),
                           self.row("javascript:alert(1)", 4), self.row("", 2)])
        self.assertEqual(a.normalize(r,spec),[("example.com",[5])])

    def test_safe_labels(self):
        self.assertEqual(a.safe_label("person@example.com","sessionCampaignName"),"(redacted)")
        self.assertEqual(a.safe_label("/private/123?token=x","landingPage"),"(other or redacted path)")
        self.assertEqual(a.safe_label("/about","landingPage"),"/about")
        self.assertEqual(a.safe_label("(direct) / (none)","sessionSourceMedium"),"(direct) / (none)")

    def test_threshold_unknown(self):
        self.assertIsNone(a.normalize(self.response([],True),a.SPECS[0]))

    def test_collect_two_bounded_batches(self):
        client=Mock()
        client.batch_run_reports.side_effect=[NS(reports=[self.response([]) for _ in range(5)]),
                                               NS(reports=[self.response([]) for _ in range(2)])]
        r=a.collect(client,"12345","6daysAgo")
        self.assertEqual(set(r),{s[0] for s in a.SPECS})
        self.assertEqual(client.batch_run_reports.call_count,2)
        for call in client.batch_run_reports.call_args_list:
            self.assertLessEqual(len(call.args[0].requests),5)
            self.assertEqual(call.kwargs["timeout"],6)

    def test_batch_error_isolated(self):
        client=Mock()
        client.batch_run_reports.side_effect=[RuntimeError("private"),NS(reports=[self.response([]),self.response([])])]
        r=a.collect(client,"12345","6daysAgo")
        self.assertIsNone(r["Campaigns"])
        self.assertEqual(r["Landing pages"],[])

    def test_render_counts_and_unknown(self):
        page=a.render_acquisition({"acquisition":{"Campaigns":[("career_outreach",[4,3])],"Referring domains":[("example.com",[5])]}})
        self.assertIn("75.0%",page)
        self.assertIn("career_outreach",page)
        self.assertIn("example.com",page)
        self.assertIn("Report unavailable",page)
        self.assertIn("No raw IP",page)

    def test_generator_website_only(self):
        for site in a.SITES:
            page=dashboard.render_portfolio(site)
            self.assertIn(b"Tracking link generator",page)
            self.assertIn(b"/utm-builder.js",page)
        for site in ("routecast","endoscopy-nurse-pro","emergent-vpn","simple-background-remover"):
            page=dashboard.render() if site=="routecast" else dashboard.render_portfolio(site)
            self.assertNotIn(b"Tracking link generator",page)
        self.assertIn(b"utm_campaign",pwa.ASSETS["/utm-builder.js"][1])
        self.assertNotIn(b"fetch(",pwa.ASSETS["/utm-builder.js"][1])

if __name__=="__main__":
    unittest.main()
