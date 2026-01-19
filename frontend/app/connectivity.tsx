import React, { useState } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, TextInput, Modal, ActivityIndicator, Platform } from 'react-native';
import axios from 'axios';
import { SafeAreaView } from 'react-native-safe-area-context';
import { API_BASE } from './apiConfig';
import PaywallModal from './components/PaywallModal';
import { hasBoondockingPro } from './utils/entitlements';

type ConnectivityTab = 'cell' | 'starlink';

export default function ConnectivityScreen() {
  // Cell inputs
  const [carrier, setCarrier] = useState<'verizon' | 'att' | 'tmobile'>('att');
  const [towerDistance, setTowerDistance] = useState('5');
  const [terrainObstruction, setTerrainObstruction] = useState('30');

  // Starlink inputs
  const [horizonSouth, setHorizonSouth] = useState('20');
  const [canopyPct, setCanopyPct] = useState('40');

  // UI state
  const [tab, setTab] = useState<ConnectivityTab>('cell');
  const [loading, setLoading] = useState(false);
  const [cellResult, setCellResult] = useState<string | null>(null);
  const [starlinkResult, setStarlinkResult] = useState<string | null>(null);
  const [premiumModalVisible, setPremiumModalVisible] = useState(false);
  const [premiumMessage, setPremiumMessage] = useState('');

  const runCellPrediction = async () => {
    setLoading(true);
    setCellResult(null);
    try {
      const entitled = await hasBoondockingPro();
      if (!entitled) {
        setPremiumMessage('Upgrade to Routecast Pro to predict cellular signal strength.');
        setPremiumModalVisible(true);
        return;
      }

      const payload = {
        carrier,
        towerDistanceKm: parseFloat(towerDistance || '0'),
        terrainObstructionPct: parseInt(terrainObstruction || '0', 10),
      };

      try {
        const resp = await axios.post(`${API_BASE}/api/pro/connectivity/cell-probability`, payload);
        const d = resp.data;
        setCellResult(`${d.bar_estimate} probability: ${(d.probability * 100).toFixed(0)}%. ${d.explanation}`);
      } catch (err: any) {
        const status = err?.response?.status;
        const code = err?.response?.data?.code || err?.response?.data?.detail?.code;
        const msg = err?.response?.data?.message || err?.response?.data?.detail?.message;
        if ((status === 402 || status === 403) && code === 'PREMIUM_LOCKED') {
          setPremiumMessage(msg || 'Upgrade to Routecast Pro to predict cellular signal.');
          setPremiumModalVisible(true);
          return;
        }
        setCellResult('Unable to predict cell signal right now.');
      }
    } finally {
      setLoading(false);
    }
  };

  const runStarlinkPrediction = async () => {
    setLoading(true);
    setStarlinkResult(null);
    try {
      const entitled = await hasBoondockingPro();
      if (!entitled) {
        setPremiumMessage('Upgrade to Routecast Pro to predict Starlink obstruction risk.');
        setPremiumModalVisible(true);
        return;
      }

      const payload = {
        horizonSouthDeg: parseInt(horizonSouth || '0', 10),
        canopyPct: parseInt(canopyPct || '0', 10),
      };

      try {
        const resp = await axios.post(`${API_BASE}/api/pro/connectivity/starlink-risk`, payload);
        const d = resp.data;
        const reasons = Array.isArray(d.reasons) ? d.reasons.join('; ') : '';
        setStarlinkResult(`${d.risk_level} risk (score: ${d.obstruction_score}). ${d.explanation}${reasons ? `; ${reasons}` : ''}`);
      } catch (err: any) {
        const status = err?.response?.status;
        const code = err?.response?.data?.code || err?.response?.data?.detail?.code;
        const msg = err?.response?.data?.message || err?.response?.data?.detail?.message;
        if ((status === 402 || status === 403) && code === 'PREMIUM_LOCKED') {
          setPremiumMessage(msg || 'Upgrade to Routecast Pro to predict Starlink risk.');
          setPremiumModalVisible(true);
          return;
        }
        setStarlinkResult('Unable to predict Starlink risk right now.');
      }
    } finally {
      setLoading(false);
    }
  };

  const fillCellDemo = () => {
    setCarrier('att');
    setTowerDistance('5');
    setTerrainObstruction('30');
  };

  const fillStarlinkDemo = () => {
    setHorizonSouth('40');
    setCanopyPct('60');
  };

  return (
    <View style={styles.container}>
      <SafeAreaView style={styles.safeArea}>
        <View style={styles.card}>
          <Text style={styles.title}>Connectivity (Pro)</Text>
          <Text style={styles.subtitle}>Predict cellular and Starlink signal quality</Text>

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

              <View style={styles.inputRow}>
                <Text style={styles.label}>Tower Distance (km)</Text>
                <TextInput
                  value={towerDistance}
                  onChangeText={setTowerDistance}
                  keyboardType={Platform.OS === 'ios' ? 'numbers-and-punctuation' : 'numeric'}
                  style={styles.input}
                  placeholder="e.g., 5"
                  placeholderTextColor="#9ca3af"
                />
              </View>

              <View style={styles.inputRow}>
                <Text style={styles.label}>Terrain Obstruction (%)</Text>
                <TextInput
                  value={terrainObstruction}
                  onChangeText={setTerrainObstruction}
                  keyboardType={Platform.OS === 'ios' ? 'numbers-and-punctuation' : 'numeric'}
                  style={styles.input}
                  placeholder="e.g., 30"
                  placeholderTextColor="#9ca3af"
                />
              </View>

              <TouchableOpacity onPress={runCellPrediction} style={styles.cta}>
                {loading ? <ActivityIndicator color="#1a1a1a" /> : <Text style={styles.ctaText}>Predict Signal</Text>}
              </TouchableOpacity>

              <TouchableOpacity onPress={fillCellDemo} style={[styles.cta, { backgroundColor: '#3f3f46' }]}>
                <Text style={[styles.ctaText, { color: '#fff' }]}>Try Demo</Text>
              </TouchableOpacity>

              {cellResult && <Text style={styles.result}>{cellResult}</Text>}
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

              <TouchableOpacity onPress={fillStarlinkDemo} style={[styles.cta, { backgroundColor: '#3f3f46' }]}>
                <Text style={[styles.ctaText, { color: '#fff' }]}>Try Demo</Text>
              </TouchableOpacity>

              {starlinkResult && <Text style={styles.result}>{starlinkResult}</Text>}
            </View>
          )}
        </View>

        <PaywallModal
          visible={premiumModalVisible}
          message={premiumMessage}
          onClose={() => setPremiumModalVisible(false)}
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
  tabRow: { flexDirection: 'row', gap: 8 },
  tabBtn: { flex: 1, backgroundColor: '#111827', paddingVertical: 10, borderRadius: 8, alignItems: 'center' },
  tabBtnActive: { backgroundColor: '#eab308' },
  tabText: { color: '#9ca3af', fontWeight: '700' },
  tabTextActive: { color: '#1a1a1a' },
  tabContent: { gap: 12 },
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
});
