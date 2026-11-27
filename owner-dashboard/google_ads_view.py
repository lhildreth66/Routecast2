"""Read-only Google Ads reporting for the existing private owner dashboard."""
import html
import math
import os
import re
from datetime import datetime, timedelta, timezone
from threading import Lock
from time import monotonic
from zoneinfo import ZoneInfo

# Verified against account 4858810197 on 2026-11-27. Match app IDs, never names.
PRODUCTS = {
    "routecast": ("com.routecast.app", "7609511939", "7918983069"),
    "emergent-vpn": ("com.emergentvpn", "7658557866", "7666723869"),
    "endoscopy-nurse-pro": ("com.endoscopynursepro.app", "7658461636", "7919001775"),
}
ACCOUNT = "4858810197"
SCOPE = "https://www.googleapis.com/auth/adwords"
API = "https://googleads.googleapis.com/v26/customers/"
CACHE = {}
LOCK = Lock()


class AdsUnavailable(Exception):
    pass


def search(session, customer, query):
    if customer != ACCOUNT:
        raise AdsUnavailable("Unexpected account")
    with session.post(API + customer + "/googleAds:searchStream",
                      json={"query": query}, timeout=(3, 8), max_allowed_time=14,
                      allow_redirects=False, stream=True) as response:
        if response.status_code != 200:
            raise AdsUnavailable("Google Ads HTTP " + str(response.status_code))
        import json
        body = bytearray()
        for chunk in response.iter_content(65536):
            body.extend(chunk)
            if len(body) > 4_000_000:
                raise AdsUnavailable("Report exceeds size limit")
        payload = json.loads(body)
    if not isinstance(payload, list):
        raise AdsUnavailable("Unexpected response")
    return [row for batch in payload for row in batch.get("results", [])]


def num(metrics, key):
    # Protobuf REST omits default zero fields.
    raw = metrics.get(key, 0)
    if isinstance(raw, bool):
        raise ValueError("Invalid metric")
    v = float(raw)
    if not math.isfinite(v):
        raise ValueError("Invalid metric")
    return v


def retrieve(query, customer, now=None):
    info = query("SELECT customer.id, customer.currency_code, customer.time_zone FROM customer")
    if len(info) != 1 or str(info[0]["customer"]["id"]) != customer:
        raise AdsUnavailable("Account mismatch")
    info = info[0]["customer"]
    if info["currencyCode"] != "USD":
        raise AdsUnavailable("Unexpected currency")
    now = now or datetime.now(timezone.utc)
    end = now.astimezone(ZoneInfo(info["timeZone"])).date()
    start = end - timedelta(days=29)
    date_filter = f"segments.date BETWEEN '{start}' AND '{end}'"
    apps = ", ".join("'" + p[0] + "'" for p in PRODUCTS.values())
    app_filter = "campaign.app_campaign_setting.app_id IN (" + apps + ")"
    actions = {a for _, i, p in PRODUCTS.values() for a in (i,p)}
    action_rows = query("SELECT conversion_action.id, conversion_action.status, conversion_action.category, "
                        "conversion_action.type FROM conversion_action WHERE conversion_action.id IN ("
                        + ", ".join(sorted(actions)) + ")")
    enabled = {str(r["conversionAction"]["id"]): r["conversionAction"] for r in action_rows
               if r["conversionAction"].get("status") == "ENABLED"}
    # Do not combine cost with conversion-action segments: it would duplicate spend.
    traffic = query("SELECT campaign.id, campaign.app_campaign_setting.app_id, segments.date, "
                    "metrics.impressions, metrics.clicks, metrics.cost_micros FROM campaign WHERE "
                    + app_filter + " AND " + date_filter)
    conv = query("SELECT campaign.id, campaign.app_campaign_setting.app_id, segments.date, "
                 "segments.conversion_action, metrics.all_conversions, metrics.all_conversions_value FROM campaign WHERE "
                 + app_filter + " AND " + date_filter)
    result = {}
    for product, (app, install, purchase) in PRODUCTS.items():
        install_ok = enabled.get(install, {}).get("type") == "GOOGLE_PLAY_DOWNLOAD"
        purchase_ok = enabled.get(purchase, {}).get("type") == "GOOGLE_PLAY_IN_APP_PURCHASE"
        days = {}
        for offset in range(30):
            day = str(start + timedelta(days=offset))
            days[day] = {"spend": 0.0, "impressions": 0, "clicks": 0,
                         "installs": 0.0 if install_ok else None,
                         "purchases": 0.0 if purchase_ok else None,
                         "value": 0.0 if purchase_ok else None}
        for row in traffic:
            if row["campaign"].get("appCampaignSetting", {}).get("appId") != app:
                continue
            d = days[row["segments"]["date"]]
            m = row.get("metrics", {})
            d["spend"] += num(m, "costMicros") / 1_000_000
            d["impressions"] += num(m, "impressions")
            d["clicks"] += num(m, "clicks")
        for row in conv:
            if row["campaign"].get("appCampaignSetting", {}).get("appId") != app:
                continue
            action = row["segments"]["conversionAction"].rsplit("/", 1)[-1]
            d = days[row["segments"]["date"]]
            m = row.get("metrics", {})
            if action == install and install_ok:
                d["installs"] += num(m, "allConversions")
            if action == purchase and purchase_ok:
                d["purchases"] += num(m, "allConversions")
                d["value"] += num(m, "allConversionsValue")
        result[product] = days
    return {"start": str(start), "end": str(end), "timezone": info["timeZone"],
            "fetched": now.astimezone(timezone.utc).isoformat(), "products": result}


