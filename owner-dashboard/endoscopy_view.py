"""Read-only aggregate Endoscopy Nurse Pro dashboard."""
import html
import json
import os
from datetime import datetime, timezone
from threading import Lock
from time import monotonic
from urllib.request import Request, build_opener, HTTPRedirectHandler

PRODUCT = "endoscopy-nurse-pro"
URL = "https://endoscopy-nurse-pro-api.onrender.com/api/owner/reporting"
KEY_NAME = "ENDOSCOPY_REPORTING_KEY"
LABELS = {
    "registered": "Registered users", "new_30d": "New users · last 30 days",
    "active": "Active subscription records", "apple": "Apple active records",
    "android": "Android active records", "monthly": "Monthly active records",
    "annual": "Annual active records", "no_expiry": "Active records without expiry",
    "lessons": "Completed lessons", "videos": "Completed videos", "quizzes": "Module quiz records",
    "simulations": "Simulation records", "bookmarks": "Bookmarks",
}
WEEKS = tuple(f"week_{i}" for i in range(1, 5))
LOCK = Lock()
CACHE = None


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def validate(data):
    if not isinstance(data, dict) or data.get("schema") != 1:
        raise ValueError("Invalid schema")
    counts = data.get("counts")
    if not isinstance(counts, dict):
        raise ValueError("Invalid counts")
    clean = {}
    for k in (*LABELS, *WEEKS):
        v = counts.get(k)
        if type(v) is not int or v < 0:
            raise ValueError("Invalid count")
        clean[k] = v
    stamp = datetime.fromisoformat(data["as_of"])
    if stamp.tzinfo is None:
        raise ValueError("Invalid timestamp")
    modules = data.get("modules")
    if not isinstance(modules, list) or len(modules) > 10:
        raise ValueError("Invalid modules")
    rows = []
    for row in modules:
        title, count = row["title"], row["completed_lessons"]
        if not isinstance(title, str) or not 0 < len(title) <= 200 or type(count) is not int or count < 0:
            raise ValueError("Invalid module")
        rows.append((title, count))
    return clean, stamp.astimezone(timezone.utc), rows


def fetch():
    global CACHE
    key = os.getenv(KEY_NAME, "")
    if not key:
        return None
    if len(key) < 32 or not key.isascii():
        raise ValueError("Invalid key configuration")
    with LOCK:
        if CACHE and monotonic() - CACHE[0] < 300:
            return CACHE[1]
        req = Request(URL, headers={"X-Reporting-Key": key, "Accept": "application/json"})
        with build_opener(NoRedirect()).open(req, timeout=16) as response:
            raw = response.read(32769)
        if len(raw) > 32768:
            raise ValueError("Response too large")
        result = validate(json.loads(raw))
        CACHE = (monotonic(), result)
        return result


def render_endoscopy(product):
    if product != PRODUCT:
        return ""
    def panel(body):
        return '<section class="panel" style="margin-bottom:18px"><h2>Endoscopy Nurse Pro · backend reporting</h2>'+body+'</section>'
    try:
        data = fetch()
    except Exception:
        return panel('<div class="pending">Backend reporting unavailable. Verify the dedicated key and reporting endpoint. No zero counts assumed.</div>')
    if data is None:
        return panel('<div class="pending">Backend reporting not connected.</div>')
    counts, stamp, rows = data
    ratio = f'{100*counts["active"]/counts["registered"]:.2f}%' if counts["registered"] else '—'
    tiles = ''.join(f'<section class="tile"><small>{label}</small><strong>{counts[k]:,}</strong></section>' for k,label in LABELS.items())
    tiles += f'<section class="tile"><small>Active records / registered users</small><strong>{ratio}</strong></section>'
    weekly = ' · '.join(f'Week {i}: {counts[k]:,}' for i,k in enumerate(WEEKS,1))
    modules = ''.join(f'<p>{html.escape(title)} — {count:,}</p>' for title,count in rows) or '<p>No completed lesson records for known modules.</p>'
    return panel(f'<p>Read-only backend counts · as of {html.escape(stamp.isoformat())} · cached up to 5 minutes</p><div class="kpis">{tiles}</div><h2>Registrations · four rolling 7-day periods (oldest first)</h2><p>{weekly}</p><h2>Top modules by completed lesson records</h2>{modules}<p>Active records require active status and future expiry. These are not independently reconciled paid subscriptions or download-to-paid conversion. Engagement counts are records, not unique customers. Store downloads, trial/payment status, cancellations and revenue require separate sources. Counts use separate read queries and may differ during concurrent updates.</p>')
