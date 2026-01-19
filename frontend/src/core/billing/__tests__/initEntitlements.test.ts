import { initEntitlements } from '../initEntitlements';
import { CachedEntitlements } from '../CachedEntitlements';
import type { EntitlementsStore } from '../EntitlementsStore';

describe('initEntitlements', () => {
  let mockStore: jest.Mocked<EntitlementsStore>;

  beforeEach(() => {
    mockStore = {
      get: jest.fn().mockResolvedValue(null),
      set: jest.fn().mockResolvedValue(undefined),
      clear: jest.fn().mockResolvedValue(undefined),
    };
  });

  it('calls hydrate on entitlements instance', async () => {
    const entitlements = new CachedEntitlements(mockStore);
    const hydrateSpy = jest.spyOn(entitlements, 'hydrate');

    await initEntitlements(entitlements);

    expect(hydrateSpy).toHaveBeenCalledTimes(1);
  });

  it('loads persisted entitlements', async () => {
    mockStore.get.mockResolvedValue({
      features: ['solar_forecast', 'battery_forecast'],
      expireAt: Date.now() + 100000,
    });

    const entitlements = new CachedEntitlements(mockStore);
    await initEntitlements(entitlements);

    expect(entitlements.has('solar_forecast')).toBe(true);
    expect(entitlements.has('battery_forecast')).toBe(true);
  });

  it('handles store errors gracefully', async () => {
    mockStore.get.mockRejectedValue(new Error('Storage error'));

    const entitlements = new CachedEntitlements(mockStore);

    await expect(initEntitlements(entitlements)).resolves.toBeUndefined();

    // Should start with empty entitlements
    expect(entitlements.has('solar_forecast')).toBe(false);
  });
});
