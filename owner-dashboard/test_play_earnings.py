"""Offline list-and-download workflow tests. All names, rows and errors are synthetic."""
import io
import sys
import types
import unittest
import zipfile
from unittest.mock import patch

import play_earnings as pe

URI = "gs://pubsite_prod_000/earnings/"
HEADER = "Package ID,Transaction Type,Merchant Currency,Amount (Merchant Currency)\n"
SECRET = "reader@example-project.iam.gserviceaccount.com"

def archive(content=HEADER + "com.routecast.app,Charge,USD,10\n"):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as z:
        z.writestr("earnings.csv", content)
    return output.getvalue()

class Response:
    def __init__(self, status=200, data=None, content=b"", text=""):
        self.status_code, self.data, self.content, self.text = status, data, content, text
    def json(self):
        if self.data is None:
            raise ValueError("not JSON")
        return self.data
    def iter_content(self, chunk_size):
        for i in range(0, len(self.content), chunk_size):
            yield self.content[i:i + chunk_size]
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False

def denied(permission):
    message = SECRET + " does not have " + permission + " access to the object."
    return Response(403, {"error": {"message": message, "errors": [{"reason": "forbidden", "message": message}]}})

def listing(*names, token=None):
    data = {"items": [{"name": n, "size": "100"} for n in names]}
    if token:
        data["nextPageToken"] = token
    return Response(data=data)

