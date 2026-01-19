import { CachedEntitlements } from '../CachedEntitlements';
import type { EntitlementsStore, PersistedEntitlements } from '../EntitlementsStore';
import type { Feature } from '../PremiumLockedError';

describe('CachedEntitlements', () => {
  let mockStore: jest.Mocked<EntitlementsStore>;
  let mockNow: jest.Mock;
  let currentTime: number;

  beforeEach(() => {
    currentTime = 1000000000; // Fixed timestamp
    mockNow = jest.fn(() => currentTime);
    
    mockStore = {
      get: jest.fn(),
      set: jest.fn(),
      clear: jest.fn(),
    };
  });

  describe('hydrate', () => {
    it('loads features from store', async () => {
      mockStore.get.mockResolvedValue({
        features: ['solar_forecast', 'road_passability'],
        expireAt: currentTime + 100000,
      });

      const entitlements = new CachedEntitlements(mockStore, mockNow);
      await entitlements.hydrate();

      expect(entitlements.has('solar_forecast')).toBe(true);
      expect(entitlements.has('road_passability')).toBe(true);
      expect(entitlements.has('battery_forecast')).toBe(false);
    });

    it('starts with empty state when no data in store', async () => {
      mockStore.get.mockResolvedValue(null);

      const entitlements = new CachedEntitlements(mockStore, mockNow);
      await entitlements.hydrate();

      expect(entitlements.has('solar_forecast')).toBe(false);
      expect(entitlements.getGranted()).toEqual([]);
    });

    it('clears expired entitlements on hydrate', async () => {
      mockStore.get.mockResolvedValue({
        features: ['solar_forecast', 'road_passability'],
        expireAt: currentTime - 1, // Expired
      });

      const entitlements = new CachedEntitlements(mockStore, mockNow);
      await entitlements.hydrate();

      expect(entitlements.has('solar_forecast')).toBe(false);
      expect(entitlements.has('road_passability')).toBe(false);
      expect(mockStore.clear).toHaveBeenCalled();
    });

    it('handles store errors gracefully', async () => {
      mockStore.get.mockRejectedValue(new Error('Storage error'));

      const entitlements = new CachedEntitlements(mockStore, mockNow);
      await entitlements.hydrate();

      // Should start with empty state
      expect(entitlements.has('solar_forecast')).toBe(false);
    });
  });

  describe('has', () => {
    it('returns true for granted features', async () => {
      mockStore.get.mockResolvedValue({
        features: ['battery_forecast'],
      });

      const entitlements = new CachedEntitlements(mockStore, mockNow);
      await entitlements.hydrate();

      expect(entitlements.has('battery_forecast')).toBe(true);
    });

    it('returns false for non-granted features', async () => {
      mockStore.get.mockResolvedValue({
        features: ['battery_forecast'],
      });

      const entitlements = new CachedEntitlements(mockStore, mockNow);
      await entitlements.hydrate();

      expect(entitlements.has('solar_forecast')).toBe(false);
    });

    it('returns false for granted but expired features', async () => {
      mockStore.get.mockResolvedValue({
        features: ['solar_forecast'],
        expireAt: currentTime + 1000,
      });

      const entitlements = new CachedEntitlements(mockStore, mockNow);
      await entitlements.hydrate();

      expect(entitlements.has('solar_forecast')).toBe(true);

      // Advance time past expiration
      currentTime += 2000;

      expect(entitlements.has('solar_forecast')).toBe(false);
    });

    it('returns true when expireAt is in future', async () => {
      mockStore.get.mockResolvedValue({
        features: ['road_passability'],
        expireAt: currentTime + 100000,
      });

      const entitlements = new CachedEntitlements(mockStore, mockNow);
      await entitlements.hydrate();

      expect(entitlements.has('road_passability')).toBe(true);
    });
  });

  describe('grant', () => {
    it('grants features and persists to store', async () => {
      mockStore.get.mockResolvedValue(null);

      const entitlements = new CachedEntitlements(mockStore, mockNow);
      await entitlements.hydrate();

      const features: Feature[] = ['solar_forecast', 'battery_forecast'];
      const expireAt = currentTime + 50000;

      await entitlements.grant(features, expireAt);

      expect(entitlements.has('solar_forecast')).toBe(true);
      expect(entitlements.has('battery_forecast')).toBe(true);
      
      expect(mockStore.set).toHaveBeenCalledWith({
        features: expect.arrayContaining(features),
        expireAt,
      });
    });

    it('adds to existing features', async () => {
      mockStore.get.mockResolvedValue({
        features: ['solar_forecast'],
      });

      const entitlements = new CachedEntitlements(mockStore, mockNow);
      await entitlements.hydrate();

      await entitlements.grant(['road_passability']);

      expect(entitlements.has('solar_forecast')).toBe(true);
      expect(entitlements.has('road_passability')).toBe(true);
      
      expect(mockStore.set).toHaveBeenCalledWith({
        features: expect.arrayContaining(['solar_forecast', 'road_passability']),
        expireAt: undefined,
      });
    });

    it('handles store errors gracefully', async () => {
      mockStore.get.mockResolvedValue(null);
      mockStore.set.mockRejectedValue(new Error('Storage error'));

      const entitlements = new CachedEntitlements(mockStore, mockNow);
      await entitlements.hydrate();

      await entitlements.grant(['solar_forecast']);

      // Should still work in-memory
      expect(entitlements.has('solar_forecast')).toBe(true);
    });
  });

  describe('revokeAll', () => {
    it('clears all features and store', async () => {
      mockStore.get.mockResolvedValue({
        features: ['solar_forecast', 'battery_forecast'],
      });

      const entitlements = new CachedEntitlements(mockStore, mockNow);
      await entitlements.hydrate();

      expect(entitlements.has('solar_forecast')).toBe(true);

      await entitlements.revokeAll();

      expect(entitlements.has('solar_forecast')).toBe(false);
      expect(entitlements.has('battery_forecast')).toBe(false);
      expect(entitlements.getGranted()).toEqual([]);
      expect(mockStore.clear).toHaveBeenCalled();
    });

    it('handles store errors gracefully', async () => {
      mockStore.get.mockResolvedValue({
        features: ['solar_forecast'],
      });
      mockStore.clear.mockRejectedValue(new Error('Storage error'));

      const entitlements = new CachedEntitlements(mockStore, mockNow);
      await entitlements.hydrate();

      await entitlements.revokeAll();

      // Should still clear in-memory
      expect(entitlements.has('solar_forecast')).toBe(false);
    });
  });

  describe('getGranted', () => {
    it('returns all granted features', async () => {
      mockStore.get.mockResolvedValue({
        features: ['solar_forecast', 'road_passability', 'camp_index'],
      });

      const entitlements = new CachedEntitlements(mockStore, mockNow);
      await entitlements.hydrate();

      const granted = entitlements.getGranted();

      expect(granted).toHaveLength(3);
      expect(granted).toContain('solar_forecast');
      expect(granted).toContain('road_passability');
      expect(granted).toContain('camp_index');
    });

    it('returns empty array when expired', async () => {
      mockStore.get.mockResolvedValue({
        features: ['solar_forecast'],
        expireAt: currentTime + 1000,
      });

      const entitlements = new CachedEntitlements(mockStore, mockNow);
      await entitlements.hydrate();

      expect(entitlements.getGranted()).toEqual(['solar_forecast']);

      // Advance time past expiration
      currentTime += 2000;

      expect(entitlements.getGranted()).toEqual([]);
    });
  });

  describe('persistence integration', () => {
    it('survives hydration after grant', async () => {
      // Simulate persistent storage
      let stored: PersistedEntitlements | null = null;
      mockStore.set.mockImplementation(async (data) => {
        stored = data;
      });
      mockStore.get.mockImplementation(async () => stored);

      // First instance - grant features
      const entitlements1 = new CachedEntitlements(mockStore, mockNow);
      await entitlements1.hydrate();
      await entitlements1.grant(['solar_forecast', 'battery_forecast'], currentTime + 50000);

      // Second instance - simulate app restart
      const entitlements2 = new CachedEntitlements(mockStore, mockNow);
      await entitlements2.hydrate();

      // Should have persisted features
      expect(entitlements2.has('solar_forecast')).toBe(true);
      expect(entitlements2.has('battery_forecast')).toBe(true);
    });

    it('does not restore expired entitlements on new hydrate', async () => {
      // Simulate persistent storage
      let stored: PersistedEntitlements | null = null;
      mockStore.set.mockImplementation(async (data) => {
        stored = data;
      });
      mockStore.get.mockImplementation(async () => stored);
      mockStore.clear.mockImplementation(async () => {
        stored = null;
      });

      // First instance - grant features with near expiration
      const entitlements1 = new CachedEntitlements(mockStore, mockNow);
      await entitlements1.hydrate();
      await entitlements1.grant(['solar_forecast'], currentTime + 1000);

      // Advance time past expiration
      currentTime += 2000;

      // Second instance - simulate app restart after expiration
      const entitlements2 = new CachedEntitlements(mockStore, mockNow);
      await entitlements2.hydrate();

      // Should NOT have expired features
      expect(entitlements2.has('solar_forecast')).toBe(false);
      expect(entitlements2.getGranted()).toEqual([]);
    });
  });
});
