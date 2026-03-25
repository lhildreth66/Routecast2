declare module 'react-native-iap' {
  import { EmitterSubscription } from 'react-native';

  export type ProductType = 'in-app' | 'subs' | 'all';

  export interface Product {
    id: string;
    title?: string;
    description?: string;
    price?: string;
    priceCurrencyCode?: string;
    localizedPrice?: string;
    type?: ProductType;
    subscriptionOfferDetailsAndroid?: Array<{ offerToken?: string }>;
  }

  export interface Purchase {
    productId: string;
    transactionId?: string;
    transactionReceipt?: string;
    purchaseToken?: string;
    orderId?: string;
  }

  export function initConnection(config?: { alternativeBillingModeAndroid?: 'none' | 'user-choice' | 'alternative-only' }): Promise<boolean | undefined>;
  export function endConnection(): Promise<boolean | undefined>;
  export function fetchProducts(params: { skus: string[]; type?: ProductType }): Promise<Product[]>;
  export function requestPurchase(params: {
    type?: ProductType;
    request: {
      android?: { skus: string[]; [key: string]: any };
      google?: { skus: string[]; [key: string]: any };
      ios?: { sku: string; [key: string]: any };
      apple?: { sku: string; [key: string]: any };
    };
  }): Promise<any>;
  export function purchaseUpdatedListener(listener: (purchase: Purchase) => void): EmitterSubscription;
  export function purchaseErrorListener(listener: (error: any) => void): EmitterSubscription;
  export function finishTransaction(args: { purchase: Purchase; isConsumable?: boolean }): Promise<void>;
  export function getAvailablePurchases(options?: any): Promise<Purchase[]>;
  export function restorePurchases(): Promise<void | any[]>;
  export function deepLinkToSubscriptions(options?: { skuAndroid?: string; packageNameAndroid?: string }): Promise<void>;
}
