import React, { useState } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, TextInput, Modal, ActivityIndicator, Platform, ScrollView } from 'react-native';
import axios from 'axios';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { API_BASE } from './apiConfig';

// Entitlement sourced from AsyncStorage key 'entitlements.boondockingPro'

export default function RoadPassabilityScreen() {
  const router = useRouter();
  const [precip, setPrecip] = useState('1.2');
  const [slope, setSlope] = useState('12');
  const [temp, setTemp] = useState('30');
  const [soil, setSoil] = useState<'sand'|'loam'|'clay'>('clay');

  const [loading, setLoading] = useState(false);

  const [resultText, setResultText] = useState<string | null>(null);
  const [result, setResult] = useState<any>(null);

  const runAssessment = async () => {
    setLoading(true);
    setResultText(null);
    setResult(null);
    try {
      const payload = {
        precip72hIn: parseFloat(precip || '0'),
        slopePct: parseFloat(slope || '0'),
        minTempF: parseInt(temp || '0', 10),
        soilType: soil,
      };

      try {
        const resp = await axios.post(`${API_BASE}/api/pro/road-passability`, payload);
        setResult(resp.data);
      } catch (err: any) {
        console.error('Road passability error:', err);
        setResultText('Unable to assess passability right now.');
      }
    } finally {
      setLoading(false);
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
            <Text style={styles.title}>Road Passability</Text>
            <Text style={styles.subtitle}>Assess mud, ice, and clearance risks</Text>

            <View style={styles.inputRow}>
            <Text style={styles.label}>Precip last 72h (in)</Text>
            <TextInput
              value={precip}
              onChangeText={setPrecip}
              keyboardType={Platform.OS === 'ios' ? 'numbers-and-punctuation' : 'numeric'}
              style={styles.input}
              placeholder="e.g., 1.2"
              placeholderTextColor="#9ca3af"
            />
          </View>

          <View style={styles.inputRow}>
            <Text style={styles.label}>Slope (%)</Text>
            <TextInput
              value={slope}
              onChangeText={setSlope}
              keyboardType={Platform.OS === 'ios' ? 'numbers-and-punctuation' : 'numeric'}
              style={styles.input}
              placeholder="e.g., 12"
              placeholderTextColor="#9ca3af"
            />
          </View>

          <View style={styles.inputRow}>
            <Text style={styles.label}>Min Temp (°F)</Text>
            <TextInput
              value={temp}
              onChangeText={setTemp}
              keyboardType={Platform.OS === 'ios' ? 'numbers-and-punctuation' : 'numeric'}
              style={styles.input}
              placeholder="e.g., 30"
              placeholderTextColor="#9ca3af"
            />
          </View>

          <View style={styles.inputRow}>
            <Text style={styles.label}>Soil Type</Text>
            <View style={styles.soilRow}>
              {(['sand','loam','clay'] as const).map((s) => (
                <TouchableOpacity
                  key={s}
                  onPress={() => setSoil(s)}
                  style={[styles.soilBtn, soil === s && styles.soilBtnActive]}
                >
                  <Text style={[styles.soilText, soil === s && styles.soilTextActive]}>{s.toUpperCase()}</Text>
                </TouchableOpacity>
              ))}
            </View>
          </View>

          <TouchableOpacity onPress={runAssessment} style={styles.cta}>
            {loading ? (
              <ActivityIndicator color="#1a1a1a" />
            ) : (
              <Text style={styles.ctaText}>Run Assessment</Text>
            )}
          </TouchableOpacity>

          {resultText && (
            <View style={styles.resultBox}>
              <Text style={styles.resultText}>{resultText}</Text>
            </View>
          )}

          {result && (
            <View style={styles.resultCard}>
              <Text style={styles.resultTitle}>🛣️ Assessment Results</Text>
              
              <View style={styles.scoreBox}>
                <Text style={styles.scoreLabel}>Passability Score</Text>
                <Text style={styles.scoreValue}>{result.passability_score}/100</Text>
                <Text style={styles.conditionText}>{result.condition_assessment}</Text>
              </View>

              {result.advisory && (
                <View style={styles.advisoryBox}>
                  <Text style={styles.advisoryText}>💡 {result.advisory}</Text>
                </View>
              )}

              <View style={styles.detailsRow}>
                <View style={styles.detailBox}>
                  <Text style={styles.detailLabel}>Min Clearance</Text>
                  <Text style={styles.detailValue}>{result.min_clearance_cm} cm</Text>
                </View>
                <View style={styles.detailBox}>
                  <Text style={styles.detailLabel}>Vehicle Type</Text>
                  <Text style={styles.detailValue}>{result.recommended_vehicle_type}</Text>
                </View>
              </View>

              {result.risks && (
                <View style={styles.risksBox}>
                  <Text style={styles.risksTitle}>⚠️ Risk Factors:</Text>
                  {result.risks.mud_risk && <Text style={styles.riskText}>• Mud Risk</Text>}
                  {result.risks.ice_risk && <Text style={styles.riskText}>• Ice Risk</Text>}
                  {result.risks.deep_rut_risk && <Text style={styles.riskText}>• Deep Rut Risk</Text>}
                  {result.risks.high_clearance_recommended && <Text style={styles.riskText}>• High Clearance Recommended</Text>}
                  {result.risks.four_x_four_recommended && <Text style={styles.riskText}>• 4×4 Recommended</Text>}
                  {!Object.values(result.risks).some(v => v) && (
                    <Text style={styles.noRiskText}>✅ No significant risks detected</Text>
                  )}
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
  inputRow: { gap: 6 },
  label: { color: '#e4e4e7', fontWeight: '600' },
  input: { backgroundColor: '#111827', color: '#fff', borderRadius: 8, paddingHorizontal: 12, paddingVertical: 10 },
  soilRow: { flexDirection: 'row', gap: 8 },
  soilBtn: { backgroundColor: '#111827', paddingVertical: 8, paddingHorizontal: 12, borderRadius: 8 },
  soilBtnActive: { backgroundColor: '#eab308' },
  soilText: { color: '#9ca3af', fontWeight: '700' },
  soilTextActive: { color: '#1a1a1a' },
  cta: { backgroundColor: '#eab308', paddingVertical: 12, borderRadius: 8, alignItems: 'center' },
  ctaText: { color: '#1a1a1a', fontWeight: '800' },
  resultBox: { backgroundColor: '#111827', borderRadius: 8, padding: 12 },
  resultText: { color: '#e5e7eb' },
  resultCard: { backgroundColor: '#111827', borderRadius: 8, padding: 16, gap: 12, marginTop: 8 },
  resultTitle: { color: '#eab308', fontSize: 18, fontWeight: '700', marginBottom: 4 },
  scoreBox: { backgroundColor: '#1f2937', borderRadius: 8, padding: 16, alignItems: 'center', borderWidth: 2, borderColor: '#eab308' },
  scoreLabel: { color: '#9ca3af', fontSize: 12, marginBottom: 4 },
  scoreValue: { color: '#fff', fontSize: 36, fontWeight: '800' },
  conditionText: { color: '#d4d4d8', fontSize: 14, fontWeight: '600', marginTop: 4 },
  advisoryBox: { backgroundColor: '#1e3a8a', borderRadius: 8, padding: 12 },
  advisoryText: { color: '#93c5fd', fontSize: 14, lineHeight: 20 },
  detailsRow: { flexDirection: 'row', gap: 12 },
  detailBox: { flex: 1, backgroundColor: '#1f2937', borderRadius: 8, padding: 12, alignItems: 'center' },
  detailLabel: { color: '#9ca3af', fontSize: 11, marginBottom: 4 },
  detailValue: { color: '#fff', fontSize: 16, fontWeight: '700' },
  risksBox: { backgroundColor: '#1f2937', borderRadius: 8, padding: 12, gap: 6 },
  risksTitle: { color: '#fbbf24', fontSize: 14, fontWeight: '700', marginBottom: 4 },
  riskText: { color: '#fca5a5', fontSize: 13 },
  noRiskText: { color: '#86efac', fontSize: 13 },
});
