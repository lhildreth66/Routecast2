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


## Updated web analytics strategy — existing Google Analytics properties (owner confirmation, Nov 25)

This supersedes the earlier blanket plan to avoid Google Analytics as a data source: the owner wants a first-party dashboard UI, not to use Google's reporting interface. The owner reports existing Google Analytics accounts/properties for HildrethTechnology.com and Patriot News US, and possibly TikHooks2. Property IDs, permissions, active tagging, historical coverage and exact property-to-domain mapping remain unverified. Keep first-party event collection available for missing metrics and products without GA4.

- Use the official GA4 Data API (read-only), not scraping or embedding Google's UI. On Friday, verify GA4 numeric property IDs (not G- measurement IDs) and property-to-host mappings, enable Data API in Google Cloud, grant a dedicated service account Viewer access to each authorized property, and store credentials in server-side secrets only (never GitHub, browser, or chat). Use the analytics.readonly scope; consider keyless credentials where supported. Verify access and test a report before production deployment.
- Pull aggregate report data via runReport/batchRunReports. Support date ranges today, 7/30/90 days, calendar month, prior period and custom range. Show totalUsers/activeUsers with explicit definitions, newUsers, sessions, screenPageViews, bounceRate, engagementRate, averageSessionDuration and engaged time where compatible; use sessionSourceMedium/sessionDefaultChannelGroup, country/region, deviceCategory, landingPage and normalized page paths. Do not sum daily unique users for monthly unique users. Query date-range totals directly; handle thresholding, missing data, quota and processing delay. Avoid full URLs/query strings or small identifying cohorts.
- Show historical data where collected and available, data source label and last successful sync; use cached aggregates with clear freshness and no fabricated zeroes. GA4 data is not necessarily real-time, complete or a source of truth for paid subscriptions. Use product billing records for actual subscriptions, conversions and revenue, reconciling definitions before aggregating.
- Website funnels and error diagnosis require relevant events already instrumented or added later. Corporate site funnel: product clicks and contact submissions. Other websites: registration, validation, email verification, checkout, payment and confirmation as applicable. Combine GA4 aggregates with privacy-conscious first-party error counts; no passwords, form content, payment data, raw IPs or session replay. Correlation is not proof of cause.
- Do not add a new GA4 tag or change existing properties without reviewing current tracking/consent and owner approval. Avoid duplicate events and double-counting between sources. Existing GA4 is optional for each product; mobile app analytics still use first-party events and store/billing APIs where appropriate.
- Official docs: https://developers.google.com/analytics/devguides/reporting/data/v1/quickstart and https://developers.google.com/analytics/devguides/reporting/data/v1/api-schema .

Status: requirements recorded only; GA4 connector, credentials, property verification, actual reports, tests and live deployment are not yet complete.

## November 26: launch preparation

The website tabs now include a server-side GA4 report adapter and PWA assets. Install dependencies with `python -m pip install -r owner-dashboard/requirements.txt`, then run `python -m unittest discover -s owner-dashboard -p 'test_*.py' -v`. The GA4 properties use the numeric IDs in GA4_HILDRETH_PROPERTY_ID, GA4_PATRIOT_PROPERTY_ID, GA4_TIKHOOKS_PROPERTY_ID and GA4_MEDPOLICYREF_PROPERTY_ID. Set Google application credentials using a server-side secret file and GOOGLE_APPLICATION_CREDENTIALS; give its service account Viewer permission for each selected GA4 property and enable the GA4 Data API. Never commit keys or passwords. Verify property-to-domain mapping before connecting.

For an isolated Render web service, use branch routecast-owner-dashboard-v1, root directory owner-dashboard, build command `pip install -r requirements.txt`, start command `python dashboard.py`, and environment DASHBOARD_HOSTED=1, a randomly generated DASHBOARD_PASSWORD of at least 24 characters, and optional ADMIN_API_KEY (RouteCast backend only). Use HTTPS and validate login, access controls and actual counts before opening the dashboard to routine use. Confirm hosting plan/cost before creating the service. Do not change the existing RouteCast service. The public assets are only icons, manifest and a non-caching worker; business pages require authentication. Browser installation is subject to Chrome/Edge support and verified HTTPS. No public deployment or production data connection has been performed.


## Endoscopy Nurse Pro backend reporting (read-only)

The existing private owner dashboard at /apps/endoscopy-nurse-pro retrieves only aggregate counts directly from MongoDB. No extra service, no changes to the Endoscopy backend or mobile app. No database writes or migrations. The other product pages do not use this connection.

Configure only the existing hildreth-dashboard Render service with ENDOSCOPY_MONGO_URL (the URI of a separate MongoDB user with solely the built-in read role on the application database) and ENDOSCOPY_DB_NAME (the verified database name). Do not reuse the application's write-enabled URI. Never paste credentials in chat, commit them or expose them to the browser. Restrict network access to the dashboard's necessary egress addresses. TLS is required. The adapter verifies the authenticated user's exact read role before each snapshot. If either variable is missing, no connection is attempted. Invalid, unauthorized or failed requests show unavailable without invented counts.

The 17 validated metrics, module counts and labels remain the same. Active subscription records are not independently verified paid subscriptions. Weekly windows are four consecutive seven-day periods, oldest first. Query load is bounded: a 12-second client deadline, sequential counts, small pool, five-minute success cache, one-minute failure cooldown. Real query load and Atlas compatibility need live verification with the dedicated read-only credential.

Deployment: after isolated tests and approval, release only to routecast-owner-dashboard-v1. Do not change gi-nurse-trainer main, the live Endoscopy service or its environment, billing, public websites or any other dashboard settings. Set the two new variables only on hildreth-dashboard, then verify actual counts and timestamp with the owner. To disable the integration, remove those variables from the dashboard; configuration changes may restart the dashboard. The Endoscopy application is not redeployed.
