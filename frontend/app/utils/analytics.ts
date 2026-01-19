/**
 * Analytics Event Tracking (Task F1)
 * 
 * Centralized event logging for conversion tracking and funnel analysis.
 * 
 * Supported events:
 * - paywall_viewed: When paywall screen/modal is shown
 * - trial_started: When user successfully starts free trial
 * - purchase_success: After confirmed subscription purchase
 * - feature_intent_used: When user attempts to use premium feature
 * - feature_locked_shown: When premium gate blocks access
 * 
 * Usage:
 *   trackEvent("paywall_viewed", { feature: "solar_forecast", source: "route_summary" });
 */

// Declare React Native __DEV__ global
declare const __DEV__: boolean;

import AsyncStorage from '@react-native-async-storage/async-storage';

// Event names (typed for safety)
export type AnalyticsEvent =
  | 'paywall_viewed'
  | 'trial_started'
  | 'purchase_success'
  | 'feature_intent_used'
  | 'feature_locked_shown';

// Event parameters
export interface AnalyticsParams {
  // Paywall viewed
  feature?: string;
  source?: string;
  screen?: string;
  
  // Trial started / Purchase success
  planType?: 'monthly' | 'yearly';
  platform?: 'ios' | 'android';
  productId?: string;
  price?: string;
  
  // Feature intent/locked
  isPremium?: boolean;
  entryPoint?: string;
  
  // Additional context
  [key: string]: any;
}

// Event metadata
interface EventRecord {
  name: AnalyticsEvent;
  params: AnalyticsParams;
  timestamp: number;
  sessionId: string;
}

// Session management
let sessionId: string | null = null;
const SESSION_TIMEOUT_MS = 30 * 60 * 1000; // 30 minutes
let lastEventTime = 0;

// Deduplication cache (prevent duplicate events within 1 second)
const recentEvents = new Map<string, number>();
const DEDUPE_WINDOW_MS = 1000;

/**
 * Get or create session ID
 */
async function getSessionId(): Promise<string> {
  const now = Date.now();
  
  // Check if session expired
  if (sessionId && now - lastEventTime > SESSION_TIMEOUT_MS) {
    sessionId = null;
  }
  
  // Create new session if needed
  if (!sessionId) {
    sessionId = `session_${now}_${Math.random().toString(36).substr(2, 9)}`;
    try {
      await AsyncStorage.setItem('analytics_session_id', sessionId);
    } catch (error) {
      console.warn('[Analytics] Failed to store session ID:', error);
    }
  }
  
  lastEventTime = now;
  return sessionId;
}

/**
 * Check if event is duplicate (fired recently)
 */
function isDuplicate(name: AnalyticsEvent, params: AnalyticsParams): boolean {
  const key = `${name}:${JSON.stringify(params)}`;
  const lastTime = recentEvents.get(key);
  const now = Date.now();
  
  if (lastTime && now - lastTime < DEDUPE_WINDOW_MS) {
    return true;
  }
  
  // Update cache
  recentEvents.set(key, now);
  
  // Cleanup old entries
  if (recentEvents.size > 100) {
    const cutoff = now - DEDUPE_WINDOW_MS * 2;
    const entriesToDelete: string[] = [];
    recentEvents.forEach((timestamp, key) => {
      if (timestamp < cutoff) {
        entriesToDelete.push(key);
      }
    });
    entriesToDelete.forEach(key => recentEvents.delete(key));
  }
  
  return false;
}

/**
 * Sanitize parameters to remove PII
 */
function sanitizeParams(params: AnalyticsParams): AnalyticsParams {
  const sanitized = { ...params };
  
  // Remove potential PII fields
  const piiFields = ['email', 'phone', 'name', 'address', 'userId', 'deviceId'];
  for (const field of piiFields) {
    if (field in sanitized) {
      delete sanitized[field];
    }
  }
  
  // Truncate long strings
  for (const [key, value] of Object.entries(sanitized)) {
    if (typeof value === 'string' && value.length > 200) {
      sanitized[key] = value.substring(0, 200) + '...';
    }
  }
  
  return sanitized;
}

/**
 * Store event locally for batch upload
 */
async function storeEvent(event: EventRecord): Promise<void> {
  try {
    const key = `analytics_events`;
    const stored = await AsyncStorage.getItem(key);
    const events: EventRecord[] = stored ? JSON.parse(stored) : [];
    
    // Add new event
    events.push(event);
    
    // Keep only last 100 events (prevent unbounded growth)
    const trimmed = events.slice(-100);
    
    await AsyncStorage.setItem(key, JSON.stringify(trimmed));
  } catch (error) {
    // Fail silently - analytics should never break the app
    console.warn('[Analytics] Failed to store event:', error);
  }
}

/**
 * Send event to analytics backend
 * (Placeholder - implement when backend ready)
 */
async function sendToBackend(event: EventRecord): Promise<void> {
  try {
    // TODO: Implement backend endpoint POST /api/analytics/events
    // For now, just log to console in dev mode
    if (typeof __DEV__ !== 'undefined' && __DEV__) {
      console.log('[Analytics] Event tracked:', {
        name: event.name,
        params: event.params,
        timestamp: new Date(event.timestamp).toISOString(),
      });
    }
    
    // In production, would send to backend:
    // await axios.post(`${API_URL}/analytics/events`, event);
  } catch (error) {
    // Fail silently
    console.warn('[Analytics] Failed to send event:', error);
  }
}

/**
 * Track an analytics event
 * 
 * @param name - Event name (typed)
 * @param params - Event parameters (no PII)
 * 
 * @example
 * trackEvent("paywall_viewed", { feature: "solar_forecast", source: "route_summary" });
 * trackEvent("purchase_success", { planType: "yearly", productId: "pro_yearly", price: "$99.99" });
 */
export async function trackEvent(
  name: AnalyticsEvent,
  params: AnalyticsParams = {}
): Promise<void> {
  try {
    // Sanitize parameters
    const sanitized = sanitizeParams(params);
    
    // Check for duplicates
    if (isDuplicate(name, sanitized)) {
      if (typeof __DEV__ !== 'undefined' && __DEV__) {
        console.log('[Analytics] Duplicate event ignored:', name);
      }
      return;
    }
    
    // Get session ID
    const session = await getSessionId();
    
    // Build event record
    const event: EventRecord = {
      name,
      params: sanitized,
      timestamp: Date.now(),
      sessionId: session,
    };
    
    // Store locally (non-blocking)
    storeEvent(event).catch(() => {});
    
    // Send to backend (non-blocking)
    sendToBackend(event).catch(() => {});
    
  } catch (error) {
    // Analytics should never crash the app
    console.warn('[Analytics] Error tracking event:', error);
  }
}

/**
 * Get stored events (for debugging or manual upload)
 */
export async function getStoredEvents(): Promise<EventRecord[]> {
  try {
    const key = `analytics_events`;
    const stored = await AsyncStorage.getItem(key);
    return stored ? JSON.parse(stored) : [];
  } catch (error) {
    console.warn('[Analytics] Failed to retrieve events:', error);
    return [];
  }
}

/**
 * Clear stored events (after successful upload)
 */
export async function clearStoredEvents(): Promise<void> {
  try {
    await AsyncStorage.removeItem('analytics_events');
  } catch (error) {
    console.warn('[Analytics] Failed to clear events:', error);
  }
}

/**
 * Get current session ID (for debugging)
 */
export function getCurrentSessionId(): string | null {
  return sessionId;
}
