"""Read-only Google Play monthly earnings reports; aggregate only."""
import csv
import html
import io
import os
import re
import zipfile
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from threading import Lock
from time import monotonic
from urllib.parse import quote

PACKAGES = {
    "routecast": "com.routecast.app",
    "emergent-vpn": "com.emergentvpn",
    "endoscopy-nurse-pro": "com.endoscopynursepro.app",
    "simple-background-remover": "com.hildrethtechnologies.simplebackgroundremover",
}
FIELDS = {"Package ID", "Transaction Type", "Merchant Currency", "Amount (Merchant Currency)"}
CACHE = {}
FAILURES = {}
FAILURE_SECONDS = 300
LOCK = Lock()
LIMIT = 20 * 1024 * 1024

def parse_earnings(payload):
    results = defaultdict(lambda: defaultdict(lambda: {"sales": Decimal(0), "fees": Decimal(0), "total": Decimal(0), "lines": 0}))
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        files = [f for f in archive.infolist() if not f.is_dir() and f.filename.lower().endswith(".csv")]
        if not files or sum(f.file_size for f in files) > 50 * 1024 * 1024:
            raise ValueError("Unexpected earnings archive")
        for f in files:
            raw = archive.read(f)
            encoding = "utf-16" if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
            reader = csv.DictReader(io.StringIO(raw.decode(encoding)))
            if not FIELDS.issubset(reader.fieldnames or []):
                raise ValueError("Unrecognized earnings columns")
            for row in reader:
                package = row["Package ID"].strip()
                if package not in PACKAGES.values():
                    continue
                currency = row["Merchant Currency"].strip()
                if not re.fullmatch(r"[A-Z]{3}", currency):
                    raise ValueError("Invalid currency")
                amount = Decimal(row["Amount (Merchant Currency)"].replace(",", "").strip())
                if not amount.is_finite():
                    raise ValueError("Invalid report amount")
                kind = row["Transaction Type"].strip().lower()
                entry = results[package][currency]
                entry["total"] += amount
                entry["lines"] += 1
                if kind in ("charge", "charge refund", "charge rebill"):
                    entry["sales"] += amount
                if kind in ("google fee", "google fee refund", "google fee rebill"):
                    entry["fees"] += amount
    return {p: dict(v) for p, v in results.items()}

class ReportError(Exception):
    pass

# Only these locally recognised codes are ever shown. Raw Google messages can
# contain account details, so they are never displayed.
HINTS = (
    ({"accessNotConfigured", "SERVICE_DISABLED", "serviceDisabled"}, "Cloud Storage API disabled in credential project"),
    ({"insufficientPermissions", "ACCESS_TOKEN_SCOPE_INSUFFICIENT"}, "OAuth scope insufficient"),
    ({"forbidden", "PERMISSION_DENIED"}, "permission denied"),
    ({"accountDisabled"}, "Google reports the account is disabled"),
    ({"notFound"}, "file or bucket not found"),
)

def error_details(response):
    """Return (reason codes, message text) from a JSON or plain-text error."""
    reasons, text = set(), ""
    try:
        raw = response.text
        text = raw[:4000] if isinstance(raw, str) else ""
    except Exception:
        pass
    try:
        err = response.json().get("error", {})
        text += " " + str(err.get("message", ""))
        reasons.add(err.get("status"))
        for key in ("errors", "details"):
            for item in err.get(key, []):
                if isinstance(item, dict):
                    reasons.add(item.get("reason"))
                    text += " " + str(item.get("message", ""))
    except Exception:
        pass
    return reasons, text

def check_response(response, stage="request"):
    if response.status_code == 200:
        return
    reasons, text = error_details(response)
    notes = []
    if "has not been used in project" in text:
        notes.append(HINTS[0][1])
    else:
        notes.extend([hint for codes, hint in HINTS if reasons & codes][:1])
    permission = re.search(r"storage\.(?:objects|buckets)\.(?:list|get)(?![A-Za-z])", text)
    if permission:
        notes.append("missing " + permission[0])
    hint = " (" + "; ".join(notes or ["Google gave no recognised reason"]) + ")"
    raise ReportError("Google Storage HTTP " + str(int(response.status_code)) + " during " + stage + hint)

def previous_month_report():
    previous = datetime.now(timezone.utc).replace(day=1) - timedelta(days=1)
    return "earnings/earnings_" + previous.strftime("%Y%m") + ".zip"

