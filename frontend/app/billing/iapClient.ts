/**
 * IAP Client
 * 
 * Wrapper for react-native-iap library to handle Google Play Billing.
 * Provides a simplified interface for Routecast subscription purchases.
 */

import {
  initConnection,
  endConnection,
  getSubscriptions,
  requestSubscription,
  purchaseUpdatedListener,
  purchaseErrorListener,
  finishTransaction,
  Purchase,
  Subscription,
  PurchaseError,
} from 'react-native-iap';
import type { ProductId, PurchaseResult } from './types';

const PRODUCT_IDS: ProductId[] = [
  'boondocking_pro_monthly',
  'boondocking_pro_yearly',
];

export class IAPClient {
  private purchaseUpdateSubscription: any = null;
  private purchaseErrorSubscription: any = null;

  /**
   * Initialize connection to Play Store.
   * Must be called before any other IAP operations.
   */
  async initialize(): Promise<void> {
    try {
      await initConnection();
      console.log('[IAP] Connection initialized');
    } catch (error) {
      console.error('[IAP] Failed to initialize:', error);
      throw error;
    }
  }

  /**
   * Disconnect from Play Store.
   * Should be called on app cleanup.
   */
  async disconnect(): Promise<void> {
    try {
      if (this.purchaseUpdateSubscription) {
        this.purchaseUpdateSubscription.remove();
        this.purchaseUpdateSubscription = null;
      }
      if (this.purchaseErrorSubscription) {
        this.purchaseErrorSubscription.remove();
        this.purchaseErrorSubscription = null;
      }
      await endConnection();
      console.log('[IAP] Connection ended');
    } catch (error) {
      console.error('[IAP] Failed to disconnect:', error);
    }
  }

  /**
   * Fetch available subscription products from Play Store.
   * Returns product details including prices.
   */
  async fetchProducts(): Promise<Subscription[]> {
    try {
      const products = await getSubscriptions({ skus: PRODUCT_IDS });
      console.log('[IAP] Fetched products:', products);
      return products;
    } catch (error) {
      console.error('[IAP] Failed to fetch products:', error);
      throw error;
    }
  }

  /**
   * Purchase a subscription by product ID.
   * Returns purchase result.
   */
  async purchase(productId: ProductId): Promise<PurchaseResult> {
    try {
      console.log('[IAP] Purchasing:', productId);
      await requestSubscription({ sku: productId });
      
      // Purchase will complete via purchaseUpdatedListener
      return { success: true, productId };
    } catch (error) {
      console.error('[IAP] Purchase failed:', error);
      const errorMessage = error instanceof Error ? error.message : 'Purchase failed';
      return { success: false, error: errorMessage };
    }
  }

  /**
   * Restore previous purchases.
   * Returns active purchases from Play Store.
   */
  async restorePurchases(): Promise<Purchase[]> {
    try {
      // react-native-iap v12+ uses getAvailablePurchases for restore
      const { getAvailablePurchases } = await import('react-native-iap');
      const purchases = await getAvailablePurchases();
      console.log('[IAP] Restored purchases:', purchases);
      
      // Filter for our product IDs only
      return purchases.filter((p: Purchase) => 
        PRODUCT_IDS.includes(p.productId as ProductId)
      );
    } catch (error) {
      console.error('[IAP] Failed to restore purchases:', error);
      throw error;
    }
  }

  /**
   * Set up listeners for purchase updates and errors.
   * Callbacks are invoked when purchases complete or fail.
   */
  setupListeners(
    onPurchaseUpdate: (purchase: Purchase) => void,
    onPurchaseError: (error: PurchaseError) => void
  ): void {
    this.purchaseUpdateSubscription = purchaseUpdatedListener((purchase: Purchase) => {
      console.log('[IAP] Purchase updated:', purchase);
      onPurchaseUpdate(purchase);
    });

    this.purchaseErrorSubscription = purchaseErrorListener((error: PurchaseError) => {
      console.error('[IAP] Purchase error:', error);
      onPurchaseError(error);
    });
  }

  /**
   * Finalize/acknowledge a purchase.
   * Required by Google Play to confirm receipt.
   */
  async finalizePurchase(purchase: Purchase): Promise<void> {
    try {
      await finishTransaction({ purchase, isConsumable: false });
      console.log('[IAP] Purchase finalized:', purchase.productId);
    } catch (error) {
      console.error('[IAP] Failed to finalize purchase:', error);
      throw error;
    }
  }

  /**
   * Get the most recent active purchase for our products.
   * Returns null if no active subscription found.
   */
  async getActivePurchase(): Promise<Purchase | null> {
    try {
      const purchases = await this.restorePurchases();
      
      // Sort by purchase time, most recent first
      const sorted = purchases.sort((a, b) => 
        (b.transactionDate || 0) - (a.transactionDate || 0)
      );
      
      return sorted[0] || null;
    } catch (error) {
      console.error('[IAP] Failed to get active purchase:', error);
      return null;
    }
  }
}

// Singleton instance
export const iapClient = new IAPClient();
