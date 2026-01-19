/**
 * Premium Guard
 * 
 * Helper functions to enforce premium gating across the app.
 */

import { entitlementsCache } from './entitlements';
import type { Entitlement } from './types';

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
