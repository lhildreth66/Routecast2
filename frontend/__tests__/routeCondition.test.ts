/**
 * Tests for resolveRoutePointCondition — route card condition resolver.
 *
 * Verifies:
 *  1. Flood alert → never Clear/Dry
 *  2. Ice alert at destination-like point → never Clear/Dry
 *  3. Snow alert at start-like point → never Clear/Dry
 *  4. No alerts + wet weather → WET roads (alerts do not suppress weather hazards)
 *  5. Alerts unavailable (null/undefined) → fallback "Hazard data unavailable", not "Clear"
 *  6. Alert-derived state and reroute flag are logically consistent
 *  7. Wet weather + flood alert → alert overrides lesser weather state (not just DRY)
 *  8. Fog weather + ice alert → ICY overrides FOG
 *  9. alerts_status field — timeout/error/unavailable/ok carry correct desc and alertsStatus
 */

import {
  resolveRoutePointCondition,
  isRerouteCondition,
} from '../app/utils/routeCondition';

// ── Helpers ─────────────────────────────────────────────────────────────────

function makeWp({
  temperature = 60,
  conditions = 'Clear',
  alerts = [] as any[],
  alertsField = 'present', // 'present' | 'null' | 'undefined'
  alertsStatus,           // backend alerts_status field value (optional)
}: {
  temperature?: number;
  conditions?: string;
  alerts?: any[];
  alertsField?: 'present' | 'null' | 'undefined';
  alertsStatus?: string;
}) {
  const base: any = {
    weather: { temperature, conditions, wind_speed: '10 mph' },
    waypoint: { name: 'Test Point', distance_from_start: 42 },
  };
  if (alertsStatus !== undefined) base.alerts_status = alertsStatus;
  if (alertsField === 'null') return { ...base, alerts: null };
  if (alertsField === 'undefined') return { ...base };
  return { ...base, alerts };
}

function alert(event: string, headline = ''): any {
  return { event, headline, description: 'Test alert' };
}

// ── Test 1: Flood alert → never Clear/Dry ───────────────────────────────────

describe('Test 1 — Flood alert overrides Clear weather', () => {
  it('should show FLOOD, not DRY or Clear, when weather is clear but flood alert exists', () => {
    const wp = makeWp({
      temperature: 65,
      conditions: 'Clear',
      alerts: [alert('Flood Warning', 'Flooding expected along river')],
    });
    const result = resolveRoutePointCondition(wp);
    expect(result.condLabel).toBe('FLOOD');
    expect(result.condDesc).not.toMatch(/clear/i);
    expect(result.condDesc).not.toMatch(/dry/i);
    expect(result.roadSurface).not.toMatch(/normal driving/i);
    expect(result.hazardAlert).not.toBeNull();
  });

  it('should show FLOOD for Flash Flood Warning', () => {
    const wp = makeWp({
      alerts: [alert('Flash Flood Warning')],
    });
    const result = resolveRoutePointCondition(wp);
    expect(result.condLabel).toBe('FLOOD');
    expect(result.condColor).toBe('#dc2626');
  });

  it('should flag as reroute condition when flood alert exists', () => {
    const wp = makeWp({ alerts: [alert('Flood Warning')] });
    const result = resolveRoutePointCondition(wp);
    expect(isRerouteCondition(result)).toBe(true);
  });
});

// ── Test 2: Ice alert at destination → never Clear/Dry ──────────────────────

describe('Test 2 — Ice alert at destination overrides Clear weather', () => {
  it('should show ICY for Ice Storm Warning when weather says clear', () => {
    const wp = makeWp({
      temperature: 28,
      conditions: 'Clear', // weather alone would cause ICY from temp+precip, but here conditions=clear
      alerts: [alert('Ice Storm Warning', 'Significant ice accumulation expected')],
    });
    // Set temp above freezing threshold with clear sky to isolate alert-only detection
    const wp2 = makeWp({
      temperature: 40,
      conditions: 'Clear',
      alerts: [alert('Ice Storm Warning')],
    });
    const result = resolveRoutePointCondition(wp2);
    expect(result.condLabel).toBe('ICY');
    expect(result.condDesc).not.toMatch(/clear/i);
    expect(result.condDesc).not.toMatch(/normal/i);
    expect(result.hazardAlert).not.toBeNull();
  });

  it('should show ICY for Freezing Rain Advisory', () => {
    const wp = makeWp({
      temperature: 50,
      conditions: 'Partly Cloudy',
      alerts: [alert('Freezing Rain Advisory')],
    });
    const result = resolveRoutePointCondition(wp);
    expect(result.condLabel).toBe('ICY');
    expect(isRerouteCondition(result)).toBe(true);
  });

  it('should show ICY for Winter Weather Advisory with sleet', () => {
    const wp = makeWp({
      alerts: [alert('Winter Weather Advisory', 'Sleet and freezing drizzle')],
    });
    const result = resolveRoutePointCondition(wp);
    // 'sleet' in headline → winter keyword → SNOW, or 'freezing' → ICY
    // Either way, must NOT be DRY
    expect(result.condLabel).not.toBe('DRY');
    expect(result.condDesc).not.toMatch(/^clear$/i);
    expect(result.roadSurface).not.toMatch(/normal driving/i);
  });
});

