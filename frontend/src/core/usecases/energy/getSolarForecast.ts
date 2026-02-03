import { forecastDailyWh } from '../../domain/energy/SolarForecastService';

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
 * Calculates expected solar panel energy production based on location, 
 * panel specs, and weather conditions.
 *
 * @param input Solar forecast parameters
 * @returns Array of daily energy production in Wh/day
 */
export function getSolarForecast(
  input: SolarForecastInput
): number[] {
  // Execute domain logic
  return forecastDailyWh(
    input.lat,
    input.lon,
    input.dateRange,
    input.panelWatts,
    input.shadePct,
    input.cloudCover
  );
}
