import React, { useEffect, useMemo, useState } from 'react';
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
import { buildUrl } from './apiConfig';

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

const formatTrialPeriod = (period?: string) => {
  if (!period) return '';
  // Play often returns P1W for a 7-day trial; show explicit 7-day copy.
  if (period === 'P1W' || period === 'P7D') return '7-day';
  return humanizePeriod(period);
};

const selectOfferForBasePlan = (product: IAP.Subscription | undefined, basePlanId: string): OfferInfo | null => {
  const offerDetails = (product as any)?.subscriptionOfferDetailsAndroid ?? (product as any)?.subscriptionOfferDetails;
  if (!offerDetails?.length) return { error: 'Billing unavailable for this plan' };

  const offers = offerDetails.filter((offer: any) => offer.basePlanId === basePlanId);
  if (!offers.length) return { error: `No offers found for ${basePlanId} plan` };

  // Enforce base-plan specific offer preference rules
  const filtered = basePlanId === 'annual' ? offers.filter((offer) => offer.offerId !== 'trial7d') : offers;
  if (!filtered.length) {
    return { error: basePlanId === 'annual' ? 'Annual plan unavailable right now' : `No valid offers for ${basePlanId}` };
  }

  const preferred = basePlanId === 'monthly'
    ? filtered.find((offer) => offer.offerId === 'trial7d') ?? filtered[0]
    : filtered[0];

  const pricingPhases = preferred.pricingPhases?.pricingPhaseList ?? [];
  const recurringPhase = pricingPhases[pricingPhases.length - 1];
  const trialPhase = pricingPhases.find((phase: any) => Number(phase.priceAmountMicros ?? 0) === 0);

  if (!preferred.offerToken || !recurringPhase) {
    return { error: `Offer data incomplete for ${basePlanId} plan` };
  }

  return {
    offerToken: preferred.offerToken,
    price: recurringPhase.formattedPrice,
    period: recurringPhase.billingPeriod,
    trialPeriod: trialPhase?.billingPeriod,
    offerId: preferred.offerId,
  };
};