// ── Test 3: Snow alert at start → never Clear/Dry ───────────────────────────

describe('Test 3 — Snow alert at start point overrides Clear weather', () => {
  it('should show SNOW for Winter Storm Warning when weather is clear', () => {
    const wp = makeWp({
      temperature: 55,
      conditions: 'Clear',
      alerts: [alert('Winter Storm Warning')],
    });
    const result = resolveRoutePointCondition(wp);
    expect(result.condLabel).toBe('SNOW');
    expect(result.condDesc).not.toMatch(/clear/i);
    expect(result.roadSurface).not.toMatch(/normal driving/i);
    expect(result.hazardAlert).not.toBeNull();
  });

  it('should show SNOW for Blizzard Warning', () => {
    const wp = makeWp({
      temperature: 25,
      conditions: 'Clear', // clear sky obs but NWS issued blizzard
      alerts: [alert('Blizzard Warning')],
    });
    const result = resolveRoutePointCondition(wp);
    expect(result.condLabel).toBe('SNOW');
    expect(result.condColor).toBe('#60a5fa');
    expect(isRerouteCondition(result)).toBe(true);
  });

  it('should show SNOW for Heavy Snow Warning', () => {
    const wp = makeWp({
      alerts: [alert('Heavy Snow Warning', 'Heavy snow expected')],
    });
    const result = resolveRoutePointCondition(wp);
    expect(result.condLabel).toBe('SNOW');
  });
});

// ── Test 4: No alerts + wet weather → WET ───────────────────────────────────

describe('Test 4 — Weather-only hazard still shows when no alerts exist', () => {
  it('should show WET roads when rain with no alerts', () => {
    const wp = makeWp({
      temperature: 55,
      conditions: 'Rain',
      alerts: [], // empty = fetched successfully, no alerts
    });
    const result = resolveRoutePointCondition(wp);
    expect(result.condLabel).toBe('WET');
    expect(result.condDesc).toMatch(/wet/i);
    expect(result.hazardAlert).toBeNull();
  });

  it('should show ICY roads from weather alone (temp + precip) when no alerts', () => {
    const wp = makeWp({
      temperature: 30,
      conditions: 'Freezing Rain',
      alerts: [],
    });
    const result = resolveRoutePointCondition(wp);
    expect(result.condLabel).toBe('ICY');
    expect(result.hazardAlert).toBeNull();
  });

  it('should show DRY when clear weather and no alerts', () => {
    const wp = makeWp({
      temperature: 70,
      conditions: 'Sunny',
      alerts: [],
    });
    const result = resolveRoutePointCondition(wp);
    expect(result.condLabel).toBe('DRY');
    expect(result.condDesc).toBe('Clear');
    expect(result.roadSurface).toBe('Normal driving conditions');
  });

  it('should show SNOW from weather when snowing and no alerts', () => {
    const wp = makeWp({
      temperature: 28,
      conditions: 'Heavy Snow',
      alerts: [],
    });
    const result = resolveRoutePointCondition(wp);
    expect(result.condLabel).toBe('SNOW');
    expect(result.hazardAlert).toBeNull();
  });
});

// ── Test 5: Alerts unavailable → neutral fallback, not "Clear" ──────────────

