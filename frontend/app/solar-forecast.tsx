/**
 * Solar Forecast – RV Solar + Battery Calculator
 *
 * Step-by-step calculator:
 *   1. Location (manual search / GPS)
 *   2. Battery bank
 *   3. Solar array
 *   4. Daily appliance usage
 *   5. Results + recommendations
 *
 * Rules:
 *  - NO auto-GPS on mount. GPS only on "Use My Location" tap.
 *  - Uses shared useLocationSearch / LocationSearchBox pattern.
 *  - All errors shown as banners, never thrown to React.
 *  - Backend /solar-forecast used to derive peak sun hours;
 *    falls back to local latitude-based math if call fails.
 *  - Appliance editable fields use STRING state (not number) to avoid
 *    controlled-input cursor-jump on web.
 *  - No Switch component (unreliable on RN Web); uses TouchableOpacity toggle.
 */

import React, { useState, useMemo, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  TextInput,
  ActivityIndicator,
  ScrollView,
} from 'react-native';
import axios from 'axios';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { buildUrl } from '../lib/apiConfig';
import { useLocationSearch } from '../lib/useLocationSearch';
import LocationSearchBox from '../lib/components/LocationSearchBox';

// ─── Types ────────────────────────────────────────────────────────────────────

type BattType = 'lithium' | 'agm' | 'gel' | 'lead';

/** All editable fields kept as strings to avoid controlled-input issues on web */
interface Appliance {
  id: string;
  label: string;
  icon: string;
  wattStr: string;
  hourStr: string;
  minStr: string;
  enabled: boolean;
}

// ─── Constants ────────────────────────────────────────────────────────────────

const ACCENT = '#eab308';

const DEFAULT_DOD: Record<BattType, number> = {
  lithium: 0.85,
  agm: 0.50,
  gel: 0.50,
  lead: 0.50,
};

const DOD_PRESETS: Record<BattType, number[]> = {
  lithium: [0.80, 0.85, 0.90],
  agm:     [0.40, 0.50, 0.60],
  gel:     [0.40, 0.50, 0.60],
  lead:    [0.40, 0.50, 0.60],
};

const INVERTER_EFF = 0.92;
const SYSTEM_LOSS  = 0.77;   // wiring + MPPT + temp + dust

const MK = (id: string, label: string, icon: string,
            w: number, h: number, m: number, on: boolean): Appliance => ({
  id, label, icon,
  wattStr: String(w), hourStr: String(h), minStr: String(m),
  enabled: on,
});

const DEFAULT_APPLIANCES: Appliance[] = [
  MK('fridge',    '12V Compressor Fridge', '🧊',   50, 24,  0, true),
  MK('lights',    'LED Lights',            '💡',   20,  5,  0, true),
  MK('pump',      'Water Pump',            '🚿',   60,  0, 30, true),
  MK('phone',     'Phone Charging',        '📱',   15,  2,  0, true),
  MK('fan',       'Roof Vent Fan',         '🌀',   25,  4,  0, false),
  MK('cpap',      'CPAP Machine',          '💨',   55,  8,  0, false),
  MK('laptop',    'Laptop / Tablet',       '💻',   45,  2,  0, false),
  MK('tv',        'TV / Streaming',        '📺',   60,  2,  0, false),
  MK('microwave', 'Microwave',             '📡', 1000,  0, 10, false),
  MK('coffee',    'Coffee Maker',          '☕',  900,  0,  6, false),
  MK('airfryer',  'Air Fryer',             '🍳', 1500,  0, 15, false),
  MK('other',     'Other / Custom',        '🔌',  100,  1,  0, false),
];

// ─── Local peak-sun-hours estimate (mirrors backend solar geometry) ────────────

