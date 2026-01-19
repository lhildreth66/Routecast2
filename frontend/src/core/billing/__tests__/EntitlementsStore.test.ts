import { AsyncStorageEntitlementsStore } from '../EntitlementsStore';
import type { Feature } from '../PremiumLockedError';

describe('AsyncStorageEntitlementsStore', () => {
  let mockStorage: {
    getItem: jest.Mock;
    setItem: jest.Mock;
    removeItem: jest.Mock;
  };
  let store: AsyncStorageEntitlementsStore;

  beforeEach(() => {
    mockStorage = {
      getItem: jest.fn(),
      setItem: jest.fn(),
      removeItem: jest.fn(),
    };
    store = new AsyncStorageEntitlementsStore(mockStorage);
  });

  describe('get', () => {
    it('returns null when no data stored', async () => {
      mockStorage.getItem.mockResolvedValue(null);

      const result = await store.get();

      expect(result).toBeNull();
      expect(mockStorage.getItem).toHaveBeenCalledWith('entitlements_v1');
    });

    it('returns parsed data when valid JSON stored', async () => {
      const stored = {
        features: ['solar_forecast', 'road_passability'] as Feature[],
        expireAt: 1234567890,
      };
      mockStorage.getItem.mockResolvedValue(JSON.stringify(stored));

      const result = await store.get();

      expect(result).toEqual(stored);
    });

    it('returns data without expireAt when not set', async () => {
      const stored = {
        features: ['battery_forecast'] as Feature[],
      };
      mockStorage.getItem.mockResolvedValue(JSON.stringify(stored));

      const result = await store.get();

      expect(result).toEqual({
        features: ['battery_forecast'],
        expireAt: undefined,
      });
    });

    it('returns null on invalid JSON', async () => {
      mockStorage.getItem.mockResolvedValue('invalid json{');

      const result = await store.get();

      expect(result).toBeNull();
    });

    it('returns null when features is not an array', async () => {
      mockStorage.getItem.mockResolvedValue(JSON.stringify({
        features: 'not_an_array',
      }));

      const result = await store.get();

      expect(result).toBeNull();
    });

    it('returns null on storage error', async () => {
      mockStorage.getItem.mockRejectedValue(new Error('Storage error'));

      const result = await store.get();

      expect(result).toBeNull();
    });

    it('does not throw on storage error', async () => {
      mockStorage.getItem.mockRejectedValue(new Error('Storage error'));

      await expect(store.get()).resolves.toBeNull();
    });
  });

  describe('set', () => {
    it('serializes and stores data', async () => {
      const data = {
        features: ['solar_forecast', 'propane_forecast'] as Feature[],
        expireAt: 9999999999,
      };

      await store.set(data);

      expect(mockStorage.setItem).toHaveBeenCalledWith(
        'entitlements_v1',
        JSON.stringify(data)
      );
    });

    it('stores data without expireAt', async () => {
      const data = {
        features: ['water_plan'] as Feature[],
      };

      await store.set(data);

      expect(mockStorage.setItem).toHaveBeenCalledWith(
        'entitlements_v1',
        JSON.stringify(data)
      );
    });

    it('does not throw on storage error', async () => {
      mockStorage.setItem.mockRejectedValue(new Error('Storage full'));

      await expect(store.set({
        features: ['solar_forecast'],
      })).resolves.toBeUndefined();
    });
  });

  describe('clear', () => {
    it('removes stored data', async () => {
      await store.clear();

      expect(mockStorage.removeItem).toHaveBeenCalledWith('entitlements_v1');
    });

    it('does not throw on storage error', async () => {
      mockStorage.removeItem.mockRejectedValue(new Error('Storage error'));

      await expect(store.clear()).resolves.toBeUndefined();
    });
  });

  describe('integration', () => {
    it('round-trips data through storage', async () => {
      const data = {
        features: ['solar_forecast', 'road_passability', 'camp_index'] as Feature[],
        expireAt: 1234567890,
      };

      // Simulate storage
      let stored: string | null = null;
      mockStorage.setItem.mockImplementation(async (key, value) => {
        stored = value;
      });
      mockStorage.getItem.mockImplementation(async () => stored);

      await store.set(data);
      const retrieved = await store.get();

      expect(retrieved).toEqual(data);
    });
  });
});
