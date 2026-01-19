/**
 * useEntitlements Hook
 * 
 * Background verifier and entitlement state management.
 * Runs verification on:
 * - App start
 * - App returns to foreground
 * - After successful purchase
 * - Periodic timer (every 12 hours)
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { AppState, AppStateStatus } from 'react-native';
import type { Purchase, PurchaseError } from 'react-native-iap';
import { iapClient } from './iapClient';
import { entitlementsCache } from './entitlements';
import type { Entitlement, ProductId } from './types';

const VERIFY_INTERVAL_MS = 12 * 60 * 60 * 1000; // 12 hours

export async function performVerification(): Promise<Entitlement> {
  // Try to get active purchase from Play Store
  const activePurchase = await iapClient.getActivePurchase();

  if (activePurchase) {
    // Update cache with fresh purchase data
    const productId = activePurchase.productId as ProductId;
    const purchaseDate = activePurchase.transactionDate || Date.now();
    
    await entitlementsCache.updateFromPurchase(productId, purchaseDate);
    
    const cached = await entitlementsCache.load();
    if (cached) {
      return {
        isPro: true,
        productId: cached.productId,
        expireAt: cached.expireAt,
        source: 'play',
      };
    }
  }

  // Fallback to cache
  const cached = await entitlementsCache.load();
  if (cached && entitlementsCache.isValid(cached)) {
    return entitlementsCache.toEntitlement(cached);
  }

  return entitlementsCache.createLocked();
}

export function useEntitlements() {
  const [entitlement, setEntitlement] = useState<Entitlement | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  const verifyTimerRef = useRef<NodeJS.Timeout | null>(null);
  const lastVerifyTimeRef = useRef<number>(0);

  /**
   * Verify entitlement from Play Store.
   * Updates cache and state.
   */
  const verify = useCallback(async (force = false) => {
    // Prevent duplicate verifications within 30 seconds
    const now = Date.now();
    if (!force && now - lastVerifyTimeRef.current < 30000) {
      console.log('[useEntitlements] Skipping verification (too soon)');
      return;
    }
    lastVerifyTimeRef.current = now;

    try {
      console.log('[useEntitlements] Verifying entitlement...');
      setIsLoading(true);
      setError(null);

      const ent = await performVerification();
      setEntitlement(ent);

      // Update verification timestamp
      await entitlementsCache.updateVerificationTime();
    } catch (err) {
      console.error('[useEntitlements] Verification failed:', err);
      setError(err instanceof Error ? err.message : 'Verification failed');
      
      // Fall back to cache on error
      const cached = await entitlementsCache.load();
      if (cached && entitlementsCache.isValid(cached)) {
        const ent = entitlementsCache.toEntitlement(cached);
        setEntitlement(ent);
      } else {
        const locked = entitlementsCache.createLocked();
        setEntitlement(locked);
      }
    } finally {
      setIsLoading(false);
    }
  }, []);

  /**
   * Handle purchase update from IAP listener.
   */
  const handlePurchaseUpdate = useCallback(async (purchase: Purchase) => {
    try {
      console.log('[useEntitlements] Processing purchase update:', purchase.productId);
      
      // Finalize the purchase
      await iapClient.finalizePurchase(purchase);
      
      // Update entitlement
      await verify(true);
    } catch (err) {
      console.error('[useEntitlements] Failed to process purchase:', err);
      setError(err instanceof Error ? err.message : 'Purchase processing failed');
    }
  }, [verify]);

  /**
   * Handle purchase error from IAP listener.
   */
  const handlePurchaseError = useCallback((err: PurchaseError) => {
    console.error('[useEntitlements] Purchase error:', err);
    setError(err.message || 'Purchase failed');
  }, []);

  /**
   * Initialize IAP and set up listeners.
   */
  useEffect(() => {
    let mounted = true;

    const init = async () => {
      try {
        await iapClient.initialize();
        iapClient.setupListeners(handlePurchaseUpdate, handlePurchaseError);
        
        if (mounted) {
          // Initial verification on mount
          await verify();
        }
      } catch (err) {
        console.error('[useEntitlements] Initialization failed:', err);
        if (mounted) {
          setError(err instanceof Error ? err.message : 'Initialization failed');
          setIsLoading(false);
        }
      }
    };

    init();

    return () => {
      mounted = false;
      iapClient.disconnect();
    };
  }, [verify, handlePurchaseUpdate, handlePurchaseError]);

  /**
   * Set up periodic verification timer.
   */
  useEffect(() => {
    verifyTimerRef.current = setInterval(() => {
      console.log('[useEntitlements] Periodic verification triggered');
      verify();
    }, VERIFY_INTERVAL_MS);

    return () => {
      if (verifyTimerRef.current) {
        clearInterval(verifyTimerRef.current);
      }
    };
  }, [verify]);

  /**
   * Listen for app state changes (foreground/background).
   */
  useEffect(() => {
    const subscription = AppState.addEventListener('change', (nextAppState: AppStateStatus) => {
      if (nextAppState === 'active') {
        console.log('[useEntitlements] App foregrounded, verifying...');
        verify();
      }
    });

    return () => {
      subscription.remove();
    };
  }, [verify]);

  /**
   * Refresh entitlement manually (for pull-to-refresh, etc.)
   */
  const refresh = useCallback(() => {
    return verify(true);
  }, [verify]);

  return {
    entitlement,
    isLoading,
    error,
    refresh,
  };
}
