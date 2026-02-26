# Routecast2 — Validation Checklist
**Generated:** 2026-02-24  
**Last commit:** `ef81cbeb`

---

## Code Changes Shipped (all pushed to `main`)

| Commit | Description |
|---|---|
| `77fc64dd` | Hard paywall: verify → Stripe → login flow |
| `d76c33ac` | Bridge height OSM pipeline wired end-to-end |
| `7989db2c` | Paywall correctness: webhook sub fetch, checkout 403 guard, /account whitelist, polling stop |
| `cd9ea18e` | Webhook: guard `checkout.session.completed` to `mode=subscription` only |
| `ef81cbeb` | Bridge cache: ceiling rounding for height buckets + 24 deterministic unit tests |

---

## Manual Confirmation Required

### 1. Render Deploy SHA
Go to **Render Dashboard → each service → Deploys** and confirm the deployed commit.

| Service | Required SHA (or later) | What it includes |
|---|---|---|
| **Backend** | `ef81cbeb` | Bridge wiring, checkout 403 guard, webhook mode guard, ceiling rounding |
| **Frontend** | `7989db2c` | Paywall guards, /account whitelist, polling stop |

If either service shows an older SHA, trigger a manual redeploy.

---

### 2. Stripe Webhook Events
Go to **Stripe Dashboard → Developers → Webhooks → your endpoint** and confirm:

- [ ] `checkout.session.completed` — critical, unlocks premium on trial start
- [ ] `customer.subscription.created` — backup activation path
- [ ] `customer.subscription.updated` — renewals and cancellations
- [ ] `customer.subscription.deleted` — revokes premium

Also confirm:
- **Endpoint URL** ends in `/api/webhooks/stripe` pointed at your live Render backend domain
- **`STRIPE_WEBHOOK_SECRET`** env var on Render matches the signing secret shown in the Stripe webhook detail page

---

### 3. Bridge Cards Proof Test

Use the **"11'8" bridge" in Durham, NC** — the most-filmed low-clearance railroad bridge in the US, with a dedicated Wikipedia article and reliably tagged in OSM with `maxheight=3.76` (12'4" after its 2019 raise). A 13.5 ft vehicle has a **−1.17 ft margin** → guaranteed DANGER alert and reroute flag.

**Test route:**
- **From:** `201 S Gregson St, Durham, NC 27701`
- **To:** `605 N Gregson St, Durham, NC 27701`
- **Vehicle height:** `13.5 ft`

Both addresses are on Gregson St itself — one block south and two blocks north of the bridge. Any routing engine keeps you on Gregson St for this one-mile trip and drives directly under it.

**Pass conditions:**
- [ ] `bridge_clearance_alerts` array in the route response JSON is non-empty
- [ ] Bridge card shows `clearance_ft ≈ 12.3`, `vehicle_height_ft = 13.5`, `margin_ft ≈ -1.2`
- [ ] `warning_level = "danger"` and warning text contains `"DANGER"`
- [ ] Red reroute banner appears on the route screen

To inspect the raw payload: **DevTools → Network → route POST request → response → search `bridge_clearance_alerts`**

---

### 4. Trial Webhook Proof Test
1. Create a brand new user account
2. Verify email
3. Complete Stripe trial checkout (enters card, clicks subscribe)
4. In **Stripe Dashboard → Webhooks → Event deliveries**, find `checkout.session.completed` — confirm HTTP 200 response
5. In **MongoDB Atlas**, check the user document:

```json
{
  "is_premium": true,
  "subscription_status": "trialing",
  "stripe_subscription_id": "sub_..."
}
```

**Pass condition:** `is_premium = true` and `subscription_status = "trialing"` within 30 seconds of the checkout redirect — without the user needing to revisit the site.

---

### 5. Checkout 403 Guard Test
1. Create a user account — **do not verify email**
2. Open DevTools → Network tab
3. Navigate to `/subscription` in the app
4. Find the `POST /api/subscription/checkout` request

**Pass condition:** HTTP `403` with body:
```json
{ "detail": "Email address must be verified before starting a subscription." }
```

---

## Addendum: 3 Gotchas That Cause False Negatives

### A) Clear Cache Before Any Proof Test (Web)

You've already seen service worker caching hide deployed updates. Before running any test on the web app:

