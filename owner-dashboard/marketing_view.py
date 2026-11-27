"""Private aggregate marketing snapshot, supplied only via server environment."""
import html
import json
import math
import os
from datetime import date
from google_ads_view import render_ads

PRODUCTS = {"routecast", "emergent-vpn", "endoscopy-nurse-pro", "simple-background-remover"}

def snapshot():
    raw = os.getenv("DASHBOARD_MARKETING_SNAPSHOT", "")
    if not raw:
        return None
    data = json.loads(raw)
    if not isinstance(data, dict) or data.get("currency") != "USD":
        raise ValueError("Invalid marketing snapshot")
    date.fromisoformat(data["as_of"])
    date.fromisoformat(data["start"])
    if data["start"] > data["as_of"]:
        raise ValueError("Invalid report dates")
    if not isinstance(data["products"], dict):
        raise ValueError("Invalid products")
    return data

def numeric(record, key):
    v = record.get(key)
    return v if type(v) in (int, float) and math.isfinite(v) and v >= 0 else None

def money(v):
    return "—" if v is None else f"${v:,.2f}"

def number(v):
    return "—" if v is None else f"{v:,.2f}".rstrip("0").rstrip(".")

def render_saved_marketing(product):
    if product not in PRODUCTS:
        return ""
    title = '<h2>Advertising &amp; revenue</h2>'
    try:
        data = snapshot()
        record = data["products"].get(product) if data else None
        if record is not None and not isinstance(record, dict):
            raise ValueError("Invalid record")
    except (ValueError, TypeError, KeyError):
        return '<section class="panel">'+title+'<p>Marketing snapshot unavailable; check server configuration.</p></section>'
    if record is None:
        return '<section class="panel">'+title+'<div class="pending">Advertising and store revenue source not connected.</div></section>'
    spend = numeric(record, "spend")
    installs = numeric(record, "installs")
    purchases = numeric(record, "purchases")
    value = numeric(record, "purchase_value")
    gross = numeric(record, "gross_revenue")
    cost_per_install = spend / installs if spend is not None and installs else None
    cost_per_purchase = spend / purchases if spend is not None and purchases else None
    roas = value / spend if value is not None and spend else None
    tiles = [
        ("Google Ads spend", money(spend)),
        ("Ad-attributed installs (all)", number(installs)),
        ("Cost per attributed install", money(cost_per_install)),
        ("Recorded purchase conversions", number(purchases)),
        ("Cost per recorded purchase", money(cost_per_purchase)),
        ("Attributed purchase value", money(value)),
        ("Attributed return on ad spend", "—" if roas is None else f"{roas:.2f}x"),
        ("Google Play gross subscription revenue", money(gross)),
    ]
    cards = "".join(f'<section class="tile"><small>{label}</small><strong>{v}</strong></section>' for label,v in tiles)
    coverage = html.escape(str(record.get("coverage", "Attribution coverage unverified.")))
    return f'<section class="panel" style="margin:18px 0">{title}<p>Google Ads and Google Play · saved report, not live · {data["start"]} to {data["as_of"]} · USD</p><div class="kpis">{cards}</div><p>{coverage}</p><p>Install counts use Google Ads All conversions and may differ from the primary Conversions column. Purchase events are not unique paying customers. Total store revenue is not ad-attributed revenue. Organic purchases and unique customer acquisition cost are unavailable without reliable attribution. Blank means unknown, not zero. Gross revenue precedes applicable fees and adjustments.</p></section>'


def render_marketing(product):
    return render_ads(product) + render_saved_marketing(product)
