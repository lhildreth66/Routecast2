import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TextInput,
  TouchableOpacity,
  ActivityIndicator,
  Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import axios from 'axios';
import * as FileSystem from 'expo-file-system';
import * as Sharing from 'expo-sharing';
import { Buffer } from 'buffer';
import { API_BASE } from './apiConfig';

interface ClaimLogPreview {
  schema_version: string;
  route_id: string;
  generated_at: string;
  hazards: any[];
  weather_snapshot: any;
  totals: {
    total_events: number;
    by_type: Record<string, number>;
    by_severity: Record<string, number>;
  };
  narrative: string;
}

export default function ClaimLogScreen() {
  const [routeId, setRouteId] = useState('route_demo');
  const [hazardType, setHazardType] = useState('hail');
  const [severity, setSeverity] = useState('high');
  const [timestamp, setTimestamp] = useState(new Date().toISOString());
  const [lat, setLat] = useState('40.7128');
  const [lon, setLon] = useState('-74.0060');
  const [notes, setNotes] = useState('1-2 inch hailstones');

  const [weatherSummary, setWeatherSummary] = useState('Severe thunderstorm with large hail');
  const [weatherSource, setWeatherSource] = useState('NWS');
  const [weatherStart, setWeatherStart] = useState(new Date().toISOString());
  const [weatherEnd, setWeatherEnd] = useState(new Date(Date.now() + 3600 * 1000).toISOString());
  const [windMph, setWindMph] = useState('50');
  const [precipIn, setPrecipIn] = useState('0.75');

  const [loading, setLoading] = useState(false);
  const [preview, setPreview] = useState<ClaimLogPreview | null>(null);
  const [premiumModalVisible, setPremiumModalVisible] = useState(false);
  const [premiumMessage, setPremiumMessage] = useState('Upgrade to Routecast Pro to generate claim logs.');

  const buildPayload = () => ({
    routeId,
    hazards: [
      {
        timestamp,
        type: hazardType,
        severity,
        location: {
          latitude: parseFloat(lat),
          longitude: parseFloat(lon),
        },
        notes,
      },
    ],
    weatherSnapshot: {
      summary: weatherSummary,
      source: weatherSource,
      time_range: {
        start: weatherStart,
        end: weatherEnd,
      },
      key_metrics: {
        wind_mph: parseFloat(windMph),
        precip_in: parseFloat(precipIn),
      },
    },
    subscription_id: undefined,
  });

  const handlePremiumLock = () => {
    setPremiumMessage('Upgrade to Routecast Pro to generate claim logs.');
    setPremiumModalVisible(true);
  };

  const generatePreview = async () => {
    setLoading(true);
    setPreview(null);
    try {
      const entitled = await hasBoondockingPro();
      if (!entitled) {
        handlePremiumLock();
        return;
      }
      const payload = buildPayload();
      const res = await axios.post(`${API_BASE}/pro/claim-log/build`, payload);
      setPreview(res.data);
    } catch (err: any) {
      if (err?.response?.status === 402) {
        handlePremiumLock();
        return;
      }
      const msg = err?.response?.data?.detail || err?.message || 'Failed to build claim log';
      Alert.alert('Error', msg);
    } finally {
      setLoading(false);
    }
  };

  const downloadPdf = async () => {
    setLoading(true);
    try {
      const entitled = await hasBoondockingPro();
      if (!entitled) {
        handlePremiumLock();
        return;
      }
      const payload = buildPayload();
      const res = await axios.post(`${API_BASE}/pro/claim-log/pdf`, payload, { responseType: 'arraybuffer' });
      const base64 = Buffer.from(res.data, 'binary').toString('base64');
      const fileUri = `${FileSystem.cacheDirectory}claim_log_${routeId}.pdf`;
      await FileSystem.writeAsStringAsync(fileUri, base64, { encoding: FileSystem.EncodingType.Base64 });
      await Sharing.shareAsync(fileUri, {
        mimeType: 'application/pdf',
        dialogTitle: 'Routecast Claim Log',
      });
    } catch (err: any) {
      if (err?.response?.status === 402) {
        handlePremiumLock();
        return;
      }
      const msg = err?.response?.data?.detail || err?.message || 'Failed to generate PDF';
      Alert.alert('Error', msg);
    } finally {
      setLoading(false);
    }
  };

  const fillDemo = () => {
    setRouteId('route_demo');
    setHazardType('hail');
    setSeverity('high');
    setTimestamp('2026-01-18T14:30:00Z');
    setLat('40.7128');
    setLon('-74.0060');
    setNotes('1-2 inch hailstones');
    setWeatherSummary('Severe thunderstorm with large hail');
    setWeatherSource('NWS');
    setWeatherStart('2026-01-18T14:00:00Z');
    setWeatherEnd('2026-01-18T15:00:00Z');
    setWindMph('50');
    setPrecipIn('0.75');
  };

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.title}>Generate Claim Log</Text>
        <Text style={styles.subtitle}>Create an insurance-ready claim log and export as PDF.</Text>

        <View style={styles.card}>
          <Text style={styles.sectionTitle}>Route & Hazard</Text>
          <TextInput style={styles.input} placeholder="Route ID" value={routeId} onChangeText={setRouteId} />
          <TextInput style={styles.input} placeholder="Timestamp" value={timestamp} onChangeText={setTimestamp} />
          <View style={styles.row}>
            <TextInput style={[styles.input, styles.half]} placeholder="Hazard Type" value={hazardType} onChangeText={setHazardType} />
            <TextInput style={[styles.input, styles.half]} placeholder="Severity" value={severity} onChangeText={setSeverity} />
          </View>
          <View style={styles.row}>
            <TextInput style={[styles.input, styles.half]} placeholder="Latitude" value={lat} onChangeText={setLat} keyboardType="decimal-pad" />
            <TextInput style={[styles.input, styles.half]} placeholder="Longitude" value={lon} onChangeText={setLon} keyboardType="decimal-pad" />
          </View>
          <TextInput style={styles.input} placeholder="Notes" value={notes} onChangeText={setNotes} />
        </View>

        <View style={styles.card}>
          <Text style={styles.sectionTitle}>Weather Snapshot</Text>
          <TextInput style={styles.input} placeholder="Summary" value={weatherSummary} onChangeText={setWeatherSummary} />
          <TextInput style={styles.input} placeholder="Source" value={weatherSource} onChangeText={setWeatherSource} />
          <TextInput style={styles.input} placeholder="Start (ISO)" value={weatherStart} onChangeText={setWeatherStart} />
          <TextInput style={styles.input} placeholder="End (ISO)" value={weatherEnd} onChangeText={setWeatherEnd} />
          <View style={styles.row}>
            <TextInput style={[styles.input, styles.half]} placeholder="Wind mph" value={windMph} onChangeText={setWindMph} keyboardType="decimal-pad" />
            <TextInput style={[styles.input, styles.half]} placeholder="Precip in" value={precipIn} onChangeText={setPrecipIn} keyboardType="decimal-pad" />
          </View>
        </View>

        <View style={styles.actions}>
          <TouchableOpacity style={[styles.button, styles.secondary]} onPress={fillDemo} disabled={loading}>
            <Text style={styles.buttonTextSecondary}>Fill Demo</Text>
          </TouchableOpacity>
          <TouchableOpacity style={[styles.button, styles.primary]} onPress={generatePreview} disabled={loading}>
            {loading ? <ActivityIndicator color="#fff" /> : <Text style={styles.buttonText}>Preview JSON</Text>}
          </TouchableOpacity>
        </View>

        <TouchableOpacity style={[styles.button, styles.primary, { marginBottom: 16 }]} onPress={downloadPdf} disabled={loading}>
          {loading ? <ActivityIndicator color="#fff" /> : <Text style={styles.buttonText}>Generate PDF</Text>}
        </TouchableOpacity>

        {preview && (
          <View style={styles.previewCard}>
            <Text style={styles.sectionTitle}>Preview</Text>
            <Text style={styles.previewLabel}>Narrative</Text>
            <Text style={styles.previewText}>{preview.narrative}</Text>
            <Text style={styles.previewLabel}>Totals</Text>
            <Text style={styles.previewText}>Events: {preview.totals.total_events}</Text>
            <Text style={styles.previewText}>By Type: {JSON.stringify(preview.totals.by_type)}</Text>
            <Text style={styles.previewText}>By Severity: {JSON.stringify(preview.totals.by_severity)}</Text>
          </View>
        )}
      </ScrollView>

      <PaywallModal
        visible={premiumModalVisible}
        message={premiumMessage}
        onClose={() => setPremiumModalVisible(false)}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0a0a0a' },
  content: { padding: 16, gap: 12 },
  title: { color: '#fff', fontSize: 24, fontWeight: '800' },
  subtitle: { color: '#d4d4d8', fontSize: 14, marginBottom: 8 },
  card: { backgroundColor: '#18181b', borderRadius: 12, padding: 12, gap: 8 },
  sectionTitle: { color: '#fff', fontSize: 16, fontWeight: '700' },
  input: {
    backgroundColor: '#111827',
    borderRadius: 8,
    padding: 12,
    color: '#fff',
    borderWidth: 1,
    borderColor: '#27272a',
    fontSize: 14,
  },
  row: { flexDirection: 'row', gap: 8 },
  half: { flex: 1 },
  actions: { flexDirection: 'row', gap: 8, marginTop: 4 },
  button: {
    flex: 1,
    borderRadius: 10,
    paddingVertical: 12,
    alignItems: 'center',
    justifyContent: 'center',
  },
  primary: { backgroundColor: '#eab308' },
  secondary: { backgroundColor: '#111827', borderWidth: 1, borderColor: '#eab308' },
  buttonText: { color: '#1a1a1a', fontWeight: '800' },
  buttonTextSecondary: { color: '#eab308', fontWeight: '700' },
  previewCard: { backgroundColor: '#111827', borderRadius: 12, padding: 12, gap: 6 },
  previewLabel: { color: '#cbd5e1', fontWeight: '700' },
  previewText: { color: '#e5e7eb', fontSize: 13 },
});
