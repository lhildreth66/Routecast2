/**
 * Purchase Success Hook — Pure TypeScript
 *
 * Framework-agnostic hook for when purchase completes successfully.
 * Tracks analytics and grants entitlements immediately.
 */

import { trackPurchaseSuccess } from '../../analytics/paywall';
import type { Feature } from '../../billing/PremiumLockedError';
import type { CachedEntitlements } from '../../billing/CachedEntitlements';

/**
 * All premium features granted with any subscription
 */
const ALL_PREMIUM_FEATURES: Feature[] = [
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
 * Calculate expiration timestamp for subscription plan.
 *
 * @param plan Subscription plan type
 * @param now Current timestamp (ms since epoch)
 * @returns Expiration timestamp (ms since epoch)
 */
function calculateExpireAt(plan: 'monthly' | 'yearly', now: number): number {
  const MS_PER_DAY = 24 * 60 * 60 * 1000;
  
  if (plan === 'monthly') {
    return now + (32 * MS_PER_DAY); // 32 days
  } else {
    return now + (370 * MS_PER_DAY); // 370 days
  }
}

/**
 * Handle purchase success event.
 *
 * Call this when a user successfully completes a subscription purchase.
 * - Tracks analytics event
 * - Grants all premium features immediately
 * - Sets expiration based on plan (monthly: 32 days, yearly: 370 days)
 * - Persists entitlements to storage
 *
 * Safe implementation that never throws.
 *
 * @param entitlements Cached entitlements instance
 * @param feature Which premium feature was being accessed
 * @param plan Which subscription plan was purchased
 * @param source Optional analytics source identifier
 * @param now Optional time function for deterministic testing
 */
export async function onPurchaseSuccess(
  entitlements: CachedEntitlements,
  feature: Feature,
  plan: 'monthly' | 'yearly',
  source?: string,
  now: () => number = () => Date.now()
): Promise<void> {
  try {
    // Track analytics
    trackPurchaseSuccess({ feature, plan, source });

    // Calculate expiration
    const expireAt = calculateExpireAt(plan, now());

    // Grant all premium features
    await entitlements.grant(ALL_PREMIUM_FEATURES, expireAt);
  } catch (error) {
    // Silently fail - errors should not crash app
  }
}
