import axios from 'axios';
import AsyncStorage from '@react-native-async-storage/async-storage';

const API_BASE = process.env.EXPO_PUBLIC_BACKEND_URL || 'http://localhost:8000';

export interface BillingProduct {
  id: string;
  name: string;
  price: string;
  priceMicros: number;
  currencyCode: string;
}

export interface Subscription {
  subscriptionId: string;
  purchaseToken: string;
  expiryTime: number;
  isActive: boolean;
}

export const BillingService = {
  /**
   * Initialize Google Play Billing (stubbed - awaiting real implementation)
   * Currently returns success to allow app to function
   */
  async initializeBilling(): Promise<boolean> {
    try {
      console.log('[BILLING] Initializing Google Play Billing (STUB)');
      
      // TODO: Replace with real Google Play Billing Library integration
      // For now, just validate backend connectivity
      try {
        const response = await axios.get(`${API_BASE}/api/health`, {
          timeout: 5000,
        });
        console.log('[BILLING] Backend available, billing ready');
        return true;
      } catch (err) {
        console.log('[BILLING] Backend unavailable, operating in offline mode');
        return true; // Still return true to allow app to function
      }
    } catch (err) {
      console.error('[BILLING] Initialization error (non-fatal):', err);
      return true; // Graceful fallback
    }
  },

  /**
   * Get available products from Google Play Store
   * Currently returns test/placeholder product IDs
   */
  async getAvailableProducts(): Promise<BillingProduct[]> {
    try {
      console.log('[BILLING] Fetching available products (STUB)');
      
      // TODO: Replace with real Google Play getProductDetails()
      // Using test/placeholder SKUs for now
      return [
        {
          id: 'routecast_pro_monthly',
          name: 'Routecast Pro - Monthly',
          price: '$4.99',
          priceMicros: 4990000,
          currencyCode: 'USD',
        },
        {
          id: 'routecast_pro_annual',
          name: 'Routecast Pro - Annual',
          price: '$29.99',
          priceMicros: 29990000,
          currencyCode: 'USD',
        },
      ];
    } catch (err) {
      console.error('[BILLING] Error fetching products:', err);
      return [];
    }
  },

  /**
   * Initiate purchase flow with Google Play
   * Currently stubs the purchase and returns success
   */
  async purchase(subscriptionId: string): Promise<boolean> {
    try {
      console.log(`[BILLING] Starting purchase for: ${subscriptionId}`);
      
      // TODO: Replace with real Google Play launchBillingFlow()
      // For now, simulate a successful purchase
      
      // In production:
      // 1. Call Google Play launchBillingFlow()
      // 2. Handle purchase result
      // 3. Validate purchase with backend
      // 4. Enable premium features
      
      console.log('[BILLING] Purchase flow started (STUB - test mode)');
      
      // Simulate successful purchase after 2 seconds
      await new Promise(resolve => setTimeout(resolve, 2000));
      
      // Save to local storage (in real app, backend would verify)
      await AsyncStorage.setItem('routecast_premium_status', 'active');
      await AsyncStorage.setItem('routecast_subscription_id', subscriptionId);
      
      console.log('[BILLING] Purchase successful (STUB)');
      return true;
    } catch (err) {
      console.error('[BILLING] Purchase error:', err);
      return false;
    }
  },

  /**
   * Get current active subscription
   */
  async getActiveSubscription(): Promise<Subscription | null> {
    try {
      console.log('[BILLING] Checking active subscription');
      
      const subId = await AsyncStorage.getItem('routecast_subscription_id');
      const premiumStatus = await AsyncStorage.getItem('routecast_premium_status');
      
      if (subId && premiumStatus === 'active') {
        console.log('[BILLING] Active subscription found:', subId);
        return {
          subscriptionId: subId,
          purchaseToken: 'stub_token', // Placeholder
          expiryTime: Date.now() + 30 * 24 * 60 * 60 * 1000, // 30 days from now
          isActive: true,
        };
      }
      
      console.log('[BILLING] No active subscription');
      return null;
    } catch (err) {
      console.error('[BILLING] Error checking subscription:', err);
      return null;
    }
  },

  /**
   * Cancel subscription
   */
  async cancelSubscription(subscriptionId: string): Promise<boolean> {
    try {
      console.log(`[BILLING] Canceling subscription: ${subscriptionId}`);
      
      // TODO: Call Google Play cancelSubscription()
      
      await AsyncStorage.removeItem('routecast_premium_status');
      await AsyncStorage.removeItem('routecast_subscription_id');
      
      console.log('[BILLING] Subscription canceled');
      return true;
    } catch (err) {
      console.error('[BILLING] Error canceling subscription:', err);
      return false;
    }
  },

  /**
   * Restore previous purchases (on app start or after login)
   */
  async restorePurchases(): Promise<boolean> {
    try {
      console.log('[BILLING] Restoring purchases');
      
      // TODO: Call Google Play queryPurchasesAsync()
      // For now, just check local storage
      
      const premiumStatus = await AsyncStorage.getItem('routecast_premium_status');
      
      if (premiumStatus === 'active') {
        console.log('[BILLING] Previous purchase restored');
        return true;
      }
      
      console.log('[BILLING] No previous purchases found');
      return false;
    } catch (err) {
      console.error('[BILLING] Error restoring purchases:', err);
      return false;
    }
  },
};
