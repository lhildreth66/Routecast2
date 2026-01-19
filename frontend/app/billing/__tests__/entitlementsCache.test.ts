import { entitlementsCache } from '../entitlements';
import type { CachedEntitlement } from '../types';

const futureDate = () => new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString();
const pastDate = () => new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString();

describe('EntitlementsCache', () => {
  beforeEach(async () => {
    await entitlementsCache.clear();
  });

  it('stores and loads deterministically', async () => {
    const cached: CachedEntitlement = {
      isPro: true,
      productId: 'boondocking_pro_yearly',
      expireAt: futureDate(),
      lastVerifiedAt: new Date().toISOString(),
    };

    await entitlementsCache.save(cached);

    const loaded = await entitlementsCache.load();
    expect(loaded).toEqual(cached);

    const entitlement = entitlementsCache.toEntitlement(loaded!);
    expect(entitlement.isPro).toBe(true);
    expect(entitlement.productId).toBe('boondocking_pro_yearly');
    expect(entitlement.source).toBe('cache');
  });

  it('expires based on expireAt', async () => {
    const cached: CachedEntitlement = {
      isPro: true,
      productId: 'boondocking_pro_monthly',
      expireAt: pastDate(),
      lastVerifiedAt: new Date().toISOString(),
    };

    await entitlementsCache.save(cached);

    const loaded = await entitlementsCache.load();
    expect(entitlementsCache.isValid(loaded)).toBe(false);
  });
});
