/**
 * Analytics Event Tracking — Pure TypeScript
 *
 * Safe, no-throw analytics helper for tracking user events.
 * No React Native dependencies.
 */

export type AnalyticsParams = Record<string, any>;

/**
 * Track an analytics event.
 *
 * Safe implementation that never throws:
 * - Wraps all operations in try/catch
 * - Only logs to console in development
 * - Gracefully handles missing console
 *
 * @param name Event name
 * @param params Optional event parameters
 */
export function trackEvent(name: string, params?: AnalyticsParams): void {
  try {
    // Check if we're in development mode
    const isDev = typeof __DEV__ !== 'undefined' ? __DEV__ : process.env.NODE_ENV !== 'production';

    if (isDev && typeof console !== 'undefined' && console.log) {
      console.log('[Analytics]', name, params || {});
    }

    // Future: Add real analytics SDK here
    // Example: analytics.track(name, params);
  } catch (error) {
    // Silently fail - analytics should never break app functionality
  }
}

// Declare __DEV__ for TypeScript (React Native global)
declare const __DEV__: boolean | undefined;
