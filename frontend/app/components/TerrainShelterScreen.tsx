/**
 * TerrainShelterScreen - React Native Component for Terrain Shade & Wind Shelter
 *
 * Complete UI for solar exposure and wind shelter planning with terrain consideration.
 * Integrates both terrain shade (solar path, tree canopy) and wind shelter (orientation)
 * features with results visualization and premium paywall.
 *
 * Usage in navigation:
 * ```typescript
 * <Stack.Screen
 *   name="terrain-shelter"
 *   component={TerrainShelterScreen}
 *   options={{ title: '☀️ Terrain Shelter' }}
 * />
 * ```
 */

import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  Alert,
  ActivityIndicator,
  ScrollView,
  TouchableOpacity,
  Dimensions,
  TextInput,
  Switch,
} from 'react-native';
import { useTerrainShade } from '../hooks/useTerrainShade';
import { useWindShelter } from '../hooks/useWindShelter';
import { usePremium } from '../hooks/usePremium';
import PaywallModal from './PaywallModal';

const COLORS = {
  primary: '#fbbf24',      // Amber (sun)
  secondary: '#10b981',    // Emerald (shelter)
  warning: '#f59e0b',      // Amber
  danger: '#ef4444',       // Red
  background: '#f9fafb',   // Light gray
  surface: '#ffffff',      // White
  border: '#e5e7eb',       // Border gray
  text: '#1f2937',         // Dark text
  textSecondary: '#6b7280', // Light text
};

const WIND_DIRECTIONS = [
  { label: 'N', value: 0 },
  { label: 'NE', value: 45 },
  { label: 'E', value: 90 },
  { label: 'SE', value: 135 },
  { label: 'S', value: 180 },
  { label: 'SW', value: 225 },
  { label: 'W', value: 270 },
  { label: 'NW', value: 315 },
];

const RIDGE_STRENGTHS = ['low', 'med', 'high'];

