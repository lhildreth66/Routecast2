import React, { useState, useEffect, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ActivityIndicator,
  Linking,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { router, useLocalSearchParams, useRootNavigationState } from 'expo-router';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';

const API_BASE = process.env.EXPO_PUBLIC_BACKEND_URL || '';

export default function VerifyEmailScreen() {
  const { user, accessToken, refreshUser } = useAuth();
  const { token } = useLocalSearchParams<{ token?: string }>();
  const rootNavState = useRootNavigationState();

  // Token-based verification states
  const [verifying, setVerifying] = useState(!!token);
  const [verifyDone, setVerifyDone] = useState(false);

  const [resending, setResending] = useState(false);
  const [resendSuccess, setResendSuccess] = useState(false);
  const [error, setError] = useState('');
  const [countdown, setCountdown] = useState(0);

  // ── AUTO-VERIFY from URL token ────────────────────────────────────────────
  // The verification email sends users to /verify-email?token=<token>.
  // On mount, if a token is present, call POST /api/auth/verify-email to
  // consume the token and mark the account as verified, then route to
  // /subscription. This is the primary verification path.
  useEffect(() => {
    if (!token) return;

    let cancelled = false;
    (async () => {
      setVerifying(true);
      setError('');
      try {
        await axios.post(`${API_BASE}/api/auth/verify-email`, { token });
        if (cancelled) return;
        // Refresh user so AuthContext gets email_verified=true
        if (accessToken) {
          await refreshUser();
        }
        if (!cancelled) setVerifyDone(true);
      } catch (err: any) {
        if (cancelled) return;
        const detail = err?.response?.data?.detail || 'Verification failed. The link may have expired.';
        setError(detail);
        setVerifying(false);
      }
    })();

    return () => { cancelled = true; };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]); // run once on mount – token is static

  // ── LAUNCH STRIPE (same-device) or route to login (cross-device) ────────
  // Called once verification has been confirmed (verifyDone=true or user
  // already has email_verified=true from a prior session).
  //
  // Same-device (has session): call POST /api/subscription/checkout and
  //   window.location.href the user directly into Stripe — no app access.
  // Cross-device (no session): go to /login?verified=1 so user signs in;
  //   after login the global PaywallGuard intercepts and forces /subscription
  //   which auto-launches checkout.
  const launchCheckoutRef = useRef(false);
  const launchCheckout = async (token: string) => {
    if (launchCheckoutRef.current) return; // prevent double-fire
    launchCheckoutRef.current = true;
    setVerifying(true);
    setError('');
    try {
      const origin = typeof window !== 'undefined'
        ? window.location.origin
        : 'https://routecastweather.com';
      const { data } = await axios.post(
        `${API_BASE}/api/subscription/checkout`,
        { plan: 'yearly', origin_url: origin },
        { headers: { Authorization: `Bearer ${token}` } },
      );
      if (typeof window !== 'undefined') {
        window.location.href = data.checkout_url;
      }
      // Native: fall through to the PaywallGuard → /subscription which handles it
    } catch (err: any) {
      const detail = err?.response?.data?.detail || 'Failed to start checkout. Please try again.';
      setError(detail);
      setVerifying(false);
      launchCheckoutRef.current = false;
    }
  };

  useEffect(() => {
    if (!rootNavState?.key) return;
    if (!(verifyDone || user?.email_verified)) return;
    if (!accessToken) {
      router.replace('/login?verified=1');
      return;
    }
    launchCheckout(accessToken);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rootNavState?.key, verifyDone, user?.email_verified, accessToken]);

  // ── POLLING fallback (same-session tab without the token URL) ────────────
  // Stop as soon as email_verified becomes true or verifyDone fires so we
  // don't keep hitting /auth/me while redirecting to Stripe.
  useEffect(() => {
    if (verifyDone || user?.email_verified) return; // already done — no interval needed
    const interval = setInterval(() => {
      if (accessToken && !user?.email_verified) {
        refreshUser();
      }
    }, 5000);
    return () => clearInterval(interval);
  }, [accessToken, user?.email_verified, verifyDone]);

  useEffect(() => {
    // Countdown timer for resend button
    if (countdown > 0) {
      const timer = setTimeout(() => setCountdown(countdown - 1), 1000);
      return () => clearTimeout(timer);
    }
  }, [countdown]);

  const handleResendEmail = async () => {
    if (countdown > 0) return;

    setResending(true);
    setError('');
    setResendSuccess(false);

    try {
      await axios.post(
        `${API_BASE}/api/auth/resend-verification`,
        {},
        { headers: { Authorization: `Bearer ${accessToken}` } }
      );
      setResendSuccess(true);
      setCountdown(60); // 60 second cooldown
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to resend email');
    } finally {
      setResending(false);
    }
  };

  const handleSkip = () => {
    router.replace('/subscription');
  };

  // Full-screen state while consuming the token from the URL.
  if (verifying) {
    // Error state: token invalid/expired/already-used.
    if (error) {
      return (
        <View style={[styles.container, { justifyContent: 'center', alignItems: 'center', padding: 32 }]}>
          <Ionicons name="alert-circle" size={52} color="#ef4444" />
          <Text style={{ color: '#ffffff', fontSize: 20, fontWeight: '700', marginTop: 16, textAlign: 'center' }}>
            Verification Failed
          </Text>
          <Text style={{ color: '#a1a1aa', fontSize: 14, marginTop: 8, textAlign: 'center', lineHeight: 20 }}>
            {error}
          </Text>
          <TouchableOpacity
            style={{ marginTop: 28, backgroundColor: '#22c55e', paddingVertical: 13, paddingHorizontal: 32, borderRadius: 10 }}
            onPress={() => router.replace('/login')}
          >
            <Text style={{ color: '#0a0a0a', fontWeight: '700', fontSize: 15 }}>Sign In</Text>
          </TouchableOpacity>
          {accessToken ? (
            <TouchableOpacity
              style={{ marginTop: 12, paddingVertical: 10 }}
              onPress={handleResendEmail}
              disabled={resending || countdown > 0}
            >
              <Text style={{ color: '#eab308', fontSize: 14 }}>
                {countdown > 0 ? `Resend in ${countdown}s` : 'Request a new verification link'}
              </Text>
            </TouchableOpacity>
          ) : null}
        </View>
      );
    }
    // Loading state: request in flight.
    return (
      <View style={[styles.container, { justifyContent: 'center', alignItems: 'center' }]}>
        <ActivityIndicator size="large" color="#22c55e" />
        <Text style={{ color: '#a1a1aa', marginTop: 16, fontSize: 15 }}>Verifying your email…</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <SafeAreaView style={styles.safeArea}>
        <View style={styles.content}>
          {/* Icon */}
          <View style={styles.iconContainer}>
            <Ionicons name="mail-unread" size={48} color="#eab308" />
          </View>

          {/* Title */}
          <Text style={styles.title}>Verify Your Email</Text>
          <Text style={styles.subtitle}>
            We've sent a verification link to
          </Text>
          <Text style={styles.email}>{user?.email || 'your email'}</Text>

          {/* Instructions */}
          <View style={styles.instructionsBox}>
            <View style={styles.instructionRow}>
              <Ionicons name="checkmark-circle" size={20} color="#22c55e" />
              <Text style={styles.instructionText}>Check your inbox</Text>
            </View>
            <View style={styles.instructionRow}>
              <Ionicons name="checkmark-circle" size={20} color="#22c55e" />
              <Text style={styles.instructionText}>Click the verification link</Text>
            </View>
            <View style={styles.instructionRow}>
              <Ionicons name="checkmark-circle" size={20} color="#22c55e" />
              <Text style={styles.instructionText}>Return here to continue</Text>
            </View>
          </View>

          {/* Status Messages */}
          {resendSuccess && (
            <View style={styles.successContainer}>
              <Ionicons name="checkmark-circle" size={18} color="#22c55e" />
              <Text style={styles.successText}>Verification email sent!</Text>
            </View>
          )}

          {error && (
            <View style={styles.errorContainer}>
              <Ionicons name="alert-circle" size={18} color="#ef4444" />
              <Text style={styles.errorText}>{error}</Text>
            </View>
          )}

          {/* Resend Button */}
          <TouchableOpacity
            style={[styles.resendButton, countdown > 0 && styles.resendButtonDisabled]}
            onPress={handleResendEmail}
            disabled={resending || countdown > 0}
            data-testid="resend-email-btn"
          >
            {resending ? (
              <ActivityIndicator color="#eab308" size="small" />
            ) : (
              <>
                <Ionicons name="refresh" size={18} color="#eab308" />
                <Text style={styles.resendButtonText}>
                  {countdown > 0 ? `Resend in ${countdown}s` : 'Resend Email'}
                </Text>
              </>
            )}
          </TouchableOpacity>

          {/* Skip for now */}
          <TouchableOpacity
            style={styles.skipButton}
            onPress={handleSkip}
            data-testid="skip-verification-btn"
          >
            <Text style={styles.skipButtonText}>Skip for now</Text>
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
  skipButton: {
    paddingVertical: 12,
    marginBottom: 24,
  },
  skipButtonText: {
    color: '#6b7280',
    fontSize: 14,
  },
  helpText: {
    color: '#52525b',
    fontSize: 12,
    textAlign: 'center',
    paddingHorizontal: 20,
  },
});
