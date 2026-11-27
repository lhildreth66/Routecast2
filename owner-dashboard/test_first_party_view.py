import isolation
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
import first_party_view as fp
import dashboard

class FirstPartyTests(unittest.TestCase):
    def setUp(self):
        fp.CACHE.clear()
        self.addCleanup(fp.CACHE.clear)

    def test_window(self):
        now=datetime(2026,11,27,15,tzinfo=timezone.utc)
        self.assertEqual(fp.window("today",now)[0].hour,0)
        self.assertEqual(fp.window("7",now)[0].day,21)
        self.assertEqual(fp.window("90",now),fp.window("30",now))

    def test_roles(self):
        fp.verify_roles({"authInfo":{"authenticatedUsers":[{"user":"reader"}],
                        "authenticatedUserRoles":[{"role":"read","db":fp.DATABASE}]}})
        with self.assertRaises(ValueError):
            fp.verify_roles({"authInfo":{"authenticatedUsers":[{}],
                         "authenticatedUserRoles":[{"role":"readWrite","db":fp.DATABASE}]}})

    def test_aggregate_only(self):
        c=MagicMock()
        s={"count":[{"count":2}],"sources":[]}
        e={"kinds":[]}
        c.aggregate.side_effect=[MagicMock(),MagicMock()]
        c.aggregate.side_effect[0] if False else None
        a,b=MagicMock(),MagicMock()
        a.__enter__.return_value=iter([s])
        b.__enter__.return_value=iter([e])
        c.aggregate.side_effect=[a,b]
        now=datetime.now(timezone.utc)
        d=fp.query_snapshot(c,now,now)
        self.assertEqual(d["sessions"],s)
        self.assertEqual(c.aggregate.call_count,2)
        for call in c.aggregate.call_args_list:
            self.assertEqual(call.kwargs["maxTimeMS"],3000)
            self.assertNotIn("$out",str(call.args))
            self.assertNotIn("$merge",str(call.args))
        c.insert_one.assert_not_called()

    def test_render_and_failure(self):
        data={"start":"start","fetched":"now","sessions":{"count":[{"count":2}],
              "sources":[{"_id":{"source":"<unsafe>","medium":"email"},"count":2}],
              **{key:[] for key in ("campaigns","referrers","landing","devices","browsers","systems")}},
              "events":{"kinds":[{"_id":"page_view","count":4}],"time":[],
              **{key:[] for key in ("pages","products","daily")}}}
        with patch.dict("os.environ",{fp.ENV:"mongodb://example.invalid"}),patch.object(fp,"read_snapshot",return_value=data) as read:
            page=fp.render_first_party(fp.PRODUCT,"7")
            self.assertIn("Observed sessions",page)
            self.assertIn("&lt;unsafe&gt;",page)
            self.assertNotIn("<unsafe>",page)
            self.assertIn("IP security-log reporting is not connected",page)
            fp.render_first_party(fp.PRODUCT,"7")
            read.assert_called_once()
            self.assertEqual(fp.render_first_party("routecast","7"),"")
        fp.CACHE.clear()
        with patch.dict("os.environ",{fp.ENV:"mongodb://example.invalid"}),patch.object(fp,"read_snapshot",side_effect=RuntimeError("secret")) as read:
            page=fp.render_first_party(fp.PRODUCT,"7")
            self.assertIn("unavailable",page)
            self.assertNotIn("secret",page)
            fp.render_first_party(fp.PRODUCT,"7")
            read.assert_called_once()

    def test_corporate_only(self):
        self.assertIn(b"Hildreth first-party analytics",dashboard.render_portfolio(fp.PRODUCT))
        self.assertNotIn(b"Hildreth first-party analytics",dashboard.render_portfolio("patriot-news-us"))
