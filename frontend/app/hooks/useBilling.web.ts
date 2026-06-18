import { useMemo } from 'react';

export interface BillingState {
  products: never[];
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
  purchaseToken: string;
  productId: string;
  packageName: string;
  platform?: 'android' | 'ios';
  receiptData?: string;
  transactionId?: string;
  originalTransactionId?: string;
}

const noopAsync = async () => {};
const noopPurchase = async (): Promise<PurchaseVerificationPayload | null> => null;

export function useBilling(): BillingApi {
  // No billing on web; return stable no-op values.
  return useMemo(() => ({
    products: [],
    isLoading: false,
    isPurchasing: false,
    isRestoring: false,
    error: null,
    entitlementActive: false,
    connect: noopAsync,
    purchase: noopPurchase,
    restore: noopAsync,
  }), []);
}

export const billingSku = 'routecast_vs1';
