"""Aggregate GA4 acquisition reporting. No raw IP or full referrer URL stored."""
import html
import re
from urllib.parse import urlsplit

SPECS = (
    ("Acquisition channels", "sessionDefaultChannelGroup", ("sessions", "engagedSessions")),
    ("Engagement by traffic source", "sessionSourceMedium", ("sessions", "engagedSessions")),
    ("Campaigns", "sessionCampaignName", ("sessions", "engagedSessions")),
    ("First acquisition source", "firstUserSourceMedium", ("newUsers",)),
    ("New vs. returning sessions", "newVsReturning", ("sessions",)),
    ("Landing pages", "landingPage", ("sessions", "engagedSessions")),
    ("Referring domains", "pageReferrer", ("screenPageViews",)),
)
SITES = {"hildreth-technology": "https://hildrethtechnology.com/",
         "medpolicyref": "https://medpolicyref.com/",
         "patriot-news-us": "", "tikhooks2": ""}


def safe_label(value, dimension):
    value = str(value).strip()
    if dimension == "pageReferrer":
        try:
            parsed = urlsplit(value)
            host = parsed.hostname
            if parsed.scheme not in ("http", "https") or not host:
                return None
            if not re.fullmatch(r"[A-Za-z0-9.-]{1,253}", host):
                return None
            return host.lower()
        except ValueError:
            return None
    if dimension == "landingPage":
        # Do not display query strings, tokens, numeric IDs or private paths.
        if value == "(not set)":
            return value
        if not re.fullmatch(r"/[A-Za-z/_-]{0,120}", value):
            return "(other or redacted path)"
        return value
    # Reject obvious URLs, identifiers, email addresses or arbitrary long strings.
    if len(value) > 100 or "@" in value or "://" in value or "?" in value:
        return "(redacted)"
    if not re.fullmatch(r"[A-Za-z0-9 ._()/&:+-]{1,100}", value):
        return "(redacted)"
    return value or "(not set)"


def normalize(response, spec):
    title, dim, metrics = spec
    if getattr(response.metadata, "subject_to_thresholding", False):
        return None
    result = {}
    for row in response.rows:
        label = safe_label(row.dimension_values[0].value, dim)
        if label is None:
            continue
        values = tuple(int(m.value) for m in row.metric_values)
        if len(values) != len(metrics) or any(v < 0 for v in values):
            raise ValueError("Invalid GA4 report")
        if label not in result:
            result[label] = [0] * len(values)
        # Add only additive counts. First acquisition rows use new users by source.
        for i, v in enumerate(values):
            result[label][i] += v
    return sorted(result.items(), key=lambda x: (-x[1][0], x[0]))[:30]


def collect(client, prop, start):
    from google.analytics.data_v1beta.types import (BatchRunReportsRequest, RunReportRequest,
        DateRange, Metric, Dimension, OrderBy)
    result = {}
    # A batch supports up to five reports. Optional failures must not affect traffic totals.
    for offset in (0, 5):
        subset = SPECS[offset:offset+5]
        requests = [
            RunReportRequest(property="properties/"+prop,
                date_ranges=[DateRange(start_date=start, end_date="today")],
                dimensions=[Dimension(name=dim)], metrics=[Metric(name=m) for m in metrics],
                order_bys=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name=metrics[0]), desc=True)],
                limit=100)
            for _, dim, metrics in subset
        ]
        try:
            response = client.batch_run_reports(
                BatchRunReportsRequest(property="properties/"+prop, requests=requests),
                timeout=6, retry=None)
            if len(response.reports) != len(subset):
                raise ValueError("Unexpected report count")
        except Exception:
            result.update({spec[0]: None for spec in subset})
            continue
        for spec, report in zip(subset, response.reports):
            try:
                result[spec[0]] = normalize(report, spec)
            except Exception:
                result[spec[0]] = None
    return result


