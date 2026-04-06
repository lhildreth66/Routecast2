/**
 * Error classification for the Last Chance Supplies screen.
 *
 * Re-exports shared premium-screen error utilities with screen-specific
 * type aliases and a convenience wrapper for the 'supplies' array key.
 */

export { classifyPremiumError as classifyLastChanceError } from './premiumScreenErrors';
export type { PremiumErrorResult as LastChanceErrorResult, PremiumErrorKind as LastChanceErrorKind } from './premiumScreenErrors';

import { extractResultArray } from './premiumScreenErrors';

/**
 * Extract the 'supplies' array from a last-chance/search response payload.
 * Returns [] for any non-array or missing value.
 */
export function extractSupplies(data: unknown): unknown[] {
  return extractResultArray(data, 'supplies');
}
