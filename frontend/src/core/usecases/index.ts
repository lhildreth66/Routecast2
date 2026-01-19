/**
 * Use Cases — Application Layer
 *
 * Orchestrates domain logic with cross-cutting concerns (entitlements, analytics, etc.)
 */

// Energy Use Cases
export { getSolarForecast } from './energy/getSolarForecast';
export type { SolarForecastInput } from './energy/getSolarForecast';

// Road Use Cases
export {
  getRoadPassability,
  SoilTypeEnum,
  type Passability,
  type SoilType,
} from './road/getRoadPassability';
export type { RoadPassabilityInput } from './road/getRoadPassability';
