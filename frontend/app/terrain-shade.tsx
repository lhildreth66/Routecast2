import React, { useState } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, TextInput, ActivityIndicator, ScrollView, Alert } from 'react-native';
import axios from 'axios';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import * as Location from 'expo-location';
import { API_BASE } from './apiConfig';

export default function TerrainShadeScreen() {
  const router = useRouter();
  const [latitude, setLatitude] = useState('34.05');
  const [longitude, setLongitude] = useState('-111.03');
  const [date, setDate] = useState('2026-06-15');

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

  const calculate = async () => {
    setLoading(true);
    setResult(null);
    try {
      const resp = await axios.post(`${API_BASE}/api/pro/terrain/sun-path`, {
        latitude: parseFloat(latitude),
        longitude: parseFloat(longitude),
        date: date,
        tree_canopy_pct: 0,
        horizon_obstruction_deg: 0,
      });
      setResult(resp.data);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to analyze terrain shade');
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
          <Text style={styles.title}>Terrain Shade</Text>
          <Text style={styles.subtitle}>Analyze terrain shading at your campsite</Text>

          <View style={styles.locationInfo}>
            <Ionicons name="location" size={16} color="#fbbf24" />
            <Text style={styles.locationText}>
              Analyzing: {latitude}, {longitude}
            </Text>
          </View>

          <TouchableOpacity onPress={useCurrentLocation} style={styles.locationButton}>
            <Ionicons name="locate" size={18} color="#fbbf24" />
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
            <Text style={styles.label}>Date (YYYY-MM-DD)</Text>
            <TextInput
              value={date}
              onChangeText={setDate}
              style={styles.input}
              placeholder="e.g., 2026-06-15"
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
              <Text style={styles.resultTitle}>☀️ Sun Exposure Analysis</Text>
              <Text style={styles.resultText}>
                Effective Sun Hours: {result.exposure_hours?.toFixed(1)} hrs
              </Text>
              <Text style={styles.resultText}>
                Shade Coverage: {((result.shade_factor || 0) * 100).toFixed(0)}%
              </Text>
              
              {result.sun_path_slots && result.sun_path_slots.length > 0 && (
                <>
                  <Text style={styles.resultSubtitle}>Hourly Sun Path:</Text>
                  <ScrollView horizontal style={styles.hoursScroll} showsHorizontalScrollIndicator={false}>
                    {result.sun_path_slots.map((slot: any) => (
                      <View key={slot.hour} style={styles.hourCard}>
                        <Text style={styles.hourTime}>{slot.time_label}</Text>
                        <Text style={styles.hourValue}>{slot.sun_elevation_deg.toFixed(0)}°</Text>
                        <Text style={styles.hourLabel}>
                          {(slot.usable_sunlight_fraction * 100).toFixed(0)}% usable
                        </Text>
                      </View>
                    ))}
                  </ScrollView>
                </>
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
  locationButton: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#1f2937', paddingVertical: 10, borderRadius: 8, borderWidth: 1, borderColor: '#fbbf24' },
  locationButtonText: { color: '#fbbf24', fontWeight: '600', fontSize: 14 },
  inputRow: { gap: 6 },
  label: { color: '#e4e4e7', fontWeight: '600' },
  input: { backgroundColor: '#111827', color: '#fff', borderRadius: 8, paddingHorizontal: 12, paddingVertical: 10 },
  button: { backgroundColor: '#eab308', paddingVertical: 12, borderRadius: 8, alignItems: 'center' },
  buttonText: { color: '#1a1a1a', fontWeight: '800' },
  errorBox: { backgroundColor: '#7f1d1d', borderRadius: 8, padding: 12 },
  errorText: { color: '#fecaca', fontSize: 14 },
  resultBox: { backgroundColor: '#111827', borderRadius: 8, padding: 12, gap: 8 },
  resultTitle: { color: '#fff', fontSize: 16, fontWeight: '700', marginBottom: 4 },
  resultSubtitle: { color: '#d4d4d8', fontSize: 14, fontWeight: '600', marginTop: 8, marginBottom: 4 },
  resultText: { color: '#e5e7eb', fontSize: 14 },
  hoursScroll: { marginTop: 4 },
  hourCard: { backgroundColor: '#1f2937', borderRadius: 8, padding: 10, marginRight: 8, minWidth: 80, alignItems: 'center' },
  hourTime: { color: '#fbbf24', fontSize: 12, fontWeight: '600' },
  hourValue: { color: '#fff', fontSize: 18, fontWeight: '700', marginVertical: 2 },
  hourLabel: { color: '#9ca3af', fontSize: 10 },
});
