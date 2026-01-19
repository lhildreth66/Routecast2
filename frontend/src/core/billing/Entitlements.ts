import type { Feature } from './PremiumLockedError';

/**
 * Entitlements Interface
 *
 * Represents user's access to premium features.
 * Implementations can be backed by:
 * - In-memory cache
 * - AsyncStorage persistence
 * - Remote API validation
 */
export interface Entitlements {
  /**
   * Check if user has access to a specific feature.
   *
   * @param feature The feature to check
   * @returns true if user has access, false otherwise
   */
  has(feature: Feature): boolean;
}

/**
 * Simple In-Memory Entitlements Implementation
 *
 * For testing and development. Does not persist across app restarts.
 */
export class InMemoryEntitlements implements Entitlements {
  private features: Set<Feature>;

  /**
   * Create entitlements with optional initial features.
   *
   * @param initialFeatures Features to grant access to (default: empty)
   */
  constructor(initialFeatures: Feature[] = []) {
    this.features = new Set(initialFeatures);
  }

  /**
   * Check if user has access to a feature.
   */
  has(feature: Feature): boolean {
    return this.features.has(feature);
  }

  /**
   * Grant access to a feature.
   *
   * @param feature Feature to grant
   */
  grant(feature: Feature): void {
    this.features.add(feature);
  }

  /**
   * Revoke access to a feature.
   *
   * @param feature Feature to revoke
   */
  revoke(feature: Feature): void {
    this.features.delete(feature);
  }

  /**
   * Grant access to all features (Pro subscription).
   */
  grantAll(): void {
    const allFeatures: Feature[] = [
      'solar_forecast',
      'road_passability',
      'propane_forecast',
      'battery_forecast',
      'water_plan',
      'cell_starlink',
      'camp_index',
      'claim_log',
    ];
    allFeatures.forEach((f) => this.features.add(f));
  }

  /**
   * Revoke all features (free tier).
   */
  revokeAll(): void {
    this.features.clear();
  }

  /**
   * Get list of granted features.
   */
  getGranted(): Feature[] {
    return Array.from(this.features);
  }
}