const TerrainShelterScreen: React.FC = () => {
  // Hooks
  const { estimate: estimateShade, loading: shadeLoading, result: shadeResult } = useTerrainShade();
  const { estimate: estimateWind, loading: windLoading, result: windResult } = useWindShelter();
  const { subscriptionId } = usePremium?.() || { subscriptionId: null };

  // Terrain Shade State
  const [latitude, setLatitude] = useState('40.7128');
  const [longitude, setLongitude] = useState('-105.1084');
  const [date, setDate] = useState(new Date().toISOString().split('T')[0]);
  const [canopyPct, setCanopyPct] = useState(50);
  const [obstructionDeg, setObstructionDeg] = useState(15);

  // Wind Shelter State
  const [windDirectionIdx, setWindDirectionIdx] = useState(2); // E = 90°
  const [gustMph, setGustMph] = useState(25);
  const [ridges, setRidges] = useState<Array<{ bearing: number; strength: string; name: string }>>([
    { bearing: 0, strength: 'high', name: 'North ridge' },
  ]);
  const [newRidgeBearing, setNewRidgeBearing] = useState('90');
  const [newRidgeStrength, setNewRidgeStrength] = useState('med');
  const [newRidgeName, setNewRidgeName] = useState('');

  // UI State
  const [activeTab, setActiveTab] = useState<'shade' | 'wind'>('shade');
  const [showPaywall, setShowPaywall] = useState(false);
  const [paywallFeature, setPaywallFeature] = useState<'shade' | 'wind'>('shade');

  // Handle terrain shade estimation
  const handleEstimateShade = async () => {
    const lat = parseFloat(latitude);
    const lon = parseFloat(longitude);

    if (isNaN(lat) || isNaN(lon)) {
      Alert.alert('Invalid Input', 'Please enter valid latitude and longitude');
      return;
    }

    const response = await estimateShade({
      latitude: lat,
      longitude: lon,
      date,
      tree_canopy_pct: canopyPct,
      horizon_obstruction_deg: obstructionDeg,
      subscription_id: subscriptionId || undefined,
    });

    if (response?.is_premium_locked) {
      setPaywallFeature('shade');
      setShowPaywall(true);
    }
  };

  // Handle wind shelter estimation
  const handleEstimateWind = async () => {
    const gustNum = parseInt(gustMph.toString());
    if (isNaN(gustNum)) {
      Alert.alert('Invalid Input', 'Please enter valid gust speed');
      return;
    }

    const response = await estimateWind({
      predominant_dir_deg: WIND_DIRECTIONS[windDirectionIdx].value,
      gust_mph: gustNum,
      local_ridges: ridges.map((r) => ({
        bearing_deg: r.bearing,
        strength: r.strength as 'low' | 'med' | 'high',
        name: r.name,
      })),
      subscription_id: subscriptionId || undefined,
    });

    if (response?.is_premium_locked) {
      setPaywallFeature('wind');
      setShowPaywall(true);
    }
  };

  // Add new ridge
  const handleAddRidge = () => {
    const bearing = parseInt(newRidgeBearing);
    if (isNaN(bearing) || bearing < 0 || bearing > 360) {
      Alert.alert('Invalid Bearing', 'Enter bearing 0-360°');
      return;
    }

    setRidges([
      ...ridges,
      {
        bearing,
        strength: newRidgeStrength,
        name: newRidgeName || `Ridge at ${bearing}°`,
      },
    ]);

    setNewRidgeBearing('0');
    setNewRidgeStrength('med');
    setNewRidgeName('');
  };

  // Remove ridge
  const handleRemoveRidge = (index: number) => {
    setRidges(ridges.filter((_, i) => i !== index));
  };

  // Render shade factor color
  const getShadeFactor = () => {
    if (!shadeResult?.shade_factor) return null;
    const factor = shadeResult.shade_factor;
    if (factor < 0.2) return { text: 'Excellent', color: COLORS.primary };
    if (factor < 0.5) return { text: 'Good', color: '#10b981' };
    if (factor < 0.8) return { text: 'Limited', color: COLORS.warning };
    return { text: 'Heavy', color: COLORS.danger };
  };

  // Render risk level color
  const getRiskColor = () => {
    if (!windResult?.risk_level) return COLORS.textSecondary;
    if (windResult.risk_level === 'low') return '#10b981';
    if (windResult.risk_level === 'medium') return COLORS.warning;
    return COLORS.danger;
  };

  const loading = shadeLoading || windLoading;
  const shade = shadeResult && !shadeResult.is_premium_locked ? shadeResult : null;
  const wind = windResult && !windResult.is_premium_locked ? windResult : null;

  return (
    <View style={styles.container}>
      <ScrollView style={styles.scrollView} showsVerticalScrollIndicator={false}>
        {/* Tab Navigation */}
        <View style={styles.tabContainer}>
          <TouchableOpacity
            style={[
              styles.tab,
              activeTab === 'shade' && styles.activeTab,
            ]}
            onPress={() => setActiveTab('shade')}
          >
            <Text style={[
              styles.tabText,
              activeTab === 'shade' && styles.activeTabText,
            ]}>
              ☀️ Shade
            </Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[
              styles.tab,
              activeTab === 'wind' && styles.activeTab,
            ]}
            onPress={() => setActiveTab('wind')}
          >
            <Text style={[
              styles.tabText,
              activeTab === 'wind' && styles.activeTabText,
            ]}>
              💨 Wind
            </Text>
          </TouchableOpacity>
        </View>

        {/* Shade Tab */}
        {activeTab === 'shade' && (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Solar Path & Shade Blocking</Text>
            <Text style={styles.subtitle}>
              Analyze sunlight availability for boondocking with terrain obstruction
            </Text>

            {/* Location Input */}
            <View style={styles.inputGroup}>
              <Text style={styles.label}>Latitude</Text>
              <TextInput
                style={styles.input}
                placeholder="40.7128"
                value={latitude}
                onChangeText={setLatitude}
                keyboardType="decimal-pad"
              />
            </View>

            <View style={styles.inputGroup}>
              <Text style={styles.label}>Longitude</Text>
              <TextInput
                style={styles.input}
                placeholder="-105.1084"
                value={longitude}
                onChangeText={setLongitude}
                keyboardType="decimal-pad"
              />
            </View>

            <View style={styles.inputGroup}>
              <Text style={styles.label}>Date: {date}</Text>
              <Text style={styles.hint}>Today's date in YYYY-MM-DD format</Text>
              <TextInput
                style={styles.input}
                placeholder="2024-06-21"
                value={date}
                onChangeText={setDate}
              />
            </View>

            {/* Sliders */}
            <View style={styles.inputGroup}>
              <View style={styles.sliderHeader}>
                <Text style={styles.label}>Tree Canopy Coverage</Text>
                <Text style={styles.sliderValue}>{canopyPct}%</Text>
              </View>
              <View style={styles.sliderTrack}>
                <View
                  style={[
                    styles.sliderFill,
                    { width: `${canopyPct}%` },
                  ]}
                />
              </View>
              <View style={styles.sliderButtons}>
                {[0, 25, 50, 75, 100].map((val) => (
                  <TouchableOpacity
                    key={val}
                    style={[
                      styles.sliderButton,
                      canopyPct === val && styles.sliderButtonActive,
                    ]}
                    onPress={() => setCanopyPct(val)}
                  >
                    <Text style={styles.sliderButtonText}>{val}</Text>
                  </TouchableOpacity>
                ))}
              </View>
            </View>

            <View style={styles.inputGroup}>
              <View style={styles.sliderHeader}>
                <Text style={styles.label}>Horizon Obstruction</Text>
                <Text style={styles.sliderValue}>{obstructionDeg}°</Text>
              </View>
              <View style={styles.sliderTrack}>
                <View
                  style={[
                    styles.sliderFill,
                    { width: `${(obstructionDeg / 90) * 100}%` },
                  ]}
                />
              </View>
              <View style={styles.sliderButtons}>
                {[0, 15, 30, 60, 90].map((val) => (
                  <TouchableOpacity
                    key={val}
                    style={[
                      styles.sliderButton,
                      obstructionDeg === val && styles.sliderButtonActive,
                    ]}
                    onPress={() => setObstructionDeg(val)}
                  >
                    <Text style={styles.sliderButtonText}>{val}</Text>
                  </TouchableOpacity>
                ))}
              </View>
            </View>

            {/* Estimate Button */}
            <TouchableOpacity
              style={[styles.button, styles.primaryButton]}
              onPress={handleEstimateShade}
              disabled={shadeLoading}
            >
              {shadeLoading ? (
                <ActivityIndicator color="#fff" />
              ) : (
                <Text style={styles.buttonText}>Calculate Solar Path</Text>
              )}
            </TouchableOpacity>

            {/* Results */}
            {shade && (
              <View style={styles.resultsContainer}>
                <Text style={styles.resultsTitle}>Solar Path Results</Text>

                {/* Shade Factor Card */}
                <View style={[styles.card, { borderLeftColor: COLORS.primary, borderLeftWidth: 4 }]}>
                  <Text style={styles.cardLabel}>Shade Factor</Text>
                  <View style={styles.resultRow}>
                    <Text style={[styles.resultValue, { color: getShadeFactor()?.color }]}>
                      {(shade.shade_factor * 100).toFixed(1)}%
                    </Text>
                    <Text style={styles.resultLabel}>
                      {getShadeFactor()?.text} Solar Exposure
                    </Text>
                  </View>
                  <Text style={styles.hint}>
                    {shade.shade_factor < 0.3
                      ? '✓ Excellent for solar panels'
                      : shade.shade_factor < 0.6
                      ? '○ Moderate for solar panels'
                      : '✗ Limited solar viability'}
                  </Text>
                </View>

                {/* Exposure Hours */}
                {shade.exposure_hours !== undefined && (
                  <View style={[styles.card, { borderLeftColor: COLORS.secondary, borderLeftWidth: 4 }]}>
                    <Text style={styles.cardLabel}>Effective Sunlight</Text>
                    <Text style={styles.resultValue}>
                      {shade.exposure_hours.toFixed(1)} hours
                    </Text>
                    <Text style={styles.hint}>
                      Daily exposure after shade obstruction
                    </Text>
                  </View>
                )}

                {/* Solar Path Slots */}
                {shade.sun_path_slots && shade.sun_path_slots.length > 0 && (
                  <View style={[styles.card, { borderLeftColor: '#f59e0b', borderLeftWidth: 4 }]}>
                    <Text style={styles.cardLabel}>Hourly Solar Elevation</Text>
                    <ScrollView horizontal showsHorizontalScrollIndicator={false}>
                      <View style={styles.slotsContainer}>
                        {shade.sun_path_slots.map((slot, idx) => (
                          <View key={idx} style={styles.slotCard}>
                            <Text style={styles.slotTime}>{slot.time_label}</Text>
                            <Text style={styles.slotValue}>
                              {slot.sun_elevation_deg.toFixed(0)}°
                            </Text>
                            <Text style={styles.slotLabel}>
                              {slot.usable_sunlight_fraction > 0.8
                                ? '☀️'
                                : slot.usable_sunlight_fraction > 0.5
                                ? '◐'
                                : '◑'}
                            </Text>
                          </View>
                        ))}
                      </View>
                    </ScrollView>
                  </View>
                )}
              </View>
            )}
          </View>
        )}

        {/* Wind Tab */}
        {activeTab === 'wind' && (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Wind Shelter Orientation</Text>
            <Text style={styles.subtitle}>
              Optimize RV positioning using local ridge terrain for wind protection
            </Text>

            {/* Wind Direction Selection */}
            <View style={styles.inputGroup}>
              <Text style={styles.label}>Predominant Wind Direction</Text>
              <View style={styles.directionGrid}>
                {WIND_DIRECTIONS.map((dir, idx) => (
                  <TouchableOpacity
                    key={idx}
                    style={[
                      styles.directionButton,
                      windDirectionIdx === idx && styles.directionButtonActive,
                    ]}
                    onPress={() => setWindDirectionIdx(idx)}
                  >
                    <Text style={[
                      styles.directionText,
                      windDirectionIdx === idx && styles.directionTextActive,
                    ]}>
                      {dir.label}
                    </Text>
                  </TouchableOpacity>
                ))}
              </View>
            </View>

            {/* Gust Speed */}
            <View style={styles.inputGroup}>
              <View style={styles.sliderHeader}>
                <Text style={styles.label}>Gust Speed</Text>
                <Text style={styles.sliderValue}>{gustMph} mph</Text>
              </View>
              <View style={styles.sliderButtons}>
                {[10, 15, 20, 25, 30, 35, 40].map((val) => (
                  <TouchableOpacity
                    key={val}
                    style={[
                      styles.sliderButton,
                      Number(gustMph) === val && styles.sliderButtonActive,
                    ]}
                    onPress={() => setGustMph(val)}
                  >
                    <Text style={styles.sliderButtonText}>{val}</Text>
                  </TouchableOpacity>
                ))}
              </View>
            </View>

            {/* Local Ridges */}
            <View style={styles.inputGroup}>
              <Text style={styles.label}>Local Ridge Terrain</Text>
              {ridges.map((ridge, idx) => (
                <View key={idx} style={styles.ridgeCard}>
                  <View style={styles.ridgeInfo}>
                    <Text style={styles.ridgeText}>
                      {ridge.bearing}° {ridge.name} ({ridge.strength})
                    </Text>
                  </View>
                  <TouchableOpacity
                    onPress={() => handleRemoveRidge(idx)}
                    style={styles.removeButton}
                  >
                    <Text style={styles.removeButtonText}>✕</Text>
                  </TouchableOpacity>
                </View>
              ))}

              {/* Add Ridge Form */}
              <View style={styles.addRidgeForm}>
                <TextInput
                  style={[styles.input, styles.smallInput]}
                  placeholder="Bearing (0-360°)"
                  value={newRidgeBearing}
                  onChangeText={setNewRidgeBearing}
                  keyboardType="number-pad"
                />
                <View style={styles.strengthPicker}>
                  {RIDGE_STRENGTHS.map((str) => (
                    <TouchableOpacity
                      key={str}
                      style={[
                        styles.strengthButton,
                        newRidgeStrength === str && styles.strengthButtonActive,
                      ]}
                      onPress={() => setNewRidgeStrength(str)}
                    >
                      <Text style={[
                        styles.strengthText,
                        newRidgeStrength === str && styles.strengthTextActive,
                      ]}>
                        {str.charAt(0).toUpperCase() + str.slice(1)}
                      </Text>
                    </TouchableOpacity>
                  ))}
                </View>
                <TextInput
                  style={[styles.input, styles.smallInput]}
                  placeholder="Ridge name"
                  value={newRidgeName}
                  onChangeText={setNewRidgeName}
                />
                <TouchableOpacity
                  style={[styles.button, styles.secondaryButton]}
                  onPress={handleAddRidge}
                >
                  <Text style={styles.secondaryButtonText}>+ Add Ridge</Text>
                </TouchableOpacity>
              </View>
            </View>

            {/* Estimate Button */}
            <TouchableOpacity
              style={[styles.button, styles.primaryButton]}
              onPress={handleEstimateWind}
              disabled={windLoading}
            >
              {windLoading ? (
                <ActivityIndicator color="#fff" />
              ) : (
                <Text style={styles.buttonText}>Recommend Orientation</Text>
              )}
            </TouchableOpacity>

            {/* Results */}
            {wind && (
              <View style={styles.resultsContainer}>
                <Text style={styles.resultsTitle}>Wind Shelter Results</Text>

                {/* Risk Level */}
                <View style={[styles.card, { borderLeftColor: getRiskColor(), borderLeftWidth: 4 }]}>
                  <Text style={styles.cardLabel}>Wind Risk Level</Text>
                  <Text style={[styles.resultValue, { color: getRiskColor() }]}>
                    {wind.risk_level ? wind.risk_level.charAt(0).toUpperCase() + wind.risk_level.slice(1) : 'Unknown'}
                  </Text>
                </View>

                {/* Recommended Bearing */}
                <View style={[styles.card, { borderLeftColor: COLORS.secondary, borderLeftWidth: 4 }]}>
                  <Text style={styles.cardLabel}>Recommended RV Bearing</Text>
                  <Text style={styles.resultValue}>
                    {wind.recommended_bearing_deg}°
                  </Text>
                  <Text style={styles.hint}>Direction RV front should face</Text>
                </View>

                {/* Shelter Info */}
                {wind.shelter_available && (
                  <View style={[styles.card, { borderLeftColor: '#10b981', borderLeftWidth: 4 }]}>
                    <Text style={styles.cardLabel}>Shelter Available</Text>
                    <Text style={styles.hint}>✓ Local terrain provides wind protection</Text>
                    {wind.estimated_wind_reduction_pct !== undefined && (
                      <Text style={styles.cardValue}>
                        ~{wind.estimated_wind_reduction_pct}% Wind Reduction
                      </Text>
                    )}
                  </View>
                )}

                {/* Rationale */}
                {wind.rationale_text && (
                  <View style={[styles.card, { backgroundColor: '#f0fdf4' }]}>
                    <Text style={styles.cardLabel}>Recommendation</Text>
                    <Text style={styles.rationale}>{wind.rationale_text}</Text>
                  </View>
                )}
              </View>
            )}
          </View>
        )}
      </ScrollView>

      {/* Paywall Modal */}
      <PaywallModal
        visible={showPaywall}
        onClose={() => setShowPaywall(false)}
        feature={`Terrain Shelter (${paywallFeature === 'shade' ? 'Solar Analysis' : 'Wind Optimization'})`}
      />
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: COLORS.background,
  },
  scrollView: {
    flex: 1,
  },
  section: {
    paddingHorizontal: 16,
    paddingVertical: 20,
  },
  sectionTitle: {
    fontSize: 22,
    fontWeight: 'bold',
    color: COLORS.text,
    marginBottom: 8,
  },
  subtitle: {
    fontSize: 14,
    color: COLORS.textSecondary,
    marginBottom: 20,
  },
  tabContainer: {
    flexDirection: 'row',
    borderBottomWidth: 1,
    borderBottomColor: COLORS.border,
    backgroundColor: COLORS.surface,
  },
  tab: {
    flex: 1,
    paddingVertical: 16,
    alignItems: 'center',
    borderBottomWidth: 3,
    borderBottomColor: 'transparent',
  },
  activeTab: {
    borderBottomColor: COLORS.primary,
  },
  tabText: {
    fontSize: 14,
    fontWeight: '600',
    color: COLORS.textSecondary,
  },
  activeTabText: {
    color: COLORS.primary,
  },
  inputGroup: {
    marginBottom: 20,
  },
  label: {
    fontSize: 14,
    fontWeight: '600',
    color: COLORS.text,
    marginBottom: 8,
  },
  hint: {
    fontSize: 12,
    color: COLORS.textSecondary,
    marginTop: 4,
  },
  input: {
    borderWidth: 1,
    borderColor: COLORS.border,
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 14,
    backgroundColor: COLORS.surface,
    color: COLORS.text,
  },
  smallInput: {
    marginBottom: 8,
  },
  sliderHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  sliderValue: {
    fontSize: 16,
    fontWeight: 'bold',
    color: COLORS.primary,
  },
  sliderTrack: {
    height: 6,
    backgroundColor: COLORS.border,
    borderRadius: 3,
    overflow: 'hidden',
    marginBottom: 12,
  },
  sliderFill: {
    height: '100%',
    backgroundColor: COLORS.primary,
  },
  sliderButtons: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  sliderButton: {
    paddingHorizontal: 8,
    paddingVertical: 6,
    borderRadius: 6,
    borderWidth: 1,
    borderColor: COLORS.border,
    backgroundColor: COLORS.surface,
  },
  sliderButtonActive: {
    backgroundColor: COLORS.primary,
    borderColor: COLORS.primary,
  },
  sliderButtonText: {
    fontSize: 12,
    fontWeight: '600',
    color: COLORS.text,
  },
  directionGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'space-between',
  },
  directionButton: {
    width: '23%',
    aspectRatio: 1,
    borderRadius: 8,
    borderWidth: 2,
    borderColor: COLORS.border,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 8,
    backgroundColor: COLORS.surface,
  },
  directionButtonActive: {
    borderColor: COLORS.secondary,
    backgroundColor: COLORS.secondary,
  },
  directionText: {
    fontSize: 16,
    fontWeight: '700',
    color: COLORS.text,
  },
  directionTextActive: {
    color: COLORS.surface,
  },
  strengthPicker: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 8,
  },
  strengthButton: {
    flex: 1,
    marginHorizontal: 4,
    paddingVertical: 8,
    borderRadius: 6,
    borderWidth: 1,
    borderColor: COLORS.border,
    backgroundColor: COLORS.surface,
    alignItems: 'center',
  },
  strengthButtonActive: {
    backgroundColor: COLORS.secondary,
    borderColor: COLORS.secondary,
  },
  strengthText: {
    fontSize: 12,
    fontWeight: '600',
    color: COLORS.text,
  },
  strengthTextActive: {
    color: COLORS.surface,
  },
  addRidgeForm: {
    marginTop: 12,
  },
  ridgeCard: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    backgroundColor: COLORS.surface,
    borderWidth: 1,
    borderColor: COLORS.border,
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 10,
    marginBottom: 8,
  },
  ridgeInfo: {
    flex: 1,
  },
  ridgeText: {
    fontSize: 14,
    fontWeight: '500',
    color: COLORS.text,
  },
  removeButton: {
    paddingHorizontal: 8,
    paddingVertical: 4,
  },
  removeButtonText: {
    fontSize: 18,
    color: COLORS.danger,
    fontWeight: 'bold',
  },
  button: {
    borderRadius: 8,
    paddingVertical: 12,
    paddingHorizontal: 16,
    alignItems: 'center',
    marginTop: 12,
  },
  primaryButton: {
    backgroundColor: COLORS.primary,
  },
  secondaryButton: {
    backgroundColor: COLORS.secondary,
  },
  buttonText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#fff',
  },
  secondaryButtonText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#fff',
  },
  resultsContainer: {
    marginTop: 24,
  },
  resultsTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: COLORS.text,
    marginBottom: 12,
  },
  card: {
    backgroundColor: COLORS.surface,
    borderRadius: 8,
    padding: 12,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  cardLabel: {
    fontSize: 12,
    fontWeight: '600',
    color: COLORS.textSecondary,
    textTransform: 'uppercase',
    marginBottom: 8,
  },
  cardValue: {
    fontSize: 14,
    fontWeight: '600',
    color: COLORS.secondary,
    marginTop: 8,
  },
  resultRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 8,
  },
  resultValue: {
    fontSize: 28,
    fontWeight: 'bold',
    marginRight: 12,
  },
  resultLabel: {
    fontSize: 14,
    color: COLORS.textSecondary,
  },
  slotsContainer: {
    flexDirection: 'row',
    paddingVertical: 8,
  },
  slotCard: {
    alignItems: 'center',
    marginRight: 12,
    paddingHorizontal: 8,
    paddingVertical: 8,
    backgroundColor: '#fffbeb',
    borderRadius: 6,
    minWidth: 60,
  },
  slotTime: {
    fontSize: 11,
    fontWeight: '600',
    color: COLORS.textSecondary,
    marginBottom: 4,
  },
  slotValue: {
    fontSize: 14,
    fontWeight: 'bold',
    color: COLORS.primary,
    marginBottom: 4,
  },
  slotLabel: {
    fontSize: 12,
  },
  rationale: {
    fontSize: 13,
    color: COLORS.text,
    lineHeight: 18,
    marginTop: 8,
  },
});

export default TerrainShelterScreen;
