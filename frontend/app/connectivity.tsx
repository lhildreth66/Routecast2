import React, { useState } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, TextInput, Modal, ActivityIndicator, Platform, ScrollView, Alert } from 'react-native';
import axios from 'axios';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import * as Location from 'expo-location';
import { API_BASE } from './apiConfig';

type ConnectivityTab = 'cell' | 'starlink';

export default function ConnectivityScreen() {
  const router = useRouter();
  const [latitude, setLatitude] = useState('34.05');
  const [longitude, setLongitude] = useState('-111.03');
  
  // Cell inputs
  const [carrier, setCarrier] = useState<'verizon' | 'att' | 'tmobile'>('att');

  // Starlink inputs
  const [horizonSouth, setHorizonSouth] = useState('20');
  const [canopyPct, setCanopyPct] = useState('40');

  // UI state
  const [tab, setTab] = useState<ConnectivityTab>('cell');
  const [loading, setLoading] = useState(false);
  const [locationLoading, setLocationLoading] = useState(true);
  const [cellResult, setCellResult] = useState<string | null>(null);
  const [cellResultData, setCellResultData] = useState<any>(null);
  const [starlinkResult, setStarlinkResult] = useState<string | null>(null);
  const [starlinkResultData, setStarlinkResultData] = useState<any>(null);

  useEffect(() => {
    getCurrentLocation();
  }, []);

  const getCurrentLocation = async () => {
    try {
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status === 'granted') {
        const location = await Location.getCurrentPositionAsync({
          accuracy: Location.Accuracy.Balanced,
        });
        setLatitude(location.coords.latitude.toFixed(4));
        setLongitude(location.coords.longitude.toFixed(4));
      }
    } catch (err) {
      console.log('Could not get current location:', err);
    } finally {
      setLocationLoading(false);
    }
  };

  const refreshLocation = async () => {
    setLocationLoading(true);
    try {
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== 'granted') {
        Alert.alert('Permission Denied', 'Location permission is required.');
        setLocationLoading(false);
        return;
      }

      const location = await Location.getCurrentPositionAsync({
        accuracy: Location.Accuracy.Balanced,
      });
      setLatitude(location.coords.latitude.toFixed(4));
      setLongitude(location.coords.longitude.toFixed(4));
      Alert.alert('Location Updated', `Refreshed to: ${location.coords.latitude.toFixed(4)}, ${location.coords.longitude.toFixed(4)}`);
    } catch (err) {
      Alert.alert('Error', 'Failed to refresh location');
    } finally {
      setLocationLoading(false);
    }
  };

  const useCurrentLocation = async () => {
    await refreshLocation();
  };

  const runCellPrediction = async () => {
    setLoading(true);
    setCellResult(null);
    setCellResultData(null);
    try {
      const payload = {
        carrier,
        lat: parseFloat(latitude),
        lon: parseFloat(longitude),
      };

      try {
        const resp = await axios.post(`${API_BASE}/api/pro/connectivity/cell-probability`, payload);
        const d = resp.data;
        setCellResultData(d);
        setCellResult(`${d.bar_estimate} probability: ${(d.probability * 100).toFixed(0)}%. ${d.explanation}`);
      } catch (err: any) {
        console.error('Cell prediction error:', err);
        // Show actual error details for debugging
        const errorDetail = err?.response?.data?.detail || err?.message || 'Unknown error';
        setCellResult(`Error: ${errorDetail}`);
      }
    } finally {
      setLoading(false);
    }
  };

  const runStarlinkPrediction = async () => {
    setLoading(true);
    setStarlinkResult(null);
    setStarlinkResultData(null);
    try {
      const payload = {
        horizonSouthDeg: parseInt(horizonSouth || '0', 10),
        canopyPct: parseInt(canopyPct || '0', 10),
      };

      try {
        const resp = await axios.post(`${API_BASE}/api/pro/connectivity/starlink-risk`, payload);
        const d = resp.data;
        setStarlinkResultData(d);
        const reasons = Array.isArray(d.reasons) ? d.reasons.join('; ') : '';
        setStarlinkResult(`${d.risk_level} risk (score: ${d.obstruction_score}). ${d.explanation}${reasons ? `; ${reasons}` : ''}`);
      } catch (err: any) {
        console.error('Starlink prediction error:', err);
        // Show actual error details for debugging
        const errorDetail = err?.response?.data?.detail || err?.message || 'Unknown error';
        setStarlinkResult(`Error: ${errorDetail}`);
      }
    } finally {
      setLoading(false);
    }
  };

  const getRiskStyle = (risk: string) => {
    switch (risk?.toLowerCase()) {
      case 'low': return { borderColor: '#4ade80', backgroundColor: '#14532d' };
      case 'medium': return { borderColor: '#fbbf24', backgroundColor: '#713f12' };
      case 'high': return { borderColor: '#f87171', backgroundColor: '#7f1d1d' };
      default: return { borderColor: '#9ca3af', backgroundColor: '#1f2937' };
    }
  };

  return (
    <View style={styles.container}>
      <SafeAreaView style={styles.safeArea}>
        {/* Back Button */}
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="arrow-back" size={24} color="#fff" />
          <Text style={styles.backText}>Back</Text>
        </TouchableOpacity>
        
        <ScrollView style={styles.content}>
          <View style={styles.card}>
            <Text style={styles.title}>Connectivity</Text>
            <Text style={styles.subtitle}>Predict cellular and Starlink signal quality</Text>

            <View style={styles.locationInfo}>
              <Ionicons name="location" size={16} color="#06b6d4" />
              <Text style={styles.locationText}>
                {locationLoading ? 'Getting location...' : `Location: ${latitude}, ${longitude}`}
              </Text>
              {!locationLoading && (
                <TouchableOpacity onPress={refreshLocation} style={styles.refreshBtn}>
                  <Ionicons name="refresh" size={18} color="#06b6d4" />
                </TouchableOpacity>
              )}
            </View>

            {/* Tab buttons */}
            <View style={styles.tabRow}>
            <TouchableOpacity
              onPress={() => setTab('cell')}
              style={[styles.tabBtn, tab === 'cell' && styles.tabBtnActive]}
            >
              <Text style={[styles.tabText, tab === 'cell' && styles.tabTextActive]}>Cellular</Text>
            </TouchableOpacity>
            <TouchableOpacity
              onPress={() => setTab('starlink')}
              style={[styles.tabBtn, tab === 'starlink' && styles.tabBtnActive]}
            >
              <Text style={[styles.tabText, tab === 'starlink' && styles.tabTextActive]}>Starlink</Text>
            </TouchableOpacity>
          </View>

          {tab === 'cell' ? (
            <View style={styles.tabContent}>
              <Text style={styles.helpText}>
                Select your carrier and use your GPS location to predict signal strength at your campsite.
              </Text>
              
              <View style={styles.inputRow}>
                <Text style={styles.label}>Carrier</Text>
                <View style={styles.carrierRow}>
                  {(['att', 'verizon', 'tmobile'] as const).map((c) => (
                    <TouchableOpacity
                      key={c}
                      onPress={() => setCarrier(c)}
                      style={[styles.carrierBtn, carrier === c && styles.carrierBtnActive]}
                    >
                      <Text style={[styles.carrierText, carrier === c && styles.carrierTextActive]}>
                        {c.toUpperCase()}
                      </Text>
                    </TouchableOpacity>
                  ))}
                </View>
              </View>

              <TouchableOpacity onPress={runCellPrediction} style={styles.cta}>
                {loading ? <ActivityIndicator color="#1a1a1a" /> : <Text style={styles.ctaText}>Predict Signal</Text>}
              </TouchableOpacity>

              {cellResult && (
                <View style={styles.resultCard}>
                  <Text style={styles.resultTitle}>📱 Signal Prediction</Text>
                  {cellResultData && (
                    <>
                      <View style={styles.signalBox}>
                        <Text style={styles.signalBars}>{cellResultData.bar_estimate}</Text>
                        <Text style={styles.signalProb}>{(cellResultData.probability * 100).toFixed(0)}% probability</Text>
                      </View>
                      <Text style={styles.resultExplanation}>{cellResultData.explanation}</Text>
                      <Text style={styles.carrierInfo}>Carrier: {cellResultData.carrier.toUpperCase()}</Text>
                    </>
                  )}
                  {!cellResultData && <Text style={styles.result}>{cellResult}</Text>}
                </View>
              )}
            </View>
          ) : (
            <View style={styles.tabContent}>
              <View style={styles.inputRow}>
                <Text style={styles.label}>South Horizon Obstruction (°)</Text>
                <TextInput
                  value={horizonSouth}
                  onChangeText={setHorizonSouth}
                  keyboardType={Platform.OS === 'ios' ? 'numbers-and-punctuation' : 'numeric'}
                  style={styles.input}
                  placeholder="e.g., 20"
                  placeholderTextColor="#9ca3af"
                />
              </View>

              <View style={styles.inputRow}>
                <Text style={styles.label}>Canopy Coverage (%)</Text>
                <TextInput
                  value={canopyPct}
                  onChangeText={setCanopyPct}
                  keyboardType={Platform.OS === 'ios' ? 'numbers-and-punctuation' : 'numeric'}
                  style={styles.input}
                  placeholder="e.g., 40"
                  placeholderTextColor="#9ca3af"
                />
              </View>

              <TouchableOpacity onPress={runStarlinkPrediction} style={styles.cta}>
                {loading ? <ActivityIndicator color="#1a1a1a" /> : <Text style={styles.ctaText}>Predict Risk</Text>}
              </TouchableOpacity>

              {starlinkResult && (
                <View style={styles.resultCard}>
                  <Text style={styles.resultTitle}>🛰️ Starlink Assessment</Text>
                  {starlinkResultData && (
                    <>
                      <View style={[styles.riskBox, getRiskStyle(starlinkResultData.risk_level)]}>
                        <Text style={styles.riskLabel}>Risk Level</Text>
                        <Text style={styles.riskValue}>{starlinkResultData.risk_level.toUpperCase()}</Text>
                        <Text style={styles.riskScore}>Obstruction Score: {starlinkResultData.obstruction_score}</Text>
                      </View>
                      <Text style={styles.resultExplanation}>{starlinkResultData.explanation}</Text>
                      {starlinkResultData.reasons && starlinkResultData.reasons.length > 0 && (
                        <View style={styles.reasonsBox}>
                          <Text style={styles.reasonsTitle}>Factors:</Text>
                          {starlinkResultData.reasons.map((reason: string, idx: number) => (
                            <Text key={idx} style={styles.reasonText}>• {reason}</Text>
                          ))}
                        </View>
                      )}
                    </>
                  )}
                  {!starlinkResultData && <Text style={styles.result}>{starlinkResult}</Text>}
                </View>
              )}
            </View>
          )}
        </View>
      </ScrollView>
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0a0a0a' },
  safeArea: { flex: 1, padding: 16 },
  backButton: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 16,
    gap: 8,
  },
  backText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '600',
  },
  content: { flex: 1 },
  card: { backgroundColor: '#18181b', borderRadius: 12, padding: 16, gap: 12, marginBottom: 16 },
  title: { color: '#fff', fontSize: 20, fontWeight: '800' },
  subtitle: { color: '#d4d4d8' },
  locationInfo: { flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: '#111827', padding: 10, borderRadius: 8 },
  locationText: { color: '#d4d4d8', fontSize: 12, flex: 1 },
  refreshBtn: { padding: 4 },
  locationButton: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#1f2937', paddingVertical: 10, borderRadius: 8, borderWidth: 1, borderColor: '#06b6d4' },
  locationButtonText: { color: '#06b6d4', fontWeight: '600', fontSize: 14 },
  tabRow: { flexDirection: 'row', gap: 8 },
  tabBtn: { flex: 1, backgroundColor: '#111827', paddingVertical: 10, borderRadius: 8, alignItems: 'center' },
  tabBtnActive: { backgroundColor: '#eab308' },
  tabText: { color: '#9ca3af', fontWeight: '700' },
  tabTextActive: { color: '#1a1a1a' },
  tabContent: { gap: 12 },
  helpText: { color: '#9ca3af', fontSize: 13, lineHeight: 18, fontStyle: 'italic' },
  inputRow: { gap: 6 },
  label: { color: '#e4e4e7', fontWeight: '600' },
  input: { backgroundColor: '#111827', color: '#fff', borderRadius: 8, paddingHorizontal: 12, paddingVertical: 10 },
  carrierRow: { flexDirection: 'row', gap: 8 },
  carrierBtn: { backgroundColor: '#111827', paddingVertical: 8, paddingHorizontal: 12, borderRadius: 8 },
  carrierBtnActive: { backgroundColor: '#eab308' },
  carrierText: { color: '#9ca3af', fontWeight: '700' },
  carrierTextActive: { color: '#1a1a1a' },
  cta: { backgroundColor: '#eab308', paddingVertical: 12, borderRadius: 8, alignItems: 'center' },
  ctaText: { color: '#1a1a1a', fontWeight: '800' },
  result: { backgroundColor: '#111827', borderRadius: 8, padding: 12, color: '#e5e7eb' },
  resultCard: { backgroundColor: '#111827', borderRadius: 8, padding: 16, gap: 12, marginTop: 8 },
  resultTitle: { color: '#06b6d4', fontSize: 16, fontWeight: '700' },
  signalBox: { backgroundColor: '#1f2937', borderRadius: 8, padding: 16, alignItems: 'center', borderWidth: 2, borderColor: '#06b6d4' },
  signalBars: { color: '#fff', fontSize: 28, fontWeight: '800' },
  signalProb: { color: '#9ca3af', fontSize: 14, marginTop: 4 },
  resultExplanation: { color: '#d4d4d8', fontSize: 14, lineHeight: 20 },
  carrierInfo: { color: '#9ca3af', fontSize: 12, fontStyle: 'italic' },
  riskBox: { backgroundColor: '#1f2937', borderRadius: 8, padding: 16, alignItems: 'center', borderWidth: 2 },
  riskLabel: { color: '#9ca3af', fontSize: 12, marginBottom: 4 },
  riskValue: { color: '#fff', fontSize: 24, fontWeight: '800' },
  riskScore: { color: '#d4d4d8', fontSize: 13, marginTop: 4 },
  reasonsBox: { backgroundColor: '#1f2937', borderRadius: 8, padding: 12 },
  reasonsTitle: { color: '#fbbf24', fontSize: 13, fontWeight: '700', marginBottom: 6 },
  reasonText: { color: '#d4d4d8', fontSize: 12, marginBottom: 2 },
});
