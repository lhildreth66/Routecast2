import { useEffect, useMemo, useState } from 'react';
import { Platform } from 'react-native';
import * as IAP from 'expo-iap';

type BillingProduct = IAP.ProductSubscription;

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
  purchase: (skuOrToken?: string) => Promise<PurchaseVerificationPayload | null>;
  restore: () => Promise<void>;
}

export interface PurchaseVerificationPayload {
  // Required — structurally compatible with postPurchaseFlow.ts
  purchaseToken: string;  // Android: Play token;  iOS: transactionId (compat)
  productId: string;
  packageName: string;
  // Discriminant
  platform: 'android' | 'ios';
  // iOS-specific extras
  receiptData?: string;          // JWS signed transaction (purchaseToken from expo-iap on iOS)
  transactionId?: string;
  originalTransactionId?: string;
}

// Android: single subscription SKU with base plans (monthly, annual) and optional offers.
const ANDROID_SUBSCRIPTION_SKU = 'routecast_vs1';

// iOS: separate product IDs for each plan (matches App Store Connect).
const IOS_SKU_MONTHLY = 'routecast_monthly';
const IOS_SKU_ANNUAL  = 'routecast_annual';
const IOS_SKUS        = [IOS_SKU_MONTHLY, IOS_SKU_ANNUAL];

/** @deprecated Use ANDROID_SUBSCRIPTION_SKU. Kept for external callers. */
const SUBSCRIPTION_SKU = ANDROID_SUBSCRIPTION_SKU;

export function useBilling(): BillingApi {
  const [products, setProducts] = useState<BillingProduct[]>([]);
  const [isLoading, setLoading] = useState(false);
  const [isPurchasing, setPurchasing] = useState(false);
  const [isRestoring, setRestoring] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [purchases, setPurchases] = useState<Array<IAP.Purchase | IAP.ActiveSubscription>>([]);

  // Entitlement: active purchase for any of our SKUs
  const entitlementActive = useMemo(() => {
    return purchases.some((p: any) => {
      const pid = p.id ?? p.productId ?? p.sku;
      // Android SKU
      if (pid === ANDROID_SUBSCRIPTION_SKU || p.sku === ANDROID_SUBSCRIPTION_SKU) {
        if (p.isActive === true) return true;
        if (p.purchaseState === 'purchased') return true;
        if (p.purchaseState === 'restored') return true;
        if (p.acknowledged === true) return true;
      }
      // iOS SKUs
      if (IOS_SKUS.includes(pid)) {
        if (p.isActive === true) return true;
        if (p.purchaseState === 'purchased') return true;
        if (p.transactionId) return true;
      }
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

    // Safety: if StoreKit/Play hangs and never resolves, force-clear loading
    // after 15 seconds so the screen never traps the user.
    const loadingTimeout = setTimeout(() => {
      setLoading((prev) => {
        if (prev) {
          setError('Store connection timed out. Please go back and try again.');
        }
        return false;
      });
    }, 15000);

    try {
      await IAP.initConnection();

      if (Platform.OS === 'ios') {
        // iOS: fetch each plan as a separate product.
        const fetched = await IAP.fetchProducts({ skus: IOS_SKUS, type: 'subs' });
        setProducts((fetched ?? []) as unknown as IAP.ProductSubscription[]);
      } else {
        // Android: single SKU with base plans; normalize offer details field name.
        const fetched = await IAP.fetchProducts({ skus: [ANDROID_SUBSCRIPTION_SKU], type: 'subs' });
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
      }

      // Hydrate active subs to infer entitlement
      const active = await IAP.getAvailablePurchases();
      if (active) setPurchases(active);
    } catch (e: any) {
      setError(e?.message ?? 'Billing unavailable');
    } finally {
      clearTimeout(loadingTimeout);
      setLoading(false);
    }
  };

  const purchase = async (skuOrToken?: string): Promise<PurchaseVerificationPayload | null> => {
    if (Platform.OS === 'ios') {
      return purchaseIos(skuOrToken);
    }
    return purchaseAndroid(skuOrToken);
  };

  // ── Android purchase ──────────────────────────────────────────────────────
  const purchaseAndroid = async (offerToken?: string): Promise<PurchaseVerificationPayload | null> => {
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
            skus: [ANDROID_SUBSCRIPTION_SKU],
            subscriptionOffers: [{ sku: ANDROID_SUBSCRIPTION_SKU, offerToken }],
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
              return pid === ANDROID_SUBSCRIPTION_SKU;
            });

          const purchaseToken = (latest as any)?.purchaseToken ?? (latest as any)?.purchaseTokenAndroid ?? '';
          const productId = (latest as any)?.productId ?? (latest as any)?.sku ?? (latest as any)?.id ?? ANDROID_SUBSCRIPTION_SKU;
          if (purchaseToken) {
            return {
              purchaseToken,
              productId,
              packageName: 'com.routecast.app',
              platform: 'android',
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

  // ── iOS purchase ──────────────────────────────────────────────────────────
  const purchaseIos = async (sku?: string): Promise<PurchaseVerificationPayload | null> => {
    if (!sku) {
      setError('No product selected');
      return null;
    }
    setPurchasing(true);
    setError(null);
    try {
      await IAP.requestPurchase({
        type: 'subs',
        request: {
          apple: { sku },
        },
      });

      // Poll for the completed StoreKit transaction.
      for (let attempt = 0; attempt < 5; attempt += 1) {
        const active = await IAP.getAvailablePurchases();
        if (active?.length) {
          setPurchases(active);
          const latest = [...active]
            .reverse()
            .find((p: any) => {
              const pid = p.productId ?? p.sku ?? p.id;
              return IOS_SKUS.includes(pid);
            });

          if (latest) {
            const jws      = (latest as any)?.purchaseToken ?? '';   // JWS signed transaction
            const txId     = (latest as any)?.transactionId ?? '';
            const origTxId = (latest as any)?.originalTransactionIdentifierIOS ?? txId;
            const pid      = (latest as any)?.productId ?? (latest as any)?.sku ?? (latest as any)?.id ?? sku;

            if (jws || txId) {
              return {
                purchaseToken: txId,              // compat field
                productId: pid,
                packageName: 'com.routecast.app',
                platform: 'ios',
                receiptData: jws,
                transactionId: txId,
                originalTransactionId: origTxId,
              };
            }
          }
        }

        await new Promise((resolve) => setTimeout(resolve, 700));
      }

      setError('Purchase finished, but receipt was unavailable. Tap Restore purchases and try again.');
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
export const billingSku = ANDROID_SUBSCRIPTION_SKU;
