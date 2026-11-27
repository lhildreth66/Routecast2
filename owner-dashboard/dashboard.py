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
from urllib.parse import urlsplit, parse_qs
from ga4_reports import report as ga4_report, PERIODS
from web_view import render_web
from marketing_view import render_marketing
from revenuecat_view import render_revenuecat
from play_earnings import render_play
from endoscopy_view import render_endoscopy
from pwa import ASSETS, HEAD
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import Request, urlopen

URL = "https://routecast-backend.onrender.com/api/admin/stats"

# Product inventory from the public Hildreth Technologies portfolio.
# Website status is not a confirmation of App Store / Google Play availability.
APPS = {
    "hildreth-technology": ("HildrethTechnology.com", "Live", "Corporate website"),
    "routecast": ("RouteCast", "Live", "Travel & weather"),
    "emergent-vpn": ("Emergent VPN", "Live", "Privacy & networking"),
    "medpolicyref": ("MedPolicyRef", "Live", "Medical policy SaaS"),
    "endoscopy-nurse-pro": ("Endoscopy Nurse Pro", "Live", "Nursing education"),
    "patriot-news-us": ("Patriot News US", "Live", "Digital publishing"),
    "tikhooks2": ("TikHooks2", "Live", "Creator tools"),
    "simple-background-remover": ("Simple Background Remover", "In testing", "Photo utility"),
}


# Owner-confirmed product types; store publication status still requires verification.
PRODUCT_TYPES = {
    "hildreth-technology": "Website",
    "routecast": "Mobile app",
    "emergent-vpn": "Mobile app",
    "endoscopy-nurse-pro": "Mobile app",
    "simple-background-remover": "Mobile app (testing)",
    "medpolicyref": "Website",
    "patriot-news-us": "Website",
    "tikhooks2": "Website",
}

def product_metrics(key):
    if PRODUCT_TYPES[key] == "Website":
        traffic = ("Visitors this month", "Sessions this month", "Page views", "Average engaged time", "Bounce rate", "Returning visitors")
        if key == "hildreth-technology":
            return traffic + ("Contact submissions", "Product link clicks", "Contact completion rate")
        return traffic + ("Paying subscribers", "Active accounts", "New registrations", "Signup completion rate", "Revenue")
    return ("Apple subscribers", "Google Play subscribers", "Direct subscriptions", "Trials", "Active accounts", "Revenue")

def product_panels(key):
    if PRODUCT_TYPES[key] == "Website":
        panels = [
            ("Visitor Sources", "Traffic by referring domain, direct, organic search, social, referral and campaign. Direct includes unknown sources."),
            ("Visitor Geography", "Approximate country and region totals only; no precise coordinates."),
            ("Most Visited Pages", "Page views, engaged time, entries and exits by normalized page path."),
            ("Engagement & Bounce", "Session and engagement trends, landing-page bounce rates, device and browser categories."),
            ("Conversion Funnel", "Visit, product or contact click, contact form start and submission." if key == "hildreth-technology" else "Visit, signup start, validation, registration, verification and purchase where applicable."),
            ("Errors & Drop-off Signals", "Allowlisted error codes, form step failures, slow requests and failed submissions. These are diagnostic clues, not proof of why a visitor left."),
            ("Recent Customer Suggestions", "Feedback integration pending."),
            ("Recent Trends", "Daily, weekly and monthly comparisons need first-party event collection."),
        ]
        if key == "hildreth-technology":
            panels.append(("Product Referrals", "Outbound clicks to each portfolio product and app-store listing, with conversion attribution only where supported."))
        return panels
    return [
        ("Subscriber Sources", "Store availability and account data need verification."),
        ("Most Used Features", "First-party product analytics not connected."),
        ("Recent Customer Suggestions", "Feedback integration pending."),
        ("Recent Trends", "Historical data and reporting not connected."),
    ]

