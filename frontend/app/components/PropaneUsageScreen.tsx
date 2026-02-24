/**
 * PropaneUsageScreen — deterministic RV propane planner
 *
 * Answers: "How many nights will my propane last?"
 * All math is client-side. No API calls.
 */

import React, { useState, useMemo } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
} from 'react-native';
import Ionicons from '@expo/vector-icons/Ionicons';
import {
  calcPropane,
  PropaneInputs,
  PropaneResult,
  PROPANE_BTU_PER_GAL,
  PROPANE_LB_PER_GAL,
  DEFAULT_NIGHT_HOURS,
} from '../hooks/usePropaneUsage';

// ─── Format helpers ───────────────────────────────────────────────────────────
const fmt1 = (n: number) => n.toFixed(1);
const fmt2 = (n: number) => n.toFixed(2);
const pct  = (n: number, total: number) =>
  total > 0 ? Math.round((n / total) * 100) : 0;

// ─── Stepper ─────────────────────────────────────────────────────────────────
const Stepper = ({
  label, onDec, onInc, display,
}: {
  label: string;
  onDec: () => void;
  onInc: () => void;
  display: string;
}) => (
  <View style={s.stepRow}>
    <Text style={s.stepLabel}>{label}</Text>
    <View style={s.stepControls}>
      <TouchableOpacity style={s.stepBtn} onPress={onDec}>
        <Text style={s.stepBtnTxt}>−</Text>
      </TouchableOpacity>
      <Text style={s.stepVal}>{display}</Text>
      <TouchableOpacity style={s.stepBtn} onPress={onInc}>
        <Text style={s.stepBtnTxt}>+</Text>
      </TouchableOpacity>
    </View>
  </View>
);

// ─── Toggle group ─────────────────────────────────────────────────────────────
function ToggleGroup<T extends string>({
  label, options, value, onChange,
}: {
  label: string;
  options: { label: string; value: T }[];
  value: T;
  onChange: (v: T) => void;
}) {
  return (
    <View style={s.toggleRow}>
      <Text style={s.stepLabel}>{label}</Text>
      <View style={s.toggleGroup}>
        {options.map(o => (
          <TouchableOpacity
            key={o.value}
            style={[s.toggleOpt, value === o.value && s.toggleOptActive]}
            onPress={() => onChange(o.value)}
          >
            <Text style={[s.toggleOptTxt, value === o.value && s.toggleOptTxtActive]}>
              {o.label}
            </Text>
          </TouchableOpacity>
        ))}
      </View>
    </View>
  );
}

// ─── Breakdown bar row ───────────────────────────────────────────────────────
const BreakdownRow = ({
  icon, label, gal, totalGal,
}: { icon: string; label: string; gal: number; totalGal: number }) => {
  const p = pct(gal, totalGal);
  return (
    <View style={s.bkRow}>
      <Text style={s.bkIcon}>{icon}</Text>
      <View style={s.bkBody}>
        <View style={s.bkLabelRow}>
          <Text style={s.bkLabel}>{label}</Text>
          <Text style={s.bkVal}>{fmt2(gal)} gal ({p}%)</Text>
        </View>
        <View style={s.bkBarBg}>
          <View style={[s.bkBarFill, { width: `${p}%` as any }]} />
        </View>
      </View>
    </View>
  );
};