def render_acquisition(data):
    if "acquisition" not in data:
        return ""
    panels = []
    descriptions = {
        "Acquisition channels": "Session channel, including direct, email, referral, paid and organic sources.",
        "Engagement by traffic source": "Sessions by source / medium, with engaged sessions and engagement rate.",
        "Campaigns": "Session campaign, including tagged links; untagged visits may be direct or not set.",
        "First acquisition source": "New users by their first recorded source / medium.",
        "New vs. returning sessions": "Session breakdown, not unique people.",
        "Landing pages": "First page in a session. Query strings and potentially identifying paths are omitted.",
        "Referring domains": "Page-view referrers, including internal navigation; not a count of external referrals or unique visitors.",
    }
    for name, dim, metrics in SPECS:
        rows = data["acquisition"].get(name)
        if rows is None:
            body = '<div class="pending">Report unavailable or withheld by Google.</div>'
        elif not rows:
            body = '<p>No reportable rows.</p>'
        else:
            heads = ["Source / group", "New users" if metrics[0]=="newUsers" else
                     "Page views" if metrics[0]=="screenPageViews" else "Sessions"]
            if len(metrics)==2:
                heads += ["Engaged", "Engagement"]
            trs = []
            for label, counts in rows:
                values = [f"{n:,}" for n in counts]
                if len(counts)==2:
                    values.append(f"{counts[1]/counts[0]*100:.1f}%" if counts[0] else "—")
                trs.append("<tr><td style='overflow-wrap:anywhere'>"+html.escape(label)+"</td>"+
                           "".join("<td style='text-align:right'>"+v+"</td>" for v in values)+"</tr>")
            body = '<div style="overflow-x:auto"><table style="width:100%;font-size:13px"><thead><tr>'
            body += "".join("<th>"+h+"</th>" for h in heads)+"</tr></thead><tbody>"+"".join(trs)+"</tbody></table></div>"
        panels.append('<section class="panel"><h2>'+name+'</h2><p>'+descriptions[name]+'</p>'+body+'</section>')
    return '<h2 style="margin:20px 0 12px">Detailed visitor acquisition</h2><div class="columns">'+"".join(panels)+'</div><p>Top reported rows; Google may withhold small groups. Direct / none means the source is unknown, not necessarily a typed address. Campaign links identify a traffic source, not a person. No raw IP addresses are available from GA4.</p>'


def render_link_generator(product):
    if product not in SITES:
        return ""
    destination = html.escape(SITES[product], quote=True)
    return f"""<section class="panel" style="margin:18px 0"><h2>Tracking link generator</h2>
<p>Tag links you share in email, social media or ads to see their traffic in the Campaigns report. Use general campaign labels, never names, emails or other personal information.</p>
<div id="utm-builder" style="display:grid;gap:10px;max-width:720px">
<label>Destination website<input id="utm-url" type="url" value="{destination}" placeholder="https://your-website.com/" style="display:block;width:100%;padding:9px;box-sizing:border-box"></label>
<label>Source<input id="utm-source" maxlength="80" placeholder="outlook, linkedin, newsletter" style="display:block;width:100%;padding:9px;box-sizing:border-box"></label>
<label>Medium<select id="utm-medium" style="display:block;width:100%;padding:9px"><option>email</option><option>social</option><option>referral</option><option>cpc</option><option>organic</option><option>other</option></select></label>
<label>Campaign<input id="utm-campaign" maxlength="80" placeholder="career_outreach, launch_2026" style="display:block;width:100%;padding:9px;box-sizing:border-box"></label>
<label>Content (optional)<input id="utm-content" maxlength="80" placeholder="newsletter_banner" style="display:block;width:100%;padding:9px;box-sizing:border-box"></label>
<button type="button" id="utm-generate" class="refresh" style="width:fit-content;border:0;cursor:pointer">Generate link</button>
<label>Generated URL<textarea id="utm-output" readonly rows="3" style="display:block;width:100%;box-sizing:border-box;padding:9px"></textarea></label>
<button type="button" id="utm-copy" class="refresh" style="width:fit-content;border:0;cursor:pointer">Copy link</button><p id="utm-status" role="status"></p>
</div><script src="/utm-builder.js" defer></script><p>Generated in your browser; nothing is sent or saved by this tool. Google Analytics can attribute visits only if the destination already has analytics and visitors permit collection.</p></section>"""


UTM_JS = r"""
(() => {
  "use strict";
  const el = id => document.getElementById("utm-" + id);
  if (!el("builder")) return;
  const status = message => { el("status").textContent = message; };
  const tag = value => {
    const v = value.trim();
    if (!/^[A-Za-z0-9_-]{1,80}$/.test(v)) throw new Error("Use letters, numbers, hyphens or underscores in tags.");
    return v;
  };
  el("generate").addEventListener("click", () => {
    el("output").value = "";
    try {
      const u = new URL(el("url").value.trim());
      if (u.protocol !== "https:" || u.username || u.password) throw new Error("Enter a public HTTPS website URL.");
      u.searchParams.set("utm_source", tag(el("source").value));
      u.searchParams.set("utm_medium", tag(el("medium").value));
      u.searchParams.set("utm_campaign", tag(el("campaign").value));
      const content = el("content").value.trim();
      if (content) u.searchParams.set("utm_content", tag(content));
      else u.searchParams.delete("utm_content");
      el("output").value = u.toString();
      status("Link ready to copy.");
    } catch (e) { status(e instanceof Error ? e.message : "Invalid URL or tags."); }
  });
  el("copy").addEventListener("click", async () => {
    if (!el("output").value) { status("Generate a link first."); return; }
    try {
      await navigator.clipboard.writeText(el("output").value);
      status("Link copied.");
    } catch (_) {
      el("output").focus(); el("output").select();
      status("Press Ctrl+C or use your device's Copy command.");
    }
  });
})();
""".encode("utf-8")
