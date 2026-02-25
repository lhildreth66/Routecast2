import React, { useState } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, TextInput, ActivityIndicator, ScrollView } from 'react-native';
import axios from 'axios';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { API_BASE, buildUrl } from '../lib/apiConfig';
import { useLocationSearch } from '../lib/useLocationSearch';
import LocationSearchBox from '../lib/components/LocationSearchBox';

export default function WindShelterScreen() {
  const router = useRouter();

  // ── Location (manual search + explicit GPS only) ────────────────────
  const {
    lat: latitude, lon: longitude,
    locationLabel, locationLoading,
    locationQuery, suggestions, showSuggestions,
    handleLocationQueryChange, selectSuggestion,
    clearManualLocation, triggerGps, setShowSuggestions,
  } = useLocationSearch('windShelterLoc');

  const [windDirection, setWindDirection] = useState('270'); // degrees (0-360)
  const [gustSpeed, setGustSpeed] = useState('25'); // mph

  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string>('');



  const refreshLocation = async () => {
    await triggerGps();
  };

  const calculate = async () => {
    setLoading(true);
    setResult(null);
    setError('');
    try {
      const resp = await axios.post(buildUrl('wind-shelter/orientation'), {
        predominant_dir_deg: parseInt(windDirection, 10),
        gust_mph: parseInt(gustSpeed, 10),
      });
      setResult(resp.data);
    } catch (err: any) {
      console.error('Wind shelter error:', err);
      setError(err?.response?.data?.detail || err?.message || 'Failed to calculate wind shelter');
    } finally {
      setLoading(false);
    }
  };

  const getRiskColor = (risk: string) => {
    switch (risk.toLowerCase()) {
      case 'low': return { color: '#4ade80' };
      case 'medium': return { color: '#fbbf24' };
      case 'high': return { color: '#f87171' };
      default: return { color: '#e5e7eb' };
    }
  };

  return (
    <SafeAreaView style={styles.container}>
      <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
        <Ionicons name="arrow-back" size={24} color="#fff" />
        <Text style={styles.backText}>Back</Text>
      </TouchableOpacity>

      <ScrollView style={styles.content}>
        <View style={styles.card}>
          <Text style={styles.title}>Wind Shelter</Text>
          <Text style={styles.subtitle}>Get RV orientation recommendations for wind protection</Text>

          <LocationSearchBox
            lat={latitude}
            lon={longitude}
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
            accentColor="#06b6d4"
          />

          <View style={styles.inputRow}>
            <Text style={styles.label}>Wind Direction (0-360°)</Text>
            <TextInput
              value={windDirection}
              onChangeText={setWindDirection}
              keyboardType="numeric"
              style={styles.input}
              placeholder="e.g., 270 (from west)"
              placeholderTextColor="#9ca3af"
            />
          </View>

          <View style={styles.inputRow}>
            <Text style={styles.label}>Peak Gust Speed (mph)</Text>
            <TextInput
              value={gustSpeed}
              onChangeText={setGustSpeed}
              keyboardType="numeric"
              style={styles.input}
              placeholder="e.g., 25"
              placeholderTextColor="#9ca3af"
            />
          </View>

          <TouchableOpacity onPress={calculate} style={styles.button} disabled={loading}>
            {loading ? <ActivityIndicator color="#1a1a1a" /> : <Text style={styles.buttonText}>Analyze</Text>}
          </TouchableOpacity>

          {error && (
            <View style={styles.errorBox}>
              <Text style={styles.errorText}>❌ {error}</Text>
            </View>
          )}

          {result && (
            <View style={styles.resultBox}>
              <Text style={styles.resultTitle}>🧭 Wind Shelter Recommendation</Text>
              
              {result.recommended_bearing_deg !== null && (
                <View style={styles.bearingBox}>
                  <Text style={styles.bearingLabel}>Recommended RV Orientation</Text>
                  <Text style={styles.bearingValue}>{result.recommended_bearing_deg}°</Text>
                </View>
              )}
              
              {result.rationale_text && (
                <Text style={styles.resultText}>💡 {result.rationale_text}</Text>
              )}
              
              <View style={styles.statsRow}>
                {result.risk_level && (
                  <View style={styles.statBox}>
                    <Text style={styles.statLabel}>Risk Level</Text>
                    <Text style={[styles.statValue, getRiskColor(result.risk_level)]}>
                      {result.risk_level.toUpperCase()}
                    </Text>
                  </View>
                )}
                
                {result.estimated_wind_reduction_pct !== null && (
                  <View style={styles.statBox}>
                    <Text style={styles.statLabel}>Wind Reduction</Text>
                    <Text style={styles.statValue}>{result.estimated_wind_reduction_pct}%</Text>
                  </View>
                )}
              </View>
              
              {result.shelter_available !== null && (
                <Text style={styles.shelterStatus}>
                  {result.shelter_available ? '✅ Shelter Available' : '⚠️ Limited Shelter'}
                </Text>
              )}
            </View>
          )}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0a0a0a' },
  backButton: { flexDirection: 'row', alignItems: 'center', padding: 16, gap: 8 },
  backText: { color: '#fff', fontSize: 16, fontWeight: '600' },
  content: { flex: 1 },
  card: { backgroundColor: '#18181b', borderRadius: 12, padding: 16, margin: 16, gap: 12 },
  title: { color: '#fff', fontSize: 20, fontWeight: '800' },
  subtitle: { color: '#d4d4d8', fontSize: 14 },
  locationInfo: { flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: '#111827', padding: 10, borderRadius: 8 },
  locationText: { color: '#d4d4d8', fontSize: 12, flex: 1 },
  refreshBtn: { padding: 4 },
  locationButton: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#1f2937', paddingVertical: 10, borderRadius: 8, borderWidth: 1, borderColor: '#06b6d4' },
  locationButtonText: { color: '#06b6d4', fontWeight: '600', fontSize: 14 },
  inputRow: { gap: 6 },
  label: { color: '#e4e4e7', fontWeight: '600' },
  input: { backgroundColor: '#111827', color: '#fff', borderRadius: 8, paddingHorizontal: 12, paddingVertical: 10 },
  button: { backgroundColor: '#eab308', paddingVertical: 12, borderRadius: 8, alignItems: 'center' },
  buttonText: { color: '#1a1a1a', fontWeight: '800' },
  errorBox: { backgroundColor: '#7f1d1d', borderRadius: 8, padding: 12 },
  errorText: { color: '#fecaca', fontSize: 14 },
  resultBox: { backgroundColor: '#111827', borderRadius: 8, padding: 12, gap: 12 },
  resultTitle: { color: '#06b6d4', fontSize: 16, fontWeight: '700' },
  bearingBox: { backgroundColor: '#1f2937', borderRadius: 8, padding: 12, alignItems: 'center', borderWidth: 2, borderColor: '#06b6d4' },
  bearingLabel: { color: '#9ca3af', fontSize: 12, marginBottom: 4 },
  bearingValue: { color: '#fff', fontSize: 32, fontWeight: '800' },
  resultText: { color: '#e5e7eb', fontSize: 14, lineHeight: 20 },
  statsRow: { flexDirection: 'row', gap: 12 },
  statBox: { flex: 1, backgroundColor: '#1f2937', borderRadius: 8, padding: 10, alignItems: 'center' },
  statLabel: { color: '#9ca3af', fontSize: 11, marginBottom: 4 },
  statValue: { color: '#fff', fontSize: 18, fontWeight: '700' },
  shelterStatus: { color: '#d4d4d8', fontSize: 14, fontWeight: '600', textAlign: 'center', marginTop: 4 },
});
