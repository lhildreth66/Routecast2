"""Read-only RevenueCat aggregate metrics. No customer IDs or VPN activity."""
import html
import json
import math
import os
import re
from datetime import datetime, timezone
from threading import Lock
from time import monotonic
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

CACHE = {}
LOCK = Lock()
ALLOWED_PRODUCTS = {"emergent-vpn": "EMERGENT"}
METRIC_NAMES = {
    "active_trials": "Active trials",
    "active_subscriptions": "Active paid subscriptions",
    "mrr": "Monthly recurring revenue",
    "revenue": "Revenue",
    "new_customers": "New customers",
    "active_customers": "Active customers",
}

def fetch_overview(product):
    prefix = ALLOWED_PRODUCTS.get(product)
    if not prefix:
        return None
    project = os.getenv("RC_" + prefix + "_PROJECT_ID", "").strip()
    key = os.getenv("RC_" + prefix + "_API_KEY", "").strip()
    if not project or not key:
        return None
    if not re.fullmatch(r"proj[a-zA-Z0-9_-]{1,100}", project):
        raise ValueError("Invalid project ID format")
    if not key.startswith("sk_"):
        raise ValueError("Invalid secret API key format")
    with LOCK:
        cached = CACHE.get(product)
        if cached and cached[0] == project and monotonic() - cached[1] < 300:
            return cached[2]
    url = "https://api.revenuecat.com/v2/projects/" + project + "/metrics/overview?currency=USD"
    request = Request(url, headers={"Authorization": "Bearer " + key, "Accept": "application/json"})
    with urlopen(request, timeout=10) as response:
        data = json.load(response)
    if data.get("currency") != "USD" or not isinstance(data.get("metrics"), list):
        raise ValueError("Invalid RevenueCat response")
    metrics = []
    for item in data["metrics"]:
        metric_id = item.get("id")
        value = item.get("value")
        if metric_id not in METRIC_NAMES or type(value) not in (int, float) or not math.isfinite(value):
            continue
        metrics.append({"id": metric_id, "value": value, "period": str(item.get("period", ""))[:40], "updated": str(item.get("last_updated_at_iso8601", ""))[:60]})
    result = {"metrics": metrics, "fetched": datetime.now(timezone.utc).isoformat()}
    with LOCK:
        CACHE[product] = (project, monotonic(), result)
    return result

def render_revenuecat(product):
    if product not in ALLOWED_PRODUCTS:
        return ""
    title = '<h2>RevenueCat · subscription overview</h2>'
    try:
        data = fetch_overview(product)
    except HTTPError as exc:
        hints = {400: "Request rejected; check project configuration.", 401: "Authentication rejected. Verify the V2 secret API key.", 403: "Access denied. Verify Charts metrics → Overview metrics read permission and that the key belongs to this project.", 404: "Project or endpoint not found. Verify the project ID in RevenueCat project settings.", 423: "RevenueCat reports this resource is locked.", 429: "Rate limit reached. Try again later."}
        message = f"RevenueCat HTTP {exc.code}: " + hints.get(exc.code, "RevenueCat service unavailable.")
        return '<section class="panel" style="margin-bottom:18px">'+title+'<div class="pending">'+html.escape(message)+'</div></section>'
    except ValueError as exc:
        # Only display locally defined, allowlisted error messages; never raw exceptions.
        known = ("Invalid project ID format", "Invalid secret API key format", "Invalid RevenueCat response")
        message = str(exc) if str(exc) in known else "Unexpected report format."
        return '<section class="panel" style="margin-bottom:18px">'+title+'<div class="pending">'+html.escape(message)+'</div></section>'
    except (URLError, TimeoutError):
        return '<section class="panel" style="margin-bottom:18px">'+title+'<div class="pending">RevenueCat network error or timeout.</div></section>'
    except Exception:
        return '<section class="panel" style="margin-bottom:18px">'+title+'<div class="pending">Unexpected reporting error.</div></section>'
    if data is None:
        return '<section class="panel" style="margin-bottom:18px">'+title+'<div class="pending">RevenueCat not connected. Configure server settings.</div></section>'
    cards = []
    for metric in data["metrics"]:
        metric_id = metric["id"]
        value = metric["value"]
        if metric_id in ("mrr", "revenue"):
            formatted = f"${value:,.2f}"
        else:
            formatted = f"{value:,.0f}"
        period = metric["period"]
        period_text = "Current snapshot" if period == "P0D" else ("Last " + period[1:-1] + " days" if re.fullmatch(r"P[1-9][0-9]*D", period) else "RevenueCat reporting period: " + (period or "not provided"))
        updated = html.escape(metric["updated"])
        cards.append(f'<section class="tile"><small>{METRIC_NAMES[metric_id]}</small><strong>{formatted}</strong><span>{html.escape(period_text)}<br>{updated}</span></section>')
    body = "".join(cards) or '<div class="pending">No supported overview metrics returned.</div>'
    stamp = html.escape(data["fetched"])
    return f'<section class="panel" style="margin-bottom:18px">{title}<p>Read-only project aggregate · USD · fetched {stamp}</p><div class="kpis">{body}</div><p>RevenueCat counts only transactions and customers tracked in this project; subscription counts are not unique paying people. Revenue is not ad-attributed or necessarily net payout. No individual customer records or VPN activity retrieved.</p></section>'
