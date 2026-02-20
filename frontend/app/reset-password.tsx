import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TextInput,
  TouchableOpacity,
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { router, useLocalSearchParams } from 'expo-router';
import axios from 'axios';

const API_BASE = process.env.EXPO_PUBLIC_BACKEND_URL || '';

export default function ResetPasswordScreen() {
  const { token } = useLocalSearchParams<{ token: string }>();
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);

  const validatePassword = (pass: string): string | null => {
    if (pass.length < 8) return 'Password must be at least 8 characters';
    if (!/[A-Z]/.test(pass)) return 'Password must contain an uppercase letter';
    if (!/[a-z]/.test(pass)) return 'Password must contain a lowercase letter';
    if (!/[0-9]/.test(pass)) return 'Password must contain a number';
    return null;
  };

  const handleSubmit = async () => {
    setError('');

    if (!password.trim()) {
      setError('Please enter a new password');
      return;
    }

    const passwordError = validatePassword(password);
    if (passwordError) {
      setError(passwordError);
      return;
    }

    if (password !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    setLoading(true);

    try {
      await axios.post(`${API_BASE}/api/auth/reset-password`, {
        token,
        new_password: password
      });
      setSuccess(true);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to reset password. Link may be expired.');
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    return (
      <View style={styles.container}>
        <SafeAreaView style={styles.safeArea}>
          <View style={styles.successContent}>
            <View style={styles.successIconContainer}>
              <Ionicons name="checkmark-circle" size={64} color="#22c55e" />
            </View>

            <Text style={styles.successTitle}>Password Reset!</Text>
            <Text style={styles.successSubtitle}>
              Your password has been successfully reset. You can now sign in with your new password.
            </Text>

            <TouchableOpacity
              style={styles.button}
              onPress={() => router.replace('/login')}
              data-testid="go-to-login-btn"
            >
              <Ionicons name="log-in-outline" size={22} color="#1a1a1a" />
              <Text style={styles.buttonText}>SIGN IN</Text>
            </TouchableOpacity>
          </View>
        </SafeAreaView>
      </View>
    );
  }

  if (!token) {
    return (
      <View style={styles.container}>
        <SafeAreaView style={styles.safeArea}>
          <View style={styles.errorContent}>
            <View style={styles.errorIconContainer}>
              <Ionicons name="alert-circle" size={64} color="#ef4444" />
            </View>

            <Text style={styles.errorTitle}>Invalid Link</Text>
            <Text style={styles.errorSubtitle}>
              This password reset link is invalid or has expired. Please request a new one.
            </Text>

            <TouchableOpacity
              style={styles.button}
              onPress={() => router.replace('/forgot-password')}
            >
              <Ionicons name="refresh" size={20} color="#1a1a1a" />
              <Text style={styles.buttonText}>REQUEST NEW LINK</Text>
            </TouchableOpacity>
          </View>
        </SafeAreaView>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <SafeAreaView style={styles.safeArea}>
        <KeyboardAvoidingView
          behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
          style={styles.keyboardView}
        >
          <ScrollView
            contentContainerStyle={styles.scrollContent}
            keyboardShouldPersistTaps="handled"
            showsVerticalScrollIndicator={false}
          >
            {/* Header */}
            <View style={styles.header}>
              <View style={styles.iconContainer}>
                <Ionicons name="lock-open" size={32} color="#1a1a1a" />
              </View>
              <Text style={styles.title}>Reset Password</Text>
              <Text style={styles.subtitle}>Enter your new password below</Text>
            </View>

            {/* Form */}
            <View style={styles.form}>
              {/* New Password */}
              <View style={styles.inputSection}>
                <Text style={styles.inputLabel}>NEW PASSWORD</Text>
                <View style={styles.inputWrapper}>
                  <Ionicons name="lock-closed-outline" size={20} color="#a1a1aa" style={styles.inputIcon} />
                  <TextInput
                    style={styles.input}
                    placeholder="Enter new password"
                    placeholderTextColor="#6b7280"
                    value={password}
                    onChangeText={setPassword}
                    secureTextEntry={!showPassword}
                    autoCapitalize="none"
                    data-testid="reset-password-input"
                  />
                  <TouchableOpacity
                    onPress={() => setShowPassword(!showPassword)}
                    style={styles.eyeButton}
                  >
                    <Ionicons
                      name={showPassword ? 'eye-off-outline' : 'eye-outline'}
                      size={20}
                      color="#6b7280"
                    />
                  </TouchableOpacity>
                </View>
                <Text style={styles.passwordHint}>
                  8+ characters, uppercase, lowercase, and number
                </Text>
              </View>

              {/* Confirm Password */}
              <View style={styles.inputSection}>
                <Text style={styles.inputLabel}>CONFIRM PASSWORD</Text>
                <View style={styles.inputWrapper}>
                  <Ionicons name="lock-closed-outline" size={20} color="#a1a1aa" style={styles.inputIcon} />
                  <TextInput
                    style={styles.input}
                    placeholder="Confirm new password"
                    placeholderTextColor="#6b7280"
                    value={confirmPassword}
                    onChangeText={setConfirmPassword}
                    secureTextEntry={!showPassword}
                    autoCapitalize="none"
                    data-testid="reset-confirm-password-input"
                  />
                </View>
              </View>

              {/* Error Message */}
              {error ? (
                <View style={styles.errorContainer}>
                  <Ionicons name="alert-circle" size={18} color="#ef4444" />
                  <Text style={styles.errorText}>{error}</Text>
                </View>
              ) : null}

              {/* Submit Button */}
              <TouchableOpacity
                style={[styles.button, loading && styles.buttonDisabled]}
                onPress={handleSubmit}
                disabled={loading}
                data-testid="reset-password-submit-btn"
              >
                {loading ? (
                  <ActivityIndicator color="#1a1a1a" size="small" />
                ) : (
                  <>
                    <Ionicons name="checkmark-circle" size={22} color="#1a1a1a" />
                    <Text style={styles.buttonText}>RESET PASSWORD</Text>
                  </>
                )}
              </TouchableOpacity>
            </View>
          </ScrollView>
        </KeyboardAvoidingView>
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
  keyboardView: {
    flex: 1,
  },
  scrollContent: {
    padding: 20,
    paddingTop: 40,
  },
  header: {
    alignItems: 'center',
    marginBottom: 32,
  },
  iconContainer: {
    width: 72,
    height: 72,
    borderRadius: 20,
    backgroundColor: '#eab308',
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 20,
  },
  title: {
    fontSize: 28,
    fontWeight: '700',
    color: '#ffffff',
    marginBottom: 8,
  },
  subtitle: {
    fontSize: 15,
    color: '#a1a1aa',
  },
  form: {
    backgroundColor: '#27272a',
    borderRadius: 16,
    padding: 20,
  },
  inputSection: {
    marginBottom: 16,
  },
  inputLabel: {
    fontSize: 11,
    fontWeight: '600',
    color: '#a1a1aa',
    letterSpacing: 1,
    marginBottom: 8,
  },
  inputWrapper: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#3f3f46',
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#52525b',
    paddingHorizontal: 12,
  },
  inputIcon: {
    marginRight: 10,
  },
  input: {
    flex: 1,
    fontSize: 15,
    color: '#ffffff',
    paddingVertical: 14,
    fontWeight: '500',
  },
  eyeButton: {
    padding: 8,
  },
  passwordHint: {
    color: '#6b7280',
    fontSize: 11,
    marginTop: 6,
  },
  errorContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(239, 68, 68, 0.15)',
    padding: 12,
    borderRadius: 8,
    marginBottom: 16,
    gap: 8,
  },
  errorText: {
    color: '#ef4444',
    fontSize: 13,
    flex: 1,
  },
  button: {
    backgroundColor: '#eab308',
    borderRadius: 10,
    paddingVertical: 16,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 10,
  },
  buttonDisabled: {
    opacity: 0.7,
  },
  buttonText: {
    color: '#1a1a1a',
    fontSize: 15,
    fontWeight: '700',
    letterSpacing: 0.5,
  },
  // Success/Error state styles
  successContent: {
    flex: 1,
    padding: 24,
    alignItems: 'center',
    justifyContent: 'center',
  },
  successIconContainer: {
    marginBottom: 24,
  },
  successTitle: {
    fontSize: 28,
    fontWeight: '700',
    color: '#ffffff',
    marginBottom: 12,
    textAlign: 'center',
  },
  successSubtitle: {
    fontSize: 15,
    color: '#a1a1aa',
    textAlign: 'center',
    paddingHorizontal: 20,
    marginBottom: 32,
  },
  errorContent: {
    flex: 1,
    padding: 24,
    alignItems: 'center',
    justifyContent: 'center',
  },
  errorIconContainer: {
    marginBottom: 24,
  },
  errorTitle: {
    fontSize: 28,
    fontWeight: '700',
    color: '#ffffff',
    marginBottom: 12,
    textAlign: 'center',
  },
  errorSubtitle: {
    fontSize: 15,
    color: '#a1a1aa',
    textAlign: 'center',
    paddingHorizontal: 20,
    marginBottom: 32,
  },
});
