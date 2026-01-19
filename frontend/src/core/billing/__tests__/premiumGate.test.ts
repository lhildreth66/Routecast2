import { premiumGate } from '../premiumGate';
import { InMemoryEntitlements } from '../Entitlements';
import { PremiumLockedError } from '../PremiumLockedError';

describe('premiumGate', () => {
  describe('when user has entitlement', () => {
    it('executes block and returns value', () => {
      const entitlements = new InMemoryEntitlements(['solar_forecast']);

      const result = premiumGate(entitlements, 'solar_forecast', () => {
        return 42;
      });

      expect(result).toBe(42);
    });

    it('executes block with complex return value', () => {
      const entitlements = new InMemoryEntitlements(['road_passability']);

      const result = premiumGate(entitlements, 'road_passability', () => {
        return { score: 85, mudRisk: false };
      });

      expect(result).toEqual({ score: 85, mudRisk: false });
    });

    it('executes block that throws other errors', () => {
      const entitlements = new InMemoryEntitlements(['battery_forecast']);

      expect(() => {
        premiumGate(entitlements, 'battery_forecast', () => {
          throw new Error('Domain logic error');
        });
      }).toThrow('Domain logic error');
    });

    it('allows access when all features granted', () => {
      const entitlements = new InMemoryEntitlements();
      entitlements.grantAll();

      const result = premiumGate(entitlements, 'solar_forecast', () => 'success');
      expect(result).toBe('success');
    });
  });

  describe('when user lacks entitlement', () => {
    it('throws PremiumLockedError', () => {
      const entitlements = new InMemoryEntitlements(); // No features granted

      expect(() => {
        premiumGate(entitlements, 'solar_forecast', () => {
          return 42;
        });
      }).toThrow(PremiumLockedError);
    });

    it('throws with correct feature name', () => {
      const entitlements = new InMemoryEntitlements();

      try {
        premiumGate(entitlements, 'road_passability', () => 42);
        fail('Should have thrown');
      } catch (error) {
        expect(error).toBeInstanceOf(PremiumLockedError);
        expect((error as PremiumLockedError).feature).toBe('road_passability');
      }
    });

    it('does not execute block when locked', () => {
      const entitlements = new InMemoryEntitlements();
      const mockBlock = jest.fn(() => 42);

      expect(() => {
        premiumGate(entitlements, 'solar_forecast', mockBlock);
      }).toThrow(PremiumLockedError);

      expect(mockBlock).not.toHaveBeenCalled();
    });

    it('throws even if user has other features', () => {
      const entitlements = new InMemoryEntitlements(['solar_forecast']);

      expect(() => {
        premiumGate(entitlements, 'road_passability', () => 42);
      }).toThrow(PremiumLockedError);
    });
  });

  describe('all feature types', () => {
    it('gates solar_forecast', () => {
      const entitlements = new InMemoryEntitlements();
      expect(() => premiumGate(entitlements, 'solar_forecast', () => 42)).toThrow();

      entitlements.grant('solar_forecast');
      expect(premiumGate(entitlements, 'solar_forecast', () => 42)).toBe(42);
    });

    it('gates road_passability', () => {
      const entitlements = new InMemoryEntitlements();
      expect(() => premiumGate(entitlements, 'road_passability', () => 42)).toThrow();

      entitlements.grant('road_passability');
      expect(premiumGate(entitlements, 'road_passability', () => 42)).toBe(42);
    });

    it('gates propane_forecast', () => {
      const entitlements = new InMemoryEntitlements();
      expect(() => premiumGate(entitlements, 'propane_forecast', () => 42)).toThrow();

      entitlements.grant('propane_forecast');
      expect(premiumGate(entitlements, 'propane_forecast', () => 42)).toBe(42);
    });

    it('gates battery_forecast', () => {
      const entitlements = new InMemoryEntitlements();
      expect(() => premiumGate(entitlements, 'battery_forecast', () => 42)).toThrow();

      entitlements.grant('battery_forecast');
      expect(premiumGate(entitlements, 'battery_forecast', () => 42)).toBe(42);
    });

    it('gates water_plan', () => {
      const entitlements = new InMemoryEntitlements();
      expect(() => premiumGate(entitlements, 'water_plan', () => 42)).toThrow();

      entitlements.grant('water_plan');
      expect(premiumGate(entitlements, 'water_plan', () => 42)).toBe(42);
    });

    it('gates cell_starlink', () => {
      const entitlements = new InMemoryEntitlements();
      expect(() => premiumGate(entitlements, 'cell_starlink', () => 42)).toThrow();

      entitlements.grant('cell_starlink');
      expect(premiumGate(entitlements, 'cell_starlink', () => 42)).toBe(42);
    });

    it('gates camp_index', () => {
      const entitlements = new InMemoryEntitlements();
      expect(() => premiumGate(entitlements, 'camp_index', () => 42)).toThrow();

      entitlements.grant('camp_index');
      expect(premiumGate(entitlements, 'camp_index', () => 42)).toBe(42);
    });

    it('gates claim_log', () => {
      const entitlements = new InMemoryEntitlements();
      expect(() => premiumGate(entitlements, 'claim_log', () => 42)).toThrow();

      entitlements.grant('claim_log');
      expect(premiumGate(entitlements, 'claim_log', () => 42)).toBe(42);
    });
  });

  describe('InMemoryEntitlements', () => {
    it('starts with no features by default', () => {
      const entitlements = new InMemoryEntitlements();
      expect(entitlements.has('solar_forecast')).toBe(false);
      expect(entitlements.getGranted()).toEqual([]);
    });

    it('can be initialized with features', () => {
      const entitlements = new InMemoryEntitlements(['solar_forecast', 'road_passability']);
      expect(entitlements.has('solar_forecast')).toBe(true);
      expect(entitlements.has('road_passability')).toBe(true);
      expect(entitlements.has('battery_forecast')).toBe(false);
    });

    it('can grant features', () => {
      const entitlements = new InMemoryEntitlements();
      entitlements.grant('solar_forecast');
      expect(entitlements.has('solar_forecast')).toBe(true);
    });

    it('can revoke features', () => {
      const entitlements = new InMemoryEntitlements(['solar_forecast']);
      expect(entitlements.has('solar_forecast')).toBe(true);

      entitlements.revoke('solar_forecast');
      expect(entitlements.has('solar_forecast')).toBe(false);
    });

    it('grantAll grants all 8 features', () => {
      const entitlements = new InMemoryEntitlements();
      entitlements.grantAll();

      expect(entitlements.has('solar_forecast')).toBe(true);
      expect(entitlements.has('road_passability')).toBe(true);
      expect(entitlements.has('propane_forecast')).toBe(true);
      expect(entitlements.has('battery_forecast')).toBe(true);
      expect(entitlements.has('water_plan')).toBe(true);
      expect(entitlements.has('cell_starlink')).toBe(true);
      expect(entitlements.has('camp_index')).toBe(true);
      expect(entitlements.has('claim_log')).toBe(true);

      expect(entitlements.getGranted()).toHaveLength(8);
    });

    it('revokeAll removes all features', () => {
      const entitlements = new InMemoryEntitlements();
      entitlements.grantAll();
      expect(entitlements.getGranted()).toHaveLength(8);

      entitlements.revokeAll();
      expect(entitlements.getGranted()).toEqual([]);
      expect(entitlements.has('solar_forecast')).toBe(false);
    });

    it('getGranted returns current features', () => {
      const entitlements = new InMemoryEntitlements(['solar_forecast', 'road_passability']);
      const granted = entitlements.getGranted();

      expect(granted).toContain('solar_forecast');
      expect(granted).toContain('road_passability');
      expect(granted).toHaveLength(2);
    });
  });

  describe('PremiumLockedError properties', () => {
    it('has correct name', () => {
      const error = new PremiumLockedError('solar_forecast');
      expect(error.name).toBe('PremiumLockedError');
    });

    it('has default message', () => {
      const error = new PremiumLockedError('solar_forecast');
      expect(error.message).toBe('Premium feature locked: solar_forecast');
    });

    it('allows custom message', () => {
      const error = new PremiumLockedError('solar_forecast', 'Custom message');
      expect(error.message).toBe('Custom message');
      expect(error.feature).toBe('solar_forecast');
    });

    it('is instance of Error', () => {
      const error = new PremiumLockedError('solar_forecast');
      expect(error).toBeInstanceOf(Error);
    });
  });
});
