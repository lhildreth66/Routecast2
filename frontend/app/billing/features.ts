/**
 * Premium Feature Definitions
 * 
 * Shared constants for premium features across frontend.
 * These must match the backend definitions exactly.
 */

export const SOLAR_FORECAST = "solar_forecast";
export const BATTERY_SOC = "battery_soc";
export const PROPANE_USAGE = "propane_usage";
export const ROAD_SIM = "road_sim";
export const CELL_STARLINK = "cell_starlink";
export const EVAC_OPTIMIZER = "evac_optimizer";
export const CLAIM_LOG = "claim_log";

export const PREMIUM_FEATURES = [
  SOLAR_FORECAST,
  BATTERY_SOC,
  PROPANE_USAGE,
  ROAD_SIM,
  CELL_STARLINK,
  EVAC_OPTIMIZER,
  CLAIM_LOG,
] as const;

export type PremiumFeature = typeof PREMIUM_FEATURES[number];

export function isPremiumFeature(feature: string): feature is PremiumFeature {
  return PREMIUM_FEATURES.includes(feature as PremiumFeature);
}
