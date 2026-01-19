import type { Entitlements } from '../../billing/Entitlements';
import { PremiumLockedError } from '../../billing/PremiumLockedError';
import { score, type Passability, type SoilType } from '../../domain/road/RoadPassability';
import { trackEvent } from '../../analytics/track';

/**
 * Road Passability Input Parameters
 */
export interface RoadPassabilityInput {
  /** Total precipitation in last 72 hours (inches) */
  precip72hIn: number;

  /** Road slope/gradient as percentage */
  slopePct: number;

  /** Minimum temperature in Fahrenheit */
  minTempF: number;

  /** Soil type affecting drainage */
  soil: SoilType;
}

/**
 * Get Road Passability Use Case
 *
 * Premium-gated wrapper around road passability domain logic.
 * Requires 'road_passability' entitlement.
 *
 * Analytics events:
 * - Always logs 'feature_intent_used' when called
 * - Logs 'feature_locked_shown' if entitlement missing (before throwing)
 *
 * @param entitlements User's entitlements
 * @param input Road passability parameters
 * @param source Optional analytics source identifier
 * @returns Passability assessment with score and flags
 * @throws PremiumLockedError if user lacks road_passability entitlement
 */
export function getRoadPassability(
  entitlements: Entitlements,
  input: RoadPassabilityInput,
  source?: string
): Passability {
  const feature = 'road_passability';

  // Always track intent
  trackEvent('feature_intent_used', { feature, source });

  // Check if locked and track before throwing
  if (!entitlements.has(feature)) {
    trackEvent('feature_locked_shown', { feature, source });
    throw new PremiumLockedError(feature);
  }

  // Execute domain logic if entitled
  return score(input.precip72hIn, input.slopePct, input.minTempF, input.soil);
}

// Re-export types for convenience
export type { Passability, SoilType };
export { SoilType as SoilTypeEnum } from '../../domain/road/RoadPassability';
