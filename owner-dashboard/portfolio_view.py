"""Compact portfolio overview. Reads only existing in-process report caches."""
import html
import math
import os
from time import monotonic
from threading import Lock
import ga4_reports as ga4
import revenuecat_view as rc
import endoscopy_view as endo
import google_ads_view as ads
import play_earnings as play

ORDER = ("routecast","emergent-vpn","endoscopy-nurse-pro","simple-background-remover",
         "hildreth-technology","medpolicyref","patriot-news-us","tikhooks2")
MARKS = {"routecast":"RC","emergent-vpn":"EV","endoscopy-nurse-pro":"EN",
         "simple-background-remover":"SB","hildreth-technology":"HT","medpolicyref":"MP",
         "patriot-news-us":"PN","tikhooks2":"TK"}
_ROUTE = None
_LOCK = Lock()

def remember_route(data):
    global _ROUTE
    with _LOCK:
        _ROUTE = (monotonic(), dict(data))

def clear_route():
    global _ROUTE
    with _LOCK:
        _ROUTE = None

def configured(*keys):
    return all(os.getenv(k,"").strip() for k in keys)

def fresh(entry, seconds=300):
    return bool(entry and 0 <= monotonic()-entry[0] < seconds)

def integer(value):
    if isinstance(value,bool):
        return None
    try:
        n=float(value)
        return f"{int(n):,}" if math.isfinite(n) and n>=0 and n.is_integer() else None
    except (TypeError, ValueError, OverflowError):
        return None

def snapshot(product):
    metrics, sources = [], []
    def add(label, value):
        v=integer(value)
        if v is not None:
            metrics.append((label,v))
    def source(label, ready):
        if ready:
            sources.append(label)
    if product in ga4.PROPERTIES:
        prop=ga4.property_id(product)
        source("Google Analytics",prop)
        cached=ga4.CACHE.get((product,prop,"30")) if prop else None
        if fresh(cached):
            t=cached[1].get("totals",{})
            add("Visitors · 30 days",t.get("totalUsers"))
            add("Sessions · 30 days",t.get("sessions"))
    if product=="routecast":
        enabled=configured("ADMIN_API_KEY")
        source("Backend accounts",enabled)
        entry=_ROUTE
        if enabled and fresh(entry):
            d=entry[1]
            add("Active account records",d.get("active_subscriptions"))
            add("Registered accounts",d.get("total_users"))
    if product=="emergent-vpn":
        ready=configured("RC_EMERGENT_PROJECT_ID","RC_EMERGENT_API_KEY")
        source("RevenueCat",ready)
        entry=rc.CACHE.get(product)
        if ready and entry and entry[0]==os.getenv("RC_EMERGENT_PROJECT_ID","").strip() and fresh((entry[1],)):
            m={r["id"]:r["value"] for r in entry[2]["metrics"]}
            add("Active paid subscriptions",m.get("active_subscriptions"))
            add("Active trials",m.get("active_trials"))
    if product=="endoscopy-nurse-pro":
        ready=configured(endo.URI_NAME,endo.DB_NAME)
        source("Backend learning & accounts",ready)
        entry=endo.CACHE
        if ready and fresh(entry):
            d=entry[1][0]
            add("Registered accounts",d.get("registered"))
            add("Active subscription records",d.get("active"))
    if product in ads.PRODUCTS:
        ready=os.getenv("GOOGLE_ADS_CUSTOMER_ID","").strip().replace("-","")==ads.ACCOUNT
        source("Google Ads",ready)
        entry=ads.CACHE.get(ads.ACCOUNT)
        if ready and fresh(entry) and entry[1]:
            days=entry[1]["products"].get(product,{})
            if days:
                spend=sum(d["spend"] for d in days.values())
                if math.isfinite(spend) and spend>=0:
                    metrics.append(("Ad spend · 30 days",f"$"+f"{spend:,.2f}"))
    if product in play.PACKAGES:
        source("Google Play earnings",configured("PLAY_EARNINGS_URI"))
    return metrics[:3],sources

