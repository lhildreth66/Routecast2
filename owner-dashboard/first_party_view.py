"""Read-only reporting for the corporate website's isolated first-party database."""
import html
import os
from datetime import datetime, timedelta, timezone
from threading import Lock
from time import monotonic

PRODUCT = "hildreth-technology"
DATABASE = "hildreth_owner_analytics"
COLLECTION = "owner_web_events_v1"
ENV = "HILDRETH_FIRST_PARTY_MONGO_URL"
CACHE = {}
LOCK = Lock()


def window(period, now):
    today = now.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    days = {"today":1,"7":7,"30":30,"90":30}[period]
    return max(now-timedelta(days=30), today-timedelta(days=days-1)), now


def verify_roles(status):
    a = status.get("authInfo", {})
    if (len(a.get("authenticatedUsers", [])) != 1 or
            a.get("authenticatedUserRoles", []) != [{"role":"read","db":DATABASE}]):
        raise ValueError("Dedicated read-only analytics account required")


def ranked(field, count=20):
    return [{"$group":{"_id":field,"count":{"$sum":1}}},
            {"$sort":{"count":-1,"_id":1}},{"$limit":count}]


def query_snapshot(collection, start, now):
    match = {"ts":{"$gte":start,"$lte":now},"expires_at":{"$gt":now}}
    sessions_pipeline = [
        {"$match":{**match,"kind":"page_view"}},
        {"$sort":{"ts":1}},
        {"$group":{"_id":"$session","source":{"$first":"$source"},
                   "medium":{"$first":"$medium"},"campaign":{"$first":"$campaign"},
                   "referrer":{"$first":"$referrer"},"device":{"$first":"$device"},
                   "browser":{"$first":"$browser"},"os":{"$first":"$os"},
                   "landing":{"$first":"$page"}}},
        {"$facet":{
            "count":[{"$count":"count"}],
            "sources":ranked({"source":"$source","medium":"$medium"}),
            "campaigns":ranked("$campaign"),"referrers":ranked("$referrer"),
            "landing":ranked("$landing"),"devices":ranked("$device"),
            "browsers":ranked("$browser"),"systems":ranked("$os")}}
    ]
    events_pipeline = [
        {"$match":match},
        {"$facet":{
            "kinds":ranked("$kind"),
            "pages":[{"$match":{"kind":"page_view"}},*ranked("$page")],
            "products":[{"$match":{"kind":"product_click"}},*ranked("$product")],
            "time":[{"$match":{"kind":"page_time"}},
                    {"$group":{"_id":None,"seconds":{"$sum":"$seconds"}}}],
            "daily":[{"$match":{"kind":"page_view"}},
                     {"$group":{"_id":{"$dateToString":{"format":"%Y-%m-%d","date":"$ts","timezone":"UTC"}},"count":{"$sum":1}}},
                     {"$sort":{"_id":1}},{"$limit":31}]
        }}
    ]
    with collection.aggregate(sessions_pipeline, maxTimeMS=3000, allowDiskUse=False) as cursor:
        s = next(cursor)
    with collection.aggregate(events_pipeline, maxTimeMS=3000, allowDiskUse=False) as cursor:
        e = next(cursor)
    return {"start":start.isoformat(),"fetched":now.isoformat(),"sessions":s,"events":e}


def read_snapshot(uri, period):
    if not uri.startswith(("mongodb://","mongodb+srv://")):
        raise ValueError("Invalid connection")
    from pymongo import MongoClient, timeout
    with MongoClient(uri, tls=True,tlsAllowInvalidCertificates=False,tlsAllowInvalidHostnames=False,
                     connect=False,maxPoolSize=2,minPoolSize=0,retryReads=False,
                     serverSelectionTimeoutMS=3500,connectTimeoutMS=2500,socketTimeoutMS=3500) as client:
        with timeout(10):
            verify_roles(client.admin.command("connectionStatus"))
            db=client[DATABASE]
            if COLLECTION not in db.list_collection_names(filter={"name":COLLECTION}):
                return None
            start, now = window(period,datetime.now(timezone.utc))
            return query_snapshot(db[COLLECTION],start,now)


