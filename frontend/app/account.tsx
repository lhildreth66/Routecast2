import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ActivityIndicator,
  ScrollView,
  Alert,
  ToastAndroid,
  ActionSheetIOS,
  Linking,
  Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { router } from 'expo-router';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';

const API_BASE = process.env.EXPO_PUBLIC_BACKEND_URL || '';

export default function AccountScreen() {
  const { user, accessToken, isAuthenticated, hasHydrated, isLoading: authLoading, logout, refreshUser } = useAuth();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [logoutLoading, setLogoutLoading] = useState(false);

  // AuthContext hydration is passive: it restores tokens without calling
  // /auth/me. Screens that need the user object must call refreshUser().
  useEffect(() => {
    if (__DEV__) {
      console.log('[account] mount diagnostic', {
        origin: typeof window !== 'undefined' ? window.location.origin : 'native',
        hasAccessToken: !!accessToken,
        storageKey: 'rc_access_token (web) / accessToken (AsyncStorage)',
        isAuthenticated,
        userIsNull: user === null,
      });
    }
    if (accessToken && !user) {
      refreshUser();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accessToken]);

  // STRIPE DISABLED - Google Play submission - do not delete
  /*
  const handleManageSubscription = async () => {
    if (!user?.subscription_provider || user.subscription_provider !== 'stripe') {
      Alert.alert(
        'Subscription Management',
        'Please manage your subscription through the platform where you subscribed (App Store or Google Play).'
      );
      return;
    }

    setLoading(true);
    setError('');

    try {
      const response = await axios.post(
        `${API_BASE}/api/subscription/portal`,
        {},
        { headers: { Authorization: `Bearer ${accessToken}` } }
      );
      const portalUrl = response.data?.url;

      if (!portalUrl) {
        const message = 'Unable to open subscription portal. Please try again.';
        if (Platform.OS === 'android') {
          ToastAndroid.show(message, ToastAndroid.LONG);
        } else if (Platform.OS === 'web' && typeof window !== 'undefined') {
          window.alert(message);
        } else {
          Alert.alert('Subscription Error', message);
        }
        setError(message);
        return;
      }

      if (Platform.OS === 'web' && typeof window !== 'undefined') {
        const isMobileWeb = /Android|iPhone|iPad|iPod|IEMobile|Opera Mini/i.test(
          window.navigator?.userAgent || ''
        );
        if (isMobileWeb) {
          const popup = window.open(portalUrl, '_blank', 'noopener,noreferrer');
          if (!popup) {
            await Linking.openURL(portalUrl);
          }
        } else {
          window.location.href = portalUrl;
        }
      } else {
        await Linking.openURL(portalUrl);
      }
    } catch (err: any) {
      const message = err.response?.data?.detail || 'Failed to open subscription portal';
      if (Platform.OS === 'android') {
        ToastAndroid.show(message, ToastAndroid.LONG);
      } else if (Platform.OS === 'web' && typeof window !== 'undefined') {
        window.alert(message);
      } else {
        Alert.alert('Subscription Error', message);
      }
      setError(message);
    } finally {
      setLoading(false);
    }
  };
  */

  const performLogout = async () => {
    setError('');
    setLogoutLoading(true);
    try {
      await logout();
      router.replace('/login');
    } catch {
      setError('Failed to sign out. Please try again.');
    } finally {
      setLogoutLoading(false);
    }
  };

  const handleLogout = () => {
    if (logoutLoading) return;
    __DEV__ && console.log('[account] Sign Out pressed, platform:', Platform.OS);

    // On web, Alert.alert() calls window.confirm() which React Native Web does
    // not reliably wire up callbacks for. Skip the dialog and sign out directly.
    if (Platform.OS === 'web') {
      performLogout();
      return;
    }

    if (Platform.OS === 'ios') {
      ActionSheetIOS.showActionSheetWithOptions(
        {
          title: 'Sign Out',
          message: 'Are you sure you want to sign out?',
          options: ['Cancel', 'Sign Out'],
          destructiveButtonIndex: 1,
          cancelButtonIndex: 0,
        },
        (buttonIndex) => {
          if (buttonIndex === 1) {
            performLogout();
          }
        }
      );
      return;
    }

    Alert.alert(
      'Sign Out',
      'Are you sure you want to sign out?',
      [
        { text: 'Cancel', style: 'cancel' },
        { text: 'Sign Out', style: 'destructive', onPress: performLogout }
      ]
    );
  };

  const getSubscriptionBadge = () => {
    if (!user) return null;
    
    if (user.is_premium) {
      if (user.subscription_status === 'trialing') {
        return { label: 'TRIAL', color: '#eab308', bgColor: '#422006' };
      }
      return { label: 'PREMIUM', color: '#22c55e', bgColor: '#14532d' };
    }
    return { label: 'FREE', color: '#6b7280', bgColor: '#27272a' };
  };

  const badge = getSubscriptionBadge();

  const formatDate = (dateString?: string) => {
    if (!dateString) return 'N/A';
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric'
    });
  };

  if (!hasHydrated || authLoading || (isAuthenticated && !user)) {
    // Still hydrating or loading the user profile – show a neutral spinner
    // so we never flash "Not Signed In" for an already-authenticated session.
    return (
      <View style={[styles.container, { justifyContent: 'center', alignItems: 'center' }]}>
        <ActivityIndicator size="large" color="#eab308" />
      </View>
    );
  }

  if (!isAuthenticated) {
    return (
      <View style={styles.container}>
        <SafeAreaView style={styles.safeArea}>
          <View style={styles.notLoggedIn}>
            <TouchableOpacity
              style={styles.backButton}
              onPress={() => router.back()}
            >
              <Ionicons name="arrow-back" size={24} color="#fff" />
            </TouchableOpacity>

            <View style={styles.notLoggedInContent}>
              <Ionicons name="person-circle-outline" size={80} color="#52525b" />
              <Text style={styles.notLoggedInTitle}>Not Signed In</Text>
              <Text style={styles.notLoggedInSubtitle}>
                Sign in to manage your account and subscription
              </Text>

              <TouchableOpacity
                style={styles.signInButton}
                onPress={() => router.push('/login')}
                data-testid="account-login-btn"
              >
                <Ionicons name="log-in-outline" size={22} color="#1a1a1a" />
                <Text style={styles.signInButtonText}>SIGN IN</Text>
              </TouchableOpacity>

              <TouchableOpacity
                style={styles.signUpButton}
                onPress={() => router.push('/signup')}
                data-testid="account-signup-btn"
              >
                <Text style={styles.signUpButtonText}>Create Account</Text>
              </TouchableOpacity>
            </View>
          </View>
        </SafeAreaView>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <SafeAreaView style={styles.safeArea}>
        <ScrollView
          contentContainerStyle={styles.scrollContent}
          showsVerticalScrollIndicator={false}
        >
          {/* Back Button */}
          <TouchableOpacity
            style={styles.backButton}
            onPress={() => router.back()}
            data-testid="account-back-btn"
          >
            <Ionicons name="arrow-back" size={24} color="#fff" />
          </TouchableOpacity>

          {/* Header */}
          <View style={styles.header}>
            <View style={styles.avatarContainer}>
              <Ionicons name="person" size={40} color="#eab308" />
            </View>
            <Text style={styles.userName}>{user.name || 'Routecast User'}</Text>
            <Text style={styles.userEmail}>{user.email}</Text>
            {badge && (
              <View style={[styles.badge, { backgroundColor: badge.bgColor }]}>
                <Text style={[styles.badgeText, { color: badge.color }]}>{badge.label}</Text>
              </View>
            )}
          </View>

          {/* Subscription Section */}
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>SUBSCRIPTION</Text>
            <View style={styles.card}>
              <View style={styles.cardRow}>
                <View style={styles.cardRowLeft}>
                  <Ionicons name="card" size={22} color="#a1a1aa" />
                  <Text style={styles.cardRowLabel}>Plan</Text>
                </View>
                <Text style={styles.cardRowValue}>
                  {user.subscription_plan.charAt(0).toUpperCase() + user.subscription_plan.slice(1)}
                </Text>
              </View>

              <View style={styles.cardDivider} />

              <View style={styles.cardRow}>
                <View style={styles.cardRowLeft}>
                  <Ionicons name="pulse" size={22} color="#a1a1aa" />
                  <Text style={styles.cardRowLabel}>Status</Text>
                </View>
                <View style={styles.statusContainer}>
                  <View style={[
                    styles.statusDot,
                    { backgroundColor: user.is_premium ? '#22c55e' : '#6b7280' }
                  ]} />
                  <Text style={[
                    styles.cardRowValue,
                    { color: user.is_premium ? '#22c55e' : '#a1a1aa' }
                  ]}>
                    {user.subscription_status.charAt(0).toUpperCase() + user.subscription_status.slice(1)}
                  </Text>
                </View>
              </View>

              {user.subscription_expiration && (
                <>
                  <View style={styles.cardDivider} />
                  <View style={styles.cardRow}>
                    <View style={styles.cardRowLeft}>
                      <Ionicons name="calendar" size={22} color="#a1a1aa" />
                      <Text style={styles.cardRowLabel}>
                        {user.subscription_status === 'trialing' ? 'Trial Ends' : 'Renews'}
                      </Text>
                    </View>
                    <Text style={styles.cardRowValue}>
                      {formatDate(user.subscription_expiration)}
                    </Text>
                  </View>
                </>
              )}

              {user.trial_days_remaining !== undefined && user.trial_days_remaining !== null && (
                <>
                  <View style={styles.cardDivider} />
                  <View style={styles.trialRemaining}>
                    <Ionicons name="time" size={18} color="#eab308" />
                    <Text style={styles.trialRemainingText}>
                      {user.trial_days_remaining} days remaining in trial
                    </Text>
                  </View>
                </>
              )}
            </View>

            {/* // STRIPE DISABLED - Google Play submission - do not delete */}
            {/* Manage Subscription - only for premium Stripe users */}
            {/**
            {user.is_premium && user.subscription_provider === 'stripe' && (
              <TouchableOpacity
                style={[styles.manageButton, loading && styles.buttonDisabled]}
                onPress={handleManageSubscription}
                disabled={loading}
                data-testid="manage-subscription-btn"
              >
                {loading ? (
                  <ActivityIndicator color="#eab308" size="small" />
                ) : (
                  <>
                    <Ionicons name="settings-outline" size={20} color="#eab308" />
                    <Text style={styles.manageButtonText}>Manage Subscription</Text>
                  </>
                )}
              </TouchableOpacity>
            )}
            */}
          </View>

          {/* Account Section */}
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>ACCOUNT</Text>
            <View style={styles.card}>
              <TouchableOpacity style={styles.menuItem}>
                <View style={styles.menuItemLeft}>
                  <Ionicons name="mail" size={22} color="#a1a1aa" />
                  <Text style={styles.menuItemText}>Email</Text>
                </View>
                <View style={styles.menuItemRight}>
                  {user.email_verified ? (
                    <View style={styles.verifiedBadge}>
                      <Ionicons name="checkmark-circle" size={16} color="#22c55e" />
                      <Text style={styles.verifiedText}>Verified</Text>
                    </View>
                  ) : (
                    <TouchableOpacity
                      style={styles.verifyButton}
                      onPress={() => router.push('/verify-email')}
                    >
                      <Text style={styles.verifyButtonText}>Verify</Text>
                    </TouchableOpacity>
                  )}
                </View>
              </TouchableOpacity>

              <View style={styles.cardDivider} />

              <TouchableOpacity style={styles.menuItem}>
                <View style={styles.menuItemLeft}>
                  <Ionicons name="calendar-outline" size={22} color="#a1a1aa" />
                  <Text style={styles.menuItemText}>Member Since</Text>
                </View>
                <Text style={styles.menuItemValue}>
                  {formatDate(user.created_at)}
                </Text>
              </TouchableOpacity>
            </View>
          </View>

          {/* Features Section */}
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>YOUR FEATURES</Text>
            <View style={styles.card}>
              {user.entitlements.map((entitlement, index) => (
                <React.Fragment key={entitlement}>
                  {index > 0 && <View style={styles.cardDivider} />}
                  <View style={styles.entitlementRow}>
                    <Ionicons name="checkmark-circle" size={20} color="#22c55e" />
                    <Text style={styles.entitlementText}>
                      {entitlement.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                    </Text>
                  </View>
                </React.Fragment>
              ))}
            </View>
          </View>

          {/* Error Message */}
          {error && (
            <View style={styles.errorContainer}>
              <Ionicons name="alert-circle" size={18} color="#ef4444" />
              <Text style={styles.errorText}>{error}</Text>
            </View>
          )}

          {/* Sign Out Button */}
          <TouchableOpacity
            style={[styles.logoutButton, logoutLoading && styles.buttonDisabled]}
            onPress={handleLogout}
            disabled={logoutLoading}
            data-testid="logout-btn"
          >
            {logoutLoading ? (
              <ActivityIndicator size="small" color="#ef4444" />
            ) : (
              <>
                <Ionicons name="log-out-outline" size={22} color="#ef4444" />
                <Text style={styles.logoutButtonText}>Sign Out</Text>
              </>
            )}
          </TouchableOpacity>
        </ScrollView>
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
  avatarContainer: {
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: '#27272a',
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 16,
  },
  userName: {
    fontSize: 24,
    fontWeight: '700',
    color: '#ffffff',
    marginBottom: 4,
  },
  userEmail: {
    fontSize: 14,
    color: '#a1a1aa',
    marginBottom: 12,
  },
  badge: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 16,
  },
  badgeText: {
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 0.5,
  },
  section: {
    marginBottom: 24,
  },
  sectionTitle: {
    fontSize: 11,
    fontWeight: '600',
    color: '#6b7280',
    letterSpacing: 1,
    marginBottom: 12,
  },
  card: {
    backgroundColor: '#27272a',
    borderRadius: 12,
    padding: 16,
  },
  cardRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 4,
  },
  cardRowLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  cardRowLabel: {
    color: '#a1a1aa',
    fontSize: 14,
  },
  cardRowValue: {
    color: '#ffffff',
    fontSize: 14,
    fontWeight: '500',
  },
  cardDivider: {
    height: 1,
    backgroundColor: '#3f3f46',
    marginVertical: 12,
  },
  statusContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  trialRemaining: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    backgroundColor: '#422006',
    padding: 10,
    borderRadius: 8,
    marginTop: 4,
  },
  trialRemainingText: {
    color: '#eab308',
    fontSize: 13,
    fontWeight: '500',
  },
  upgradeButton: {
    backgroundColor: '#eab308',
    borderRadius: 10,
    paddingVertical: 14,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    marginTop: 12,
  },
  upgradeButtonText: {
    color: '#1a1a1a',
    fontSize: 14,
    fontWeight: '700',
  },
  manageButton: {
    backgroundColor: '#27272a',
    borderRadius: 10,
    paddingVertical: 14,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    marginTop: 12,
    borderWidth: 1,
    borderColor: '#eab308',
  },
  buttonDisabled: {
    opacity: 0.7,
  },
  manageButtonText: {
    color: '#eab308',
    fontSize: 14,
    fontWeight: '600',
  },
  menuItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 4,
  },
  menuItemLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  menuItemText: {
    color: '#a1a1aa',
    fontSize: 14,
  },
  menuItemRight: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  menuItemValue: {
    color: '#ffffff',
    fontSize: 14,
  },
  verifiedBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  verifiedText: {
    color: '#22c55e',
    fontSize: 13,
  },
  verifyButton: {
    backgroundColor: '#eab308',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 6,
  },
  verifyButtonText: {
    color: '#1a1a1a',
    fontSize: 12,
    fontWeight: '600',
  },
  entitlementRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    paddingVertical: 4,
  },
  entitlementText: {
    color: '#e4e4e7',
    fontSize: 14,
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
  logoutButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: 16,
    marginTop: 8,
    marginBottom: 40,
  },
  logoutButtonText: {
    color: '#ef4444',
    fontSize: 15,
    fontWeight: '600',
  },
  // Not logged in state
  notLoggedIn: {
    flex: 1,
    padding: 20,
    paddingTop: 12,
  },
  notLoggedInContent: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingBottom: 100,
  },
  notLoggedInTitle: {
    fontSize: 24,
    fontWeight: '700',
    color: '#ffffff',
    marginTop: 20,
    marginBottom: 8,
  },
  notLoggedInSubtitle: {
    fontSize: 14,
    color: '#a1a1aa',
    textAlign: 'center',
    marginBottom: 32,
  },
  signInButton: {
    backgroundColor: '#eab308',
    borderRadius: 10,
    paddingVertical: 16,
    paddingHorizontal: 48,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 10,
    marginBottom: 12,
  },
  signInButtonText: {
    color: '#1a1a1a',
    fontSize: 15,
    fontWeight: '700',
    letterSpacing: 0.5,
  },
  signUpButton: {
    paddingVertical: 12,
  },
  signUpButtonText: {
    color: '#a1a1aa',
    fontSize: 14,
  },
});
