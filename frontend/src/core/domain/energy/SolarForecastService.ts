/**
 * Solar Forecast Service — Pure Domain Logic
 *
 * Estimates daily solar energy production (Wh/day) for boondocking/RV solar systems.
 * All functions are pure (no side effects) and deterministic (same inputs → same outputs).
 *
 * Calculation Model:
 * 1. Clear-sky baseline: ~5.5 peak sun hours/day at equator on equinox
 * 2. Latitude adjustment: cosine scaling for distance from equator
 * 3. Seasonal adjustment: solar declination varies ±23.5° throughout year
 * 4. Cloud cover multiplier: 0.2 (full overcast) to 1.0 (clear sky)
 * 5. Shade loss: (100 - shade_pct) / 100
 * 6. Final: baseline × cloud_multiplier × shade_loss × panel_watts
 *
 * Assumptions:
 * - Standard panel efficiency (~20%)
 * - No obstructions except shade
 * - Panel orientation: optimal (south-facing, tilted)
 * - Clear-sky irradiance: 1000 W/m² at solar noon
 *
 * Edge Cases:
 * - Latitude > 66.5°: polar regions (extreme seasonal variation)
 * - Shade > 100%: clamped to 100% (0 production)
 * - Cloud > 100%: clamped to 100% (minimum 0.2 multiplier)
 * - Panel watts < 0: throws Error
 */

const BASELINE_PEAK_SUN_HOURS = 5.5; // Equator on equinox
const SOLAR_DECLINATION_MAX = 23.45; // Degrees
const MINIMUM_CLOUD_MULTIPLIER = 0.2; // Full overcast

/**
 * Calculate clear-sky solar irradiance baseline (peak sun hours/day).
 *
 * Uses simplified solar geometry:
 * - Day length and sun angle vary by latitude and day of year
 * - Solar declination: ~23.5° × sin((doy - 81) × 2π / 365)
 * - Peak sun hours: baseline × cos(lat - declination)
 *
 * @param lat Latitude in degrees (-90 to 90, positive = north)
 * @param doy Day of year (1 = Jan 1, 365 = Dec 31)
 * @returns Clear-sky baseline in peak sun hours/day
 * @throws Error if lat outside [-90, 90] or doy outside [1, 365]
 */
export function calculateClearSkyBaseline(lat: number, doy: number): number {
  if (lat < -90 || lat > 90) {
    throw new Error(`Latitude must be in range [-90, 90], got: ${lat}`);
  }
  if (doy < 1 || doy > 365) {
    throw new Error(`Day of year must be in range [1, 365], got: ${doy}`);
  }

  // Solar declination (angle of sun relative to equator)
  const declination = SOLAR_DECLINATION_MAX * Math.sin(((doy - 81) * 2 * Math.PI) / 365);

  // Latitude adjustment: cosine of effective latitude difference
  const effectiveLatDiff = Math.abs(lat - declination);
  const latitudeMultiplier = Math.max(0, Math.cos((effectiveLatDiff * Math.PI) / 180));

  // Apply latitude adjustment to baseline
  const peakSunHours = BASELINE_PEAK_SUN_HOURS * latitudeMultiplier;

  // Clamp to realistic range (polar regions)
  return Math.max(0, Math.min(12, peakSunHours));
}

/**
 * Calculate cloud cover multiplier (0.2 to 1.0).
 *
 * Mapping:
 * - 0% cloud → 1.0 (clear sky, full sun)
 * - 30% cloud → 0.8 (mostly clear)
 * - 60% cloud → 0.5 (partly cloudy)
 * - 90% cloud → 0.2 (mostly overcast)
 * - 100% cloud → 0.2 (full overcast, minimum)
 *
 * Formula: 1.0 - (cloud_pct / 100 × 0.8), clamped to [0.2, 1.0]
 *
 * @param cloudCover Cloud cover percentage (0-100, values >100 clamped)
 * @returns Multiplier in range [0.2, 1.0]
 * @throws Error if cloudCover < 0
 */
