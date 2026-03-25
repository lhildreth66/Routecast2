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
  Linking,
  Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { router, useLocalSearchParams } from 'expo-router';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';

const API_BASE = process.env.EXPO_PUBLIC_BACKEND_URL || '';
const GOOGLE_PLAY_URL = 'GOOGLE_PLAY_URL';
const isWeb = Platform.OS === 'web';

interface Plan {
  id: string;
  name: string;
  price: number;
  currency: string;
  interval: string;
  trial_days: number;
  features: string[];
  savings?: string;
}

export default function SubscriptionScreen() {
  const { user, accessToken, refreshUser, isAuthenticated } = useAuth();
  useLocalSearchParams<{ canceled?: string }>();
  const [plans, setPlans] = useState<Plan[]>([]);
  const [loading, setLoading] = useState(true);
  const [checkoutLoading, setCheckoutLoading] = useState(false);
  const [trialLoading, setTrialLoading] = useState(false);
  const [error, setError] = useState('');
  const [mounted, setMounted] = useState(false);
  // track which plan is currently launching so each card can show its own spinner
  const [launchingPlan, setLaunchingPlan] = useState<string | null>(null);

  useEffect(() => {
    if (isWeb) return;
    fetchPlans();
  }, [isWeb]);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (isWeb) {
      router.replace('/landing');
    }
  }, [isWeb]);

  const openGooglePlay = () => Linking.openURL(GOOGLE_PLAY_URL);

  const fetchPlans = async () => {
    try {
      const response = await axios.get(`${API_BASE}/api/subscription/plans`);
      setPlans(response.data.plans);
    } catch (err) {
      console.log('Error fetching plans:', err);
      setError('Failed to load subscription plans');
    } finally {
      setLoading(false);
    }
  };

  const handleStartTrial = async () => {
    if (!isAuthenticated) {
      router.push('/signup');
      return;
    }

    setTrialLoading(true);
    setError('');

    try {
      await axios.post(
        `${API_BASE}/api/subscription/start-trial`,
        {},
        { headers: { Authorization: `Bearer ${accessToken}` } }
      );
      await refreshUser();
      router.replace('/');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to start trial');
    } finally {
      setTrialLoading(false);
    }
  };

  const handleCheckout = async (planId: string) => {
    if (!isAuthenticated) {
      router.push('/signup');
      return;
    }

    setLaunchingPlan(planId);
    setCheckoutLoading(true);
    setError('');

    try {
      const origin = Platform.OS === 'web' && typeof window !== 'undefined'
        ? window.location.origin
        : 'https://routecastweather.com';

      const response = await axios.post(
        `${API_BASE}/api/subscription/checkout`,
        { plan: planId, origin_url: origin },
        { headers: { Authorization: `Bearer ${accessToken}` } }
      );

      const { checkout_url } = response.data;

      if (Platform.OS === 'web' && typeof window !== 'undefined') {
        window.location.href = checkout_url;
      } else {
        await Linking.openURL(checkout_url);
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to start checkout');
    } finally {
      setCheckoutLoading(false);
      setLaunchingPlan(null);
    }
  };

  const handleManageSubscription = async () => {
    if (!isAuthenticated) {
      router.push('/login');
      return;
    }

    setCheckoutLoading(true);
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
      setCheckoutLoading(false);
    }
  };

  if (!mounted) return null;

  if (isWeb) {
    return (
      <View style={styles.webContainer}>
        <SafeAreaView style={styles.safeArea}>
          <View style={styles.webContent}>
            <Text style={styles.webTitle}>Get RouteCast on Android</Text>
            <Text style={styles.webSubtitle}>
              Subscriptions are available in the Android app through Google Play. Download to manage billing and premium access securely in-app.
            </Text>
            <TouchableOpacity style={styles.webCta} onPress={openGooglePlay}>
              <Ionicons name="logo-google-playstore" size={22} color="#0f0f0f" />
              <Text style={styles.webCtaText}>Download on Google Play</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.webSecondary} onPress={() => router.replace('/landing')}>
              <Text style={styles.webSecondaryText}>Return to Landing</Text>
              <Ionicons name="arrow-forward" size={18} color="#eab308" />
            </TouchableOpacity>
          </View>
        </SafeAreaView>
      </View>
    );
  }

  const isPremium = user?.is_premium;
  const isTrialing = user?.subscription_status === 'trialing';
  const canStartTrial = user?.trial_available && !isPremium && !isTrialing;

  if (loading && !error) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#eab308" />
      </View>
    );
  }

  // Already premium - show success state
  if (isPremium && !isTrialing) {
    return (
      <View style={styles.container}>
        <SafeAreaView style={styles.safeArea}>
          <View style={styles.premiumContent}>
            <TouchableOpacity
              style={styles.backButton}
              onPress={() => router.back()}
            >
              <Ionicons name="arrow-back" size={24} color="#fff" />
            </TouchableOpacity>

            <View style={styles.premiumIconContainer}>
              <Ionicons name="star" size={48} color="#eab308" />
            </View>

            <Text style={styles.premiumTitle}>You're Premium!</Text>
            <Text style={styles.premiumSubtitle}>
              You have full access to all Routecast features
            </Text>

            <View style={styles.premiumInfoBox}>
              <View style={styles.premiumInfoRow}>
                <Ionicons name="calendar" size={20} color="#a1a1aa" />
                <Text style={styles.premiumInfoText}>
                  Plan: {user?.subscription_plan?.charAt(0).toUpperCase() + user?.subscription_plan?.slice(1)}
                </Text>
              </View>
              {user?.subscription_expiration && (
                <View style={styles.premiumInfoRow}>
                  <Ionicons name="time" size={20} color="#a1a1aa" />
                  <Text style={styles.premiumInfoText}>
                    Renews: {new Date(user.subscription_expiration).toLocaleDateString()}
                  </Text>
                </View>
              )}
            </View>

            <TouchableOpacity
              style={[styles.manageButton, checkoutLoading && styles.buttonDisabled]}
              onPress={handleManageSubscription}
              disabled={checkoutLoading}
            >
              {checkoutLoading ? (
                <ActivityIndicator color="#eab308" size="small" />
              ) : (
                <>
                  <Ionicons name="settings-outline" size={20} color="#eab308" />
                  <Text style={styles.manageButtonText}>Manage Subscription</Text>
                </>
              )}
            </TouchableOpacity>

            <TouchableOpacity
              style={styles.continueButton}
              onPress={() => router.replace('/')}
            >
              <Text style={styles.continueButtonText}>Continue to App</Text>
            </TouchableOpacity>
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
            data-testid="subscription-back-btn"
          >
            <Ionicons name="arrow-back" size={24} color="#fff" />
          </TouchableOpacity>

          {/* Header */}
          <View style={styles.header}>
            <View style={styles.iconContainer}>
              <Ionicons name="rocket" size={32} color="#1a1a1a" />
            </View>
            <Text style={styles.title}>Upgrade to Premium</Text>
            <Text style={styles.subtitle}>
              Unlock all features and drive with confidence
            </Text>
          </View>

          {/* Trial Banner */}
          {canStartTrial && (
            <View style={styles.trialBanner}>
              <View style={styles.trialBannerContent}>
                <Ionicons name="gift" size={24} color="#22c55e" />
                <View style={styles.trialBannerText}>
                  <Text style={styles.trialBannerTitle}>7-Day Free Trial</Text>
                  <Text style={styles.trialBannerSubtitle}>
                    Try all premium features free. No credit card required.
                  </Text>
                </View>
              </View>
              <TouchableOpacity
                style={[styles.trialButton, trialLoading && styles.buttonDisabled]}
                onPress={handleStartTrial}
                disabled={trialLoading}
                data-testid="start-trial-btn"
              >
                {trialLoading ? (
                  <ActivityIndicator color="#fff" size="small" />
                ) : (
                  <Text style={styles.trialButtonText}>Start Free Trial</Text>
                )}
              </TouchableOpacity>
            </View>
          )}

          {/* Active Trial Banner */}
          {isTrialing && user?.trial_days_remaining !== undefined && (
            <View style={styles.activeTrialBanner}>
              <Ionicons name="time" size={24} color="#eab308" />
              <View style={styles.activeTrialText}>
                <Text style={styles.activeTrialTitle}>Trial Active</Text>
                <Text style={styles.activeTrialSubtitle}>
                  {user.trial_days_remaining} days remaining
                </Text>
              </View>
            </View>
          )}

          {/* Plans */}
          <Text style={styles.sectionTitle}>Choose Your Plan</Text>
          
          <View style={styles.plansContainer}>
            {plans.map((plan) => (
              <View
                key={plan.id}
                style={styles.planCard}
                data-testid={`plan-${plan.id}`}
              >
                {plan.savings && (
                  <View style={styles.savingsBadge}>
                    <Text style={styles.savingsText}>{plan.savings}</Text>
                  </View>
                )}
                
                <View style={styles.planHeader}>
                  <Text style={styles.planName}>{plan.name}</Text>
                  <View style={styles.planPriceContainer}>
                    <Text style={styles.planPrice}>${plan.price}</Text>
                    <Text style={styles.planInterval}>/{plan.interval}</Text>
                  </View>
                </View>

                <View style={styles.planFeatures}>
                  {plan.features.map((feature, index) => (
                    <View key={index} style={styles.featureRow}>
                      <Ionicons name="checkmark-circle" size={18} color="#22c55e" />
                      <Text style={styles.featureText}>{feature}</Text>
                    </View>
                  ))}
                </View>

                {/* Per-plan CTA button */}
                <TouchableOpacity
                  style={[styles.planCTAButton, launchingPlan === plan.id && styles.buttonDisabled]}
                  onPress={() => handleCheckout(plan.id)}
                  disabled={checkoutLoading}
                  data-testid={`checkout-${plan.id}`}
                >
                  {launchingPlan === plan.id ? (
                    <ActivityIndicator color="#1a1a1a" size="small" />
                  ) : (
                    <Text style={styles.planCTAButtonText}>
                      Start 7-day free trial — {plan.interval === 'year' || plan.id === 'yearly' ? `$${plan.price}/yr` : `$${plan.price}/mo`}
                    </Text>
                  )}
                </TouchableOpacity>
              </View>
            ))}
          </View>

          {/* Error Message */}
          {error && (
            <View style={styles.errorContainer}>
              <Ionicons name="alert-circle" size={18} color="#ef4444" />
              <Text style={styles.errorText}>{error}</Text>
            </View>
          )}

          {/* Terms */}
          <Text style={styles.termsText}>
            By subscribing, you agree to our Terms of Service and Privacy Policy.
            Subscriptions auto-renew unless cancelled.
          </Text>
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
  loadingContainer: {
    flex: 1,
    backgroundColor: '#0f0f0f',
    justifyContent: 'center',
    alignItems: 'center',
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
  webContainer: {
    flex: 1,
    backgroundColor: '#0f0f0f',
  },
  webContent: {
    flex: 1,
    padding: 24,
    gap: 16,
    maxWidth: 520,
    marginHorizontal: 'auto',
    justifyContent: 'center',
  },
  webTitle: {
    color: '#ffffff',
    fontSize: 28,
    fontWeight: '800',
    textAlign: 'center',
  },
  webSubtitle: {
    color: '#a1a1aa',
    fontSize: 16,
    textAlign: 'center',
    lineHeight: 24,
  },
  webCta: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 10,
    backgroundColor: '#eab308',
    paddingVertical: 14,
    borderRadius: 12,
  },
  webCtaText: {
    color: '#0f0f0f',
    fontSize: 16,
    fontWeight: '700',
  },
  webSecondary: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    marginTop: 6,
    paddingVertical: 12,
  },
  webSecondaryText: {
    color: '#eab308',
    fontSize: 15,
    fontWeight: '600',
  },
  header: {
    alignItems: 'center',
    marginBottom: 24,
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
    textAlign: 'center',
  },
  trialBanner: {
    backgroundColor: '#14532d',
    borderRadius: 12,
    padding: 16,
    marginBottom: 24,
  },
  trialBannerContent: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    marginBottom: 12,
  },
  trialBannerText: {
    flex: 1,
  },
  trialBannerTitle: {
    color: '#22c55e',
    fontSize: 16,
    fontWeight: '700',
  },
  trialBannerSubtitle: {
    color: '#86efac',
    fontSize: 13,
    marginTop: 2,
  },
  trialButton: {
    backgroundColor: '#22c55e',
    borderRadius: 8,
    paddingVertical: 12,
    alignItems: 'center',
  },
  trialButtonText: {
    color: '#fff',
    fontSize: 14,
    fontWeight: '700',
  },
  activeTrialBanner: {
    backgroundColor: '#422006',
    borderRadius: 12,
    padding: 16,
    marginBottom: 24,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  activeTrialText: {
    flex: 1,
  },
  activeTrialTitle: {
    color: '#eab308',
    fontSize: 16,
    fontWeight: '700',
  },
  activeTrialSubtitle: {
    color: '#fcd34d',
    fontSize: 13,
    marginTop: 2,
  },
  sectionTitle: {
    color: '#a1a1aa',
    fontSize: 13,
    fontWeight: '600',
    letterSpacing: 0.5,
    marginBottom: 12,
    textTransform: 'uppercase',
  },
  plansContainer: {
    gap: 12,
    marginBottom: 20,
  },
  planCard: {
    backgroundColor: '#27272a',
    borderRadius: 12,
    padding: 16,
    borderWidth: 2,
    borderColor: 'transparent',
    position: 'relative',
  },
  planCardSelected: {
    borderColor: '#eab308',
    backgroundColor: '#1c1917',
  },
  savingsBadge: {
    position: 'absolute',
    top: -10,
    right: 12,
    backgroundColor: '#22c55e',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
  },
  savingsText: {
    color: '#fff',
    fontSize: 11,
    fontWeight: '700',
  },
  planHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
  },
  planName: {
    color: '#fff',
    fontSize: 18,
    fontWeight: '700',
  },
  planPriceContainer: {
    flexDirection: 'row',
    alignItems: 'baseline',
    flexWrap: 'nowrap',
  },
  planPrice: {
    color: '#eab308',
    fontSize: 24,
    fontWeight: '700',
  },
  planInterval: {
    color: '#6b7280',
    fontSize: 14,
    flexShrink: 0,
  },
  planFeatures: {
    gap: 8,
  },
  featureRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  featureText: {
    color: '#d4d4d8',
    fontSize: 13,
  },
  selectedIndicator: {
    position: 'absolute',
    top: 12,
    left: 12,
  },
  planCTAButton: {
    backgroundColor: '#eab308',
    borderRadius: 10,
    paddingVertical: 13,
    alignItems: 'center',
    marginTop: 14,
  },
  planCTAButtonText: {
    color: '#1a1a1a',
    fontSize: 14,
    fontWeight: '800',
    letterSpacing: 0.2,
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
  checkoutButton: {
    backgroundColor: '#eab308',
    borderRadius: 10,
    paddingVertical: 16,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 10,
    marginBottom: 12,
  },
  buttonDisabled: {
    opacity: 0.7,
  },
  checkoutButtonText: {
    color: '#1a1a1a',
    fontSize: 16,
    fontWeight: '700',
  },
  termsText: {
    color: '#52525b',
    fontSize: 11,
    textAlign: 'center',
    lineHeight: 16,
  },
  // Premium state styles
  premiumContent: {
    flex: 1,
    padding: 24,
    alignItems: 'center',
  },
  premiumIconContainer: {
    width: 96,
    height: 96,
    borderRadius: 24,
    backgroundColor: '#422006',
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 24,
    marginTop: 40,
  },
  premiumTitle: {
    fontSize: 28,
    fontWeight: '700',
    color: '#ffffff',
    marginBottom: 8,
  },
  premiumSubtitle: {
    fontSize: 15,
    color: '#a1a1aa',
    textAlign: 'center',
    marginBottom: 32,
  },
  premiumInfoBox: {
    backgroundColor: '#27272a',
    borderRadius: 12,
    padding: 16,
    width: '100%',
    gap: 12,
    marginBottom: 24,
  },
  premiumInfoRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  premiumInfoText: {
    color: '#e4e4e7',
    fontSize: 14,
  },
  manageButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    backgroundColor: '#27272a',
    borderRadius: 10,
    paddingVertical: 14,
    paddingHorizontal: 24,
    borderWidth: 1,
    borderColor: '#eab308',
    width: '100%',
    justifyContent: 'center',
    marginBottom: 12,
  },
  manageButtonText: {
    color: '#eab308',
    fontSize: 14,
    fontWeight: '600',
  },
  continueButton: {
    paddingVertical: 12,
  },
  continueButtonText: {
    color: '#6b7280',
    fontSize: 14,
  },
});
