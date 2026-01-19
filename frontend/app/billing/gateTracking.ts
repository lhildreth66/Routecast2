/**
 * Gate Tracking
 * 
 * Tracks premium feature access attempts to determine soft vs hard gate behavior.
 */

import AsyncStorage from '@react-native-async-storage/async-storage';
import type { PremiumFeature } from './features';

const GATE_TRACKING_KEY = 'routecast_gate_tracking';
const GATE_WINDOW_DAYS = 7;

export type GateMode = 'soft' | 'hard';

interface GateAttempt {
  feature: PremiumFeature;
  timestamp: string;
}

interface GateTracking {
  locked_attempt_count: number;
  first_locked_attempt_at?: string;
  last_locked_attempt_at?: string;
  attempts: GateAttempt[];
}

/**
 * Load gate tracking from storage.
 */
async function loadTracking(): Promise<GateTracking> {
  try {
    const json = await AsyncStorage.getItem(GATE_TRACKING_KEY);
    if (!json) {
      return {
        locked_attempt_count: 0,
        attempts: [],
      };
    }
    return JSON.parse(json);
  } catch (error) {
    console.error('[GateTracking] Failed to load:', error);
    return {
      locked_attempt_count: 0,
      attempts: [],
    };
  }
}

/**
 * Save gate tracking to storage.
 */
async function saveTracking(tracking: GateTracking): Promise<void> {
  try {
    const json = JSON.stringify(tracking);
    await AsyncStorage.setItem(GATE_TRACKING_KEY, json);
  } catch (error) {
    console.error('[GateTracking] Failed to save:', error);
  }
}

/**
 * Check if the gate window has expired.
 */
function isWindowExpired(firstAttemptAt: string | undefined): boolean {
  if (!firstAttemptAt) {
    return true;
  }
  
  const firstAttempt = new Date(firstAttemptAt);
  const now = new Date();
  const daysSinceFirst = (now.getTime() - firstAttempt.getTime()) / (1000 * 60 * 60 * 24);
  
  return daysSinceFirst > GATE_WINDOW_DAYS;
}

/**
 * Determine gate mode based on attempt history.
 * 
 * - First attempt: soft (can dismiss)
 * - Second+ attempt within 7 days: hard (cannot dismiss)
 * - After 7 days: resets to soft
 */
export async function getGateMode(feature: PremiumFeature): Promise<GateMode> {
  const tracking = await loadTracking();
  
  // Check if window expired
  if (isWindowExpired(tracking.first_locked_attempt_at)) {
    // Reset tracking if window expired
    if (tracking.locked_attempt_count > 0) {
      console.log('[GateTracking] Window expired, resetting to soft gate');
      await resetTracking();
    }
    return 'soft';
  }
  
  // First attempt is always soft
  if (tracking.locked_attempt_count === 0) {
    return 'soft';
  }
  
  // Second+ attempt is hard
  return 'hard';
}

/**
 * Record a locked feature attempt.
 */
export async function recordAttempt(feature: PremiumFeature): Promise<void> {
  const tracking = await loadTracking();
  const now = new Date().toISOString();
  
  // Check if window expired
  if (isWindowExpired(tracking.first_locked_attempt_at)) {
    // Reset and start fresh
    tracking.locked_attempt_count = 1;
    tracking.first_locked_attempt_at = now;
    tracking.last_locked_attempt_at = now;
    tracking.attempts = [{ feature, timestamp: now }];
  } else {
    // Increment existing tracking
    tracking.locked_attempt_count += 1;
    if (!tracking.first_locked_attempt_at) {
      tracking.first_locked_attempt_at = now;
    }
    tracking.last_locked_attempt_at = now;
    tracking.attempts.push({ feature, timestamp: now });
    
    // Keep only recent attempts (last 30 days)
    const thirtyDaysAgo = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString();
    tracking.attempts = tracking.attempts.filter(a => a.timestamp > thirtyDaysAgo);
  }
  
  await saveTracking(tracking);
  
  console.log('[GateTracking] Recorded attempt:', {
    feature,
    count: tracking.locked_attempt_count,
    firstAt: tracking.first_locked_attempt_at,
  });
}

/**
 * Reset gate tracking (e.g., after successful purchase).
 */
export async function resetTracking(): Promise<void> {
  try {
    await AsyncStorage.removeItem(GATE_TRACKING_KEY);
    console.log('[GateTracking] Reset tracking');
  } catch (error) {
    console.error('[GateTracking] Failed to reset:', error);
  }
}

/**
 * Get current tracking stats (for debugging).
 */
export async function getTrackingStats(): Promise<GateTracking> {
  return loadTracking();
}