class WorkflowTests(unittest.TestCase):
    def setUp(self):
        for cache in (pe.CACHE, pe.FAILURES):
            cache.clear()
            self.addCleanup(cache.clear)
        self.responses, self.calls, self.scopes, self.auth_error = [], [], [], None
        test = self

        class Session:
            def __init__(self, credentials):
                pass
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def get(self, url, params=None, **kwargs):
                test.calls.append((url, dict(params or {})))
                item = test.responses.pop(0)
                if isinstance(item, Exception):
                    raise item
                return item

        def default(scopes):
            if test.auth_error:
                raise test.auth_error
            test.scopes.append(scopes)
            return object(), None

        # CI does not install requirements, so stand in for the Google modules.
        modules = {n: types.ModuleType(n) for n in
                   ("google", "google.auth", "google.auth.transport", "google.auth.transport.requests")}
        modules["google"].auth = modules["google.auth"]
        modules["google.auth"].default = default
        modules["google.auth"].transport = modules["google.auth.transport"]
        modules["google.auth.transport"].requests = modules["google.auth.transport.requests"]
        modules["google.auth.transport.requests"].AuthorizedSession = Session
        for patcher in (patch.dict(sys.modules, modules),
                        patch.dict("os.environ", {"PLAY_EARNINGS_URI": URI}),
                        patch.object(pe, "previous_month_report", return_value="earnings/earnings_202602.zip")):
            patcher.start()
            self.addCleanup(patcher.stop)

    def failure(self, *responses):
        self.responses = list(responses)
        with self.assertRaises(pe.ReportError) as caught:
            pe.report()
        message = str(caught.exception)
        self.assertNotIn(SECRET, message)
        return message

    def test_lists_all_pages_and_downloads_newest(self):
        self.responses = [listing("earnings/earnings_202601.zip", token="next"),
                          listing("earnings/earnings_202602.zip"), Response(content=archive())]
        data = pe.report()
        self.assertEqual(data["month"], "February 2026")
        self.assertIsNone(data["warning"])
        self.assertIn("com.routecast.app", data["totals"])
        self.assertEqual(self.scopes, [["https://www.googleapis.com/auth/devstorage.read_only"]])
        self.assertTrue(self.calls[0][0].endswith("/b/pubsite_prod_000/o"))
        self.assertEqual(self.calls[1][1]["pageToken"], "next")
        self.assertTrue(self.calls[2][0].endswith("/o/earnings%2Fearnings_202602.zip"))
        self.assertEqual(self.calls[2][1], {"alt": "media"})

    def test_success_is_cached(self):
        self.responses = [listing("earnings/earnings_202602.zip"), Response(content=archive())]
        self.assertIs(pe.report(), pe.report())
        self.assertEqual(len(self.calls), 2)

    def test_both_403s_are_reported(self):
        message = self.failure(denied("storage.objects.list"), denied("storage.objects.get"))
        self.assertIn("HTTP 403 during report listing (permission denied; missing storage.objects.list)", message)
        self.assertIn("HTTP 403 during monthly file download (permission denied; missing storage.objects.get)", message)

    def test_listing_403_with_working_direct_read_warns(self):
        self.responses = [denied("storage.objects.list"), Response(content=archive())]
        self.assertIn("storage.objects.list", pe.report()["warning"])
        page = pe.render_play("routecast")
        self.assertIn("could not be checked", page)
        self.assertNotIn(SECRET, page)

    def test_listing_403_then_404(self):
        message = self.failure(denied("storage.objects.list"), Response(404, text="No such object"))
        self.assertIn("during report listing", message)
        self.assertIn("HTTP 404 during monthly file download", message)

    def test_listing_403_then_network_error_keeps_both(self):
        message = self.failure(denied("storage.objects.list"), OSError(SECRET))
        self.assertIn("missing storage.objects.list", message)
        self.assertIn("failed during monthly file download", message)

    def test_download_403_after_successful_listing(self):
        message = self.failure(listing("earnings/earnings_202602.zip"), denied("storage.objects.get"))
        self.assertNotIn("report listing", message)
        self.assertIn("missing storage.objects.get", message)

    def test_plain_text_403(self):
        text = SECRET + " does not have storage.objects.get access."
        message = self.failure(listing("earnings/earnings_202602.zip"), Response(403, text=text))
        self.assertIn("missing storage.objects.get", message)

    def test_api_disabled(self):
        body = {"error": {"errors": [{"reason": "accessNotConfigured"}]}}
        message = self.failure(Response(403, body), Response(403, body))
        self.assertEqual(message.count("Cloud Storage API disabled"), 2)

    def test_unrecognised_reason(self):
        message = self.failure(Response(403, text=SECRET), Response(403, text=SECRET))
        self.assertIn("no recognised reason", message)

    def test_failure_is_cached_then_retried(self):
        with patch.object(pe, "monotonic", return_value=1000):
            first = self.failure(denied("storage.objects.list"), denied("storage.objects.get"))
        with patch.object(pe, "monotonic", return_value=1299):
            self.assertEqual(self.failure(), first)
        self.assertEqual(len(self.calls), 2)
        self.responses = [listing("earnings/earnings_202602.zip"), Response(content=archive())]
        with patch.object(pe, "monotonic", return_value=1300):
            self.assertIsNone(pe.report()["warning"])
        self.assertEqual(len(self.calls), 4)
        self.assertEqual(pe.FAILURES, {})

    def test_credential_failure_is_cached(self):
        self.auth_error = RuntimeError(SECRET)
        first = self.failure()
        self.auth_error = None
        self.assertEqual(self.failure(), first)
        self.assertEqual(self.calls, [])

    def test_listing_server_error_does_not_download(self):
        self.assertIn("HTTP 500 during report listing", self.failure(Response(500)))
        self.assertEqual(len(self.calls), 1)

    def test_no_matching_filename(self):
        self.assertIn("no filename matched", self.failure(listing("earnings/other.txt")))

    def test_credential_failure(self):
        self.auth_error = RuntimeError(SECRET)
        self.assertIn("while loading Google credentials", self.failure())

    def test_unreadable_reports(self):
        for content in (b"not a zip", archive("Wrong,Columns\n1,2\n")):
            pe.FAILURES.clear()
            message = self.failure(listing("earnings/earnings_202602.zip"), Response(content=content))
            self.assertIn("while reading the downloaded report", message)

    def test_download_size_limit(self):
        with patch.object(pe, "LIMIT", 120):
            message = self.failure(listing("earnings/earnings_202602.zip"), Response(content=b"x" * 121))
        self.assertIn("size limit", message)

    def test_error_is_shown_on_page(self):
        self.responses = [denied("storage.objects.list"), denied("storage.objects.get")]
        page = pe.render_play("routecast")
        self.assertIn("missing storage.objects.list", page)
        self.assertNotIn(SECRET, page)

    def test_invalid_uri_makes_no_request(self):
        with patch.dict("os.environ", {"PLAY_EARNINGS_URI": "https://example.invalid"}):
            self.assertIn("Invalid earnings storage URI", self.failure())
        self.assertEqual(self.calls, [])

if __name__ == "__main__":
    unittest.main()