// ─── Main component ───────────────────────────────────────────────────────────
const PropaneUsageScreen: React.FC = () => {
  // ── Inputs ──
  const [outsideTempF,    setOutsideTempF]    = useState(35);
  const [nights,          setNights]          = useState(3);
  const [nightHours,      setNightHours]      = useState(DEFAULT_NIGHT_HOURS);
  const [rvLengthFt,      setRvLengthFt]      = useState(28);
  const [people,          setPeople]          = useState(2);
  const [showersPerDay,   setShowersPerDay]   = useState(1);
  const [showerMinutes,    setShowerMinutes]    = useState<'2'|'5'|'8'|'10'>('5');
  const [waterHeaterMode,  setWaterHeaterMode]  = useState<'propane'|'electric'|'both'>('propane');
  const [tankSizeLb,      setTankSizeLb]      = useState(40);
  const [tankFillPct,     setTankFillPct]     = useState(80);
  const [furnaceBTU,      setFurnaceBTU]      = useState(30_000);
  const [mealsPerDay,     setMealsPerDay]     = useState(2);
  const [fridgeMode,      setFridgeMode]      = useState<'propane'|'electric'>('electric');
  const [genHoursPerDay,  setGenHoursPerDay]  = useState(0);
  const [showAssumptions, setShowAssumptions] = useState(false);

  // ── Live calculation ──
  const inputs: PropaneInputs = {
    outsideTempF, nights, nightHours, rvLengthFt,
    people, showersPerDay, showerMinutes: parseInt(showerMinutes, 10), waterHeaterMode,
    tankSizeLb, tankFillPct,
    furnaceBTU, mealsPerDay, fridgeMode, genHoursPerDay,
  };
  const result: PropaneResult = useMemo(() => calcPropane(inputs), [
    outsideTempF, nights, nightHours, rvLengthFt,
    people, showersPerDay, showerMinutes, waterHeaterMode,
    tankSizeLb, tankFillPct,
    furnaceBTU, mealsPerDay, fridgeMode, genHoursPerDay,
  ]);

  const nightsColor =
    result.nightsRemaining >= nights       ? '#22c55e' :
    result.nightsRemaining >= nights * 0.7 ? '#f59e0b' : '#ef4444';

  const SHOWER_OPTS: { label: string; value: '2'|'5'|'8'|'10' }[] = [
    { label: '2 min',  value: '2'  },
    { label: '5 min',  value: '5'  },
    { label: '8 min',  value: '8'  },
    { label: '10 min', value: '10' },
  ];

  return (
    <ScrollView style={s.root} contentContainerStyle={s.content} showsVerticalScrollIndicator={false}>

      {/* Header */}
      <Text style={s.h1}>⛽ Propane Planner</Text>
      <Text style={s.subtitle}>How many nights will my propane last?</Text>

      {/* ── HERO RESULT ── */}
      <View style={s.heroCard}>
        <Text style={[s.heroNights, { color: nightsColor }]}>
          {isFinite(result.nightsRemaining) ? fmt1(result.nightsRemaining) : '∞'}
        </Text>
        <Text style={s.heroLabel}>nights remaining</Text>
        <Text style={s.heroSub}>
          {fmt2(result.totalGalPerNight)} gal/night · {fmt1(result.totalLbPerNight)} lb/night
        </Text>
        <View style={s.heroDivider} />
        <View style={s.heroRow}>
          <View style={s.heroStat}>
            <Text style={s.heroStatVal}>{fmt2(result.usableGal)}</Text>
            <Text style={s.heroStatLbl}>usable gal</Text>
          </View>
          <View style={s.heroStat}>
            <Text style={s.heroStatVal}>{fmt2(result.totalGalTrip)}</Text>
            <Text style={s.heroStatLbl}>trip needs (gal)</Text>
          </View>
          <View style={s.heroStat}>
            <Text style={s.heroStatVal}>{fmt1(result.totalLbTrip)}</Text>
            <Text style={s.heroStatLbl}>trip needs (lb)</Text>
          </View>
        </View>
      </View>

      {/* ── Low / Typical / High ── */}
      <View style={s.rangeCard}>
        <Text style={s.sectionTitle}>Range (±20%)</Text>
        <View style={s.rangeRow}>
          <View style={s.rangeStat}>
            <Text style={[s.rangeVal, { color: '#22c55e' }]}>{fmt2(result.lowGalPerNight)}</Text>
            <Text style={s.rangeLbl}>LOW gal/night</Text>
          </View>
          <View style={s.rangeStat}>
            <Text style={[s.rangeVal, { color: '#f59e0b' }]}>{fmt2(result.totalGalPerNight)}</Text>
            <Text style={s.rangeLbl}>TYPICAL</Text>
          </View>
          <View style={s.rangeStat}>
            <Text style={[s.rangeVal, { color: '#ef4444' }]}>{fmt2(result.highGalPerNight)}</Text>
            <Text style={s.rangeLbl}>HIGH gal/night</Text>
          </View>
        </View>
      </View>

      {/* ── Breakdown ── */}
      <View style={s.card}>
        <Text style={s.sectionTitle}>📊 Breakdown (per night)</Text>
        <BreakdownRow icon="🔥" label="Furnace"    gal={result.breakdown.furnaceGalPerNight}   totalGal={result.totalGalPerNight} />
        <BreakdownRow icon="🚿" label="Showers"    gal={result.breakdown.hotWaterGalPerNight}  totalGal={result.totalGalPerNight} />
        <BreakdownRow icon="🍳" label="Cooking"    gal={result.breakdown.cookGalPerNight}      totalGal={result.totalGalPerNight} />
        <BreakdownRow icon="❄️"  label="Fridge"     gal={result.breakdown.fridgeGalPerNight}    totalGal={result.totalGalPerNight} />
        <BreakdownRow icon="⚡"  label="Generator"  gal={result.breakdown.genGalPerNight}       totalGal={result.totalGalPerNight} />
      </View>

      {/* ── INPUTS ── */}

      {/* Trip & Weather */}
      <View style={s.card}>
        <Text style={s.sectionTitle}>🌡️ Trip & Weather</Text>
        <Stepper
          label="Outside temp (°F)"
          display={`${outsideTempF}°F`}
          onDec={() => setOutsideTempF(v => v - 5)}
          onInc={() => setOutsideTempF(v => v + 5)}
        />
        <Stepper
          label="Trip length (nights)"
          display={String(nights)}
          onDec={() => setNights(v => Math.max(1, v - 1))}
          onInc={() => setNights(v => v + 1)}
        />
        <Stepper
          label="Heating hours/night"
          display={String(nightHours)}
          onDec={() => setNightHours(v => Math.max(1, v - 1))}
          onInc={() => setNightHours(v => Math.min(24, v + 1))}
        />
      </View>

      {/* RV */}
      <View style={s.card}>
        <Text style={s.sectionTitle}>🚐 RV</Text>
        <Stepper
          label="RV length (ft)"
          display={`${rvLengthFt} ft`}
          onDec={() => setRvLengthFt(v => Math.max(10, v - 1))}
          onInc={() => setRvLengthFt(v => v + 1)}
        />
        <Stepper
          label="Furnace output"
          display={`${(furnaceBTU / 1000).toFixed(0)}k BTU`}
          onDec={() => setFurnaceBTU(v => Math.max(10_000, v - 5_000))}
          onInc={() => setFurnaceBTU(v => v + 5_000)}
        />
        <View style={s.infoRow}>
          <Ionicons name="information-circle-outline" size={14} color="#6b7280" />
          <Text style={s.infoTxt}>
            Calculated duty cycle: {Math.round(result.effectiveDuty * 100)}% (temp {outsideTempF}°F, length {rvLengthFt} ft)
          </Text>
        </View>
      </View>

      {/* People & Showers */}
      <View style={s.card}>
        <Text style={s.sectionTitle}>👥 People & Showers</Text>
        <Stepper
          label="People"
          display={String(people)}
          onDec={() => setPeople(v => Math.max(1, v - 1))}
          onInc={() => setPeople(v => v + 1)}
        />
        <Stepper
          label="Showers / person / day"
          display={fmt1(showersPerDay)}
          onDec={() => setShowersPerDay(v => Math.max(0, parseFloat(fmt1(v - 0.5))))}
          onInc={() => setShowersPerDay(v => parseFloat(fmt1(v + 0.5)))}
        />
        <ToggleGroup
          label="Shower duration"
          options={SHOWER_OPTS}
          value={showerMinutes}
          onChange={v => setShowerMinutes(v)}
        />
        <ToggleGroup
          label="Water heater"
          options={[
            { label: 'Propane',  value: 'propane'  },
            { label: 'Electric', value: 'electric' },
            { label: 'Both',     value: 'both'     },
          ]}
          value={waterHeaterMode}
          onChange={v => setWaterHeaterMode(v)}
        />
        {waterHeaterMode !== 'propane' && (
          <View style={s.infoRow}>
            <Ionicons name="information-circle-outline" size={14} color="#6b7280" />
            <Text style={s.infoTxt}>
              {waterHeaterMode === 'electric'
                ? 'On hookups with electric water heater? Showers use 0 propane.'
                : 'Half your hot water from electric, half from propane.'}
            </Text>
          </View>
        )}
      </View>

      {/* Tank */}
      <View style={s.card}>
        <Text style={s.sectionTitle}>🛢️ Propane Tank</Text>
        <Stepper
          label="Tank size (lb)"
          display={`${tankSizeLb} lb  (${fmt2(tankSizeLb / PROPANE_LB_PER_GAL)} gal)`}
          onDec={() => setTankSizeLb(v => Math.max(5, v - 5))}
          onInc={() => setTankSizeLb(v => v + 5)}
        />
        <Stepper
          label="Current fill level"
          display={`${tankFillPct}%`}
          onDec={() => setTankFillPct(v => Math.max(0, v - 5))}
          onInc={() => setTankFillPct(v => Math.min(100, v + 5))}
        />
      </View>

      {/* Appliances */}
      <View style={s.card}>
        <Text style={s.sectionTitle}>🔌 Appliances</Text>
        <Stepper
          label="Meals cooked / day"
          display={String(mealsPerDay)}
          onDec={() => setMealsPerDay(v => Math.max(0, v - 1))}
          onInc={() => setMealsPerDay(v => Math.min(5, v + 1))}
        />
        <ToggleGroup
          label="Fridge runs on"
          options={[
            { label: 'Electric', value: 'electric' },
            { label: 'Propane',  value: 'propane'  },
          ]}
          value={fridgeMode}
          onChange={v => setFridgeMode(v)}
        />
        <Stepper
          label="Generator (propane) hrs/day"
          display={String(genHoursPerDay)}
          onDec={() => setGenHoursPerDay(v => Math.max(0, v - 1))}
          onInc={() => setGenHoursPerDay(v => Math.min(8, v + 1))}
        />
      </View>

      {/* Assumptions accordion */}
      <TouchableOpacity
        style={s.accordionHeader}
        onPress={() => setShowAssumptions(v => !v)}
        activeOpacity={0.7}
      >
        <Text style={s.accordionTitle}>Assumptions & Constants</Text>
        <Ionicons
          name={showAssumptions ? 'chevron-up' : 'chevron-down'}
          size={16}
          color="#9ca3af"
        />
      </TouchableOpacity>
      {showAssumptions && (
        <View style={s.accordionBody}>
          {([
            ['PROPANE_BTU_PER_GAL',       '91,500 BTU/gal'],
            ['PROPANE_LB_PER_GAL',        '4.2 lb/gal'],
            ['HOT_WATER_BTU_PER_GAL_60F', '500 BTU/gal  (8.34 lb/gal × 60°F rise)'],
            ['DEFAULT_SHOWER_GPM',        '2.0 gal/min'],
            ['DEFAULT_HOT_MIX',           '60% hot water ratio'],
            ['MAX_DUTY_CYCLE',            '90%'],
            ['Cook propane',              '0.10 gal/meal'],
            ['Fridge (propane mode)',      '0.20 gal/day'],
            ['Generator (propane)',        '0.40 gal/hr'],
            ['Water heater (electric)',     '0% propane for showers'],
            ['Water heater (both)',         '50% propane for showers'],
          ] as [string, string][]).map(([k, v]) => (
            <View key={k} style={s.assumRow}>
              <Text style={s.assumKey}>{k}</Text>
              <Text style={s.assumVal}>{v}</Text>
            </View>
          ))}
        </View>
      )}

      <View style={{ height: 40 }} />
    </ScrollView>
  );
};

