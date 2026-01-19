import { getSolarForecast } from '../getSolarForecast';
import { InMemoryEntitlements } from '../../../billing/Entitlements';
import { PremiumLockedError } from '../../../billing/PremiumLockedError';
import { trackEvent } from '../../../analytics/track';

// Mock analytics
jest.mock('../../../analytics/track');
const mockTrackEvent = trackEvent as jest.MockedFunction<typeof trackEvent>;

describe('getSolarForecast', () => {
  beforeEach(() => {
    mockTrackEvent.mockClear();
  });
  const validInput = {
    lat: 34.05,
    lon: -111.03,
    dateRange: [20, 21, 22], // Jan 20-22
    panelWatts: 400,
    shadePct: 20,
    cloudCover: [0, 40, 90], // Clear, partly cloudy, overcast
  };

  describe('when user lacks entitlement', () => {
    it('throws PremiumLockedError', () => {
      const entitlements = new InMemoryEntitlements(); // No features

      expect(() => {
        getSolarForecast(entitlements, validInput);
      }).toThrow(PremiumLockedError);
    });

    it('throws with correct feature name', () => {
      const entitlements = new InMemoryEntitlements();

      try {
        getSolarForecast(entitlements, validInput);
        fail('Should have thrown');
      } catch (error) {
        expect(error).toBeInstanceOf(PremiumLockedError);
        expect((error as PremiumLockedError).feature).toBe('solar_forecast');
      }
    });

    it('throws even with other features granted', () => {
      const entitlements = new InMemoryEntitlements(['road_passability', 'battery_forecast']);

      expect(() => {
        getSolarForecast(entitlements, validInput);
      }).toThrow(PremiumLockedError);
    });

    it('tracks feature_intent_used and feature_locked_shown', () => {
      const entitlements = new InMemoryEntitlements();

      expect(() => {
        getSolarForecast(entitlements, validInput, 'test_screen');
      }).toThrow(PremiumLockedError);

      // Should track both events
      expect(mockTrackEvent).toHaveBeenCalledTimes(2);

      // First: intent
      expect(mockTrackEvent).toHaveBeenNthCalledWith(1, 'feature_intent_used', {
        feature: 'solar_forecast',
        source: 'test_screen',
      });

      // Second: locked (before throw)
      expect(mockTrackEvent).toHaveBeenNthCalledWith(2, 'feature_locked_shown', {
        feature: 'solar_forecast',
        source: 'test_screen',
      });
    });

    it('tracks events with undefined source when omitted', () => {
      const entitlements = new InMemoryEntitlements();

      expect(() => {
        getSolarForecast(entitlements, validInput); // No source
      }).toThrow(PremiumLockedError);

      expect(mockTrackEvent).toHaveBeenCalledTimes(2);

      expect(mockTrackEvent).toHaveBeenNthCalledWith(1, 'feature_intent_used', {
        feature: 'solar_forecast',
        source: undefined,
      });

      expect(mockTrackEvent).toHaveBeenNthCalledWith(2, 'feature_locked_shown', {
        feature: 'solar_forecast',
        source: undefined,
      });
    });
  });

  describe('when user has entitlement', () => {
    it('returns solar forecast results', () => {
      const entitlements = new InMemoryEntitlements(['solar_forecast']);

      const result = getSolarForecast(entitlements, validInput);

      expect(result).toHaveLength(3); // 3 days
      expect(result.every((v) => typeof v === 'number')).toBe(true);
      expect(result.every((v) => v >= 0)).toBe(true);
    });

    it('tracks only feature_intent_used (not locked)', () => {
      const entitlements = new InMemoryEntitlements(['solar_forecast']);

      getSolarForecast(entitlements, validInput, 'dashboard');

      // Only intent, no locked event
      expect(mockTrackEvent).toHaveBeenCalledTimes(1);
      expect(mockTrackEvent).toHaveBeenCalledWith('feature_intent_used', {
        feature: 'solar_forecast',
        source: 'dashboard',
      });
    });

    it('tracks intent with undefined source when omitted', () => {
      const entitlements = new InMemoryEntitlements(['solar_forecast']);

      getSolarForecast(entitlements, validInput); // No source

      expect(mockTrackEvent).toHaveBeenCalledTimes(1);
      expect(mockTrackEvent).toHaveBeenCalledWith('feature_intent_used', {
        feature: 'solar_forecast',
        source: undefined,
      });
    });

    it('returns deterministic results', () => {
      const entitlements = new InMemoryEntitlements(['solar_forecast']);

      const result1 = getSolarForecast(entitlements, validInput);
      const result2 = getSolarForecast(entitlements, validInput);

      expect(result1).toEqual(result2);
    });

    it('clear day produces more than overcast day', () => {
      const entitlements = new InMemoryEntitlements(['solar_forecast']);

      const result = getSolarForecast(entitlements, validInput);

      expect(result[0]).toBeGreaterThan(result[2]); // Clear > overcast
    });

    it('works with all features granted', () => {
      const entitlements = new InMemoryEntitlements();
      entitlements.grantAll();

      const result = getSolarForecast(entitlements, validInput);

      expect(result).toHaveLength(3);
      expect(result.every((v) => v > 0)).toBe(true);
    });

    it('accepts optional source parameter', () => {
      const entitlements = new InMemoryEntitlements(['solar_forecast']);

      const result = getSolarForecast(entitlements, validInput, 'trip_planning_screen');

      expect(result).toHaveLength(3);
    });
  });

  describe('domain validation still applies', () => {
    it('throws on invalid latitude', () => {
      const entitlements = new InMemoryEntitlements(['solar_forecast']);

      expect(() => {
        getSolarForecast(entitlements, { ...validInput, lat: 95 });
      }).toThrow('Latitude must be in range');
    });

    it('throws on negative panel watts', () => {
      const entitlements = new InMemoryEntitlements(['solar_forecast']);

      expect(() => {
        getSolarForecast(entitlements, { ...validInput, panelWatts: -100 });
      }).toThrow('Panel watts must be > 0');
    });

    it('throws on cloud cover size mismatch', () => {
      const entitlements = new InMemoryEntitlements(['solar_forecast']);

      expect(() => {
        getSolarForecast(entitlements, {
          ...validInput,
          cloudCover: [0, 40], // Only 2, need 3
        });
      }).toThrow('Cloud cover list size');
    });
  });

  describe('different input scenarios', () => {
    const entitlements = new InMemoryEntitlements(['solar_forecast']);

    it('single day forecast', () => {
      const result = getSolarForecast(entitlements, {
        lat: 0,
        lon: 0,
        dateRange: [81], // Equinox
        panelWatts: 400,
        shadePct: 0,
        cloudCover: [0],
      });

      expect(result).toHaveLength(1);
      expect(result[0]).toBeGreaterThan(2000);
    });

    it('100% shade produces zero', () => {
      const result = getSolarForecast(entitlements, {
        lat: 34.05,
        lon: -111.03,
        dateRange: [100],
        panelWatts: 400,
        shadePct: 100,
        cloudCover: [0],
      });

      expect(result).toHaveLength(1);
      expect(result[0]).toBeCloseTo(0, 2);
    });

    it('week-long forecast', () => {
      const result = getSolarForecast(entitlements, {
        lat: 40,
        lon: -100,
        dateRange: [100, 101, 102, 103, 104, 105, 106],
        panelWatts: 200,
        shadePct: 30,
        cloudCover: [0, 20, 40, 60, 80, 100, 50],
      });

      expect(result).toHaveLength(7);
      expect(result.every((v) => v >= 0)).toBe(true);
    });
  });
});
