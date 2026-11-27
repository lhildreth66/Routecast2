"""Accessible daily session chart with missing dates left blank."""
from datetime import datetime, timedelta
import html
import math

def render_trend(rows):
    if rows is None:
        return '<section class="panel trend-panel"><h2>Website traffic over time</h2><p>Daily session report unavailable.</p></section>'
    values={}
    for raw,n in rows:
        try:
            day=datetime.strptime(raw,"%Y%m%d").date()
            if type(n) is not int or n<0:
                continue
            if day in values:
                continue
            values[day]=n
        except (ValueError,TypeError):
            continue
    if not values:
        return '<section class="panel trend-panel"><h2>Website traffic over time</h2><p>No daily session rows reported. This does not establish zero traffic.</p></section>'
    first,last=min(values),max(values)
    if (last-first).days>100:
        return '<section class="panel trend-panel"><h2>Website traffic over time</h2><p>Unexpected date range; chart unavailable.</p></section>'
    days=(last-first).days+1
    peak=max(values.values())
    peak_day=min(d for d,v in values.items() if v==peak)
    axis=max(1,math.ceil(peak/4)*4)
    left,right,top,bottom=58,932,22,212
    span=right-left
    width=span/days
    def y(n): return bottom-(bottom-top)*n/axis
    svg=['<svg viewBox="0 0 960 255" role="img" aria-label="Daily website sessions. Missing days have no bar." style="display:block;width:100%;height:auto;min-height:150px;font-family:system-ui,sans-serif">']
    ticks=sorted(set([0,axis//4,axis//2,axis*3//4,axis]))
    for n in ticks:
        yy=y(n)
        svg.append(f'<line x1="{left}" y1="{yy:.1f}" x2="{right}" y2="{yy:.1f}" stroke="#e2e8f0"/><text x="{left-10}" y="{yy+4:.1f}" text-anchor="end" font-size="12" fill="#53677b">{n:,}</text>')
    for d,n in sorted(values.items()):
        x=left+((d-first).days+.5)*width
        height=bottom-y(n)
        bw=min(38,width*.68)
        stamp=d.strftime("%b %d, %Y")
        svg.append(f'<rect x="{x-bw/2:.1f}" y="{y(n):.1f}" width="{bw:.1f}" height="{height:.1f}" rx="2" fill="#1668dc"><title>{stamp}: {n:,} sessions</title></rect>' if n else f'<circle cx="{x:.1f}" cy="{bottom}" r="2.5" fill="#1668dc"><title>{stamp}: 0 reported sessions</title></circle>')
    indexes=sorted({round((days-1)*i/4) for i in range(5)})
    for i in indexes:
        d=first+timedelta(days=i)
        x=left+(i+.5)*width
        svg.append(f'<text x="{x:.1f}" y="235" text-anchor="middle" fill="#53677b" font-size="12">{d.strftime("%b %d")}</text>')
    svg.append('</svg>')
    table=''.join(f'<tr><td>{d.strftime("%b %d, %Y")}</td><td style="text-align:right">{n:,}</td></tr>' for d,n in sorted(values.items(),reverse=True))
    return ('<section class="panel trend-panel"><h2>Website traffic over time</h2><p>Daily sessions · GA4 · reported dates only</p>'
            '<div style="display:flex;gap:24px;flex-wrap:wrap;margin:12px 0 8px">'
            f'<div><small>Sessions on reported dates</small><div style="font-size:26px;font-weight:750">{sum(values.values()):,}</div></div>'
            f'<div><small>Peak day · {peak_day.strftime("%b %d")}</small><div style="font-size:26px;font-weight:750">{peak:,}</div></div>'
            f'<div><small>Dates reported</small><div style="font-size:26px;font-weight:750">{len(values)}</div></div></div>'
            +''.join(svg)+
            '<p style="font-size:13px">Each bar is the number of sessions on that date, not a percentage. Missing days are not reported, not assumed zero. Today may be partial.</p>'
            '<details><summary style="cursor:pointer;font-weight:650;color:#155cba">View daily numbers</summary>'
            '<table style="width:100%;font-size:13px;margin-top:10px"><thead><tr><th style="text-align:left">Date</th><th style="text-align:right">Sessions</th></tr></thead><tbody>'+table+'</tbody></table></details></section>')
