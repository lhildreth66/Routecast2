import { trackPaywallViewed, trackPurchaseSuccess } from '../paywall';
import { trackEvent } from '../track';

// Mock trackEvent
jest.mock('../track');
const mockTrackEvent = trackEvent as jest.MockedFunction<typeof trackEvent>;

describe('paywall analytics', () => {
  beforeEach(() => {
    mockTrackEvent.mockClear();
  });

  describe('trackPaywallViewed', () => {
    it('calls trackEvent with paywall_viewed event name', () => {
      trackPaywallViewed({ feature: 'solar_forecast', source: 'dashboard' });

      expect(mockTrackEvent).toHaveBeenCalledTimes(1);
      expect(mockTrackEvent).toHaveBeenCalledWith('paywall_viewed', {
        feature: 'solar_forecast',
        source: 'dashboard',
      });
    });

    it('passes through feature and source params', () => {
      trackPaywallViewed({ feature: 'road_passability', source: 'map_screen' });

      expect(mockTrackEvent).toHaveBeenCalledWith('paywall_viewed', {
        feature: 'road_passability',
        source: 'map_screen',
      });
    });

    it('handles undefined source', () => {
      trackPaywallViewed({ feature: 'battery_forecast' });

      expect(mockTrackEvent).toHaveBeenCalledWith('paywall_viewed', {
        feature: 'battery_forecast',
        source: undefined,
      });
    });

    it('does not throw when trackEvent throws', () => {
      mockTrackEvent.mockImplementationOnce(() => {
        throw new Error('Network failure');
      });

      expect(() => {
        trackPaywallViewed({ feature: 'solar_forecast' });
      }).not.toThrow();
    });

    it('works with all feature types', () => {
      const features: Array<'solar_forecast' | 'road_passability' | 'propane_forecast' | 'battery_forecast' | 'water_plan' | 'cell_starlink' | 'camp_index' | 'claim_log'> = [
        'solar_forecast',
        'road_passability',
        'propane_forecast',
        'battery_forecast',
        'water_plan',
        'cell_starlink',
        'camp_index',
        'claim_log',
      ];

      features.forEach((feature) => {
        mockTrackEvent.mockClear();
        trackPaywallViewed({ feature });

        expect(mockTrackEvent).toHaveBeenCalledWith('paywall_viewed', {
          feature,
          source: undefined,
        });
      });
    });
  });

  describe('trackPurchaseSuccess', () => {
    it('calls trackEvent with purchase_success event name', () => {
      trackPurchaseSuccess({
        feature: 'solar_forecast',
        plan: 'yearly',
        source: 'dashboard',
      });

      expect(mockTrackEvent).toHaveBeenCalledTimes(1);
      expect(mockTrackEvent).toHaveBeenCalledWith('purchase_success', {
        feature: 'solar_forecast',
        plan: 'yearly',
        source: 'dashboard',
      });
    });

    it('passes through feature, plan, and source params', () => {
      trackPurchaseSuccess({
        feature: 'road_passability',
        plan: 'monthly',
        source: 'paywall',
      });

      expect(mockTrackEvent).toHaveBeenCalledWith('purchase_success', {
        feature: 'road_passability',
        plan: 'monthly',
        source: 'paywall',
      });
    });

    it('handles undefined source', () => {
      trackPurchaseSuccess({
        feature: 'battery_forecast',
        plan: 'yearly',
      });

      expect(mockTrackEvent).toHaveBeenCalledWith('purchase_success', {
        feature: 'battery_forecast',
        plan: 'yearly',
        source: undefined,
      });
    });

    it('does not throw when trackEvent throws', () => {
      mockTrackEvent.mockImplementationOnce(() => {
        throw new Error('Analytics SDK crashed');
      });

      expect(() => {
        trackPurchaseSuccess({
          feature: 'solar_forecast',
          plan: 'monthly',
        });
      }).not.toThrow();
    });

    it('works with monthly plan', () => {
      trackPurchaseSuccess({
        feature: 'propane_forecast',
        plan: 'monthly',
        source: 'upgrade_prompt',
      });

      expect(mockTrackEvent).toHaveBeenCalledWith('purchase_success', {
        feature: 'propane_forecast',
        plan: 'monthly',
        source: 'upgrade_prompt',
      });
    });

    it('works with yearly plan', () => {
      trackPurchaseSuccess({
        feature: 'water_plan',
        plan: 'yearly',
        source: 'settings',
      });

      expect(mockTrackEvent).toHaveBeenCalledWith('purchase_success', {
        feature: 'water_plan',
        plan: 'yearly',
        source: 'settings',
      });
    });
  });
});
