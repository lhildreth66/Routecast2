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
 *  - Backend `/solar-forecast` used to get peak sun hours; falls back to
 *    local latitude-based math if the call fails.
 */

import React, { useState, useMemo } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  TextInput,
  ActivityIndicator,
  ScrollView,
  Switch,
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

interface Appliance {
  id: string;
  label: string;
  icon: string;
  watts: number;
  hours: number;
  mins: number;
  enabled: boolean;
}

// ─── Constants ────────────────────────────────────────────────────────────────

const ACCENT = '#eab308'; // yellow

const DEFAULT_DOD: Record<BattType, number> = {
  lithium: 0.85,
  agm: 0.50,
  gel: 0.50,
  lead: 0.50,
};

const INVERTER_EFF = 0.92;   // inverter efficiency
const SYSTEM_LOSS = 0.77;    // wiring + MPPT + temperature + dust losses

const DEFAULT_APPLIANCES: Appliance[] = [
  { id: 'fridge',    label: '12V Compressor Fridge', icon: '🧊', watts: 50,   hours: 24, mins:  0, enabled: true  },
  { id: 'lights',    label: 'LED Lights',             icon: '💡', watts: 20,   hours:  5, mins:  0, enabled: true  },
  { id: 'pump',      label: 'Water Pump',             icon: '🚿', watts: 60,   hours:  0, mins: 30, enabled: true  },
  { id: 'phone',     label: 'Phone Charging',         icon: '📱', watts: 15,   hours:  2, mins:  0, enabled: true  },
  { id: 'fan',       label: 'Roof Vent Fan',          icon: '🌀', watts: 25,   hours:  4, mins:  0, enabled: false },
  { id: 'cpap',      label: 'CPAP Machine',           icon: '💨', watts: 55,   hours:  8, mins:  0, enabled: false },
  { id: 'laptop',    label: 'Laptop / Tablet',        icon: '💻', watts: 45,   hours:  2, mins:  0, enabled: false },
  { id: 'tv',        label: 'TV / Streaming',         icon: '📺', watts: 60,   hours:  2, mins:  0, enabled: false },
  { id: 'microwave', label: 'Microwave',              icon: '📡', watts: 1000, hours:  0, mins: 10, enabled: false },
  { id: 'coffee',    label: 'Coffee Maker',           icon: '☕', watts: 900,  hours:  0, mins:  6, enabled: false },
  { id: 'airfryer',  label: 'Air Fryer',              icon: '🍳', watts: 1500, hours:  0, mins: 15, enabled: false },
  { id: 'other',     label: 'Other / Custom',         icon: '🔌', watts: 100,  hours:  1, mins:  0, enabled: false },
];

// ─── Local peak-sun-hours approximation (mirrors backend solar geometry) ──────

