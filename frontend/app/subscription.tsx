import React, { useEffect, useMemo } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ActivityIndicator,
  ScrollView,
  Linking,
  Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { router, useLocalSearchParams } from 'expo-router';
import * as IAP from 'expo-iap';
import { useAuth } from '../contexts/AuthContext';
import { useBilling } from './hooks/useBilling';

const GOOGLE_PLAY_URL = 'https://play.google.com/store/apps/details?id=com.routecast.app';
const isWeb = Platform.OS === 'web';

type OfferInfo = {
  offerToken?: string;
  price?: string;
  period?: string;
  trialPeriod?: string;
  offerId?: string;
  error?: string;
};

const humanizePeriod = (period?: string) => {
  if (!period) return '';
  const match = /P(\d+)([YMWD])/i.exec(period);
  if (!match) return period;
  const value = Number(match[1]);
  const unitMap: Record<string, string> = { Y: 'year', M: 'month', W: 'week', D: 'day' };
  const unit = unitMap[match[2].toUpperCase()] ?? period;
  return value === 1 ? unit : `${value} ${unit}s`;
};

const selectOfferForBasePlan = (product: IAP.Subscription | undefined, basePlanId: string): OfferInfo | null => {
  if (!product?.subscriptionOfferDetails?.length) return { error: 'Billing unavailable for this plan' };

  const offers = product.subscriptionOfferDetails.filter((offer) => offer.basePlanId === basePlanId);
  if (!offers.length) return { error: `No offers found for ${basePlanId} plan` };

  // Enforce base-plan specific offer preference rules
  const filtered = basePlanId === 'annual' ? offers.filter((offer) => offer.offerId !== 'trial7d') : offers;
  if (!filtered.length) {
    return { error: basePlanId === 'annual' ? 'Annual plan unavailable right now' : `No valid offers for ${basePlanId}` };
  }

  const preferred = basePlanId === 'monthly'
    ? filtered.find((offer) => offer.offerId === 'trial7d') ?? filtered[0]
    : filtered[0];

  const phases = preferred.pricingPhases?.pricingPhaseList ?? [];
  const pricePhase = phases.find((phase) => (phase.priceAmountMicros ?? 0) > 0) ?? phases[0];
  const trialPhase = phases.find((phase) => (phase.priceAmountMicros ?? 0) === 0);

  if (!preferred.offerToken || !pricePhase) {
    return { error: `Offer data incomplete for ${basePlanId} plan` };
  }

  return {
    offerToken: preferred.offerToken,
    price: pricePhase?.formattedPrice || pricePhase?.price,
    period: pricePhase?.billingPeriod,
    trialPeriod: trialPhase?.billingPeriod,
    offerId: preferred.offerId,
  };
};