export function calculateCloudMultiplier(cloudCover: number): number {
  if (cloudCover < 0) {
    throw new Error(`Cloud cover must be >= 0, got: ${cloudCover}`);
  }

  // Clamp to 100% max
  const clampedCloud = Math.min(cloudCover, 100);

  // Linear reduction: 0% = 1.0, 100% = 0.2
  const multiplier = 1.0 - (clampedCloud / 100) * 0.8;

  return Math.max(MINIMUM_CLOUD_MULTIPLIER, Math.min(1.0, multiplier));
}

/**
 * Calculate shade loss multiplier (0.0 to 1.0).
 *
 * Assumes shade blocks all direct sunlight for that percentage of panel.
 * - 0% shade → 1.0 (full sun)
 * - 50% shade → 0.5 (half blocked)
 * - 100% shade → 0.0 (complete block)
 *
 * @param shadePct Shade percentage (0-100, values >100 clamped to 100)
 * @returns Multiplier in range [0.0, 1.0]
 * @throws Error if shadePct < 0
 */
export function calculateShadeLoss(shadePct: number): number {
  if (shadePct < 0) {
    throw new Error(`Shade percentage must be >= 0, got: ${shadePct}`);
  }

  const clampedShade = Math.min(shadePct, 100);
  return (100 - clampedShade) / 100;
}

/**
 * Forecast daily solar energy production (Wh/day) for multiple days.
 *
 * Applies full solar model with latitude, seasonal, cloud, and shade adjustments.
 *
 * @param lat Latitude in degrees (-90 to 90)
 * @param lon Longitude in degrees (-180 to 180, currently unused but reserved)
 * @param dateRange Array of day-of-year integers (1-365)
 * @param panelWatts Solar panel capacity in watts (must be > 0)
 * @param shadePct Average shade percentage (0-100)
 * @param cloudCover Array of cloud cover percentages per day (0-100), must match dateRange length
 * @returns Array of daily energy production in Wh/day (one per dateRange entry)
 * @throws Error if validation fails
 */
export function forecastDailyWh(
  lat: number,
  lon: number,
  dateRange: number[],
  panelWatts: number,
  shadePct: number,
  cloudCover: number[]
): number[] {
  if (lat < -90 || lat > 90) {
    throw new Error(`Latitude must be in range [-90, 90], got: ${lat}`);
  }
  if (lon < -180 || lon > 180) {
    throw new Error(`Longitude must be in range [-180, 180], got: ${lon}`);
  }
  if (panelWatts <= 0) {
    throw new Error(`Panel watts must be > 0, got: ${panelWatts}`);
  }
  if (shadePct < 0) {
    throw new Error(`Shade percentage must be >= 0, got: ${shadePct}`);
  }
  if (dateRange.length === 0) {
    throw new Error('Date range cannot be empty');
  }
  if (cloudCover.length !== dateRange.length) {
    throw new Error(
      `Cloud cover list size (${cloudCover.length}) must match date range size (${dateRange.length})`
    );
  }
  if (!dateRange.every((doy) => doy >= 1 && doy <= 365)) {
    throw new Error('All day-of-year values must be in range [1, 365]');
  }

  const shadeLoss = calculateShadeLoss(shadePct);

  return dateRange.map((doy, index) => {
    const baseline = calculateClearSkyBaseline(lat, doy);
    const cloudMultiplier = calculateCloudMultiplier(cloudCover[index]);

    // Daily Wh = baseline (hours) × cloud × shade × panel_watts
    const dailyWh = baseline * cloudMultiplier * shadeLoss * panelWatts;

    // Clamp to realistic range [0, reasonable maximum]
    return Math.max(0, Math.min(dailyWh, panelWatts * 12)); // Max 12 hours of full sun
  });
}

/**
 * Convenience method: forecast single day.
 *
 * @param lat Latitude in degrees
 * @param lon Longitude in degrees
 * @param doy Day of year (1-365)
 * @param panelWatts Solar panel capacity in watts
 * @param shadePct Shade percentage (0-100)
 * @param cloudCover Cloud cover percentage (0-100)
 * @returns Daily energy production in Wh/day
 */
export function forecastSingleDay(
  lat: number,
  lon: number,
  doy: number,
  panelWatts: number,
  shadePct: number,
  cloudCover: number
): number {
  return forecastDailyWh(lat, lon, [doy], panelWatts, shadePct, [cloudCover])[0];
}
