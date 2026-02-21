import React, { useMemo, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  Platform,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
  Linking,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { buildUrl } from './apiConfig';

type PlanId = 'monthly' | 'yearly';

const PLANS: Record<PlanId, { title: string; price: string; note: string; badge?: string }> = {
  monthly: {
    title: 'Monthly',
    price: '$9.99/month',
    note: 'Billed monthly',
  },
  yearly: {
    title: 'Yearly',
    price: '$59.99/year',
    note: 'Save over 40% vs monthly',
    badge: 'Best value',
  },
};

export default function SubscriptionScreen() {
  const router = useRouter();
  const [selectedPlan, setSelectedPlan] = useState<PlanId>('monthly');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Use the current origin for Stripe redirect URLs; default to production when unavailable (native)
  const originUrl = useMemo(() => {
    if (typeof window !== 'undefined' && window?.location?.origin) {
      return window.location.origin;
    }
    return 'https://routecastweather.com';
  }, []);

  const handleSubscribe = async () => {
    setError('');
    setLoading(true);

    try {
      const response = await fetch(buildUrl('subscription/checkout'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ plan: selectedPlan, origin_url: originUrl }),
      });

      if (!response.ok) {
        const bodyText = await response.text();
        throw new Error(bodyText || 'Unable to start checkout.');
      }

      const data = await response.json();
      const checkoutUrl = data.checkout_url || data.url;

      if (!checkoutUrl) {
        throw new Error('Checkout URL missing from response.');
      }

      if (Platform.OS === 'web') {
        window.location.href = checkoutUrl;
      } else {
        const canOpen = await Linking.canOpenURL(checkoutUrl);
        if (!canOpen) {
          throw new Error('Unable to open checkout.');
        }
        await Linking.openURL(checkoutUrl);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unable to start checkout.';
      setError(message);
      if (Platform.OS !== 'web') {
        Alert.alert('Checkout error', message);
      }
    } finally {
      setLoading(false);
    }
  };

  const renderPlanCard = (planId: PlanId) => {
    const plan = PLANS[planId];
    const isSelected = selectedPlan === planId;

    return (
      <TouchableOpacity
        key={planId}
        activeOpacity={0.8}
        onPress={() => setSelectedPlan(planId)}
        style={[styles.planCard, isSelected && styles.planCardSelected]}
      >
        <View style={styles.planHeaderRow}>
          <View style={styles.planTitleRow}>
            <Ionicons name={planId === 'yearly' ? 'ribbon' : 'calendar'} size={22} color={isSelected ? '#0f172a' : '#eab308'} />
            <Text style={[styles.planTitle, isSelected && styles.planTitleSelected]}>{plan.title}</Text>
          </View>
          {plan.badge && (
            <View style={styles.badge}>
              <Text style={styles.badgeText}>{plan.badge}</Text>
            </View>
          )}
        </View>
        <Text style={[styles.planPrice, isSelected && styles.planPriceSelected]}>{plan.price}</Text>
        <Text style={[styles.planNote, isSelected && styles.planNoteSelected]}>{plan.note}</Text>
      </TouchableOpacity>
    );
  };

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        <View style={styles.header}>
          <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
            <Ionicons name="arrow-back" size={22} color="#60a5fa" />
            <Text style={styles.backText}>Back</Text>
          </TouchableOpacity>
          <Text style={styles.headerTitle}>Upgrade to Premium</Text>
          <View style={styles.placeholder} />
        </View>

        <View style={styles.heroCard}>
          <Text style={styles.heroTitle}>Weather-smart routing without limits</Text>
          <Text style={styles.heroSubtitle}>Start a 7-day free trial. Cancel anytime.</Text>
          <View style={styles.bulletRow}>
            <Ionicons name="cloud" size={18} color="#22d3ee" />
            <Text style={styles.bulletText}>Live radar, alerts, and hazard-aware routing</Text>
          </View>
          <View style={styles.bulletRow}>
            <Ionicons name="shield-checkmark" size={18} color="#22c55e" />
            <Text style={styles.bulletText}>Premium tools for RVers & truckers</Text>
          </View>
          <View style={styles.bulletRow}>
            <Ionicons name="sparkles" size={18} color="#fbbf24" />
            <Text style={styles.bulletText}>All features included with one plan</Text>
          </View>
        </View>

        <View style={styles.planGrid}>
          {renderPlanCard('monthly')}
          {renderPlanCard('yearly')}
        </View>

        {error ? (
          <View style={styles.errorBanner}>
            <Ionicons name="warning" size={18} color="#fcd34d" />
            <Text style={styles.errorText}>{error}</Text>
          </View>
        ) : null}

        <TouchableOpacity
          activeOpacity={0.85}
          onPress={handleSubscribe}
          disabled={loading}
          style={[styles.subscribeButton, loading && styles.subscribeButtonDisabled]}
        >
          {loading ? (
            <ActivityIndicator color="#0f172a" />
          ) : (
            <Text style={styles.subscribeText}>Subscribe & Start Trial</Text>
          )}
        </TouchableOpacity>

        <Text style={styles.legal}>You will not be charged until the 7-day trial ends. Payment method is collected today.</Text>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0a0a0a',
  },
  content: {
    padding: 20,
    gap: 16,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  backButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingVertical: 4,
  },
  backText: {
    color: '#60a5fa',
    fontSize: 15,
    fontWeight: '600',
  },
  headerTitle: {
    color: '#e5e7eb',
    fontSize: 18,
    fontWeight: '700',
  },
  placeholder: {
    width: 60,
  },
  heroCard: {
    backgroundColor: '#111827',
    borderRadius: 14,
    padding: 18,
    borderWidth: 1,
    borderColor: '#1f2937',
    gap: 10,
  },
  heroTitle: {
    color: '#fff',
    fontSize: 20,
    fontWeight: '700',
  },
  heroSubtitle: {
    color: '#9ca3af',
    fontSize: 14,
  },
  bulletRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  bulletText: {
    color: '#cbd5e1',
    fontSize: 14,
    flex: 1,
  },
  planGrid: {
    flexDirection: 'row',
    gap: 12,
    flexWrap: 'wrap',
  },
  planCard: {
    flex: 1,
    backgroundColor: '#18181b',
    borderRadius: 12,
    padding: 14,
    borderWidth: 1,
    borderColor: '#27272a',
    gap: 8,
  },
  planCardSelected: {
    backgroundColor: '#fbbf24',
    borderColor: '#f59e0b',
  },
  planHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  planTitleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  planTitle: {
    color: '#fbbf24',
    fontSize: 16,
    fontWeight: '700',
  },
  planTitleSelected: {
    color: '#0f172a',
  },
  planPrice: {
    color: '#fff',
    fontSize: 22,
    fontWeight: '800',
  },
  planPriceSelected: {
    color: '#0f172a',
  },
  planNote: {
    color: '#9ca3af',
    fontSize: 12,
  },
  planNoteSelected: {
    color: '#0f172a',
  },
  badge: {
    backgroundColor: '#0f172a',
    borderRadius: 8,
    paddingHorizontal: 8,
    paddingVertical: 4,
  },
  badgeText: {
    color: '#fbbf24',
    fontSize: 12,
    fontWeight: '700',
  },
  errorBanner: {
    backgroundColor: '#7f1d1d',
    borderRadius: 10,
    padding: 12,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    borderWidth: 1,
    borderColor: '#b91c1c',
  },
  errorText: {
    color: '#fecdd3',
    fontSize: 13,
    flex: 1,
  },
  subscribeButton: {
    backgroundColor: '#22c55e',
    paddingVertical: 16,
    borderRadius: 12,
    alignItems: 'center',
  },
  subscribeButtonDisabled: {
    opacity: 0.7,
  },
  subscribeText: {
    color: '#0f172a',
    fontSize: 16,
    fontWeight: '800',
  },
  legal: {
    color: '#9ca3af',
    fontSize: 12,
    textAlign: 'center',
    lineHeight: 18,
    paddingHorizontal: 12,
  },
});
