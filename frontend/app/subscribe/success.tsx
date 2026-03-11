import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, ActivityIndicator, TouchableOpacity } from 'react-native';
import { useLocalSearchParams, router } from 'expo-router';
import axios from 'axios';

const API_BASE = process.env.EXPO_PUBLIC_BACKEND_URL || '';

interface SessionResult {
  plan: string | null;
  status: string | null;
  amount: number | null;
  currency: string | null;
}

export default function SubscribeSuccess() {
  const { session_id } = useLocalSearchParams<{ session_id?: string }>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<SessionResult | null>(null);

  useEffect(() => {
    async function verify() {
      if (!session_id) {
        setError('Missing checkout session.');
        setLoading(false);
        return;
      }

      try {
        const resp = await axios.get(`${API_BASE}/api/subscription/checkout-session`, {
          params: { session_id },
        });
        const data: SessionResult = resp.data;
        setResult(data);
      } catch (err: any) {
        setError(err?.response?.data?.detail || 'Could not verify checkout.');
      } finally {
        setLoading(false);
      }
    }

    verify();
  }, [session_id]);

  const planLabel = result?.plan ? result.plan.charAt(0).toUpperCase() + result.plan.slice(1) : 'Subscription';

  return (
    <View style={styles.container}>
      {loading ? (
        <View style={styles.card}>
          <ActivityIndicator size="large" color="#eab308" />
          <Text style={styles.text}>Finalizing your subscription…</Text>
        </View>
      ) : error ? (
        <View style={styles.card}>
          <Text style={styles.title}>Checkout Not Verified</Text>
          <Text style={styles.text}>{error}</Text>
          <TouchableOpacity style={styles.button} onPress={() => router.replace('/subscription')}>
            <Text style={styles.buttonText}>Back to Subscription</Text>
          </TouchableOpacity>
        </View>
      ) : (
        <View style={styles.card}>
          <Text style={styles.title}>Welcome to RouteCast!</Text>
          <Text style={styles.text}>{planLabel} activated. You’re all set.</Text>
          <TouchableOpacity style={styles.button} onPress={() => router.replace('/')}
            data-testid="subscription-success-continue">
            <Text style={styles.buttonText}>Continue</Text>
          </TouchableOpacity>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0a0a0a',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 20,
  },
  card: {
    backgroundColor: '#111827',
    borderRadius: 12,
    padding: 20,
    width: '100%',
    maxWidth: 480,
    borderWidth: 1,
    borderColor: '#1f2937',
    alignItems: 'center',
    gap: 12,
  },
  title: {
    color: '#fff',
    fontSize: 20,
    fontWeight: '700',
    textAlign: 'center',
  },
  text: {
    color: '#9ca3af',
    fontSize: 14,
    textAlign: 'center',
  },
  button: {
    marginTop: 8,
    backgroundColor: '#eab308',
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: 8,
  },
  buttonText: {
    color: '#0a0a0a',
    fontWeight: '700',
    fontSize: 14,
  },
});
