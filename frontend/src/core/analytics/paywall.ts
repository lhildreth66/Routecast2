/**
 * Paywall Analytics — Pure TypeScript
 *
 * Safe analytics helpers for paywall and purchase tracking.
 * No React Native dependencies.
 */

import { trackEvent } from './track';
import type { Feature } from '../billing/PremiumLockedError';

/**
 * Track paywall viewed event.
 *
 * Logs when a user sees the paywall/upgrade screen.
 * Safe implementation that never throws.
 *
 * @param params Event parameters
 * @param params.feature Which premium feature triggered the paywall
 * @param params.source Optional analytics source identifier
 */
export function trackPaywallViewed(params: {
  feature: Feature;
  source?: string;
}): void {
  try {
    trackEvent('paywall_viewed', params);
  } catch (error) {
    // Silently fail - analytics should never break app functionality
  }
}

/**
 * Track purchase success event.
 *
 * Logs when a user successfully completes a purchase.
 * Safe implementation that never throws.
 *
 * @param params Event parameters
 * @param params.feature Which premium feature was being accessed
 * @param params.plan Which subscription plan was purchased
 * @param params.source Optional analytics source identifier
 */
export function trackPurchaseSuccess(params: {
  feature: Feature;
  plan: 'monthly' | 'yearly';
  source?: string;
}): void {
  try {
    trackEvent('purchase_success', params);
  } catch (error) {
    // Silently fail - analytics should never break app functionality
  }
}
