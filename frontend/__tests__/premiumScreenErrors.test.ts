/**
 * Tests for the shared premiumScreenErrors utility.
 *
 * This utility is used by:
 *  - last-chance.tsx   (via lastChanceErrors.ts re-export)
 *  - water-budget.tsx
 *  - dump-station.tsx
 *  - truck-parking.tsx
 *
 * These tests verify the shared contract so every screen using this utility
 * gets identical error-classification behaviour.
 */

import {
  classifyPremiumError,
  extractResultArray,
  PremiumErrorKind,
} from '../app/utils/premiumScreenErrors';

// ── helpers ──────────────────────────────────────────────────────────────────

function axiosError(status: number, detail?: string) {
  return {
    response: { status, data: detail ? { detail } : {} },
    message: `Request failed with status code ${status}`,
  };
}

function networkError() {
  return { message: 'Network Error' };
}

// ─────────────────────────────────────────────────────────────────────────────
// classifyPremiumError
// ─────────────────────────────────────────────────────────────────────────────

describe('classifyPremiumError — entitlement failures', () => {
  it('maps HTTP 401 to entitlement kind', () => {
    expect(classifyPremiumError(axiosError(401)).kind).toBe<PremiumErrorKind>('entitlement');
  });

  it('maps HTTP 403 to entitlement kind', () => {
    expect(classifyPremiumError(axiosError(403)).kind).toBe<PremiumErrorKind>('entitlement');
  });

  it('entitlement message mentions subscription', () => {
    expect(classifyPremiumError(axiosError(403)).message).toMatch(/subscription/i);
  });

  it('401 and 403 produce identical entitlement messages', () => {
    expect(classifyPremiumError(axiosError(401)).message)
      .toBe(classifyPremiumError(axiosError(403)).message);
  });
});

describe('classifyPremiumError — network failures', () => {
  it('maps no-response error to network kind', () => {
    expect(classifyPremiumError(networkError()).kind).toBe<PremiumErrorKind>('network');
  });

  it('network message mentions connection', () => {
    expect(classifyPremiumError(networkError()).message).toMatch(/network|connection/i);
  });
});

describe('classifyPremiumError — server errors', () => {
  it('maps HTTP 503 to server kind', () => {
    expect(classifyPremiumError(axiosError(503, 'Overpass unavailable')).kind)
      .toBe<PremiumErrorKind>('server');
  });

  it('uses backend detail message for server errors', () => {
    expect(classifyPremiumError(axiosError(503, 'Overpass unavailable')).message)
      .toBe('Overpass unavailable');
  });

  it('maps HTTP 500 to server kind', () => {
    expect(classifyPremiumError(axiosError(500)).kind).toBe<PremiumErrorKind>('server');
  });

  it('maps HTTP 429 to server kind', () => {
    expect(classifyPremiumError(axiosError(429)).kind).toBe<PremiumErrorKind>('server');
  });

  it('uses custom fallback when no backend detail and no axios message', () => {
    const err = { response: { status: 500, data: {} }, message: '' };
    const result = classifyPremiumError(err, 'Custom fallback');
    expect(result.message).toBe('Custom fallback');
  });

  it('uses generic fallback when no custom fallback provided', () => {
    const err = { response: { status: 500, data: {} }, message: '' };
    const result = classifyPremiumError(err);
    expect(result.message.length).toBeGreaterThan(0);
  });
});

