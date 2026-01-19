/**
 * Entitlements Persistence — Storage Interface
 *
 * Defines contract for persisting user entitlements.
 * Implementation-agnostic (can use AsyncStorage, SQLite, etc.)
 */

import type { Feature } from './PremiumLockedError';

/**
 * Persisted entitlements data structure
 */
export interface PersistedEntitlements {
  /** Array of granted premium features */
  features: Feature[];
  
  /** Optional expiration timestamp (milliseconds since epoch) */
  expireAt?: number;
}

/**
 * Storage interface for entitlements persistence
 */
export interface EntitlementsStore {
  /**
   * Retrieve persisted entitlements.
   * Returns null if not found or on error.
   * Must never throw.
   */
  get(): Promise<PersistedEntitlements | null>;

  /**
   * Persist entitlements data.
   * Must never throw.
   */
  set(data: PersistedEntitlements): Promise<void>;

  /**
   * Clear all persisted entitlements.
   * Must never throw.
   */
  clear(): Promise<void>;
}

/**
 * AsyncStorage-based implementation of EntitlementsStore
 *
 * Uses React Native's AsyncStorage for persistence.
 * Safe implementation that never throws.
 */
export class AsyncStorageEntitlementsStore implements EntitlementsStore {
  private readonly STORAGE_KEY = 'entitlements_v1';

  constructor(private readonly storage: {
    getItem(key: string): Promise<string | null>;
    setItem(key: string, value: string): Promise<void>;
    removeItem(key: string): Promise<void>;
  }) {}

  async get(): Promise<PersistedEntitlements | null> {
    try {
      const raw = await this.storage.getItem(this.STORAGE_KEY);
      if (!raw) {
        return null;
      }

      const parsed = JSON.parse(raw);
      
      // Validate structure
      if (!parsed || !Array.isArray(parsed.features)) {
        return null;
      }

      return {
        features: parsed.features,
        expireAt: parsed.expireAt,
      };
    } catch (error) {
      // Silently fail - return null on any error
      return null;
    }
  }

  async set(data: PersistedEntitlements): Promise<void> {
    try {
      const serialized = JSON.stringify(data);
      await this.storage.setItem(this.STORAGE_KEY, serialized);
    } catch (error) {
      // Silently fail - persistence errors should not crash app
    }
  }

  async clear(): Promise<void> {
    try {
      await this.storage.removeItem(this.STORAGE_KEY);
    } catch (error) {
      // Silently fail
    }
  }
}