def navigation(selected):
    entries = [("portfolio", "All products", "/")] + [(k, v[0], "/apps/" + k) for kind in ("Mobile app", "Website", "Mobile app (testing)") for k, v in APPS.items() if PRODUCT_TYPES[k] == kind]
    return "".join(
        f'<a href="{href}"' + (' class="selected" aria-current="page"' if key == selected else '') +
        f'>{html.escape(name)}</a>' for key, name, href in entries
    )

def counts(data):
    p = data["subscriptions_by_provider"]
    result = {"Apple App Store": p["apple"], "Google Play": p["google"],
              "Combined store accounts": p["apple"] + p["google"],
              "Free trials": data["trialing_users"], "Direct / Stripe": p["stripe"],
              "Manually granted": p["admin"], "All active accounts": data["active_subscriptions"],
              "Registered accounts": data["total_users"], "Verified accounts": data["verified_users"]}
    if any(type(v) is not int or v < 0 for v in result.values()):
        raise ValueError("Invalid count")
    result["Provider not identified"] = max(0, result["All active accounts"] - sum(p[k] for k in ("apple", "google", "stripe", "admin")))
    return result

def fetch_stats(key):
    request = Request(URL, headers={"X-Admin-Key": key, "Accept": "application/json"})
    with urlopen(request, timeout=20) as response:
        return json.load(response)

