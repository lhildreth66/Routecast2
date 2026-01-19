import { requirePro } from '../guard';
import { entitlementsCache } from '../entitlements';
import type { CachedEntitlement } from '../types';

describe('requirePro guard', () => {
  beforeEach(async () => {
    await entitlementsCache.clear();
  });

  it('returns locked when no subscription', async () => {
    const result = await requirePro();
    expect(result.allowed).toBe(false);
    expect(result.reason).toBe('no_subscription');
  });

  it('allows when entitlement is valid', async () => {
    const cached: CachedEntitlement = {
      isPro: true,
      productId: 'boondocking_pro_yearly',
      expireAt: new Date(Date.now() + 60_000).toISOString(),
      lastVerifiedAt: new Date().toISOString(),
    };
    await entitlementsCache.save(cached);

    const result = await requirePro();
    expect(result.allowed).toBe(true);
    expect(result.entitlement?.productId).toBe('boondocking_pro_yearly');
  });
});
