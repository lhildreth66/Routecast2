import { score, SoilType, Passability } from '../RoadPassability';

describe('RoadPassability', () => {
  describe('Clay Soil Tests', () => {
    it('clay with heavy rain - severe mud risk', () => {
      const result = score(3.0, 5.0, 50, SoilType.CLAY);
      expect(result.score).toBeLessThan(50);
      expect(result.mudRisk).toBe(true);
      expect(result.iceRisk).toBe(false);
      expect(result.clearanceNeed).toBe(true);
      expect(result.fourByFourRecommended).toBe(true);
      expect(result.notes.some((n) => n.includes('severe mud'))).toBe(true);
    });

    it('clay with moderate rain - significant mud', () => {
      const result = score(1.0, 0.0, 60, SoilType.CLAY);
      expect(result.score).toBeGreaterThanOrEqual(40);
      expect(result.score).toBeLessThanOrEqual(60);
      expect(result.mudRisk).toBe(true);
      expect(result.iceRisk).toBe(false);
      expect(result.clearanceNeed).toBe(false);
      expect(result.notes.some((n) => n.includes('mud'))).toBe(true);
    });

    it('clay with light rain - slippery', () => {
      const result = score(0.3, 0.0, 55, SoilType.CLAY);
      expect(result.score).toBeGreaterThanOrEqual(70);
      expect(result.score).toBeLessThanOrEqual(85);
      expect(result.mudRisk).toBe(false);
      expect(result.iceRisk).toBe(false);
      expect(result.notes.some((n) => n.includes('slippery'))).toBe(true);
    });

    it('clay dry conditions - good passability', () => {
      const result = score(0.0, 5.0, 70, SoilType.CLAY);
      expect(result.score).toBe(100);
      expect(result.mudRisk).toBe(false);
      expect(result.iceRisk).toBe(false);
      expect(result.clearanceNeed).toBe(false);
      expect(result.fourByFourRecommended).toBe(false);
    });
  });

  describe('Loam Soil Tests', () => {
    it('loam with heavy rain - moderate mud risk', () => {
      const result = score(2.5, 0.0, 55, SoilType.LOAM);
      expect(result.score).toBeGreaterThanOrEqual(60);
      expect(result.score).toBeLessThanOrEqual(75);
      expect(result.mudRisk).toBe(true);
      expect(result.iceRisk).toBe(false);
      expect(result.clearanceNeed).toBe(true);
      expect(result.notes.some((n) => n.includes('moderate mud'))).toBe(true);
    });

    it('loam with moderate rain - soft surface', () => {
      const result = score(1.0, 8.0, 60, SoilType.LOAM);
      expect(result.score).toBeGreaterThanOrEqual(70);
      expect(result.score).toBeLessThanOrEqual(85);
      expect(result.mudRisk).toBe(true);
      expect(result.iceRisk).toBe(false);
      expect(result.notes.some((n) => n.includes('soft'))).toBe(true);
    });

    it('loam with light rain - minor wet conditions', () => {
      const result = score(0.2, 0.0, 50, SoilType.LOAM);
      expect(result.score).toBeGreaterThanOrEqual(85);
      expect(result.score).toBeLessThanOrEqual(95);
      expect(result.mudRisk).toBe(false);
      expect(result.iceRisk).toBe(false);
    });

    it('loam dry conditions - excellent', () => {
      const result = score(0.0, 0.0, 65, SoilType.LOAM);
      expect(result.score).toBe(100);
      expect(result.mudRisk).toBe(false);
      expect(result.fourByFourRecommended).toBe(false);
    });
  });

  describe('Sand Soil Tests', () => {
    it('sand with heavy rain - loose wet surface', () => {
      const result = score(3.0, 0.0, 70, SoilType.SAND);
      expect(result.score).toBeGreaterThanOrEqual(75);
      expect(result.score).toBeLessThanOrEqual(85);
      expect(result.mudRisk).toBe(false);
      expect(result.iceRisk).toBe(false);
      expect(result.notes.some((n) => n.includes('loose wet'))).toBe(true);
    });

    it('sand with moderate rain - soft spots', () => {
      const result = score(1.0, 5.0, 60, SoilType.SAND);
      expect(result.score).toBeGreaterThanOrEqual(80);
      expect(result.score).toBeLessThanOrEqual(90);
      expect(result.mudRisk).toBe(false);
      expect(result.notes.some((n) => n.includes('soft'))).toBe(true);
    });

    it('sand with light rain - mostly firm', () => {
      const result = score(0.3, 0.0, 55, SoilType.SAND);
      expect(result.score).toBeGreaterThanOrEqual(90);
      expect(result.score).toBeLessThanOrEqual(100);
      expect(result.mudRisk).toBe(false);
    });

    it('sand dry conditions - loose surface penalty', () => {
      const result = score(0.0, 0.0, 75, SoilType.SAND);
      expect(result.score).toBeLessThan(100);
      expect(result.score).toBe(90);
      expect(result.mudRisk).toBe(false);
      expect(result.notes.some((n) => n.includes('Dry sand'))).toBe(true);
    });
  });

  describe('Freezing Conditions', () => {
    it('freeze with precipitation - ice risk', () => {
      const result = score(0.5, 0.0, 28, SoilType.LOAM);
      expect(result.score).toBeLessThan(60);
      expect(result.mudRisk).toBe(false); // 0.5 is NOT > 0.5
      expect(result.iceRisk).toBe(true);
      expect(result.clearanceNeed).toBe(true);
      expect(result.notes.some((n) => n.includes('ice'))).toBe(true);
    });

    it('freeze with heavy precip - severe ice risk', () => {
      const result = score(1.5, 5.0, 30, SoilType.CLAY);
      expect(result.score).toBeLessThan(30);
      expect(result.mudRisk).toBe(true);
      expect(result.iceRisk).toBe(true);
      expect(result.fourByFourRecommended).toBe(true);
    });

    it('freeze without precipitation - no ice risk', () => {
      const result = score(0.0, 0.0, 25, SoilType.LOAM);
      expect(result.score).toBe(100);
      expect(result.iceRisk).toBe(false);
    });

    it('exactly 32F with precip - ice risk boundary', () => {
      const result = score(0.2, 0.0, 32, SoilType.SAND);
      expect(result.iceRisk).toBe(true);
      expect(result.score).toBeLessThan(100);
    });
  });

  describe('Slope Tests', () => {
    it('steep slope dry conditions', () => {
      const result = score(0.0, 20.0, 60, SoilType.LOAM);
      expect(result.score).toBeLessThan(100);
      expect(result.score).toBe(85);
      expect(result.mudRisk).toBe(false);
      expect(result.clearanceNeed).toBe(true);
      expect(result.notes.some((n) => n.includes('Steep'))).toBe(true);
    });

    it('very steep slope - high clearance required', () => {
      const result = score(0.0, 30.0, 65, SoilType.SAND);
      expect(result.score).toBeLessThan(70);
      expect(result.clearanceNeed).toBe(true);
      expect(result.notes.some((n) => n.includes('Very steep'))).toBe(true);
    });

    it('moderate slope - no penalty', () => {
      const result = score(0.0, 10.0, 70, SoilType.LOAM);
      expect(result.score).toBe(100);
      expect(result.clearanceNeed).toBe(false);
    });
  });

  describe('Combined Factors', () => {
    it('mud plus slope - compounding difficulty', () => {
      const result = score(1.5, 16.0, 50, SoilType.CLAY); // Use 16% to trigger steep slope
      expect(result.score).toBeLessThan(40); // -40 (moderate rain clay) -15 (steep) -10 (compound) = 35
      expect(result.mudRisk).toBe(true);
      expect(result.clearanceNeed).toBe(true);
      expect(result.fourByFourRecommended).toBe(true);
      expect(result.notes.some((n) => n.includes('compounding'))).toBe(true);
    });

    it('ice plus slope - dangerous conditions', () => {
      const result = score(0.8, 18.0, 28, SoilType.LOAM);
      expect(result.score).toBeLessThan(20);
      expect(result.mudRisk).toBe(true);
      expect(result.iceRisk).toBe(true);
      expect(result.clearanceNeed).toBe(true);
      expect(result.fourByFourRecommended).toBe(true);
      expect(result.notes.some((n) => n.includes('dangerous'))).toBe(true);
    });

    it('worst case - clay heavy rain steep slope freeze', () => {
      const result = score(3.0, 25.0, 30, SoilType.CLAY);
      expect(result.score).toBeLessThan(10);
      expect(result.mudRisk).toBe(true);
      expect(result.iceRisk).toBe(true);
      expect(result.clearanceNeed).toBe(true);
      expect(result.fourByFourRecommended).toBe(true);
      expect(result.notes.length).toBeGreaterThanOrEqual(4);
    });
  });

  describe('Edge Cases', () => {
    it('zero precipitation - perfect conditions', () => {
      const result = score(0.0, 0.0, 70, SoilType.LOAM);
      expect(result.score).toBe(100);
      expect(result.mudRisk).toBe(false);
      expect(result.iceRisk).toBe(false);
      expect(result.clearanceNeed).toBe(false);
      expect(result.fourByFourRecommended).toBe(false);
    });

    it('negative slope clamped to zero', () => {
      const result = score(0.0, -15.0, 60, SoilType.LOAM);
      expect(result.score).toBe(100);
      expect(result.clearanceNeed).toBe(false);
    });

    it('extreme high temperature', () => {
      const result = score(0.0, 0.0, 110, SoilType.SAND);
      expect(result.score).toBe(90);
      expect(result.iceRisk).toBe(false);
    });

    it('extreme low temperature without precip', () => {
      const result = score(0.0, 0.0, -20, SoilType.CLAY);
      expect(result.score).toBe(100);
      expect(result.iceRisk).toBe(false);
    });

    it('trace precipitation - no mud risk', () => {
      const result = score(0.05, 0.0, 50, SoilType.CLAY);
      expect(result.score).toBeGreaterThanOrEqual(80);
      expect(result.mudRisk).toBe(false);
    });

    it('very heavy precipitation - score clamped at zero', () => {
      const result = score(10.0, 30.0, 32, SoilType.CLAY);
      expect(result.score).toBe(0);
      expect(result.mudRisk).toBe(true);
      expect(result.iceRisk).toBe(true);
      expect(result.clearanceNeed).toBe(true);
      expect(result.fourByFourRecommended).toBe(true);
    });
  });

  describe('Invalid Inputs', () => {
    it('negative precipitation throws exception', () => {
      expect(() => score(-1.0, 5.0, 60, SoilType.LOAM)).toThrow('Precipitation must be >= 0');
    });
  });

  describe('Determinism Tests', () => {
    it('score is deterministic - clay heavy rain', () => {
      const results = Array(100)
        .fill(null)
        .map(() => score(2.5, 10.0, 50, SoilType.CLAY));
      const uniqueScores = [...new Set(results.map((r) => r.score))];
      expect(uniqueScores).toHaveLength(1);

      const uniqueMudRisk = [...new Set(results.map((r) => r.mudRisk))];
      expect(uniqueMudRisk).toHaveLength(1);
    });

    it('score is deterministic - freeze conditions', () => {
      const results = Array(100)
        .fill(null)
        .map(() => score(1.0, 15.0, 30, SoilType.LOAM));
      const unique = results.map((r) => JSON.stringify(r));
      expect([...new Set(unique)]).toHaveLength(1);
    });

    it('score is deterministic - all soil types', () => {
      for (const soil of [SoilType.SAND, SoilType.LOAM, SoilType.CLAY]) {
        const results = Array(50)
          .fill(null)
          .map(() => score(1.5, 12.0, 45, soil));
        const unique = results.map((r) => JSON.stringify(r));
        expect([...new Set(unique)]).toHaveLength(1);
      }
    });
  });

  describe('Boundary Conditions', () => {
    it('exactly 0.5 inches does NOT trigger mud risk for clay', () => {
      const result = score(0.5, 0.0, 60, SoilType.CLAY);
      expect(result.mudRisk).toBe(false);
    });

    it('just over 0.5 inches triggers mud risk', () => {
      const result = score(0.51, 0.0, 60, SoilType.CLAY);
      expect(result.mudRisk).toBe(true);
    });

    it('exactly 2.0 inches is NOT heavy rain', () => {
      const result = score(2.0, 0.0, 50, SoilType.CLAY);
      expect(result.notes.some((n) => n.includes('Heavy rain'))).toBe(false);
    });

    it('just over 2.0 inches triggers heavy rain', () => {
      const result = score(2.01, 0.0, 50, SoilType.CLAY);
      expect(result.notes.some((n) => n.includes('Heavy rain'))).toBe(true);
    });

    it('exactly 15% slope does NOT trigger steep penalty', () => {
      const result = score(0.0, 15.0, 60, SoilType.LOAM);
      expect(result.score).toBe(100);
    });

    it('just over 15% slope triggers steep', () => {
      const result = score(0.0, 15.1, 60, SoilType.LOAM);
      expect(result.notes.some((n) => n.includes('Steep'))).toBe(true);
    });
  });

  describe('Score Range Validation', () => {
    it('score always in valid range 0 to 100', () => {
      const testCases: Array<[number, number, number, SoilType]> = [
        [0.0, 0.0, 70, SoilType.LOAM],
        [5.0, 40.0, 20, SoilType.CLAY],
        [1.5, 15.0, 32, SoilType.SAND],
        [3.0, 25.0, 28, SoilType.CLAY],
        [0.1, 5.0, 100, SoilType.SAND],
      ];

      testCases.forEach(([precip, slope, temp, soil]) => {
        const result = score(precip, slope, temp, soil);
        expect(result.score).toBeGreaterThanOrEqual(0);
        expect(result.score).toBeLessThanOrEqual(100);
      });
    });

    it('fourByFourRecommended correlates with low score', () => {
      const lowScore = score(3.0, 20.0, 30, SoilType.CLAY);
      expect(lowScore.score).toBeLessThan(50);
      expect(lowScore.fourByFourRecommended).toBe(true);

      const highScore = score(0.0, 0.0, 70, SoilType.LOAM);
      expect(highScore.score).toBeGreaterThanOrEqual(50);
      expect(highScore.fourByFourRecommended).toBe(false);
    });
  });
});