def render(data=None, selected='routecast', include_reports=True):
    metrics = counts(data) if data is not None else {}
    def tile(label, description, accent=False):
        value = f"{metrics[label]:,}" if label in metrics else "—"
        return f'<section class="tile {"accent" if accent else ""}"><small>{html.escape(label)}</small><strong>{value}</strong><span>{html.escape(description)}</span></section>'
    cards = "".join([
        tile("Apple App Store", "Active Apple accounts"),
        tile("Google Play", "Active Google accounts"),
        tile("Combined store accounts", "Active records; payment not verified", True),
        tile("Free trials", "Trialing accounts"),
        tile("Direct / Stripe", "Active direct accounts"),
        tile("All active accounts", "All providers"),
    ])
    labels = ["Apple App Store", "Google Play", "Direct / Stripe", "Manually granted", "Provider not identified"]
    colors = ["#1561d8", "#3aa7eb", "#8456d9", "#a5afbd", "#d97706"]
    total = sum(metrics.get(k, 0) for k in labels)
    legend = ""
    stops = []
    pos = 0
    for label, color in zip(labels, colors):
        v = metrics.get(label, 0)
        share = 100 * v / total if total else 0
        end = pos + share
        if share:
            stops.append(f"{color} {pos:.8f}% {end:.8f}%")
        pos = end
        detail = f"{v:,} · {share:.1f}%" if data is not None else "—"
        legend += f'<div class="legend-row"><i style="background:{color}"></i><span>{label}</span><b>{detail}</b></div>'
    ring = "conic-gradient(" + ", ".join(stops) + ")" if len(stops) > 1 else (stops[0].split()[0] if stops else "#e4ebf3")
    total_display = f"{total:,}" if data is not None else "—"
    stamp = html.escape(str(data["timestamp"])) if data is not None else "Unavailable — refresh after checking backend access"
    state = "Live backend snapshot" if data is not None else "Live data unavailable"
    extra = "".join(tile(k, d) for k,d in [("Registered accounts","All registrations"),("Verified accounts","Verified email"),("Manually granted","Complimentary / admin"),("Provider not identified","Difference from listed providers")])
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>RouteCast Owner Dashboard</title>{HEAD}
<style>
*{{box-sizing:border-box}}html{{scroll-behavior:smooth}}body{{margin:0;background:#f3f6fb;color:#12243e;font:15px system-ui,sans-serif}}.layout{{display:grid;grid-template-columns:220px minmax(0,1fr);min-height:100vh}}aside{{background:linear-gradient(170deg,#102b4e,#0c1e36);color:#fff;padding:26px 16px;border-right:1px solid #dce6f3}}.brand{{font-size:26px;font-weight:850;letter-spacing:-1px;margin:0 0 32px 10px}}.brand span{{color:#62c6ef}}nav{{display:grid;gap:6px}}nav a{{color:#e9f1ff;text-decoration:none;padding:12px;border-radius:9px;font-weight:600}}nav a.selected{{background:#1668dc;color:white}}nav a:hover{{background:#dceaff;color:#124eaa}}main{{padding:28px;max-width:1540px;width:100%;margin:auto;align-self:start}}header{{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px;margin-bottom:22px}}h1{{font-size:clamp(24px,3vw,36px);letter-spacing:-.8px;margin:0}}h2{{font-size:19px;margin:0 0 18px}}p{{color:#53677b;line-height:1.55}}header p{{margin:5px 0 0}}.refresh{{background:#1668dc;color:white;padding:11px 16px;border-radius:9px;text-decoration:none;font-weight:650}}.kpis{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin-bottom:18px}}.tile,.panel{{background:white;border:1px solid #dce4ef;border-radius:12px;box-shadow:0 3px 10px #142d4d09;padding:19px;min-width:0}}.tile.accent{{background:#eaf2ff;border-color:#b7d3fa}}.tile h2{{overflow-wrap:anywhere}}.tile small{{color:#31465e;font-weight:650;font-size:13px}}.tile strong{{display:block;font-size:clamp(25px,3vw,34px);margin:8px 0;letter-spacing:-.5px;font-variant-numeric:tabular-nums}}.tile span{{font-size:12px;color:#61748b}}.columns{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px}}.chart{{display:flex;align-items:center;flex-wrap:wrap;gap:20px}}.ring{{width:160px;height:160px;border-radius:50%;display:grid;place-items:center;flex:none}}.ring-inner{{width:106px;height:106px;border-radius:50%;background:#fff;display:grid;align-content:center;text-align:center;font-size:12px;color:#61748b}}.ring-inner b{{font-size:24px;color:#12243e}}.legend{{flex:1;min-width:190px}}.legend-row{{display:flex;gap:8px;align-items:center;padding:12px 0;border-bottom:1px solid #edf1f6;font-size:12px}}.legend-row i{{width:10px;height:10px;border-radius:50%;flex:none}}.legend-row b{{margin-left:auto;white-space:nowrap}}.pending{{border:1px dashed #c9d8eb;border-radius:9px;padding:18px;background:#f8fafd;color:#52677c;line-height:1.6}}.status{{font-size:12px;letter-spacing:.03em;font-weight:650;color:#436688}}footer{{font-size:12px;color:#64758a;line-height:1.65;margin-top:18px}}@media(min-width:1500px){{.kpis{{grid-template-columns:repeat(6,minmax(0,1fr))}}}}@media(max-width:960px){{.layout{{grid-template-columns:1fr}}aside{{border-right:0;border-bottom:1px solid #dce6f3;padding:14px 18px}}.brand{{margin:0 0 8px}}nav{{display:flex;overflow:auto}}nav a{{white-space:nowrap}}main{{padding:18px}}}}@media(max-width:600px){{.columns{{grid-template-columns:1fr}}.kpis{{grid-template-columns:repeat(2,minmax(0,1fr))}}.tile,.panel{{padding:14px}}}}
</style></head><body><div class="layout"><aside><div class="brand" style="font-size:20px">Hildreth<br><span>Technologies</span></div><nav>{navigation(selected)}</nav><hr style="border:0;border-top:1px solid #dce6f3;margin:20px 0"><nav><a href="#overview">Overview</a><a href="#subscribers">Subscribers</a><a href="#usage">Usage</a><a href="#suggestions">Suggestions</a><a href="#trends">Trends</a><a href="#marketing">Advertising</a></nav></aside><main id="overview"><header><div><h1>RouteCast Owner Dashboard</h1><p>Private analytics and customer insights · <span class="status">{state}</span></p></div><a class="refresh" href="/apps/routecast">Refresh data</a></header><div class="kpis">{cards}</div><div class="columns"><section class="panel" id="subscribers"><h2>Subscriber Sources</h2><div class="chart"><div class="ring" style="background:{ring}"><div class="ring-inner"><b>{total_display}</b>Active account<br>breakdown</div></div><div class="legend">{legend}</div></div></section><section class="panel" id="usage"><h2>Most Used Features</h2><div class="pending">Feature tracking is not connected yet. Rankings will appear here once RouteCast starts receiving verified usage events. No example numbers are shown.</div></section></div><div class="columns"><section class="panel" id="suggestions"><h2>Recent Customer Suggestions</h2><div class="pending">The in-app suggestion form and private feedback inbox are planned. No customer suggestions have been collected through this dashboard yet.</div></section><section class="panel" id="trends"><h2>Recent Trends</h2><div class="pending">Historical subscriber growth, conversions, cancellations and app opens require event collection and reconciled subscription history.</div></section></div><div class="kpis">{extra}</div><div id="marketing">{render_marketing("routecast") if include_reports else ""}{render_play("routecast") if include_reports else ""}</div><footer>Backend snapshot: {stamp}<br>Counts reflect active account records in RouteCast, not independently verified paid transactions. Provider not identified is the positive difference between all active accounts and the four listed provider counts; independent database count queries can also differ during concurrent updates. Trials and grants are separate. Canceled-but-unexpired accounts may be omitted. Reconcile with Apple and Google before treating these as definitive paid counts.</footer></main></div></body></html>""".encode()

def render_portfolio(selected="portfolio", web_data=None, period="30", web_error=False):
    # Reuse the approved dashboard stylesheet, not its data or panels.
    css = render(include_reports=False).decode("utf-8").split("<style>", 1)[1].split("</style>", 1)[0]
    if selected == "portfolio":
        title = "Business portfolio"
        subtitle = "All products · private analytics and customer insights"
        cards = "".join(
            f'<section class="tile"><small>{html.escape(PRODUCT_TYPES[key])} · {html.escape(status)} · {html.escape(category)}</small>'
            f'<h2 style="margin:12px 0">{html.escape(name)}</h2>'
            f'<p>{"Subscriber API prepared; live verification pending." if key == "routecast" else "Data source not connected yet."}</p>'
            f'<a class="refresh" style="display:inline-block" href="/apps/{key}">Open dashboard</a></section>'
            for key, (name, status, category) in APPS.items()
        )
        body = '<section class="panel" style="margin-bottom:18px"><h2>Portfolio totals</h2><div class="pending">Combined subscriber, revenue and usage totals are unavailable until all applicable sources are connected and verified. No estimated counts are shown.</div></section><div class="kpis">' + cards + '</div>'
    else:
        name, status, category = APPS[selected]
        title = name + " Owner Dashboard"
        subtitle = PRODUCT_TYPES[selected] + " · " + status + " · " + category
        metrics = product_metrics(selected)
        panel_items = product_panels(selected)
        if selected == "endoscopy-nurse-pro":
            metrics = [m for m in metrics if m not in ("Apple subscribers", "Google Play subscribers", "Active accounts")]
            panel_items = [(label, detail) for label, detail in panel_items
                           if label not in ("Subscriber Sources", "Most Used Features")]
            panel_items = [(label, "Historical subscriptions and cancellation reporting not connected.")
                           if label == "Recent Trends" else (label, detail) for label, detail in panel_items]
        if PRODUCT_TYPES[selected] == "Website" and web_data is not None:
            # Live GA4 report above owns these metrics; do not render duplicate placeholders.
            metrics = [m for m in metrics if m not in ("Visitors this month", "Sessions this month", "Page views", "Bounce rate")]
            panel_items = [(label, detail) for label, detail in panel_items if label not in ("Visitor Sources", "Visitor Geography", "Most Visited Pages", "Recent Trends")]
            panel_items = [("Detailed engagement", "Landing-page engagement and browser breakdown are not connected.") if label == "Engagement & Bounce" else (label, detail) for label, detail in panel_items]
        cards = "".join(
            f'<section class="tile"><small>{html.escape(label)}</small><strong>—</strong><span>Not connected</span></section>'
            for label in metrics
        )
        panels = "".join(
            f'<section class="panel"><h2>{html.escape(label)}</h2><div class="pending">{html.escape(detail)}</div></section>'
            for label, detail in panel_items
        )
        body = '<div class="kpis">' + cards + '</div><div class="columns">' + panels + '</div>'
        if PRODUCT_TYPES[selected] == "Website" and web_data is not None:
            body = '<h2>Additional metrics — connection pending</h2>' + body
    if selected != "portfolio" and PRODUCT_TYPES[selected] == "Website":
        body = render_web(selected, web_data, period, web_error) + body
    elif selected != "portfolio":
        body = render_endoscopy(selected) + render_revenuecat(selected) + render_play(selected) + render_marketing(selected) + body
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)} | Hildreth Technologies</title>{HEAD}<style>{css}</style></head><body><div class="layout"><aside><div class="brand" style="font-size:20px">Hildreth<br><span>Technologies</span></div><nav>{navigation(selected)}</nav></aside><main><header><div><h1>{html.escape(title)}</h1><p>{html.escape(subtitle)}</p></div></header>{body}<footer>Website product status is not confirmation of a live store listing. All customer metrics require authenticated source data. No sample figures appear in the owner console.</footer></main></div></body></html>""".encode("utf-8")

def handler(key, password):
    expected = ("Basic " + base64.b64encode(("owner:" + password).encode()).decode()).encode()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def reply(self, status, body, challenge=False, content_type="text/html; charset=utf-8"):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; script-src 'self'; worker-src 'self'; manifest-src 'self'; img-src 'self'; frame-ancestors 'none'; base-uri 'none'")
            self.send_header("X-Content-Type-Options", "nosniff")
            if challenge:
                self.send_header("WWW-Authenticate", 'Basic realm="Hildreth Technologies Owner"')
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        def do_GET(self):
            asset = ASSETS.get(urlsplit(self.path).path)
            if asset:
                return self.reply(200, asset[1], content_type=asset[0])
            if not hmac.compare_digest(self.headers.get("Authorization", "").encode(), expected):
                return self.reply(401, b"Login required", True)
            parsed = urlsplit(self.path)
            if parsed.path == "/":
                return self.reply(200, render_portfolio())
            if not parsed.path.startswith("/apps/"):
                return self.reply(404, b"Not found")
            selected = parsed.path[len("/apps/"):]
            if selected not in APPS:
                return self.reply(404, b"Not found")
            if selected != "routecast":
                period = parse_qs(parsed.query).get("period", ["30"])[0]
                if period not in PERIODS:
                    return self.reply(400, b"Invalid date range")
                data = None
                failed = False
                if PRODUCT_TYPES[selected] == "Website":
                    try:
                        data = ga4_report(selected, period)
                    except Exception:
                        failed = True
                return self.reply(200, render_portfolio(selected, data, period, failed))
            try:
                body = render(fetch_stats(key)) if key else render()
            except Exception:
                return self.reply(502, render())
            self.reply(200, body)
    return Handler

if __name__ == "__main__":
    hosted = os.getenv("DASHBOARD_HOSTED") == "1"
    key = os.getenv("ADMIN_API_KEY", "") if hosted else (os.getenv("ADMIN_API_KEY") or getpass.getpass("Production ADMIN_API_KEY (optional): "))
    password = os.getenv("DASHBOARD_PASSWORD", "") if hosted else secrets.token_urlsafe(24)
    if len(password) < 24:
        raise SystemExit("A strong DASHBOARD_PASSWORD (at least 24 characters) is required")
    server = ThreadingHTTPServer(("0.0.0.0" if hosted else "127.0.0.1", int(os.getenv("PORT", "8765")) if hosted else 8765), handler(key, password))
    if hosted:
        print("Owner console started; HTTPS reverse proxy required.", flush=True)
    else:
        print("Port 8765: keep PRIVATE. Login: owner. Temporary password: " + password, flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()