1. **Chrome DevTools → Application → Service Workers** — click **Unregister** for `routecastweather.com`
2. **Application → Storage** — click **Clear site data**
3. Hard reload: `Ctrl+Shift+R`

Without this, you may be testing a stale build that predates the fix you're trying to validate.

---

### B) Stripe Webhook Signature Sanity Check

Events being enabled in the dashboard is necessary but not sufficient. Signature verification silently fails if the endpoint URL is wrong or `STRIPE_WEBHOOK_SECRET` doesn't match the signing secret for **that specific endpoint**.

**After sending a test event from Stripe Dashboard:**

1. In **Stripe → Webhooks → your endpoint → Event deliveries** — open the delivery and check the **Response** tab:
   - ✅ Pass: HTTP `200`
   - ❌ Fail: `400` / `401` / `500` — check Render logs for `"signature verification failed"`

2. In **Render → Backend service → Environment** — confirm:
   - Env var name is exactly `STRIPE_WEBHOOK_SECRET` (no trailing space, no typo)
   - The value matches the **Signing secret** shown on the Stripe webhook detail page (starts with `whsec_`)
   - It is set on the **live/production** endpoint, not a test endpoint pointing to a different URL

---

### C) Bridge Alerts Require `vehicle_height_ft` in the Request Payload

If `bridge_clearance_alerts` comes back `[]`, before assuming Overpass has no data, confirm the route request actually includes the height:

**DevTools → Network → route POST → Request Payload — verify:**
```json
{
  "origin": "...",
  "destination": "...",
  "vehicle_height_ft": 13.5
}
```

If `vehicle_height_ft` is missing or `null`, the backend defaults to `13.5 ft` internally — but it's worth confirming the UI is sending it explicitly, especially if trucker mode is your entry point.

---

### D) Auth Guard Test — Two Conditions, Not One

The 403 guard in section 5 only proves the unverified-user path. Also confirm the endpoint is not accidentally open (no auth = 401, not 200):

**Test D1 — No token:**
- `POST /api/subscription/checkout` with no `Authorization` header
- **Pass condition:** HTTP `401`

**Test D2 — Valid token, unverified user (from section 5):**
- `POST /api/subscription/checkout` with `Authorization: Bearer <token>` for unverified user
- **Pass condition:** HTTP `403` with `"Email address must be verified..."`

Both conditions together confirm the endpoint is truly authenticated and the email guard is layered on top of auth, not substituting for it.

---

## What Is Already Confirmed (code-verified)

| Item | Status | Evidence |
|---|---|---|
| Bridge cards show numeric heights | ✅ | `route.tsx` lines 902–914 render `clearance_ft` + `vehicle_height_ft` |
| Negative margin sets reroute flag | ✅ | `server.py` — `bridge_conflicts` check sets `reroute_recommended=True` |
| Reroute banner shown in UI | ✅ | `route.tsx` lines 674–686 — red `TouchableOpacity` with warning icon |
| Reroute appears in share text + TTS | ✅ | `route.tsx` lines 504–506, 547–549 |
| Overpass outage → `[]`, never raises | ✅ | `asyncio.wait_for(8s)` + 3 nested `except` blocks all return `[]` |
| Cache height bucket is ceiling (conservative) | ✅ | `ceil(vehicle_height_ft * 2) / 2` — 13.1 ft → 13.5 bucket |
| Cache bucket boundaries | ✅ | Every 0.5 ft: 10.0, 10.5, 11.0, … 13.0, 13.5, 14.0 |
| Trial checkout unlocks premium (`no_payment_required`) | ✅ | Stripe sub fetch — gates on `status in ("active","trialing")`, not `payment_status` |
| Non-subscription checkout blocked | ✅ | `mode != "subscription"` guard returns early before any DB write |
| Checkout blocked for unverified users | ✅ | `/subscription/checkout` endpoint — 403 if `email_verified=false` |
| `/account` accessible without premium | ✅ | Added to `PAYWALL_OPEN_ROUTES` |
| Polling stops after verification | ✅ | `useEffect` returns early if `verifyDone \|\| user?.email_verified` |
| 24 deterministic unit tests pass | ✅ | `pytest test_bridge_height_service.py` — 24 passed in 1.09s |
