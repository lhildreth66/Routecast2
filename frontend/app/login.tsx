import React, { useState } from 'react';
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
import { useAuth } from '../contexts/AuthContext';

export default function LoginScreen() {
  // AuthProvider already gates children on hasHydrated, so by the time
  // this screen renders, hydration is always complete. The destructure
  // of hasHydrated is kept for the early-return below as a fallback.
  const { login, hasHydrated } = useAuth();
  const { verified, trial } = useLocalSearchParams<{ verified?: string; trial?: string }>();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Defensive guard – should never be true since AuthProvider blocks children
  // until hydration completes, but keeps hook ordering intact.
  if (!hasHydrated) {
    return null;
  }

  const handleLogin = async () => {
    if (loading) {
      __DEV__ && console.log('[auth] handleLogin called while loading – blocked (double-tap guard)');
      return;
    }
    if (!email.trim() || !password.trim()) {
      setError('Please enter both email and password');
      return;
    }

    setLoading(true);
    setError('');
    __DEV__ && console.log('[auth] login submit – calling login()');

    const result = await login(email.trim(), password);
    __DEV__ && console.log('[auth] login() returned – success:', result.success, 'error:', result.error ?? 'none');

    if (result.success) {
      __DEV__ && console.log('[auth] login success – resetting loading, navigating to /');
      setLoading(false);
      // If user arrived from a verify-email link on a different device,
      // they are now verified and need to subscribe – the index guard will
      // detect email_verified=true + is_premium=false and redirect them.
      router.replace('/');
      return;
    }

    setLoading(false);
    setError(result.error || 'Login failed');
    __DEV__ && console.log('[auth] login failed – showing error:', result.error);
  };

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
            {/* Back Button */}
            <TouchableOpacity
              style={styles.backButton}
              onPress={() => router.back()}
              data-testid="login-back-btn"
            >
              <Ionicons name="arrow-back" size={24} color="#fff" />
            </TouchableOpacity>

            {/* Header */}
            <View style={styles.header}>
              <View style={styles.iconContainer}>
                <Ionicons name="person" size={32} color="#1a1a1a" />
              </View>
              <Text style={styles.title}>Welcome Back</Text>
              <Text style={styles.subtitle}>Sign in to access your account</Text>
            </View>

            {/* Verified-email success banner (cross-device link flow) */}
            {verified === '1' && (
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10,
                backgroundColor: 'rgba(34,197,94,0.12)', borderWidth: 1,
                borderColor: '#22c55e', borderRadius: 10, padding: 14, marginBottom: 16 }}>
                <Ionicons name="checkmark-circle" size={20} color="#22c55e" />
                <Text style={{ color: '#22c55e', fontSize: 14, flex: 1, lineHeight: 20 }}>
                  Email verified! Sign in to start your 7-day free trial.
                </Text>
              </View>
            )}

            {/* // STRIPE DISABLED - Google Play submission - do not delete */}
            {/* Trial-started banner (Stripe success redirect) */}
            {/*
            {trial === '1' && (
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10,
                backgroundColor: 'rgba(34,197,94,0.12)', borderWidth: 1,
                borderColor: '#22c55e', borderRadius: 10, padding: 14, marginBottom: 16 }}>
                <Ionicons name="star" size={20} color="#22c55e" />
                <Text style={{ color: '#22c55e', fontSize: 14, flex: 1, lineHeight: 20 }}>
                  Trial started! Sign in to access Routecast.
                </Text>
              </View>
            )}
            */}

            {/* Login Form */}
            <View style={styles.form}>
              {/* Email Input */}
              <View style={styles.inputSection}>
                <Text style={styles.inputLabel}>EMAIL</Text>
                <View style={styles.inputWrapper}>
                  <Ionicons name="mail-outline" size={20} color="#a1a1aa" style={styles.inputIcon} />
                  <TextInput
                    style={styles.input}
                    placeholder="Enter your email"
                    placeholderTextColor="#6b7280"
                    value={email}
                    onChangeText={setEmail}
                    keyboardType="email-address"
                    autoCapitalize="none"
                    autoCorrect={false}
                    data-testid="login-email-input"
                  />
                </View>
              </View>

              {/* Password Input */}
              <View style={styles.inputSection}>
                <Text style={styles.inputLabel}>PASSWORD</Text>
                <View style={styles.inputWrapper}>
                  <Ionicons name="lock-closed-outline" size={20} color="#a1a1aa" style={styles.inputIcon} />
                  <TextInput
                    style={styles.input}
                    placeholder="Enter your password"
                    placeholderTextColor="#6b7280"
                    value={password}
                    onChangeText={setPassword}
                    secureTextEntry={!showPassword}
                    autoCapitalize="none"
                    data-testid="login-password-input"
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
              </View>

              {/* Forgot Password */}
              <TouchableOpacity
                style={styles.forgotPassword}
                onPress={() => router.push('/forgot-password')}
                data-testid="forgot-password-link"
              >
                <Text style={styles.forgotPasswordText}>Forgot Password?</Text>
              </TouchableOpacity>

              {/* Error Message */}
              {error ? (
                <View style={styles.errorContainer}>
                  <Ionicons name="alert-circle" size={18} color="#ef4444" />
                  <Text style={styles.errorText}>{error}</Text>
                </View>
              ) : null}

              {/* Login Button */}
              <TouchableOpacity
                style={[styles.button, loading && styles.buttonDisabled]}
                onPress={handleLogin}
                disabled={loading}
                data-testid="login-submit-btn"
              >
                {loading ? (
                  <ActivityIndicator color="#1a1a1a" size="small" />
                ) : (
                  <>
                    <Ionicons name="log-in-outline" size={22} color="#1a1a1a" />
                    <Text style={styles.buttonText}>SIGN IN</Text>
                  </>
                )}
              </TouchableOpacity>

              {/* Sign Up Link */}
              <View style={styles.signupContainer}>
                <Text style={styles.signupText}>Don't have an account? </Text>
                <TouchableOpacity onPress={() => router.push('/signup')} data-testid="signup-link">
                  <Text style={styles.signupLink}>Sign Up</Text>
                </TouchableOpacity>
              </View>
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
    paddingTop: 12,
  },
  backButton: {
    width: 44,
    height: 44,
    borderRadius: 12,
    backgroundColor: '#27272a',
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 24,
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
  forgotPassword: {
    alignSelf: 'flex-end',
    marginBottom: 20,
  },
  forgotPasswordText: {
    color: '#eab308',
    fontSize: 13,
    fontWeight: '500',
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
  signupContainer: {
    flexDirection: 'row',
    justifyContent: 'center',
    marginTop: 20,
  },
  signupText: {
    color: '#a1a1aa',
    fontSize: 14,
  },
  signupLink: {
    color: '#eab308',
    fontSize: 14,
    fontWeight: '600',
  },
});
