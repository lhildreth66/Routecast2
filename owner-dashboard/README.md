# RouteCast Owner Dashboard — Friday setup

Approved design: blue-and-white desktop owner console, left navigation, subscriber KPI cards, subscriber-source donut, most-used features, recent suggestions, and trends. Match the approved November 25 mockup; scenic branding, interactive filters and charts can be added in later iterations. Never populate production panels with sample statistics.

## Friday, November 27, 2026: first private session

1. Open your trusted RouteCast GitHub Codespace. Ensure no uncommitted work would be overwritten before switching branches.
2. In the terminal run:
   ```bash
   git fetch origin
   git switch routecast-owner-dashboard-v1
   python3 -m py_compile owner-dashboard/dashboard.py
   python3 owner-dashboard/dashboard.py
   ```
   If the branch is not yet local, use `git switch --track origin/routecast-owner-dashboard-v1`.
3. If prompted, enter the production ADMIN_API_KEY from the Render routecast-backend environment. The terminal prompt hides it. Never paste it into chat, source code, a GitHub issue, a URL, or browser JavaScript.
4. In Codespaces Ports, forward port 8765 and verify visibility is Private. Open the forwarded HTTPS address. Use the temporary dashboard login shown in the terminal (username owner).
5. Refresh and confirm Apple and Google counts, trial accounts, and complimentary grants. Compare against App Store Connect and Google Play Console. The existing backend counts active status, not independently verified paid entitlements; canceled-but-unexpired subscriptions may be omitted.
6. Stop with Ctrl+C. This preview is not permanent hosting; the temporary dashboard password changes each launch.

## Next implementation phases

- Reconcile subscription statuses with platform records and distinguish paid/trial/granted/test accounts; add daily snapshots and historical reporting.
- Audit current mobile analytics implementation. Older frontend documentation describes local-only analytics, but the referenced analytics.ts file was absent at the inspected path. Do not assume centralized tracking exists. Add first-party, authenticated, batched and idempotent event ingestion using the existing backend and database. Collect only allowlisted event names, coarse platform/version, timestamp and pseudonymous account ID; no precise coordinates or unnecessary identifiers. Measure distinct users and actual feature use separately from attempted access. Review privacy disclosures and retention.
- Add Suggestions to the mobile app for current and future users, with categories, optional contact permission, input validation, rate limits, and acknowledgment. Owner inbox should support status, filtering, export, and private notes. No public posting by default.
- Deploy a separate production owner console only after validating auth, permissions, TLS, tests, secret storage, and hosting configuration. The proposed address is admin.routecastweather.com, not yet configured. No administrator secrets in client-side code. No Google Analytics or paid external analytics services.
- Keep existing mobile functionality unchanged until tested. Do not merge or deploy this branch automatically.

Current branch contains a read-only subscriber preview and design placeholders. It does not yet collect usage events, customer suggestions or live trends. Production authentication and runtime tests remain to be completed.


## Hildreth Technologies portfolio (owner-confirmed product types)

One private, responsive owner console with separate tabs and an all-products overview.

| Product | Type | Data source to connect |
| --- | --- | --- |
| RouteCast | Mobile app | Existing backend stats, Apple App Store Connect, Google Play Developer API and first-party feature events |
| Emergent VPN | Mobile app | Its own billing/backend and applicable Apple/Google subscription data |
| Endoscopy Nurse Pro | Mobile app | Its own backend and applicable Apple/Google data |
| Simple Background Remover | Mobile app in testing | Test metrics separately; include production metrics only when published |
| MedPolicyRef | Website / SaaS | Its own account database, website billing and first-party web usage events |
| Patriot News US | Website | Its own account database, website billing and first-party web usage events |
| TikHooks2 | Website | Its own account database, website billing and first-party web usage events |

Confirm actual app-store publication and backend/billing providers before connecting. Do not assume each product uses the same database or payment provider. Mobile dashboards distinguish Apple and Google; website dashboards use web registrations, active accounts, visitors, conversions, paid subscriptions and revenue. Visitor counts need privacy-conscious first-party instrumentation if not currently recorded. Keep source definitions and dates explicit; missing metrics show unavailable, not zero. Portfolio totals count subscriptions, not unique people across products, unless deduplication is justified and implemented.

Use server-side read-only integration adapters and separate scoped credentials where feasible, never public source or browser-side secrets. Suggestions and feature usage should be tagged by product. For VPN analytics collect only coarse app feature usage, never browsing history, traffic destinations, or connection content.

The prototype now includes navigation and type-specific dashboard layouts. Only RouteCast has a prepared live-data adapter; no other product integrations or verified live counts yet. No production changes or permanent hosting. Add installable PWA manifest/icons and secure HTTPS hosting after authentication and testing are complete.


## Corporate website and first-party web analytics

HildrethTechnology.com is a separate website dashboard, making eight products/website tabs in addition to the portfolio overview. The corporate site's private repository was inspected: frontend pages include Home, About, OurWork, Contact, Privacy, Terms and NotFound; the existing FastAPI backend stores contact submissions. No visitor analytics endpoint was identified in the inspected backend. Connect aggregate contact metrics through an authenticated read-only adapter; never copy contact message bodies into analytics. Do not treat the corporate website as a subscription app or invent a signup funnel for it.

For HildrethTechnology.com and all applicable website businesses, implement first-party analytics with:
- Monthly unique visitor estimates (pseudonymous browser identifiers where consent permits), sessions, page views, new/returning visitors, active engagement time, bounce rate (define explicitly as non-engaged sessions), landing and exit pages, date comparisons.
- Referring domain, sanitized campaign tags (UTM source/medium/campaign), broad channel, direct/unknown, approximate country/region, device and browser categories. Do not store full referrer URLs, query strings, precise location, or raw IPs for analytics.
- Page performance and conversion funnels: page view, product-link click, contact start/success/failure for corporate site; signup start, step completion, validation error, verification, checkout and confirmed purchase where those steps actually exist on other sites. Measure time between steps and distinguish attempted from completed events.
- Allowlisted client/server error codes, HTTP failures and timing buckets; no passwords, form contents, payment data, session replay, keystrokes, or personal search strings. Correlate aggregate abandonment and errors without claiming causal proof. Offer optional explicit feedback for reported reasons.
- Filter known bots and owner/test traffic, make collection consent-aware, define retention and deletion, and document measurement limitations (blocked tracking, missing referrers, multiple devices, small geographic cohorts). No Google Analytics or external analytics platform.
- Show monthly traffic, acquisition channels, geographic breakdown, engagement, most visited pages, conversion and error panels; corporate product outbound clicks and contact completion, not Apple/Google subscribers. Attribute downstream conversions only where a privacy-conscious supported attribution mechanism is implemented.
- Use shared event schema with product ID, timestamp, event type, normalized page/feature ID, coarse context and opaque event ID; separate authenticated collection/aggregation boundaries per product. Protect against spam, duplicate events, and unauthorized dashboard access. Keep metrics unavailable until actual events or verified records exist.

This update adds corporate and web-specific dashboard layouts only. No visitor tracking, contact-count adapter, historical import, production deployment, or website code changes have been made yet. Test syntax, auth, event schema and UI before release.
