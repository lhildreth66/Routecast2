"""Read-only GA4 aggregate reports for the owner console. Credentials never leave server."""
import os
import re
from datetime import datetime, timezone
from threading import Lock
from time import monotonic
from acquisition_view import collect

PROPERTIES = {
    "hildreth-technology": "GA4_HILDRETH_PROPERTY_ID",
    "patriot-news-us": "GA4_PATRIOT_PROPERTY_ID",
    "tikhooks2": "GA4_TIKHOOKS_PROPERTY_ID",
    "medpolicyref": "GA4_MEDPOLICYREF_PROPERTY_ID",
}
PERIODS = {"today": "today", "7": "6daysAgo", "30": "29daysAgo", "90": "89daysAgo"}
METRICS = ("totalUsers", "newUsers", "sessions", "screenPageViews", "averageSessionDuration", "bounceRate")
GROUPS = {
    "Visitor Sources": ("sessionSourceMedium", "sessions"),
    "Visitor Geography": ("country", "sessions"),
    "Most Visited Pages": ("pagePath", "screenPageViews"),
    "Device Breakdown": ("deviceCategory", "sessions"),
    "Recent Trends": ("date", "sessions"),
}
CACHE = {}
LOCK = Lock()

def property_id(product):
    value = os.getenv(PROPERTIES.get(product, ""), "").strip()
    return value if re.fullmatch(r"[1-9][0-9]{0,15}", value) else None

def report(product, period="30"):
    prop = property_id(product)
    if not prop:
        return None
    start = PERIODS[period]
    cache_key = (product, prop, period)
    with LOCK:
        cached = CACHE.get(cache_key)
        if cached and monotonic() - cached[0] < 300:
            return cached[1]
    from google.analytics.data_v1beta import BetaAnalyticsDataClient
    from google.analytics.data_v1beta.types import RunReportRequest, DateRange, Metric, Dimension, OrderBy
    import google.auth
    credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/analytics.readonly"])
    client = BetaAnalyticsDataClient(credentials=credentials)
    def query(metrics, dimension=None):
        options = dict(property="properties/" + prop, date_ranges=[DateRange(start_date=start, end_date="today")],
                       metrics=[Metric(name=m) for m in metrics], limit=100 if dimension=="date" else 10)
        if dimension:
            options["dimensions"] = [Dimension(name=dimension)]
            if dimension=="date":
                options["order_bys"] = [OrderBy(dimension=OrderBy.DimensionOrderBy(dimension_name="date"))]
            else:
                options["order_bys"] = [OrderBy(metric=OrderBy.MetricOrderBy(metric_name=metrics[0]), desc=True)]
        response = client.run_report(RunReportRequest(**options), timeout=12)
        if getattr(response.metadata, "subject_to_thresholding", False):
            return None
        return response.rows
    rows = query(METRICS)
    totals = dict(zip(METRICS, [v.value for v in rows[0].metric_values])) if rows else {}
    groups = {}
    for name, (dim, metric) in GROUPS.items():
        try:
            group = query([metric], dim)
            groups[name] = [(row.dimension_values[0].value, int(row.metric_values[0].value)) for row in group] if group else []
        except Exception:
            groups[name] = None
    try:
        acquisition = collect(client, prop, start)
    except Exception:
        acquisition = {}
    result = {"totals": totals, "groups": groups, "acquisition": acquisition, "fetched": datetime.now(timezone.utc).isoformat(), "period": period}
    if product == "tikhooks2":
        from tikhooks_view import collect_journey
        try:
            result["tikhooks_journey"] = collect_journey(client, prop, start)
        except Exception:
            result["tikhooks_journey"] = None
    with LOCK:
        CACHE[cache_key] = (monotonic(), result)
    return result
