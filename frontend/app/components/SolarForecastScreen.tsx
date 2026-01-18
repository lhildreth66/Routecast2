/**
 * Solar Forecast Component
 * 
 * Premium feature component for forecasting daily solar energy generation.
 * Shows how to integrate the useSolarForecast hook and handle premium gating.
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
import { useSolarForecast } from '../hooks/useSolarForecast';
import { usePremium } from '../hooks/usePremium';
import { PaywallModal } from './PaywallModal';

const SolarForecastScreen: React.FC = () => {
  const { forecast, loading, error, result, clearResult } = useSolarForecast();
  const { isPremium, subscriptionId } = usePremium();
  const [showPaywall, setShowPaywall] = useState(false);

  // Example input values - Arizona boondocking location
  const [latitude, setLatitude] = useState(34.05);
  const [longitude, setLongitude] = useState(-111.03);
  const [panelWatts, setPanelWatts] = useState(400);
  const [shadePct, setShadePct] = useState(20);
  
  // Multi-day forecast
  const [dateRange, setDateRange] = useState(['2026-01-20', '2026-01-21', '2026-01-22']);
  const [cloudCover, setCloudCover] = useState([10, 50, 80]); // Progressive cloud cover

  const handleForecast = async () => {
    try {
      const response = await forecast({
        lat: latitude,
        lon: longitude,
        date_range: dateRange,
        panel_watts: panelWatts,
        shade_pct: shadePct,
        cloud_cover: cloudCover,
        subscription_id: subscriptionId || undefined,
      });

      // Handle premium lock
      if (response.is_premium_locked) {
        setShowPaywall(true);
        return;
      }

      // Display results summary
      if (response.daily_wh && response.dates) {
        const totalWh = response.daily_wh.reduce((a, b) => a + b, 0);
        const avgWh = Math.round(totalWh / response.daily_wh.length);
        Alert.alert(
          'Solar Forecast',
          `Location: ${latitude.toFixed(2)}°, ${longitude.toFixed(2)}°\n` +
          `Panel Capacity: ${panelWatts}W\n` +
          `Forecast Days: ${response.dates.length}\n` +
          `Average Daily Generation: ${avgWh} Wh\n\n` +
          `${response.advisory}`
        );
      }
    } catch (err) {
      Alert.alert('Error', error || 'Failed to forecast solar energy');
    }
  };

  const getEnergyColor = (wh: number): string => {
    if (wh >= 2000) return '#22c55e'; // Green - excellent
    if (wh >= 1500) return '#3b82f6'; // Blue - good
    if (wh >= 1000) return '#f59e0b'; // Amber - fair
    return '#ef4444'; // Red - poor
  };

  return (
    <>
      <ScrollView style={styles.container}>
        {/* Header */}
        <View style={styles.header}>
          <Text style={styles.title}>☀️ Solar Forecast</Text>
          <Text style={styles.subtitle}>
            Estimate daily solar energy generation
          </Text>
        </View>

        {/* Location Input */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Location</Text>
          
          <View style={styles.inputGroup}>
            <Text style={styles.label}>Latitude: {latitude.toFixed(2)}°</Text>
            <View style={styles.sliderSimulation}>
              <TouchableOpacity
                onPress={() => setLatitude(Math.max(-90, latitude - 5))}
                style={styles.sliderButton}
              >
                <Text style={styles.buttonText}>-</Text>
              </TouchableOpacity>
              <Text style={styles.sliderValue}>{latitude.toFixed(2)}</Text>
              <TouchableOpacity
                onPress={() => setLatitude(Math.min(90, latitude + 5))}
                style={styles.sliderButton}
              >
                <Text style={styles.buttonText}>+</Text>
              </TouchableOpacity>
            </View>
          </View>

          <View style={styles.inputGroup}>
            <Text style={styles.label}>Longitude: {longitude.toFixed(2)}°</Text>
            <View style={styles.sliderSimulation}>
              <TouchableOpacity
                onPress={() => setLongitude(Math.max(-180, longitude - 5))}
                style={styles.sliderButton}
              >
                <Text style={styles.buttonText}>-</Text>
              </TouchableOpacity>
              <Text style={styles.sliderValue}>{longitude.toFixed(2)}</Text>
              <TouchableOpacity
                onPress={() => setLongitude(Math.min(180, longitude + 5))}
                style={styles.sliderButton}
              >
                <Text style={styles.buttonText}>+</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>

        {/* Equipment Input */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Equipment</Text>
          
          <View style={styles.inputGroup}>
            <Text style={styles.label}>Panel Capacity: {panelWatts}W</Text>
            <View style={styles.sliderSimulation}>
              <TouchableOpacity
                onPress={() => setPanelWatts(Math.max(100, panelWatts - 100))}
                style={styles.sliderButton}
              >
                <Text style={styles.buttonText}>-</Text>
              </TouchableOpacity>
              <Text style={styles.sliderValue}>{panelWatts}W</Text>
              <TouchableOpacity
                onPress={() => setPanelWatts(Math.min(2000, panelWatts + 100))}
                style={styles.sliderButton}
              >
                <Text style={styles.buttonText}>+</Text>
              </TouchableOpacity>
            </View>
          </View>

          <View style={styles.inputGroup}>
            <Text style={styles.label}>Shade Loss: {shadePct}%</Text>
            <View style={styles.sliderSimulation}>
              <TouchableOpacity
                onPress={() => setShadePct(Math.max(0, shadePct - 10))}
                style={styles.sliderButton}
              >
                <Text style={styles.buttonText}>-</Text>
              </TouchableOpacity>
              <Text style={styles.sliderValue}>{shadePct}%</Text>
              <TouchableOpacity
                onPress={() => setShadePct(Math.min(100, shadePct + 10))}
                style={styles.sliderButton}
              >
                <Text style={styles.buttonText}>+</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>

        {/* Results */}
        {result && !result.is_premium_locked && (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Forecast Results</Text>
            
            {result.daily_wh && result.dates && (
              <>
                {result.daily_wh.map((wh, idx) => (
                  <View key={idx} style={styles.resultItem}>
                    <Text style={styles.resultDate}>{result.dates![idx]}</Text>
                    <View
                      style={[
                        styles.whBar,
                        { backgroundColor: getEnergyColor(wh) },
                      ]}
                    >
                      <Text style={styles.whText}>{Math.round(wh)} Wh</Text>
                    </View>
                  </View>
                ))}
                
                <View style={styles.advisory}>
                  <Text style={styles.advisoryText}>{result.advisory}</Text>
                </View>
              </>
            )}
          </View>
        )}

        {/* Error Display */}
        {error && (
          <View style={styles.errorBox}>
            <Text style={styles.errorText}>{error}</Text>
          </View>
        )}

        {/* Action Button */}
        <TouchableOpacity
          style={[styles.button, loading && styles.buttonDisabled]}
          onPress={handleForecast}
          disabled={loading}
        >
          {loading ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <Text style={styles.buttonText}>Forecast Solar Energy</Text>
          )}
        </TouchableOpacity>

        {result && !result.is_premium_locked && (
          <TouchableOpacity style={styles.clearButton} onPress={clearResult}>
            <Text style={styles.clearButtonText}>Clear Results</Text>
          </TouchableOpacity>
        )}

        <View style={styles.spacer} />
      </ScrollView>

      {/* Paywall Modal */}
      <PaywallModal visible={showPaywall} onClose={() => setShowPaywall(false)} />
    </>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f8f9fa',
  },
  header: {
    backgroundColor: '#fff',
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#e5e7eb',
  },
  title: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#1f2937',
    marginBottom: 4,
  },
  subtitle: {
    fontSize: 14,
    color: '#6b7280',
  },
  section: {
    backgroundColor: '#fff',
    margin: 12,
    padding: 16,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#e5e7eb',
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#1f2937',
    marginBottom: 12,
  },
  inputGroup: {
    marginBottom: 16,
  },
  label: {
    fontSize: 13,
    color: '#4b5563',
    marginBottom: 8,
    fontWeight: '500',
  },
  sliderSimulation: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: '#f3f4f6',
    borderRadius: 6,
    paddingHorizontal: 12,
    paddingVertical: 10,
  },
  sliderButton: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: '#3b82f6',
    justifyContent: 'center',
    alignItems: 'center',
  },
  sliderValue: {
    fontSize: 14,
    fontWeight: '600',
    color: '#1f2937',
  },
  button: {
    backgroundColor: '#10b981',
    margin: 12,
    padding: 16,
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
  },
  buttonDisabled: {
    backgroundColor: '#d1d5db',
  },
  buttonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '600',
  },
  clearButton: {
    margin: 12,
    padding: 12,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#d1d5db',
    alignItems: 'center',
  },
  clearButtonText: {
    color: '#6b7280',
    fontSize: 14,
    fontWeight: '500',
  },
  resultItem: {
    marginBottom: 12,
  },
  resultDate: {
    fontSize: 13,
    color: '#6b7280',
    marginBottom: 4,
    fontWeight: '500',
  },
  whBar: {
    paddingVertical: 12,
    paddingHorizontal: 12,
    borderRadius: 6,
    justifyContent: 'center',
    alignItems: 'center',
  },
  whText: {
    color: '#fff',
    fontSize: 14,
    fontWeight: '600',
  },
  advisory: {
    backgroundColor: '#f0fdf4',
    borderLeftWidth: 4,
    borderLeftColor: '#22c55e',
    padding: 12,
    borderRadius: 4,
    marginTop: 12,
  },
  advisoryText: {
    color: '#166534',
    fontSize: 14,
    lineHeight: 20,
  },
  errorBox: {
    backgroundColor: '#fee2e2',
    margin: 12,
    padding: 12,
    borderRadius: 6,
    borderLeftWidth: 4,
    borderLeftColor: '#ef4444',
  },
  errorText: {
    color: '#991b1b',
    fontSize: 14,
  },
  spacer: {
    height: 24,
  },
});

export default SolarForecastScreen;