def fetch(period):
    uri=os.getenv(ENV,"").strip()
    if not uri:
        return None, "First-party analytics not connected."
    if not LOCK.acquire(blocking=False):
        return None, "First-party report refresh in progress."
    try:
        item=CACHE.get(period)
        if item and monotonic()-item[0] < (300 if item[1] else 60):
            return item[1], item[2]
        try:
            data=read_snapshot(uri,period)
            message="" if data is not None else "First-party event collection has not been initialized."
        except Exception:
            data,message=None,"First-party report unavailable. Check the dedicated read-only connection."
        CACHE[period]=(monotonic(),data,message)
        return data,message
    finally:
        LOCK.release()


def count(value):
    if type(value) is not int or value < 0:
        raise ValueError("Invalid count")
    return f"{value:,}"


def label(value):
    if isinstance(value,dict):
        value=(value.get("source") or "Direct / unknown")+" / "+(value.get("medium") or "(none)")
    return html.escape(str(value or "(not set)")[:253])


def table(title, rows, heading):
    body="".join("<tr><td style='overflow-wrap:anywhere'>"+label(row["_id"])+"</td><td style='text-align:right'>"+count(row["count"])+"</td></tr>" for row in rows[:31])
    return '<section class="panel"><h3>'+title+'</h3>'+(
        '<div style="overflow-x:auto"><table style="width:100%"><thead><tr><th>Group</th><th>'+heading+
        '</th></tr></thead><tbody>'+body+'</tbody></table></div>' if body else '<p>No recorded rows.</p>')+'</section>'


def render_first_party(product, period):
    if product!=PRODUCT:
        return ""
    heading='<section class="panel" style="margin:18px 0"><h2>Hildreth first-party analytics</h2>'
    note='<p>Separate from GA4. Counts cover only consented browser events since activation, and must not be added to Google Analytics totals. No individual identity, raw IP, contact details or cross-site history is collected. IP security-log reporting is not connected.</p>'
    try:
        data,message=fetch(period)
        if data is None:
            return heading+'<div class="pending">'+html.escape(message)+'</div>'+note+'</section>'
        s,e=data["sessions"],data["events"]
        k={r["_id"]:r["count"] for r in e["kinds"]}
        sc=s["count"][0]["count"] if s["count"] else 0
        sec=e["time"][0]["seconds"] if e["time"] else 0
        tiles=(("Observed sessions",sc),("Page views",k.get("page_view",0)),
               ("Product link clicks",k.get("product_click",0)),("Contact successes",k.get("contact_success",0)),
               ("Visible-page seconds (estimate)",sec))
        cards="".join('<section class="tile"><small>'+title+'</small><strong>'+count(value)+'</strong></section>' for title,value in tiles)
        tables="".join(table(title,rows,unit) for title,rows,unit in [
            ("Session sources",s["sources"],"Sessions"),("Session campaigns",s["campaigns"],"Sessions"),
            ("External referring domains",s["referrers"],"Sessions"),("First observed pages",s["landing"],"Sessions"),
            ("Device categories",s["devices"],"Sessions"),("Browser families",s["browsers"],"Sessions"),
            ("Operating systems",s["systems"],"Sessions"),("Pages",e["pages"],"Views"),
            ("Product interest",e["products"],"Clicks"),("Daily activity (UTC)",e["daily"],"Views")])
        timing='<p>UTC reporting window: '+html.escape(data["start"])+' to '+html.escape(data["fetched"])+' · 5-minute cache. Events retained for 30 days; 90-day selection is limited to available 30-day history. Today is partial. No rows means no observed consented events, not necessarily no visitors.</p>'
        return heading+timing+'<div class="kpis">'+cards+'</div>'+note+'</section><div class="columns">'+tables+'</div>'
    except Exception:
        return heading+'<div class="pending">First-party reporting unavailable. No figures assumed.</div>'+note+'</section>'
