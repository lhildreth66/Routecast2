import type { Entitlements } from '../../billing/Entitlements';
import { premiumGate } from '../../billing/premiumGate';
import { PremiumLockedError } from '../../billing/PremiumLockedError';
import { forecastDailyWh } from '../../domain/energy/SolarForecastService';
import { trackEvent } from '../../analytics/track';

/**
 * Solar Forecast Input Parameters
 */
export interface SolarForecastInput {
  /** Latitude in degrees (-90 to 90) */
  lat: number;

  /** Longitude in degrees (-180 to 180) */
  lon: number;

  /** Array of day-of-year integers (1-365) */
  dateRange: number[];

  /** Solar panel capacity in watts */
  panelWatts: number;

  /** Average shade percentage (0-100) */
  shadePct: number;

  /** Array of cloud cover percentages per day (0-100) */
  cloudCover: number[];
}

/**
 * Get Solar Forecast Use Case
 *
 * Premium-gated wrapper around solar forecast domain logic.
 * Requires 'solar_forecast' entitlement.
 *
 * Analytics events:
 * - Always logs 'feature_intent_used' when called
 * - Logs 'feature_locked_shown' if entitlement missing (before throwing)
 *
 * @param entitlements User's entitlements
 * @param input Solar forecast parameters
 * @param source Optional analytics source identifier
 * @returns Array of daily energy production in Wh/day
 * @throws PremiumLockedError if user lacks solar_forecast entitlement
 */
export function getSolarForecast(
  entitlements: Entitlements,
  input: SolarForecastInput,
  source?: string
): number[] {
  const feature = 'solar_forecast';

  // Always track intent
  trackEvent('feature_intent_used', { feature, source });

  // Check if locked and track before throwing
  if (!entitlements.has(feature)) {
    trackEvent('feature_locked_shown', { feature, source });
    throw new PremiumLockedError(feature);
  }

  // Execute domain logic if entitled
  return forecastDailyWh(
    input.lat,
    input.lon,
    input.dateRange,
    input.panelWatts,
    input.shadePct,
    input.cloudCover
  );
}
