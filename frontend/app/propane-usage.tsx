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
  const [premiumModalVisible, setPremiumModalVisible] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string>('');

  const calculate = async () => {
    setLoading(true);
    setResult(null);
    setError('');
    try {
      // TESTING: Paywall disabled
      // const guard = await requirePro();
      // if (!guard.allowed) {
      //   setPremiumModalVisible(true);
      //   return;
      // }

      const temps = nightsTempF.split(',').map(t => parseInt(t.trim(), 10)).filter(t => !isNaN(t));
      const resp = await axios.post(`${API_BASE}/api/pro/propane-usage`, {
        furnace_btu: parseInt(furnaceBtu, 10),
        duty_cycle_pct: parseFloat(dutyCyclePct),
        nights_temp_f: temps,
        subscription_id: 'test', // TESTING: Bypass premium check
      });
      setResult(resp.data);
    } catch (err: any) {
      console.error('Propane calculation error:', err);
      if (err?.response?.status === 402 || err?.response?.status === 403) {
        setPremiumModalVisible(true);
      } else {
        setError(err?.response?.data?.detail || err?.message || 'Failed to calculate propane usage');
      }
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
              <Text style={styles.resultText}>
                {result.advisory || 'Calculation complete'}
              </Text>
              {result.daily_lbs && (
                <Text style={styles.resultText}>
                  Daily usage: {result.daily_lbs.map((d: number) => d.toFixed(1)).join(', ')} lbs/day
                </Text>
              )}
            </View>
          )}
        </View>
      </ScrollView>

      <Paywall visible={premiumModalVisible} onClose={() => setPremiumModalVisible(false)} onPurchaseComplete={async () => { await refresh(); setPremiumModalVisible(false); }} />
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
  resultBox: { backgroundColor: '#111827', borderRadius: 8, padding: 12, gap: 8 },
  resultText: { color: '#e5e7eb', fontSize: 14 },
});
