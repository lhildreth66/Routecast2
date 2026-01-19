/**
 * Tests for Premium Gate Frontend
 * 
 * Tests premiumGate wrapper, API call wrapper, and error handling.
 */

import { jest } from '@jest/globals';
import {
  premiumGate,
  premiumApiCall,
  isPremiumLockedResponse,
  getLockedFeature,
  setPaywallTrigger,
  PremiumLockedError,
} from '../billing/premiumGate';
import { entitlementsCache } from '../billing/entitlements';
import type { CachedEntitlement } from '../billing/types';
import { SOLAR_FORECAST, PROPANE_USAGE, ROAD_SIM } from '../billing/features';

// Mock the entitlements cache
jest.mock('../billing/entitlements', () => ({
  entitlementsCache: {
    load: jest.fn(),
    isValid: jest.fn(),
  },
}));

describe('isPremiumLockedResponse', () => {
  it('returns true for premium_locked error', () => {
    expect(isPremiumLockedResponse({ error: 'premium_locked' })).toBe(true);
  });

  it('returns true for detail.error premium_locked', () => {
    expect(isPremiumLockedResponse({ detail: { error: 'premium_locked' } })).toBe(true);
  });

  it('returns false for other errors', () => {
    expect(isPremiumLockedResponse({ error: 'server_error' })).toBe(false);
    expect(isPremiumLockedResponse({ detail: { error: 'not_found' } })).toBe(false);
  });

  it('returns false for null/undefined', () => {
    expect(isPremiumLockedResponse(null)).toBe(false);
    expect(isPremiumLockedResponse(undefined)).toBe(false);
  });
});

describe('getLockedFeature', () => {
  it('extracts feature from response', () => {
    expect(getLockedFeature({ feature: SOLAR_FORECAST })).toBe(SOLAR_FORECAST);
  });

  it('extracts feature from detail', () => {
    expect(getLockedFeature({ detail: { feature: PROPANE_USAGE } })).toBe(PROPANE_USAGE);
  });

  it('returns null if no feature', () => {
    expect(getLockedFeature({ error: 'premium_locked' })).toBe(null);
    expect(getLockedFeature({})).toBe(null);
  });
});

describe('premiumGate', () => {
  let paywallTriggerMock: jest.Mock;

  beforeEach(() => {
    jest.clearAllMocks();
    paywallTriggerMock = jest.fn();
    setPaywallTrigger(paywallTriggerMock);
  });

  it('throws and triggers paywall when no entitlement cached', async () => {
    (entitlementsCache.load as jest.Mock).mockResolvedValue(null);

    const fn = jest.fn(() => Promise.resolve('result'));

    await expect(premiumGate(SOLAR_FORECAST, fn)).rejects.toThrow(PremiumLockedError);
    expect(paywallTriggerMock).toHaveBeenCalledWith(SOLAR_FORECAST);
    expect(fn).not.toHaveBeenCalled();
  });

  it('throws and triggers paywall when entitlement invalid', async () => {
    const invalidEntitlement: CachedEntitlement = {
      isPro: false,
    };

    (entitlementsCache.load as jest.Mock).mockResolvedValue(invalidEntitlement);
    (entitlementsCache.isValid as jest.Mock).mockReturnValue(false);

    const fn = jest.fn(() => Promise.resolve('result'));

    await expect(premiumGate(PROPANE_USAGE, fn)).rejects.toThrow(PremiumLockedError);
    expect(paywallTriggerMock).toHaveBeenCalledWith(PROPANE_USAGE);
    expect(fn).not.toHaveBeenCalled();
  });

  it('executes function when entitlement valid', async () => {
    const validEntitlement: CachedEntitlement = {
      isPro: true,
      productId: 'boondocking_pro_yearly',
      expireAt: new Date(Date.now() + 365 * 24 * 60 * 60 * 1000).toISOString(),
      lastVerifiedAt: new Date().toISOString(),
    };

    (entitlementsCache.load as jest.Mock).mockResolvedValue(validEntitlement);
    (entitlementsCache.isValid as jest.Mock).mockReturnValue(true);

    const fn = jest.fn(() => Promise.resolve('success'));

    const result = await premiumGate(SOLAR_FORECAST, fn);

    expect(result).toBe('success');
    expect(fn).toHaveBeenCalled();
    expect(paywallTriggerMock).not.toHaveBeenCalled();
  });

  it('works with sync functions', async () => {
    const validEntitlement: CachedEntitlement = {
      isPro: true,
      productId: 'boondocking_pro_monthly',
      expireAt: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString(),
    };

    (entitlementsCache.load as jest.Mock).mockResolvedValue(validEntitlement);
    (entitlementsCache.isValid as jest.Mock).mockReturnValue(true);

    const fn = jest.fn(() => 42);

    const result = await premiumGate(ROAD_SIM, fn);

    expect(result).toBe(42);
    expect(fn).toHaveBeenCalled();
  });
});