// ─── Styles ───────────────────────────────────────────────────────────────────
const s = StyleSheet.create({
  root:    { flex: 1, backgroundColor: '#0a0a0a' },
  content: { paddingHorizontal: 16, paddingTop: 20, paddingBottom: 40 },

  h1:       { fontSize: 26, fontWeight: '700', color: '#f9fafb', marginBottom: 4 },
  subtitle: { fontSize: 13, color: '#6b7280', marginBottom: 20 },

  // Hero
  heroCard: {
    backgroundColor: '#111827', borderRadius: 16, padding: 20,
    alignItems: 'center', marginBottom: 12,
    borderWidth: 1, borderColor: '#1f2937',
  },
  heroNights:  { fontSize: 64, fontWeight: '800', lineHeight: 72 },
  heroLabel:   { fontSize: 16, color: '#9ca3af', marginBottom: 4 },
  heroSub:     { fontSize: 13, color: '#6b7280', marginBottom: 12 },
  heroDivider: { width: '100%', height: 1, backgroundColor: '#1f2937', marginBottom: 12 },
  heroRow:     { flexDirection: 'row', gap: 24 },
  heroStat:    { alignItems: 'center' },
  heroStatVal: { fontSize: 18, fontWeight: '700', color: '#f3f4f6' },
  heroStatLbl: { fontSize: 10, color: '#6b7280', marginTop: 2 },

  // Range
  rangeCard: {
    backgroundColor: '#111827', borderRadius: 12, padding: 16,
    marginBottom: 12, borderWidth: 1, borderColor: '#1f2937',
  },
  rangeRow:  { flexDirection: 'row', justifyContent: 'space-around', marginTop: 8 },
  rangeStat: { alignItems: 'center' },
  rangeVal:  { fontSize: 20, fontWeight: '700' },
  rangeLbl:  { fontSize: 10, color: '#6b7280', marginTop: 2 },

  // Generic card
  card: {
    backgroundColor: '#111827', borderRadius: 12, padding: 16,
    marginBottom: 12, borderWidth: 1, borderColor: '#1f2937',
  },
  sectionTitle: { fontSize: 14, fontWeight: '600', color: '#e5e7eb', marginBottom: 12 },

  // Stepper
  stepRow:     { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 },
  stepLabel:   { fontSize: 13, color: '#d1d5db', flex: 1, flexShrink: 1, paddingRight: 8 },
  stepControls:{ flexDirection: 'row', alignItems: 'center', gap: 8 },
  stepBtn:     { width: 34, height: 34, borderRadius: 8, backgroundColor: '#1f2937', justifyContent: 'center', alignItems: 'center' },
  stepBtnTxt:  { color: '#f9fafb', fontSize: 20, fontWeight: '600', lineHeight: 24 },
  stepVal:     { minWidth: 90, textAlign: 'center', fontSize: 13, fontWeight: '600', color: '#f9fafb' },

  // Toggle
  toggleRow:         { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 },
  toggleGroup:       { flexDirection: 'row', gap: 6, flexWrap: 'wrap' },
  toggleOpt:         { paddingHorizontal: 10, paddingVertical: 6, borderRadius: 6, backgroundColor: '#1f2937', borderWidth: 1, borderColor: '#374151' },
  toggleOptActive:   { backgroundColor: '#22c55e', borderColor: '#22c55e' },
  toggleOptTxt:      { fontSize: 12, color: '#9ca3af', fontWeight: '500' },
  toggleOptTxtActive:{ color: '#fff' },

  // Info row
  infoRow: { flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: 4 },
  infoTxt: { fontSize: 11, color: '#6b7280', flex: 1 },

  // Breakdown
  bkRow:     { flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 10 },
  bkIcon:    { fontSize: 18, width: 24, textAlign: 'center' },
  bkBody:    { flex: 1 },
  bkLabelRow:{ flexDirection: 'row', justifyContent: 'space-between', marginBottom: 3 },
  bkLabel:   { fontSize: 12, color: '#d1d5db', fontWeight: '500' },
  bkVal:     { fontSize: 12, color: '#9ca3af' },
  bkBarBg:   { height: 6, backgroundColor: '#1f2937', borderRadius: 3, overflow: 'hidden' },
  bkBarFill: { height: 6, backgroundColor: '#22c55e', borderRadius: 3 },

  // Accordion
  accordionHeader: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    backgroundColor: '#111827', borderRadius: 12, padding: 16,
    marginBottom: 2, borderWidth: 1, borderColor: '#1f2937',
  },
  accordionTitle: { fontSize: 13, fontWeight: '500', color: '#9ca3af' },
  accordionBody:  {
    backgroundColor: '#0f172a', borderRadius: 12, padding: 16,
    marginBottom: 12, borderWidth: 1, borderColor: '#1f2937',
  },
  assumRow: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 5, borderBottomWidth: 1, borderBottomColor: '#1f2937' },
  assumKey: { fontSize: 11, color: '#9ca3af', flex: 1 },
  assumVal: { fontSize: 11, color: '#6b7280', flexShrink: 0, textAlign: 'right', marginLeft: 8 },
});

export default PropaneUsageScreen;
