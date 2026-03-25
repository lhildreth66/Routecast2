import { Platform } from 'react-native';
import {
  initConnection,
  endConnection,
  fetchProducts,
  requestPurchase,
  purchaseUpdatedListener,
  purchaseErrorListener,
  finishTransaction,
  restorePurchases,
  deepLinkToSubscriptions,
} from 'react-native-iap';

export const PLAY_SUBSCRIPTION_IDS = ['boondocking_pro_monthly', 'boondocking_pro_yearly'];

type ListenerCleanup = () => void;

export async function startBillingConnection(): Promise<void> {
  if (Platform.OS !== 'android') return;
  await initConnection();
}

export async function teardownBilling(): Promise<void> {
  if (Platform.OS !== 'android') return;
  await endConnection();
}

export async function fetchPlaySubscriptions() {
  if (Platform.OS !== 'android') return [] as any[];
  return fetchProducts({ skus: PLAY_SUBSCRIPTION_IDS, type: 'subs' });
}

export async function requestPlayPurchase(productId: string): Promise<void> {
  if (Platform.OS !== 'android') return;
  await requestPurchase({
    type: 'subs',
    request: {
      google: { skus: [productId] },
      android: { skus: [productId] },
    },
  });
}

export function attachPurchaseListeners(
  onPurchase: (purchase: any) => void,
  onError: (error: any) => void,
): ListenerCleanup {
  const update = purchaseUpdatedListener(onPurchase);
  const error = purchaseErrorListener(onError);

  return () => {
    try {
      update?.remove?.();
    } catch { /* noop */ }
    try {
      error?.remove?.();
    } catch { /* noop */ }
  };
}

export async function finalizePurchase(purchase: any): Promise<void> {
  if (!purchase) return;
  await finishTransaction({ purchase, isConsumable: false });
}

export async function restorePlayPurchases() {
  if (Platform.OS !== 'android') return [] as any[];
  return restorePurchases();
}

export async function openPlaySubscriptionManagement(): Promise<void> {
  if (Platform.OS !== 'android') return;
  await deepLinkToSubscriptions({ packageNameAndroid: 'com.routecast.app' });
}
