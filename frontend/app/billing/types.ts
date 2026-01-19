/**
 * Billing Types
 * 
 * Type definitions for in-app purchases and entitlements.
 */

export type ProductId = "boondocking_pro_monthly" | "boondocking_pro_yearly";

export type EntitlementSource = "play" | "cache" | "server";

export type PremiumFeature =
  | "solar_forecast"
  | "battery_soc"
  | "propane_usage"
  | "road_sim"
  | "cell_starlink"
  | "evac_optimizer"
  | "claim_log";

export interface Entitlement {
  isPro: boolean;
  productId?: ProductId;
  expireAt?: string; // ISO timestamp
  source: EntitlementSource;
}

export interface CachedEntitlement {
  isPro: boolean;
  productId?: ProductId;
  expireAt?: string;
  lastVerifiedAt?: string;
}

export interface PurchaseResult {
  success: boolean;
  productId?: ProductId;
  error?: string;
}
