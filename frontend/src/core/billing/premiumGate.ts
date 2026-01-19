import type { Entitlements } from './Entitlements';
import { PremiumLockedError, type Feature } from './PremiumLockedError';

/**
 * Premium Gate
 *
 * Guards execution of premium features behind entitlement checks.
 * Pure function with no side effects (caller must handle PremiumLockedError).
 *
 * Usage:
 * ```ts
 * const result = premiumGate(entitlements, 'solar_forecast', () => {
 *   return calculateSolarForecast(params);
 * });
 * ```
 *
 * @param entitlements User's entitlements
 * @param feature Feature being accessed
 * @param block Function to execute if entitled
 * @returns Result of block execution
 * @throws PremiumLockedError if user lacks entitlement
 */
export function premiumGate<T>(
  entitlements: Entitlements,
  feature: Feature,
  block: () => T
): T {
  if (!entitlements.has(feature)) {
    throw new PremiumLockedError(feature);
  }

  return block();
}
