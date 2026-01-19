/**
 * Road Passability Assessment — Pure Domain Logic
 *
 * Evaluates road conditions based on:
 * - Recent precipitation (72-hour window)
 * - Soil type (drainage characteristics)
 * - Slope (gradient percentage)
 * - Temperature (freezing conditions)
 *
 * Scoring Model:
 * - Base score: 100 (perfect conditions)
 * - Deductions:
 *   - Rain on clay: -40 to -60 (severe mud risk)
 *   - Rain on loam: -20 to -30 (moderate mud)
 *   - Rain on sand: -10 to -20 (loose surface)
 *   - Freezing + precip: -50 (ice risk)
 *   - Steep slope (>15%): -15 to -30
 *   - Combined factors: compounding penalties
 *
 * Thresholds:
 * - Heavy rain: >2.0 inches (72h)
 * - Moderate rain: 0.5 - 2.0 inches
 * - Light rain: 0.1 - 0.5 inches
 * - Freezing: <=32°F
 * - Steep slope: >15%
 * - Very steep: >25%
 *
 * Flags:
 * - mudRisk: precip72hIn > 0.5 AND (clay OR loam)
 * - iceRisk: minTempF <= 32 AND precip72hIn > 0.1
 * - clearanceNeed: (mudRisk AND heavy rain) OR steep slope OR iceRisk
 * - fourByFourRecommended: score < 50
 *
 * Assumptions:
 * - Unpaved road (paved roads not affected by soil)
 * - No maintenance (graded roads perform better)
 * - Standard 2WD sedan clearance (~5-6 inches)
 * - Daytime travel (night reduces visibility/safety)
 */

/**
 * Soil Type Classification
 */
export enum SoilType {
  /** Sandy soil: drains quickly, loose when dry */
  SAND = 'SAND',

  /** Loam soil: balanced, moderate drainage */
  LOAM = 'LOAM',

  /** Clay soil: poor drainage, slippery when wet */
  CLAY = 'CLAY',
}

/**
 * Road Passability Assessment Result
 *
 * Immutable result of passability scoring.
 */
export interface Passability {
  /** Score 0-100 (0 = impassable, 100 = excellent) */
  score: number;

  /** True if mud conditions likely (recent rain + poor drainage) */
  mudRisk: boolean;

  /** True if freezing conditions + precipitation */
  iceRisk: boolean;

  /** True if high clearance vehicle recommended */
  clearanceNeed: boolean;

  /** True if 4WD/AWD strongly recommended */
  fourByFourRecommended: boolean;

  /** Human-readable warnings/explanations */
  notes: string[];
}

/**
 * Calculate road passability score and risk flags.
 *
 * Pure function: same inputs always produce same output, no side effects.
 *
 * @param precip72hIn Total precipitation in last 72 hours (inches, >= 0)
 * @param slopePct Road slope/gradient as percentage (0-100, negative clamped to 0)
 * @param minTempF Minimum temperature in Fahrenheit (realistic range: -50 to 120)
 * @param soil Soil type affecting drainage
 * @returns Passability assessment with score and flags
 * @throws Error if precip72hIn < 0
 */
export function score(
  precip72hIn: number,
  slopePct: number,
  minTempF: number,
  soil: SoilType
): Passability {
  if (precip72hIn < 0) {
    throw new Error(`Precipitation must be >= 0, got: ${precip72hIn}`);
  }

  // Clamp slope to non-negative (downhill = same as uphill for passability)
  const slope = Math.max(0, slopePct);

  // Start with perfect score
  let scoreValue = 100;
  const notes: string[] = [];

  // ===== Precipitation & Soil Interaction =====
  const mudRisk = precip72hIn > 0.5 && (soil === SoilType.CLAY || soil === SoilType.LOAM);

  switch (soil) {
    case SoilType.CLAY:
      // Clay: worst drainage, severe mud when wet
      if (precip72hIn > 2.0) {
        scoreValue -= 60;
        notes.push('Heavy rain on clay soil: severe mud risk');
      } else if (precip72hIn > 0.5) {
        scoreValue -= 40;
        notes.push('Moderate rain on clay: significant mud');
      } else if (precip72hIn > 0.1) {
        scoreValue -= 20;
        notes.push('Light rain on clay: slippery surface');
      }
      break;

    case SoilType.LOAM:
      // Loam: moderate drainage
      if (precip72hIn > 2.0) {
        scoreValue -= 30;
        notes.push('Heavy rain on loam: moderate mud risk');
      } else if (precip72hIn > 0.5) {
        scoreValue -= 20;
        notes.push('Moderate rain on loam: soft surface');
      } else if (precip72hIn > 0.1) {
        scoreValue -= 10;
        notes.push('Light rain on loam: minor wet conditions');
      }
      break;

    case SoilType.SAND:
      // Sand: good drainage, but loose when dry
      if (precip72hIn > 2.0) {
        scoreValue -= 20;
        notes.push('Heavy rain on sand: loose wet surface');
      } else if (precip72hIn > 0.5) {
        scoreValue -= 15;
        notes.push('Moderate rain on sand: soft spots');
      } else if (precip72hIn > 0.1) {
        scoreValue -= 5;
        notes.push('Light rain on sand: mostly firm');
      } else {
        // Dry sand penalty
        scoreValue -= 10;
        notes.push('Dry sand: loose surface, may require 4WD');
      }
      break;
  }

  // ===== Freezing Conditions =====
  const iceRisk = minTempF <= 32 && precip72hIn > 0.1;

  if (iceRisk) {
    scoreValue -= 50;
    notes.push('Freezing temperature with precipitation: ice risk');
  }

  // ===== Slope Penalty =====
  let clearanceNeedSlope = false;

  if (slope > 25.0) {
    scoreValue -= 30;
    notes.push(`Very steep slope (>${Math.floor(slope)}%): high clearance required`);
    clearanceNeedSlope = true;
  } else if (slope > 15.0) {
    scoreValue -= 15;
    notes.push(`Steep slope (${Math.floor(slope)}%): clearance recommended`);
    clearanceNeedSlope = true;
  }

  // ===== Combined Penalties =====
  if (mudRisk && slope > 10.0) {
    scoreValue -= 10;
    notes.push('Mud + slope: compounding difficulty');
  }

  if (iceRisk && slope > 10.0) {
    scoreValue -= 15;
    notes.push('Ice + slope: dangerous conditions');
  }

  // ===== Clamp Score =====
  const finalScore = Math.max(0, Math.min(100, scoreValue));

  // ===== Determine Flags =====
  const clearanceNeed = (mudRisk && precip72hIn > 2.0) || clearanceNeedSlope || iceRisk;
  const fourByFourRecommended = finalScore < 50;

  if (fourByFourRecommended) {
    notes.push(`4WD/AWD strongly recommended (score: ${finalScore})`);
  }

  return {
    score: finalScore,
    mudRisk,
    iceRisk,
    clearanceNeed,
    fourByFourRecommended,
    notes,
  };
}
