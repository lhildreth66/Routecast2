/**
 * Road Passability Assessment Component
 * 
 * Example premium feature component that shows:
 * - How to use useRoadPassability hook
 * - How to handle premium gating / paywall
 * - How to display assessment results with risk visualization
 * 
 * This is intended as a reference implementation for integrating
 * road passability assessment into the Routecast app.
 */

import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ScrollView,
  ActivityIndicator,
  Alert,
} from 'react-native';
import { useRoadPassability } from '../hooks/useRoadPassability';
import { usePremium } from '../hooks/usePremium';
import PaywallModal from './PaywallModal';

const RoadPassabilityScreen: React.FC = () => {
  const { assess, loading, error, result, clearResult } =
    useRoadPassability();
  const { isPremium, subscriptionId } = usePremium();
  const [showPaywall, setShowPaywall] = useState(false);

  // Example soil type options
  const soilTypes = ['clay', 'sand', 'rocky', 'loam'];
  const [selectedSoilType, setSelectedSoilType] = useState('clay');

  // Example input values
  const [precip72h, setPrecip72h] = useState(30); // mm
  const [slopePct, setSlopePct] = useState(8); // %
  const [minTempF, setMinTempF] = useState(35); // °F

  const handleAssess = async () => {
    try {
      const response = await assess({
        precip_72h: precip72h,
        slope_pct: slopePct,
        min_temp_f: minTempF,
        soil_type: selectedSoilType,
        subscription_id: subscriptionId || undefined,
      });

      // Handle premium lock
      if (response.is_premium_locked) {
        setShowPaywall(true);
        return;
      }

      // Display results
      Alert.alert(
        'Road Passability Assessment',
        `Score: ${Math.round(response.passability_score)}\n${response.condition_assessment}\n\n${response.advisory}`
      );
    } catch (err) {
      Alert.alert(
        'Error',
        error || 'Failed to assess road conditions'
      );
    }
  };

  const getRiskColor = (isAtRisk: boolean): string => {
    return isAtRisk ? '#ef4444' : '#22c55e';
  };

  const getScoreColor = (score: number): string => {
    if (score >= 80) return '#22c55e'; // Green
    if (score >= 60) return '#3b82f6'; // Blue
    if (score >= 40) return '#f59e0b'; // Amber
    return '#ef4444'; // Red
  };

  return (
    <ScrollView style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <Text style={styles.title}>Road Passability Assessment</Text>
        <Text style={styles.subtitle}>
          Analyze mud, ice, and grade conditions
        </Text>
      </View>

      {/* Input Section */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Conditions</Text>

        {/* Precipitation */}
        <View style={styles.inputGroup}>
          <Text style={styles.label}>Precipitation (72h): {precip72h}mm</Text>
          <View style={styles.sliderSimulation}>
            <TouchableOpacity
              onPress={() => setPrecip72h(Math.max(0, precip72h - 10))}
            >
              <Text style={styles.button}>−</Text>
            </TouchableOpacity>
            <TouchableOpacity
              onPress={() => setPrecip72h(Math.min(100, precip72h + 10))}
            >
              <Text style={styles.button}>+</Text>
            </TouchableOpacity>
          </View>
          <Text style={styles.hint}>0 (dry) to 100+ (heavy rain)</Text>
        </View>

        {/* Slope */}
        <View style={styles.inputGroup}>
          <Text style={styles.label}>Road Slope: {slopePct}%</Text>
          <View style={styles.sliderSimulation}>
            <TouchableOpacity
              onPress={() => setSlopePct(Math.max(0, slopePct - 2))}
            >
              <Text style={styles.button}>−</Text>
            </TouchableOpacity>
            <TouchableOpacity
              onPress={() => setSlopePct(Math.min(40, slopePct + 2))}
            >
              <Text style={styles.button}>+</Text>
            </TouchableOpacity>
          </View>
          <Text style={styles.hint}>0 (flat) to 40% (very steep)</Text>
        </View>

        {/* Temperature */}
        <View style={styles.inputGroup}>
          <Text style={styles.label}>Min Temperature: {minTempF}°F</Text>
          <View style={styles.sliderSimulation}>
            <TouchableOpacity
              onPress={() => setMinTempF(Math.max(-40, minTempF - 5))}
            >
              <Text style={styles.button}>−</Text>
            </TouchableOpacity>
            <TouchableOpacity
              onPress={() => setMinTempF(Math.min(100, minTempF + 5))}
            >
              <Text style={styles.button}>+</Text>
            </TouchableOpacity>
          </View>
          <Text style={styles.hint}>Below 32°F increases ice risk</Text>
        </View>

        {/* Soil Type */}
        <View style={styles.inputGroup}>
          <Text style={styles.label}>Soil Type</Text>
          <View style={styles.soilTypeButtons}>
            {soilTypes.map((soil) => (
              <TouchableOpacity
                key={soil}
                style={[
                  styles.soilButton,
                  selectedSoilType === soil && styles.soilButtonActive,
                ]}
                onPress={() => setSelectedSoilType(soil)}
              >
                <Text
                  style={[
                    styles.soilButtonText,
                    selectedSoilType === soil &&
                      styles.soilButtonTextActive,
                  ]}
                >
                  {soil}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>
      </View>

      {/* Assess Button */}
      <TouchableOpacity
        style={[
          styles.assessButton,
          loading && styles.assessButtonDisabled,
        ]}
        onPress={handleAssess}
        disabled={loading}
      >
        {loading ? (
          <ActivityIndicator size="small" color="#fff" />
        ) : (
          <Text style={styles.assessButtonText}>Assess Road Conditions</Text>
        )}
      </TouchableOpacity>

      {/* Error Message */}
      {error && (
        <View style={styles.errorBox}>
          <Text style={styles.errorText}>⚠️ {error}</Text>
          {error.includes('premium') && (
            <TouchableOpacity
              style={styles.upgradeButton}
              onPress={() => setShowPaywall(true)}
            >
              <Text style={styles.upgradeButtonText}>
                Upgrade to Pro
              </Text>
            </TouchableOpacity>
          )}
        </View>
      )}

      {/* Results Section */}
      {result && !result.is_premium_locked && (
        <View style={styles.resultsSection}>
          <View
            style={[
              styles.scoreBox,
              {
                borderLeftColor: getScoreColor(result.passability_score),
              },
            ]}
          >
            <Text style={styles.scoreValue}>
              {Math.round(result.passability_score)}
            </Text>
            <Text style={styles.scoreLabel}>
              {result.condition_assessment}
            </Text>
          </View>

          <View style={styles.advisoryBox}>
            <Text style={styles.advisory}>{result.advisory}</Text>
          </View>

          {/* Risks Grid */}
          <View style={styles.risksGrid}>
            <View style={styles.riskItem}>
              <View
                style={[
                  styles.riskIndicator,
                  {
                    backgroundColor: getRiskColor(!result.risks.mud_risk),
                  },
                ]}
              />
              <Text style={styles.riskLabel}>
                {result.risks.mud_risk ? 'Mud Risk' : 'Good Drainage'}
              </Text>
            </View>

            <View style={styles.riskItem}>
              <View
                style={[
                  styles.riskIndicator,
                  {
                    backgroundColor: getRiskColor(!result.risks.ice_risk),
                  },
                ]}
              />
              <Text style={styles.riskLabel}>
                {result.risks.ice_risk ? 'Ice Risk' : 'No Ice Risk'}
              </Text>
            </View>

            <View style={styles.riskItem}>
              <View
                style={[
                  styles.riskIndicator,
                  {
                    backgroundColor: getRiskColor(
                      !result.risks.deep_rut_risk
                    ),
                  },
                ]}
              />
              <Text style={styles.riskLabel}>
                {result.risks.deep_rut_risk ? 'Rut Risk' : 'Good Traction'}
              </Text>
            </View>

            <View style={styles.riskItem}>
              <View
                style={[
                  styles.riskIndicator,
                  {
                    backgroundColor: getRiskColor(
                      !result.risks.high_clearance_recommended
                    ),
                  },
                ]}
              />
              <Text style={styles.riskLabel}>
                {result.risks.high_clearance_recommended
                  ? 'Clearance Needed'
                  : 'Standard Clearance'}
              </Text>
            </View>
          </View>

          {/* Recommendations */}
          <View style={styles.recommendationsBox}>
            <Text style={styles.recommendationsTitle}>Recommendations</Text>
            <View style={styles.recommendationItem}>
              <Text style={styles.recommendationLabel}>
                Vehicle Type:
              </Text>
              <Text style={styles.recommendationValue}>
                {result.recommended_vehicle_type.toUpperCase()}
              </Text>
            </View>
            <View style={styles.recommendationItem}>
              <Text style={styles.recommendationLabel}>
                Min Clearance:
              </Text>
              <Text style={styles.recommendationValue}>
                {Math.round(result.min_clearance_cm)} cm
              </Text>
            </View>
            <View style={styles.recommendationItem}>
              <Text style={styles.recommendationLabel}>4WD Needed:</Text>
              <Text style={styles.recommendationValue}>
                {result.needs_four_x_four ? '✅ Yes' : '❌ No'}
              </Text>
            </View>
          </View>

          {/* Clear Button */}
          <TouchableOpacity
            style={styles.clearButton}
            onPress={clearResult}
          >
            <Text style={styles.clearButtonText}>Clear Results</Text>
          </TouchableOpacity>
        </View>
      )}

      {/* Paywall Modal */}
      <PaywallModal
        visible={showPaywall}
        onClose={() => setShowPaywall(false)}
      />
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#fff',
    padding: 20,
  },
  header: {
    marginBottom: 30,
  },
  title: {
    fontSize: 24,
    fontWeight: '700',
    marginBottom: 8,
    color: '#000',
  },
  subtitle: {
    fontSize: 14,
    color: '#666',
  },
  section: {
    marginBottom: 30,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: '600',
    marginBottom: 16,
    color: '#000',
  },
  inputGroup: {
    marginBottom: 20,
  },
  label: {
    fontSize: 14,
    fontWeight: '500',
    marginBottom: 8,
    color: '#333',
  },
  hint: {
    fontSize: 12,
    color: '#999',
    marginTop: 4,
  },
  sliderSimulation: {
    flexDirection: 'row',
    gap: 8,
  },
  button: {
    backgroundColor: '#f3f4f6',
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 6,
    fontSize: 18,
    fontWeight: '600',
  },
  soilTypeButtons: {
    flexDirection: 'row',
    gap: 8,
    flexWrap: 'wrap',
  },
  soilButton: {
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 6,
    borderWidth: 1,
    borderColor: '#e5e7eb',
    backgroundColor: '#f9fafb',
  },
  soilButtonActive: {
    backgroundColor: '#3b82f6',
    borderColor: '#3b82f6',
  },
  soilButtonText: {
    fontSize: 12,
    fontWeight: '500',
    color: '#666',
    textTransform: 'capitalize',
  },
  soilButtonTextActive: {
    color: '#fff',
  },
  assessButton: {
    backgroundColor: '#3b82f6',
    paddingVertical: 14,
    borderRadius: 8,
    alignItems: 'center',
    marginBottom: 20,
  },
  assessButtonDisabled: {
    opacity: 0.6,
  },
  assessButtonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '600',
  },
  errorBox: {
    backgroundColor: '#fee2e2',
    borderLeftWidth: 4,
    borderLeftColor: '#ef4444',
    padding: 12,
    borderRadius: 6,
    marginBottom: 20,
  },
  errorText: {
    color: '#991b1b',
    fontSize: 14,
    marginBottom: 8,
  },
  upgradeButton: {
    backgroundColor: '#ef4444',
    paddingVertical: 8,
    paddingHorizontal: 12,
    borderRadius: 4,
    alignSelf: 'flex-start',
  },
  upgradeButtonText: {
    color: '#fff',
    fontSize: 12,
    fontWeight: '600',
  },
  resultsSection: {
    marginBottom: 40,
  },
  scoreBox: {
    backgroundColor: '#f9fafb',
    borderLeftWidth: 4,
    padding: 16,
    borderRadius: 6,
    marginBottom: 16,
    alignItems: 'center',
  },
  scoreValue: {
    fontSize: 36,
    fontWeight: '700',
    color: '#000',
  },
  scoreLabel: {
    fontSize: 14,
    fontWeight: '600',
    color: '#666',
    marginTop: 4,
  },
  advisoryBox: {
    backgroundColor: '#fffbeb',
    borderLeftWidth: 4,
    borderLeftColor: '#f59e0b',
    padding: 12,
    borderRadius: 6,
    marginBottom: 16,
  },
  advisory: {
    fontSize: 14,
    color: '#78350f',
    fontWeight: '500',
  },
  risksGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
    marginBottom: 20,
  },
  riskItem: {
    flex: 1,
    minWidth: '45%',
    alignItems: 'center',
    padding: 8,
  },
  riskIndicator: {
    width: 24,
    height: 24,
    borderRadius: 12,
    marginBottom: 4,
  },
  riskLabel: {
    fontSize: 12,
    fontWeight: '500',
    color: '#666',
    textAlign: 'center',
  },
  recommendationsBox: {
    backgroundColor: '#ecf0ff',
    padding: 16,
    borderRadius: 6,
    marginBottom: 16,
  },
  recommendationsTitle: {
    fontSize: 14,
    fontWeight: '600',
    marginBottom: 12,
    color: '#1e3a8a',
  },
  recommendationItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 6,
  },
  recommendationLabel: {
    fontSize: 13,
    color: '#1e3a8a',
    fontWeight: '500',
  },
  recommendationValue: {
    fontSize: 13,
    color: '#1e40af',
    fontWeight: '600',
  },
  clearButton: {
    borderWidth: 1,
    borderColor: '#e5e7eb',
    paddingVertical: 12,
    borderRadius: 6,
    alignItems: 'center',
  },
  clearButtonText: {
    color: '#666',
    fontSize: 14,
    fontWeight: '600',
  },
});

export default RoadPassabilityScreen;
