import { getRoadPassability, SoilTypeEnum } from '../getRoadPassability';
import { InMemoryEntitlements } from '../../../billing/Entitlements';
import { PremiumLockedError } from '../../../billing/PremiumLockedError';
import { trackEvent } from '../../../analytics/track';

// Mock analytics
jest.mock('../../../analytics/track');
const mockTrackEvent = trackEvent as jest.MockedFunction<typeof trackEvent>;

describe('getRoadPassability', () => {
  beforeEach(() => {
    mockTrackEvent.mockClear();
  });
  const validInput = {
    precip72hIn: 1.5,
    slopePct: 10,
    minTempF: 50,
    soil: SoilTypeEnum.LOAM,
  };

  describe('when user lacks entitlement', () => {
    it('throws PremiumLockedError', () => {
      const entitlements = new InMemoryEntitlements(); // No features

      expect(() => {
        getRoadPassability(entitlements, validInput);
      }).toThrow(PremiumLockedError);
    });

    it('throws with correct feature name', () => {
      const entitlements = new InMemoryEntitlements();

      try {
        getRoadPassability(entitlements, validInput);
        fail('Should have thrown');
      } catch (error) {
        expect(error).toBeInstanceOf(PremiumLockedError);
        expect((error as PremiumLockedError).feature).toBe('road_passability');
      }
    });

    it('throws even with other features granted', () => {
      const entitlements = new InMemoryEntitlements(['solar_forecast', 'battery_forecast']);

      expect(() => {
        getRoadPassability(entitlements, validInput);
      }).toThrow(PremiumLockedError);
    });

    it('tracks feature_intent_used and feature_locked_shown', () => {
      const entitlements = new InMemoryEntitlements();

      expect(() => {
        getRoadPassability(entitlements, validInput, 'map_screen');
      }).toThrow(PremiumLockedError);

      // Should track both events
      expect(mockTrackEvent).toHaveBeenCalledTimes(2);

      // First: intent
      expect(mockTrackEvent).toHaveBeenNthCalledWith(1, 'feature_intent_used', {
        feature: 'road_passability',
        source: 'map_screen',
      });

      // Second: locked (before throw)
      expect(mockTrackEvent).toHaveBeenNthCalledWith(2, 'feature_locked_shown', {
        feature: 'road_passability',
        source: 'map_screen',
      });
    });

    it('tracks events with undefined source when omitted', () => {
      const entitlements = new InMemoryEntitlements();

      expect(() => {
        getRoadPassability(entitlements, validInput); // No source
      }).toThrow(PremiumLockedError);

      expect(mockTrackEvent).toHaveBeenCalledTimes(2);

      expect(mockTrackEvent).toHaveBeenNthCalledWith(1, 'feature_intent_used', {
        feature: 'road_passability',
        source: undefined,
      });

      expect(mockTrackEvent).toHaveBeenNthCalledWith(2, 'feature_locked_shown', {
        feature: 'road_passability',
        source: undefined,
      });
    });
  });

  describe('when user has entitlement', () => {
    it('returns passability assessment', () => {
      const entitlements = new InMemoryEntitlements(['road_passability']);

      const result = getRoadPassability(entitlements, validInput);

      expect(result).toHaveProperty('score');
      expect(result).toHaveProperty('mudRisk');
      expect(result).toHaveProperty('iceRisk');
      expect(result).toHaveProperty('clearanceNeed');
      expect(result).toHaveProperty('fourByFourRecommended');
      expect(result).toHaveProperty('notes');

      expect(typeof result.score).toBe('number');
      expect(result.score).toBeGreaterThanOrEqual(0);
      expect(result.score).toBeLessThanOrEqual(100);
    });

    it('tracks only feature_intent_used (not locked)', () => {
      const entitlements = new InMemoryEntitlements(['road_passability']);

      getRoadPassability(entitlements, validInput, 'route_planner');

      // Only intent, no locked event
      expect(mockTrackEvent).toHaveBeenCalledTimes(1);
      expect(mockTrackEvent).toHaveBeenCalledWith('feature_intent_used', {
        feature: 'road_passability',
        source: 'route_planner',
      });
    });

    it('tracks intent with undefined source when omitted', () => {
      const entitlements = new InMemoryEntitlements(['road_passability']);

      getRoadPassability(entitlements, validInput); // No source

      expect(mockTrackEvent).toHaveBeenCalledTimes(1);
      expect(mockTrackEvent).toHaveBeenCalledWith('feature_intent_used', {
        feature: 'road_passability',
        source: undefined,
      });
    });

    it('returns deterministic results', () => {
      const entitlements = new InMemoryEntitlements(['road_passability']);

      const result1 = getRoadPassability(entitlements, validInput);
      const result2 = getRoadPassability(entitlements, validInput);

      expect(result1).toEqual(result2);
    });

    it('works with all features granted', () => {
      const entitlements = new InMemoryEntitlements();
      entitlements.grantAll();

      const result = getRoadPassability(entitlements, validInput);

      expect(result.score).toBeGreaterThanOrEqual(0);
      expect(result.score).toBeLessThanOrEqual(100);
    });

    it('accepts optional source parameter', () => {
      const entitlements = new InMemoryEntitlements(['road_passability']);

      const result = getRoadPassability(entitlements, validInput, 'map_screen');

      expect(result).toHaveProperty('score');
    });
  });

  describe('domain validation still applies', () => {
    it('throws on negative precipitation', () => {
      const entitlements = new InMemoryEntitlements(['road_passability']);

      expect(() => {
        getRoadPassability(entitlements, { ...validInput, precip72hIn: -1 });
      }).toThrow('Precipitation must be >= 0');
    });
  });

  describe('different road conditions', () => {
    const entitlements = new InMemoryEntitlements(['road_passability']);

    const testCases: Array<{
      name: string;
      input: { precip72hIn: number; slopePct: number; minTempF: number; soil: any };
      expectations: {
        scoreRange?: [number, number];
        mudRisk?: boolean;
        iceRisk?: boolean;
        fourByFourRecommended?: boolean;
      };
    }> = [
      {
        name: 'perfect conditions - dry loam flat road',
        input: { precip72hIn: 0, slopePct: 0, minTempF: 70, soil: SoilTypeEnum.LOAM },
        expectations: { scoreRange: [100, 100], mudRisk: false, iceRisk: false },
      },
      {
        name: 'clay with heavy rain - severe mud',
        input: { precip72hIn: 3.0, slopePct: 5, minTempF: 50, soil: SoilTypeEnum.CLAY },
        expectations: {
          scoreRange: [0, 50],
          mudRisk: true,
          iceRisk: false,
          fourByFourRecommended: true,
        },
      },
      {
        name: 'freeze with precipitation - ice risk',
        input: { precip72hIn: 0.8, slopePct: 0, minTempF: 28, soil: SoilTypeEnum.LOAM },
        expectations: {
          scoreRange: [0, 60],
          mudRisk: true,
          iceRisk: true,
          fourByFourRecommended: true,
        },
      },
      {
        name: 'dry sand - loose surface',
        input: { precip72hIn: 0, slopePct: 0, minTempF: 75, soil: SoilTypeEnum.SAND },
        expectations: { scoreRange: [85, 95], mudRisk: false, iceRisk: false },
      },
      {
        name: 'steep slope dry conditions',
        input: { precip72hIn: 0, slopePct: 20, minTempF: 60, soil: SoilTypeEnum.LOAM },
        expectations: { scoreRange: [80, 90], mudRisk: false, iceRisk: false },
      },
    ];

    testCases.forEach(({ name, input, expectations }) => {
      it(name, () => {
        const result = getRoadPassability(entitlements, input);

        if (expectations.scoreRange) {
          const [min, max] = expectations.scoreRange;
          expect(result.score).toBeGreaterThanOrEqual(min);
          expect(result.score).toBeLessThanOrEqual(max);
        }

        if (expectations.mudRisk !== undefined) {
          expect(result.mudRisk).toBe(expectations.mudRisk);
        }

        if (expectations.iceRisk !== undefined) {
          expect(result.iceRisk).toBe(expectations.iceRisk);
        }

        if (expectations.fourByFourRecommended !== undefined) {
          expect(result.fourByFourRecommended).toBe(expectations.fourByFourRecommended);
        }
      });
    });
  });

  describe('all soil types work', () => {
    const entitlements = new InMemoryEntitlements(['road_passability']);

    it('SAND soil type', () => {
      const result = getRoadPassability(entitlements, {
        precip72hIn: 1.0,
        slopePct: 5,
        minTempF: 60,
        soil: SoilTypeEnum.SAND,
      });

      expect(result.score).toBeGreaterThanOrEqual(0);
      expect(result.score).toBeLessThanOrEqual(100);
    });

    it('LOAM soil type', () => {
      const result = getRoadPassability(entitlements, {
        precip72hIn: 1.0,
        slopePct: 5,
        minTempF: 60,
        soil: SoilTypeEnum.LOAM,
      });

      expect(result.score).toBeGreaterThanOrEqual(0);
      expect(result.score).toBeLessThanOrEqual(100);
    });

    it('CLAY soil type', () => {
      const result = getRoadPassability(entitlements, {
        precip72hIn: 1.0,
        slopePct: 5,
        minTempF: 60,
        soil: SoilTypeEnum.CLAY,
      });

      expect(result.score).toBeGreaterThanOrEqual(0);
      expect(result.score).toBeLessThanOrEqual(100);
    });
  });
});