describe('premiumApiCall', () => {
  let paywallTriggerMock: jest.Mock;

  beforeEach(() => {
    jest.clearAllMocks();
    paywallTriggerMock = jest.fn();
    setPaywallTrigger(paywallTriggerMock);
  });

  it('throws and triggers paywall on 403 with premium_locked', async () => {
    const mockResponse = {
      status: 403,
      ok: false,
      json: jest.fn(() => Promise.resolve({ error: 'premium_locked', feature: SOLAR_FORECAST })),
    } as unknown as Response;

    const apiFn = jest.fn(() => Promise.resolve(mockResponse));

    await expect(premiumApiCall(SOLAR_FORECAST, apiFn)).rejects.toThrow(PremiumLockedError);
    expect(paywallTriggerMock).toHaveBeenCalledWith(SOLAR_FORECAST);
  });

  it('throws and triggers paywall on 403 with detail.error shape', async () => {
    const mockResponse = {
      status: 403,
      ok: false,
      json: jest.fn(() => Promise.resolve({ detail: { error: 'premium_locked', feature: PROPANE_USAGE } })),
    } as unknown as Response;

    const apiFn = jest.fn(() => Promise.resolve(mockResponse));

    await expect(premiumApiCall(PROPANE_USAGE, apiFn)).rejects.toThrow(PremiumLockedError);
    expect(paywallTriggerMock).toHaveBeenCalledWith(PROPANE_USAGE);
  });

  it('returns data on successful response', async () => {
    const mockData = { forecast: [100, 150, 200] };
    const mockResponse = {
      status: 200,
      ok: true,
      json: jest.fn(() => Promise.resolve(mockData)),
    } as unknown as Response;

    const apiFn = jest.fn(() => Promise.resolve(mockResponse));

    const result = await premiumApiCall(SOLAR_FORECAST, apiFn);

    expect(result).toEqual(mockData);
    expect(paywallTriggerMock).not.toHaveBeenCalled();
  });

  it('handles premium_locked in successful response body', async () => {
    const mockResponse = {
      status: 200,
      ok: true,
      json: jest.fn(() => Promise.resolve({ error: 'premium_locked', feature: ROAD_SIM })),
    } as unknown as Response;

    const apiFn = jest.fn(() => Promise.resolve(mockResponse));

    await expect(premiumApiCall(ROAD_SIM, apiFn)).rejects.toThrow(PremiumLockedError);
    expect(paywallTriggerMock).toHaveBeenCalledWith(ROAD_SIM);
  });

  it('throws generic error on non-403 failures', async () => {
    const mockResponse = {
      status: 500,
      ok: false,
    } as Response;

    const apiFn = jest.fn(() => Promise.resolve(mockResponse));

    await expect(premiumApiCall(SOLAR_FORECAST, apiFn)).rejects.toThrow('API call failed: 500');
  });
});

describe('PremiumLockedError', () => {
  it('has correct name and message', () => {
    const error = new PremiumLockedError(SOLAR_FORECAST);
    
    expect(error.name).toBe('PremiumLockedError');
    expect(error.message).toContain('solar_forecast');
    expect(error.feature).toBe(SOLAR_FORECAST);
  });

  it('stores feature property', () => {
    const features = [SOLAR_FORECAST, PROPANE_USAGE, ROAD_SIM];
    
    for (const feature of features) {
      const error = new PremiumLockedError(feature);
      expect(error.feature).toBe(feature);
    }
  });
});