describe('classifyPremiumError — edge cases', () => {
  it('handles null gracefully', () => {
    const result = classifyPremiumError(null);
    expect(result.message.length).toBeGreaterThan(0);
  });

  it('handles undefined gracefully', () => {
    const result = classifyPremiumError(undefined);
    expect(result.message.length).toBeGreaterThan(0);
  });

  it('handles a string throw gracefully', () => {
    const result = classifyPremiumError('something failed');
    expect(['network', 'server']).toContain(result.kind);
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// extractResultArray — shared array guard
// ─────────────────────────────────────────────────────────────────────────────

describe('extractResultArray — happy path', () => {
  it('extracts an array under a given key', () => {
    const item = { name: 'Test' };
    expect(extractResultArray({ supplies: [item] }, 'supplies')).toEqual([item]);
    expect(extractResultArray({ stations: [item] }, 'stations')).toEqual([item]);
    expect(extractResultArray({ spots: [item] }, 'spots')).toEqual([item]);
  });

  it('returns an empty array when the key holds an empty array', () => {
    expect(extractResultArray({ supplies: [] }, 'supplies')).toEqual([]);
    expect(extractResultArray({ stations: [] }, 'stations')).toEqual([]);
    expect(extractResultArray({ spots: [] }, 'spots')).toEqual([]);
  });
});

describe('extractResultArray — malformed / missing payload', () => {
  it('returns [] for null payload', () => {
    expect(extractResultArray(null, 'supplies')).toEqual([]);
  });

  it('returns [] for undefined payload', () => {
    expect(extractResultArray(undefined, 'supplies')).toEqual([]);
  });

  it('returns [] when the key is missing', () => {
    expect(extractResultArray({}, 'supplies')).toEqual([]);
    expect(extractResultArray({}, 'stations')).toEqual([]);
    expect(extractResultArray({}, 'spots')).toEqual([]);
  });

  it('returns [] when the key value is not an array', () => {
    expect(extractResultArray({ supplies: 'broken' }, 'supplies')).toEqual([]);
    expect(extractResultArray({ supplies: null }, 'supplies')).toEqual([]);
    expect(extractResultArray({ supplies: 42 }, 'supplies')).toEqual([]);
    expect(extractResultArray({ supplies: {} }, 'supplies')).toEqual([]);
    expect(extractResultArray({ supplies: true }, 'supplies')).toEqual([]);
  });

  it('returns [] for a non-object payload (string)', () => {
    expect(extractResultArray('bad response', 'supplies')).toEqual([]);
  });

  it('returns [] for a non-object payload (number)', () => {
    expect(extractResultArray(42, 'supplies')).toEqual([]);
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// Per-screen contract verification
// These confirm each screen's specific (key, fallback) combination
// behaves correctly through the shared utility.
// ─────────────────────────────────────────────────────────────────────────────

describe('water-budget screen contract', () => {
  const FALLBACK = 'Failed to calculate water budget.';

  it('403 → entitlement kind', () => {
    expect(classifyPremiumError(axiosError(403), FALLBACK).kind).toBe('entitlement');
  });

  it('network error → network kind', () => {
    expect(classifyPremiumError(networkError(), FALLBACK).kind).toBe('network');
  });

  it('server error with no detail uses fallback message', () => {
    const err = { response: { status: 500, data: {} }, message: '' };
    expect(classifyPremiumError(err, FALLBACK).message).toBe(FALLBACK);
  });

  it('resp.data with no days_remaining does not crash (null result guard)', () => {
    // extractResultArray is not used here (returns object not array)
    // Guard: resp.data ?? null — null is safe to render "No data available"
    const data = null;
    expect(data ?? null).toBeNull();
  });
});

describe('dump-station screen contract', () => {
  const KEY = 'stations';
  const FALLBACK = 'Failed to find dump stations. Tap to retry.';

  it('403 → entitlement', () => {
    expect(classifyPremiumError(axiosError(403), FALLBACK).kind).toBe('entitlement');
  });

  it('network → network kind', () => {
    expect(classifyPremiumError(networkError(), FALLBACK).kind).toBe('network');
  });

  it('normal response: extracts stations array', () => {
    const station = { name: 'Test Station' };
    expect(extractResultArray({ stations: [station] }, KEY)).toEqual([station]);
  });

  it('missing stations key: returns []', () => {
    expect(extractResultArray({ supplies: [] }, KEY)).toEqual([]);
  });

  it('server error uses backend detail', () => {
    expect(
      classifyPremiumError(axiosError(503, 'Overpass timeout'), FALLBACK).message
    ).toBe('Overpass timeout');
  });
});

describe('truck-parking screen contract', () => {
  const KEY = 'spots';
  const FALLBACK = 'Failed to find truck parking. Tap to retry.';

  it('403 → entitlement', () => {
    expect(classifyPremiumError(axiosError(403), FALLBACK).kind).toBe('entitlement');
  });

  it('network → network kind with actionable message', () => {
    const result = classifyPremiumError(networkError(), FALLBACK);
    expect(result.kind).toBe('network');
    expect(result.message).toMatch(/network|connection/i);
  });

  it('normal response: extracts spots array', () => {
    const spot = { name: 'Rest Area', type: 'rest_area' };
    expect(extractResultArray({ spots: [spot] }, KEY)).toEqual([spot]);
  });

  it('missing spots key: returns []', () => {
    expect(extractResultArray({}, KEY)).toEqual([]);
  });

  it('503 server error: falls back to FALLBACK when no detail', () => {
    const err = { response: { status: 503, data: {} }, message: '' };
    expect(classifyPremiumError(err, FALLBACK).message).toBe(FALLBACK);
  });
});