def report():
    uri = os.getenv("PLAY_EARNINGS_URI", "").strip()
    if not uri:
        return None
    match = re.fullmatch(r"gs://(pubsite_prod_[a-zA-Z0-9_-]+)/earnings/?", uri)
    if not match:
        raise ReportError("Invalid earnings storage URI")
    with LOCK:
        cached = CACHE.get(uri)
        if cached and monotonic() - cached[0] < 1800:
            return cached[1]
        failed = FAILURES.get(uri)
        if failed and monotonic() - failed[0] < FAILURE_SECONDS:
            raise ReportError(failed[1])
        listing_error = None
        stage = "loading Google libraries"
        try:
            import google.auth
            from google.auth.transport.requests import AuthorizedSession
            stage = "loading Google credentials"
            credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/devstorage.read_only"])
            endpoint = "https://storage.googleapis.com/storage/v1/b/" + quote(match[1], safe="") + "/o"
            names = []
            with AuthorizedSession(credentials) as session:
                params = {"prefix": "earnings/earnings_", "fields": "items(name,size),nextPageToken", "maxResults": 1000}
                for _ in range(5):
                    stage = "report listing"
                    with session.get(endpoint, params=params, timeout=12) as response:
                        if response.status_code == 403:
                            # Listing and reading are separate permissions, so still try
                            # one direct read, but keep the listing error for display.
                            try:
                                check_response(response, stage)
                            except ReportError as exc:
                                listing_error = str(exc)
                            names = [{"name": previous_month_report()}]
                            break
                        check_response(response, stage)
                        data = response.json()
                    names.extend(x for x in data.get("items", []) if re.fullmatch(r"earnings/earnings_[0-9]{6}\.zip", x.get("name", "")))
                    if not data.get("nextPageToken"):
                        break
                    params["pageToken"] = data["nextPageToken"]
                else:
                    raise ReportError("Too many reports; list incomplete")
                if not names:
                    raise ReportError("Report listing succeeded, but no filename matched earnings_YYYYMM.zip")
                newest = max(names, key=lambda x:x["name"])
                if int(newest.get("size", 0)) > LIMIT:
                    raise ReportError("Report exceeds size limit")
                stage = "monthly file download"
                with session.get(endpoint + "/" + quote(newest["name"], safe=""), params={"alt": "media"}, timeout=20, stream=True) as response:
                    check_response(response, stage)
                    chunks = bytearray()
                    for chunk in response.iter_content(chunk_size=65536):
                        chunks.extend(chunk)
                        if len(chunks) > LIMIT:
                            raise ReportError("Report exceeds size limit")
                stage = "reading the downloaded report"
                totals = parse_earnings(chunks)
            result = {"month": datetime.strptime(newest["name"][-10:-4], "%Y%m").strftime("%B %Y"), "totals": totals, "fetched": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "warning": listing_error}
        except Exception as exc:
            # Exception text can include paths or account details; show only the stage.
            if isinstance(exc, ReportError):
                message = str(exc)
            else:
                joiner = "while " if stage.startswith(("loading", "reading")) else "during "
                message = "Earnings report failed " + joiner + stage
            if listing_error:
                message = listing_error + ". Direct-file attempt also failed: " + message
            message += ". Last attempt " + datetime.now(timezone.utc).strftime("%H:%M UTC") + "; a new attempt is allowed after 5 minutes"
            FAILURES[uri] = (monotonic(), message)
            raise ReportError(message) from None
        FAILURES.pop(uri, None)
        CACHE[uri] = (monotonic(), result)
        return result

def render_play(product):
    if product not in PACKAGES:
        return ""
    title = "<h2>Google Play · monthly earnings</h2>"
    def panel(body):
        return '<section class="panel" style="margin:18px 0">'+title+body+'</section>'
    try:
        data = report()
    except ReportError as exc:
        return panel('<div class="pending">'+html.escape(str(exc))+' · Verify report access and configuration.</div>')
    except Exception:
        return panel('<div class="pending">Earnings report unavailable. Verify Google credentials, Cloud Storage access and report format.</div>')
    if data is None:
        return panel('<div class="pending">Google Play earnings reports not connected.</div>')
    rows = data["totals"].get(PACKAGES[product], {})
    body = ''
    if data.get("warning"):
        body += '<div class="pending">'+html.escape(data["warning"])+'. Showing one directly requested file; newer or additional files could not be checked.</div>'
    body += '<p>Latest available standard monthly statement: '+html.escape(data["month"])+' · fetched '+html.escape(data["fetched"])+'</p>'
    for currency, totals in sorted(rows.items()):
        body += '<div class="kpis">'+''.join(f'<section class="tile"><small>{label} ({currency})</small><strong>{totals[k]:,.2f}</strong></section>' for k,label in (("sales","Charges less refunds / rebills"),("fees","Google fee lines (signed)"),("total","Sum of app-attributed statement lines")) )+'</div>'
    if not rows:
        body += '<div class="pending">No lines attributed to this app in the statement. This is not a verified zero balance.</div>'
    return panel(body+'<p>Monthly finalized reports, not real-time sales. Includes all app product types; separate adjustment files and unallocated account-level amounts are not included. Statement sums are not confirmed bank deposits. Do not add RevenueCat revenue to overlapping Google Play earnings. Active subscriptions, installs and cancellations require separate data sources.</p>')
