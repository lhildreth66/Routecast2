/**
 * Store Billing Interface — Pure TypeScript
 *
 * Abstract interface for app store subscription management.
 * Implemented by platform-specific adapters (Google Play, App Store).
 */

export type SubscriptionPlan = 'monthly' | 'yearly';

export type PurchaseResult =
  | { ok: true; plan: SubscriptionPlan; transactionId?: string }
  | { ok: false; code: 'cancelled' | 'failed' | 'not_ready'; message?: string };

/**
 * Store Billing Interface
 *
 * Abstracts app store subscription operations.
 * Implementations must be safe/no-throw where possible.
 */
export interface StoreBilling {
  /**
   * Initialize connection to app store.
   * Must be called before other operations.
   */
  init(): Promise<void>;

  /**
   * Get product IDs for subscriptions.
   * @returns Product IDs for monthly and yearly plans
   */
  getProducts(): Promise<{ monthlyId: string; yearlyId: string }>;

  /**
   * Trigger subscription purchase flow.
   *
   * @param plan Which subscription plan to purchase
   * @returns Purchase result (success or failure with reason)
   */
  purchase(plan: SubscriptionPlan): Promise<PurchaseResult>;

  /**
   * Restore existing purchases.
   *
   * Checks if user has active subscription from previous purchase.
   * @returns True if active subscription found, false otherwise
   */
  restore(): Promise<boolean>;

  /**
   * Shutdown/cleanup store connection.
   * Should be called when app closes or billing no longer needed.
   */
  shutdown(): Promise<void>;
}
