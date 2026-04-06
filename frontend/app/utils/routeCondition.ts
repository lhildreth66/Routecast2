/**
 * resolveRoutePointCondition — single source of truth for route card condition state.
 *
 * Priority order (mirrors backend derive_road_condition):
 *   1. NWS hazard alerts  → always wins, no matter what weather reports
 *   2. Weather-derived state (temp + conditions string)
 *   3. Fallback when alerts field is null/undefined (data unavailable)
 *
 * This eliminates the contradiction where the reroute banner fires (alert-aware)
 * while route cards still show "Clear / Dry / Normal" (weather-only).
 */

export interface ConditionResult {
  condIcon: string;
  condLabel: string;
  condColor: string;
  condDesc: string;
  roadSurface: string;
  /** The first matching hazard alert object, or null if none. */
  hazardAlert: any | null;
  /**
   * True when wp.alerts is null or undefined — meaning the backend did not
   * attach alert data to this waypoint at all. Distinct from [] (fetched, clean).
   */
  alertsUnavailable: boolean;
}

/** Keywords that indicate a hazard-level NWS event in event or headline text. */
const HAZARD_KEYWORDS = [
  'flood',
  'flash flood',
  'ice',
  'icy',
  'ice storm',
  'freezing',
  'winter storm',
  'winter weather',
  'blizzard',
  'tornado',
  'severe thunderstorm',
  'severe',
  'sleet',
  'hail',
  'high wind',
  'dust storm',
  'snow',
  'winter',
];

function matchesHazardKeyword(text: string): boolean {
  const lower = text.toLowerCase();
  return HAZARD_KEYWORDS.some((kw) => lower.includes(kw));
}

/**
 * Resolve the display state for a single route waypoint.
 * Pass the raw waypoint object as received from the backend RouteResponse.
 */
export function resolveRoutePointCondition(wp: any): ConditionResult {
  // ── Detect missing alerts field ────────────────────────────────────────────
  const alertsUnavailable = wp.alerts === undefined || wp.alerts === null;
  const waypointAlerts: any[] = alertsUnavailable ? [] : (wp.alerts as any[]);

  // ── Step 1: Derive weather-based state ────────────────────────────────────
  const temp: number = wp.weather?.temperature ?? 50;
  const conditions: string = (wp.weather?.conditions ?? '').toLowerCase();

  let condIcon = '✓';
  let condLabel = 'DRY';
  let condColor = '#22c55e';
  let condDesc = alertsUnavailable ? 'Hazard data unavailable' : 'Clear';
  let roadSurface = alertsUnavailable
    ? 'Alert data could not be loaded — drive with caution'
    : 'Normal driving conditions';

  if (
    temp <= 32 &&
    (conditions.includes('rain') ||
      conditions.includes('freezing') ||
      conditions.includes('drizzle'))
  ) {
    condIcon = '🧊';
    condLabel = 'ICY';
    condColor = '#ef4444';
    condDesc = 'Black ice likely';
    roadSurface = `${temp}°F - Reduce speed significantly`;
  } else if (temp <= 32 && conditions.includes('snow')) {
    condIcon = '❄️';
    condLabel = 'SNOW';
    condColor = '#60a5fa';
    condDesc = 'Snow-covered';
    roadSurface = `${temp}°F - Use caution`;
  } else if (temp > 32 && temp <= 40 && conditions.includes('snow')) {
    condIcon = '🌨️';
    condLabel = 'SLUSH';
    condColor = '#f59e0b';
    condDesc = 'Slushy';
    roadSurface = `${temp}°F - Reduced traction`;
  } else if (conditions.includes('fog') || conditions.includes('mist')) {
    condIcon = '🌫️';
    condLabel = 'FOG';
    condColor = '#9ca3af';
    condDesc = 'Low visibility';
    roadSurface = 'Use low beams';
  } else if (
    conditions.includes('rain') ||
    conditions.includes('shower') ||
    conditions.includes('drizzle')
  ) {
    condIcon = '💧';
    condLabel = 'WET';
    condColor = '#3b82f6';
    condDesc = 'Wet roads';
    roadSurface = 'Watch for hydroplaning';
  } else if (conditions.includes('thunder') || conditions.includes('storm')) {
    condIcon = '⛈️';
    condLabel = 'STORM';
    condColor = '#7c3aed';
    condDesc = 'Storm conditions';
    roadSurface = 'Heavy rain possible';
  }

  // ── Step 2: Find the first hazard-level NWS alert ─────────────────────────
  const hazardAlert: any | null =
    waypointAlerts.find((a: any) => {
      const combined = `${a.event ?? ''} ${a.headline ?? ''}`;
      return matchesHazardKeyword(combined);
    }) ?? null;

  // ── Step 3: Alert ALWAYS overrides weather — no condLabel guard ────────────
  // This is the root-cause fix: the previous code only upgraded from DRY.
  // Now alerts override ANY weather-derived label.
  if (hazardAlert !== null) {
    const ev = (hazardAlert.event ?? '').toLowerCase();

    if (ev.includes('flood')) {
      condIcon = '🌊';
      condLabel = 'FLOOD';
      condColor = '#dc2626';
      condDesc = 'Flooding reported';
      roadSurface = hazardAlert.event ?? 'NWS Flood Alert active';
    } else if (
      ev.includes('ice') ||
      ev.includes('icy') ||
      ev.includes('freezing') ||
      ev.includes('sleet') ||
      ev.includes('ice storm')
    ) {
      condIcon = '🧊';
      condLabel = 'ICY';
      condColor = '#ef4444';
      condDesc = 'Ice conditions reported';
      roadSurface = hazardAlert.event ?? 'NWS Ice Alert active';
    } else if (
      ev.includes('snow') ||
      ev.includes('blizzard') ||
      ev.includes('winter storm') ||
      ev.includes('winter weather') ||
      ev.includes('winter')
    ) {
      condIcon = '❄️';
      condLabel = 'SNOW';
      condColor = '#60a5fa';
      condDesc = 'Winter conditions reported';
      roadSurface = hazardAlert.event ?? 'NWS Winter Alert active';
    } else if (ev.includes('tornado') || ev.includes('severe')) {
      condIcon = '🌪️';
      condLabel = 'SEVERE';
      condColor = '#7c3aed';
      condDesc = 'Severe weather alert';
      roadSurface = hazardAlert.event ?? 'NWS Severe Alert active';
    } else if (ev.includes('high wind') || ev.includes('dust storm')) {
      condIcon = '💨';
      condLabel = 'WIND';
      condColor = '#f59e0b';
      condDesc = 'Hazardous wind alert';
      roadSurface = hazardAlert.event ?? 'NWS Wind Alert active';
    } else {
      // Generic hazard match (hail, etc.)
      condIcon = '⚠️';
      condLabel = 'ALERT';
      condColor = '#f59e0b';
      condDesc = 'Weather alert active';
      roadSurface = hazardAlert.event ?? 'NWS Alert active';
    }
  }

  return {
    condIcon,
    condLabel,
    condColor,
    condDesc,
    roadSurface,
    hazardAlert,
    alertsUnavailable,
  };
}

/**
 * Returns true when a ConditionResult from resolveRoutePointCondition
 * could trigger a reroute recommendation. Mirrors backend severity >= 3 rule.
 * Used to keep card state and reroute banner logically consistent.
 */
export function isRerouteCondition(result: ConditionResult): boolean {
  return ['FLOOD', 'ICY', 'SNOW', 'SEVERE', 'WIND', 'ALERT'].includes(
    result.condLabel
  );
}
