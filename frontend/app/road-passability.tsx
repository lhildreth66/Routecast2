import React, { useState } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, TextInput, Modal, ActivityIndicator, Platform } from 'react-native';
import axios from 'axios';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { SafeAreaView } from 'react-native-safe-area-context';
import { API_BASE } from './apiConfig';
import { Paywall } from './billing/paywall';
import { requirePro } from './billing/guard';
import { useEntitlementsContext } from './billing/EntitlementsProvider';

// Entitlement sourced from AsyncStorage key 'entitlements.boondockingPro'

export default function RoadPassabilityScreen() {
  const [precip, setPrecip] = useState('1.2');
  const [slope, setSlope] = useState('12');
  const [temp, setTemp] = useState('30');
  const [soil, setSoil] = useState<'sand'|'loam'|'clay'>('clay');

  const [loading, setLoading] = useState(false);
  const [premiumModalVisible, setPremiumModalVisible] = useState(false);

  const [resultText, setResultText] = useState<string | null>(null);

  const { refresh } = useEntitlementsContext();

  const runAssessment = async () => {
    setLoading(true);
    setResultText(null);
    try {
      const guard = await requirePro();
      if (!guard.allowed) {
        setPremiumModalVisible(true);
        return;
      }

      const payload = {
        precip72hIn: parseFloat(precip || '0'),
        slopePct: parseFloat(slope || '0'),
        minTempF: parseInt(temp || '0', 10),
        soilType: soil,
        // No subscription_id per spec
      };

      try {
        const resp = await axios.post(`${API_BASE}/api/pro/road-passability`, payload);
        const d = resp.data;
        const flags = [
          d.mud_risk ? 'mud risk' : null,
          d.ice_risk ? 'ice risk' : null,
          d.four_by_four_recommended ? '4×4 recommended' : null,
        ].filter(Boolean).join(', ');
        const reasons = Array.isArray(d.reasons) ? d.reasons.join('; ') : '';
        setResultText(`Passability ${d.score}/100; clearance: ${d.clearance_need}${flags ? `; flags: ${flags}` : ''}. ${reasons}`);
      } catch (err: any) {
        const status = err?.response?.status;
        const code = err?.response?.data?.code || err?.response?.data?.detail?.code;
        const msg = err?.response?.data?.message || err?.response?.data?.detail?.message;
        if ((status === 402 || status === 403) && code === 'PREMIUM_LOCKED') {
          setPremiumModalVisible(true);
          return;
        }
        setResultText('Unable to assess passability right now.');
      }
    } finally {
      setLoading(false);
    }
  };

  const fillDemoInputs = () => {
    setPrecip('1.2');
    setSlope('12');
    setTemp('30');
    setSoil('clay');
  };

  return (
    <View style={styles.container}>
      <SafeAreaView style={styles.safeArea}>
        <View style={styles.card}>
          <Text style={styles.title}>Road Passability (Pro)</Text>
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

          <TouchableOpacity onPress={fillDemoInputs} style={[styles.cta, { backgroundColor: '#3f3f46' }] }>
            <Text style={[styles.ctaText, { color: '#fff' }]}>Try Demo Inputs</Text>
          </TouchableOpacity>

          {resultText && (
            <View style={styles.resultBox}>
              <Text style={styles.resultText}>{resultText}</Text>
            </View>
          )}
        </View>

        <Paywall
          visible={premiumModalVisible}
          onClose={() => setPremiumModalVisible(false)}
          onPurchaseComplete={async () => {
            await refresh();
            setPremiumModalVisible(false);
          }}
        />
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0a0a0a' },
  safeArea: { flex: 1, padding: 16 },
  card: { backgroundColor: '#18181b', borderRadius: 12, padding: 16, gap: 12 },
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
});