function localPeakSunHours(lat: number): number {
  const now = new Date();
  const start = new Date(now.getFullYear(), 0, 0);
  const doy = Math.floor((now.getTime() - start.getTime()) / 864e5);
  const decl = 23.44 * Math.sin((2 * Math.PI * (doy - 81)) / 365);
  const lr = (lat * Math.PI) / 180;
  const dr = (decl * Math.PI) / 180;
  const sinE = Math.sin(lr) * Math.sin(dr) + Math.cos(lr) * Math.cos(dr);
  const elevDeg = (Math.asin(Math.max(-1, Math.min(1, sinE))) * 180) / Math.PI;
  if (elevDeg <= 0) return 0.5;
  const cosH = -Math.tan(lr) * Math.tan(dr);
  const ha = Math.acos(Math.max(-1, Math.min(1, cosH)));
  const dayLen = (2 * 24 * ha) / (2 * Math.PI);
  return Math.max(0.5, 5.5 * (elevDeg / 90) ** 0.75 * (dayLen / 12));
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

const fmt = (n: number, dec = 0) => (isFinite(n) ? n.toFixed(dec) : '—');

const pctColor = (ratio: number) =>
  ratio >= 1 ? '#4ade80' : ratio >= 0.7 ? '#facc15' : '#f87171';

// ─── Sub-components ──────────────────────────────────────────────────────────

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

function Stepper({
  value,
  onChange,
  min = 1,
  max = 99,
}: {
  value: string;
  onChange: (v: string) => void;
  min?: number;
  max?: number;
}) {
  const n = parseInt(value) || 1;
  return (
    <View style={styles.stepper}>
      <TouchableOpacity
        style={styles.stepBtn}
        onPress={() => onChange(String(Math.max(min, n - 1)))}
        disabled={n <= min}
      >
        <Ionicons name="remove" size={16} color={n <= min ? '#52525b' : '#e4e4e7'} />
      </TouchableOpacity>
      <Text style={styles.stepValue}>{n}</Text>
      <TouchableOpacity
        style={styles.stepBtn}
        onPress={() => onChange(String(Math.min(max, n + 1)))}
        disabled={n >= max}
      >
        <Ionicons name="add" size={16} color={n >= max ? '#52525b' : '#e4e4e7'} />
      </TouchableOpacity>
    </View>
  );
}

// ─── Main Screen ─────────────────────────────────────────────────────────────

export default function SolarForecastScreen() {
  const router = useRouter();

  // ── Location (no auto-GPS on mount) ─────────────────────────────────────
  const {
    lat, lon, locationLabel, locationLoading,
    locationQuery, suggestions, showSuggestions,
    handleLocationQueryChange, selectSuggestion,
    clearManualLocation, triggerGps, setShowSuggestions,
  } = useLocationSearch('solarForecastLoc');

  // ── Battery bank ────────────────────────────────────────────────────────
  const [battType, setBattType] = useState<BattType>('lithium');
  const [numBatt, setNumBatt] = useState('2');
  const [ahPerBatt, setAhPerBatt] = useState('100');
  const [voltage, setVoltage] = useState<12 | 24>(12);
  const [customDodStr, setCustomDodStr] = useState('');

  // ── Solar array ─────────────────────────────────────────────────────────
  const [panelWatts, setPanelWatts] = useState('200');
  const [numPanels, setNumPanels] = useState('2');

  // ── Appliances ──────────────────────────────────────────────────────────
  const [appliances, setAppliances] = useState<Appliance[]>(DEFAULT_APPLIANCES);

  // ── Results state ────────────────────────────────────────────────────────
  const [showResults, setShowResults] = useState(false);
  const [calculating, setCalculating] = useState(false);
  const [peakSunHours, setPeakSunHours] = useState<number | null>(null);
  const [usedFallback, setUsedFallback] = useState(false);
  const [solarApiError, setSolarApiError] = useState('');

  // ── Assumptions drawer ───────────────────────────────────────────────────
  const [showAssumptions, setShowAssumptions] = useState(false);

  // ─── Computed values ──────────────────────────────────────────────────────

  const dod = useMemo(() => {
    if (customDodStr) {
      const n = parseFloat(customDodStr);
      if (!isNaN(n) && n > 0 && n <= 100) return n / 100;
    }
    return DEFAULT_DOD[battType];
  }, [battType, customDodStr]);

  const totalBattWh = useMemo(
    () => (parseInt(numBatt) || 0) * (parseFloat(ahPerBatt) || 0) * voltage,
    [numBatt, ahPerBatt, voltage],
  );

  const usableBattWh = useMemo(
    () => totalBattWh * dod * INVERTER_EFF,
    [totalBattWh, dod],
  );

  const arrayWatts = useMemo(
    () => (parseInt(panelWatts) || 0) * (parseInt(numPanels) || 0),
    [panelWatts, numPanels],
  );

  const dailyUsageWh = useMemo(
    () =>
      appliances
        .filter((a) => a.enabled)
        .reduce((s, a) => s + a.watts * (a.hours + a.mins / 60), 0),
    [appliances],
  );

  // Use backend-fetched PSH when available, else local math, else 4.5 default
  const psh = useMemo(() => {
    if (peakSunHours !== null) return peakSunHours;
    if (lat) return localPeakSunHours(parseFloat(lat));
    return 4.5;
  }, [peakSunHours, lat]);

  const solarWhDay = arrayWatts * psh * SYSTEM_LOSS;
  const batteryDays = dailyUsageWh > 0 ? usableBattWh / dailyUsageWh : Infinity;
  const netWh = solarWhDay - dailyUsageWh;
  const coverageRatio = dailyUsageWh > 0 ? solarWhDay / dailyUsageWh : 1;

  const panelWattsNum = parseInt(panelWatts) || 200;
  const ahPerBattNum = parseFloat(ahPerBatt) || 100;

  const panelsNeeded =
    dailyUsageWh > 0
      ? Math.ceil(dailyUsageWh / Math.max(0.01, panelWattsNum * psh * SYSTEM_LOSS))
      : 0;

  const batt2DaysNeeded =
    dailyUsageWh > 0
      ? Math.ceil((dailyUsageWh * 2) / Math.max(0.01, ahPerBattNum * voltage * dod * INVERTER_EFF))
      : 0;

  // ─── Handlers ──────────────────────────────────────────────────────────────

  const toggleAppliance = (id: string) =>
    setAppliances((prev) =>
      prev.map((a) => (a.id === id ? { ...a, enabled: !a.enabled } : a)),
    );

  const updateAppliance = (
    id: string,
    field: 'watts' | 'hours' | 'mins',
    raw: string,
  ) => {
    const n = Math.max(0, parseFloat(raw) || 0);
    setAppliances((prev) =>
      prev.map((a) => (a.id === id ? { ...a, [field]: n } : a)),
    );
  };

  const calculate = async () => {
    setShowResults(true);
    setCalculating(true);
    setSolarApiError('');

    if (!lat || !lon) {
      setPeakSunHours(4.5);
      setUsedFallback(true);
      setCalculating(false);
      return;
    }

    try {
      const today = new Date().toISOString().split('T')[0];
      const resp = await axios.post(buildUrl('solar-forecast'), {
        lat: parseFloat(lat),
        lon: parseFloat(lon),
        date_range: [today],
        panel_watts: 1000, // reference 1 kW panel — Wh/1000 = peak sun hours
        shade_pct: 0,
        cloud_cover: [0],
      });
      const refWh: number = resp.data?.daily_wh?.[0] ?? 4500;
      setPeakSunHours(Math.max(0.5, refWh / 1000));
      setUsedFallback(false);
    } catch (err: any) {
      const fallback = localPeakSunHours(parseFloat(lat));
      setPeakSunHours(Math.max(0.5, fallback));
      setUsedFallback(true);
      const detail =
        typeof err?.response?.data?.detail === 'string'
          ? err.response.data.detail
          : err?.message ?? '';
      if (detail) setSolarApiError(detail);
    } finally {
      setCalculating(false);
    }
  };

  // ─── Render ────────────────────────────────────────────────────────────────

  return (
    <SafeAreaView style={styles.container}>
      <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
        <Ionicons name="arrow-back" size={24} color="#fff" />
        <Text style={styles.backText}>Back</Text>
      </TouchableOpacity>

      <ScrollView style={styles.scroll} keyboardShouldPersistTaps="handled">
        {/* Title */}
        <View style={styles.titleCard}>
          <Text style={styles.titleEmoji}>☀️</Text>
          <View style={{ flex: 1 }}>
            <Text style={styles.title}>RV Solar + Battery Calculator</Text>
            <Text style={styles.subtitle}>Estimate off-grid runtime, solar coverage &amp; sizing</Text>
          </View>
        </View>

        {/* ── Step 1: Location ── */}
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
          <Text style={styles.hint}>Used to estimate peak sun hours for your campsite.</Text>
        </View>

        {/* ── Step 2: Battery Bank ── */}
        <View style={styles.section}>
          <SectionHeader n={2} label="Battery Bank" icon="🔋" />

          <Text style={styles.fieldLabel}>Battery type</Text>
          <View style={styles.chipRow}>
            {(['lithium', 'agm', 'gel', 'lead'] as BattType[]).map((bt) => (
              <TouchableOpacity
                key={bt}
                style={[styles.chip, battType === bt && styles.chipActive]}
                onPress={() => { setBattType(bt); setCustomDodStr(''); }}
              >
                <Text style={[styles.chipText, battType === bt && styles.chipTextActive]}>
                  {bt === 'lithium' ? '⚡ Lithium' : bt === 'agm' ? 'AGM' : bt === 'gel' ? 'Gel' : 'Lead Acid'}
                </Text>
              </TouchableOpacity>
            ))}
          </View>

          <Text style={styles.fieldLabel}>System voltage</Text>
          <View style={styles.chipRow}>
            {([12, 24] as const).map((v) => (
              <TouchableOpacity
                key={v}
                style={[styles.chip, voltage === v && styles.chipActive]}
                onPress={() => setVoltage(v)}
              >
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
              <TextInput
                style={styles.input}
                value={ahPerBatt}
                onChangeText={setAhPerBatt}
                keyboardType="numeric"
                placeholder="100"
                placeholderTextColor="#6b7280"
              />
            </View>
          </View>

          <View style={styles.rowInput}>
            <Text style={styles.rowLabel}>
              Depth of discharge (default {(DEFAULT_DOD[battType] * 100).toFixed(0)}%)
            </Text>
            <View style={styles.rowInputRight}>
              <TextInput
                style={styles.smallInput}
                value={customDodStr}
                onChangeText={setCustomDodStr}
                keyboardType="numeric"
                placeholder={`${(DEFAULT_DOD[battType] * 100).toFixed(0)}`}
                placeholderTextColor="#6b7280"
              />
              <Text style={styles.unitText}>%</Text>
            </View>
          </View>

          {totalBattWh > 0 && (
            <View style={styles.summaryChip}>
              <Text style={styles.summaryText}>
                Bank: {fmt(totalBattWh)} Wh total · {fmt(usableBattWh)} Wh usable
                ({(dod * 100).toFixed(0)}% DoD, {(INVERTER_EFF * 100).toFixed(0)}% inverter)
              </Text>
            </View>
          )}
        </View>

        {/* ── Step 3: Solar Array ── */}
        <View style={styles.section}>
          <SectionHeader n={3} label="Solar Array" icon="🌞" />
          <View style={styles.rowGrid}>
            <View style={styles.halfCol}>
              <Text style={styles.fieldLabel}>Watts / panel</Text>
              <TextInput
                style={styles.input}
                value={panelWatts}
                onChangeText={setPanelWatts}
                keyboardType="numeric"
                placeholder="200"
                placeholderTextColor="#6b7280"
              />
            </View>
            <View style={styles.halfCol}>
              <Text style={styles.fieldLabel}>Panels</Text>
              <Stepper value={numPanels} onChange={setNumPanels} />
            </View>
          </View>
          {arrayWatts > 0 && (
            <View style={styles.summaryChip}>
              <Text style={styles.summaryText}>
                Array: {arrayWatts} W ({numPanels} × {panelWatts} W)
              </Text>
            </View>
          )}
        </View>

        {/* ── Step 4: Appliances ── */}
        <View style={styles.section}>
          <SectionHeader n={4} label="Daily Usage" icon="🔌" />
          <Text style={styles.hint}>Toggle appliances you use. Edit watts or time as needed.</Text>

          {appliances.map((a) => (
            <View key={a.id} style={[styles.applianceRow, !a.enabled && styles.applianceRowOff]}>
              <View style={styles.applianceLeft}>
                <Switch
                  value={a.enabled}
                  onValueChange={() => toggleAppliance(a.id)}
                  thumbColor={a.enabled ? ACCENT : '#52525b'}
                  trackColor={{ false: '#3f3f46', true: ACCENT + '55' }}
                />
                <Text style={[styles.applianceLabel, !a.enabled && styles.applianceLabelOff]}>
                  {a.icon} {a.label}
                </Text>
              </View>
              {a.enabled && (
                <View style={styles.applianceInputs}>
                  <View style={styles.applianceField}>
                    <TextInput
                      style={styles.tinyInput}
                      value={String(a.watts)}
                      onChangeText={(v) => updateAppliance(a.id, 'watts', v)}
                      keyboardType="numeric"
                    />
                    <Text style={styles.tinyUnit}>W</Text>
                  </View>
                  <View style={styles.applianceField}>
                    <TextInput
                      style={styles.tinyInput}
                      value={String(a.hours)}
                      onChangeText={(v) => updateAppliance(a.id, 'hours', v)}
                      keyboardType="numeric"
                    />
                    <Text style={styles.tinyUnit}>h</Text>
                  </View>
                  <View style={styles.applianceField}>
                    <TextInput
                      style={styles.tinyInput}
                      value={String(a.mins)}
                      onChangeText={(v) => updateAppliance(a.id, 'mins', v)}
                      keyboardType="numeric"
                    />
                    <Text style={styles.tinyUnit}>m</Text>
                  </View>
                  <Text style={styles.applianceWh}>
                    {fmt(a.watts * (a.hours + a.mins / 60))} Wh
                  </Text>
                </View>
              )}
            </View>
          ))}

          {dailyUsageWh > 0 && (
            <View style={[styles.summaryChip, { marginTop: 10 }]}>
              <Text style={styles.summaryText}>
                Total daily load: {fmt(dailyUsageWh)} Wh/day
              </Text>
            </View>
          )}
        </View>

        {/* ── Calculate button ── */}
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

        {/* ── Step 5: Results ── */}
        {showResults && !calculating && (
          <View style={styles.section}>
            <SectionHeader n={5} label="Results" icon="📊" />

            {(usedFallback || solarApiError) && (
              <View style={styles.noticeBanner}>
                <Ionicons name="information-circle" size={16} color="#facc15" />
                <Text style={styles.noticeText}>
                  {solarApiError
                    ? `Solar data unavailable — using estimated sun hours. (${solarApiError})`
                    : !lat
                    ? 'No location set — using default 4.5 peak sun hours. Add a location for accurate results.'
                    : 'Using locally calculated sun hours based on latitude and today\'s date.'}
                </Text>
              </View>
            )}

            <View style={styles.metricsGrid}>
              <View style={styles.metricCard}>
                <Text style={styles.metricLabel}>Daily Usage</Text>
                <Text style={styles.metricValue}>{fmt(dailyUsageWh)}</Text>
                <Text style={styles.metricUnit}>Wh/day</Text>
              </View>
              <View style={styles.metricCard}>
                <Text style={styles.metricLabel}>Usable Battery</Text>
                <Text style={styles.metricValue}>{fmt(usableBattWh)}</Text>
                <Text style={styles.metricUnit}>Wh</Text>
              </View>
              <View style={styles.metricCard}>
                <Text style={styles.metricLabel}>Battery Runtime</Text>
                <Text style={[styles.metricValue, { color: batteryDays >= 2 ? '#4ade80' : batteryDays >= 1 ? '#facc15' : '#f87171' }]}>
                  {isFinite(batteryDays) ? fmt(batteryDays, 1) : '∞'}
                </Text>
                <Text style={styles.metricUnit}>days (no sun)</Text>
              </View>
              <View style={styles.metricCard}>
                <Text style={styles.metricLabel}>Solar Production</Text>
                <Text style={[styles.metricValue, { color: ACCENT }]}>{fmt(solarWhDay)}</Text>
                <Text style={styles.metricUnit}>Wh/day</Text>
                <Text style={styles.metricSub}>{psh.toFixed(1)} peak sun hrs</Text>
              </View>
            </View>

            {dailyUsageWh > 0 && (
              <View style={styles.coverageCard}>
                <View style={styles.coverageRow}>
                  <Text style={styles.coverageLabel}>Solar Coverage</Text>
                  <Text style={[styles.coveragePct, { color: pctColor(coverageRatio) }]}>
                    {(coverageRatio * 100).toFixed(0)}%
                  </Text>
                </View>
                <View style={styles.barBg}>
                  <View
                    style={[
                      styles.barFill,
                      {
                        width: `${Math.min(100, coverageRatio * 100).toFixed(0)}%` as any,
                        backgroundColor: pctColor(coverageRatio),
                      },
                    ]}
                  />
                </View>
                <Text style={[styles.coverageNet, { color: netWh >= 0 ? '#4ade80' : '#f87171' }]}>
                  {netWh >= 0 ? `Surplus: +${fmt(netWh)} Wh/day` : `Deficit: ${fmt(netWh)} Wh/day`}
                </Text>
              </View>
            )}

            <View style={styles.recoCard}>
              <Text style={styles.recoTitle}>💡 Recommendations</Text>
              {dailyUsageWh > 0 ? (
                <>
                  <View style={styles.recoRow}>
                    <Text style={styles.recoText}>
                      {'⚡ '}To cover {fmt(dailyUsageWh)} Wh/day you need{' '}
                      <Text style={{ color: ACCENT, fontWeight: '700' }}>
                        {panelsNeeded} panel{panelsNeeded !== 1 ? 's' : ''}
                      </Text>{' '}
                      @ {panelWattsNum} W each
                      {panelsNeeded <= parseInt(numPanels) ? ' ✅' : ` (you have ${numPanels})`}
                    </Text>
                  </View>
                  <View style={styles.recoRow}>
                    <Text style={styles.recoText}>
                      {'🔋 '}For 2 days without sun you need{' '}
                      <Text style={{ color: '#4ade80', fontWeight: '700' }}>
                        {batt2DaysNeeded} batter{batt2DaysNeeded !== 1 ? 'ies' : 'y'}
                      </Text>{' '}
                      @ {ahPerBattNum} Ah
                      {batt2DaysNeeded <= parseInt(numBatt) ? ' ✅' : ` (you have ${numBatt})`}
                    </Text>
                  </View>
                  {coverageRatio >= 1 && isFinite(batteryDays) && batteryDays >= 2 && (
                    <View style={[styles.recoRow, styles.greenBanner]}>
                      <Text style={[styles.recoText, { color: '#4ade80' }]}>
                        ✅ Your setup should handle average off-grid days at this location! 🎉
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

            <TouchableOpacity
              style={styles.assumptionsToggle}
              onPress={() => setShowAssumptions((v) => !v)}
              activeOpacity={0.7}
            >
              <Text style={styles.assumptionsToggleText}>
                {showAssumptions ? '▲' : '▼'} Assumptions &amp; methodology
              </Text>
            </TouchableOpacity>

            {showAssumptions && (
              <View style={styles.assumptionsBox}>
                <Text style={styles.assumptionsText}>
                  {'• '}<Text style={{ fontWeight: '700' }}>Peak sun hours ({psh.toFixed(1)} hrs):</Text>{' '}
                  {usedFallback || !lat
                    ? 'Estimated from latitude and day-of-year using solar geometry.'
                    : "Fetched from backend solar forecast service for your location + today's date."}
                </Text>
                <Text style={styles.assumptionsText}>
                  {'• '}<Text style={{ fontWeight: '700' }}>System losses ({(SYSTEM_LOSS * 100).toFixed(0)}%):</Text>{' '}
                  Wiring resistance, MPPT efficiency, temperature derating, dust and soiling.
                </Text>
                <Text style={styles.assumptionsText}>
                  {'• '}<Text style={{ fontWeight: '700' }}>Inverter efficiency ({(INVERTER_EFF * 100).toFixed(0)}%):</Text>{' '}
                  Applied to usable battery capacity for DC→AC conversion losses.
                </Text>
                <Text style={styles.assumptionsText}>
                  {'• '}<Text style={{ fontWeight: '700' }}>DoD ({(dod * 100).toFixed(0)}%):</Text>{' '}
                  {battType === 'lithium'
                    ? 'Lithium can safely discharge to ~15% state-of-charge.'
                    : 'Lead-based batteries limited to 50% DoD to preserve cycle life.'}
                </Text>
                <Text style={styles.assumptionsText}>
                  {'• '}Cloud cover not included — results represent a clear-sky baseline.
                </Text>
              </View>
            )}
          </View>
        )}

        <View style={{ height: 40 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

// ─── Styles ───────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#09090b' },
  scroll: { flex: 1 },

  backButton: { flexDirection: 'row', alignItems: 'center', padding: 16, gap: 8 },
  backText: { color: '#fff', fontSize: 16, fontWeight: '600' },

  titleCard: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 14,
    backgroundColor: '#18181b',
    marginHorizontal: 14,
    marginTop: 4,
    marginBottom: 10,
    padding: 16,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: '#27272a',
  },
  titleEmoji: { fontSize: 36 },
  title: { color: '#fff', fontSize: 19, fontWeight: '800' },
  subtitle: { color: '#a1a1aa', fontSize: 13, marginTop: 2 },

  section: {
    backgroundColor: '#18181b',
    borderRadius: 14,
    marginHorizontal: 14,
    marginBottom: 12,
    padding: 16,
    borderWidth: 1,
    borderColor: '#27272a',
  },

  sectionHeader: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 14 },
  stepBadge: {
    width: 22, height: 22, borderRadius: 11,
    backgroundColor: ACCENT, alignItems: 'center', justifyContent: 'center',
  },
  stepBadgeText: { color: '#1a1a1a', fontSize: 12, fontWeight: '800' },
  sectionIcon: { fontSize: 16 },
  sectionLabel: { color: '#fff', fontSize: 15, fontWeight: '700', flex: 1 },

  hint: { color: '#71717a', fontSize: 12, marginBottom: 10, marginTop: -6 },
  fieldLabel: { color: '#a1a1aa', fontSize: 12, fontWeight: '600', marginBottom: 6, marginTop: 8 },

  chipRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 4 },
  chip: {
    paddingHorizontal: 12, paddingVertical: 6,
    borderRadius: 20, borderWidth: 1,
    borderColor: '#3f3f46', backgroundColor: '#27272a',
  },
  chipActive: { borderColor: ACCENT, backgroundColor: ACCENT + '22' },
  chipText: { color: '#a1a1aa', fontSize: 13, fontWeight: '600' },
  chipTextActive: { color: ACCENT },

  rowGrid: { flexDirection: 'row', gap: 12, marginTop: 4 },
  halfCol: { flex: 1 },

  input: {
    backgroundColor: '#27272a', color: '#f4f4f5',
    borderRadius: 8, paddingHorizontal: 12, paddingVertical: 10,
    fontSize: 15, borderWidth: 1, borderColor: '#3f3f46',
  },

  rowInput: {
    flexDirection: 'row', alignItems: 'center',
    justifyContent: 'space-between', marginTop: 8,
  },
  rowLabel: { color: '#a1a1aa', fontSize: 13, flex: 1 },
  rowInputRight: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  smallInput: {
    backgroundColor: '#27272a', color: '#f4f4f5',
    borderRadius: 8, paddingHorizontal: 10, paddingVertical: 7,
    fontSize: 14, width: 70, textAlign: 'right',
    borderWidth: 1, borderColor: '#3f3f46',
  },
  unitText: { color: '#71717a', fontSize: 13, width: 24 },

  stepper: {
    flexDirection: 'row', alignItems: 'center',
    backgroundColor: '#27272a', borderRadius: 8,
    borderWidth: 1, borderColor: '#3f3f46', overflow: 'hidden',
  },
  stepBtn: { padding: 10 },
  stepValue: { color: '#f4f4f5', fontSize: 15, fontWeight: '700', paddingHorizontal: 10 },

  summaryChip: {
    backgroundColor: ACCENT + '18', borderRadius: 8,
    padding: 10, marginTop: 10,
    borderWidth: 1, borderColor: ACCENT + '40',
  },
  summaryText: { color: ACCENT, fontSize: 12, fontWeight: '600' },

  applianceRow: {
    borderBottomWidth: 1, borderBottomColor: '#27272a',
    paddingVertical: 10, gap: 6,
  },
  applianceRowOff: { opacity: 0.5 },
  applianceLeft: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  applianceLabel: { color: '#e4e4e7', fontSize: 13, flex: 1 },
  applianceLabelOff: { color: '#71717a' },
  applianceInputs: {
    flexDirection: 'row', alignItems: 'center',
    gap: 6, paddingLeft: 44,
  },
  applianceField: { flexDirection: 'row', alignItems: 'center', gap: 2 },
  tinyInput: {
    backgroundColor: '#27272a', color: '#f4f4f5',
    borderRadius: 6, paddingHorizontal: 6, paddingVertical: 4,
    fontSize: 13, width: 46, textAlign: 'center',
    borderWidth: 1, borderColor: '#3f3f46',
  },
  tinyUnit: { color: '#71717a', fontSize: 11, width: 14 },
  applianceWh: { color: '#a1a1aa', fontSize: 12, marginLeft: 4, minWidth: 50, textAlign: 'right' },

  calcBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8,
    backgroundColor: ACCENT, borderRadius: 12,
    marginHorizontal: 14, marginBottom: 14, paddingVertical: 16,
  },
  calcBtnDisabled: { opacity: 0.6 },
  calcBtnText: { color: '#1a1a1a', fontSize: 16, fontWeight: '800' },

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
  metricUnit: { color: '#71717a', fontSize: 11, marginTop: 2 },
  metricSub: { color: ACCENT, fontSize: 10, marginTop: 2 },

  coverageCard: {
    backgroundColor: '#27272a', borderRadius: 10,
    padding: 14, marginBottom: 12,
    borderWidth: 1, borderColor: '#3f3f46',
  },
  coverageRow: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 8 },
  coverageLabel: { color: '#a1a1aa', fontSize: 13, fontWeight: '600' },
  coveragePct: { fontSize: 15, fontWeight: '800' },
  barBg: { height: 8, backgroundColor: '#3f3f46', borderRadius: 4, overflow: 'hidden' },
  barFill: { height: 8, borderRadius: 4 },
  coverageNet: { fontSize: 12, fontWeight: '600', marginTop: 8, textAlign: 'right' },

  recoCard: {
    backgroundColor: '#1a1a1e', borderRadius: 10,
    padding: 14, marginBottom: 10,
    borderWidth: 1, borderColor: '#3f3f46', gap: 10,
  },
  recoTitle: { color: '#e4e4e7', fontSize: 14, fontWeight: '700' },
  recoRow: { flexDirection: 'row', alignItems: 'flex-start' },
  recoText: { color: '#d4d4d8', fontSize: 13, flex: 1, lineHeight: 19 },
  greenBanner: {
    backgroundColor: '#052e16', borderRadius: 8,
    padding: 10, borderWidth: 1, borderColor: '#14532d',
  },

  assumptionsToggle: { alignItems: 'center', paddingVertical: 10 },
  assumptionsToggleText: { color: '#71717a', fontSize: 12 },
  assumptionsBox: {
    backgroundColor: '#111113', borderRadius: 8,
    padding: 12, gap: 6,
  },
  assumptionsText: { color: '#71717a', fontSize: 12, lineHeight: 17 },
});