def fetch(customer):
    import google.auth
    from google.auth.transport.requests import AuthorizedSession
    credentials, project = google.auth.default(scopes=[SCOPE])
    if project != "hildreth-dashboard":
        raise AdsUnavailable("Unexpected credentials project")
    with AuthorizedSession(credentials, max_refresh_attempts=1, refresh_timeout=6) as session:
        return retrieve(lambda q: search(session, customer, q), customer)


def report(customer):
    # Avoid queueing multiple page requests behind a slow network call.
    if not LOCK.acquire(blocking=False):
        return None, "Refresh in progress; try again shortly."
    try:
        entry = CACHE.get(customer)
        if entry and monotonic() - entry[0] < (300 if entry[1] else 60):
            return entry[1], entry[2]
        try:
            result = fetch(customer)
            entry = (monotonic(), result, "")
        except AdsUnavailable as exc:
            # Only messages constructed locally above; no remote body or token.
            entry = (monotonic(), None, str(exc))
        except Exception:
            entry = (monotonic(), None, "Reporting request failed; check Google Ads access and dashboard credentials.")
        CACHE[customer] = entry
        return entry[1], entry[2]
    finally:
        LOCK.release()


def totals(rows):
    return {key: (sum(r[key] for r in rows) if all(r[key] is not None for r in rows) else None)
            for key in ("spend", "impressions", "clicks", "installs", "purchases", "value")}


def fmt(v, money=False):
    if v is None:
        return "—"
    return f"${v:,.2f}" if money else f"{v:,.2f}".rstrip("0").rstrip(".")


def divide(a, b):
    return a / b if a is not None and b is not None and b > 0 else None


def render_ads(product):
    if product not in PRODUCTS:
        return ""
    customer = os.getenv("GOOGLE_ADS_CUSTOMER_ID", "").strip().replace("-", "")
    if not customer:
        return ""
    heading = '<section class="panel" style="margin:18px 0"><h2>Google Ads · automatic campaign reporting</h2>'
    if customer != ACCOUNT:
        return heading + '<div class="pending">Advertising account configuration does not match the verified campaign mapping.</div></section>'
    data, error = report(customer)
    if data is None:
        return heading + '<div class="pending">' + html.escape(error) + ' No live figures assumed.</div></section>'
    days = data["products"][product]
    dates = sorted(days)
    periods = [("Today (partial)", dates[-1:]), ("Last 7 days", dates[-7:]), ("Last 30 days", dates)]
    rows = []
    for label, window in periods:
        t = totals([days[d] for d in window])
        roas = divide(t["value"], t["spend"]) if t["purchases"] else None
        values = [fmt(t["spend"], True), fmt(t["impressions"]), fmt(t["clicks"]),
                  fmt(t["installs"]), fmt(divide(t["spend"], t["installs"]), True),
                  fmt(t["purchases"]), fmt(divide(t["spend"], t["purchases"]), True),
                  fmt(t["value"], True), "—" if roas is None else f"{roas:.2f}x"]
        rows.append("<tr><td>" + label + "</td>" + "".join("<td>" + v + "</td>" for v in values) + "</tr>")
    columns = ["Period", "Spend", "Impressions", "Clicks", "Installs", "Cost/install",
               "Purchase events", "Cost/purchase", "Attributed value", "ROAS"]
    table = '<div style="overflow-x:auto"><table style="width:100%;text-align:right;white-space:nowrap"><thead><tr>' + "".join("<th>"+c+"</th>" for c in columns) + "</tr></thead><tbody>" + "".join(rows) + "</tbody></table></div>"
    daily = []
    for day in reversed(dates[-7:]):
        t = days[day]
        daily.append("<tr><td>"+html.escape(day)+"</td><td>"+fmt(t["spend"],True)+"</td><td>"+fmt(t["installs"])+"</td><td>"+fmt(t["purchases"])+"</td></tr>")
    trend = '<h3>Daily performance · last 7 days</h3><div style="overflow-x:auto"><table style="width:100%"><thead><tr><th>Date</th><th>Spend</th><th>Installs</th><th>Purchase events</th></tr></thead><tbody>'+"".join(daily)+"</tbody></table></div>"
    return (heading + '<p>Google Ads API · ' + html.escape(data["start"]) + ' to ' + html.escape(data["end"]) +
            ' · USD · account timezone ' + html.escape(data["timezone"]) + ' · retrieved ' + html.escape(data["fetched"]) +
            ' · 5-minute cache</p>' + table + trend +
            '<p>Android app campaigns only, matched by verified app ID. Conversions use the configured install and in-app purchase actions (All conversions); attribution can be fractional and delayed. Purchase events are not unique paying subscribers. Attributed value is not independently verified revenue. — means unavailable or undefined. Today is incomplete. The saved historical report below is separate.</p></section>')
