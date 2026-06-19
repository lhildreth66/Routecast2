import React, { useEffect, useMemo, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ActivityIndicator,
  ScrollView,
  Platform,
  Linking,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { router, useLocalSearchParams } from 'expo-router';
import * as IAP from 'expo-iap';
import { useAuth } from '../contexts/AuthContext';
import { useBilling } from './hooks/useBilling';
import { buildUrl } from './apiConfig';
import { runPostPurchaseFlow } from './utils/postPurchaseFlow';
import { savePendingPurchase } from './utils/pendingPurchase';



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

// Returns the localized price from an iOS StoreKit product.
// expo-iap's ProductSubscriptionIOS exposes `displayPrice` (typed).
// Some runtime versions also set `localizedPrice` for RN IAP compatibility.
// We check both; never use hardcoded fallbacks — show an error instead.
const getIosProductPrice = (product: any): string | undefined =>
  product?.displayPrice || product?.localizedPrice || undefined;

const selectOfferForBasePlan = (product: any, basePlanId: string): OfferInfo | null => {
  const offerDetails = (product as any)?.subscriptionOfferDetailsAndroid ?? (product as any)?.subscriptionOfferDetails;
  if (!offerDetails?.length) return { error: 'Billing unavailable for this plan' };

  const offers = offerDetails.filter((offer: any) => offer.basePlanId === basePlanId);
  if (!offers.length) return { error: `No offers found for ${basePlanId} plan` };

  // Enforce base-plan specific offer preference rules
  const filtered = basePlanId === 'annual' ? offers.filter((offer: any) => offer.offerId !== 'trial7d') : offers;
  if (!filtered.length) {
    return { error: basePlanId === 'annual' ? 'Annual plan unavailable right now' : `No valid offers for ${basePlanId}` };
  }

  const preferred = basePlanId === 'monthly'
    ? filtered.find((offer: any) => offer.offerId === 'trial7d') ?? filtered[0]
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
  const [purchasePending, setPurchasePending] = useState(false);

  // Navigate only after React has committed user.is_premium = true.
  // Without this, router.replace('/') fires while user.is_premium is still
  // false in React state, causing PaywallGuard to immediately re-redirect
  // back to /subscription before the entitlement state is reflected.
  useEffect(() => {
    if (!purchasePending) return;
    const hasServerEntitlement = Boolean(user?.is_premium && user?.email_verified);
    if (!hasServerEntitlement) return;
    setPurchasePending(false);
    router.replace('/');
  }, [purchasePending, user?.is_premium, user?.email_verified]);

  // Safety timeout: if /auth/me never returns the updated entitlement,
  // unblock the UI after 10 seconds rather than leaving loading state stuck.
  useEffect(() => {
    if (!purchasePending) return;
    const t = setTimeout(() => {
      setPurchasePending(false);
      router.replace('/');
    }, 10000);
    return () => clearTimeout(t);
  }, [purchasePending]);

  // ── Android: single product with base plans ──────────────────────────────
  const product = billing.products[0];
  const monthlyOffer = useMemo(() => selectOfferForBasePlan(product, 'monthly'), [product]);
  const annualOffer  = useMemo(() => selectOfferForBasePlan(product, 'annual'),  [product]);

  // ── iOS: separate products per plan ──────────────────────────────────────
  const iosMonthlyProduct = useMemo(
    () => billing.products.find((p: any) => (p.id ?? p.productId) === 'routecast_monthly'),
    [billing.products],
  );
  const iosAnnualProduct = useMemo(
    () => billing.products.find((p: any) => (p.id ?? p.productId) === 'routecast_annual'),
    [billing.products],
  );
  type IosOfferInfo = { price?: string; error?: string };
  // No hardcoded price fallbacks. If the product loads but StoreKit returns no
  // price, show an error so the paywall cannot silently display wrong pricing.
  const iosMonthlyOffer: IosOfferInfo = iosMonthlyProduct
    ? (() => {
        const p = getIosProductPrice(iosMonthlyProduct);
        return p ? { price: p } : { error: 'App Store price unavailable — please restart the app' };
      })()
    : !billing.isLoading ? { error: 'App Store product unavailable' } : {};
  const iosAnnualOffer: IosOfferInfo = iosAnnualProduct
    ? (() => {
        const p = getIosProductPrice(iosAnnualProduct);
        return p ? { price: p } : { error: 'App Store price unavailable — please restart the app' };
      })()
    : !billing.isLoading ? { error: 'App Store product unavailable' } : {};

  // Trial subtitles — price derives from StoreKit, never hardcoded
  const iosMonthlyTrialSubtitle = `7-day free trial — then ${iosMonthlyOffer.price ?? '—'}/month`;
  const iosAnnualTrialSubtitle  = `7-day free trial — then ${iosAnnualOffer.price ?? '—'}/year · Best value`;

  // ── Unified UI values (platform-aware) ───────────────────────────────────
  const [selectedPlan, setSelectedPlan] = useState<'monthly' | 'annual'>('monthly');
  const selectedOffer = selectedPlan === 'monthly' ? monthlyOffer : annualOffer;
  const selectedIosOffer = selectedPlan === 'monthly' ? iosMonthlyOffer : iosAnnualOffer;

  // Both iOS plans include a 7-day free trial
  const mainCtaText = Platform.OS === 'ios'
    ? 'Start 7-Day Free Trial'
    : (selectedPlan === 'monthly' ? 'Start Subscription (7-Day Trial Included)' : 'Subscribe Annually');
  const helperText = Platform.OS === 'ios'
    ? (selectedPlan === 'monthly'
        ? `7-day free trial · then ${iosMonthlyOffer.price ?? '—'}/month · Cancel anytime`
        : `7-day free trial · then ${iosAnnualOffer.price ?? '—'}/year · Cancel anytime`)
    : (selectedPlan === 'monthly' ? 'Then $9.99/month unless canceled' : null);

  // iOS product field diagnostics — visible in Xcode console and EAS logs
  useEffect(() => {
    if (Platform.OS !== 'ios' || !billing.products.length) return;
    billing.products.forEach((p: any) => {
      console.log('[iOS IAP product]', JSON.stringify({
        id: p.id,
        title: p.title,
        displayPrice: p.displayPrice,
        localizedPrice: p.localizedPrice,
        price: p.price,
        currency: p.currency,
        subscriptionPeriodNumberIOS: p.subscriptionPeriodNumberIOS,
        subscriptionPeriodUnitIOS: p.subscriptionPeriodUnitIOS,
        introductoryPricePaymentModeIOS: p.introductoryPricePaymentModeIOS,
        introductoryPriceIOS: p.introductoryPriceIOS,
        introductoryPriceNumberOfPeriodsIOS: p.introductoryPriceNumberOfPeriodsIOS,
        introductoryPriceSubscriptionPeriodIOS: p.introductoryPriceSubscriptionPeriodIOS,
        subscriptionInfoIOS: p.subscriptionInfoIOS,
      }));
    });
  }, [billing.products]);

  useEffect(() => {
    if (!product) {
      console.log('[billing] no product loaded');
      return;
    }
    const productId = (product as any)?.id ?? (product as any)?.productId;
    const offers = (product as any).subscriptionOfferDetailsAndroid?.map((o: any) => ({
      basePlanId: o.basePlanId,
      offerId: o.offerId,
      offerToken: o.offerToken,
      pricing: o.pricingPhases?.pricingPhaseList?.map((ph: any) => ({ price: ph.formattedPrice, billingPeriod: ph.billingPeriod })),
    }));
    console.log('[billing] render product', { productId, offers, monthlyOffer, annualOffer });
  }, [product, monthlyOffer, annualOffer]);

  // ── Apple verification ───────────────────────────────────────────────────
  const verifyApplePurchase = async (payload: { receiptData?: string; productId: string }) => {
    if (!accessToken) {
      throw new Error('Sign in is required before starting a trial/subscription.');
    }
    const response = await fetch(buildUrl('subscription/verify/apple'), {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${accessToken}`,
      },
      body: JSON.stringify({
        receipt_data: payload.receiptData ?? '',
        product_id: payload.productId,
      }),
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(body?.detail || 'App Store verification failed');
    }
    if (!body?.valid) {
      throw new Error(body?.message || 'App Store entitlement is not active.');
    }
  };

  const verifyAllActiveApplePurchases = async () => {
    if (!accessToken) {
      throw new Error('Sign in is required to restore purchases.');
    }
    const active = await IAP.getAvailablePurchases();
    const iosSkus = ['routecast_monthly', 'routecast_annual'];
    const candidates = (active ?? []).filter((p: any) => {
      const pid = p.productId ?? p.sku ?? p.id;
      return iosSkus.includes(pid);
    });
    if (!candidates.length) {
      throw new Error('No active App Store purchases found to restore.');
    }
    for (const p of candidates) {
      const jws = (p as any)?.purchaseToken ?? '';
      const pid = (p as any)?.productId ?? (p as any)?.sku ?? (p as any)?.id ?? '';
      await verifyApplePurchase({ receiptData: jws, productId: pid });
    }
  };

  // ── Google verification ──────────────────────────────────────────────────
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

  // ── iOS purchase handler ─────────────────────────────────────────────────
  const handleIosPurchase = async (sku: string) => {
    const receipt = await billing.purchase(sku);
    if (!accessToken) {
      await savePendingPurchase(receipt);
      router.replace('/login');
      return;
    }
    setVerifyLoading(true);
    try {
      if (receipt) {
        await verifyApplePurchase({ receiptData: receipt.receiptData, productId: receipt.productId });
      } else {
        await verifyAllActiveApplePurchases();
      }
    } catch (err: any) {
      setVerifyError(err?.message ?? 'Unable to verify purchase. Tap "Restore Purchases" to try again.');
      setVerifyLoading(false);
      return;
    }
    try { await refreshUser(); } catch { /* non-fatal */ }
    setVerifyLoading(false);
    setPurchasePending(true);
  };

  // ── Unified purchase handler ─────────────────────────────────────────────
  const handlePurchase = async (basePlanId: string, offerToken?: string) => {
    setVerifyError(null);

    if (Platform.OS === 'ios') {
      const sku = basePlanId === 'monthly' ? 'routecast_monthly' : 'routecast_annual';
      console.log('[billing] iOS CTA', { sku });
      await handleIosPurchase(sku);
      return;
    }

    // ── Android path (unchanged) ────────────────────────────────────────────
    const productId = (product as any)?.id ?? (product as any)?.productId;
    console.log('[billing] CTA payload', { productId, basePlanId, offerToken });

    // billing.purchase() polls IAP.getAvailablePurchases() for the receipt token.
    // On Android the purchaseUpdatedListener can acknowledge (finish) the transaction
    // before the poll runs, causing getAvailablePurchases to return nothing for the
    // new purchase.  runPostPurchaseFlow falls through to the restore path in that
    // case, so the successful purchase is never silently dropped.
    const receipt = await billing.purchase(offerToken);

    // Google Play completed but the user is not authenticated.
    // Store the receipt so it can be verified immediately after login, then
    // take the user to the login screen (step 8 of the required flow).
    if (!accessToken) {
      await savePendingPurchase(receipt);
      router.replace('/login');
      return;
    }

    setVerifyLoading(true);
    const { error } = await runPostPurchaseFlow(receipt, {
      verifyWithReceipt: verifyGooglePurchase,
      verifyWithRestore: verifyAllActiveGooglePurchases,
      refreshUser,
      // Deferred navigation: set purchasePending=true instead of navigating
      // immediately. The purchasePending useEffect navigates only once
      // user.is_premium is confirmed in React state, preventing PaywallGuard
      // from evaluating stale entitlement on the pathname change.
      navigate: () => setPurchasePending(true),
    });
    setVerifyLoading(false);
    if (error) setVerifyError(error);
  };

  const handleRestore = async () => {
    setVerifyError(null);
    setVerifyLoading(true);

    if (Platform.OS === 'ios') {
      try {
        await billing.restore();
        await verifyAllActiveApplePurchases();
      } catch (err: any) {
        setVerifyError(err?.message ?? 'Restore failed');
        setVerifyLoading(false);
        return;
      }
      try { await refreshUser(); } catch { /* non-fatal */ }
      setVerifyLoading(false);
      setPurchasePending(true);
      return;
    }

    // Android restore path
    const { error } = await runPostPurchaseFlow(null, {
      verifyWithReceipt: verifyGooglePurchase,
      verifyWithRestore: async () => {
        await billing.restore();
        await verifyAllActiveGooglePurchases();
      },
      refreshUser,
      navigate: () => setPurchasePending(true),
    });
    setVerifyLoading(false);
    if (error) setVerifyError(error);
  };

  const isPremium = Boolean(user?.is_premium);
  const isTrialing = user?.subscription_status === 'trialing';
  const hasServerEntitlement = Boolean(isPremium && user?.email_verified);
  const purchaseDetectedPendingSync = billing.entitlementActive && !hasServerEntitlement;

  if (billing.isLoading && !billing.error) {
    return (
      <View style={styles.container}>
        <SafeAreaView style={styles.safeArea}>
          <View style={styles.loadingContainer}>
            <TouchableOpacity
              style={styles.loadingBackButton}
              onPress={() => router.back()}
              hitSlop={{ top: 12, bottom: 12, left: 12, right: 12 }}
            >
              <Ionicons name="arrow-back" size={24} color="#fff" />
            </TouchableOpacity>
            <ActivityIndicator size="large" color="#eab308" />
            <Text style={styles.loadingText}>Loading subscription info…</Text>
          </View>
        </SafeAreaView>
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
                  Plan: {((user?.subscription_plan ?? '') as string).charAt(0).toUpperCase() + ((user?.subscription_plan ?? '') as string).slice(1)}
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
            <Text style={styles.subtitle}>{Platform.OS === 'ios' ? 'Start a free 7-day trial, then choose your plan.' : 'Start a Google Play subscription to activate your included 7-day full-access trial.'}</Text>
          </View>

          <Text style={styles.sectionTitle}>Choose Your Plan</Text>

          {/* RouteCast Pro feature list */}
          {Platform.OS === 'ios' && (
            <View style={styles.featuresSection}>
              <Text style={styles.featuresSectionTitle}>Everything included in Pro</Text>
              {[
                'Route Weather Intelligence',
                'Push Weather Alerts',
                'Bridge Height & Truck Restriction Alerts',
                'Truck Parking Finder',
                'Boondocking & Free Camping Tools',
                'Campground & Overnight Parking',
                'Live Weather Radar',
                'Connectivity Forecast',
                'Solar Energy Forecast',
                'Water Budget Advisor',
                'Propane Usage Advisor',
              ].map((feature) => (
                <View key={feature} style={styles.featureRow}>
                  <Ionicons name="checkmark-circle" size={16} color="#22c55e" />
                  <Text style={styles.featureText}>{feature}</Text>
                </View>
              ))}
              <View style={styles.featuresTrialBanner}>
                <Ionicons name="gift-outline" size={16} color="#eab308" />
                <Text style={styles.featuresTrialNote}>All features unlocked free for 7 days</Text>
              </View>
            </View>
          )}

          <View style={styles.plansContainer}>
            {[
              { label: 'Monthly', basePlanId: 'monthly', offer: Platform.OS === 'ios' ? iosMonthlyOffer : monthlyOffer, subtitle: Platform.OS === 'ios' ? iosMonthlyTrialSubtitle : 'Keeps access after your included 7-day full-access period', badge: 'Recommended' },
              { label: 'Annual', basePlanId: 'annual', offer: Platform.OS === 'ios' ? iosAnnualOffer : annualOffer, subtitle: Platform.OS === 'ios' ? iosAnnualTrialSubtitle : '$59.99/year' },
            ].map(({ label, basePlanId, offer, subtitle, badge }) => {
              const price = offer?.price ?? '—';
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
                  {Platform.OS === 'ios' && (
                    <Text style={styles.planSubscriptionTitle}>
                      {basePlanId === 'monthly' ? 'RouteCast Premium Monthly' : 'RouteCast Premium Annual'}
                    </Text>
                  )}
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
            style={[styles.planButton, (billing.isPurchasing || verifyLoading || (Platform.OS === 'android' && !selectedOffer?.offerToken) || !!(Platform.OS === 'ios' ? selectedIosOffer?.error : selectedOffer?.error)) && styles.buttonDisabled, styles.mainCta]}
            onPress={() => handlePurchase(selectedPlan, selectedOffer?.offerToken)}
            disabled={billing.isPurchasing || verifyLoading || (Platform.OS === 'android' && !selectedOffer?.offerToken) || !!(Platform.OS === 'ios' ? selectedIosOffer?.error : selectedOffer?.error)}
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
            style={[styles.restoreButton, (billing.isRestoring || verifyLoading) && styles.buttonDisabled]}
            onPress={handleRestore}
            disabled={billing.isRestoring || verifyLoading}
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
                {Platform.OS === 'ios'
                  ? 'Unable to load App Store products. Please ensure you are signed in to the App Store and try again.'
                  : 'Unable to load Google Play products. Please ensure Play Store is available and try again.'}
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
            {Platform.OS === 'ios'
              ? 'Billing handled securely via the App Store. Subscriptions auto-renew unless canceled at least 24 hours before the end of the current period.'
              : 'Billing handled securely via Google Play. Subscriptions auto-renew unless canceled.'}
          </Text>

          <View style={styles.legalLinks}>
            <TouchableOpacity onPress={() => Linking.openURL('https://routecastweather.com/privacy')}>
              <Text style={styles.legalLinkText}>Privacy Policy</Text>
            </TouchableOpacity>
            <Text style={styles.legalSeparator}> · </Text>
            <TouchableOpacity onPress={() => Linking.openURL('https://www.apple.com/legal/internet-services/itunes/dev/stdeula/')}>
              <Text style={styles.legalLinkText}>Terms of Use</Text>
            </TouchableOpacity>
          </View>
        </ScrollView>
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0f0f0f' },
  loadingContainer: { flex: 1, backgroundColor: '#0f0f0f', justifyContent: 'center', alignItems: 'center', gap: 16, padding: 20 },
  loadingBackButton: {
    position: 'absolute',
    top: 16,
    left: 20,
    width: 44,
    height: 44,
    borderRadius: 12,
    backgroundColor: '#27272a',
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingText: { color: '#a1a1aa', fontSize: 14 },
  safeArea: { flex: 1 },
  scrollContent: { padding: 20, paddingTop: 12, paddingBottom: 48 },
  backButton: {
    width: 44,
    height: 44,
    borderRadius: 12,
    backgroundColor: '#27272a',
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 24,
  },
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
  // Feature list (iOS paywall)
  featuresSection: {
    backgroundColor: '#1c1917',
    borderRadius: 14,
    padding: 16,
    marginBottom: 18,
    borderWidth: 1,
    borderColor: '#22c55e30',
  },
  featuresSectionTitle: {
    color: '#a1a1aa',
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 0.8,
    textTransform: 'uppercase',
    marginBottom: 12,
  },
  featureRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    paddingVertical: 5,
  },
  featureText: {
    color: '#e4e4e7',
    fontSize: 13,
    fontWeight: '500',
    flex: 1,
  },
  featuresTrialBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginTop: 12,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: '#3f3f46',
  },
  featuresTrialNote: {
    color: '#eab308',
    fontSize: 13,
    fontWeight: '600',
  },
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
  planSubscriptionTitle: {
    color: '#a1a1aa',
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 0.8,
    textTransform: 'uppercase',
    marginBottom: 2,
  },
  legalLinks: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    marginTop: 10,
    marginBottom: 8,
    flexWrap: 'wrap',
  },
  legalLinkText: {
    color: '#a1a1aa',
    fontSize: 12,
    textDecorationLine: 'underline',
    paddingVertical: 6,
    paddingHorizontal: 4,
  },
  legalSeparator: {
    color: '#52525b',
    fontSize: 12,
  },
});
