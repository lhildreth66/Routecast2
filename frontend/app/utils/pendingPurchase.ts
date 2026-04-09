/**
 * pendingPurchase.ts
 *
 * Handles the unauthenticated-purchase flow:
 *   email-verification deep-link → routecast2://subscription → user subscribes
 *   via Google Play BEFORE logging in → receipt stored here → user navigates
 *   to /login → logs in once → receipt verified here → user enters app.
 *
 * The break in the 13-step required flow occurs at step 8:
 *   verifyGooglePurchase() in subscription.tsx throws
 *   "Sign in is required before starting a trial/subscription."
 *   when accessToken is null, instead of storing the receipt and routing to /login.
 *
 * This utility provides:
 *   savePendingPurchase   — called from subscription.tsx when !accessToken after purchase
 *   getPendingPurchase    — called from login.tsx after successful login
 *   clearPendingPurchase  — called after verification (success or failure)
 *   verifyGooglePurchaseWithToken — standalone backend call taking an explicit token
 */

import AsyncStorage from '@react-native-async-storage/async-storage';
import { buildUrl } from '../apiConfig';
import { PurchaseVerificationPayload } from './postPurchaseFlow';

export const PENDING_PURCHASE_KEY = 'routecast_pending_purchase';

// --------------------------------------------------------------------------
// Storage helpers
// --------------------------------------------------------------------------

/**
 * Persist a receipt from a Google Play purchase that completed before login.
 * Pass null when billing.purchase() returned null (transaction acknowledged
 * before the poll could retrieve the token) — callers handle that case by
 * navigating normally and letting the user restore manually.
 */
export async function savePendingPurchase(
  receipt: PurchaseVerificationPayload | null,
): Promise<void> {
  if (!receipt) {
    // No token available — store a restore marker so post-login code knows
    // a purchase happened but can't verify directly.
    await AsyncStorage.setItem(PENDING_PURCHASE_KEY, JSON.stringify({ pendingRestore: true }));
    return;
  }
  await AsyncStorage.setItem(PENDING_PURCHASE_KEY, JSON.stringify(receipt));
}

export type PendingPurchaseValue =
  | PurchaseVerificationPayload
  | { pendingRestore: true }
  | null;

/** Read the pending purchase from AsyncStorage. Returns null if nothing stored. */
export async function getPendingPurchase(): Promise<PendingPurchaseValue> {
  try {
    const raw = await AsyncStorage.getItem(PENDING_PURCHASE_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as PendingPurchaseValue;
  } catch {
    return null;
  }
}

/** Remove the pending purchase marker. Always call after handling it. */
export async function clearPendingPurchase(): Promise<void> {
  await AsyncStorage.removeItem(PENDING_PURCHASE_KEY);
}

// --------------------------------------------------------------------------
// Backend verification — standalone, takes explicit accessToken
// --------------------------------------------------------------------------

/**
 * POST /subscription/verify/google with the given receipt and access token.
 * Throws on HTTP error or invalid entitlement.
 */
export async function verifyGooglePurchaseWithToken(
  accessToken: string,
  receipt: PurchaseVerificationPayload,
): Promise<void> {
  const response = await fetch(buildUrl('subscription/verify/google'), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${accessToken}`,
    },
    body: JSON.stringify({
      purchase_token: receipt.purchaseToken,
      product_id: receipt.productId,
      package_name: receipt.packageName,
    }),
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body?.detail ?? 'Google Play verification failed');
  }
  if (!body?.valid) {
    throw new Error(body?.message ?? 'Google Play entitlement is not active.');
  }
}
