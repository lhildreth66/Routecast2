/**
 * Enhanced Paywall Screen
 * 
 * Premium subscription modal with soft/hard gate support.
 * Shows value props, pricing, and purchase options.
 */

import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ActivityIndicator,
  ScrollView,
  Modal,
  Linking,
  Platform,
} from 'react-native';
import type { Subscription } from 'react-native-iap';
import { iapClient } from './iapClient';
import type { ProductId, PremiumFeature } from './types';
import type { GateMode } from './gateTracking';
import { trackEvent } from '../utils/analytics';

interface PaywallScreenProps {
  visible: boolean;
  feature?: PremiumFeature;
  gateMode?: GateMode;
  onClose: () => void;
  onPurchaseComplete?: () => void;
}

export function PaywallScreen({
  visible,
  feature,
  gateMode = 'soft',
  onClose,
  onPurchaseComplete,
}: PaywallScreenProps) {
  const [products, setProducts] = useState<Subscription[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedProduct, setSelectedProduct] = useState<ProductId>('boondocking_pro_yearly');

  const canDismiss = gateMode === 'soft';

  useEffect(() => {
    if (visible) {
      loadProducts();
      
      // Track paywall viewed
      trackEvent('paywall_viewed', {
        feature,
        source: gateMode === 'hard' ? 'hard_gate' : 'soft_gate',
        screen: feature || 'unknown',
      });
    }
  }, [visible, feature, gateMode]);

  const loadProducts = async () => {
    try {
      setLoading(true);
      setError(null);
      const fetchedProducts = await iapClient.fetchProducts();
      setProducts(fetchedProducts);
    } catch (err) {
      console.error('[Paywall] Failed to load products:', err);
      setError('Failed to load products. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handlePurchase = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const result = await iapClient.purchase(selectedProduct);
      
      if (result.success) {
        console.log('[Paywall] Purchase successful:', selectedProduct);
        
        // Track purchase success
        const product = products.find(p => p.productId === selectedProduct);
        const planType = selectedProduct.includes('yearly') ? 'yearly' : 'monthly';
        
        trackEvent('purchase_success', {
          productId: selectedProduct,
          planType,
          price: product?.localizedPrice,
        });
        
        // Note: If this is a trial, we should also track trial_started
        // Trial detection requires checking transaction.introductoryPricePaymentModeIOS
        // or transaction.isTrialPeriod from the purchase receipt
        // For now, treating all new subscriptions as potential trials
        trackEvent('trial_started', {
          planType,
          platform: Platform.OS === 'ios' ? 'ios' : 'android',
        });
        
        onPurchaseComplete?.();
        onClose();
      } else {
        setError(result.error || 'Purchase failed. Please try again.');
      }
    } catch (err) {
      console.error('[Paywall] Purchase error:', err);
      setError(err instanceof Error ? err.message : 'Purchase failed');
    } finally {
      setLoading(false);
    }
  };

  const handleRestore = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const purchases = await iapClient.restorePurchases();
      
      if (purchases.length > 0) {
        console.log('[Paywall] Purchases restored');
        onPurchaseComplete?.();
        onClose();
      } else {
        setError('No previous purchases found');
      }
    } catch (err) {
      console.error('[Paywall] Restore error:', err);
      setError('Failed to restore purchases');
    } finally {
      setLoading(false);
    }
  };

  const handleDismiss = () => {
    if (canDismiss) {
      onClose();
    }
  };

  const openTerms = () => {
    Linking.openURL('https://routecast.app/terms');
  };

  const openPrivacy = () => {
    Linking.openURL('https://routecast.app/privacy');
  };

  const getProductPrice = (productId: ProductId): string => {
    const product = products.find(p => p.productId === productId);
    return product?.localizedPrice || '...';
  };

  return (
    <Modal
      visible={visible}
      animationType="slide"
      presentationStyle="pageSheet"
      onRequestClose={handleDismiss}
    >
      <View style={styles.container}>
        <ScrollView contentContainerStyle={styles.scrollContent}>
          {/* Header */}
          <View style={styles.header}>
            <Text style={styles.title}>Boondocking Pro</Text>
            <Text style={styles.subtitle}>
              Advanced planning tools for off-grid camping
            </Text>
          </View>

          {/* Value Props */}
          <View style={styles.features}>
            <FeatureItem
              icon="🚙"
              title="Road Passability"
              description="Simulate road conditions based on weather and terrain"
            />
            <FeatureItem
              icon="📡"
              title="Connectivity Prediction"
              description="Cell signal and Starlink obstruction analysis"
            />
            <FeatureItem
              icon="⚡"
              title="Power & Battery Planning"
              description="Solar forecast and battery state-of-charge modeling"
            />
            <FeatureItem
              icon="🔥"
              title="Propane & Water Budget"
              description="Plan your off-grid resources with precision"
            />
            <FeatureItem
              icon="⭐"
              title="Campsite Quality Score"
              description="Multi-factor suitability index for any location"
            />
            <FeatureItem
              icon="📋"
              title="Claim Logs"
              description="Export detailed incident reports (JSON + PDF)"
            />
          </View>

          {/* Plan Selector */}
          <View style={styles.planSelector}>
            <TouchableOpacity
              style={[
                styles.planOption,
                selectedProduct === 'boondocking_pro_yearly' && styles.planOptionSelected,
              ]}
              onPress={() => setSelectedProduct('boondocking_pro_yearly')}
              disabled={loading}
            >
              <View style={styles.badge}>
                <Text style={styles.badgeText}>BEST VALUE</Text>
              </View>
              <Text style={styles.planTitle}>Yearly</Text>
              <Text style={styles.planPrice}>
                {getProductPrice('boondocking_pro_yearly')}
              </Text>
              <Text style={styles.planPeriod}>per year</Text>
              <Text style={styles.planSavings}>Save 50%</Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={[
                styles.planOption,
                selectedProduct === 'boondocking_pro_monthly' && styles.planOptionSelected,
              ]}
              onPress={() => setSelectedProduct('boondocking_pro_monthly')}
              disabled={loading}
            >
              <Text style={styles.planTitle}>Monthly</Text>
              <Text style={styles.planPrice}>
                {getProductPrice('boondocking_pro_monthly')}
              </Text>
              <Text style={styles.planPeriod}>per month</Text>
            </TouchableOpacity>
          </View>

          {/* Trial/Cancel Text */}
          <View style={styles.trialInfo}>
            <Text style={styles.trialText}>Cancel anytime. No commitments.</Text>
          </View>

          {/* Error Display */}
          {error && (
            <View style={styles.errorBox}>
              <Text style={styles.errorText}>{error}</Text>
            </View>
          )}

          {/* CTA Button */}
          <TouchableOpacity
            style={[styles.ctaButton, loading && styles.ctaButtonDisabled]}
            onPress={handlePurchase}
            disabled={loading}
          >
            {loading ? (
              <ActivityIndicator size="small" color="#fff" />
            ) : (
              <Text style={styles.ctaButtonText}>Start Boondocking Pro</Text>
            )}
          </TouchableOpacity>

          {/* Restore Purchases */}
          <TouchableOpacity
            style={styles.restoreButton}
            onPress={handleRestore}
            disabled={loading}
          >
            <Text style={styles.restoreText}>Restore Purchases</Text>
          </TouchableOpacity>

          {/* Dismiss Button (only for soft gate) */}
          {canDismiss && (
            <TouchableOpacity style={styles.dismissButton} onPress={handleDismiss}>
              <Text style={styles.dismissText}>Not Now</Text>
            </TouchableOpacity>
          )}

          {/* Hard Gate Message */}
          {!canDismiss && (
            <View style={styles.hardGateMessage}>
              <Text style={styles.hardGateText}>
                Premium features require an active subscription
              </Text>
            </View>
          )}

          {/* Legal Links */}
          <View style={styles.legalLinks}>
            <TouchableOpacity onPress={openTerms}>
              <Text style={styles.legalLink}>Terms of Service</Text>
            </TouchableOpacity>
            <Text style={styles.legalSeparator}> • </Text>
            <TouchableOpacity onPress={openPrivacy}>
              <Text style={styles.legalLink}>Privacy Policy</Text>
            </TouchableOpacity>
          </View>
        </ScrollView>
      </View>
    </Modal>
  );
}

