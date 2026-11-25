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
