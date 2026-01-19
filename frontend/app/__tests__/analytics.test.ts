/**
 * Tests for analytics.ts (Task F1)
 * 
 * Verifies event tracking, deduplication, sanitization, and session management.
 */

import AsyncStorage from '@react-native-async-storage/async-storage';
import {
  trackEvent,
  getStoredEvents,
  clearStoredEvents,
  getCurrentSessionId,
} from '../utils/analytics';

// Mock AsyncStorage
jest.mock('@react-native-async-storage/async-storage', () => ({
  getItem: jest.fn(),
  setItem: jest.fn(),
  removeItem: jest.fn(),
}));

describe('Analytics', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (AsyncStorage.getItem as jest.Mock).mockResolvedValue(null);
    (AsyncStorage.setItem as jest.Mock).mockResolvedValue(undefined);
    
    // Clear deduplication cache by waiting
    jest.useRealTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  describe('trackEvent', () => {
    it('tracks paywall_viewed event', async () => {
      await trackEvent('paywall_viewed', {
        feature: 'solar_forecast',
        source: 'route_summary',
      });

      expect(AsyncStorage.setItem).toHaveBeenCalled();
      const calls = (AsyncStorage.setItem as jest.Mock).mock.calls;
      
      // Find the analytics_events call
      const eventsCall = calls.find(([key]) => key === 'analytics_events');
      expect(eventsCall).toBeTruthy();
      
      const storedData = JSON.parse(eventsCall[1]);
      expect(storedData).toHaveLength(1);
      expect(storedData[0].name).toBe('paywall_viewed');
      expect(storedData[0].params.feature).toBe('solar_forecast');
    });

    it('tracks trial_started event', async () => {
      await trackEvent('trial_started', {
        planType: 'yearly',
        platform: 'ios',
      });

      const calls = (AsyncStorage.setItem as jest.Mock).mock.calls;
      const eventsCall = calls.find(([key]) => key === 'analytics_events');
      
      const storedData = JSON.parse(eventsCall[1]);
      expect(storedData[0].name).toBe('trial_started');
      expect(storedData[0].params.planType).toBe('yearly');
    });

    it('tracks purchase_success event', async () => {
      await trackEvent('purchase_success', {
        productId: 'pro_yearly',
        planType: 'yearly',
        price: '$99.99',
      });

      const calls = (AsyncStorage.setItem as jest.Mock).mock.calls;
      const eventsCall = calls.find(([key]) => key === 'analytics_events');
      
      const storedData = JSON.parse(eventsCall[1]);
      expect(storedData[0].name).toBe('purchase_success');
      expect(storedData[0].params.productId).toBe('pro_yearly');
    });

    it('tracks feature_intent_used event', async () => {
      await trackEvent('feature_intent_used', {
        feature: 'solar_forecast',
        isPremium: false,
      });

      const calls = (AsyncStorage.setItem as jest.Mock).mock.calls;
      const eventsCall = calls.find(([key]) => key === 'analytics_events');
      
      const storedData = JSON.parse(eventsCall[1]);
      expect(storedData[0].name).toBe('feature_intent_used');
      expect(storedData[0].params.isPremium).toBe(false);
    });

    it('tracks feature_locked_shown event', async () => {
      await trackEvent('feature_locked_shown', {
        feature: 'solar_forecast',
        entryPoint: 'soft_gate',
      });

      const calls = (AsyncStorage.setItem as jest.Mock).mock.calls;
      const eventsCall = calls.find(([key]) => key === 'analytics_events');
      
      const storedData = JSON.parse(eventsCall[1]);
      expect(storedData[0].name).toBe('feature_locked_shown');
      expect(storedData[0].params.entryPoint).toBe('soft_gate');
    });
  });

  describe('Deduplication', () => {
    it('prevents duplicate events within 1 second', async () => {
      const params = { feature: 'solar_forecast' };
      
      await trackEvent('paywall_viewed', params);
      await trackEvent('paywall_viewed', params);
      await trackEvent('paywall_viewed', params);

      const calls = (AsyncStorage.setItem as jest.Mock).mock.calls;
      const eventsCalls = calls.filter(([key]) => key === 'analytics_events');
      
      // Should only store once (first event is stored, others are deduplicated)
      expect(eventsCalls.length).toBe(1);
      
      const storedData = JSON.parse(eventsCalls[0][1]);
      expect(storedData.length).toBe(1); // Only one event stored
    });

    it('allows same event with different params', async () => {
      await trackEvent('paywall_viewed', { feature: 'solar_forecast' });
      
      // Clear mock calls after first event
      jest.clearAllMocks();
      (AsyncStorage.getItem as jest.Mock).mockResolvedValue(JSON.stringify([
        { name: 'paywall_viewed', params: { feature: 'solar_forecast' }, timestamp: Date.now(), sessionId: 'test' }
      ]));
      
      // Wait to avoid deduplication
      await new Promise(resolve => setTimeout(resolve, 100));
      
      await trackEvent('paywall_viewed', { feature: 'road_passability' });

      const calls = (AsyncStorage.setItem as jest.Mock).mock.calls;
      const eventsCalls = calls.filter(([key]) => key === 'analytics_events');
      
      // Different params should create a new event
      expect(eventsCalls.length).toBeGreaterThan(0);
      const storedData = JSON.parse(eventsCalls[0][1]);
      expect(storedData.some((e: any) => e.params.feature === 'road_passability')).toBe(true);
    });
  });

  describe('PII Sanitization', () => {
    it('removes email from params', async () => {
      await trackEvent('purchase_success', {
        productId: 'pro_yearly',
        email: 'user@example.com', // Should be removed
      } as any);

      const calls = (AsyncStorage.setItem as jest.Mock).mock.calls;
      const eventsCall = calls.find(([key]) => key === 'analytics_events');
      
      const storedData = JSON.parse(eventsCall[1]);
      expect(storedData[0].params.email).toBeUndefined();
      expect(storedData[0].params.productId).toBe('pro_yearly');
    });

    it('removes userId from params', async () => {
      await trackEvent('feature_intent_used', {
        feature: 'solar_forecast',
        userId: '12345', // Should be removed
      } as any);

      const calls = (AsyncStorage.setItem as jest.Mock).mock.calls;
      const eventsCall = calls.find(([key]) => key === 'analytics_events');
      
      const storedData = JSON.parse(eventsCall[1]);
      expect(storedData[0].params.userId).toBeUndefined();
    });

    it('truncates very long strings', async () => {
      const longString = 'x'.repeat(300);
      
      await trackEvent('paywall_viewed', {
        feature: longString,
      });

      const calls = (AsyncStorage.setItem as jest.Mock).mock.calls;
      const eventsCall = calls.find(([key]) => key === 'analytics_events');
      
      const storedData = JSON.parse(eventsCall[1]);
      expect(storedData[0].params.feature.length).toBeLessThanOrEqual(203); // 200 + "..."
    });
  });

  describe('Session Management', () => {
    it('creates session ID', () => {
      const sessionId = getCurrentSessionId();
      expect(sessionId).toBeTruthy();
      expect(sessionId).toMatch(/^session_/);
    });

    it('includes session ID in events', async () => {
      // Ensure AsyncStorage is mocked properly
      (AsyncStorage.getItem as jest.Mock).mockResolvedValue(null);
      (AsyncStorage.setItem as jest.Mock).mockResolvedValue(undefined);
      
      // Use a unique feature name to avoid deduplication with other tests
      await trackEvent('paywall_viewed', { feature: 'session_test_feature' });

      const calls = (AsyncStorage.setItem as jest.Mock).mock.calls;
      
      // Find the analytics_events call
      const eventsCall = calls.find(([key]) => key === 'analytics_events');
      
      if (!eventsCall) {
        // Debug: show all calls if not found
        console.log('All AsyncStorage.setItem calls:', calls.map(c => c[0]));
        throw new Error('analytics_events call not found');
      }
      
      const storedData = JSON.parse(eventsCall[1]);
      expect(storedData[0].sessionId).toBeTruthy();
      expect(storedData[0].sessionId).toMatch(/^session_/);
    });
  });

  describe('Error Handling', () => {
    it('does not throw when AsyncStorage fails', async () => {
      (AsyncStorage.setItem as jest.Mock).mockRejectedValue(new Error('Storage full'));

      await expect(
        trackEvent('paywall_viewed', { feature: 'solar_forecast' })
      ).resolves.not.toThrow();
    });

    it('does not throw with invalid params', async () => {
      await expect(
        trackEvent('paywall_viewed', null as any)
      ).resolves.not.toThrow();
    });
  });

  describe('Storage Management', () => {
    it('retrieves stored events', async () => {
      const mockEvents = JSON.stringify([
        { name: 'paywall_viewed', params: {}, timestamp: Date.now(), sessionId: 'test' },
      ]);
      (AsyncStorage.getItem as jest.Mock).mockResolvedValue(mockEvents);

      const events = await getStoredEvents();
      expect(events).toHaveLength(1);
      expect(events[0].name).toBe('paywall_viewed');
    });

    it('clears stored events', async () => {
      await clearStoredEvents();
      expect(AsyncStorage.removeItem).toHaveBeenCalledWith('analytics_events');
    });

    it('limits stored events to 100', async () => {
      // Mock 95 existing events
      const existingEvents = Array.from({ length: 95 }, (_, i) => ({
        name: 'test_event',
        params: { index: i },
        timestamp: Date.now(),
        sessionId: 'test',
      }));
      (AsyncStorage.getItem as jest.Mock).mockResolvedValue(JSON.stringify(existingEvents));

      // Add 10 more events
      for (let i = 0; i < 10; i++) {
        await trackEvent('paywall_viewed', { index: i });
      }

      const calls = (AsyncStorage.setItem as jest.Mock).mock.calls;
      const lastEventsCall = calls.filter(([key]) => key === 'analytics_events').pop();
      
      const storedData = JSON.parse(lastEventsCall[1]);
      expect(storedData.length).toBeLessThanOrEqual(100);
    });
  });
});
