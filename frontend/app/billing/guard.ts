/**
 * Premium Guard
 * 
 * Helper functions to enforce premium gating across the app.
 */

import { entitlementsCache } from './entitlements';
import type { Entitlement } from './types';

// 🔓 TESTING MODE: Set to true to bypass all premium checks
const BYPASS_PREMIUM_FOR_TESTING = false;

export interface GuardResult {
  allowed: boolean;
  reason?: 'locked' | 'expired' | 'no_subscription';
  entitlement?: Entitlement;
}

/**
 * Check if user has active Pro subscription.
 * Returns guard result with allowed status.
 */
export async function requirePro(): Promise<GuardResult> {
  // 🔓 TESTING BYPASS
  if (BYPASS_PREMIUM_FOR_TESTING) {
    return {
      allowed: true,
      entitlement: {
        isPro: true,
        productId: 'test_bypass',
        purchaseDate: new Date().toISOString(),
        expireAt: new Date(Date.now() + 365 * 24 * 60 * 60 * 1000).toISOString(),
      },
    };
  }
  
  const cached = await entitlementsCache.load();
  
  if (!cached) {
    return {
      allowed: false,
      reason: 'no_subscription',
    };
  }
  
  const isValid = entitlementsCache.isValid(cached);
  
  if (!isValid) {
    if (cached.expireAt && new Date(cached.expireAt) < new Date()) {
      return {
        allowed: false,
        reason: 'expired',
        entitlement: entitlementsCache.toEntitlement(cached),
      };
    }
    
    return {
      allowed: false,
      reason: 'locked',
      entitlement: entitlementsCache.toEntitlement(cached),
    };
  }
  
  return {
    allowed: true,
    entitlement: entitlementsCache.toEntitlement(cached),
  };
}

/**
 * Check if user is Pro (synchronous version for UI).
 * WARNING: May not reflect latest state. Use requirePro() for gating logic.
 */
export function isProSync(entitlement: Entitlement | null): boolean {
  return entitlement?.isPro === true;
}
