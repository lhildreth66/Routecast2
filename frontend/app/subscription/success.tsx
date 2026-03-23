import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, ActivityIndicator } from 'react-native';
import { router, useLocalSearchParams } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useAuth } from '../../contexts/AuthContext';

export default function SubscriptionSuccessScreen() {
  const { session_id } = useLocalSearchParams<{ session_id?: string }>();
  const { refreshUser } = useAuth();
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');

  // STRIPE DISABLED - Google Play submission - do not delete
  /*
  useEffect(() => {
    let cancelled = false;

    const confirm = async () => {
      try {
        // Refresh user profile so is_premium / subscription_status reflect the new trial
        await refreshUser();
        if (!cancelled) setStatus('success');
      } catch (e) {
        console.warn('[success] refreshUser failed', e);
        if (!cancelled) setStatus('success'); // still redirect — Stripe already processed
      } finally {
        if (!cancelled) {
          // Give user 1.5 s to see the success screen, then go to account
          setTimeout(() => {
            if (!cancelled) router.replace('/account');
          }, 1500);
        }
      }
    };

    confirm();
    return () => { cancelled = true; };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session_id]);
  */

  return (
    <View style={styles.container}>
      {status === 'loading' ? (
        <>
          <ActivityIndicator size="large" color="#22c55e" />
          <Text style={styles.message}>Activating your trial…</Text>
        </>
      ) : (
        <>
          <View style={styles.iconCircle}>
            <Ionicons name="checkmark" size={48} color="#fff" />
          </View>
          <Text style={styles.title}>Trial Activated! 🎉</Text>
          <Text style={styles.message}>
            Your 7-day free trial has started.{'\n'}Redirecting to your account…
          </Text>
        </>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0a0a0a',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
    gap: 16,
  },
  iconCircle: {
    width: 88,
    height: 88,
    borderRadius: 44,
    backgroundColor: '#16a34a',
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 8,
  },
  title: {
    color: '#f0fdf4',
    fontSize: 24,
    fontWeight: '800',
    textAlign: 'center',
  },
  message: {
    color: '#d1d5db',
    fontSize: 15,
    textAlign: 'center',
    lineHeight: 22,
  },
});
