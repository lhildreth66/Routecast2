import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { router } from 'expo-router';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';

const API_BASE = process.env.EXPO_PUBLIC_BACKEND_URL || '';

export default function VerifyEmailScreen() {
  const { user, accessToken, refreshUser } = useAuth();
  const [resending, setResending] = useState(false);
  const [resendSuccess, setResendSuccess] = useState(false);
  const [error, setError] = useState('');
  const [countdown, setCountdown] = useState(0);

  useEffect(() => {
    // Poll for email verification status
    const interval = setInterval(() => {
      if (accessToken) {
        refreshUser();
      }
    }, 5000); // Check every 5 seconds

    return () => clearInterval(interval);
  }, [accessToken]);

  useEffect(() => {
    // Redirect when email is verified
    if (user?.email_verified) {
      router.replace('/subscription');
    }
  }, [user?.email_verified]);

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
