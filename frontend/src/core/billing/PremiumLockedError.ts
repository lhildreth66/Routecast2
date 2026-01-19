/**
 * Premium Feature Types
 *
 * Defines all premium features available in Routecast Pro (Boondocking Pro).
 */
export type Feature =
  | 'solar_forecast'
  | 'road_passability'
  | 'propane_forecast'
  | 'battery_forecast'
  | 'water_plan'
  | 'cell_starlink'
  | 'camp_index'
  | 'claim_log';

/**
 * Premium Locked Error
 *
 * Thrown when a premium feature is accessed without proper entitlements.
 * This error can be caught by UI layers to display paywall prompts.
 */
export class PremiumLockedError extends Error {
  public readonly feature: Feature;

  constructor(feature: Feature, message?: string) {
    super(message || `Premium feature locked: ${feature}`);
    this.name = 'PremiumLockedError';
    this.feature = feature;

    // Maintain proper stack trace for where error was thrown (V8 only)
    if (Error.captureStackTrace) {
      Error.captureStackTrace(this, PremiumLockedError);
    }
  }
}
