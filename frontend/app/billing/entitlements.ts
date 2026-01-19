/**
 * EntitlementsCache
 * 
 * Secure local storage for subscription entitlements.
 * Uses expo-secure-store for encrypted persistence.
 */

import * as SecureStore from 'expo-secure-store';
import type { CachedEntitlement, Entitlement, ProductId } from './types';

const CACHE_KEY = 'routecast_entitlements_v1';

export class EntitlementsCache {
  /**
   * Save entitlement to secure storage.
   */
  async save(entitlement: CachedEntitlement): Promise<void> {
    try {
      const json = JSON.stringify(entitlement);
      await SecureStore.setItemAsync(CACHE_KEY, json);
      console.log('[EntitlementsCache] Saved:', entitlement);
    } catch (error) {
      console.error('[EntitlementsCache] Failed to save:', error);
      throw error;
    }
  }

  /**
   * Load entitlement from secure storage.
   * Returns null if not found or invalid.
   */
  async load(): Promise<CachedEntitlement | null> {
    try {
      const json = await SecureStore.getItemAsync(CACHE_KEY);
      if (!json) {
        console.log('[EntitlementsCache] No cached entitlement found');
        return null;
      }

      const cached: CachedEntitlement = JSON.parse(json);
      console.log('[EntitlementsCache] Loaded:', cached);
      return cached;
    } catch (error) {
      console.error('[EntitlementsCache] Failed to load:', error);
      return null;
    }
  }

  /**
   * Clear cached entitlement.
   */
  async clear(): Promise<void> {
    try {
      await SecureStore.deleteItemAsync(CACHE_KEY);
      console.log('[EntitlementsCache] Cleared');
    } catch (error) {
      console.error('[EntitlementsCache] Failed to clear:', error);
    }
  }

  /**
   * Check if cached entitlement is currently valid.
   * Valid only if isPro === true and expireAt is in the future.
   */
  isValid(cached: CachedEntitlement | null): boolean {
    if (!cached) {
      return false;
    }

    if (!cached.isPro) {
      return false;
    }

    if (!cached.expireAt) {
      // No expiration date means perpetual (shouldn't happen with subscriptions)
      return cached.isPro;
    }

    const now = new Date();
    const expiry = new Date(cached.expireAt);
    const isNotExpired = expiry > now;

    console.log('[EntitlementsCache] Validity check:', {
      isPro: cached.isPro,
      expireAt: cached.expireAt,
      now: now.toISOString(),
      isNotExpired,
    });

    return isNotExpired;
  }

  /**
   * Convert cached entitlement to public Entitlement type.
   */
  toEntitlement(cached: CachedEntitlement): Entitlement {
    const isValid = this.isValid(cached);
    
    return {
      isPro: isValid,
      productId: cached.productId,
      expireAt: cached.expireAt,
      source: 'cache',
    };
  }

  /**
   * Create a locked (no access) entitlement.
   */
  createLocked(): Entitlement {
    return {
      isPro: false,
      source: 'cache',
    };
  }

  /**
   * Update cached entitlement with new purchase data.
   * Calculates expireAt based on product type (monthly/yearly).
   */
  async updateFromPurchase(
    productId: ProductId,
    purchaseDate: number
  ): Promise<void> {
    const purchaseDateObj = new Date(purchaseDate);
    
    // Calculate expiration based on product type
    const expireAt = new Date(purchaseDateObj);
    if (productId === 'boondocking_pro_monthly') {
      expireAt.setMonth(expireAt.getMonth() + 1);
    } else if (productId === 'boondocking_pro_yearly') {
      expireAt.setFullYear(expireAt.getFullYear() + 1);
    }

    const cached: CachedEntitlement = {
      isPro: true,
      productId,
      expireAt: expireAt.toISOString(),
      lastVerifiedAt: new Date().toISOString(),
    };

    await this.save(cached);
  }

  /**
   * Update lastVerifiedAt timestamp.
   * Call after successful verification from Play Store.
   */
  async updateVerificationTime(): Promise<void> {
    const cached = await this.load();
    if (cached) {
      cached.lastVerifiedAt = new Date().toISOString();
      await this.save(cached);
    }
  }
}

// Singleton instance
export const entitlementsCache = new EntitlementsCache();