CSS = """
.portfolio-intro{margin-bottom:24px;max-width:860px;color:#53677b;font-size:15px;line-height:1.6}
.portfolio-summary{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px;margin:0 0 30px}
.portfolio-summary .tile{padding:20px 22px}.portfolio-summary strong{font-size:30px;margin:6px 0}
.portfolio-group{margin:0 0 28px}.portfolio-group h2{font-size:21px;letter-spacing:-.3px;margin:0 0 14px}
.portfolio-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px}
.portfolio-card{background:#fff;border:1px solid #dce4ef;border-radius:15px;padding:22px;display:flex;flex-direction:column;gap:16px;min-width:0;box-shadow:0 3px 12px #142d4d08}
.portfolio-card-top{display:flex;align-items:flex-start;gap:12px}.portfolio-mark{display:grid;place-items:center;flex:none;width:42px;height:42px;border-radius:11px;background:#eaf2ff;color:#174b98;font-weight:800;font-size:14px}
.portfolio-card h3{font-size:19px;line-height:1.35;letter-spacing:-.35px;margin:0;overflow-wrap:anywhere}.portfolio-card p{font-size:13px;margin:4px 0 0}
.portfolio-state{display:inline-flex;align-items:center;gap:7px;font-size:12px;font-weight:700;color:#45617b}.portfolio-state:before{content:"";height:7px;width:7px;border-radius:50%;background:#64748b}.portfolio-state.live:before{background:#168061}
.portfolio-metrics{display:grid;gap:8px;min-height:76px}.portfolio-metric{display:flex;justify-content:space-between;align-items:baseline;gap:8px;font-size:13px;color:#53677b}.portfolio-metric b{font-size:20px;color:#12243e;white-space:nowrap;font-variant-numeric:tabular-nums}
.portfolio-sources{font-size:13px;color:#53677b;line-height:1.5;border-top:1px solid #e8eef5;padding-top:12px}.portfolio-sources b{color:#31465e}
.portfolio-open{display:flex;align-items:center;justify-content:space-between;margin-top:auto;text-decoration:none;color:#155cba;font-weight:700;padding:10px 0 2px;border-top:1px solid #e8eef5}.portfolio-open:hover{text-decoration:underline}.portfolio-open:focus-visible{outline:2px solid #1668dc;outline-offset:4px}
@media(max-width:1250px){.portfolio-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:680px){.portfolio-grid,.portfolio-summary{grid-template-columns:1fr}.portfolio-card{padding:18px}.portfolio-summary{gap:10px}}
"""

def render_overview(apps, product_types):
    snapshots={}
    for key in ORDER:
        try:
            snapshots[key]=snapshot(key)
        except Exception:
            snapshots[key]=([],[])
    total=len(apps)
    configured_count=sum(bool(sources) for _,sources in snapshots.values())
    observed=sum(bool(metrics) for metrics,_ in snapshots.values())
    summary="".join(f'<section class="tile"><small>{label}</small><strong>{value}</strong><span>{note}</span></section>'
        for label,value,note in (("Portfolio products",total,"Apps and websites"),("Reporting configured",configured_count,"At least one configured source"),("Recent data available",observed,"In-memory snapshots within five minutes")))
    def card(key):
        name,status,category=apps[key]
        metrics,sources=snapshots[key]
        state="Recent report" if metrics else "Sources configured" if sources else "Reporting setup pending"
        metric_rows="".join(f'<div class="portfolio-metric"><span>{html.escape(label)}</span><b>{html.escape(value)}</b></div>' for label,value in metrics)
        if not metrics:
            metric_rows='<p>Open this dashboard to retrieve its latest available reports.</p>' if sources else '<p>No reporting source is configured for this product.</p>'
        source_text=" · ".join(sources) or "Not yet configured"
        return (f'<article class="portfolio-card"><div class="portfolio-card-top"><span class="portfolio-mark" aria-hidden="true">{MARKS[key]}</span>'
                f'<div><h3>{html.escape(name)}</h3><p>{html.escape(category)} · {html.escape(status)}</p></div></div>'
                f'<span class="portfolio-state {"live" if metrics else ""}">{state}</span>'
                f'<div class="portfolio-metrics">{metric_rows}</div><div class="portfolio-sources"><b>Reporting sources</b><br>{html.escape(source_text)}</div>'
                f'<a class="portfolio-open" href="/apps/{key}" aria-label="Open {html.escape(name,quote=True)} dashboard">View dashboard <span aria-hidden="true">→</span></a></article>')
    groups=[]
    for title,keys in (("Mobile applications",ORDER[:4]),("Websites & SaaS",ORDER[4:])):
        groups.append('<section class="portfolio-group"><h2>'+title+'</h2><div class="portfolio-grid">'+''.join(card(k) for k in keys)+'</div></section>')
    return ('<p class="portfolio-intro">Your business at a glance. Select a product for detailed customer, traffic, subscription or advertising reports. Figures below use recent existing report snapshots; this overview does not launch additional API requests.</p>'
            '<div class="portfolio-summary">'+summary+'</div>'+''.join(groups)+
            '<p>Configured sources are not proof of successful retrieval. Subscription records, verified payments and advertising conversions are different measures; overlapping revenue sources are not added together.</p>')
