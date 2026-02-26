import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ActivityIndicator,
  TextInput,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useLocalSearchParams } from 'expo-router';
import axios from 'axios';

const API_BASE = process.env.EXPO_PUBLIC_BACKEND_URL || '';

/**
 * Verify-email screen.
 *
 * Three modes:
 * 1. **Token present** (`?token=...`): Immediately redirects the browser to
 *    the backend GET `/api/auth/verify-email?token=...` which validates the
 *    token, creates a Stripe Customer + Checkout Session, and 302-redirects
 *    the user to the Stripe-hosted checkout page.
 *
 * 2. **Error present** (`?error=...`): Shows a friendly error message after
 *    the backend redirected back because the token was invalid / expired.
 *
 * 3. **No params** (arrived from signup): Shows "Check your email"
 *    instructions with a resend button.
 */
export default function VerifyEmailScreen() {
  const {
    token: tokenParam,
    t: tParam,
    error: errorParam,
    email: emailParam,
  } = useLocalSearchParams<{
    token?: string;
    t?: string;
    error?: string;
    email?: string;
  }>();

  const token = tokenParam || tParam;

  // Resend state
  const [resending, setResending] = useState(false);
  const [resendSuccess, setResendSuccess] = useState(false);
  const [resendError, setResendError] = useState('');
  const [countdown, setCountdown] = useState(0);
  const [resendEmail, setResendEmail] = useState(emailParam || '');

  // ── MODE 1: Token present → redirect to backend for Stripe checkout ────
  useEffect(() => {
    if (!token) return;
    // Redirect the browser directly to the backend GET endpoint which will
    // validate the token, create the Stripe Checkout Session, and 302 to
    // Stripe.  This keeps the flow in a single page-navigation chain.
    if (typeof window !== 'undefined') {
      window.location.href = `${API_BASE}/api/auth/verify-email?token=${encodeURIComponent(token)}`;
    }
  }, [token]);

  // Countdown timer for resend cooldown
  useEffect(() => {
    if (countdown > 0) {
      const timer = setTimeout(() => setCountdown(countdown - 1), 1000);
      return () => clearTimeout(timer);
    }
  }, [countdown]);

  const handleResendEmail = async () => {
    if (countdown > 0 || !resendEmail.trim()) return;

    setResending(true);
    setResendError('');
    setResendSuccess(false);

    try {
      await axios.post(`${API_BASE}/api/auth/resend-verification`, {
        email: resendEmail.trim(),
      });
      setResendSuccess(true);
      setCountdown(60);
    } catch (err: any) {
      setResendError(err.response?.data?.detail || 'Failed to resend email');
    } finally {
      setResending(false);
    }
  };

  // ── MODE 1 loading state: redirecting to backend ───────────────────────
  if (token) {
    return (
      <View style={[styles.container, { justifyContent: 'center', alignItems: 'center' }]}>
        <ActivityIndicator size="large" color="#22c55e" />
        <Text style={{ color: '#a1a1aa', marginTop: 16, fontSize: 15 }}>
          Verifying your email…
        </Text>
      </View>
    );
  }

  // ── MODE 2: Error from backend redirect ────────────────────────────────
  if (errorParam) {
    return (
      <View style={styles.container}>
        <SafeAreaView style={styles.safeArea}>
          <View style={styles.content}>
            <View style={styles.iconContainer}>
              <Ionicons name="alert-circle" size={48} color="#ef4444" />
            </View>
            <Text style={styles.title}>Verification Failed</Text>
            <Text style={styles.subtitle}>{decodeURIComponent(errorParam)}</Text>

            {/* Resend section */}
            <View style={{ width: '100%', marginTop: 24 }}>
              <TextInput
                style={styles.emailInput}
                placeholder="Enter your email to resend"
                placeholderTextColor="#71717a"
                value={resendEmail}
                onChangeText={setResendEmail}
                keyboardType="email-address"
                autoCapitalize="none"
              />
              <TouchableOpacity
                style={[styles.resendButton, countdown > 0 && styles.resendButtonDisabled]}
                onPress={handleResendEmail}
                disabled={resending || countdown > 0 || !resendEmail.trim()}
              >
                {resending ? (
                  <ActivityIndicator color="#eab308" size="small" />
                ) : (
                  <Text style={styles.resendButtonText}>
                    {countdown > 0 ? `Resend in ${countdown}s` : 'Resend Verification Email'}
                  </Text>
                )}
              </TouchableOpacity>
            </View>

            {resendSuccess && (
              <View style={styles.successContainer}>
                <Ionicons name="checkmark-circle" size={18} color="#22c55e" />
                <Text style={styles.successText}>Verification email sent!</Text>
              </View>
            )}
            {!!resendError && (
              <View style={styles.errorContainer}>
                <Ionicons name="alert-circle" size={18} color="#ef4444" />
                <Text style={styles.errorText}>{resendError}</Text>
              </View>
            )}
          </View>
        </SafeAreaView>
      </View>
    );
  }

  // ── MODE 3: No token, no error — "check your email" instructions ───────
  return (
    <View style={styles.container}>
      <SafeAreaView style={styles.safeArea}>
        <View style={styles.content}>
          {/* Icon */}
          <View style={styles.iconContainer}>
            <Ionicons name="mail-unread" size={48} color="#eab308" />
          </View>

          {/* Title */}
          <Text style={styles.title}>Check Your Email</Text>
          <Text style={styles.subtitle}>
            We've sent a verification link to
          </Text>
          {emailParam ? (
            <Text style={styles.email}>{emailParam}</Text>
          ) : (
            <Text style={styles.email}>your email address</Text>
          )}

          {/* Instructions */}
          <View style={styles.instructionsBox}>
            <View style={styles.instructionRow}>
              <Ionicons name="checkmark-circle" size={20} color="#22c55e" />
              <Text style={styles.instructionText}>Check your inbox (and spam folder)</Text>
            </View>
            <View style={styles.instructionRow}>
              <Ionicons name="checkmark-circle" size={20} color="#22c55e" />
              <Text style={styles.instructionText}>Click the verification link</Text>
            </View>
            <View style={styles.instructionRow}>
              <Ionicons name="checkmark-circle" size={20} color="#22c55e" />
              <Text style={styles.instructionText}>You'll be redirected to set up your free trial</Text>
            </View>
          </View>

          {/* Status Messages */}
          {resendSuccess && (
            <View style={styles.successContainer}>
              <Ionicons name="checkmark-circle" size={18} color="#22c55e" />
              <Text style={styles.successText}>Verification email sent!</Text>
            </View>
          )}
          {!!resendError && (
            <View style={styles.errorContainer}>
              <Ionicons name="alert-circle" size={18} color="#ef4444" />
              <Text style={styles.errorText}>{resendError}</Text>
            </View>
          )}

          {/* Resend section */}
          {!emailParam && (
            <TextInput
              style={styles.emailInput}
              placeholder="Enter your email to resend"
              placeholderTextColor="#71717a"
              value={resendEmail}
              onChangeText={setResendEmail}
              keyboardType="email-address"
              autoCapitalize="none"
            />
          )}

          <TouchableOpacity
            style={[styles.resendButton, countdown > 0 && styles.resendButtonDisabled]}
            onPress={handleResendEmail}
            disabled={resending || countdown > 0 || !resendEmail.trim()}
          >
            {resending ? (
              <ActivityIndicator color="#eab308" size="small" />
            ) : (
              <>
                <Ionicons name="refresh" size={18} color="#eab308" />
                <Text style={styles.resendButtonText}>
                  {countdown > 0 ? `Resend in ${countdown}s` : 'Resend Verification Email'}
                </Text>
              </>
            )}
          </TouchableOpacity>

          {/* Help Text */}
          <Text style={styles.helpText}>
            Didn't receive the email? Check your spam folder or try resending.
          </Text>
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
  },
  email: {
    fontSize: 16,
    color: '#eab308',
    fontWeight: '600',
    marginBottom: 32,
  },
  instructionsBox: {
    backgroundColor: '#27272a',
    borderRadius: 12,
    padding: 20,
    width: '100%',
    marginBottom: 24,
    gap: 16,
  },
  instructionRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  instructionText: {
    color: '#e4e4e7',
    fontSize: 14,
  },
  successContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(34, 197, 94, 0.15)',
    padding: 12,
    borderRadius: 8,
    marginBottom: 16,
    gap: 8,
    width: '100%',
  },
  successText: {
    color: '#22c55e',
    fontSize: 13,
  },
  errorContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(239, 68, 68, 0.15)',
    padding: 12,
    borderRadius: 8,
    marginBottom: 16,
    gap: 8,
    width: '100%',
  },
  errorText: {
    color: '#ef4444',
    fontSize: 13,
    flex: 1,
  },
  emailInput: {
    backgroundColor: '#27272a',
    borderRadius: 10,
    padding: 14,
    color: '#ffffff',
    fontSize: 15,
    borderWidth: 1,
    borderColor: '#3f3f46',
    width: '100%',
    marginBottom: 12,
  },
  resendButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    backgroundColor: '#27272a',
    borderRadius: 10,
    paddingVertical: 14,
    paddingHorizontal: 24,
    borderWidth: 1,
    borderColor: '#eab308',
    width: '100%',
    marginBottom: 12,
  },
  resendButtonDisabled: {
    borderColor: '#52525b',
    opacity: 0.6,
  },
  resendButtonText: {
    color: '#eab308',
    fontSize: 14,
    fontWeight: '600',
  },
  helpText: {
    color: '#52525b',
    fontSize: 12,
    textAlign: 'center',
    paddingHorizontal: 20,
    marginTop: 12,
  },
});