function localPeakSunHours(lat: number): number {
  const now   = new Date();
  const start = new Date(now.getFullYear(), 0, 0);
  const doy   = Math.floor((now.getTime() - start.getTime()) / 864e5);
  const decl  = 23.44 * Math.sin((2 * Math.PI * (doy - 81)) / 365);
  const lr    = (lat  * Math.PI) / 180;
  const dr    = (decl * Math.PI) / 180;
  const sinE  = Math.sin(lr) * Math.sin(dr) + Math.cos(lr) * Math.cos(dr);
  const elev  = (Math.asin(Math.max(-1, Math.min(1, sinE))) * 180) / Math.PI;
  if (elev <= 0) return 1;
  const cosH  = -Math.tan(lr) * Math.tan(dr);
  const ha    = Math.acos(Math.max(-1, Math.min(1, cosH)));
  const dayLen = (2 * 24 * ha) / (2 * Math.PI);
  return Math.max(1, Math.min(8, 5.5 * (elev / 90) ** 0.75 * (dayLen / 12)));
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

const num  = (s: string, fallback = 0) => { const n = parseFloat(s); return isFinite(n) ? Math.max(0, n) : fallback; };
const fmt  = (n: number, dec = 0)      => (isFinite(n) && n >= 0 ? n.toFixed(dec) : '—');
const fmtN = (n: number, dec = 0)      => (isFinite(n) ? n.toFixed(dec) : '—');

const appWh = (a: Appliance) => num(a.wattStr) * (num(a.hourStr) + num(a.minStr) / 60);

const pctColor = (ratio: number) =>
  ratio >= 1 ? '#4ade80' : ratio >= 0.7 ? '#facc15' : '#f87171';

// ─── Toggle sub-component (replaces Switch — more reliable on RN Web) ─────────

function Toggle({ value, onToggle }: { value: boolean; onToggle: () => void }) {
  return (
    <TouchableOpacity
      onPress={onToggle}
      activeOpacity={0.8}
      style={[styles.toggleTrack, value && styles.toggleTrackOn]}
      hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
    >
      <View style={[styles.toggleThumb, value && styles.toggleThumbOn]} />
    </TouchableOpacity>
  );
}

// ─── Section header ───────────────────────────────────────────────────────────

function SectionHeader({ n, label, icon }: { n: number; label: string; icon: string }) {
  return (
    <View style={styles.sectionHeader}>
      <View style={styles.stepBadge}>
        <Text style={styles.stepBadgeText}>{n}</Text>
      </View>
      <Text style={styles.sectionIcon}>{icon}</Text>
      <Text style={styles.sectionLabel}>{label}</Text>
    </View>
  );
}

// ─── Stepper (+/–) ────────────────────────────────────────────────────────────

function Stepper({ value, onChange, min = 1, max = 99 }: {
  value: string; onChange: (v: string) => void; min?: number; max?: number;
}) {
  const n = parseInt(value) || 1;
  return (
    <View style={styles.stepper}>
      <TouchableOpacity style={styles.stepBtn} onPress={() => onChange(String(Math.max(min, n - 1)))} disabled={n <= min}>
        <Ionicons name="remove" size={16} color={n <= min ? '#52525b' : '#e4e4e7'} />
      </TouchableOpacity>
      <Text style={styles.stepValue}>{n}</Text>
      <TouchableOpacity style={styles.stepBtn} onPress={() => onChange(String(Math.min(max, n + 1)))} disabled={n >= max}>
        <Ionicons name="add" size={16} color={n >= max ? '#52525b' : '#e4e4e7'} />
      </TouchableOpacity>
    </View>
  );
}

// ─── Main screen ──────────────────────────────────────────────────────────────

export default function SolarForecastScreen() {
  const router = useRouter();

  // ── Location (no auto-GPS on mount) ──────────────────────────────────────
  const {
    lat, lon, locationLabel, locationLoading,
    locationQuery, suggestions, showSuggestions,
    handleLocationQueryChange, selectSuggestion,
    clearManualLocation, triggerGps, setShowSuggestions,
  } = useLocationSearch('solarForecastLoc');

  // ── Battery bank ─────────────────────────────────────────────────────────
  const [battType,    setBattType]    = useState<BattType>('lithium');
  const [numBatt,     setNumBatt]     = useState('2');
  const [ahPerBatt,   setAhPerBatt]   = useState('100');
  const [voltage,     setVoltage]     = useState<12 | 24>(12);
  const [dod,         setDod]         = useState<number>(DEFAULT_DOD['lithium']);

  // ── Solar array ───────────────────────────────────────────────────────────
  const [panelWatts, setPanelWatts] = useState('200');
  const [numPanels,  setNumPanels]  = useState('2');

  // ── Appliances ────────────────────────────────────────────────────────────
  const [appliances, setAppliances] = useState<Appliance[]>(DEFAULT_APPLIANCES);

  // ── Results ───────────────────────────────────────────────────────────────
  const [showResults,  setShowResults]  = useState(false);
  const [calculating,  setCalculating]  = useState(false);
  const [peakSunHours, setPeakSunHours] = useState<number | null>(null);
  const [usedFallback, setUsedFallback] = useState(false);
  const [apiError,     setApiError]     = useState('');
  const [showAssumptions, setShowAssumptions] = useState(false);

  // When battery type changes, reset DoD to its default
  const selectBattType = (bt: BattType) => {
    setBattType(bt);
    setDod(DEFAULT_DOD[bt]);
  };

  // ── Computed values ───────────────────────────────────────────────────────

  const totalBattWh = useMemo(
    () => (parseInt(numBatt) || 0) * (num(ahPerBatt)) * voltage,
    [numBatt, ahPerBatt, voltage],
  );

  const usableBattWh = useMemo(
    () => totalBattWh * dod * INVERTER_EFF,
    [totalBattWh, dod],
  );

  const usableBattAh = voltage > 0 ? usableBattWh / voltage : 0;

  // Capacity after DoD only, before inverter losses — for breakdown display
  const preinvBattWh = useMemo(() => totalBattWh * dod, [totalBattWh, dod]);
  const preinvBattAh = voltage > 0 ? preinvBattWh / voltage : 0;

  const arrayWatts = useMemo(
    () => (parseInt(panelWatts) || 0) * (parseInt(numPanels) || 0),
    [panelWatts, numPanels],
  );

  const dailyUsageWh = useMemo(
    () => appliances.filter(a => a.enabled).reduce((s, a) => s + appWh(a), 0),
    [appliances],
  );

  const dailyUsageAh = voltage > 0 ? dailyUsageWh / voltage : 0;

  // Peak sun hours: backend value (clamped 1–8); local estimate; or 4.5 default
  const psh = useMemo(() => {
    if (peakSunHours !== null) return peakSunHours;
    if (lat) return Math.min(8, Math.max(1, localPeakSunHours(parseFloat(lat))));
    return 4.5;
  }, [peakSunHours, lat]);

  const solarWhDay    = arrayWatts * psh * SYSTEM_LOSS;
  const batteryDays   = dailyUsageWh > 0 ? usableBattWh / dailyUsageWh : Infinity;
  const batteryHours  = batteryDays * 24;
  const netWh         = solarWhDay - dailyUsageWh;
  const coverageRatio = dailyUsageWh > 0 ? solarWhDay / dailyUsageWh : 1;

  const panelWattsNum  = parseInt(panelWatts) || 200;
  const ahPerBattNum   = num(ahPerBatt) || 100;

  const panelsNeeded =
    dailyUsageWh > 0
      ? Math.ceil(dailyUsageWh / Math.max(0.01, panelWattsNum * psh * SYSTEM_LOSS))
      : 0;

  const batt2DaysNeeded =
    dailyUsageWh > 0
      ? Math.ceil((dailyUsageWh * 2) / Math.max(0.01, ahPerBattNum * voltage * dod * INVERTER_EFF))
      : 0;

  const extraWattsNeeded = netWh < 0
    ? Math.ceil(-netWh / (psh * SYSTEM_LOSS))
    : 0;

  // ── Appliance handlers ────────────────────────────────────────────────────

  const toggleAppliance = useCallback((id: string) =>
    setAppliances(prev => prev.map(a => a.id === id ? { ...a, enabled: !a.enabled } : a)), []);

  const updateAppliance = useCallback((id: string, field: 'wattStr' | 'hourStr' | 'minStr', val: string) =>
    setAppliances(prev => prev.map(a => a.id === id ? { ...a, [field]: val } : a)), []);

  // ── Calculate ─────────────────────────────────────────────────────────────

  const calculate = async () => {
    setShowResults(true);
    setCalculating(true);
    setApiError('');

    if (!lat || !lon) {
      setPeakSunHours(4.5);
      setUsedFallback(true);
      setCalculating(false);
      return;
    }

    try {
      const today = new Date().toISOString().split('T')[0];
      // 1000 W reference panel, no shade, no cloud → daily_wh[0] / 1000 = PSH
      const resp = await axios.post(buildUrl('solar-forecast'), {
        lat: parseFloat(lat),
        lon: parseFloat(lon),
        date_range: [today],
        panel_watts: 1000,
        shade_pct: 0,
        cloud_cover: [0],
      });

      const data = resp.data as Record<string, unknown>;

      // Prefer explicit peak_sun_hours field; fall back to derivation
      let derived: number | null = null;
      if (typeof data?.peak_sun_hours === 'number' && isFinite(data.peak_sun_hours as number)) {
        derived = data.peak_sun_hours as number;
      } else if (
        Array.isArray(data?.daily_wh) &&
        (data.daily_wh as unknown[]).length > 0 &&
        typeof (data.daily_wh as unknown[])[0] === 'number' &&
        isFinite((data.daily_wh as number[])[0])
      ) {
        derived = (data.daily_wh as number[])[0] / 1000;
      }

      if (derived === null || !isFinite(derived) || derived < 0.5 || derived > 12) {
        const fb = localPeakSunHours(parseFloat(lat));
        setPeakSunHours(Math.min(8, Math.max(1, fb)));
        setUsedFallback(true);
        setApiError('Server returned unexpected sun-hours value — using local estimate.');
        return;
      }

      const clamped = Math.min(8, Math.max(1, derived));
      if (clamped !== derived) {
        setApiError(`Sun hours (${derived.toFixed(1)} hr) clamped to ${clamped.toFixed(1)} hr.`);
      }
      setPeakSunHours(clamped);
      setUsedFallback(false);
    } catch (err: unknown) {
      const fb = localPeakSunHours(parseFloat(lat));
      setPeakSunHours(Math.min(8, Math.max(1, fb)));
      setUsedFallback(true);
      let detail = 'Solar API unavailable — using local estimate.';
      if (err && typeof err === 'object') {
        const e = err as Record<string, unknown>;
        const rd = (e?.response as Record<string, unknown>)?.data as Record<string, unknown> | undefined;
        const rdDetail = rd?.detail;
        if (typeof rdDetail === 'string') detail = rdDetail;
        else if (rdDetail !== undefined) detail = `API error — using local estimate.`;
        else if (typeof e?.message === 'string') detail = e.message as string;
      } else if (typeof err === 'string') {
        detail = err;
      }
      setApiError(detail);
    } finally {
      setCalculating(false);
    }
  };

  // ─── Render ───────────────────────────────────────────────────────────────

  return (
    <SafeAreaView style={styles.container}>
      <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
        <Ionicons name="arrow-back" size={24} color="#fff" />
        <Text style={styles.backText}>Back</Text>
      </TouchableOpacity>

      <ScrollView style={styles.scroll} keyboardShouldPersistTaps="handled">

        {/* Title */}
        <View style={styles.titleCard}>
          <Text style={styles.titleEmoji}>{'☀️'}</Text>
          <View style={{ flex: 1 }}>
            <Text style={styles.title}>RV Solar + Battery Calculator</Text>
            <Text style={styles.subtitle}>Estimate off-grid runtime, solar coverage {'&'} sizing</Text>
          </View>
        </View>

        {/* ── Step 1: Location ─────────────────────────────────────────── */}
        <View style={styles.section}>
          <SectionHeader n={1} label="Location" icon="📍" />
          <LocationSearchBox
            lat={lat}
            lon={lon}
            locationLabel={locationLabel}
            locationLoading={locationLoading}
            locationQuery={locationQuery}
            suggestions={suggestions}
            showSuggestions={showSuggestions}
            handleLocationQueryChange={handleLocationQueryChange}
            selectSuggestion={selectSuggestion}
            clearManualLocation={clearManualLocation}
            triggerGps={triggerGps}
            setShowSuggestions={setShowSuggestions}
            accentColor={ACCENT}
          />
          {locationLabel ? (
            <View style={styles.locationBadge}>
              <Ionicons name="location" size={13} color={ACCENT} />
              <Text style={styles.locationBadgeText}>{locationLabel}</Text>
            </View>
          ) : (
            <Text style={styles.hint}>
              {lat ? `Coordinates: ${parseFloat(lat).toFixed(4)}, ${parseFloat(lon).toFixed(4)}` : 'Search a city or tap "Use My Location" for accurate sun hours.'}
            </Text>
          )}
        </View>

        {/* ── Step 2: Battery Bank ─────────────────────────────────────── */}
        <View style={styles.section}>
          <SectionHeader n={2} label="Battery Bank" icon="🔋" />

          <Text style={styles.fieldLabel}>Battery type</Text>
          <View style={styles.chipRow}>
            {(['lithium', 'agm', 'gel', 'lead'] as BattType[]).map(bt => (
              <TouchableOpacity key={bt} style={[styles.chip, battType === bt && styles.chipActive]}
                onPress={() => selectBattType(bt)}>
                <Text style={[styles.chipText, battType === bt && styles.chipTextActive]}>
                  {bt === 'lithium' ? '⚡ Lithium' : bt === 'agm' ? 'AGM' : bt === 'gel' ? 'Gel' : 'Lead Acid'}
                </Text>
              </TouchableOpacity>
            ))}
          </View>

          <Text style={styles.fieldLabel}>System voltage</Text>
          <View style={styles.chipRow}>
            {([12, 24] as const).map(v => (
              <TouchableOpacity key={v} style={[styles.chip, voltage === v && styles.chipActive]}
                onPress={() => setVoltage(v)}>
                <Text style={[styles.chipText, voltage === v && styles.chipTextActive]}>{v}V</Text>
              </TouchableOpacity>
            ))}
          </View>

          <View style={styles.rowGrid}>
            <View style={styles.halfCol}>
              <Text style={styles.fieldLabel}>Batteries</Text>
              <Stepper value={numBatt} onChange={setNumBatt} />
            </View>
            <View style={styles.halfCol}>
              <Text style={styles.fieldLabel}>Ah each</Text>
              <TextInput style={styles.input} value={ahPerBatt} onChangeText={setAhPerBatt}
                keyboardType="numeric" placeholder="100" placeholderTextColor="#6b7280" />
            </View>
          </View>

          <Text style={styles.fieldLabel}>
            Depth of discharge — DoD ({(dod * 100).toFixed(0)}%)
          </Text>
          <View style={styles.chipRow}>
            {DOD_PRESETS[battType].map(p => (
              <TouchableOpacity key={p} style={[styles.chip, dod === p && styles.chipActive]}
                onPress={() => setDod(p)}>
                <Text style={[styles.chipText, dod === p && styles.chipTextActive]}>{(p * 100).toFixed(0)}%</Text>
              </TouchableOpacity>
            ))}
          </View>
          <Text style={styles.hint}>
            {battType === 'lithium'
              ? 'Lithium: safe to discharge to 10–20% SOC.'
              : 'Lead-based: discharge deeper than 50% shortens cycle life.'}
          </Text>

          {totalBattWh > 0 && (
            <View style={styles.summaryChip}>
              <Text style={styles.summaryText}>
                Total: {fmt(totalBattWh)} Wh
                {'  ·  '}
                After {(dod * 100).toFixed(0)}% DoD: {fmt(preinvBattWh)} Wh / {fmt(preinvBattAh, 1)} Ah
                {'  ·  '}
                Effective AC: {fmt(usableBattWh)} Wh
              </Text>
            </View>
          )}
        </View>

        {/* ── Step 3: Solar Array ──────────────────────────────────────── */}
        <View style={styles.section}>
          <SectionHeader n={3} label="Solar Array" icon="🌞" />
          <View style={styles.rowGrid}>
            <View style={styles.halfCol}>
              <Text style={styles.fieldLabel}>Watts / panel</Text>
              <TextInput style={styles.input} value={panelWatts} onChangeText={setPanelWatts}
                keyboardType="numeric" placeholder="200" placeholderTextColor="#6b7280" />
            </View>
            <View style={styles.halfCol}>
              <Text style={styles.fieldLabel}>Panels</Text>
              <Stepper value={numPanels} onChange={setNumPanels} />
            </View>
          </View>
          {arrayWatts > 0 && (
            <View style={styles.summaryChip}>
              <Text style={styles.summaryText}>
                Array: {arrayWatts} W ({numPanels} {'\u00d7'} {panelWatts} W)
              </Text>
            </View>
          )}
        </View>

        {/* ── Step 4: Appliance Usage ──────────────────────────────────── */}
        <View style={styles.section}>
          <SectionHeader n={4} label="Daily Usage" icon="🔌" />
          <View style={styles.appHeader}>
            <Text style={styles.appHeaderCol}>Appliance</Text>
            <Text style={styles.appHeaderSmall}>W</Text>
            <Text style={styles.appHeaderSmall}>h</Text>
            <Text style={styles.appHeaderSmall}>min</Text>
            <Text style={styles.appHeaderWh}>Wh/day</Text>
          </View>

          {appliances.map(a => {
            const wh = appWh(a);
            return (
              <View key={a.id} style={[styles.appRow, !a.enabled && styles.appRowOff]}>
                {/* Toggle + label */}
                <View style={styles.appRowLeft}>
                  <Toggle value={a.enabled} onToggle={() => toggleAppliance(a.id)} />
                  <Text style={[styles.appLabel, !a.enabled && styles.appLabelOff]} numberOfLines={1}>
                    {a.icon} {a.label}
                  </Text>
                </View>
                {/* Editable fields — always rendered so layout doesn't shift */}
                <TextInput
                  style={[styles.appInput, !a.enabled && styles.appInputOff]}
                  value={a.wattStr}
                  onChangeText={v => updateAppliance(a.id, 'wattStr', v)}
                  keyboardType="numeric"
                  editable={a.enabled}
                />
                <TextInput
                  style={[styles.appInput, !a.enabled && styles.appInputOff]}
                  value={a.hourStr}
                  onChangeText={v => updateAppliance(a.id, 'hourStr', v)}
                  keyboardType="numeric"
                  editable={a.enabled}
                />
                <TextInput
                  style={[styles.appInput, !a.enabled && styles.appInputOff]}
                  value={a.minStr}
                  onChangeText={v => updateAppliance(a.id, 'minStr', v)}
                  keyboardType="numeric"
                  editable={a.enabled}
                />
                <Text style={[styles.appWh, !a.enabled && { color: '#52525b' }]}>
                  {a.enabled ? fmt(wh) : '—'}
                </Text>
              </View>
            );
          })}

          {dailyUsageWh > 0 && (
            <View style={[styles.summaryChip, { marginTop: 12 }]}>
              <Text style={styles.summaryText}>
                Daily load: {fmt(dailyUsageWh)} Wh/day {'\u00b7'} {fmt(dailyUsageAh, 1)} Ah/day @ {voltage}V
              </Text>
            </View>
          )}
        </View>

        {/* ── Calculate button ─────────────────────────────────────────── */}
        <TouchableOpacity
          style={[styles.calcBtn, calculating && styles.calcBtnDisabled]}
          onPress={calculate}
          disabled={calculating}
        >
          {calculating ? (
            <ActivityIndicator color="#1a1a1a" />
          ) : (
            <>
              <Ionicons name="calculator" size={20} color="#1a1a1a" />
              <Text style={styles.calcBtnText}>Calculate</Text>
            </>
          )}
        </TouchableOpacity>

        {/* ── Step 5: Results ──────────────────────────────────────────── */}
        {showResults && !calculating && (
          <View style={styles.section}>
            <SectionHeader n={5} label="Results" icon="📊" />

            {/* Location context banner */}
            {lat && (
              <View style={styles.locContext}>
                <Ionicons name="location" size={13} color={ACCENT} />
                <Text style={styles.locContextText}>
                  {locationLabel
                    ? locationLabel
                    : `${parseFloat(lat).toFixed(3)}, ${parseFloat(lon).toFixed(3)}`}
                  {' '}{'\u2014'} {psh.toFixed(1)} peak sun hrs
                  {usedFallback ? ' (estimated)' : ''}
                </Text>
              </View>
            )}

            {/* API notice */}
            {(usedFallback || apiError) && (
              <View style={styles.noticeBanner}>
                <Ionicons name="information-circle" size={16} color="#facc15" />
                <Text style={styles.noticeText}>
                  {apiError
                    ? apiError
                    : !lat
                    ? 'No location set — using 4.5 peak sun hrs default. Add a location for better accuracy.'
                    : 'Using locally estimated sun hours (latitude + day-of-year).'}
                </Text>
              </View>
            )}

            {/* 4-metric grid */}
            <View style={styles.metricsGrid}>
              <View style={styles.metricCard}>
                <Text style={styles.metricLabel}>Daily Usage</Text>
                <Text style={styles.metricValue}>{fmt(dailyUsageWh)}</Text>
                <Text style={styles.metricUnit}>Wh/day</Text>
                <Text style={styles.metricSub}>{fmt(dailyUsageAh, 1)} Ah/day</Text>
              </View>
              <View style={styles.metricCard}>
                <Text style={styles.metricLabel}>Usable Battery</Text>
                <Text style={styles.metricValue}>{fmt(usableBattWh)}</Text>
                <Text style={styles.metricUnit}>Wh</Text>
                <Text style={styles.metricSub}>{fmt(usableBattAh, 1)} Ah @ {voltage}V</Text>
              </View>
              <View style={styles.metricCard}>
                <Text style={styles.metricLabel}>Battery Runtime</Text>
                <Text style={[styles.metricValue,
                  { color: batteryDays >= 2 ? '#4ade80' : batteryDays >= 1 ? '#facc15' : '#f87171' }]}>
                  {isFinite(batteryDays) ? fmt(batteryDays, 1) : '\u221e'}
                </Text>
                <Text style={styles.metricUnit}>days (no sun)</Text>
                <Text style={styles.metricSub}>
                  {isFinite(batteryHours) ? `${fmt(batteryHours, 0)} hrs` : ''}
                </Text>
              </View>
              <View style={styles.metricCard}>
                <Text style={styles.metricLabel}>Solar Production</Text>
                <Text style={[styles.metricValue, { color: ACCENT }]}>{fmt(solarWhDay)}</Text>
                <Text style={styles.metricUnit}>Wh/day</Text>
                <Text style={styles.metricSub}>{psh.toFixed(1)} peak sun hrs</Text>
              </View>
            </View>

            {/* Battery capacity breakdown */}
            {totalBattWh > 0 && (
              <View style={styles.battBreakCard}>
                <Text style={styles.battBreakTitle}>{'🔋'} Battery Capacity Breakdown</Text>
                <View style={styles.battBreakRow}>
                  <Text style={styles.battBreakLabel}>Total capacity</Text>
                  <Text style={styles.battBreakVal}>{fmt(totalBattWh)} Wh</Text>
                </View>
                <View style={styles.battBreakRow}>
                  <Text style={styles.battBreakLabel}>After {(dod * 100).toFixed(0)}% DoD</Text>
                  <Text style={styles.battBreakVal}>{fmt(preinvBattWh)} Wh{' · '}{fmt(preinvBattAh, 1)} Ah @ {voltage}V</Text>
                </View>
                <View style={styles.battBreakRow}>
                  <Text style={styles.battBreakLabel}>Inverter loss ({((1 - INVERTER_EFF) * 100).toFixed(0)}% at {(INVERTER_EFF * 100).toFixed(0)}% eff.)</Text>
                  <Text style={[styles.battBreakVal, { color: '#f87171' }]}>{'−'}{fmt(preinvBattWh - usableBattWh)} Wh</Text>
                </View>
                <View style={[styles.battBreakRow, styles.battBreakTotalRow]}>
                  <Text style={styles.battBreakLabelBold}>Effective AC capacity</Text>
                  <Text style={[styles.battBreakVal, { color: '#4ade80', fontWeight: '700' }]}>{fmt(usableBattWh)} Wh{' · '}{fmt(usableBattAh, 1)} Ah</Text>
                </View>
              </View>
            )}

            {/* Coverage progress bar */}
            {dailyUsageWh > 0 && (
              <View style={styles.coverageCard}>
                <View style={styles.coverageRow}>
                  <Text style={styles.coverageLabel}>Solar Coverage</Text>
                  <Text style={[styles.coveragePct, { color: pctColor(coverageRatio) }]}>
                    {(Math.min(coverageRatio, 9.99) * 100).toFixed(0)}%
                  </Text>
                </View>
                <View style={styles.barBg}>
                  <View style={[styles.barFill, {
                    width: (Math.round(Math.min(1, coverageRatio) * 100) + '%') as any,
                    backgroundColor: pctColor(coverageRatio),
                  }]} />
                </View>
                <Text style={[styles.coverageNet, { color: netWh >= 0 ? '#4ade80' : '#f87171' }]}>
                  {netWh >= 0
                    ? ('Surplus: +' + fmt(netWh) + ' Wh/day')
                    : ('Deficit: ' + fmtN(netWh) + ' Wh/day')}
                </Text>
              </View>
            )}

            {/* Recommendations */}
            <View style={styles.recoCard}>
              <Text style={styles.recoTitle}>{'💡'} Recommendations</Text>
              {dailyUsageWh > 0 ? (
                <>
                  {netWh < 0 && (
                    <View style={styles.recoRow}>
                      <Text style={styles.recoText}>
                        {'☀️ '}To break even daily at {locationLabel ?? 'this location'}, add{' '}
                        <Text style={{ color: ACCENT, fontWeight: '700' }}>
                          ~{extraWattsNeeded} W
                        </Text>
                        {' '}more solar (about{' '}
                        {Math.ceil(extraWattsNeeded / panelWattsNum)} {'\u00d7'} {panelWattsNum} W panel{Math.ceil(extraWattsNeeded / panelWattsNum) !== 1 ? 's' : ''})
                        {' '}OR reduce usage by{' '}
                        <Text style={{ color: '#f87171', fontWeight: '700' }}>
                          {fmt(-netWh)} Wh/day.
                        </Text>
                      </Text>
                    </View>
                  )}
                  <View style={styles.recoRow}>
                    <Text style={styles.recoText}>
                      {'⚡ '}To cover {fmt(dailyUsageWh)} Wh/day you need{' '}
                      <Text style={{ color: ACCENT, fontWeight: '700' }}>
                        {panelsNeeded} panel{panelsNeeded !== 1 ? 's' : ''}
                      </Text>
                      {' '}@ {panelWattsNum} W each
                      {panelsNeeded <= parseInt(numPanels) ? ' ✅' : ` (you have ${numPanels})`}
                    </Text>
                  </View>
                  <View style={styles.recoRow}>
                    <Text style={styles.recoText}>
                      {'🔋 '}For 2 days without sun, you need{' '}
                      <Text style={{ color: '#4ade80', fontWeight: '700' }}>
                        {batt2DaysNeeded} batter{batt2DaysNeeded !== 1 ? 'ies' : 'y'}
                      </Text>
                      {' '}@ {fmt(ahPerBattNum)} Ah
                      {batt2DaysNeeded <= parseInt(numBatt) ? ' ✅' : ` (you have ${numBatt})`}
                    </Text>
                  </View>
                  {coverageRatio >= 1 && isFinite(batteryDays) && batteryDays >= 2 && (
                    <View style={[styles.recoRow, styles.greenBanner]}>
                      <Text style={[styles.recoText, { color: '#4ade80' }]}>
                        {'✅ '}Your setup should comfortably handle an average off-grid day{locationLabel ? ` at ${locationLabel}` : ''}!
                      </Text>
                    </View>
                  )}
                </>
              ) : (
                <Text style={styles.recoText}>
                  Enable some appliances in Step 4 to see recommendations.
                </Text>
              )}
            </View>

            {/* Assumptions */}
            <TouchableOpacity onPress={() => setShowAssumptions(v => !v)} style={styles.assumptionsToggle}>
              <Text style={styles.assumptionsToggleText}>
                {showAssumptions ? '\u25b2' : '\u25bc'} Assumptions {'&'} methodology
              </Text>
            </TouchableOpacity>
            {showAssumptions && (
              <View style={styles.assumptionsBox}>
                <Text style={styles.assumptionsText}>
                  {'• '}<Text style={{ fontWeight: '700' }}>Peak sun hours ({psh.toFixed(1)} hrs):</Text>
                  {usedFallback || !lat
                    ? ' Estimated from latitude and day-of-year using solar geometry.'
                    : " Fetched from backend solar service for your location + today's date."}
                </Text>
                <Text style={styles.assumptionsText}>
                  {'• '}<Text style={{ fontWeight: '700' }}>System losses ({(SYSTEM_LOSS * 100).toFixed(0)}%):</Text>
                  {' '}Wiring resistance, MPPT efficiency, temperature derating, dust, and soiling.
                </Text>
                <Text style={styles.assumptionsText}>
                  {'• '}<Text style={{ fontWeight: '700' }}>Inverter efficiency ({(INVERTER_EFF * 100).toFixed(0)}%):</Text>
                  {' '}Applied to usable battery (DC-to-AC conversion loss).
                </Text>
                <Text style={styles.assumptionsText}>
                  {'• '}<Text style={{ fontWeight: '700' }}>DoD ({(dod * 100).toFixed(0)}%):</Text>
                  {battType === 'lithium'
                    ? ' Lithium can safely discharge to ~10-15% state-of-charge.'
                    : ' Lead-based batteries limited to 50% DoD to preserve cycle life.'}
                </Text>
                <Text style={styles.assumptionsText}>
                  {'• '}Cloud cover not included — results represent a clear-sky baseline.
                </Text>
                <Text style={styles.assumptionsText}>
                  {'• '}Fridge draw shown as average (compressor cycles ~50% duty cycle).
                </Text>
              </View>
            )}
          </View>
        )}

        <View style={{ height: 48 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

// ─── Styles ───────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#09090b' },
  scroll:    { flex: 1 },

  backButton: { flexDirection: 'row', alignItems: 'center', padding: 16, gap: 8 },
  backText:   { color: '#fff', fontSize: 16, fontWeight: '600' },

  titleCard: {
    flexDirection: 'row', alignItems: 'center', gap: 14,
    backgroundColor: '#18181b', marginHorizontal: 14, marginTop: 4, marginBottom: 10,
    padding: 16, borderRadius: 14, borderWidth: 1, borderColor: '#27272a',
  },
  titleEmoji: { fontSize: 36 },
  title:    { color: '#fff',    fontSize: 19, fontWeight: '800' },
  subtitle: { color: '#a1a1aa', fontSize: 13, marginTop: 2 },

  section: {
    backgroundColor: '#18181b', borderRadius: 14,
    marginHorizontal: 14, marginBottom: 12,
    padding: 16, borderWidth: 1, borderColor: '#27272a',
  },

  sectionHeader: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 14 },
  stepBadge: {
    width: 22, height: 22, borderRadius: 11,
    backgroundColor: ACCENT, alignItems: 'center', justifyContent: 'center',
  },
  stepBadgeText: { color: '#1a1a1a', fontSize: 12, fontWeight: '800' },
  sectionIcon:   { fontSize: 16 },
  sectionLabel:  { color: '#fff', fontSize: 15, fontWeight: '700', flex: 1 },

  hint: { color: '#71717a', fontSize: 12, marginTop: 4, marginBottom: 6 },

  locationBadge: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    marginTop: 8, backgroundColor: ACCENT + '18',
    borderRadius: 6, paddingHorizontal: 10, paddingVertical: 6,
    alignSelf: 'flex-start',
    borderWidth: 1, borderColor: ACCENT + '40',
  },
  locationBadgeText: { color: ACCENT, fontSize: 13, fontWeight: '600' },

  fieldLabel: { color: '#a1a1aa', fontSize: 12, fontWeight: '600', marginBottom: 6, marginTop: 8 },

  chipRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 4 },
  chip: {
    paddingHorizontal: 12, paddingVertical: 7,
    borderRadius: 20, borderWidth: 1,
    borderColor: '#3f3f46', backgroundColor: '#27272a',
  },
  chipActive:     { borderColor: ACCENT, backgroundColor: ACCENT + '22' },
  chipText:       { color: '#a1a1aa', fontSize: 13, fontWeight: '600' },
  chipTextActive: { color: ACCENT },

  rowGrid:  { flexDirection: 'row', gap: 12, marginTop: 4 },
  halfCol:  { flex: 1 },

  input: {
    backgroundColor: '#27272a', color: '#f4f4f5',
    borderRadius: 8, paddingHorizontal: 12, paddingVertical: 10,
    fontSize: 15, borderWidth: 1, borderColor: '#3f3f46',
  },

  stepper: {
    flexDirection: 'row', alignItems: 'center',
    backgroundColor: '#27272a', borderRadius: 8,
    borderWidth: 1, borderColor: '#3f3f46', overflow: 'hidden',
  },
  stepBtn:   { padding: 10 },
  stepValue: { color: '#f4f4f5', fontSize: 15, fontWeight: '700', paddingHorizontal: 10 },

  summaryChip: {
    backgroundColor: ACCENT + '18', borderRadius: 8,
    padding: 10, marginTop: 6,
    borderWidth: 1, borderColor: ACCENT + '40',
  },
  summaryText: { color: ACCENT, fontSize: 12, fontWeight: '600' },

  // Custom toggle (replaces Switch — more reliable on RN Web)
  toggleTrack: {
    width: 38, height: 22, borderRadius: 11,
    backgroundColor: '#3f3f46',
    justifyContent: 'center', paddingHorizontal: 2,
  },
  toggleTrackOn: { backgroundColor: ACCENT + '88' },
  toggleThumb: {
    width: 18, height: 18, borderRadius: 9,
    backgroundColor: '#71717a',
    alignSelf: 'flex-start',
  },
  toggleThumbOn: {
    backgroundColor: ACCENT,
    alignSelf: 'flex-end',
  },

  // Appliances
  appHeader: {
    flexDirection: 'row', alignItems: 'center',
    paddingBottom: 6, borderBottomWidth: 1, borderBottomColor: '#3f3f46', marginBottom: 4,
  },
  appHeaderCol:   { color: '#52525b', fontSize: 11, flex: 1, marginLeft: 46 },
  appHeaderSmall: { color: '#52525b', fontSize: 11, width: 40, textAlign: 'center' },
  appHeaderWh:    { color: '#52525b', fontSize: 11, width: 52, textAlign: 'right' },

  appRow: {
    flexDirection: 'row', alignItems: 'center',
    paddingVertical: 8,
    borderBottomWidth: 1, borderBottomColor: '#27272a',
  },
  appRowOff: { opacity: 0.45 },
  appRowLeft: { flex: 1, flexDirection: 'row', alignItems: 'center', gap: 8, minWidth: 0 },
  appLabel:    { color: '#e4e4e7', fontSize: 12, flex: 1, marginRight: 4 },
  appLabelOff: { color: '#71717a' },

  appInput: {
    backgroundColor: '#27272a', color: '#f4f4f5',
    borderRadius: 6, paddingHorizontal: 4, paddingVertical: 5,
    fontSize: 13, width: 40, textAlign: 'center',
    borderWidth: 1, borderColor: '#3f3f46', marginHorizontal: 0,
  },
  appInputOff: { color: '#52525b', borderColor: '#27272a' },
  appWh: { color: '#a1a1aa', fontSize: 12, width: 52, textAlign: 'right' },

  // Calculate
  calcBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8,
    backgroundColor: ACCENT, borderRadius: 12,
    marginHorizontal: 14, marginBottom: 14, paddingVertical: 16,
  },
  calcBtnDisabled: { opacity: 0.6 },
  calcBtnText: { color: '#1a1a1a', fontSize: 16, fontWeight: '800' },

  // Results
  locContext: {
    flexDirection: 'row', gap: 6, alignItems: 'center',
    backgroundColor: ACCENT + '12', borderRadius: 6,
    paddingHorizontal: 10, paddingVertical: 6,
    marginBottom: 10,
  },
  locContextText: { color: ACCENT, fontSize: 12, fontWeight: '600', flex: 1 },

  noticeBanner: {
    flexDirection: 'row', gap: 8,
    backgroundColor: '#422006', borderRadius: 8,
    padding: 10, marginBottom: 12, alignItems: 'flex-start',
    borderWidth: 1, borderColor: '#854d0e',
  },
  noticeText: { color: '#fde68a', fontSize: 12, flex: 1 },

  metricsGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10, marginBottom: 14 },
  metricCard: {
    backgroundColor: '#27272a', borderRadius: 10,
    padding: 12, width: '47%', alignItems: 'center',
    borderWidth: 1, borderColor: '#3f3f46',
  },
  metricLabel: { color: '#71717a', fontSize: 11, fontWeight: '600', marginBottom: 4, textAlign: 'center' },
  metricValue: { color: '#f4f4f5', fontSize: 24, fontWeight: '800' },
  metricUnit:  { color: '#71717a', fontSize: 11, marginTop: 2 },
  metricSub:   { color: ACCENT,    fontSize: 10, marginTop: 3 },

  coverageCard: {
    backgroundColor: '#27272a', borderRadius: 10,
    padding: 14, marginBottom: 12,
    borderWidth: 1, borderColor: '#3f3f46',
  },
  coverageRow:  { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 8 },
  coverageLabel: { color: '#a1a1aa', fontSize: 13, fontWeight: '600' },
  coveragePct:  { fontSize: 15, fontWeight: '800' },
  barBg:   { height: 8, backgroundColor: '#3f3f46', borderRadius: 4, overflow: 'hidden' },
  barFill: { height: 8, borderRadius: 4 },
  coverageNet: { fontSize: 12, fontWeight: '600', marginTop: 8, textAlign: 'right' },

  recoCard: {
    backgroundColor: '#1a1a1e', borderRadius: 10,
    padding: 14, marginBottom: 10,
    borderWidth: 1, borderColor: '#3f3f46',
  },
  recoTitle: { color: '#e4e4e7', fontSize: 14, fontWeight: '700', marginBottom: 8 },
  recoRow:   { flexDirection: 'row', alignItems: 'flex-start', marginBottom: 8 },
  recoText:  { color: '#d4d4d8', fontSize: 13, flex: 1, lineHeight: 19 },
  greenBanner: {
    backgroundColor: '#052e16', borderRadius: 8,
    padding: 10, borderWidth: 1, borderColor: '#14532d',
  },

  assumptionsToggle:     { alignItems: 'center', paddingVertical: 10 },
  assumptionsToggleText: { color: '#71717a', fontSize: 12 },
  assumptionsBox: {
    backgroundColor: '#111113', borderRadius: 8,
    padding: 12,
  },
  assumptionsText: { color: '#71717a', fontSize: 12, lineHeight: 17, marginBottom: 4 },

  // Battery breakdown card (Results step)
  battBreakCard: {
    backgroundColor: '#27272a', borderRadius: 10,
    padding: 14, marginBottom: 12,
    borderWidth: 1, borderColor: '#3f3f46',
  },
  battBreakTitle: { color: '#e4e4e7', fontSize: 13, fontWeight: '700', marginBottom: 10 },
  battBreakRow: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    paddingVertical: 5,
    borderBottomWidth: 1, borderBottomColor: '#3f3f46',
  },
  battBreakTotalRow: {
    borderBottomWidth: 0, marginTop: 2, paddingTop: 8,
    borderTopWidth: 1, borderTopColor: '#52525b',
  },
  battBreakLabel:     { color: '#a1a1aa', fontSize: 12, flex: 1 },
  battBreakLabelBold: { color: '#e4e4e7', fontSize: 12, fontWeight: '700', flex: 1 },
  battBreakVal:       { color: '#f4f4f5', fontSize: 12, fontWeight: '600', textAlign: 'right' },
});
