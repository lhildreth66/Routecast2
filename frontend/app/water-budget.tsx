import React, { useState } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, TextInput, ActivityIndicator, ScrollView } from 'react-native';
import axios from 'axios';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { API_BASE } from './apiConfig';
import { Paywall } from './billing/paywall';
import { requirePro } from './billing/guard';
import { useEntitlementsContext } from './billing/EntitlementsProvider';

export default function WaterBudgetScreen() {
  const router = useRouter();
  const [freshGallons, setFreshGallons] = useState('40');
  const [grayGallons, setGrayGallons] = useState('30');
  const [blackGallons, setBlackGallons] = useState('20');
  const [numPeople, setNumPeople] = useState('2');
  const [showersPerWeek, setShowersPerWeek] = useState('2');

  const [loading, setLoading] = useState(false);
  const [premiumModalVisible, setPremiumModalVisible] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string>('');

  const { refresh } = useEntitlementsContext();

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

      const resp = await axios.post(`${API_BASE}/api/pro/water-budget`, {
        fresh_gal: parseInt(freshGallons, 10),
        gray_gal: parseInt(grayGallons, 10),
        black_gal: parseInt(blackGallons, 10),
        people: parseInt(numPeople, 10),
        showers_per_week: parseFloat(showersPerWeek),
        hot_days: false, // Could add a toggle for this
        subscription_id: 'test', // TESTING: Bypass premium check
      });
      setResult(resp.data);
    } catch (err: any) {
      console.error('Water budget calculation error:', err);
      if (err?.response?.status === 402 || err?.response?.status === 403) {
        setPremiumModalVisible(true);
      } else {
        setError(err?.response?.data?.detail || err?.message || 'Failed to calculate water budget');
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
          <Text style={styles.title}>Water Planning</Text>
          <Text style={styles.subtitle}>Calculate how long your water tanks will last</Text>

          <View style={styles.inputRow}>
            <Text style={styles.label}>Fresh Water Tank (gallons)</Text>
            <TextInput
              value={freshGallons}
              onChangeText={setFreshGallons}
              keyboardType="numeric"
              style={styles.input}
              placeholder="e.g., 40"
              placeholderTextColor="#9ca3af"
            />
          </View>

          <View style={styles.inputRow}>
            <Text style={styles.label}>Gray Water Tank (gallons)</Text>
            <TextInput
              value={grayGallons}
              onChangeText={setGrayGallons}
              keyboardType="numeric"
              style={styles.input}
              placeholder="e.g., 30"
              placeholderTextColor="#9ca3af"
            />
          </View>

          <View style={styles.inputRow}>
            <Text style={styles.label}>Black Water Tank (gallons)</Text>
            <TextInput
              value={blackGallons}
              onChangeText={setBlackGallons}
              keyboardType="numeric"
              style={styles.input}
              placeholder="e.g., 20"
              placeholderTextColor="#9ca3af"
            />
          </View>

          <View style={styles.inputRow}>
            <Text style={styles.label}>Number of People</Text>
            <TextInput
              value={numPeople}
              onChangeText={setNumPeople}
              keyboardType="numeric"
              style={styles.input}
              placeholder="e.g., 2"
              placeholderTextColor="#9ca3af"
            />
          </View>

          <View style={styles.inputRow}>
            <Text style={styles.label}>Showers Per Week</Text>
            <TextInput
              value={showersPerWeek}
              onChangeText={setShowersPerWeek}
              keyboardType="numeric"
              style={styles.input}
              placeholder="e.g., 2"
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
              <Text style={styles.resultTitle}>Water Budget Results</Text>
              {result.days_remaining !== null && result.days_remaining !== undefined ? (
                <>
                  <Text style={styles.resultText}>
                    ⏱️ Days Remaining: {result.days_remaining} days
                  </Text>
                  <Text style={styles.resultText}>
                    🚰 Limiting Factor: {result.limiting_factor || 'N/A'}
                  </Text>
                  <View style={styles.usageBreakdown}>
                    <Text style={styles.breakdownTitle}>Daily Usage:</Text>
                    {result.daily_fresh_gal && (
                      <Text style={styles.usageText}>Fresh: {result.daily_fresh_gal.toFixed(1)} gal/day</Text>
                    )}
                    {result.daily_gray_gal && (
                      <Text style={styles.usageText}>Gray: {result.daily_gray_gal.toFixed(1)} gal/day</Text>
                    )}
                    {result.daily_black_gal && (
                      <Text style={styles.usageText}>Black: {result.daily_black_gal.toFixed(1)} gal/day</Text>
                    )}
                  </View>
                  {result.advisory && (
                    <View style={styles.advisoryBox}>
                      <Text style={styles.advisoryText}>{result.advisory}</Text>
                    </View>
                  )}
                </>
              ) : (
                <Text style={styles.resultText}>No calculation data available</Text>
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
  resultTitle: { color: '#eab308', fontSize: 16, fontWeight: '700', marginBottom: 4 },
  resultText: { color: '#e5e7eb', fontSize: 14 },
  usageBreakdown: { marginTop: 8, gap: 4, paddingTop: 8, borderTopWidth: 1, borderTopColor: '#27272a' },
  breakdownTitle: { color: '#a1a1aa', fontSize: 12, fontWeight: '600', marginBottom: 4 },
  usageText: { color: '#d4d4d8', fontSize: 13 },
  advisoryBox: { backgroundColor: '#1e3a8a', borderRadius: 6, padding: 8, marginTop: 4 },
  advisoryText: { color: '#93c5fd', fontSize: 12 },
});
