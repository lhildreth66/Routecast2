"""HTML display of verified GA4 reports; no invented metrics."""
import html
import math
from datetime import datetime
from traffic_trend import render_trend
from acquisition_view import render_acquisition, render_link_generator

def render_web(product, data, period, failed=False):
    return render_traffic(product, data, period, failed) + (render_acquisition(data) if data is not None else '') + render_link_generator(product)

def render_traffic(product, data, period, failed=False):
    base = "/apps/" + product
    buttons = []
    for k, label in [("today", "Today"), ("7", "7 days"), ("30", "30 days"), ("90", "90 days")]:
        color = "#1668dc" if k == period else "#53677b"
        buttons.append(f'<a class="refresh" style="display:inline-block;margin:3px;background:{color}" href="{base}?period={k}">{label}</a>')
    filters = " ".join(buttons)
    if data is None:
        message = "GA4 report unavailable; verify property and permissions." if failed else "GA4 property not connected. Configure server settings."
        return f'<section class="panel"><h2>Website traffic</h2>{filters}<p>{message}</p></section>'
    totals = data["totals"]
    def fmt(key):
        try:
            v = float(totals[key])
            if not math.isfinite(v) or v < 0:
                return "—"
            if key == "bounceRate":
                return f"{v*100:.1f}%"
            if key == "averageSessionDuration":
                return f"{int(v)//60}m {int(v)%60:02d}s"
            return f"{int(v):,}"
        except (KeyError, ValueError, TypeError):
            return "—"
    cards = "".join(f'<section class="tile"><small>{label}</small><strong>{fmt(key)}</strong></section>' for label, key in [("Visitors","totalUsers"),("New visitors","newUsers"),("Sessions","sessions"),("Page views","screenPageViews"),("Average session","averageSessionDuration"),("Bounce rate","bounceRate")])
    panels = []
    for label, rows in data["groups"].items():
        if label == "Recent Trends":
            continue
        rows = rows or []
        if label == "Most Visited Pages":
            rows = [(k,v) for k,v in rows if k.startswith("/") and "?" not in k and "@" not in k and not any(ch.isdigit() for ch in k)]
        peak = max((v for _,v in rows), default=1) or 1
        lines = []
        displayed = rows[-30:] if label == "Recent Trends" else rows[:30]
        for k,v in displayed:
            if label == "Recent Trends":
                try:
                    k = datetime.strptime(k, "%Y%m%d").strftime("%b %d, %Y")
                except (ValueError, TypeError):
                    pass
            safe = html.escape(str(k)[:100])
            width = max(0,min(100,v/peak*100))
            lines.append(f'<div class="legend-row"><span style="overflow-wrap:anywhere">{safe}</span><b>{v:,}</b></div><div style="height:7px;background:#e4ebf3;border-radius:4px"><div style="height:7px;width:{width:.1f}%;background:#1684cc;border-radius:4px"></div></div>')
        body = "".join(lines) or "<p>No reportable rows or report unavailable.</p>"
        if label == "Recent Trends" and len(rows) > 30:
            body = "<p>Latest 30 reported dates in the selected period.</p>" + body
        panels.append(f'<section class="panel"><h2>{html.escape(label)}</h2>{body}</section>')
    stamp = html.escape(data["fetched"])
    return f'<section class="panel" style="margin-bottom:18px"><h2>Google Analytics · website traffic</h2>{filters}<p>Read-only GA4 · today may be incomplete · fetched {stamp}</p></section><div class="kpis">{cards}</div>{render_trend(data["groups"].get("Recent Trends"))}<div class="columns" style="margin-top:16px">{"".join(panels)}</div><p>Visitors are GA4 total users, not guaranteed unique people. Sources, country, device and trend panels count sessions; pages count views. Bars scale to the largest row. GA4 may omit or threshold data.</p>'
