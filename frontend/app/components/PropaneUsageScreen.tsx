"""
PropaneUsageScreen - React Native Component for Propane Consumption Estimation

Complete UI for propane usage estimation with inputs, results visualization,
and premium paywall integration.

Usage in navigation:
```typescript
<Stack.Screen
  name="propane-usage"
  component={PropaneUsageScreen}
  options={{ title: '🔥 Propane Usage' }}
/>
```
"""

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
} from 'react-native';
import { usePropaneUsage } from '../hooks/usePropaneUsage';
import { usePremium } from '../hooks/usePremium'; // Assuming this exists for subscription info
import PaywallModal from './PaywallModal'; // Premium paywall UI

const COLORS = {
  primary: '#22c55e',      // Green
  secondary: '#3b82f6',    // Blue
  warning: '#f59e0b',      // Amber
  danger: '#ef4444',       // Red
  background: '#f9fafb',   // Light gray
  surface: '#ffffff',      // White
  border: '#e5e7eb',       // Border gray
  text: '#1f2937',         // Dark text
  textSecondary: '#6b7280', // Light text
};

const PropaneUsageScreen: React.FC = () => {
  // Hooks
  const { estimate, loading, error, result, clearResult } = usePropaneUsage();
  const { subscriptionId } = usePremium?.() || { subscriptionId: null };

  // State for inputs
  const [furnaceBTU, setFurnaceBTU] = useState(20000);
  const [dutyCyclePct, setDutyCyclePct] = useState(50);
  const [people, setPeople] = useState(2);
  const [nights, setNights] = useState<number[]>([35, 35, 35]);
  const [tempInput, setTempInput] = useState('35');
  const [showPaywall, setShowPaywall] = useState(false);

  // Furnace preset options
  const FURNACE_PRESETS = [
    { label: 'Small (10k)', value: 10000 },
    { label: 'Standard (20k)', value: 20000 },
    { label: 'Large (30k)', value: 30000 },
    { label: 'Extra Large (40k)', value: 40000 },
  ];

  // Temperature adjustment helpers
  const addTemperature = () => {
    const temp = parseInt(tempInput, 10);
    if (!isNaN(temp) && temp >= -50 && temp <= 110) {
      setNights([...nights, temp]);
    } else {
      Alert.alert('Invalid Temperature', 'Please enter a value between -50°F and 110°F');
    }
  };

  const removeTemperature = (index: number) => {
    const updated = nights.filter((_, i) => i !== index);
    setNights(updated);
  };

  const updateTemperature = (index: number, value: string) => {
    const temp = parseInt(value, 10);
    if (!isNaN(temp)) {
      const updated = [...nights];
      updated[index] = temp;
      setNights(updated);
    }
  };

  // Handle forecast
  const handleEstimate = async () => {
    if (nights.length === 0) {
      Alert.alert('No Nights', 'Add at least one night temperature');
      return;
    }

    const response = await estimate({
      furnace_btu: furnaceBTU,
      duty_cycle_pct: dutyCyclePct,
      nights_temp_f: nights,
      people,
      subscription_id: subscriptionId || undefined,
    });

    if (!response) {
      Alert.alert('Error', error || 'Failed to estimate propane usage');
      return;
    }

    if (response.is_premium_locked) {
      setShowPaywall(true);
      return;
    }

    if (response.daily_lbs && response.daily_lbs.length > 0) {
      const totalLbs = response.daily_lbs.reduce((a, b) => a + b, 0);
      const avgLbs = totalLbs / response.daily_lbs.length;
      Alert.alert(
        '⛽ Propane Estimate',
        `Total: ${totalLbs.toFixed(1)} lbs\nAverage: ${avgLbs.toFixed(2)} lbs/day\n\n${response.advisory || ''}`
      );
    }
  };

  // Color helper for consumption level
  const getConsumptionColor = (lbs: number): string => {
    if (lbs >= 2.0) return COLORS.danger;        // Red: very high
    if (lbs >= 1.5) return COLORS.warning;       // Amber: high
    if (lbs >= 1.0) return COLORS.secondary;     // Blue: medium
    return COLORS.primary;                       // Green: low
  };

  const getConsumptionLabel = (lbs: number): string => {
    if (lbs >= 2.0) return 'Very High';
    if (lbs >= 1.5) return 'High';
    if (lbs >= 1.0) return 'Medium';
    return 'Low';
  };

  return (
    <ScrollView style={styles.container} showsVerticalScrollIndicator={false}>
      {/* Header */}
      <View style={styles.header}>
        <Text style={styles.title}>⛽ Propane Usage</Text>
        <Text style={styles.subtitle}>Estimate daily consumption for your trip</Text>
      </View>

      {/* Error Display */}
      {error && !result?.is_premium_locked && (
        <View style={styles.errorBox}>
          <Text style={styles.errorText}>⚠️ {error}</Text>
        </View>
      )}

      {/* Furnace Section */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>🔥 Furnace</Text>

        {/* Furnace BTU Presets */}
        <Text style={styles.label}>Furnace Capacity:</Text>
        <View style={styles.presetGrid}>
          {FURNACE_PRESETS.map((preset) => (
            <TouchableOpacity
              key={preset.value}
              style={[
                styles.presetButton,
                furnaceBTU === preset.value && styles.presetButtonActive,
              ]}
              onPress={() => setFurnaceBTU(preset.value)}
            >
              <Text
                style={[
                  styles.presetButtonText,
                  furnaceBTU === preset.value && styles.presetButtonTextActive,
                ]}
              >
                {preset.label}
              </Text>
            </TouchableOpacity>
          ))}
        </View>

        {/* Custom BTU Input */}
        <Text style={styles.label}>Or enter custom BTU:</Text>
        <View style={styles.inputGroup}>
          <TouchableOpacity
            style={styles.adjustButton}
            onPress={() => setFurnaceBTU(Math.max(1000, furnaceBTU - 5000))}
          >
            <Text style={styles.adjustButtonText}>−</Text>
          </TouchableOpacity>
          <Text style={styles.inputValue}>{furnaceBTU} BTU</Text>
          <TouchableOpacity
            style={styles.adjustButton}
            onPress={() => setFurnaceBTU(furnaceBTU + 5000)}
          >
            <Text style={styles.adjustButtonText}>+</Text>
          </TouchableOpacity>
        </View>

        {/* Duty Cycle */}
        <Text style={styles.label}>Furnace Duty Cycle:</Text>
        <View style={styles.inputGroup}>
          <TouchableOpacity
            style={styles.adjustButton}
            onPress={() => setDutyCyclePct(Math.max(0, dutyCyclePct - 5))}
          >
            <Text style={styles.adjustButtonText}>−</Text>
          </TouchableOpacity>
          <Text style={styles.inputValue}>{dutyCyclePct.toFixed(0)}%</Text>
          <TouchableOpacity
            style={styles.adjustButton}
            onPress={() => setDutyCyclePct(Math.min(100, dutyCyclePct + 5))}
          >
            <Text style={styles.adjustButtonText}>+</Text>
          </TouchableOpacity>
        </View>
      </View>

      {/* Environment Section */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>👥 Trip Setup</Text>

        {/* People Count */}
        <Text style={styles.label}>Number of People:</Text>
        <View style={styles.inputGroup}>
          <TouchableOpacity
            style={styles.adjustButton}
            onPress={() => setPeople(Math.max(1, people - 1))}
          >
            <Text style={styles.adjustButtonText}>−</Text>
          </TouchableOpacity>
          <Text style={styles.inputValue}>{people}</Text>
          <TouchableOpacity
            style={styles.adjustButton}
            onPress={() => setPeople(people + 1)}
          >
            <Text style={styles.adjustButtonText}>+</Text>
          </TouchableOpacity>
        </View>

        {/* Temperature List */}
        <Text style={styles.label}>Nightly Low Temperatures (°F):</Text>

        {nights.length > 0 && (
          <View style={styles.tempList}>
            {nights.map((temp, index) => (
              <View key={index} style={styles.tempItem}>
                <View style={styles.inputGroup}>
                  <TouchableOpacity
                    style={styles.adjustButton}
                    onPress={() => updateTemperature(index, (temp - 5).toString())}
                  >
                    <Text style={styles.adjustButtonText}>−</Text>
                  </TouchableOpacity>
                  <Text style={styles.inputValue}>{temp}°F</Text>
                  <TouchableOpacity
                    style={styles.adjustButton}
                    onPress={() => updateTemperature(index, (temp + 5).toString())}
                  >
                    <Text style={styles.adjustButtonText}>+</Text>
                  </TouchableOpacity>
                </View>
                <TouchableOpacity
                  style={styles.removeButton}
                  onPress={() => removeTemperature(index)}
                >
                  <Text style={styles.removeButtonText}>✕</Text>
                </TouchableOpacity>
              </View>
            ))}
          </View>
        )}

        {/* Add Temperature */}
        <View style={styles.tempInput}>
          <View style={[styles.inputGroup, { flex: 1 }]}>
            <TouchableOpacity
              style={styles.adjustButton}
              onPress={() => setTempInput((parseInt(tempInput, 10) - 5).toString())}
            >
              <Text style={styles.adjustButtonText}>−</Text>
            </TouchableOpacity>
            <Text style={styles.inputValue}>{tempInput}°F</Text>
            <TouchableOpacity
              style={styles.adjustButton}
              onPress={() => setTempInput((parseInt(tempInput, 10) + 5).toString())}
            >
              <Text style={styles.adjustButtonText}>+</Text>
            </TouchableOpacity>
          </View>
          <TouchableOpacity
            style={styles.addButton}
            onPress={addTemperature}
          >
            <Text style={styles.addButtonText}>Add Day</Text>
          </TouchableOpacity>
        </View>
      </View>

      {/* Results Section */}
      {result && !result.is_premium_locked && result.daily_lbs && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>📊 Daily Breakdown</Text>

          <View style={styles.resultsList}>
            {result.daily_lbs.map((lbs, index) => {
              const temp = result.nights_temp_f?.[index] ?? 'N/A';
              const color = getConsumptionColor(lbs);
              const label = getConsumptionLabel(lbs);
              const barWidth = (lbs / 2.5) * 100; // Scale to max 2.5 lbs

              return (
                <View key={index} style={styles.resultItem}>
                  <View style={styles.resultLabel}>
                    <Text style={styles.resultDate}>Day {index + 1}</Text>
                    <Text style={styles.resultTemp}>{temp}°F</Text>
                  </View>
                  <View style={[styles.resultBar, { width: `${Math.min(barWidth, 100)}%`, backgroundColor: color }]}>
                    <Text style={styles.resultBarText}>{lbs.toFixed(2)} lbs</Text>
                  </View>
                  <Text style={[styles.resultLabel, { color }]}>{label}</Text>
                </View>
              );
            })}
          </View>

          {/* Advisory */}
          {result.advisory && (
            <View style={styles.advisory}>
              <Text style={styles.advisoryText}>{result.advisory}</Text>
            </View>
          )}

          {/* Clear Button */}
          <TouchableOpacity
            style={styles.clearButton}
            onPress={clearResult}
          >
            <Text style={styles.clearButtonText}>Clear Results</Text>
          </TouchableOpacity>
        </View>
      )}

      {/* Loading Indicator */}
      {loading && (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={COLORS.primary} />
          <Text style={styles.loadingText}>Calculating propane usage...</Text>
        </View>
      )}

      {/* Main Action Button */}
      {!loading && (
        <TouchableOpacity
          style={styles.estimateButton}
          onPress={handleEstimate}
          disabled={loading || nights.length === 0}
        >
          <Text style={styles.estimateButtonText}>📊 Estimate Propane Usage</Text>
        </TouchableOpacity>
      )}

      {/* Paywall Modal */}
      {showPaywall && (
        <PaywallModal
          isVisible={showPaywall}
          onClose={() => setShowPaywall(false)}
          feature="Propane Usage"
          message="Get accurate propane consumption estimates for any furnace and trip duration."
        />
      )}
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: COLORS.background,
  },

  header: {
    paddingHorizontal: 20,
    paddingTop: 20,
    paddingBottom: 10,
  },

  title: {
    fontSize: 28,
    fontWeight: 'bold',
    color: COLORS.text,
    marginBottom: 4,
  },

  subtitle: {
    fontSize: 14,
    color: COLORS.textSecondary,
  },

  section: {
    marginHorizontal: 20,
    marginBottom: 20,
    paddingHorizontal: 16,
    paddingVertical: 16,
    backgroundColor: COLORS.surface,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: COLORS.border,
  },

  sectionTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: COLORS.text,
    marginBottom: 12,
  },

  label: {
    fontSize: 13,
    fontWeight: '500',
    color: COLORS.textSecondary,
    marginTop: 10,
    marginBottom: 6,
  },

  errorBox: {
    marginHorizontal: 20,
    marginTop: 12,
    marginBottom: 12,
    paddingHorizontal: 12,
    paddingVertical: 10,
    backgroundColor: '#fee2e2',
    borderLeftWidth: 4,
    borderLeftColor: COLORS.danger,
    borderRadius: 6,
  },

  errorText: {
    fontSize: 13,
    color: '#991b1b',
    fontWeight: '500',
  },

  inputGroup: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 12,
  },

  adjustButton: {
    width: 40,
    height: 40,
    borderRadius: 8,
    backgroundColor: COLORS.primary,
    justifyContent: 'center',
    alignItems: 'center',
  },

  adjustButtonText: {
    color: COLORS.surface,
    fontSize: 20,
    fontWeight: 'bold',
  },

  inputValue: {
    fontSize: 16,
    fontWeight: '600',
    color: COLORS.text,
    minWidth: 60,
    textAlign: 'center',
  },

  presetGrid: {
    flexDirection: 'row',
    gap: 10,
    marginBottom: 12,
    flexWrap: 'wrap',
  },

  presetButton: {
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 6,
    backgroundColor: '#f3f4f6',
    borderWidth: 1,
    borderColor: COLORS.border,
  },

  presetButtonActive: {
    backgroundColor: COLORS.primary,
    borderColor: COLORS.primary,
  },

  presetButtonText: {
    fontSize: 12,
    fontWeight: '500',
    color: COLORS.text,
  },

  presetButtonTextActive: {
    color: COLORS.surface,
  },

  tempList: {
    gap: 8,
    marginBottom: 12,
  },

  tempItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },

  removeButton: {
    width: 36,
    height: 36,
    borderRadius: 6,
    backgroundColor: '#fee2e2',
    justifyContent: 'center',
    alignItems: 'center',
  },

  removeButtonText: {
    color: COLORS.danger,
    fontSize: 18,
    fontWeight: 'bold',
  },

  tempInput: {
    flexDirection: 'row',
    gap: 8,
    alignItems: 'center',
  },

  addButton: {
    paddingHorizontal: 12,
    paddingVertical: 8,
    backgroundColor: COLORS.primary,
    borderRadius: 6,
    justifyContent: 'center',
    alignItems: 'center',
  },

  addButtonText: {
    color: COLORS.surface,
    fontWeight: '600',
    fontSize: 12,
  },

  resultsList: {
    gap: 10,
    marginBottom: 12,
  },

  resultItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },

  resultLabel: {
    width: 50,
    alignItems: 'center',
  },

  resultDate: {
    fontSize: 12,
    fontWeight: '600',
    color: COLORS.text,
  },

  resultTemp: {
    fontSize: 11,
    color: COLORS.textSecondary,
  },

  resultBar: {
    flex: 1,
    minHeight: 32,
    borderRadius: 4,
    justifyContent: 'center',
    paddingHorizontal: 8,
  },

  resultBarText: {
    fontSize: 12,
    fontWeight: '600',
    color: COLORS.surface,
  },

  advisory: {
    marginTop: 12,
    paddingHorizontal: 12,
    paddingVertical: 10,
    backgroundColor: '#dcfce7',
    borderLeftWidth: 3,
    borderLeftColor: COLORS.primary,
    borderRadius: 6,
  },

  advisoryText: {
    fontSize: 13,
    color: '#15803d',
    fontWeight: '500',
  },

  clearButton: {
    marginTop: 12,
    paddingHorizontal: 12,
    paddingVertical: 8,
    backgroundColor: '#f3f4f6',
    borderRadius: 6,
    alignItems: 'center',
  },

  clearButtonText: {
    fontSize: 13,
    fontWeight: '600',
    color: COLORS.textSecondary,
  },

  loadingContainer: {
    marginHorizontal: 20,
    marginVertical: 20,
    paddingVertical: 40,
    alignItems: 'center',
  },

  loadingText: {
    marginTop: 12,
    fontSize: 14,
    color: COLORS.textSecondary,
  },

  estimateButton: {
    marginHorizontal: 20,
    marginVertical: 20,
    paddingVertical: 14,
    backgroundColor: COLORS.primary,
    borderRadius: 8,
    alignItems: 'center',
  },

  estimateButtonText: {
    fontSize: 16,
    fontWeight: '600',
    color: COLORS.surface,
  },
});

export default PropaneUsageScreen;
