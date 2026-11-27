"""TikHooks2 aggregate reporting. No raw customer records, no write operations."""
import html
import json
import os
import re
import threading
from datetime import datetime, timezone
from time import monotonic
from urllib.request import Request, build_opener, HTTPRedirectHandler

URL = "https://cnktoiaibxkvujxvdhbt.supabase.co/functions/v1/tikhooks-owner-report"
TOKEN_NAME = "TIKHOOKS_OWNER_REPORT_TOKEN"
FIELDS = ("total_accounts","owner_entitlements","internal_accounts","nonowner_accounts","new_nonowner_accounts_30d",
          "nonowner_subscription_records","active_nonowner_subscription_records","live_payment_events",
          "live_payment_events_30d","sandbox_webhook_events")
CACHE = None
LOCK = threading.Lock()

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        return None

def validate(data):
    if not isinstance(data,dict) or data.get("version")!=1 or data.get("product")!="tikhooks2":
        raise ValueError("Invalid report")
    for key in FIELDS:
        if type(data.get(key)) is not int or not 0<=data[key]<=2**53-1:
            raise ValueError("Invalid count")
    stamp=datetime.fromisoformat(data["fetched_at"].replace("Z","+00:00"))
    if stamp.tzinfo is None or not -60 <= (datetime.now(timezone.utc)-stamp).total_seconds() <= 900:
        raise ValueError("Stale report")
    if (data["internal_accounts"]+data["nonowner_accounts"]!=data["total_accounts"] or data["new_nonowner_accounts_30d"]>data["nonowner_accounts"]
            or data["active_nonowner_subscription_records"]>data["nonowner_subscription_records"]
            or data["live_payment_events_30d"]>data["live_payment_events"]):
        raise ValueError("Inconsistent counts")
    return {k:data[k] for k in (*FIELDS,"fetched_at")}

def fetch(token):
    request=Request(URL,headers={"Authorization":"Bearer "+token,"Accept":"application/json"},method="GET")
    with build_opener(NoRedirect()).open(request,timeout=12) as response:
        raw=response.read(16385)
    if len(raw)>16384:
        raise ValueError("Oversize report")
    return validate(json.loads(raw))

def report():
    global CACHE
    token=os.getenv(TOKEN_NAME,"").strip()
    if not re.fullmatch(r"[a-fA-F0-9]{64}",token):
        return None,"Reporting token not configured."
    if not LOCK.acquire(blocking=False):
        return None,"Report refresh in progress."
    try:
        if CACHE and monotonic()-CACHE[0] < (300 if CACHE[1] else 60):
            return CACHE[1],CACHE[2]
        try:
            data,error=fetch(token),""
        except Exception:
            data,error=None,"Report unavailable. Check the Supabase function and reporting token."
        CACHE=(monotonic(),data,error)
        return data,error
    finally:
        LOCK.release()

EVENTS = (
    ("funnel_visit","Visit tracked"),("signup_started","Signup started"),("signup_submitted","Signup submitted"),
    ("signup_succeeded","Signup succeeded"),("checkout_view","Checkout viewed"),("checkout_started","Checkout started"),
    ("checkout_approved","Checkout approved"),("dashboard_access_granted","Dashboard access granted"),
    ("signup_failed","Signup failed"),("login_success","Login succeeded"),("login_error","Login failed"),
    ("checkout_cancelled","Checkout cancelled"),("checkout_failed","Checkout failed"),
    ("dashboard_access_denied","Dashboard access denied"),
)
def collect_journey(client,prop,start):
    from google.analytics.data_v1beta.types import RunReportRequest,DateRange,Metric,Dimension,Filter,FilterExpression
    request=RunReportRequest(property="properties/"+prop,date_ranges=[DateRange(start_date=start,end_date="today")],
        dimensions=[Dimension(name="eventName")],metrics=[Metric(name="eventCount"),Metric(name="totalUsers")],
        dimension_filter=FilterExpression(filter=Filter(field_name="eventName",
            in_list_filter=Filter.InListFilter(values=[k for k,_ in EVENTS]))),limit=50)
    result=client.run_report(request,timeout=12)
    if getattr(result.metadata,"subject_to_thresholding",False):
        return None
    allowed={k for k,_ in EVENTS}
    rows={}
    for row in result.rows:
        key=row.dimension_values[0].value
        if key not in allowed:
            continue
        counts=[int(m.value) for m in row.metric_values]
        if len(counts)!=2 or min(counts)<0 or key in rows:
            raise ValueError("Invalid event report")
        rows[key]=counts
    return rows

def tile(label,value,detail):
    return f'<section class="tile"><small>{label}</small><strong>{value:,}</strong><span>{detail}</span></section>'

def render_tikhooks(web_data):
    data,error=report()
    body='<section class="panel" style="margin-bottom:18px"><h2>Accounts &amp; subscriptions · TikHooks2</h2>'
    if data is None:
        body+='<p>'+html.escape(error)+' No customer counts assumed.</p>'
    else:
        body+='<p>Supabase snapshot · '+html.escape(data["fetched_at"])+'</p><div class="kpis">'+''.join(
            tile(label,data[key],detail) for label,key,detail in (
                ("Registered accounts","total_accounts","All profile records"),
                ("External registered accounts","nonowner_accounts","Excludes confirmed internal accounts"),
                ("New external accounts","new_nonowner_accounts_30d","Rolling 30 days"),
                ("Active subscription records","active_nonowner_subscription_records","Not verified paid customers"),
                ("Live payment events","live_payment_events","Recorded external-account events · all time"),
                ("Live payment events","live_payment_events_30d","Recorded events · rolling 30 days"),
            ))+'</div><p>Internal accounts: '+str(data["internal_accounts"])+' · Owner entitlements: '+str(data["owner_entitlements"])+' · Sandbox webhook events: '+str(data["sandbox_webhook_events"])+' · External subscription records: '+str(data["nonowner_subscription_records"])+'.</p>'
    body+='<p>Verified paying customer totals and actual revenue require PayPal reconciliation. A recorded webhook event is not necessarily a unique payment. No advertising data is included.</p></section>'
    body+='<section class="panel" style="margin:18px 0"><h2>Customer journey · signup to checkout</h2>'
    rows=(web_data or {}).get("tikhooks_journey")
    if rows is None:
        body+='<p>GA4 customer journey report unavailable or not yet collected.</p>'
    elif not rows:
        body+='<p>No reportable customer journey events for this date range. This does not prove that no attempts occurred.</p>'
    else:
        body+='<p>Reported events and users per stage for the selected GA4 date range. Includes test/internal traffic unless the property excludes it. Counts are not a sequenced conversion funnel.</p><div style="overflow-x:auto"><table style="width:100%"><thead><tr><th style="text-align:left">Step</th><th style="text-align:right">Events</th><th style="text-align:right">Users</th></tr></thead><tbody>'
        for key,label in EVENTS:
            v=rows.get(key)
            body+=f'<tr><td style="padding:8px 0">{label}</td><td style="text-align:right">{v[0]:,}</td><td style="text-align:right">{v[1]:,}</td></tr>' if v is not None else f'<tr><td style="padding:8px 0">{label}</td><td style="text-align:right">—</td><td style="text-align:right">—</td></tr>'
        body+='</tbody></table></div><p>— means no reported row, not a confirmed zero. Checkout approval is not proof of a completed payment.</p>'
    return body+'</section>'
