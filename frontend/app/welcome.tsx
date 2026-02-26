import React, { useEffect, useState, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ActivityIndicator,
  TouchableOpacity,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { router, useLocalSearchParams } from 'expo-router';
import { useAuth } from '../contexts/AuthContext';

const API_BASE = process.env.EXPO_PUBLIC_BACKEND_URL || '';

/**
 * Welcome page — the Stripe Checkout success_url lands here.
 *
 * Flow:
 * 1. Reads `session_id` from URL query params (injected by Stripe).
 * 2. POSTs `session_id` to `/api/auth/welcome` which validates the checkout
 *    session, activates the user's trial subscription, and returns JWT tokens.
 * 3. Stores the tokens via `loginWithTokens()` (first login).
 * 4. Redirects to the dashboard.
 */
export default function WelcomeScreen() {
  const { session_id } = useLocalSearchParams<{ session_id: string }>();
  const { loginWithTokens } = useAuth();

  const [error, setError] = useState('');
  const [activating, setActivating] = useState(true);
  const activatedRef = useRef(false);

  useEffect(() => {
    if (!session_id || activatedRef.current) return;
    activatedRef.current = true;

    (async () => {
      try {
        const res = await fetch(`${API_BASE}/api/auth/welcome`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ session_id }),
        });

        const data = await res.json().catch(() => ({}));

        if (!res.ok) {
          throw new Error(data?.detail || 'Activation failed. Please try again.');
        }

        const { access_token, refresh_token } = data;
        if (!access_token || !refresh_token) {
          throw new Error('Activation failed — no credentials received.');
        }

        // Store tokens and fetch user profile (first login)
        await loginWithTokens(access_token, refresh_token);

        // Navigate to the main app
        router.replace('/' as any);
      } catch (err: any) {
        console.error('[welcome] activation error:', err);
        setError(err.message || 'Something went wrong. Please try again.');
        setActivating(false);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session_id]);

  // ── Error state ────────────────────────────────────────────────────────────
  if (error) {
    return (
      <View style={styles.container}>
        <SafeAreaView style={styles.safeArea}>
          <View style={styles.content}>
            <View style={styles.iconContainer}>
              <Ionicons name="alert-circle" size={48} color="#ef4444" />
            </View>
            <Text style={styles.title}>Activation Failed</Text>
            <Text style={styles.subtitle}>{error}</Text>

            <TouchableOpacity
              style={styles.primaryButton}
              onPress={() => router.replace('/login' as any)}
            >
              <Text style={styles.primaryButtonText}>Go to Sign In</Text>
            </TouchableOpacity>
          </View>
        </SafeAreaView>
      </View>
    );
  }

  // ── Loading state ──────────────────────────────────────────────────────────
  return (
    <View style={styles.container}>
      <SafeAreaView style={styles.safeArea}>
        <View style={styles.content}>
          <View style={styles.iconContainer}>
            <Ionicons name="checkmark-circle" size={48} color="#22c55e" />
          </View>
          <Text style={styles.title}>Welcome to RouteCast!</Text>
          <Text style={styles.subtitle}>Setting up your account…</Text>
          <ActivityIndicator
            size="large"
            color="#22c55e"
            style={{ marginTop: 24 }}
          />
        </View>
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0f0f0f',
  },
  safeArea: {
    flex: 1,
  },
  content: {
    flex: 1,
    padding: 24,
    alignItems: 'center',
    justifyContent: 'center',
  },
  iconContainer: {
    width: 96,
    height: 96,
    borderRadius: 24,
    backgroundColor: '#27272a',
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 24,
  },
  title: {
    fontSize: 28,
    fontWeight: '700',
    color: '#ffffff',
    marginBottom: 12,
    textAlign: 'center',
  },
  subtitle: {
    fontSize: 15,
    color: '#a1a1aa',
    textAlign: 'center',
    lineHeight: 22,
    paddingHorizontal: 20,
  },
  primaryButton: {
    marginTop: 28,
    backgroundColor: '#22c55e',
    paddingVertical: 14,
    paddingHorizontal: 32,
    borderRadius: 10,
  },
  primaryButtonText: {
    color: '#0a0a0a',
    fontWeight: '700',
    fontSize: 15,
  },
});
