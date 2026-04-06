/**
 * Shared error classification for premium-gated screens.
 *
 * Any screen that POSTs to a require_premium() endpoint can use this
 * utility to classify errors into safe, renderable states without crashing.
 *
 * Covered error shapes:
 *  - 401 / 403       → entitlement (show subscription UI)
 *  - no .response    → network (show connectivity message)
 *  - all other HTTP  → server (show best-available backend message)
 *  - null/undefined  → server fallback
 */

export type PremiumErrorKind =
  | 'entitlement' // 401/403 – user lacks an active entitlement
  | 'network'     // no HTTP response – connectivity problem
  | 'server';     // 4xx/5xx other than auth

export interface PremiumErrorResult {
  kind: PremiumErrorKind;
  message: string;
}

/**
 * Classify any thrown value from an axios call into a PremiumErrorResult.
 *
 * @param err   The caught error (typically an axios error object)
 * @param fallback  Fallback message for server-kind errors when no detail is
 *                  available from the backend. Defaults to a generic message.
 */
export function classifyPremiumError(
  err: unknown,
  fallback = 'Something went wrong. Please try again.'
): PremiumErrorResult {
  if (!err) {
    return { kind: 'server', message: fallback };
  }

  const status: number | undefined = (err as any)?.response?.status;
  const detail: string | undefined = (err as any)?.response?.data?.detail;
  const message: string | undefined = (err as any)?.message;

  // Auth / entitlement failures
  if (status === 401 || status === 403) {
    return {
      kind: 'entitlement',
      message:
        'Active subscription required. Please restore or activate your subscription.',
    };
  }

  // Network error – no HTTP response at all
  if (!(err as any)?.response) {
    return {
      kind: 'network',
      message: 'Network error. Please check your connection and try again.',
    };
  }

  // Everything else (500, 503, 429, malformed payload, etc.)
  return {
    kind: 'server',
    message: detail || message || fallback,
  };
}

/**
 * Safely extract a named array from a backend response payload.
 * Returns [] for any non-array value, null, undefined, or non-object payload.
 *
 * @param data  The axios response data (unknown shape)
 * @param key   The key holding the array (e.g. 'supplies', 'stations', 'spots')
 */
export function extractResultArray(data: unknown, key: string): unknown[] {
  if (!data || typeof data !== 'object') return [];
  const arr = (data as Record<string, unknown>)[key];
  return Array.isArray(arr) ? arr : [];
}
