/**
 * Entitlement Verification — Pure TypeScript
 *
 * Verifies user's subscription status and grants entitlements accordingly.
 * Called on app start to restore purchases and sync local entitlements.
 */

import type { StoreBilling } from './StoreBilling';
import type { CachedEntitlements } from './CachedEntitlements';
import type { Feature } from './PremiumLockedError';

// All premium features
const ALL_FEATURES: Feature[] = [
  'solar_forecast',
  'road_passability',
  'propane_forecast',
  'battery_forecast',
  'water_plan',
  'cell_starlink',
  'camp_index',
  'claim_log',
];

/**
 * Verify and sync entitlements from app store.
 *
 * Call this on app start after initializing billing and entitlements.
 *
 * Behavior:
 * - Initializes billing connection
 * - Restores purchases from app store
 * - If active subscription found → grants all features with 370 day expiration
 * - If no active subscription → keeps existing entitlements if not expired
 *
 * Limitations:
 * - No server-side receipt validation (temporary)
 * - Assumes yearly expiration for all active subscriptions
 * - Client-side only, can be bypassed on rooted devices
 *
 * @param billing StoreBilling implementation
 * @param entitlements CachedEntitlements instance
 * @param now Optional time function for deterministic testing
 */
export async function verifyEntitlements(
  billing: StoreBilling,
  entitlements: CachedEntitlements,
  now: () => number = Date.now
): Promise<void> {
  try {
    // Initialize billing connection
    await billing.init();

    // Restore purchases from store
    const hasActiveSubscription = await billing.restore();

    if (hasActiveSubscription) {
      // Grant all features with ~1 year expiration
      // TODO: Replace with server-side receipt validation that gets actual expiration
      const expireAt = now() + 370 * 24 * 60 * 60 * 1000; // 370 days
      await entitlements.grant(ALL_FEATURES, expireAt);
    }

    // If no active subscription, do nothing
    // Existing entitlements will remain if not expired
  } catch (error) {
    console.error('[verifyEntitlements] Failed to verify entitlements:', error);
    // Don't throw - app should continue even if verification fails
  }
}
