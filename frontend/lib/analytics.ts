import { Platform } from 'react-native';
import ReactGA from 'react-ga4';

/**
 * Lightweight GA4 event wrapper to avoid duplicate GA script tags.
 * GA is initialized once in app/_layout.tsx; this helper only sends events.
 */
export function trackEvent(eventName: string, params?: Record<string, any>) {
  if (Platform.OS !== 'web') return; // only send from web/SPA
  ReactGA.event(eventName, params);
}