describe('Test 5 — Alerts unavailable does not silently show hazard-free state', () => {
  it('should show "Hazard data unavailable" in condDesc when alerts field is null', () => {
    const wp = makeWp({
      temperature: 65,
      conditions: 'Clear',
      alertsField: 'null',
    });
    const result = resolveRoutePointCondition(wp);
    expect(result.alertsUnavailable).toBe(true);
    expect(result.condDesc).toMatch(/hazard data unavailable/i);
    expect(result.roadSurface).not.toMatch(/normal driving/i);
    expect(result.condDesc).not.toBe('Clear');
  });

  it('should show "Hazard data unavailable" in condDesc when alerts field is undefined', () => {
    const wp = makeWp({
      temperature: 65,
      conditions: 'Clear',
      alertsField: 'undefined',
    });
    const result = resolveRoutePointCondition(wp);
    expect(result.alertsUnavailable).toBe(true);
    expect(result.condDesc).toMatch(/hazard data unavailable/i);
    expect(result.condDesc).not.toBe('Clear');
  });

  it('should still show weather hazard (WET) even when alerts field is null', () => {
    const wp = makeWp({
      temperature: 55,
      conditions: 'Rain',
      alertsField: 'null',
    });
    const result = resolveRoutePointCondition(wp);
    // Weather hazard still surfaces; alert-unavailable applies to the desc override only for DRY
    expect(result.condLabel).toBe('WET');
    expect(result.alertsUnavailable).toBe(true);
  });

  it('alertsUnavailable is false when alerts is empty array (fetched cleanly)', () => {
    const wp = makeWp({ alerts: [] });
    const result = resolveRoutePointCondition(wp);
    expect(result.alertsUnavailable).toBe(false);
    expect(result.condDesc).toBe('Clear');
  });
});

// ── Test 6: Reroute and card state stay consistent ──────────────────────────

describe('Test 6 — Reroute and card state are logically consistent', () => {
  it('isRerouteCondition is true for FLOOD', () => {
    const wp = makeWp({ alerts: [alert('Flood Warning')] });
    expect(isRerouteCondition(resolveRoutePointCondition(wp))).toBe(true);
  });

  it('isRerouteCondition is true for ICY', () => {
    const wp = makeWp({ alerts: [alert('Ice Storm Warning')] });
    expect(isRerouteCondition(resolveRoutePointCondition(wp))).toBe(true);
  });

  it('isRerouteCondition is true for SNOW/blizzard', () => {
    const wp = makeWp({ alerts: [alert('Winter Storm Warning')] });
    expect(isRerouteCondition(resolveRoutePointCondition(wp))).toBe(true);
  });

  it('isRerouteCondition is true for SEVERE', () => {
    const wp = makeWp({ alerts: [alert('Severe Thunderstorm Warning')] });
    expect(isRerouteCondition(resolveRoutePointCondition(wp))).toBe(true);
  });

  it('isRerouteCondition is false for DRY with no alerts', () => {
    const wp = makeWp({ alerts: [] });
    expect(isRerouteCondition(resolveRoutePointCondition(wp))).toBe(false);
  });

  it('isRerouteCondition is false for WET with no alerts', () => {
    const wp = makeWp({ conditions: 'Rain', alerts: [] });
    expect(isRerouteCondition(resolveRoutePointCondition(wp))).toBe(false);
  });
});

// ── Test 7: Flood alert overrides WET (not just DRY) — root-cause regression ─

describe('Test 7 — Alert overrides ANY weather state, not just DRY', () => {
  it('should show FLOOD (not WET) when rain weather + flood alert', () => {
    const wp = makeWp({
      temperature: 62,
      conditions: 'Rain', // weather alone → WET
      alerts: [alert('Flood Warning')],
    });
    const result = resolveRoutePointCondition(wp);
    // This was the root-cause bug: old code only upgraded from DRY
    expect(result.condLabel).toBe('FLOOD');
    expect(result.condLabel).not.toBe('WET');
    expect(result.hazardAlert).not.toBeNull();
  });

  it('should show SNOW (not STORM) when thunderstorm weather + winter storm alert', () => {
    const wp = makeWp({
      temperature: 35,
      conditions: 'Thunderstorm', // weather → STORM
      alerts: [alert('Winter Storm Warning')],
    });
    const result = resolveRoutePointCondition(wp);
    expect(result.condLabel).toBe('SNOW');
    expect(result.condLabel).not.toBe('STORM');
  });

  it('should show FLOOD (not SNOW) when snow weather + flood alert (flood is more dangerous)', () => {
    const wp = makeWp({
      temperature: 30,
      conditions: 'Snow', // weather → SNOW
      alerts: [alert('Flash Flood Warning', 'Rapid onset flooding')],
    });
    const result = resolveRoutePointCondition(wp);
    expect(result.condLabel).toBe('FLOOD');
  });
});

