/**
 * Entitlements Initialization
 *
 * App startup helper for loading persisted entitlements.
 */

import type { CachedEntitlements } from './CachedEntitlements';

/**
 * Initialize entitlements on app start.
 *
 * Hydrates entitlements from persistent storage into memory.
 * Must be called before using entitlements.
 *
 * @param entitlements Cached entitlements instance to hydrate
 */
export async function initEntitlements(
  entitlements: CachedEntitlements
): Promise<void> {
  await entitlements.hydrate();
}
