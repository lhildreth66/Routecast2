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
  purchase: (offerToken?: string) => Promise<PurchaseVerificationPayload | null>;
  restore: () => Promise<void>;
}

export interface PurchaseVerificationPayload {
  purchaseToken: string;
  productId: string;
  packageName: string;
}

// Single Play subscription SKU with base plans (monthly, annual) and optional offers (e.g., trial7d).
const SUBSCRIPTION_SKU = 'routecast_vs1';

export function useBilling(): BillingApi {
  const [products, setProducts] = useState<BillingProduct[]>([]);
  const [isLoading, setLoading] = useState(false);
  const [isPurchasing, setPurchasing] = useState(false);
  const [isRestoring, setRestoring] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [purchases, setPurchases] = useState<Array<IAP.Purchase | IAP.ActiveSubscription>>([]);

  // Entitlement: any completed purchase (state PURCHASED, acknowledged) for our SKUs
  const entitlementActive = useMemo(() => {
    return purchases.some((p: any) => {
      const pid = p.id ?? p.productId ?? p.sku;
      // ActiveSubscription uses isActive; Purchase uses purchaseState === 'purchased'
      if (pid !== SUBSCRIPTION_SKU && p.sku !== SUBSCRIPTION_SKU) return false;
      if (p.isActive === true) return true;
      if (p.purchaseState === 'purchased') return true;
      if (p.purchaseStateAndroid === IAP.PurchaseState.PURCHASED) return true;
      if (p.acknowledged === true) return true;
      return false;
    });
  }, [purchases]);

  useEffect(() => {
    let mounted = true;

    const purchaseSub = IAP.purchaseUpdatedListener(async (purchase) => {
      if (!mounted || !purchase) return;
      setPurchases([purchase]);
      try {
        await IAP.finishTransaction({ purchase });
      } catch (e) {
        // swallow; retry on next launch
      }
    });

    const errorSub = IAP.purchaseErrorListener((err) => {
      console.error('Purchase error:', err);
      setError(err?.message ?? 'Purchase failed');
    });

    connect();

    return () => {
      mounted = false;
      purchaseSub.remove();
      errorSub.remove();
      IAP.endConnection?.();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const connect = async () => {
    console.log('IAP initConnection starting...');
    setLoading(true);
    setError(null);
    try {
      await IAP.initConnection();
      const fetched = await IAP.fetchProducts({ skus: [SUBSCRIPTION_SKU], type: 'subs' });
      const normalized = (fetched ?? []).map((p: any) => ({
        ...p,
        id: p.id ?? p.productId,
        subscriptionOfferDetailsAndroid: p.subscriptionOfferDetailsAndroid ?? p.subscriptionOfferDetails,
      }));
      console.log('[billing] fetched products summary', normalized?.map((p) => ({
        productId: p.id,
        title: p.title,
        offers: p.subscriptionOfferDetailsAndroid?.map((o: any) => ({
          basePlanId: o.basePlanId,
          offerId: o.offerId,
          hasToken: Boolean(o.offerToken),
          pricingPhases: o.pricingPhases?.pricingPhaseList?.length,
        })),
      })));
      setProducts(normalized ?? []);

      // Hydrate active subs to infer entitlement
      const active = await IAP.getAvailablePurchases();
      if (active) setPurchases(active);
    } catch (e: any) {
      setError(e?.message ?? 'Billing unavailable');
    } finally {
      setLoading(false);
    }
  };

  const purchase = async (offerToken?: string) => {
    if (!offerToken) {
      setError('Offer unavailable');
      return null;
    }
    setPurchasing(true);
    setError(null);
    try {
      await IAP.requestPurchase({
        type: 'subs',
        request: {
          google: {
            skus: [SUBSCRIPTION_SKU],
            subscriptionOffers: [{ sku: SUBSCRIPTION_SKU, offerToken }],
          },
        },
      });

      // The purchase listener can resolve after requestPurchase returns.
      // Poll briefly for an active purchase token we can send to backend verification.
      for (let attempt = 0; attempt < 5; attempt += 1) {
        const active = await IAP.getAvailablePurchases();
        if (active?.length) {
          setPurchases(active);
          const latest = [...active]
            .reverse()
            .find((p: any) => {
              const pid = p.productId ?? p.sku ?? p.id;
              return pid === SUBSCRIPTION_SKU;
            });

          const purchaseToken = (latest as any)?.purchaseToken ?? (latest as any)?.purchaseTokenAndroid ?? '';
          const productId = (latest as any)?.productId ?? (latest as any)?.sku ?? (latest as any)?.id ?? SUBSCRIPTION_SKU;
          if (purchaseToken) {
            return {
              purchaseToken,
              productId,
              packageName: 'com.routecast.app',
            };
          }
        }

        await new Promise((resolve) => setTimeout(resolve, 700));
      }

      setError('Purchase finished, but receipt token was unavailable. Tap Restore purchases and try again.');
      return null;
    } catch (e: any) {
      setError(e?.message ?? 'Purchase failed');
      return null;
    } finally {
      setPurchasing(false);
    }
  };

  const restore = async () => {
    setRestoring(true);
    setError(null);
    try {
      await IAP.restorePurchases();
      const active = await IAP.getAvailablePurchases();
      if (active) setPurchases(active);
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