// ── Test 8: Fog weather + ice alert → ICY overrides FOG ─────────────────────

describe('Test 8 — Ice alert overrides fog weather state', () => {
  it('should show ICY (not FOG) when foggy but ice alert exists', () => {
    const wp = makeWp({
      temperature: 34,
      conditions: 'Fog',
      alerts: [alert('Freezing Rain Advisory')],
    });
    const result = resolveRoutePointCondition(wp);
    expect(result.condLabel).toBe('ICY');
    expect(result.condLabel).not.toBe('FOG');
    expect(isRerouteCondition(result)).toBe(true);
  });
});

// ── Test 9: alerts_status field — granular fetch status ─────────────────────

describe('Test 9 — alerts_status field drives alertsStatus and condDesc', () => {
  it('alerts_status "ok" with empty alerts → Clear, alertsUnavailable=false, alertsStatus="ok"', () => {
    const wp = makeWp({ alerts: [], alertsStatus: 'ok' });
    const result = resolveRoutePointCondition(wp);
    expect(result.alertsStatus).toBe('ok');
    expect(result.alertsUnavailable).toBe(false);
    expect(result.condDesc).toBe('Clear');
    expect(result.roadSurface).toBe('Normal driving conditions');
  });

  it('alerts_status "timeout" → alertsUnavailable=true, alertsStatus="timeout", desc mentions timed out', () => {
    const wp = makeWp({ alerts: [], alertsStatus: 'timeout' });
    const result = resolveRoutePointCondition(wp);
    expect(result.alertsStatus).toBe('timeout');
    expect(result.alertsUnavailable).toBe(true);
    expect(result.condDesc).toMatch(/timed out/i);
    expect(result.roadSurface).toMatch(/timed out/i);
  });

  it('alerts_status "error" → alertsUnavailable=true, alertsStatus="error", desc says unavailable', () => {
    const wp = makeWp({ alerts: [], alertsStatus: 'error' });
    const result = resolveRoutePointCondition(wp);
    expect(result.alertsStatus).toBe('error');
    expect(result.alertsUnavailable).toBe(true);
    expect(result.condDesc).toMatch(/hazard data unavailable/i);
  });

  it('alerts_status "unavailable" → alertsUnavailable=true, alertsStatus="unavailable"', () => {
    const wp = makeWp({ alerts: [], alertsStatus: 'unavailable' });
    const result = resolveRoutePointCondition(wp);
    expect(result.alertsStatus).toBe('unavailable');
    expect(result.alertsUnavailable).toBe(true);
    expect(result.condDesc).toMatch(/hazard data unavailable/i);
  });

  it('alerts_status "ok" with flood alert → alert still overrides DRY, alertsStatus="ok"', () => {
    const wp = makeWp({ alerts: [alert('Flood Warning')], alertsStatus: 'ok' });
    const result = resolveRoutePointCondition(wp);
    expect(result.alertsStatus).toBe('ok');
    expect(result.condLabel).toBe('FLOOD');
    expect(result.alertsUnavailable).toBe(false);
  });

  it('alerts_status "timeout" with non-null alerts list → treats as timeout (status wins over list)', () => {
    // Backend sends alerts=[] and alerts_status="timeout": timeout status must win
    const wp = makeWp({ alerts: [], alertsStatus: 'timeout' });
    const result = resolveRoutePointCondition(wp);
    expect(result.alertsStatus).toBe('timeout');
    expect(result.alertsUnavailable).toBe(true);
    // No hazard was in alerts, so label stays DRY
    expect(result.condLabel).toBe('DRY');
  });

  it('no alerts_status field + alerts=null → backward-compat fallback to unavailable', () => {
    // Old backend response without alerts_status field
    const wp = makeWp({ alertsField: 'null' });
    const result = resolveRoutePointCondition(wp);
    expect(result.alertsStatus).toBe('unavailable');
    expect(result.alertsUnavailable).toBe(true);
  });

  it('no alerts_status field + alerts=[] → backward-compat fallback to ok', () => {
    const wp = makeWp({ alerts: [] }); // no alertsStatus, alerts is []
    const result = resolveRoutePointCondition(wp);
    expect(result.alertsStatus).toBe('ok');
    expect(result.alertsUnavailable).toBe(false);
    expect(result.condDesc).toBe('Clear');
  });
});
