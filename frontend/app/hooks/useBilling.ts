import { useEffect, useMemo, useState } from 'react';
import * as IAP from 'expo-iap';

type BillingProduct = IAP.Subscription;

export interface BillingState {
  products: BillingProduct[];
  isLoading: boolean;
  isPurchasing: boolean;
  isRestoring: boolean;
  error: string | null;
  entitlementActive: boolean;
}

export interface BillingApi extends BillingState {
  connect: () => Promise<void>;
  purchase: (offerToken?: string) => Promise<void>;
  restore: () => Promise<void>;
}

// Single Play subscription SKU with base plans (monthly, annual) and optional offers (e.g., trial7d).
const SUBSCRIPTION_SKU = 'routecast_vs1';

export function useBilling(): BillingApi {
  const [products, setProducts] = useState<BillingProduct[]>([]);
  const [isLoading, setLoading] = useState(false);
  const [isPurchasing, setPurchasing] = useState(false);
  const [isRestoring, setRestoring] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [purchases, setPurchases] = useState<IAP.InAppPurchase[]>([]);

  // Entitlement: any completed purchase (state PURCHASED, acknowledged) for our SKUs
  const entitlementActive = useMemo(() => {
    return purchases.some((p) =>
      p.productId === SUBSCRIPTION_SKU &&
      (p.purchaseStateAndroid === IAP.PurchaseState.PURCHASED || p.acknowledged === true)
    );
  }, [purchases]);

  useEffect(() => {
    let mounted = true;

    const listener = IAP.setPurchaseListener(async (result) => {
      if (!mounted) return;
      if (result.responseCode === IAP.IAPResponseCode.OK && result.results?.length) {
        setPurchases(result.results);
        // Acknowledge/finish to avoid future blocking
        for (const purchase of result.results) {
          try {
            await IAP.finishTransaction(purchase, false);
          } catch (e) {
            // swallow; will retry on next launch
          }
        }
      } else if (result.responseCode === IAP.IAPResponseCode.USER_CANCELED) {
        setError('Purchase canceled');
      } else if (result.responseCode !== IAP.IAPResponseCode.OK) {
        setError(result.errorCode || 'Purchase failed');
      }
    });

    connect();

    return () => {
      mounted = false;
      listener.remove();
      IAP.endConnection?.();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const connect = async () => {
    setLoading(true);
    setError(null);
    try {
      await IAP.initConnection();
      const subs = await IAP.getSubscriptions([SUBSCRIPTION_SKU]);
      setProducts(subs ?? []);
      // Also hydrate purchase history to infer entitlement
      const history = await IAP.getPurchaseHistory();
      setPurchases(history ?? []);
    } catch (e: any) {
      setError(e?.message ?? 'Billing unavailable');
    } finally {
      setLoading(false);
    }
  };

  const purchase = async (offerToken?: string) => {
    if (!offerToken) {
      setError('Offer unavailable');
      return;
    }
    setPurchasing(true);
    setError(null);
    try {
      await IAP.requestSubscription({
        sku: SUBSCRIPTION_SKU,
        subscriptionOffers: [{ sku: SUBSCRIPTION_SKU, offerToken }],
      });
    } catch (e: any) {
      setError(e?.message ?? 'Purchase failed');
    } finally {
      setPurchasing(false);
    }
  };

  const restore = async () => {
    setRestoring(true);
    setError(null);
    try {
      const history = await IAP.getPurchaseHistory();
      setPurchases(history ?? []);
    } catch (e: any) {
      setError(e?.message ?? 'Restore failed');
    } finally {
      setRestoring(false);
    }
  };

  return {
    products,
    isLoading,
    isPurchasing,
    isRestoring,
    error,
    entitlementActive,
    connect,
    purchase,
    restore,
  };
}
export const billingSku = SUBSCRIPTION_SKU;