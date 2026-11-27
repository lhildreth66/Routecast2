"""Read-only aggregate Endoscopy Nurse Pro dashboard."""
import html
import json
import os
import re
from datetime import datetime, timezone
from threading import Lock
from time import monotonic
from urllib.request import Request, build_opener, HTTPRedirectHandler

PRODUCT = "endoscopy-nurse-pro"
URL = "https://endoscopy-nurse-pro-api.onrender.com/api/owner/reporting"
KEY_NAME = "ENDOSCOPY_REPORTING_KEY"
KEY_FORMAT = re.compile(r"[\x21-\x7e]{32,}")
SUCCESS_SECONDS = 300
FAILURE_SECONDS = 60
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
FAILURE = None
LAST_SUCCESS = None


class ReportingUnavailable(Exception):
    """A recent attempt failed; the next attempt is deferred."""


def reset():
    global CACHE, FAILURE, LAST_SUCCESS
    with LOCK:
        CACHE = FAILURE = LAST_SUCCESS = None


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
    global CACHE, FAILURE, LAST_SUCCESS
    key = os.getenv(KEY_NAME, "").strip()
    if not key:
        return None
    if not KEY_FORMAT.fullmatch(key):
        raise ValueError("Invalid key configuration")
    # One lock: concurrent page loads wait for a single attempt, then share its outcome.
    with LOCK:
        now = monotonic()
        if CACHE and now - CACHE[0] < SUCCESS_SECONDS:
            return CACHE[1]
        if FAILURE is not None and now - FAILURE < FAILURE_SECONDS:
            raise ReportingUnavailable("Recent attempt failed")
        try:
            req = Request(URL, headers={"X-Reporting-Key": key, "Accept": "application/json"})
            with build_opener(NoRedirect()).open(req, timeout=16) as response:
                raw = response.read(32769)
            if len(raw) > 32768:
                raise ValueError("Response too large")
            result = validate(json.loads(raw))
        except Exception:
            FAILURE = monotonic()
            raise
        CACHE, FAILURE, LAST_SUCCESS = (monotonic(), result), None, result[1]
        return result


STYLE = ('<style>.endo-h{margin:22px 0 4px;font-size:16px}.endo-note{margin:0 0 10px;font-size:13px}'
         '.endo-scroll{overflow-x:auto}.endo-table{width:100%;border-collapse:collapse;font-size:14px}'
         '.endo-table th,.endo-table td{text-align:left;padding:9px 10px;border-bottom:1px solid #edf1f6}'
         '.endo-table th{color:#31465e;font-size:13px}.endo-table .num{text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}'
         '.endo-bar{background:#e4ebf3;border-radius:5px;height:10px;min-width:80px}'
         '.endo-bar i{display:block;height:10px;border-radius:5px;background:#1668dc}</style>')
GROUPS = (
    ("Registered users", "All accounts created in the app, whether or not they ever subscribed.", ("registered", "new_30d")),
    ("Active subscription records", "Backend records with active status and a future expiry. Not checked against Apple, Google or RevenueCat, so not confirmed paying subscribers.",
     ("active", "apple", "android", "monthly", "annual", "no_expiry")),
    ("Learning activity", "Records, not unique customers.", ("lessons", "videos", "quizzes", "simulations", "bookmarks")),
)


def tile(label, value):
    return f'<section class="tile"><small>{label}</small><strong>{value}</strong></section>'


def stamp_text(stamp):
    return html.escape(stamp.isoformat())


def unavailable():
    last = f"Last successful report: {stamp_text(LAST_SUCCESS)}." if LAST_SUCCESS else "No successful report since this dashboard started."
    return ('<div class="pending">Backend reporting unavailable. No counts are shown and no zero values are assumed. '
            'Verify the dedicated key and reporting endpoint; a new attempt is made at most once per minute. ' + last + '</div>')


def weekly_table(counts):
    peak = max(counts[k] for k in WEEKS)
    rows = ''
    for i, k in enumerate(WEEKS, 1):
        width = 100 * counts[k] / peak if peak else 0
        rows += (f'<tr><td>Days {35 - 7 * i}–{28 - 7 * i} before snapshot</td><td class="num">{counts[k]:,}</td>'
                 f'<td><div class="endo-bar"><i style="width:{width:.1f}%"></i></div></td></tr>')
    return ('<h3 class="endo-h">Weekly registrations</h3><p class="endo-note">Four consecutive 7-day periods, oldest first.</p>'
            '<div class="endo-scroll"><table class="endo-table"><thead><tr><th>Period</th><th class="num">Registrations</th><th>Relative</th></tr></thead>'
            f'<tbody>{rows}</tbody></table></div>')


def modules_table(rows):
    if not rows:
        return '<h3 class="endo-h">Popular training modules</h3><p>No completed lesson records for known modules.</p>'
    body, rank = '', 0
    for i, (title, count) in enumerate(rows, 1):
        if i == 1 or count != rows[i - 2][1]:
            rank = i
        body += f'<tr><td class="num">{rank}</td><td>{html.escape(title)}</td><td class="num">{count:,}</td></tr>'
    return ('<h3 class="endo-h">Popular training modules</h3><p class="endo-note">Ranked by completed lesson records.</p>'
            '<div class="endo-scroll"><table class="endo-table"><thead><tr><th class="num">Rank</th><th>Module</th><th class="num">Completed lessons</th></tr></thead>'
            f'<tbody>{body}</tbody></table></div>')


def render_endoscopy(product):
    if product != PRODUCT:
        return ""
    def panel(body):
        return '<section class="panel" style="margin-bottom:18px"><h2>Endoscopy Nurse Pro · backend reporting</h2>'+body+'</section>'
    try:
        data = fetch()
    except Exception:
        return panel(unavailable())
    if data is None:
        return panel('<div class="pending">Backend reporting not connected.</div>')
    counts, stamp, rows = data
    ratio = f'{100*counts["active"]/counts["registered"]:.2f}%' if counts["registered"] else '—'
    sections = ''
    for title, note, keys in GROUPS:
        tiles = ''.join(tile(LABELS[k], f'{counts[k]:,}') for k in keys)
        if title == "Active subscription records":
            tiles += tile("Active records / registered users", ratio)
        sections += f'<h3 class="endo-h">{title}</h3><p class="endo-note">{note}</p><div class="kpis">{tiles}</div>'
        if title == "Active subscription records":
            sections += ('<h3 class="endo-h">Verified paying subscribers</h3>'
                         '<div class="pending">Not connected. Requires verified App Store, Google Play or RevenueCat data; no figure is estimated here.</div>')
    return panel(STYLE + f'<p>Last successful report: <strong>{stamp_text(stamp)}</strong> (UTC). Backend and dashboard caches combined can make this data up to about 6 minutes old.</p>'
                 + sections + weekly_table(counts) + modules_table(rows)
                 + '<p>Registered users, active subscription records and verified paying subscribers are different measures. Active records are not independently reconciled paid subscriptions or download-to-paid conversion. Store downloads, trial/payment status, cancellations and revenue require separate sources. Counts use separate read queries and may differ during concurrent updates.</p>')
