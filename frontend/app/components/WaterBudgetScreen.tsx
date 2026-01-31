/**
 * WaterBudgetScreen - React Native Component for Water Budget Estimation
 *
 * Complete UI for water tank duration estimation with inputs, results visualization,
 * and premium paywall integration.
 *
 * Water tanks track fresh/gray/black water capacity and estimates how many days
 * the trip can be sustained before the limiting tank runs out.
 *
 * Usage in navigation:
 * ```typescript
 * <Stack.Screen
 *   name="water-budget"
 *   component={WaterBudgetScreen}
 *   options={{ title: '💧 Water Budget' }}
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
} from 'react-native';
import { useWaterBudget } from '../hooks/useWaterBudget';

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

const WaterBudgetScreen: React.FC = () => {
  // Hooks
  const { estimate, loading, error, result, clearResult } = useWaterBudget();

  // State for inputs
  const [freshGal, setFreshGal] = useState(40);
  const [grayGal, setGrayGal] = useState(50);
  const [blackGal, setBlackGal] = useState(20);
  const [people, setPeople] = useState(2);
  const [showersPerWeek, setShowersPerWeek] = useState(2);
  const [isHotDays, setIsHotDays] = useState(false);

  // Tank presets (typical RV capacities in gallons)
  const FRESH_PRESETS = [
    { label: 'Small (25gal)', value: 25 },
    { label: 'Standard (40gal)', value: 40 },
    { label: 'Large (60gal)', value: 60 },
    { label: 'Extra Large (100gal)', value: 100 },
  ];

  const GRAY_PRESETS = [
    { label: 'Small (30gal)', value: 30 },
    { label: 'Standard (50gal)', value: 50 },
    { label: 'Large (75gal)', value: 75 },
    { label: 'Extra Large (100gal)', value: 100 },
  ];

  const BLACK_PRESETS = [
    { label: 'Small (10gal)', value: 10 },
    { label: 'Standard (20gal)', value: 20 },
    { label: 'Large (30gal)', value: 30 },
    { label: 'Extra Large (40gal)', value: 40 },
  ];

  // Handle estimation
  const handleEstimate = async () => {
    const response = await estimate({
      fresh_gal: freshGal,
      gray_gal: grayGal,
      black_gal: blackGal,
      people,
      showers_per_week: showersPerWeek,
      hot_days: isHotDays,
    });

    // Handle premium paywall
    if (response?.is_premium_locked) {
      setShowPaywall(true);
    }
  };

  // Get color based on days remaining
  const getDaysColor = (days: number | undefined): string => {
    if (days === undefined || days === null) return COLORS.text;
    if (days > 10) return COLORS.primary; // Green
    if (days > 5) return COLORS.warning; // Amber
    return COLORS.danger; // Red
  };

  // Get advisory icon based on limiting factor
  const getAdvisoryIcon = (factor: string | undefined): string => {
    switch (factor?.toLowerCase()) {
      case 'fresh':
        return '🚱'; // Drinking water
      case 'gray':
        return '🚿'; // Showers/gray water
      case 'black':
        return '🚽'; // Toilet/black water
      default:
        return '💧';
    }
  };

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.contentContainer}
      showsVerticalScrollIndicator={false}
    >
      {/* Header */}
      <View style={styles.header}>
        <Text style={styles.title}>💧 Water Budget Planner</Text>
        <Text style={styles.subtitle}>
          Estimate how many days your water will last during boondocking
        </Text>
      </View>

      {/* Tank Capacities Section */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Tank Capacities (Gallons)</Text>

        {/* Fresh Water Tank */}
        <View style={styles.inputGroup}>
          <Text style={styles.label}>Fresh Water Tank 🚱</Text>
          <View style={styles.presetButtons}>
            {FRESH_PRESETS.map((preset) => (
              <TouchableOpacity
                key={preset.value}
                style={[
                  styles.presetButton,
                  freshGal === preset.value && styles.presetButtonActive,
                ]}
                onPress={() => setFreshGal(preset.value)}
              >
                <Text
                  style={[
                    styles.presetButtonText,
                    freshGal === preset.value && styles.presetButtonTextActive,
                  ]}
                >
                  {preset.label}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
          <Text style={styles.selectedValue}>{freshGal} gallons</Text>
        </View>

        {/* Gray Water Tank */}
        <View style={styles.inputGroup}>
          <Text style={styles.label}>Gray Water Tank 🚿</Text>
          <View style={styles.presetButtons}>
            {GRAY_PRESETS.map((preset) => (
              <TouchableOpacity
                key={preset.value}
                style={[
                  styles.presetButton,
                  grayGal === preset.value && styles.presetButtonActive,
                ]}
                onPress={() => setGrayGal(preset.value)}
              >
                <Text
                  style={[
                    styles.presetButtonText,
                    grayGal === preset.value && styles.presetButtonTextActive,
                  ]}
                >
                  {preset.label}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
          <Text style={styles.selectedValue}>{grayGal} gallons</Text>
        </View>

        {/* Black Water Tank */}
        <View style={styles.inputGroup}>
          <Text style={styles.label}>Black Water Tank 🚽</Text>
          <View style={styles.presetButtons}>
            {BLACK_PRESETS.map((preset) => (
              <TouchableOpacity
                key={preset.value}
                style={[
                  styles.presetButton,
                  blackGal === preset.value && styles.presetButtonActive,
                ]}
                onPress={() => setBlackGal(preset.value)}
              >
                <Text
                  style={[
                    styles.presetButtonText,
                    blackGal === preset.value && styles.presetButtonTextActive,
                  ]}
                >
                  {preset.label}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
          <Text style={styles.selectedValue}>{blackGal} gallons</Text>
        </View>
      </View>

      {/* Usage Parameters Section */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Usage Parameters</Text>

        {/* People */}
        <View style={styles.inputGroup}>
          <Text style={styles.label}>Number of People</Text>
          <View style={styles.stepper}>
            <TouchableOpacity
              style={styles.stepperButton}
              onPress={() => setPeople(Math.max(1, people - 1))}
            >
              <Text style={styles.stepperButtonText}>−</Text>
            </TouchableOpacity>
            <Text style={styles.stepperValue}>{people}</Text>
            <TouchableOpacity
              style={styles.stepperButton}
              onPress={() => setPeople(Math.min(10, people + 1))}
            >
              <Text style={styles.stepperButtonText}>+</Text>
            </TouchableOpacity>
          </View>
        </View>

        {/* Showers per Week */}
        <View style={styles.inputGroup}>
          <Text style={styles.label}>Showers per Week</Text>
          <View style={styles.showerOptions}>
            {[0, 1, 2, 3, 7, 14].map((val) => (
              <TouchableOpacity
                key={val}
                style={[
                  styles.optionButton,
                  showersPerWeek === val && styles.optionButtonActive,
                ]}
                onPress={() => setShowersPerWeek(val)}
              >
                <Text
                  style={[
                    styles.optionButtonText,
                    showersPerWeek === val && styles.optionButtonTextActive,
                  ]}
                >
                  {val === 0 ? 'None' : val === 7 ? 'Daily' : val === 14 ? '2x/day' : `${val}`}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>

        {/* Hot Days Toggle */}
        <View style={styles.inputGroup}>
          <Text style={styles.label}>Weather Conditions</Text>
          <TouchableOpacity
            style={[
              styles.toggleButton,
              isHotDays && styles.toggleButtonActive,
            ]}
            onPress={() => setIsHotDays(!isHotDays)}
          >
            <Text
              style={[
                styles.toggleButtonText,
                isHotDays && styles.toggleButtonTextActive,
              ]}
            >
              {isHotDays ? '☀️ Hot Days (1.2x usage)' : '❄️ Cool Days (0.85x usage)'}
            </Text>
          </TouchableOpacity>
        </View>
      </View>

      {/* Estimate Button */}
      <TouchableOpacity
        style={[
          styles.estimateButton,
          loading && styles.estimateButtonDisabled,
        ]}
        onPress={handleEstimate}
        disabled={loading}
      >
        {loading ? (
          <ActivityIndicator color="#fff" size="small" />
        ) : (
          <Text style={styles.estimateButtonText}>Calculate Water Budget</Text>
        )}
      </TouchableOpacity>

      {/* Results Section */}
      {result && !result.is_premium_locked && (
        <View style={styles.resultsSection}>
          <View style={styles.resultCard}>
            <Text
              style={[
                styles.daysRemaining,
                { color: getDaysColor(result.days_remaining) },
              ]}
            >
              {result.days_remaining} days
            </Text>
            <Text style={styles.daysLabel}>Water will last</Text>
          </View>

          {/* Limiting Factor */}
          {result.limiting_factor && (
            <View style={styles.limitingFactorCard}>
              <Text style={styles.limitingFactorIcon}>
                {getAdvisoryIcon(result.limiting_factor)}
              </Text>
              <View style={styles.limitingFactorText}>
                <Text style={styles.limitingFactorLabel}>Limiting Factor:</Text>
                <Text style={styles.limitingFactorValue}>
                  {result.limiting_factor.charAt(0).toUpperCase() +
                    result.limiting_factor.slice(1)}{' '}
                  Tank
                </Text>
              </View>
            </View>
          )}

          {/* Daily Usage Breakdown */}
          {(result.daily_fresh_gal !== null ||
            result.daily_gray_gal !== null ||
            result.daily_black_gal !== null) && (
            <View style={styles.usageBreakdown}>
              <Text style={styles.usageTitle}>Daily Water Usage</Text>

              {result.daily_fresh_gal !== null && (
                <View style={styles.usageItem}>
                  <Text style={styles.usageLabel}>🚱 Fresh</Text>
                  <Text style={styles.usageValue}>
                    {result.daily_fresh_gal.toFixed(1)} gal/day
                  </Text>
                </View>
              )}

              {result.daily_gray_gal !== null && (
                <View style={styles.usageItem}>
                  <Text style={styles.usageLabel}>🚿 Gray</Text>
                  <Text style={styles.usageValue}>
                    {result.daily_gray_gal.toFixed(1)} gal/day
                  </Text>
                </View>
              )}

              {result.daily_black_gal !== null && (
                <View style={styles.usageItem}>
                  <Text style={styles.usageLabel}>🚽 Black</Text>
                  <Text style={styles.usageValue}>
                    {result.daily_black_gal.toFixed(1)} gal/day
                  </Text>
                </View>
              )}
            </View>
          )}

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

      {/* Error Display */}
      {error && (
        <View style={styles.errorBox}>
          <Text style={styles.errorText}>{error}</Text>
        </View>
      )}

      {/* Premium Paywall Modal */}
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: COLORS.background,
  },
  contentContainer: {
    paddingHorizontal: 16,
    paddingVertical: 20,
  },
  header: {
    marginBottom: 24,
  },
  title: {
    fontSize: 28,
    fontWeight: 'bold',
    color: COLORS.text,
    marginBottom: 8,
  },
  subtitle: {
    fontSize: 14,
    color: COLORS.textSecondary,
    lineHeight: 20,
  },
  section: {
    backgroundColor: COLORS.surface,
    borderRadius: 12,
    padding: 16,
    marginBottom: 20,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: COLORS.text,
    marginBottom: 16,
  },
  inputGroup: {
    marginBottom: 20,
  },
  label: {
    fontSize: 14,
    fontWeight: '500',
    color: COLORS.text,
    marginBottom: 8,
  },
  presetButtons: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginBottom: 8,
  },
  presetButton: {
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: COLORS.border,
    backgroundColor: COLORS.background,
  },
  presetButtonActive: {
    backgroundColor: COLORS.primary,
    borderColor: COLORS.primary,
  },
  presetButtonText: {
    fontSize: 12,
    color: COLORS.text,
    fontWeight: '500',
  },
  presetButtonTextActive: {
    color: '#fff',
  },
  selectedValue: {
    fontSize: 12,
    color: COLORS.textSecondary,
    fontStyle: 'italic',
  },
  stepper: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  stepperButton: {
    width: 40,
    height: 40,
    borderRadius: 8,
    backgroundColor: COLORS.primary,
    justifyContent: 'center',
    alignItems: 'center',
  },
  stepperButtonText: {
    fontSize: 20,
    color: '#fff',
    fontWeight: 'bold',
  },
  stepperValue: {
    fontSize: 16,
    fontWeight: 'bold',
    color: COLORS.text,
    minWidth: 40,
    textAlign: 'center',
  },
  showerOptions: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  optionButton: {
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: COLORS.border,
    backgroundColor: COLORS.background,
  },
  optionButtonActive: {
    backgroundColor: COLORS.secondary,
    borderColor: COLORS.secondary,
  },
  optionButtonText: {
    fontSize: 12,
    color: COLORS.text,
    fontWeight: '500',
  },
  optionButtonTextActive: {
    color: '#fff',
  },
  toggleButton: {
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: COLORS.border,
    backgroundColor: COLORS.background,
  },
  toggleButtonActive: {
    backgroundColor: COLORS.warning,
    borderColor: COLORS.warning,
  },
  toggleButtonText: {
    fontSize: 14,
    color: COLORS.text,
    fontWeight: '500',
  },
  toggleButtonTextActive: {
    color: '#fff',
  },
  estimateButton: {
    backgroundColor: COLORS.primary,
    paddingVertical: 14,
    borderRadius: 8,
    alignItems: 'center',
    marginBottom: 20,
  },
  estimateButtonDisabled: {
    opacity: 0.6,
  },
  estimateButtonText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#fff',
  },
  resultsSection: {
    backgroundColor: COLORS.surface,
    borderRadius: 12,
    padding: 16,
    marginBottom: 20,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  resultCard: {
    alignItems: 'center',
    paddingVertical: 20,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.border,
    marginBottom: 16,
  },
  daysRemaining: {
    fontSize: 36,
    fontWeight: 'bold',
    marginBottom: 4,
  },
  daysLabel: {
    fontSize: 14,
    color: COLORS.textSecondary,
  },
  limitingFactorCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: COLORS.background,
    borderRadius: 8,
    padding: 12,
    marginBottom: 16,
  },
  limitingFactorIcon: {
    fontSize: 24,
    marginRight: 12,
  },
  limitingFactorText: {
    flex: 1,
  },
  limitingFactorLabel: {
    fontSize: 12,
    color: COLORS.textSecondary,
    marginBottom: 2,
  },
  limitingFactorValue: {
    fontSize: 14,
    fontWeight: '600',
    color: COLORS.text,
  },
  usageBreakdown: {
    backgroundColor: COLORS.background,
    borderRadius: 8,
    padding: 12,
    marginBottom: 16,
  },
  usageTitle: {
    fontSize: 12,
    fontWeight: '600',
    color: COLORS.textSecondary,
    marginBottom: 8,
  },
  usageItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 6,
  },
  usageLabel: {
    fontSize: 13,
    color: COLORS.text,
  },
  usageValue: {
    fontSize: 13,
    fontWeight: '500',
    color: COLORS.primary,
  },
  advisory: {
    backgroundColor: '#fff3cd',
    borderLeftWidth: 4,
    borderLeftColor: COLORS.warning,
    borderRadius: 4,
    padding: 12,
    marginBottom: 16,
  },
  advisoryText: {
    fontSize: 13,
    color: '#856404',
    lineHeight: 18,
  },
  clearButton: {
    paddingVertical: 12,
    alignItems: 'center',
    borderTopWidth: 1,
    borderTopColor: COLORS.border,
  },
  clearButtonText: {
    fontSize: 14,
    color: COLORS.textSecondary,
    fontWeight: '500',
  },
  errorBox: {
    backgroundColor: '#fee',
    borderLeftWidth: 4,
    borderLeftColor: COLORS.danger,
    borderRadius: 4,
    padding: 12,
    marginBottom: 20,
  },
  errorText: {
    fontSize: 13,
    color: COLORS.danger,
    lineHeight: 18,
  },
});

export default WaterBudgetScreen;
