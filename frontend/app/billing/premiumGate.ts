/**
 * Premium Gate
 * 
 * Frontend wrapper for enforcing premium entitlements.
 * Checks cache, triggers paywall when locked, executes when entitled.
 */

import { entitlementsCache } from './entitlements';
import type { PremiumFeature } from './features';
import { getGateMode, recordAttempt, type GateMode } from './gateTracking';
import { trackEvent } from '../utils/analytics';

export class PremiumLockedError extends Error {
  constructor(public feature: PremiumFeature) {
    super(`Premium feature locked: ${feature}`);
    this.name = 'PremiumLockedError';
  }
}

/**
 * Global paywall trigger callback with gate mode support.
 * Set this in your app root to handle paywall display.
 */
let paywallTrigger: ((feature: PremiumFeature, gateMode: GateMode) => void) | null = null;

export function setPaywallTrigger(trigger: (feature: PremiumFeature, gateMode: GateMode) => void) {
  paywallTrigger = trigger;
}

/**
 * Check if user has entitlement for a premium feature.
 */
async function checkEntitlement(feature: PremiumFeature): Promise<boolean> {
  const cached = await entitlementsCache.load();
  
  if (!cached) {
    return false;
  }
  
  return entitlementsCache.isValid(cached);
}

/**
 * Trigger the paywall UI for a specific feature.
 */
async function triggerPaywall(feature: PremiumFeature): Promise<void> {
  // Record the attempt
  await recordAttempt(feature);
  
  // Determine gate mode
  const gateMode = await getGateMode(feature);
  
  // Track feature locked shown
  trackEvent('feature_locked_shown', {
    feature,
    entryPoint: gateMode === 'hard' ? 'hard_gate' : 'soft_gate',
  });
  
  if (paywallTrigger) {
    paywallTrigger(feature, gateMode);
  } else {
    console.warn('[premiumGate] No paywall trigger registered');
  }
}

/**
 * Premium gate wrapper for functions.
 * Checks entitlement before executing the function.
 * 
 * Usage:
 *   const result = await premiumGate('solar_forecast', async () => {
 *     return await fetchSolarForecast();
 *   });
 */
export async function premiumGate<T>(
  feature: PremiumFeature,
  fn: () => Promise<T> | T
): Promise<T> {
  const entitled = await checkEntitlement(feature);
  
  // Track feature intent
  trackEvent('feature_intent_used', {
    feature,
    isPremium: entitled,
  });
  
  if (!entitled) {
    await triggerPaywall(feature);
    throw new PremiumLockedError(feature);
  }
  
  return await fn();
}

/**
 * Check if an API response indicates premium locked.
 */
export function isPremiumLockedResponse(response: any): boolean {
  if (!response) {
    return false;
  }
  
  // Check for premium_locked error in response body
  if (response.error === 'premium_locked') {
    return true;
  }
  
  // Check for detail.error shape (FastAPI HTTPException)
  if (response.detail?.error === 'premium_locked') {
    return true;
  }
  
  return false;
}

/**
 * Extract feature from premium locked response.
 */
export function getLockedFeature(response: any): PremiumFeature | null {
  if (response?.feature) {
    return response.feature as PremiumFeature;
  }
  
  if (response?.detail?.feature) {
    return response.detail.feature as PremiumFeature;
  }
  
  return null;
}

/**
 * Wrapper for API calls that automatically handles premium locked responses.
 * 
 * Usage:
 *   const data = await premiumApiCall('solar_forecast', async () => {
 *     const response = await fetch('/api/pro/solar-forecast', { ... });
 *     return await response.json();
 *   });
 */
export async function premiumApiCall<T>(
  feature: PremiumFeature,
  apiFn: () => Promise<Response>
): Promise<T> {
  try {
    const response = await apiFn();
    
    // Check for 403 status (Forbidden)
    if (response.status === 403) {
      const body = await response.json().catch(() => ({}));
      
      if (isPremiumLockedResponse(body)) {
        const lockedFeature = getLockedFeature(body) || feature;
        await triggerPaywall(lockedFeature);
        throw new PremiumLockedError(lockedFeature);
      }
    }
    
    // Check for premium_locked in successful response body
    if (response.ok) {
      const body = await response.json();
      
      if (isPremiumLockedResponse(body)) {
        const lockedFeature = getLockedFeature(body) || feature;
        await triggerPaywall(lockedFeature);
        throw new PremiumLockedError(lockedFeature);
      }
      
      return body as T;
    }
    
    // Other error
    throw new Error(`API call failed: ${response.status}`);
  } catch (error) {
    if (error instanceof PremiumLockedError) {
      throw error;
    }
    
    // Re-throw other errors
    throw error;
  }
}
