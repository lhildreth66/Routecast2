import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  TextInput,
  ActivityIndicator,
  Alert,
} from 'react-native';
import { useRouter } from 'expo-router';
import PaywallModal from './components/PaywallModal';
import { hasBoondockingPro } from './utils/entitlements';

interface CampsiteIndexResult {
  score: number;
  breakdown: {
    wind: number;
    shade: number;
    slope: number;
    access: number;
    signal: number;
    passability: number;
  };
  explanations: string[];
}

export default function CampsiteIndexScreen() {
  const router = useRouter();
  const [windGustMph, setWindGustMph] = useState('15');
  const [shadeScore, setShadeScore] = useState('0.5');
  const [slopePct, setSlopePct] = useState('8');
  const [accessScore, setAccessScore] = useState('0.7');
  const [signalScore, setSignalScore] = useState('0.6');
  const [passabilityScore, setPassabilityScore] = useState('75');

  const [result, setResult] = useState<CampsiteIndexResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [showPaywall, setShowPaywall] = useState(false);
  const [premiumMessage, setPremiumMessage] = useState('');
  const [isPro, setIsPro] = useState(false);

  useEffect(() => {
    const checkPro = async () => {
      const pro = await hasBoondockingPro();
      setIsPro(pro);
    };
    checkPro();
  }, []);

  const fillDemoValues = () => {
    setWindGustMph('20');
    setShadeScore('0.6');
    setSlopePct('8');
    setAccessScore('0.7');
    setSignalScore('0.4');
    setPassabilityScore('75');
  };

  const calculateScore = async () => {
    if (!isPro) {
      setPremiumMessage('Upgrade to Routecast Pro to calculate Campsite Index scores.');
      setShowPaywall(true);
      return;
    }

    setLoading(true);
    try {
      const response = await fetch('http://localhost:8000/api/pro/campsite-index', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          wind_gust_mph: parseFloat(windGustMph),
          shade_score: parseFloat(shadeScore),
          slope_pct: parseFloat(slopePct),
          access_score: parseFloat(accessScore),
          signal_score: parseFloat(signalScore),
          road_passability_score: parseFloat(passabilityScore),
          subscription_id: 'test-subscription', // For demo
        }),
      });

      if (response.status === 402) {
        setPremiumMessage('Upgrade to Routecast Pro to calculate Campsite Index scores.');
        setShowPaywall(true);
        return;
      }

      if (!response.ok) {
        const error = await response.json();
        Alert.alert('Error', error.detail || 'Failed to calculate campsite index');
        return;
      }

      const data = await response.json();
      setResult(data);
    } catch (error) {
      Alert.alert('Error', 'Failed to connect to server. Make sure backend is running.');
    } finally {
      setLoading(false);
    }
  };

  const getScoreColor = (score: number) => {
    if (score >= 80) return '#4CAF50'; // Green
    if (score >= 60) return '#2196F3'; // Blue
    if (score >= 40) return '#FF9800'; // Orange
    return '#F44336'; // Red
  };

  return (
    <ScrollView style={styles.container}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
          <Text style={styles.backText}>← Back</Text>
        </TouchableOpacity>
        <Text style={styles.title}>Campsite Index</Text>
        <Text style={styles.subtitle}>Calculate overall campsite quality score</Text>
      </View>

      <View style={styles.card}>
        <Text style={styles.sectionTitle}>Site Conditions</Text>

        <View style={styles.inputGroup}>
          <Text style={styles.label}>Wind Gust (mph)</Text>
          <TextInput
            style={styles.input}
            placeholder="e.g., 15"
            keyboardType="decimal-pad"
            value={windGustMph}
            onChangeText={setWindGustMph}
            editable={!loading}
          />
          <Text style={styles.hint}>0-40+ mph. Higher wind reduces comfort.</Text>
        </View>

        <View style={styles.inputGroup}>
          <Text style={styles.label}>Shade Score (0-1)</Text>
          <TextInput
            style={styles.input}
            placeholder="e.g., 0.5"
            keyboardType="decimal-pad"
            value={shadeScore}
            onChangeText={setShadeScore}
            editable={!loading}
          />
          <Text style={styles.hint}>0 = no shade, 1 = full shade coverage</Text>
        </View>

        <View style={styles.inputGroup}>
          <Text style={styles.label}>Slope (%)</Text>
          <TextInput
            style={styles.input}
            placeholder="e.g., 8"
            keyboardType="decimal-pad"
            value={slopePct}
            onChangeText={setSlopePct}
            editable={!loading}
          />
          <Text style={styles.hint}>0% = flat, 25%+ = steep. Steeper slopes are harder to set up.</Text>
        </View>

        <View style={styles.inputGroup}>
          <Text style={styles.label}>Access Score (0-1)</Text>
          <TextInput
            style={styles.input}
            placeholder="e.g., 0.7"
            keyboardType="decimal-pad"
            value={accessScore}
            onChangeText={setAccessScore}
            editable={!loading}
          />
          <Text style={styles.hint}>0 = poor road/parking access, 1 = excellent</Text>
        </View>

        <View style={styles.inputGroup}>
          <Text style={styles.label}>Signal Score (0-1)</Text>
          <TextInput
            style={styles.input}
            placeholder="e.g., 0.6"
            keyboardType="decimal-pad"
            value={signalScore}
            onChangeText={setSignalScore}
            editable={!loading}
          />
          <Text style={styles.hint}>0 = no signal, 1 = excellent connectivity</Text>
        </View>

        <View style={styles.inputGroup}>
          <Text style={styles.label}>Road Passability Score (0-100)</Text>
          <TextInput
            style={styles.input}
            placeholder="e.g., 75"
            keyboardType="decimal-pad"
            value={passabilityScore}
            onChangeText={setPassabilityScore}
            editable={!loading}
          />
          <Text style={styles.hint}>0 = impassable, 100 = easily drivable</Text>
        </View>
      </View>

      <View style={styles.buttonGroup}>
        <TouchableOpacity
          style={[styles.button, styles.primaryButton]}
          onPress={calculateScore}
          disabled={loading}
        >
          {loading ? (
            <ActivityIndicator color="#FFF" />
          ) : (
            <Text style={styles.buttonText}>Calculate Score</Text>
          )}
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.button, styles.secondaryButton]}
          onPress={fillDemoValues}
          disabled={loading}
        >
          <Text style={styles.buttonTextSecondary}>Try Demo</Text>
        </TouchableOpacity>
      </View>

      {result && (
        <View style={styles.resultCard}>
          <Text style={styles.resultTitle}>Campsite Score</Text>
          <Text
            style={[
              styles.resultScore,
              { color: getScoreColor(result.score) },
            ]}
          >
            {result.score}/100
          </Text>

          <Text style={styles.breakdownTitle}>Factor Breakdown</Text>
          {Object.entries(result.breakdown).map(([factor, value]) => (
            <View key={factor} style={styles.breakdownRow}>
              <Text style={styles.breakdownLabel}>{factor.charAt(0).toUpperCase() + factor.slice(1)}</Text>
              <Text style={styles.breakdownValue}>{Math.round(value)}</Text>
            </View>
          ))}

          {result.explanations && result.explanations.length > 0 && (
            <>
              <Text style={styles.explanationsTitle}>Insights</Text>
              {result.explanations.map((explanation, idx) => (
                <View key={idx} style={styles.explanationItem}>
                  <Text style={styles.explanationBullet}>•</Text>
                  <Text style={styles.explanationText}>{explanation}</Text>
                </View>
              ))}
            </>
          )}
        </View>
      )}

      <PaywallModal
        visible={showPaywall}
        message={premiumMessage}
        onClose={() => setShowPaywall(false)}
      />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F5F5F5',
  },
  header: {
    backgroundColor: '#1E88E5',
    paddingTop: 16,
    paddingHorizontal: 16,
    paddingBottom: 20,
    marginBottom: 16,
  },
  backButton: {
    marginBottom: 8,
  },
  backText: {
    color: '#FFF',
    fontSize: 14,
    fontWeight: '500',
  },
  title: {
    fontSize: 28,
    fontWeight: 'bold',
    color: '#FFF',
    marginBottom: 4,
  },
  subtitle: {
    fontSize: 14,
    color: 'rgba(255,255,255,0.9)',
  },
  card: {
    backgroundColor: '#FFF',
    marginHorizontal: 12,
    marginBottom: 16,
    borderRadius: 8,
    padding: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 2,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#333',
    marginBottom: 16,
  },
  inputGroup: {
    marginBottom: 16,
  },
  label: {
    fontSize: 14,
    fontWeight: '600',
    color: '#333',
    marginBottom: 6,
  },
  input: {
    borderWidth: 1,
    borderColor: '#DDD',
    borderRadius: 6,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 14,
    color: '#333',
    marginBottom: 4,
  },
  hint: {
    fontSize: 12,
    color: '#888',
    fontStyle: 'italic',
  },
  buttonGroup: {
    flexDirection: 'row',
    marginHorizontal: 12,
    marginBottom: 16,
    gap: 8,
  },
  button: {
    flex: 1,
    paddingVertical: 12,
    borderRadius: 8,
    alignItems: 'center',
  },
  primaryButton: {
    backgroundColor: '#1E88E5',
  },
  secondaryButton: {
    backgroundColor: '#F5F5F5',
    borderWidth: 1,
    borderColor: '#1E88E5',
  },
  buttonText: {
    color: '#FFF',
    fontSize: 14,
    fontWeight: '600',
  },
  buttonTextSecondary: {
    color: '#1E88E5',
    fontSize: 14,
    fontWeight: '600',
  },
  resultCard: {
    backgroundColor: '#FFF',
    marginHorizontal: 12,
    marginBottom: 24,
    borderRadius: 8,
    padding: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 2,
  },
  resultTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#333',
    marginBottom: 12,
  },
  resultScore: {
    fontSize: 48,
    fontWeight: 'bold',
    textAlign: 'center',
    marginBottom: 20,
  },
  breakdownTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: '#333',
    marginTop: 16,
    marginBottom: 8,
  },
  breakdownRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: '#EEE',
  },
  breakdownLabel: {
    fontSize: 13,
    color: '#555',
  },
  breakdownValue: {
    fontSize: 13,
    fontWeight: '600',
    color: '#333',
  },
  explanationsTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: '#333',
    marginTop: 16,
    marginBottom: 8,
  },
  explanationItem: {
    flexDirection: 'row',
    marginBottom: 8,
  },
  explanationBullet: {
    color: '#1E88E5',
    fontSize: 14,
    marginRight: 8,
    fontWeight: 'bold',
  },
  explanationText: {
    flex: 1,
    fontSize: 13,
    color: '#555',
    lineHeight: 18,
  },
});
