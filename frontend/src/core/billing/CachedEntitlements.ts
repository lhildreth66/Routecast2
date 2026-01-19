/**
 * Cached Entitlements — Runtime Entitlements with Persistence
 *
 * In-memory entitlements cache backed by persistent storage.
 * Handles expiration, hydration, and persistence.
 */

import type { Entitlements } from './Entitlements';
import type { EntitlementsStore } from './EntitlementsStore';
import type { Feature } from './PremiumLockedError';

/**
 * Cached entitlements implementation with persistence.
 *
 * Maintains in-memory cache of entitlements backed by persistent storage.
 * Respects expiration timestamps.
 */
export class CachedEntitlements implements Entitlements {
  private features: Set<Feature> = new Set();
  private expireAt: number | undefined;

  constructor(
    private readonly store: EntitlementsStore,
    private readonly now: () => number = () => Date.now()
  ) {}

  /**
   * Load entitlements from persistent storage into memory.
   * Must be called before using has().
   */
  async hydrate(): Promise<void> {
    try {
      const data = await this.store.get();
      
      if (!data) {
        this.features.clear();
        this.expireAt = undefined;
        return;
      }

      // Check if expired
      if (data.expireAt && data.expireAt < this.now()) {
        // Expired - clear everything
        this.features.clear();
        this.expireAt = undefined;
        await this.store.clear();
        return;
      }

      // Load valid data
      this.features = new Set(data.features);
      this.expireAt = data.expireAt;
    } catch (error) {
      // On error, start with empty state
      this.features.clear();
      this.expireAt = undefined;
    }
  }

  /**
   * Check if user has a specific feature entitlement.
   * Returns false if entitlements are expired.
   */
  has(feature: Feature): boolean {
    // Check expiration
    if (this.expireAt && this.expireAt < this.now()) {
      return false;
    }

    return this.features.has(feature);
  }

  /**
   * Grant entitlements to user.
   * Updates in-memory cache and persists to storage.
   *
   * @param features Array of features to grant
   * @param expireAt Optional expiration timestamp (ms since epoch)
   */
  async grant(features: Feature[], expireAt?: number): Promise<void> {
    try {
      // Update in-memory cache
      features.forEach((f) => this.features.add(f));
      this.expireAt = expireAt;

      // Persist to storage
      await this.store.set({
        features: Array.from(this.features),
        expireAt,
      });
    } catch (error) {
      // Persistence errors should not crash - in-memory state is updated
    }
  }

  /**
   * Revoke all entitlements.
   * Clears in-memory cache and persistent storage.
   */
  async revokeAll(): Promise<void> {
    try {
      this.features.clear();
      this.expireAt = undefined;
      await this.store.clear();
    } catch (error) {
      // Always clear in-memory state even if persistence fails
      this.features.clear();
      this.expireAt = undefined;
    }
  }

  /**
   * Get all currently granted features.
   * Returns empty array if expired.
   *
   * @returns Array of granted features
   */
  getGranted(): Feature[] {
    // Check expiration
    if (this.expireAt && this.expireAt < this.now()) {
      return [];
    }

    return Array.from(this.features);
  }
}
