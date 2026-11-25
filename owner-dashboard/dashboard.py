"""Private, read-only RouteCast subscriber dashboard.
Run python3 owner-dashboard/dashboard.py in a trusted Codespace.
Keep port 8765 PRIVATE. Enter the admin key only at the terminal prompt.
"""
import base64
import getpass
import hmac
import html
import json
import os
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import Request, urlopen

URL = "https://routecast-backend.onrender.com/api/admin/stats"

def counts(data):
    p = data["subscriptions_by_provider"]
    result = {"Apple App Store": p["apple"], "Google Play": p["google"],
              "Combined store accounts": p["apple"] + p["google"],
              "Free trials": data["trialing_users"], "Direct / Stripe": p["stripe"],
              "Manually granted": p["admin"], "All active accounts": data["active_subscriptions"],
              "Registered accounts": data["total_users"], "Verified accounts": data["verified_users"]}
    if any(type(v) is not int or v < 0 for v in result.values()):
        raise ValueError("Invalid count")
    return result

def fetch_stats(key):
    request = Request(URL, headers={"X-Admin-Key": key, "Accept": "application/json"})
    with urlopen(request, timeout=20) as response:
        return json.load(response)

def render(data=None):
    if data is None:
        body = "<p>Live data unavailable. Check your administrator key and backend, then refresh. No counts are displayed.</p>"
    else:
        body = '<div class="grid">' + "".join(f"<section><small>{html.escape(k)}</small><strong>{v:,}</strong></section>" for k,v in counts(data).items()) + "</div>"
        body += "<p>Backend snapshot: " + html.escape(str(data["timestamp"])) + "</p>"
    return f"""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>RouteCast Owner</title>
<style>body{{background:#f3f6fa;color:#16314b;font:16px system-ui;margin:0}}main{{max-width:1000px;margin:auto;padding:28px}}header{{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}}small,p{{color:#53677b}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:14px;margin:28px 0}}section{{background:white;border:1px solid #dbe4ee;border-radius:12px;padding:22px}}section:nth-child(-n+3){{border-top:4px solid #1663aa}}strong{{display:block;font-size:36px;margin-top:12px}}a{{background:#174e83;color:white;padding:12px 18px;border-radius:8px;text-decoration:none}}footer{{border-top:1px solid #dbe4ee;padding-top:15px;font-size:14px;line-height:1.6;color:#53677b}}</style>
<main><header><div><small>ROUTECAST · OWNER CONSOLE</small><h1>Subscriber dashboard</h1><p>Private · Read-only · Live backend snapshot</p></div><a href="/">Refresh data</a></header>{body}<footer>Counts are active account records in RouteCast, not independently verified paid transactions. Trials and grants are separate. Canceled-but-unexpired accounts may be omitted. Reconcile with Apple and Google for definitive paid counts. Feature analytics and suggestions are not implemented in this version.</footer></main></html>""".encode()

def handler(key, password):
    expected = ("Basic " + base64.b64encode(("owner:" + password).encode()).decode()).encode()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def reply(self, status, body, challenge=False):
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'")
            self.send_header("X-Content-Type-Options", "nosniff")
            if challenge:
                self.send_header("WWW-Authenticate", 'Basic realm="RouteCast Owner"')
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        def do_GET(self):
            if not hmac.compare_digest(self.headers.get("Authorization", "").encode(), expected):
                return self.reply(401, b"Login required", True)
            if self.path != "/":
                return self.reply(404, b"Not found")
            try:
                body = render(fetch_stats(key))
            except Exception:
                return self.reply(502, render())
            self.reply(200, body)
    return Handler

if __name__ == "__main__":
    key = os.getenv("ADMIN_API_KEY") or getpass.getpass("Production ADMIN_API_KEY: ")
    if not key.strip():
        raise SystemExit("Administrator key required")
    password = secrets.token_urlsafe(24)
    server = ThreadingHTTPServer(("127.0.0.1", 8765), handler(key, password))
    print("Port 8765: keep PRIVATE. Login: owner. Temporary password: " + password, flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()
