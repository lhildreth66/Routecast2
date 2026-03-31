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
  purchase: (offerToken?: string) => Promise<void>;
  restore: () => Promise<void>;
}

const noopAsync = async () => {};

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
    purchase: noopAsync,
    restore: noopAsync,
  }), []);
}

export const billingSku = 'routecast_vs1';
