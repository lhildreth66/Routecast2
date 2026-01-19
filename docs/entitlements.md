# Entitlements (Boondocking Pro)

This document outlines the client-side entitlement key and future wiring steps for premium features like Road Passability (A6).

- Key: `entitlements.boondockingPro`
- Storage: AsyncStorage boolean
- Default: `false` when missing or invalid
- Client utility: see [frontend/app/utils/entitlements.ts](frontend/app/utils/entitlements.ts)
- Paywall: local modal component at [frontend/app/components/PaywallModal.tsx](frontend/app/components/PaywallModal.tsx)

## Current Behavior
- Home button navigates to [frontend/app/road-passability.tsx](frontend/app/road-passability.tsx).
- Screen checks `hasBoondockingPro()`; if `false`, opens PaywallModal.
- Screen calls backend `POST /api/pro/road-passability`.
  - If server returns HTTP 402 (or 403) with `{ code: "PREMIUM_LOCKED" }`, opens PaywallModal.
- When entitlement flips `true`, user can retry and see results (score, flags, reasons).

## Setting the Entitlement (Local Dev)
Use AsyncStorage to set the boolean key:

```ts
import AsyncStorage from '@react-native-async-storage/async-storage';
await AsyncStorage.setItem('entitlements.boondockingPro', 'true');
// To disable:
await AsyncStorage.setItem('entitlements.boondockingPro', 'false');
```

Tip: You can run this from a debug button, dev tools, or an ad-hoc effect while testing.

### Dev-Only Gesture Toggle
In dev builds (`__DEV__` is true), tap the subtitle "Weather forecasts for your journey" on the Home screen **5 times rapidly** (within 2 seconds) to toggle the Pro entitlement. An Alert will confirm the change. This feature is **disabled in production builds**.

## Backend Premium Gating
- Endpoint: `POST /api/pro/road-passability`
- Locked response: HTTP 402 with body:

```json
{
  "code": "PREMIUM_LOCKED",
  "message": "Upgrade to Routecast Pro to assess backroad passability (mud/ice/clearance)."
}
```

Frontend is expected to check either local entitlement or server response (402/403 with `code: PREMIUM_LOCKED`) and open the paywall.

## Future Wiring Steps (Placeholder)
- Add a real billing flow to acquire Pro.
- On successful purchase, persist `entitlements.boondockingPro` as `true`.
- Optionally validate with server-side subscription status and refresh the entitlement flag.
- Consider centralizing paywall copy and upgrade CTA once more Pro features are added.

## Quick Backend Test
If you want to test the locked response quickly:

```bash
curl -sX POST "$API_BASE/api/pro/road-passability" \
  -H "Content-Type: application/json" \
  -d '{"precip72hIn":1.2,"slopePct":12,"minTempF":30,"soilType":"clay"}'
```

Expected: `402` with `{ code: "PREMIUM_LOCKED" }` until entitlement and subscription are wired.
