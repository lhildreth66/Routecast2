import React, { useState } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, TextInput, ActivityIndicator, ScrollView } from 'react-native';
import axios from 'axios';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { API_BASE } from './apiConfig';

export default function PropaneUsageScreen() {
  const router = useRouter();
  const [furnaceBtu, setFurnaceBtu] = useState('30000');
  const [dutyCyclePct, setDutyCyclePct] = useState('40');
  const [nightsTempF, setNightsTempF] = useState('32,35,38');

  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string>('');

  const calculate = async () => {
    setLoading(true);
    setResult(null);
    setError('');
    try {
      const temps = nightsTempF.split(',').map(t => parseInt(t.trim(), 10)).filter(t => !isNaN(t));
      const resp = await axios.post(`${API_BASE}/api/pro/propane-usage`, {
        furnace_btu: parseInt(furnaceBtu, 10),
        duty_cycle_pct: parseFloat(dutyCyclePct),
        nights_temp_f: temps,
      });
      setResult(resp.data);
    } catch (err: any) {
      console.error('Propane calculation error:', err);
      setError(err?.response?.data?.detail || err?.message || 'Failed to calculate propane usage');
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
          <Text style={styles.title}>Propane Usage</Text>
          <Text style={styles.subtitle}>Calculate fuel consumption for your trip</Text>

          <View style={styles.inputRow}>
            <Text style={styles.label}>Furnace BTU Capacity</Text>
            <TextInput
              value={furnaceBtu}
              onChangeText={setFurnaceBtu}
              keyboardType="numeric"
              style={styles.input}
              placeholder="e.g., 30000"
              placeholderTextColor="#9ca3af"
            />
          </View>

          <View style={styles.inputRow}>
            <Text style={styles.label}>Furnace Duty Cycle (%)</Text>
            <TextInput
              value={dutyCyclePct}
              onChangeText={setDutyCyclePct}
              keyboardType="numeric"
              style={styles.input}
              placeholder="e.g., 40"
              placeholderTextColor="#9ca3af"
            />
          </View>

          <View style={styles.inputRow}>
            <Text style={styles.label}>Nightly Temps (°F, comma-separated)</Text>
            <TextInput
              value={nightsTempF}
              onChangeText={setNightsTempF}
              style={styles.input}
              placeholder="e.g., 32,35,38"
              placeholderTextColor="#9ca3af"
            />
          </View>

          <TouchableOpacity onPress={calculate} style={styles.button} disabled={loading}>
            {loading ? <ActivityIndicator color="#1a1a1a" /> : <Text style={styles.buttonText}>Calculate</Text>}
          </TouchableOpacity>

          {error && (
            <View style={styles.errorBox}>
              <Text style={styles.errorText}>❌ {error}</Text>
            </View>
          )}

          {result && (
            <View style={styles.resultBox}>
              <Text style={styles.resultTitle}>📊 Propane Usage Estimate</Text>
              
              {result.advisory && (
                <Text style={styles.advisoryText}>{result.advisory}</Text>
              )}
              
              {result.daily_lbs && (
                <View style={styles.usageSection}>
                  <Text style={styles.sectionLabel}>Daily Usage (Typical):</Text>
                  {result.daily_lbs.map((lbs: number, idx: number) => (
                    <Text key={idx} style={styles.usageValue}>
                      Night {idx + 1}: {lbs.toFixed(1)} lbs/day
                    </Text>
                  ))}
                </View>
              )}
              
              {result.daily_lbs_best && result.daily_lbs_worst && (
                <View style={styles.rangesSection}>
                  <Text style={styles.sectionLabel}>📈 Best/Worst Case Ranges:</Text>
                  {result.daily_lbs_best.map((best: number, idx: number) => (
                    <Text key={idx} style={styles.rangeText}>
                      Night {idx + 1}: {best.toFixed(1)} - {result.daily_lbs_worst[idx].toFixed(1)} lbs/day
                    </Text>
                  ))}
                </View>
              )}
              
              {result.tank_status && (
                <View style={[styles.tankStatus, { 
                  backgroundColor: result.tank_status === 'comfortable' ? '#065f4620' : 
                                   result.tank_status === 'borderline' ? '#78350f20' : '#7f1d1d20',
                  borderColor: result.tank_status === 'comfortable' ? '#059669' : 
                               result.tank_status === 'borderline' ? '#d97706' : '#dc2626'
                }]}>
                  <Text style={[styles.tankLabel, {
                    color: result.tank_status === 'comfortable' ? '#10b981' : 
                           result.tank_status === 'borderline' ? '#f59e0b' : '#ef4444'
                  }]}>
                    {result.tank_status === 'comfortable' ? '✅ Tank Comfortable' :
                     result.tank_status === 'borderline' ? '⚠️ Tank Borderline' : '🚨 High Risk'}
                  </Text>
                  {result.tank_explanation && (
                    <Text style={styles.tankExplanation}>{result.tank_explanation}</Text>
                  )}
                </View>
              )}
              
              {result.cold_weather_warnings && result.cold_weather_warnings.length > 0 && (
                <View style={styles.warningsSection}>
                  <Text style={styles.warningTitle}>⚠️ Cold Weather Warnings:</Text>
                  {result.cold_weather_warnings.map((warning: string, idx: number) => (
                    <Text key={idx} style={styles.warningText}>• {warning}</Text>
                  ))}
                </View>
              )}
              
              {result.assumptions_used && result.assumptions_used.length > 0 && (
                <View style={styles.assumptionsSection}>
                  <Text style={styles.assumptionTitle}>💡 Assumptions:</Text>
                  {result.assumptions_used.map((assumption: string, idx: number) => (
                    <Text key={idx} style={styles.assumptionText}>• {assumption}</Text>
                  ))}
                </View>
              )}
              
              {result.ai_used && (
                <Text style={styles.aiIndicator}>
                  ✨ Enhanced with AI ({result.fallback_level || 'full_ai'})
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
  inputRow: { gap: 6 },
  label: { color: '#e4e4e7', fontWeight: '600' },
  input: { backgroundColor: '#111827', color: '#fff', borderRadius: 8, paddingHorizontal: 12, paddingVertical: 10 },
  button: { backgroundColor: '#eab308', paddingVertical: 12, borderRadius: 8, alignItems: 'center' },
  buttonText: { color: '#1a1a1a', fontWeight: '800' },
  errorBox: { backgroundColor: '#7f1d1d', borderRadius: 8, padding: 12 },
  errorText: { color: '#fecaca', fontSize: 14 },
  resultBox: { backgroundColor: '#111827', borderRadius: 8, padding: 16, gap: 12 },
  resultTitle: { color: '#fff', fontSize: 18, fontWeight: '700', marginBottom: 4 },
  advisoryText: { color: '#e5e7eb', fontSize: 14, lineHeight: 20 },
  usageSection: { gap: 4 },
  sectionLabel: { color: '#9ca3af', fontSize: 13, fontWeight: '600', marginBottom: 4 },
  usageValue: { color: '#fbbf24', fontSize: 14, fontWeight: '600', marginLeft: 8 },
  rangesSection: { gap: 4, marginTop: 8 },
  rangeText: { color: '#06b6d4', fontSize: 13, marginLeft: 8 },
  tankStatus: { borderRadius: 8, borderWidth: 1, padding: 12, marginTop: 8 },
  tankLabel: { fontSize: 15, fontWeight: '700', marginBottom: 4 },
  tankExplanation: { color: '#d4d4d8', fontSize: 13, lineHeight: 18 },
  warningsSection: { backgroundColor: '#7f1d1d', borderRadius: 8, padding: 12, marginTop: 8 },
  warningTitle: { color: '#fecaca', fontSize: 14, fontWeight: '700', marginBottom: 6 },
  warningText: { color: '#fecaca', fontSize: 13, lineHeight: 18 },
  assumptionsSection: { backgroundColor: '#18181b', borderRadius: 8, padding: 12, marginTop: 8, borderWidth: 1, borderColor: '#3f3f46' },
  assumptionTitle: { color: '#a1a1aa', fontSize: 13, fontWeight: '600', marginBottom: 6 },
  assumptionText: { color: '#a1a1aa', fontSize: 12, lineHeight: 18 },
  aiIndicator: { color: '#818cf8', fontSize: 12, fontStyle: 'italic', marginTop: 4, textAlign: 'center' },
});
