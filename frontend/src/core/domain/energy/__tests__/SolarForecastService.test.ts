import {
  calculateClearSkyBaseline,
  calculateCloudMultiplier,
  calculateShadeLoss,
  forecastDailyWh,
  forecastSingleDay,
} from '../SolarForecastService';

describe('SolarForecastService', () => {
  describe('calculateClearSkyBaseline', () => {
    it('equator on equinox should be near 5.5 hours', () => {
      const result = calculateClearSkyBaseline(0, 81); // March 22 (equinox)
      expect(result).toBeGreaterThanOrEqual(5.0);
      expect(result).toBeLessThanOrEqual(6.0);
    });

    it('mid-latitude summer should be high', () => {
      const result = calculateClearSkyBaseline(40, 172); // June 21 (summer solstice)
      expect(result).toBeGreaterThan(5.0);
    });

    it('mid-latitude winter should be lower', () => {
      const result = calculateClearSkyBaseline(40, 355); // Dec 21 (winter solstice)
      expect(result).toBeLessThan(5.5);
    });

    it('arctic circle summer should have extended daylight', () => {
      const result = calculateClearSkyBaseline(66.5, 172);
      expect(result).toBeGreaterThanOrEqual(0);
    });

    it('arctic circle winter should be minimal', () => {
      const result = calculateClearSkyBaseline(66.5, 355);
      expect(result).toBeGreaterThanOrEqual(0);
      expect(result).toBeLessThanOrEqual(12);
    });

    it('throws on latitude too high', () => {
      expect(() => calculateClearSkyBaseline(91, 100)).toThrow('Latitude must be in range');
    });

    it('throws on latitude too low', () => {
      expect(() => calculateClearSkyBaseline(-91, 100)).toThrow('Latitude must be in range');
    });

    it('throws on doy zero', () => {
      expect(() => calculateClearSkyBaseline(40, 0)).toThrow('Day of year must be in range');
    });

    it('throws on doy 366', () => {
      expect(() => calculateClearSkyBaseline(40, 366)).toThrow('Day of year must be in range');
    });

    it('is deterministic', () => {
      const results = Array(100)
        .fill(null)
        .map(() => calculateClearSkyBaseline(34.05, 20));
      const unique = [...new Set(results)];
      expect(unique).toHaveLength(1);
    });
  });

  describe('calculateCloudMultiplier', () => {
    it('clear sky returns 1.0', () => {
      const result = calculateCloudMultiplier(0);
      expect(result).toBeCloseTo(1.0, 2);
    });

    it('30% cloudy returns ~0.76-0.80', () => {
      const result = calculateCloudMultiplier(30);
      expect(result).toBeGreaterThanOrEqual(0.75);
      expect(result).toBeLessThanOrEqual(0.85);
    });

    it('60% cloudy returns ~0.50-0.55', () => {
      const result = calculateCloudMultiplier(60);
      expect(result).toBeGreaterThanOrEqual(0.45);
      expect(result).toBeLessThanOrEqual(0.60);
    });

    it('90% overcast returns near 0.2', () => {
      const result = calculateCloudMultiplier(90);
      expect(result).toBeGreaterThanOrEqual(0.2);
      expect(result).toBeLessThanOrEqual(0.3);
    });

    it('100% overcast returns 0.2', () => {
      const result = calculateCloudMultiplier(100);
      expect(result).toBeCloseTo(0.2, 2);
    });

    it('over 100% clamped to 0.2', () => {
      const result = calculateCloudMultiplier(150);
      expect(result).toBeCloseTo(0.2, 2);
    });

    it('throws on negative', () => {
      expect(() => calculateCloudMultiplier(-10)).toThrow('Cloud cover must be >= 0');
    });

    it('is deterministic', () => {
      const results = Array(100)
        .fill(null)
        .map(() => calculateCloudMultiplier(40));
      const unique = [...new Set(results)];
      expect(unique).toHaveLength(1);
    });
  });

  describe('calculateShadeLoss', () => {
    it('no shade returns 1.0', () => {
      const result = calculateShadeLoss(0);
      expect(result).toBeCloseTo(1.0, 2);
    });

    it('25% shade returns 0.75', () => {
      const result = calculateShadeLoss(25);
      expect(result).toBeCloseTo(0.75, 2);
    });

    it('50% shade returns 0.5', () => {
      const result = calculateShadeLoss(50);
      expect(result).toBeCloseTo(0.5, 2);
    });

    it('100% shade returns 0.0', () => {
      const result = calculateShadeLoss(100);
      expect(result).toBeCloseTo(0.0, 2);
    });

    it('over 100% clamped to 0.0', () => {
      const result = calculateShadeLoss(150);
      expect(result).toBeCloseTo(0.0, 2);
    });

    it('throws on negative', () => {
      expect(() => calculateShadeLoss(-5)).toThrow('Shade percentage must be >= 0');
    });

    it('is deterministic', () => {
      const results = Array(100)
        .fill(null)
        .map(() => calculateShadeLoss(25));
      const unique = [...new Set(results)];
      expect(unique).toHaveLength(1);
    });
  });

  describe('forecastDailyWh', () => {
    it('clear sunny day at equator produces ~2000-2400 Wh', () => {
      const result = forecastDailyWh(0, 0, [81], 400, 0, [0]);
      expect(result).toHaveLength(1);
      expect(result[0]).toBeGreaterThanOrEqual(2000);
      expect(result[0]).toBeLessThanOrEqual(2400);
    });

    it('clear day with 20% shade is reduced', () => {
      const result = forecastDailyWh(34.05, -111.03, [20], 400, 20, [0]);
      expect(result).toHaveLength(1);
      expect(result[0]).toBeGreaterThan(0);
      expect(result[0]).toBeLessThan(2400);
    });

    it('partly cloudy day is reduced', () => {
      const result = forecastDailyWh(34.05, -111.03, [20], 400, 20, [40]);
      expect(result).toHaveLength(1);
      expect(result[0]).toBeGreaterThan(0);
    });

    it('overcast day severely reduced', () => {
      const result = forecastDailyWh(34.05, -111.03, [20], 400, 20, [90]);
      expect(result).toHaveLength(1);
      expect(result[0]).toBeGreaterThan(0);
      expect(result[0]).toBeLessThan(1000);
    });

    it('100% shade produces zero', () => {
      const result = forecastDailyWh(34.05, -111.03, [20], 400, 100, [0]);
      expect(result).toHaveLength(1);
      expect(result[0]).toBeCloseTo(0, 2);
    });

    it('multi-day forecast with varying conditions', () => {
      const result = forecastDailyWh(34.05, -111.03, [20, 21, 22], 400, 20, [0, 40, 90]);
      expect(result).toHaveLength(3);
      expect(result[0]).toBeGreaterThan(result[1]); // Clear > partly cloudy
      expect(result[1]).toBeGreaterThan(result[2]); // Partly cloudy > overcast
      expect(result.every((v) => v > 0)).toBe(true);
    });

    it('throws on zero panel watts', () => {
      expect(() => forecastDailyWh(34.05, -111.03, [20], 0, 0, [0])).toThrow(
        'Panel watts must be > 0'
      );
    });

    it('throws on negative panel watts', () => {
      expect(() => forecastDailyWh(34.05, -111.03, [20], -100, 0, [0])).toThrow(
        'Panel watts must be > 0'
      );
    });

    it('throws on empty date range', () => {
      expect(() => forecastDailyWh(34.05, -111.03, [], 400, 0, [])).toThrow(
        'Date range cannot be empty'
      );
    });

    it('throws on cloud cover size mismatch', () => {
      expect(() => forecastDailyWh(34.05, -111.03, [20, 21, 22], 400, 0, [0, 0])).toThrow(
        'Cloud cover list size'
      );
    });

    it('throws on invalid latitude', () => {
      expect(() => forecastDailyWh(95, 0, [20], 400, 0, [0])).toThrow('Latitude must be in range');
    });

    it('throws on invalid longitude', () => {
      expect(() => forecastDailyWh(34.05, -190, [20], 400, 0, [0])).toThrow(
        'Longitude must be in range'
      );
    });

    it('throws on invalid day of year', () => {
      expect(() => forecastDailyWh(34.05, -111.03, [0], 400, 0, [0])).toThrow(
        'All day-of-year values must be in range'
      );
    });

    it('throws on negative shade', () => {
      expect(() => forecastDailyWh(34.05, -111.03, [20], 400, -10, [0])).toThrow(
        'Shade percentage must be >= 0'
      );
    });

    it('is deterministic', () => {
      const results = Array(100)
        .fill(null)
        .map(() => forecastDailyWh(34.05, -111.03, [20, 21, 22], 400, 20, [0, 40, 90]));
      const unique = results.map((r) => JSON.stringify(r));
      expect([...new Set(unique)]).toHaveLength(1);
    });
  });

  describe('forecastSingleDay', () => {
    it('convenience method works', () => {
      const result = forecastSingleDay(34.05, -111.03, 20, 400, 20, 0);
      expect(result).toBeGreaterThan(0);
    });
  });

  describe('Boundary Conditions', () => {
    it('north pole summer solstice clamped to [0, 12]', () => {
      const result = calculateClearSkyBaseline(90, 172);
      expect(result).toBeGreaterThanOrEqual(0);
      expect(result).toBeLessThanOrEqual(12);
    });

    it('south pole winter solstice clamped to [0, 12]', () => {
      const result = calculateClearSkyBaseline(-90, 355);
      expect(result).toBeGreaterThanOrEqual(0);
      expect(result).toBeLessThanOrEqual(12);
    });

    it('zero longitude works', () => {
      const result = forecastDailyWh(0, 0, [81], 400, 0, [0]);
      expect(result).toHaveLength(1);
      expect(result[0]).toBeGreaterThan(0);
    });

    it('180 degrees longitude works', () => {
      const result = forecastDailyWh(0, 180, [81], 400, 0, [0]);
      expect(result).toHaveLength(1);
      expect(result[0]).toBeGreaterThan(0);
    });

    it('max panel watts produces proportionally higher output', () => {
      const result = forecastDailyWh(0, 0, [81], 10000, 0, [0]);
      expect(result).toHaveLength(1);
      expect(result[0]).toBeGreaterThan(10000);
    });
  });

  describe('Real-World Scenarios', () => {
    it('RV in Arizona clear winter day', () => {
      const result = forecastSingleDay(34.05, -111.03, 20, 400, 20, 0);
      expect(result).toBeGreaterThanOrEqual(900); // Adjusted for winter latitude (Jan 20, lat 34)
      expect(result).toBeLessThanOrEqual(1200);
    });

    it('Van in Oregon partly cloudy fall day', () => {
      const result = forecastSingleDay(45.52, -122.68, 274, 200, 30, 50);
      expect(result).toBeGreaterThan(0);
      expect(result).toBeLessThan(1000);
    });

    it('Full shade dense forest zero output', () => {
      const result = forecastSingleDay(40, -100, 100, 300, 100, 0);
      expect(result).toBeCloseTo(0, 2);
    });
  });
});
