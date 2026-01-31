import React, { useState } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, TextInput, ActivityIndicator, Platform, ScrollView, Alert } from 'react-native';
import axios from 'axios';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import * as Location from 'expo-location';
import { API_BASE } from './apiConfig';

export default function SolarForecastScreen() {
  const router = useRouter();
  const [latitude, setLatitude] = useState('34.05');
  const [longitude, setLongitude] = useState('-111.03');
  const [panelWatts, setPanelWatts] = useState('400');
  const [numPanels, setNumPanels] = useState('2');

  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string>('');

  const useCurrentLocation = async () => {
    try {
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== 'granted') {
        Alert.alert('Permission Denied', 'Location permission is required to use current location.');
        return;
      }

      const location = await Location.getCurrentPositionAsync({});
      setLatitude(location.coords.latitude.toFixed(4));
      setLongitude(location.coords.longitude.toFixed(4));
      Alert.alert('Location Updated', `Using current position: ${location.coords.latitude.toFixed(4)}, ${location.coords.longitude.toFixed(4)}`);
    } catch (err) {
      Alert.alert('Error', 'Failed to get current location');
    }
  };

  const runForecast = async () => {
    setLoading(true);
    setResult(null);
    setError('');
    try {
      // Generate next 7 days
      const dates = [];
      for (let i = 0; i < 7; i++) {
        const d = new Date();
        d.setDate(d.getDate() + i);
        dates.push(d.toISOString().split('T')[0]);
      }

      const totalWatts = parseInt(panelWatts, 10) * parseInt(numPanels, 10);

      const resp = await axios.post(`${API_BASE}/api/pro/solar-forecast`, {
        lat: parseFloat(latitude),
        lon: parseFloat(longitude),
        date_range: dates,
        panel_watts: totalWatts,
        shade_pct: 10, // Default 10% shade
        cloud_cover: Array(7).fill(30), // Default 30% cloud cover
      });
      setResult(resp.data);
    } catch (err: any) {
      console.error('Solar forecast error:', err);
      console.error('Response:', err?.response?.data);
      setError(err?.response?.data?.detail || err?.message || 'Failed to calculate solar forecast');
    } finally {
      setLoading(false);
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
          <Text style={styles.title}>Solar Forecast</Text>
          <Text style={styles.subtitle}>Estimate solar power output at your campsite</Text>

          <View style={styles.locationInfo}>
            <Ionicons name="location" size={16} color="#eab308" />
            <Text style={styles.locationText}>
              Analyzing: {latitude}, {longitude}
            </Text>
          </View>

          <TouchableOpacity onPress={useCurrentLocation} style={styles.locationButton}>
            <Ionicons name="locate" size={18} color="#eab308" />
            <Text style={styles.locationButtonText}>Use Current Location</Text>
          </TouchableOpacity>

          <View style={styles.inputRow}>
            <Text style={styles.label}>Latitude</Text>
            <TextInput
              value={latitude}
              onChangeText={setLatitude}
              keyboardType="numeric"
              style={styles.input}
              placeholder="e.g., 34.05"
              placeholderTextColor="#9ca3af"
            />
          </View>

          <View style={styles.inputRow}>
            <Text style={styles.label}>Longitude</Text>
            <TextInput
              value={longitude}
              onChangeText={setLongitude}
              keyboardType="numeric"
              style={styles.input}
              placeholder="e.g., -111.03"
              placeholderTextColor="#9ca3af"
            />
          </View>

          <View style={styles.inputRow}>
            <Text style={styles.label}>Panel Watts</Text>
            <TextInput
              value={panelWatts}
              onChangeText={setPanelWatts}
              keyboardType="numeric"
              style={styles.input}
              placeholder="e.g., 400"
              placeholderTextColor="#9ca3af"
            />
          </View>

          <View style={styles.inputRow}>
            <Text style={styles.label}>Number of Panels</Text>
            <TextInput
              value={numPanels}
              onChangeText={setNumPanels}
              keyboardType="numeric"
              style={styles.input}
              placeholder="e.g., 2"
              placeholderTextColor="#9ca3af"
            />
          </View>

          <TouchableOpacity onPress={runForecast} style={styles.button} disabled={loading}>
            {loading ? <ActivityIndicator color="#1a1a1a" /> : <Text style={styles.buttonText}>Calculate</Text>}
          </TouchableOpacity>

          {error && (
            <View style={styles.errorBox}>
              <Text style={styles.errorText}>❌ {error}</Text>
            </View>
          )}

          {result && (
            <View style={styles.resultBox}>
              <Text style={styles.resultTitle}>Solar Forecast Results</Text>
              {result.daily_wh && result.daily_wh.length > 0 ? (
                <>
                  <Text style={styles.resultText}>
                    Daily Average: {(result.daily_wh.reduce((a: number, b: number) => a + b, 0) / result.daily_wh.length).toFixed(0)} Wh/day
                  </Text>
                  <Text style={styles.resultText}>
                    7-Day Range: {Math.min(...result.daily_wh).toFixed(0)} - {Math.max(...result.daily_wh).toFixed(0)} Wh
                  </Text>
                  <Text style={styles.resultText}>
                    Peak Hours Estimate: {((result.daily_wh.reduce((a: number, b: number) => a + b, 0) / result.daily_wh.length) / (result.panel_watts || 1) * 1000).toFixed(1)} hrs/day
                  </Text>
                  {result.advisory && (
                    <View style={styles.advisoryBox}>
                      <Text style={styles.advisoryText}>{result.advisory}</Text>
                    </View>
                  )}
                  <View style={styles.dailyBreakdown}>
                    <Text style={styles.breakdownTitle}>Daily Breakdown:</Text>
                    {result.dates?.map((date: string, idx: number) => (
                      <View key={idx} style={styles.dailyRow}>
                        <Text style={styles.dateText}>{new Date(date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}</Text>
                        <Text style={styles.whText}>{result.daily_wh[idx].toFixed(0)} Wh</Text>
                      </View>
                    ))}
                  </View>
                </>
              ) : (
                <Text style={styles.resultText}>No forecast data available</Text>
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
  locationText: { color: '#d4d4d8', fontSize: 12 },
  locationButton: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#1f2937', paddingVertical: 10, borderRadius: 8, borderWidth: 1, borderColor: '#eab308' },
  locationButtonText: { color: '#eab308', fontWeight: '600', fontSize: 14 },
  inputRow: { gap: 6 },
  label: { color: '#e4e4e7', fontWeight: '600' },
  input: { backgroundColor: '#111827', color: '#fff', borderRadius: 8, paddingHorizontal: 12, paddingVertical: 10 },
  button: { backgroundColor: '#eab308', paddingVertical: 12, borderRadius: 8, alignItems: 'center' },
  buttonText: { color: '#1a1a1a', fontWeight: '800' },
  errorBox: { backgroundColor: '#7f1d1d', borderRadius: 8, padding: 12 },
  errorText: { color: '#fecaca', fontSize: 14 },
  resultBox: { backgroundColor: '#111827', borderRadius: 8, padding: 12, gap: 8 },
  resultTitle: { color: '#eab308', fontSize: 16, fontWeight: '700', marginBottom: 4 },
  resultText: { color: '#e5e7eb', fontSize: 14 },
  advisoryBox: { backgroundColor: '#1e3a8a', borderRadius: 6, padding: 8, marginTop: 4 },
  advisoryText: { color: '#93c5fd', fontSize: 12 },
  dailyBreakdown: { marginTop: 12, gap: 4 },
  breakdownTitle: { color: '#a1a1aa', fontSize: 12, fontWeight: '600', marginBottom: 4 },
  dailyRow: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 4 },
  dateText: { color: '#9ca3af', fontSize: 13 },
  whText: { color: '#d4d4d8', fontSize: 13, fontWeight: '600' },
});
