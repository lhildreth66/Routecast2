/**
 * Paywall Entry-Point Hook — Pure TypeScript
 *
 * Framework-agnostic hook for when paywall is shown to user.
 * No UI logic, no navigation, no side effects.
 */

import { trackPaywallViewed } from '../../analytics/paywall';
import type { Feature } from '../../billing/PremiumLockedError';

/**
 * Handle paywall shown event.
 *
 * Call this when the paywall/upgrade screen is displayed to the user.
 * Logs analytics event only - no UI or state changes.
 * Safe implementation that never throws.
 *
 * @param feature Which premium feature triggered the paywall
 * @param source Optional analytics source identifier
 */
export function onPaywallShown(feature: Feature, source?: string): void {
  try {
    trackPaywallViewed({ feature, source });
  } catch (error) {
    // Silently fail - analytics should never break app functionality
  }
}
