import { score, type Passability, type SoilType } from '../../domain/road/RoadPassability';

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
 * Assesses road passability based on weather and terrain conditions.
 *
 * @param input Road passability parameters
 * @returns Passability assessment with score and flags
 */
export function getRoadPassability(
  input: RoadPassabilityInput
): Passability {
  // Execute domain logic
  return score(input.precip72hIn, input.slopePct, input.minTempF, input.soil);
}

// Re-export types for convenience
export type { Passability, SoilType };
export { SoilType as SoilTypeEnum } from '../../domain/road/RoadPassability';