interface FeatureItemProps {
  icon: string;
  title: string;
  description: string;
}

function FeatureItem({ icon, title, description }: FeatureItemProps) {
  return (
    <View style={styles.featureItem}>
      <Text style={styles.featureIcon}>{icon}</Text>
      <View style={styles.featureContent}>
        <Text style={styles.featureTitle}>{title}</Text>
        <Text style={styles.featureDescription}>{description}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#fff',
  },
  scrollContent: {
    padding: 24,
    paddingBottom: 40,
  },
  header: {
    alignItems: 'center',
    marginTop: 20,
    marginBottom: 32,
  },
  title: {
    fontSize: 32,
    fontWeight: 'bold',
    color: '#000',
    marginBottom: 8,
  },
  subtitle: {
    fontSize: 16,
    color: '#666',
    textAlign: 'center',
    paddingHorizontal: 20,
  },
  features: {
    marginBottom: 32,
  },
  featureItem: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    marginBottom: 20,
    paddingHorizontal: 8,
  },
  featureIcon: {
    fontSize: 28,
    marginRight: 16,
    marginTop: 2,
  },
  featureContent: {
    flex: 1,
  },
  featureTitle: {
    fontSize: 17,
    fontWeight: '600',
    color: '#000',
    marginBottom: 4,
  },
  featureDescription: {
    fontSize: 14,
    color: '#666',
    lineHeight: 20,
  },
  planSelector: {
    flexDirection: 'row',
    gap: 12,
    marginBottom: 16,
  },
  planOption: {
    flex: 1,
    backgroundColor: '#f5f5f5',
    borderRadius: 16,
    padding: 20,
    alignItems: 'center',
    borderWidth: 2,
    borderColor: '#f5f5f5',
    position: 'relative',
  },
  planOptionSelected: {
    borderColor: '#007AFF',
    backgroundColor: '#E3F2FF',
  },
  badge: {
    position: 'absolute',
    top: -10,
    backgroundColor: '#FF6B00',
    paddingHorizontal: 12,
    paddingVertical: 4,
    borderRadius: 12,
  },
  badgeText: {
    color: '#fff',
    fontSize: 10,
    fontWeight: 'bold',
    letterSpacing: 0.5,
  },
  planTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: '#000',
    marginTop: 8,
    marginBottom: 8,
  },
  planPrice: {
    fontSize: 28,
    fontWeight: 'bold',
    color: '#007AFF',
    marginBottom: 4,
  },
  planPeriod: {
    fontSize: 13,
    color: '#666',
    marginBottom: 4,
  },
  planSavings: {
    fontSize: 12,
    color: '#FF6B00',
    fontWeight: '600',
  },
  trialInfo: {
    alignItems: 'center',
    marginBottom: 20,
  },
  trialText: {
    fontSize: 14,
    color: '#666',
  },
  errorBox: {
    backgroundColor: '#FFE5E5',
    padding: 12,
    borderRadius: 8,
    marginBottom: 16,
  },
  errorText: {
    color: '#D32F2F',
    textAlign: 'center',
    fontSize: 14,
  },
  ctaButton: {
    backgroundColor: '#007AFF',
    borderRadius: 12,
    paddingVertical: 16,
    alignItems: 'center',
    marginBottom: 12,
  },
  ctaButtonDisabled: {
    opacity: 0.6,
  },
  ctaButtonText: {
    color: '#fff',
    fontSize: 18,
    fontWeight: '600',
  },
  restoreButton: {
    paddingVertical: 12,
    alignItems: 'center',
    marginBottom: 8,
  },
  restoreText: {
    fontSize: 16,
    color: '#007AFF',
    fontWeight: '500',
  },
  dismissButton: {
    paddingVertical: 12,
    alignItems: 'center',
    marginBottom: 16,
  },
  dismissText: {
    fontSize: 16,
    color: '#999',
  },
  hardGateMessage: {
    backgroundColor: '#FFF8E1',
    padding: 12,
    borderRadius: 8,
    marginBottom: 16,
    borderLeftWidth: 4,
    borderLeftColor: '#FFC107',
  },
  hardGateText: {
    fontSize: 14,
    color: '#F57C00',
    textAlign: 'center',
    fontWeight: '500',
  },
  legalLinks: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    marginTop: 8,
  },
  legalLink: {
    fontSize: 12,
    color: '#007AFF',
  },
  legalSeparator: {
    fontSize: 12,
    color: '#999',
  },
});