export default function SubscriptionScreen() {
  const { user, refreshUser, isAuthenticated } = useAuth();
  useLocalSearchParams<{ canceled?: string }>();
  const billing = useBilling();

  const product = billing.products[0];
  const monthlyOffer = useMemo(() => selectOfferForBasePlan(product, 'monthly'), [product]);
  const annualOffer = useMemo(() => selectOfferForBasePlan(product, 'annual'), [product]);

  useEffect(() => {
    if (!product) {
      console.log('[billing] no product loaded');
      return;
    }
    console.log('[billing] render product', {
      productId: product.productId,
      offers: product.subscriptionOfferDetails?.map((o) => ({
        basePlanId: o.basePlanId,
        offerId: o.offerId,
        offerToken: o.offerToken,
        pricing: o.pricingPhases?.pricingPhaseList?.map((ph) => ({ price: ph.formattedPrice, billingPeriod: ph.billingPeriod })),
      })),
      monthlyOffer,
      annualOffer,
    });
  }, [product, monthlyOffer, annualOffer]);

  useEffect(() => {
    if (isWeb) {
      router.replace('/landing');
    }
  }, []);

  const openGooglePlay = () => Linking.openURL(GOOGLE_PLAY_URL);

  const handlePurchase = async (offerToken?: string) => {
    await billing.purchase(offerToken);

    // If the user is already signed in, sync their server profile; otherwise prompt to link/create after purchase.
    if (isAuthenticated) {
      await refreshUser();
    } else {
      router.replace('/signup?postPurchase=1');
    }
  };

  const handleRestore = async () => {
    await billing.restore();
    await refreshUser();
  };

  const isPremium = user?.is_premium;
  const isTrialing = user?.subscription_status === 'trialing';

  if (billing.isLoading && !billing.error) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#eab308" />
      </View>
    );
  }

  if (billing.entitlementActive || (isPremium && !isTrialing)) {
    return (
      <View style={styles.container}>
        <SafeAreaView style={styles.safeArea}>
          <View style={styles.premiumContent}>
            <TouchableOpacity style={styles.backButton} onPress={() => router.back()}>
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
              style={[styles.manageButton, billing.isRestoring && styles.buttonDisabled]}
              onPress={handleRestore}
              disabled={billing.isRestoring}
            >
              {billing.isRestoring ? (
                <ActivityIndicator color="#eab308" size="small" />
              ) : (
                <>
                  <Ionicons name="settings-outline" size={20} color="#eab308" />
                  <Text style={styles.manageButtonText}>Restore Purchases</Text>
                </>
              )}
            </TouchableOpacity>

            <TouchableOpacity style={styles.continueButton} onPress={() => router.replace('/')}>
              <Text style={styles.continueButtonText}>Continue to App</Text>
            </TouchableOpacity>
          </View>
        </SafeAreaView>
      </View>
    );
  }

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

  return (
    <View style={styles.container}>
      <SafeAreaView style={styles.safeArea}>
        <ScrollView contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
          <TouchableOpacity style={styles.backButton} onPress={() => router.back()} data-testid="subscription-back-btn">
            <Ionicons name="arrow-back" size={24} color="#fff" />
          </TouchableOpacity>

          <View style={styles.header}>
            <View style={styles.iconContainer}>
              <Ionicons name="rocket" size={32} color="#1a1a1a" />
            </View>
            <Text style={styles.title}>Upgrade to Premium</Text>
            <Text style={styles.subtitle}>Unlock all features and drive with confidence</Text>
          </View>

          <Text style={styles.sectionTitle}>Choose Your Plan</Text>

          <View style={styles.plansContainer}>
            {[{ label: 'Monthly', basePlanId: 'monthly', offer: monthlyOffer }, { label: 'Annual', basePlanId: 'annual', offer: annualOffer }].map(
              ({ label, basePlanId, offer }) => {
                const price = offer?.price || '$—';
                const interval = offer?.period ? humanizePeriod(offer.period) : basePlanId === 'annual' ? 'year' : 'month';
                const trial = offer?.trialPeriod ? humanizePeriod(offer.trialPeriod) : null;
                const disabled = billing.isPurchasing || !offer?.offerToken || !!offer?.error;

                console.log('[billing] CTA render', {
                  basePlanId,
                  price,
                  interval,
                  trial,
                  offerToken: offer?.offerToken,
                });

                return (
                  <View key={basePlanId} style={styles.planCard} data-testid={`plan-${basePlanId}`}>
                    <View style={styles.planHeader}>
                      <Text style={styles.planName}>{label}</Text>
                      <View style={styles.planPriceContainer}>
                        <Text style={styles.planPrice}>{price}</Text>
                        <Text style={styles.planInterval}>/{interval}</Text>
                      </View>
                    </View>

                    {trial && (
                      <View style={styles.trialBannerInline}>
                        <Ionicons name="gift" size={18} color="#22c55e" />
                        <Text style={styles.trialBannerInlineText}>Free trial: {trial}</Text>
                      </View>
                    )}

                    <TouchableOpacity
                      style={[styles.planButton, disabled && styles.buttonDisabled]}
                      onPress={() => {
                        console.log('[billing] purchase tap', { basePlanId, offerToken: offer?.offerToken });
                        handlePurchase(offer?.offerToken);
                      }}
                      disabled={disabled}
                      data-testid={`purchase-${basePlanId}`}
                    >
                      {billing.isPurchasing ? (
                        <ActivityIndicator color="#1a1a1a" size="small" />
                      ) : (
                        <>
                          <Ionicons name="cart" size={18} color="#1a1a1a" />
                          <Text style={styles.planButtonText}>Purchase with Google Play</Text>
                        </>
                      )}
                    </TouchableOpacity>

                    {offer?.error && (
                      <View style={styles.errorContainer}>
                        <Ionicons name="alert-circle" size={18} color="#ef4444" />
                        <Text style={styles.errorText}>{offer.error}</Text>
                      </View>
                    )}

                    <TouchableOpacity
                      style={[styles.restoreButton, billing.isRestoring && styles.buttonDisabled]}
                      onPress={handleRestore}
                      disabled={billing.isRestoring}
                    >
                      {billing.isRestoring ? (
                        <ActivityIndicator color="#eab308" size="small" />
                      ) : (
                        <Text style={styles.restoreText}>Restore purchases</Text>
                      )}
                    </TouchableOpacity>
                  </View>
                );
              }
            )}
          </View>

          {billing.error && (
            <View style={styles.errorContainer}>
              <Ionicons name="alert-circle" size={18} color="#ef4444" />
              <Text style={styles.errorText}>{billing.error}</Text>
            </View>
          )}

          {!billing.error && !billing.products.length && !billing.isLoading && (
            <View style={styles.errorContainer}>
              <Ionicons name="alert-circle" size={18} color="#ef4444" />
              <Text style={styles.errorText}>
                Unable to load Google Play products. Please ensure Play Store is available and try again.
              </Text>
            </View>
          )}

          <TouchableOpacity
            style={[styles.loginLinkContainer, billing.isPurchasing && styles.buttonDisabled]}
            onPress={() => router.push('/login')}
            disabled={billing.isPurchasing}
          >
            <Text style={styles.loginLinkText}>Already subscribed? Sign in to link</Text>
          </TouchableOpacity>

          <Text style={styles.termsText}>
            Billing handled securely via Google Play. Subscriptions auto-renew unless canceled.
          </Text>
        </ScrollView>
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0f0f0f' },
  loadingContainer: { flex: 1, backgroundColor: '#0f0f0f', justifyContent: 'center', alignItems: 'center' },
  safeArea: { flex: 1 },
  scrollContent: { padding: 20, paddingTop: 12 },
  backButton: {
    width: 44,
    height: 44,
    borderRadius: 12,
    backgroundColor: '#27272a',
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 24,
  },
  webContainer: { flex: 1, backgroundColor: '#0f0f0f' },
  webContent: { flex: 1, padding: 24, gap: 16, maxWidth: 520, marginHorizontal: 'auto', justifyContent: 'center' },
  webTitle: { color: '#ffffff', fontSize: 28, fontWeight: '800', textAlign: 'center' },
  webSubtitle: { color: '#a1a1aa', fontSize: 16, textAlign: 'center', lineHeight: 24 },
  webCta: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 12,
    backgroundColor: '#eab308',
    paddingVertical: 14,
    borderRadius: 14,
  },
  webCtaText: { color: '#0f0f0f', fontWeight: '700', fontSize: 16 },
  webSecondary: { flexDirection: 'row', alignItems: 'center', gap: 8, justifyContent: 'center' },
  webSecondaryText: { color: '#eab308', fontSize: 15 },
  header: { gap: 8, marginBottom: 18 },
  iconContainer: {
    width: 56,
    height: 56,
    borderRadius: 16,
    backgroundColor: '#eab308',
    alignItems: 'center',
    justifyContent: 'center',
  },
  title: { color: '#fff', fontSize: 26, fontWeight: '800' },
  subtitle: { color: '#a1a1aa', fontSize: 16, lineHeight: 22 },
  sectionTitle: { color: '#fff', fontSize: 18, fontWeight: '700', marginBottom: 12, marginTop: 8 },
  plansContainer: { gap: 16 },
  planCard: {
    backgroundColor: '#18181b',
    borderRadius: 18,
    padding: 16,
    borderWidth: 1,
    borderColor: '#27272a',
    gap: 12,
  },
  planHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  planName: { color: '#fff', fontSize: 18, fontWeight: '700' },
  planPriceContainer: { flexDirection: 'row', alignItems: 'flex-end', gap: 4 },
  planPrice: { color: '#fff', fontSize: 22, fontWeight: '800' },
  planInterval: { color: '#a1a1aa', fontSize: 14 },
  trialBannerInline: { flexDirection: 'row', alignItems: 'center', gap: 8, padding: 10, backgroundColor: '#122b19', borderRadius: 12 },
  trialBannerInlineText: { color: '#c3e7d4', fontSize: 14 },
  planButton: {
    backgroundColor: '#eab308',
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: 'center',
    flexDirection: 'row',
    justifyContent: 'center',
    gap: 8,
  },
  planButtonText: { color: '#0f0f0f', fontWeight: '700' },
  restoreButton: {
    marginTop: 8,
    alignItems: 'center',
    paddingVertical: 10,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#3f3f46',
  },
  restoreText: { color: '#eab308', fontWeight: '600' },
  errorContainer: {
    marginTop: 16,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    backgroundColor: '#2f1212',
    borderRadius: 12,
    padding: 12,
  },
  errorText: { color: '#fca5a5' },
  loginLinkContainer: {
    marginTop: 12,
    alignItems: 'center',
    paddingVertical: 10,
  },
  loginLinkText: { color: '#eab308', fontWeight: '700' },
  termsText: { color: '#71717a', fontSize: 12, marginTop: 16, lineHeight: 18 },
  premiumContent: { flex: 1, padding: 20, gap: 20 },
  premiumIconContainer: {
    width: 84,
    height: 84,
    borderRadius: 24,
    backgroundColor: '#1f1f22',
    justifyContent: 'center',
    alignItems: 'center',
    alignSelf: 'center',
  },
  premiumTitle: { color: '#fff', fontSize: 24, fontWeight: '800', textAlign: 'center' },
  premiumSubtitle: { color: '#a1a1aa', fontSize: 16, textAlign: 'center' },
  premiumInfoBox: { backgroundColor: '#18181b', borderRadius: 16, padding: 16, gap: 10, borderWidth: 1, borderColor: '#27272a' },
  premiumInfoRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  premiumInfoText: { color: '#e4e4e7', fontSize: 15 },
  manageButton: {
    borderRadius: 12,
    paddingVertical: 14,
    borderWidth: 1,
    borderColor: '#3f3f46',
    alignItems: 'center',
    gap: 8,
    flexDirection: 'row',
    justifyContent: 'center',
  },
  manageButtonText: { color: '#eab308', fontWeight: '700', fontSize: 16 },
  continueButton: {
    backgroundColor: '#eab308',
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: 'center',
  },
  continueButtonText: { color: '#0f0f0f', fontWeight: '700', fontSize: 16 },
  buttonDisabled: { opacity: 0.6 },
});