export default function SubscriptionScreen() {
  const { user, refreshUser, isAuthenticated, accessToken } = useAuth();
  useLocalSearchParams<{ canceled?: string }>();
  const billing = useBilling();
  const [verifyLoading, setVerifyLoading] = useState(false);
  const [verifyError, setVerifyError] = useState<string | null>(null);

  const product = billing.products[0];
  const monthlyOffer = useMemo(() => selectOfferForBasePlan(product, 'monthly'), [product]);
  const annualOffer = useMemo(() => selectOfferForBasePlan(product, 'annual'), [product]);
  const [selectedPlan, setSelectedPlan] = useState<'monthly' | 'annual'>('monthly');
  const selectedOffer = selectedPlan === 'monthly' ? monthlyOffer : annualOffer;
  const mainCtaText = selectedPlan === 'monthly' ? 'Start Subscription (7-Day Trial Included)' : 'Subscribe Annually';
  const helperText = selectedPlan === 'monthly' ? 'Then $9.99/month unless canceled' : null;

  useEffect(() => {
    if (!product) {
      console.log('[billing] no product loaded');
      return;
    }
    const productId = product.id ?? (product as any).productId;
    const offers = (product as any).subscriptionOfferDetailsAndroid?.map((o: any) => ({
      basePlanId: o.basePlanId,
      offerId: o.offerId,
      offerToken: o.offerToken,
      pricing: o.pricingPhases?.pricingPhaseList?.map((ph) => ({ price: ph.formattedPrice, billingPeriod: ph.billingPeriod })),
    }));
    console.log('[billing] render product', { productId, offers, monthlyOffer, annualOffer });
  }, [product, monthlyOffer, annualOffer]);

  useEffect(() => {
    if (isWeb) {
      router.replace('/landing');
    }
  }, []);

  const openGooglePlay = () => Linking.openURL(GOOGLE_PLAY_URL);

  const verifyGooglePurchase = async (payload: { purchaseToken: string; productId: string; packageName: string }) => {
    if (!accessToken) {
      throw new Error('Sign in is required before starting a trial/subscription.');
    }

    const response = await fetch(buildUrl('subscription/verify/google'), {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${accessToken}`,
      },
      body: JSON.stringify({
        purchase_token: payload.purchaseToken,
        product_id: payload.productId,
        package_name: payload.packageName,
      }),
    });

    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(body?.detail || 'Google Play verification failed');
    }

    if (!body?.valid) {
      throw new Error(body?.message || 'Google Play entitlement is not active.');
    }
  };

  const verifyAllActiveGooglePurchases = async () => {
    if (!accessToken) {
      throw new Error('Sign in is required to restore purchases.');
    }

    const active = await IAP.getAvailablePurchases();
    const candidates = (active ?? []).filter((p: any) => {
      const pid = p.productId ?? p.sku ?? p.id;
      return pid === 'routecast_vs1';
    });

    if (!candidates.length) {
      throw new Error('No active Google Play purchases found to restore.');
    }

    let atLeastOneVerified = false;
    for (const p of candidates) {
      const purchaseToken = (p as any)?.purchaseToken ?? (p as any)?.purchaseTokenAndroid;
      const productId = (p as any)?.productId ?? (p as any)?.sku ?? (p as any)?.id ?? 'routecast_vs1';
      if (!purchaseToken) continue;
      await verifyGooglePurchase({
        purchaseToken,
        productId,
        packageName: 'com.routecast.app',
      });
      atLeastOneVerified = true;
    }

    if (!atLeastOneVerified) {
      throw new Error('No valid purchase token found for restore verification.');
    }
  };

  const handlePurchase = async (basePlanId: string, offerToken?: string) => {
    const productId = product?.id ?? (product as any)?.productId;
    console.log('[billing] CTA payload', { productId, basePlanId, offerToken });
    setVerifyError(null);

    const receipt = await billing.purchase(offerToken);
    if (!receipt) {
      return;
    }

    setVerifyLoading(true);
    try {
      await verifyGooglePurchase(receipt);
      await refreshUser();
      router.replace('/account');
    } catch (err: any) {
      setVerifyError(err?.message ?? 'Unable to verify purchase with backend');
    } finally {
      setVerifyLoading(false);
    }

    if (!isAuthenticated) {
      router.replace('/signup?postPurchase=1');
    }
  };

  const handleRestore = async () => {
    setVerifyError(null);
    setVerifyLoading(true);
    try {
      await billing.restore();
      await verifyAllActiveGooglePurchases();
      await refreshUser();
      router.replace('/account');
    } catch (err: any) {
      setVerifyError(err?.message ?? 'Unable to restore entitlement from backend');
    } finally {
      setVerifyLoading(false);
    }
  };

  const isPremium = Boolean(user?.is_premium);
  const isTrialing = user?.subscription_status === 'trialing';
  const hasServerEntitlement = Boolean(isPremium && user?.email_verified);
  const purchaseDetectedPendingSync = billing.entitlementActive && !hasServerEntitlement;

  if (billing.isLoading && !billing.error) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#eab308" />
      </View>
    );
  }

  if (hasServerEntitlement) {
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

            <Text style={styles.premiumTitle}>{isTrialing ? 'Trial Active' : 'Subscription Active'}</Text>
            <Text style={styles.premiumSubtitle}>
              You have full access to all RouteCast features
            </Text>

            <View style={styles.premiumInfoBox}>
              <View style={styles.premiumInfoRow}>
                <Ionicons name="calendar" size={20} color="#a1a1aa" />
                <Text style={styles.premiumInfoText}>
                  Plan: {user?.subscription_plan?.charAt(0).toUpperCase() + user?.subscription_plan?.slice(1)}
                </Text>
              </View>
              {isTrialing && (
                <View style={styles.premiumInfoRow}>
                  <Ionicons name="hourglass-outline" size={20} color="#a1a1aa" />
                  <Text style={styles.premiumInfoText}>Status: Trial Active</Text>
                </View>
              )}
              {user?.subscription_expiration && (
                <View style={styles.premiumInfoRow}>
                  <Ionicons name="time" size={20} color="#a1a1aa" />
                  <Text style={styles.premiumInfoText}>
                    {isTrialing ? 'Trial Ends' : 'Renews'}: {new Date(user.subscription_expiration).toLocaleDateString()}
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
            <Text style={styles.title}>Continue Full Access</Text>
            <Text style={styles.subtitle}>Every signup gets 7 days of full access. Subscribe to keep access after day 7.</Text>
          </View>

          <Text style={styles.sectionTitle}>Choose Your Plan</Text>

          <View style={styles.plansContainer}>
            {[
              { label: 'Monthly', basePlanId: 'monthly', offer: monthlyOffer, subtitle: 'Keeps access after your included 7-day full-access period', badge: 'Recommended' },
              { label: 'Annual', basePlanId: 'annual', offer: annualOffer, subtitle: '$59.99/year' },
            ].map(({ label, basePlanId, offer, subtitle, badge }) => {
              const price = offer?.price ?? (basePlanId === 'annual' ? '$59.99' : '$9.99');
              const interval = basePlanId === 'annual' ? 'year' : 'month';
              const selected = selectedPlan === basePlanId;

              return (
                <TouchableOpacity
                  key={basePlanId}
                  style={[styles.planCard, selected && styles.planCardSelected]}
                  onPress={() => setSelectedPlan(basePlanId as 'monthly' | 'annual')}
                  activeOpacity={0.9}
                  data-testid={`plan-${basePlanId}`}
                >
                  <View style={styles.planHeader}>
                    <View style={styles.planNameRow}>
                      <Text style={styles.planName}>{label}</Text>
                      {badge && basePlanId === 'monthly' && <View style={styles.planBadge}><Text style={styles.planBadgeText}>{badge}</Text></View>}
                    </View>
                    <View style={styles.planPriceContainer}>
                      <Text style={styles.planPrice}>{price}</Text>
                      <Text style={styles.planInterval}>/{interval}</Text>
                    </View>
                  </View>

                  <Text style={styles.planSubtitle}>{subtitle}</Text>

                  <View style={styles.planSelectRow}>
                    <View style={[styles.radioOuter, selected && styles.radioOuterSelected]}>
                      {selected && <View style={styles.radioInner} />}
                    </View>
                    <Text style={styles.radioLabel}>{selected ? 'Selected' : 'Tap to select'}</Text>
                  </View>

                  {offer?.error && (
                    <View style={styles.errorContainer}>
                      <Ionicons name="alert-circle" size={18} color="#ef4444" />
                      <Text style={styles.errorText}>{offer.error}</Text>
                    </View>
                  )}
                </TouchableOpacity>
              );
            })}
          </View>

          <TouchableOpacity
            style={[styles.planButton, (!selectedOffer?.offerToken || !!selectedOffer?.error || billing.isPurchasing || verifyLoading) && styles.buttonDisabled, styles.mainCta]}
            onPress={() => handlePurchase(selectedPlan, selectedOffer?.offerToken)}
            disabled={billing.isPurchasing || verifyLoading || !selectedOffer?.offerToken || !!selectedOffer?.error}
            data-testid="purchase-selected"
          >
            {(billing.isPurchasing || verifyLoading) ? (
              <ActivityIndicator color="#1a1a1a" size="small" />
            ) : (
              <>
                <Ionicons name="cart" size={18} color="#1a1a1a" />
                <Text style={styles.planButtonText}>{mainCtaText}</Text>
              </>
            )}
          </TouchableOpacity>

          {helperText && <Text style={styles.ctaHelper}>{helperText}</Text>}

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

          {billing.error && (
            <View style={styles.errorContainer}>
              <Ionicons name="alert-circle" size={18} color="#ef4444" />
              <Text style={styles.errorText}>{billing.error}</Text>
            </View>
          )}

          {verifyError && (
            <View style={styles.errorContainer}>
              <Ionicons name="alert-circle" size={18} color="#ef4444" />
              <Text style={styles.errorText}>{verifyError}</Text>
            </View>
          )}

          {purchaseDetectedPendingSync && (
            <View style={styles.errorContainer}>
              <Ionicons name="information-circle" size={18} color="#eab308" />
              <Text style={styles.errorText}>
                Purchase detected on device. Access unlocks only after account entitlement sync completes.
              </Text>
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
  planNameRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  planName: { color: '#fff', fontSize: 18, fontWeight: '700' },
  planPriceContainer: { flexDirection: 'row', alignItems: 'flex-end', gap: 4 },
  planPrice: { color: '#fff', fontSize: 22, fontWeight: '800' },
  planInterval: { color: '#a1a1aa', fontSize: 14 },
  planSubtitle: { color: '#d4d4d8', fontSize: 14, lineHeight: 20 },
  planSelectRow: { flexDirection: 'row', alignItems: 'center', gap: 10, marginTop: 10 },
  planBadge: { backgroundColor: '#eab308', borderRadius: 10, paddingHorizontal: 10, paddingVertical: 4 },
  planBadgeText: { color: '#0f0f0f', fontWeight: '800', fontSize: 12 },
  planCardSelected: { borderColor: '#eab308', shadowColor: '#eab308', shadowOpacity: 0.25, shadowRadius: 8, shadowOffset: { width: 0, height: 4 } },
  radioOuter: { width: 20, height: 20, borderRadius: 10, borderWidth: 2, borderColor: '#3f3f46', alignItems: 'center', justifyContent: 'center' },
  radioOuterSelected: { borderColor: '#eab308' },
  radioInner: { width: 10, height: 10, borderRadius: 5, backgroundColor: '#eab308' },
  radioLabel: { color: '#e4e4e7', fontWeight: '600' },
  planButton: {
    backgroundColor: '#eab308',
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: 'center',
    flexDirection: 'row',
    justifyContent: 'center',
    gap: 8,
  },
  mainCta: { marginTop: 12 },
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
  ctaHelper: { color: '#d4d4d8', marginTop: 8, textAlign: 'center', fontSize: 13 },
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
