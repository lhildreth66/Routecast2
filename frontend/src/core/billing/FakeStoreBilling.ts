/**
 * Fake Store Billing — Test Double
 *
 * In-memory implementation of StoreBilling for testing.
 * Allows simulating various purchase scenarios without real store.
 */

import type { StoreBilling, SubscriptionPlan, PurchaseResult } from './StoreBilling';

/**
 * Fake Store Billing Implementation
 *
 * Useful for:
 * - Unit tests
 * - Integration tests
 * - UI development without real store
 * - Simulating error conditions
 */
export class FakeStoreBilling implements StoreBilling {
  private initialized = false;
  private hasActiveSubscription = false;
  private shouldFailInit = false;
  private shouldFailPurchase = false;
  private shouldCancelPurchase = false;

  /**
   * Configure whether init should fail.
   */
  setInitFailure(shouldFail: boolean): void {
    this.shouldFailInit = shouldFail;
  }

  /**
   * Configure whether purchases should fail.
   */
  setPurchaseFailure(shouldFail: boolean): void {
    this.shouldFailPurchase = shouldFail;
  }

  /**
   * Configure whether purchases should be cancelled.
   */
  setPurchaseCancellation(shouldCancel: boolean): void {
    this.shouldCancelPurchase = shouldCancel;
  }

  /**
   * Set active subscription state (for restore testing).
   */
  setActiveSubscription(active: boolean): void {
    this.hasActiveSubscription = active;
  }

  async init(): Promise<void> {
    if (this.shouldFailInit) {
      throw new Error('Fake init failure');
    }
    this.initialized = true;
  }

  async getProducts(): Promise<{ monthlyId: string; yearlyId: string }> {
    return {
      monthlyId: 'fake_monthly',
      yearlyId: 'fake_yearly',
    };
  }

  async purchase(plan: SubscriptionPlan): Promise<PurchaseResult> {
    if (!this.initialized) {
      return {
        ok: false,
        code: 'not_ready',
        message: 'Not initialized',
      };
    }

    if (this.shouldCancelPurchase) {
      return {
        ok: false,
        code: 'cancelled',
      };
    }

    if (this.shouldFailPurchase) {
      return {
        ok: false,
        code: 'failed',
        message: 'Fake purchase failure',
      };
    }

    // Success - update active subscription state
    this.hasActiveSubscription = true;

    return {
      ok: true,
      plan,
      transactionId: `fake_txn_${Date.now()}`,
    };
  }

  async restore(): Promise<boolean> {
    if (!this.initialized) {
      return false;
    }
    return this.hasActiveSubscription;
  }

  async shutdown(): Promise<void> {
    this.initialized = false;
  }
}
