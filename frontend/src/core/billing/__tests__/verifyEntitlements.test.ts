import { verifyEntitlements } from '../verifyEntitlements';
import { FakeStoreBilling } from '../FakeStoreBilling';
import { CachedEntitlements } from '../CachedEntitlements';
import type { EntitlementsStore } from '../EntitlementsStore';

// Mock store
class InMemoryStore implements EntitlementsStore {
  private data: any = null;

  async get() {
    return this.data;
  }

  async set(data: any) {
    this.data = data;
  }

  async clear() {
    this.data = null;
  }
}

describe('verifyEntitlements', () => {
  let billing: FakeStoreBilling;
  let store: InMemoryStore;
  let entitlements: CachedEntitlements;
  let now: jest.Mock<number, []>;

  beforeEach(() => {
    billing = new FakeStoreBilling();
    store = new InMemoryStore();
    now = jest.fn(() => 1000000000);
    entitlements = new CachedEntitlements(store, now);
  });

  it('initializes billing', async () => {
    await verifyEntitlements(billing, entitlements, now);

    const products = await billing.getProducts();
    expect(products.monthlyId).toBe('fake_monthly');
  });

  it('grants all features when restore finds active subscription', async () => {
    billing.setActiveSubscription(true);

    await verifyEntitlements(billing, entitlements, now);

    // Should have all 8 features
    expect(entitlements.has('solar_forecast')).toBe(true);
    expect(entitlements.has('road_passability')).toBe(true);
    expect(entitlements.has('propane_forecast')).toBe(true);
    expect(entitlements.has('battery_forecast')).toBe(true);
    expect(entitlements.has('water_plan')).toBe(true);
    expect(entitlements.has('cell_starlink')).toBe(true);
    expect(entitlements.has('camp_index')).toBe(true);
    expect(entitlements.has('claim_log')).toBe(true);
  });

  it('sets expireAt to ~370 days when subscription active', async () => {
    const nowMs = 1000000000;
    now.mockReturnValue(nowMs);
    billing.setActiveSubscription(true);

    await verifyEntitlements(billing, entitlements, now);

    // Verify expireAt persisted
    const data = await store.get();
    expect(data).not.toBeNull();
    expect(data!.expireAt).toBe(nowMs + 370 * 24 * 60 * 60 * 1000);
  });

  it('does not grant features when no active subscription', async () => {
    billing.setActiveSubscription(false);

    await verifyEntitlements(billing, entitlements, now);

    expect(entitlements.has('solar_forecast')).toBe(false);
    expect(entitlements.has('road_passability')).toBe(false);
  });

  it('keeps existing entitlements when no active subscription', async () => {
    // Pre-grant some features
    await entitlements.grant(['solar_forecast'], now() + 100000);
    billing.setActiveSubscription(false);

    await verifyEntitlements(billing, entitlements, now);

    // Should still have pre-granted feature
    expect(entitlements.has('solar_forecast')).toBe(true);
  });

  it('does not throw when billing init fails', async () => {
    billing.setInitFailure(true);

    await expect(
      verifyEntitlements(billing, entitlements, now)
    ).resolves.not.toThrow();

    // Should not have granted anything
    expect(entitlements.has('solar_forecast')).toBe(false);
  });

  it('does not throw when restore fails', async () => {
    // Simulate restore failure by not initializing
    const uninitializedBilling = new FakeStoreBilling();

    await expect(
      verifyEntitlements(uninitializedBilling, entitlements, now)
    ).resolves.not.toThrow();
  });

  it('persists granted entitlements to store', async () => {
    billing.setActiveSubscription(true);

    await verifyEntitlements(billing, entitlements, now);

    // Create new instance and hydrate
    const newEntitlements = new CachedEntitlements(store, now);
    await newEntitlements.hydrate();

    // Should have features from store
    expect(newEntitlements.has('solar_forecast')).toBe(true);
    expect(newEntitlements.has('road_passability')).toBe(true);
  });
});
