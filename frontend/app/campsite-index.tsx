import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  TextInput,
  ActivityIndicator,
  Alert,
} from 'react-native';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import axios from 'axios';
import { API_BASE, buildUrl } from '../lib/apiConfig';
import { useLocationSearch } from '../lib/useLocationSearch';
import LocationSearchBox from '../lib/components/LocationSearchBox';

interface CampsiteIndexResult {
  score: number;
  breakdown: {
    wind: number;
    shade: number;
    slope: number;
    access: number;
    signal: number;
    passability: number;
  };
  explanations: string[];
}

export default function CampsiteIndexScreen() {
  const router = useRouter();

  // ── Location (manual search + explicit GPS only) ────────────────────
  const {
    lat: latitude, lon: longitude,
    locationLabel, locationLoading,
    locationQuery, suggestions, showSuggestions,
    handleLocationQueryChange, selectSuggestion,
    clearManualLocation, triggerGps, setShowSuggestions,
  } = useLocationSearch('campsiteIndexLoc');

  
  // Keep manual inputs as fallback
  const [windGustMph, setWindGustMph] = useState('15');
  const [shadeScore, setShadeScore] = useState('0.5');
  const [slopePct, setSlopePct] = useState('8');
  const [accessScore, setAccessScore] = useState('0.7');
  const [signalScore, setSignalScore] = useState('0.6');
  const [passabilityScore, setPassabilityScore] = useState('75');
  const [useAutoMode, setUseAutoMode] = useState(true);

  const [result, setResult] = useState<CampsiteIndexResult | null>(null);
  const [loading, setLoading] = useState(false);


  const refreshLocation = async () => {
    await triggerGps();
  };

  const calculateScore = async () => {
    if (useAutoMode && (!latitude || !longitude)) {
      Alert.alert('Location Required', 'Please enter coordinates or use current location.');
      return;
    }

    setLoading(true);
    setResult(null);
    try {
      let response;
      if (useAutoMode) {
        // Auto mode: fetch real data from backend
        response = await axios.post(buildUrl('campsite-index/auto'), {
          latitude: parseFloat(latitude),
          longitude: parseFloat(longitude),
        });
      } else {
        // Manual mode: use user inputs
        response = await axios.post(buildUrl('campsite-index'), {
          wind_gust_mph: parseFloat(windGustMph),
          shade_score: parseFloat(shadeScore),
          slope_pct: parseFloat(slopePct),
          access_score: parseFloat(accessScore),
          signal_score: parseFloat(signalScore),
          road_passability_score: parseFloat(passabilityScore),
        });
      }

      setResult(response.data);
    } catch (error: any) {
      console.error('Campsite index error:', error);
      Alert.alert('Error', error?.response?.data?.detail || error?.message || 'Failed to calculate campsite index');
    } finally {
      setLoading(false);
    }
  };

  const getScoreColor = (score: number) => {
    if (score >= 80) return '#4CAF50'; // Green
    if (score >= 60) return '#2196F3'; // Blue
    if (score >= 40) return '#FF9800'; // Orange
    return '#F44336'; // Red
  };

  return (
    <ScrollView style={styles.container}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
          <Text style={styles.backText}>← Back</Text>
        </TouchableOpacity>
        <Text style={styles.title}>Campsite Index</Text>
        <Text style={styles.subtitle}>Calculate overall campsite quality score</Text>
      </View>

      <View style={styles.card}>
        <View style={styles.modeToggle}>
          <TouchableOpacity
            style={[styles.modeButton, useAutoMode && styles.modeButtonActive]}
            onPress={() => setUseAutoMode(true)}
          >
            <Text style={[styles.modeButtonText, useAutoMode && styles.modeButtonTextActive]}>
              Auto
            </Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.modeButton, !useAutoMode && styles.modeButtonActive]}
            onPress={() => setUseAutoMode(false)}
          >
            <Text style={[styles.modeButtonText, !useAutoMode && styles.modeButtonTextActive]}>
              Manual
            </Text>
          </TouchableOpacity>
        </View>

        {useAutoMode ? (
          <>
            <Text style={styles.sectionTitle}>Location</Text>
            <Text style={styles.infoText}>
              Automatic mode fetches real-time data: current wind, terrain slope, tree shade, road access, cell signal, and passability conditions.
            </Text>
            
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
              accentColor="#22c55e"
            />
          </>
        ) : (
          <>
            <Text style={styles.sectionTitle}>Site Conditions (Manual)</Text>
            <Text style={styles.infoText}>
              Manual mode requires you to enter each factor yourself.
            </Text>

            <View style={styles.inputGroup}>
              <Text style={styles.label}>Wind Gust (mph)</Text>
              <TextInput
                style={styles.input}
                placeholder="e.g., 15"
                keyboardType="decimal-pad"
                value={windGustMph}
                onChangeText={setWindGustMph}
                editable={!loading}
              />
              <Text style={styles.hint}>0-40+ mph. Higher wind reduces comfort.</Text>
            </View>

            <View style={styles.inputGroup}>
              <Text style={styles.label}>Shade Score (0-1)</Text>
              <TextInput
                style={styles.input}
                placeholder="e.g., 0.5"
                keyboardType="decimal-pad"
                value={shadeScore}
                onChangeText={setShadeScore}
                editable={!loading}
              />
              <Text style={styles.hint}>0 = no shade, 1 = full shade coverage</Text>
            </View>

            <View style={styles.inputGroup}>
              <Text style={styles.label}>Slope (%)</Text>
              <TextInput
                style={styles.input}
                placeholder="e.g., 8"
                keyboardType="decimal-pad"
                value={slopePct}
                onChangeText={setSlopePct}
                editable={!loading}
              />
              <Text style={styles.hint}>0% = flat, 25%+ = steep. Steeper slopes are harder to set up.</Text>
            </View>

            <View style={styles.inputGroup}>
              <Text style={styles.label}>Access Score (0-1)</Text>
              <TextInput
                style={styles.input}
                placeholder="e.g., 0.7"
                keyboardType="decimal-pad"
                value={accessScore}
                onChangeText={setAccessScore}
                editable={!loading}
              />
              <Text style={styles.hint}>0 = poor road/parking access, 1 = excellent</Text>
            </View>

            <View style={styles.inputGroup}>
              <Text style={styles.label}>Signal Score (0-1)</Text>
              <TextInput
                style={styles.input}
                placeholder="e.g., 0.6"
                keyboardType="decimal-pad"
                value={signalScore}
                onChangeText={setSignalScore}
                editable={!loading}
              />
              <Text style={styles.hint}>0 = no signal, 1 = excellent connectivity</Text>
            </View>

            <View style={styles.inputGroup}>
              <Text style={styles.label}>Road Passability Score (0-100)</Text>
              <TextInput
                style={styles.input}
                placeholder="e.g., 75"
                keyboardType="decimal-pad"
                value={passabilityScore}
                onChangeText={setPassabilityScore}
                editable={!loading}
              />
              <Text style={styles.hint}>0 = impassable, 100 = easily drivable</Text>
            </View>
          </>
        )}
      </View>

      <View style={styles.buttonGroup}>
        <TouchableOpacity
          style={[styles.button, styles.primaryButton]}
          onPress={calculateScore}
          disabled={loading}
        >
          {loading ? (
            <ActivityIndicator color="#FFF" />
          ) : (
            <Text style={styles.buttonText}>Calculate Score</Text>
          )}
        </TouchableOpacity>
      </View>

      {result && (
        <View style={styles.resultCard}>
          <Text style={styles.resultTitle}>Campsite Score</Text>
          <Text
            style={[
              styles.resultScore,
              { color: getScoreColor(result.score) },
            ]}
          >
            {result.score}/100
          </Text>

          <Text style={styles.breakdownTitle}>Factor Breakdown</Text>
          {Object.entries(result.breakdown).map(([factor, value]) => (
            <View key={factor} style={styles.breakdownRow}>
              <Text style={styles.breakdownLabel}>{factor.charAt(0).toUpperCase() + factor.slice(1)}</Text>
              <Text style={styles.breakdownValue}>{Math.round(value)}</Text>
            </View>
          ))}

          {result.explanations && result.explanations.length > 0 && (
            <>
              <Text style={styles.explanationsTitle}>Insights</Text>
              {result.explanations.map((explanation, idx) => (
                <View key={idx} style={styles.explanationItem}>
                  <Text style={styles.explanationBullet}>•</Text>
                  <Text style={styles.explanationText}>{explanation}</Text>
                </View>
              ))}
            </>
          )}
        </View>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F5F5F5',
  },
  header: {
    backgroundColor: '#1E88E5',
    paddingTop: 16,
    paddingHorizontal: 16,
    paddingBottom: 20,
    marginBottom: 16,
  },
  backButton: {
    marginBottom: 8,
  },
  backText: {
    color: '#FFF',
    fontSize: 14,
    fontWeight: '500',
  },
  title: {
    fontSize: 28,
    fontWeight: 'bold',
    color: '#FFF',
    marginBottom: 4,
  },
  subtitle: {
    fontSize: 14,
    color: 'rgba(255,255,255,0.9)',
  },
  card: {
    backgroundColor: '#FFF',
    marginHorizontal: 12,
    marginBottom: 16,
    borderRadius: 8,
    padding: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 2,
  },
  locationBox: {
    backgroundColor: '#1f1f23',
    borderRadius: 12,
    padding: 14,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: '#eab30820',
  },
  locationBoxHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 8,
    gap: 8,
  },
  locationBoxLabel: {
    color: '#9ca3af',
    fontSize: 13,
    fontWeight: '500',
    flex: 1,
  },
  refreshLocationBtn: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: '#eab30815',
    justifyContent: 'center',
    alignItems: 'center',
  },
  locationBoxCoords: {
    color: '#eab308',
    fontSize: 15,
    fontWeight: '600',
    fontFamily: 'monospace',
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#333',
    marginBottom: 16,
  },
  inputGroup: {
    marginBottom: 16,
  },
  label: {
    fontSize: 14,
    fontWeight: '600',
    color: '#333',
    marginBottom: 6,
  },
  input: {
    borderWidth: 1,
    borderColor: '#DDD',
    borderRadius: 6,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 14,
    color: '#333',
    marginBottom: 4,
  },
  hint: {
    fontSize: 12,
    color: '#888',
    fontStyle: 'italic',
  },
  modeToggle: {
    flexDirection: 'row',
    backgroundColor: '#F0F0F0',
    borderRadius: 8,
    padding: 4,
    marginBottom: 16,
  },
  modeButton: {
    flex: 1,
    paddingVertical: 8,
    alignItems: 'center',
    borderRadius: 6,
  },
  modeButtonActive: {
    backgroundColor: '#1E88E5',
  },
  modeButtonText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#666',
  },
  modeButtonTextActive: {
    color: '#FFF',
  },
  infoText: {
    fontSize: 13,
    color: '#666',
    marginBottom: 16,
    lineHeight: 20,
  },
  locationRow: {
    flexDirection: 'row',
    gap: 12,
    marginBottom: 12,
  },
  coordInput: {
    flex: 1,
  },
  refreshLocationButton: {
    padding: 8,
    justifyContent: 'center',
    alignItems: 'center',
  },
  buttonGroup: {
    flexDirection: 'row',
    marginHorizontal: 12,
    marginBottom: 40,
    gap: 8,
  },
  button: {
    flex: 1,
    paddingVertical: 12,
    borderRadius: 8,
    alignItems: 'center',
  },
  primaryButton: {
    backgroundColor: '#1E88E5',
  },
  secondaryButton: {
    backgroundColor: '#F5F5F5',
    borderWidth: 1,
    borderColor: '#1E88E5',
  },
  buttonText: {
    color: '#FFF',
    fontSize: 14,
    fontWeight: '600',
  },
  buttonTextSecondary: {
    color: '#1E88E5',
    fontSize: 14,
    fontWeight: '600',
  },
  resultCard: {
    backgroundColor: '#FFF',
    marginHorizontal: 12,
    marginBottom: 24,
    borderRadius: 8,
    padding: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 2,
  },
  resultTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#333',
    marginBottom: 12,
  },
  resultScore: {
    fontSize: 48,
    fontWeight: 'bold',
    textAlign: 'center',
    marginBottom: 20,
  },
  breakdownTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: '#333',
    marginTop: 16,
    marginBottom: 8,
  },
  breakdownRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: '#EEE',
  },
  breakdownLabel: {
    fontSize: 13,
    color: '#555',
  },
  breakdownValue: {
    fontSize: 13,
    fontWeight: '600',
    color: '#333',
  },
  explanationsTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: '#333',
    marginTop: 16,
    marginBottom: 8,
  },
  explanationItem: {
    flexDirection: 'row',
    marginBottom: 8,
  },
  explanationBullet: {
    color: '#1E88E5',
    fontSize: 14,
    marginRight: 8,
    fontWeight: 'bold',
  },
  explanationText: {
    flex: 1,
    fontSize: 13,
    color: '#555',
    lineHeight: 18,
  },
});
