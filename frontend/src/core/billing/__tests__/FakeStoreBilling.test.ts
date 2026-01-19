import { FakeStoreBilling } from '../FakeStoreBilling';

describe('FakeStoreBilling', () => {
  let billing: FakeStoreBilling;

  beforeEach(() => {
    billing = new FakeStoreBilling();
  });

  describe('init', () => {
    it('initializes successfully by default', async () => {
      await expect(billing.init()).resolves.not.toThrow();
    });

    it('fails when configured to fail', async () => {
      billing.setInitFailure(true);

      await expect(billing.init()).rejects.toThrow('Fake init failure');
    });
  });

  describe('getProducts', () => {
    it('returns fake product IDs', async () => {
      const products = await billing.getProducts();

      expect(products).toEqual({
        monthlyId: 'fake_monthly',
        yearlyId: 'fake_yearly',
      });
    });
  });

  describe('purchase', () => {
    beforeEach(async () => {
      await billing.init();
    });

    it('succeeds by default', async () => {
      const result = await billing.purchase('monthly');

      expect(result.ok).toBe(true);
      if (result.ok) {
        expect(result.plan).toBe('monthly');
        expect(result.transactionId).toBeDefined();
      }
    });

    it('returns not_ready when not initialized', async () => {
      const uninitializedBilling = new FakeStoreBilling();

      const result = await uninitializedBilling.purchase('monthly');

      expect(result).toEqual({
        ok: false,
        code: 'not_ready',
        message: 'Not initialized',
      });
    });

    it('returns cancelled when configured', async () => {
      billing.setPurchaseCancellation(true);

      const result = await billing.purchase('yearly');

      expect(result).toEqual({
        ok: false,
        code: 'cancelled',
      });
    });

    it('returns failed when configured', async () => {
      billing.setPurchaseFailure(true);

      const result = await billing.purchase('monthly');

      expect(result).toEqual({
        ok: false,
        code: 'failed',
        message: 'Fake purchase failure',
      });
    });

    it('updates active subscription on success', async () => {
      billing.setActiveSubscription(false);

      const result = await billing.purchase('yearly');

      expect(result.ok).toBe(true);
      expect(await billing.restore()).toBe(true);
    });
  });

  describe('restore', () => {
    beforeEach(async () => {
      await billing.init();
    });

    it('returns false by default', async () => {
      const result = await billing.restore();

      expect(result).toBe(false);
    });

    it('returns true when active subscription configured', async () => {
      billing.setActiveSubscription(true);

      const result = await billing.restore();

      expect(result).toBe(true);
    });

    it('returns false when not initialized', async () => {
      const uninitializedBilling = new FakeStoreBilling();

      const result = await uninitializedBilling.restore();

      expect(result).toBe(false);
    });
  });

  describe('shutdown', () => {
    it('shuts down successfully', async () => {
      await billing.init();

      await expect(billing.shutdown()).resolves.not.toThrow();
    });

    it('can be called without init', async () => {
      await expect(billing.shutdown()).resolves.not.toThrow();
    });
  });
});
