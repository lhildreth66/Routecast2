/**
 * propaneCalc — deterministic RV propane calculator
 *
 * All math is client-side. No API calls. No hidden magic numbers.
 * Constants, duty-cycle table, and length multipliers are verbatim from spec.
 */

// ─── Constants (DO NOT CHANGE) ──────────────────────────────────────────────
export const PROPANE_BTU_PER_GAL  = 91_500;
export const PROPANE_LB_PER_GAL   = 4.2;
const HOT_WATER_BTU_PER_GAL_60F   = 500;   // ~8.34 lb/gal × 60 °F rise
const DEFAULT_SHOWER_GPM          = 2.0;
const DEFAULT_HOT_MIX             = 0.60;
export const DEFAULT_NIGHT_HOURS  = 10;
const MAX_DUTY_CYCLE              = 0.90;

// ─── Input shape ─────────────────────────────────────────────────────────────
export interface PropaneInputs {
  outsideTempF:   number;
  nights:         number;
  nightHours:     number;
  rvLengthFt:     number;
  people:         number;
  showersPerDay:  number;
  showerMinutes:     number;
  waterHeaterMode:    'propane' | 'electric' | 'both';
  tankSizeLb:         number;
  tankFillPct:    number;
  furnaceBTU:     number;
  mealsPerDay:    number;
  fridgeMode:     'propane' | 'electric';
  genHoursPerDay: number;
}

// ─── Output shape ─────────────────────────────────────────────────────────────
export interface PropaneBreakdown {
  furnaceGalPerNight:   number;
  hotWaterGalPerNight:  number;
  cookGalPerNight:      number;
  fridgeGalPerNight:    number;
  genGalPerNight:       number;
}

export interface PropaneResult {
  totalGalPerNight:  number;
  totalLbPerNight:   number;
  totalGalTrip:      number;
  totalLbTrip:       number;
  tankTotalGal:      number;
  usableGal:         number;
  nightsRemaining:   number;
  breakdown:         PropaneBreakdown;
  lowGalPerNight:    number;
  highGalPerNight:   number;
  effectiveDuty:     number;
}

// ─── Internal helpers ────────────────────────────────────────────────────────
function baseDutyCycle(tempF: number): number {
  if (tempF >= 55) return 0.10;
  if (tempF >= 45) return 0.20;
  if (tempF >= 35) return 0.35;
  if (tempF >= 25) return 0.50;
  if (tempF >= 15) return 0.65;
  return 0.80;
}

function lengthMultiplier(ft: number): number {
  if (ft <= 20) return 0.85;
  if (ft <= 25) return 0.95;
  if (ft <= 30) return 1.00;
  if (ft <= 35) return 1.10;
  if (ft <= 40) return 1.20;
  return 1.30;
}

function inletMultiplier(tempF: number): number {
  if (tempF >= 60) return 1.0;
  if (tempF >= 40) return 1.2;
  if (tempF >= 20) return 1.4;
  return 1.6;
}

function clamp(val: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, val));
}

// ─── Main calculator ─────────────────────────────────────────────────────────
export function calcPropane(i: PropaneInputs): PropaneResult {
  // 2. Furnace
  const duty = clamp(
    baseDutyCycle(i.outsideTempF) * lengthMultiplier(i.rvLengthFt),
    0,
    MAX_DUTY_CYCLE
  );
  const furnaceBTUPerNight  = i.furnaceBTU * duty * i.nightHours;
  const furnaceGalPerNight  = furnaceBTUPerNight / PROPANE_BTU_PER_GAL;

  // 3. Hot water
  const hotGalPerShower        = i.showerMinutes * DEFAULT_SHOWER_GPM * DEFAULT_HOT_MIX;
  const dailyHotGal             = hotGalPerShower * i.showersPerDay * i.people;
  const hotWaterBTUPerDay       = dailyHotGal * HOT_WATER_BTU_PER_GAL_60F * inletMultiplier(i.outsideTempF);
  const hotWaterGalRaw          = hotWaterBTUPerDay / PROPANE_BTU_PER_GAL;
  // Apply water heater mode multiplier
  const whMultiplier            = i.waterHeaterMode === 'electric' ? 0.0
                                : i.waterHeaterMode === 'both'     ? 0.5
                                : /* propane */                      1.0;
  const hotWaterGalPerNight     = hotWaterGalRaw * whMultiplier;

  // 4. Other appliances
  const cookGalPerNight   = i.mealsPerDay * 0.10;
  const fridgeGalPerNight = i.fridgeMode === 'propane' ? 0.20 : 0;
  const genGalPerNight    = i.genHoursPerDay * 0.40;

  // 5. Totals
  const totalGalPerNight = (
    furnaceGalPerNight +
    hotWaterGalPerNight +
    cookGalPerNight +
    fridgeGalPerNight +
    genGalPerNight
  );
  const totalGalTrip = totalGalPerNight * i.nights;

  // 6. Tank
  const tankTotalGal    = i.tankSizeLb / PROPANE_LB_PER_GAL;
  const usableGal       = tankTotalGal * (i.tankFillPct / 100);
  const nightsRemaining = totalGalPerNight > 0 ? usableGal / totalGalPerNight : Infinity;

  // 7. Ranges (±20%)
  const lowGalPerNight  = totalGalPerNight * 0.8;
  const highGalPerNight = totalGalPerNight * 1.2;

  return {
    totalGalPerNight,
    totalLbPerNight:  totalGalPerNight * PROPANE_LB_PER_GAL,
    totalGalTrip,
    totalLbTrip:      totalGalTrip * PROPANE_LB_PER_GAL,
    tankTotalGal,
    usableGal,
    nightsRemaining,
    breakdown: { furnaceGalPerNight, hotWaterGalPerNight, cookGalPerNight, fridgeGalPerNight, genGalPerNight },
    lowGalPerNight,
    highGalPerNight,
    effectiveDuty: duty,
  };
}
