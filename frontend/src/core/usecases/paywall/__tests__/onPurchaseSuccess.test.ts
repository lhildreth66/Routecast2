import { onPurchaseSuccess } from '../onPurchaseSuccess';
import { trackPurchaseSuccess } from '../../../analytics/paywall';
import { CachedEntitlements } from '../../../billing/CachedEntitlements';
import type { EntitlementsStore } from '../../../billing/EntitlementsStore';

// Mock paywall analytics
jest.mock('../../../analytics/paywall');
const mockTrackPurchaseSuccess = trackPurchaseSuccess as jest.MockedFunction<typeof trackPurchaseSuccess>;

describe('onPurchaseSuccess', () => {
  let mockStore: jest.Mocked<EntitlementsStore>;
  let entitlements: CachedEntitlements;
  let currentTime: number;
  let mockNow: jest.Mock;

  beforeEach(() => {
    mockTrackPurchaseSuccess.mockClear();

    currentTime = 1000000000; // Fixed timestamp
    mockNow = jest.fn(() => currentTime);

    mockStore = {
      get: jest.fn().mockResolvedValue(null),
      set: jest.fn().mockResolvedValue(undefined),
      clear: jest.fn().mockResolvedValue(undefined),
    };

    entitlements = new CachedEntitlements(mockStore, mockNow);
  });

  it('calls trackPurchaseSuccess with feature, plan, and source', async () => {
    await entitlements.hydrate();
    await onPurchaseSuccess(entitlements, 'solar_forecast', 'yearly', 'paywall', mockNow);

    expect(mockTrackPurchaseSuccess).toHaveBeenCalledTimes(1);
    expect(mockTrackPurchaseSuccess).toHaveBeenCalledWith({
      feature: 'solar_forecast',
      plan: 'yearly',
      source: 'paywall',
    });
  });

  it('handles undefined source', async () => {
    await entitlements.hydrate();
    await onPurchaseSuccess(entitlements, 'road_passability', 'monthly', undefined, mockNow);

    expect(mockTrackPurchaseSuccess).toHaveBeenCalledWith({
      feature: 'road_passability',
      plan: 'monthly',
      source: undefined,
    });
  });

  it('does not throw when trackPurchaseSuccess throws', async () => {
    mockTrackPurchaseSuccess.mockImplementationOnce(() => {
      throw new Error('Analytics failure');
    });

    await entitlements.hydrate();

    await expect(
      onPurchaseSuccess(entitlements, 'battery_forecast', 'yearly', 'settings', mockNow)
    ).resolves.toBeUndefined();
  });

  it('grants all premium features', async () => {
    await entitlements.hydrate();
    await onPurchaseSuccess(entitlements, 'solar_forecast', 'yearly', undefined, mockNow);

    // Check all 8 features are granted
    expect(entitlements.has('solar_forecast')).toBe(true);
    expect(entitlements.has('road_passability')).toBe(true);
    expect(entitlements.has('propane_forecast')).toBe(true);
    expect(entitlements.has('battery_forecast')).toBe(true);
    expect(entitlements.has('water_plan')).toBe(true);
    expect(entitlements.has('cell_starlink')).toBe(true);
    expect(entitlements.has('camp_index')).toBe(true);
    expect(entitlements.has('claim_log')).toBe(true);
  });

  it('sets expireAt to 32 days for monthly plan', async () => {
    await entitlements.hydrate();
    await onPurchaseSuccess(entitlements, 'solar_forecast', 'monthly', undefined, mockNow);

    const MS_PER_DAY = 24 * 60 * 60 * 1000;
    const expectedExpireAt = currentTime + (32 * MS_PER_DAY);

    expect(mockStore.set).toHaveBeenCalledWith({
      features: expect.any(Array),
      expireAt: expectedExpireAt,
    });
  });

  it('sets expireAt to 370 days for yearly plan', async () => {
    await entitlements.hydrate();
    await onPurchaseSuccess(entitlements, 'solar_forecast', 'yearly', undefined, mockNow);

    const MS_PER_DAY = 24 * 60 * 60 * 1000;
    const expectedExpireAt = currentTime + (370 * MS_PER_DAY);

    expect(mockStore.set).toHaveBeenCalledWith({
      features: expect.any(Array),
      expireAt: expectedExpireAt,
    });
  });

  it('persists entitlements to store', async () => {
    await entitlements.hydrate();
    await onPurchaseSuccess(entitlements, 'battery_forecast', 'monthly', undefined, mockNow);

    expect(mockStore.set).toHaveBeenCalledWith({
      features: expect.arrayContaining([
        'solar_forecast',
        'road_passability',
        'propane_forecast',
        'battery_forecast',
        'water_plan',
        'cell_starlink',
        'camp_index',
        'claim_log',
      ]),
      expireAt: expect.any(Number),
    });
  });

  it('works with all feature types', async () => {
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

    for (const feature of features) {
      mockTrackPurchaseSuccess.mockClear();
      await entitlements.hydrate();
      await onPurchaseSuccess(entitlements, feature, 'monthly', 'test', mockNow);

      expect(mockTrackPurchaseSuccess).toHaveBeenCalledWith({
        feature,
        plan: 'monthly',
        source: 'test',
      });
    }
  });

  it('handles store errors gracefully', async () => {
    mockStore.set.mockRejectedValue(new Error('Storage full'));

    await entitlements.hydrate();

    await expect(
      onPurchaseSuccess(entitlements, 'solar_forecast', 'yearly', undefined, mockNow)
    ).resolves.toBeUndefined();

    // Should still track analytics
    expect(mockTrackPurchaseSuccess).toHaveBeenCalled();
  });
});
