import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ActivityIndicator,
  ScrollView,
  Linking,
  Platform,
  Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { router } from 'expo-router';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';

const API_BASE = process.env.EXPO_PUBLIC_BACKEND_URL || '';

interface Plan {
  id: string;
  name: string;
  price: number;
  currency: string;
  interval: string;
  trial_days: number;
  features: string[];
  savings?: string;
}

const PLAN_FEATURES = [
  'Premium weather along your route',
  'Severe weather alerts',
  'Radar + forecast tools',
  'Advanced trucking restrictions',
];

const FALLBACK_PLANS: Plan[] = [
  {
    id: 'monthly',
    name: 'Monthly',
    price: 9.99,
    currency: 'USD',
    interval: 'month',
    trial_days: 7,
    features: PLAN_FEATURES,
  },
  {
    id: 'yearly',
    name: 'Yearly',
    price: 59.99,
    currency: 'USD',
    interval: 'year',
    trial_days: 7,
    savings: 'Save 50%',
    features: PLAN_FEATURES,
  },
];

function normalizePlans(data: any): Plan[] | null {
  if (Array.isArray(data)) return data as Plan[];
  if (data && Array.isArray(data.plans)) return data.plans as Plan[];
  return null;
}

export default function SubscriptionScreen() {
  const { user, accessToken, refreshUser, isAuthenticated } = useAuth();
  const [plans, setPlans] = useState<Plan[]>([]);
  const [selectedPlan, setSelectedPlan] = useState<string>('yearly');
  const [loading, setLoading] = useState(true);
  const [checkoutLoading, setCheckoutLoading] = useState(false);
  const [trialLoading, setTrialLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    fetchPlans();
  }, []);

  const fetchPlans = async () => {
    setLoading(true);
    setError('');

    const candidates = [
      `${API_BASE}/api/subscriptions/plans`,
      `${API_BASE}/api/subscription/plans`,
    ];

    try {
      for (const url of candidates) {
        try {
          const resp = await axios.get(url);
          const parsed = normalizePlans(resp.data);
          if (parsed && parsed.length) {
            setPlans(parsed);
            setSelectedPlan(parsed.some(p => p.id === 'yearly') ? 'yearly' : parsed[0].id);
            return;
          }
        } catch {}
      }

      setPlans(FALLBACK_PLANS);
      setSelectedPlan('yearly');
    } finally {
      setLoading(false);
    }
  };

  const handleStartTrial = async () => {
    if (!isAuthenticated) {
      router.push('/signup');
      return;
    }

    setTrialLoading(true);
    setError('');

    try {
      const urls = [
        `${API_BASE}/api/subscriptions/start-trial`,
        `${API_BASE}/api/subscription/start-trial`,
      ];

      let ok = false;
      for (const url of urls) {
        try {
          await axios.post(url, {}, { headers: { Authorization: `Bearer ${accessToken}` } });
          ok = true;
          break;
        } catch {}
      }

      if (!ok) {
        const msg = 'Trial is not available yet. You can still use the free version.';
        setError(msg);
        if (Platform.OS !== 'web') Alert.alert('Trial coming soon', msg);
        return;
      }

      await refreshUser();
      router.replace('/');
    } finally {
      setTrialLoading(false);
    }
  };

  const handleCheckout = async (planId: string) => {
    if (!isAuthenticated) {
      router.push('/signup');
      return;
    }

    setCheckoutLoading(true);
    setError('');

    try {
      const origin =
        Platform.OS === 'web'
          ? window.location.origin
          : 'https://app.routecastweather.com';

      const urls = [
        `${API_BASE}/api/subscriptions/checkout`,
        `${API_BASE}/api/subscription/checkout`,
      ];

      let response: any = null;
      for (const url of urls) {
        try {
          response = await axios.post(
            url,
            { plan: planId, origin_url: origin },
            { headers: { Authorization: `Bearer ${accessToken}` } }
          );
          break;
        } catch {}
      }

      if (!response?.data?.checkout_url) {
        const msg = 'Billing is not configured yet. You can still use the free version.';
        setError(msg);
        if (Platform.OS !== 'web') Alert.alert('Not ready yet', msg);
        return;
      }

      Platform.OS === 'web'
        ? (window.location.href = response.data.checkout_url)
        : await Linking.openURL(response.data.checkout_url);
    } finally {
      setCheckoutLoading(false);
    }
  };

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#eab308" />
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <SafeAreaView style={styles.safeArea}>
        <ScrollView contentContainerStyle={styles.scrollContent}>
          <TouchableOpacity style={styles.backButton} onPress={() => router.back()}>
            <Ionicons name="arrow-back" size={24} color="#fff" />
          </TouchableOpacity>

          <View style={styles.header}>
            <View style={styles.iconContainer}>
              <Ionicons name="rocket" size={32} color="#1a1a1a" />
            </View>
            <Text style={styles.title}>Upgrade to Premium</Text>
            <Text style={styles.subtitle}>Unlock all features and drive with confidence</Text>
          </View>

          <View style={styles.trialInfoAlways}>
            <Text style={styles.trialInfoTitle}>Free for 7 days</Text>
            <Text style={styles.trialInfoSub}>No credit card required (for now)</Text>
          </View>

          <Text style={styles.sectionTitle}>Choose Your Plan</Text>

          <View style={styles.plansContainer}>
            {plans.map(plan => (
              <TouchableOpacity
                key={plan.id}
                style={[styles.planCard, selectedPlan === plan.id && styles.planCardSelected]}
                onPress={() => setSelectedPlan(plan.id)}
              >
                {plan.savings && (
                  <View style={styles.savingsBadge}>
                    <Text style={styles.savingsText}>{plan.savings}</Text>
                  </View>
                )}

                <View style={styles.planHeader}>
                  <Text style={styles.planName}>{plan.name}</Text>
                  <Text style={styles.planPrice}>${plan.price}/{plan.interval}</Text>
                </View>

                <Text style={styles.planTrialText}>7-day free trial • No card required</Text>
                <Text style={styles.planBillingText}>
                  {plan.id === 'yearly' ? 'Billed annually • Save 50%' : 'Billed monthly'}
                </Text>

                {PLAN_FEATURES.map((f, i) => (
                  <View key={i} style={styles.featureRow}>
                    <Ionicons name="checkmark-circle" size={18} color="#22c55e" />
                    <Text style={styles.featureText}>{f}</Text>
                  </View>
                ))}
              </TouchableOpacity>
            ))}
          </View>

          <TouchableOpacity
            style={styles.checkoutButton}
            onPress={() => handleCheckout(selectedPlan)}
          >
            <Text style={styles.checkoutButtonText}>Subscribe</Text>
          </TouchableOpacity>

          <TouchableOpacity style={styles.skipButton} onPress={() => router.replace('/')}>
            <Text style={styles.skipButtonText}>Continue with free version</Text>
          </TouchableOpacity>
        </ScrollView>
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0f0f0f' },
  loadingContainer: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  safeArea: { flex: 1 },
  scrollContent: { padding: 20 },
  backButton: { marginBottom: 20 },
  header: { alignItems: 'center', marginBottom: 20 },
  iconContainer: { backgroundColor: '#eab308', borderRadius: 20, padding: 16, marginBottom: 10 },
  title: { color: '#fff', fontSize: 28, fontWeight: '700' },
  subtitle: { color: '#a1a1aa' },
  trialInfoAlways: { backgroundColor: '#14532d', padding: 14, borderRadius: 12, marginBottom: 20 },
  trialInfoTitle: { color: '#22c55e', fontSize: 16, fontWeight: '800' },
  trialInfoSub: { color: '#86efac', fontSize: 13 },
  sectionTitle: { color: '#a1a1aa', marginBottom: 12 },
  plansContainer: { gap: 12 },
  planCard: { backgroundColor: '#27272a', padding: 16, borderRadius: 12 },
  planCardSelected: { borderColor: '#eab308', borderWidth: 2 },
  savingsBadge: { position: 'absolute', top: -8, right: 10, backgroundColor: '#22c55e', padding: 6, borderRadius: 10 },
  savingsText: { color: '#fff', fontSize: 11 },
  planHeader: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 6 },
  planName: { color: '#fff', fontSize: 18, fontWeight: '700' },
  planPrice: { color: '#eab308', fontSize: 18, fontWeight: '700' },
  planTrialText: { color: '#86efac', fontSize: 12 },
  planBillingText: { color: '#a1a1aa', fontSize: 12, marginBottom: 10 },
  featureRow: { flexDirection: 'row', gap: 8, marginBottom: 6 },
  featureText: { color: '#d4d4d8', fontSize: 13 },
  checkoutButton: { backgroundColor: '#eab308', padding: 16, borderRadius: 10, marginTop: 20 },
  checkoutButtonText: { color: '#1a1a1a', textAlign: 'center', fontWeight: '700' },
  skipButton: { marginTop: 14 },
  skipButtonText: { color: '#6b7280', textAlign: 'center' },
});