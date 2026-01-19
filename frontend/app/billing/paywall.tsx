/**
 * Paywall Component
 * 
 * Modal UI for subscription purchase.
 * Shows benefits, pricing, and purchase buttons.
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
} from 'react-native';
import type { Subscription } from 'react-native-iap';
import { iapClient } from './iapClient';
import type { ProductId } from './types';

interface PaywallProps {
  visible: boolean;
  onClose: () => void;
  onPurchaseComplete?: () => void;
}

export function Paywall({ visible, onClose, onPurchaseComplete }: PaywallProps) {
  const [products, setProducts] = useState<Subscription[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedProduct, setSelectedProduct] = useState<ProductId | null>(null);

  useEffect(() => {
    if (visible) {
      loadProducts();
    }
  }, [visible]);

  const loadProducts = async () => {
    try {
      setLoading(true);
      setError(null);
      const fetchedProducts = await iapClient.fetchProducts();
      setProducts(fetchedProducts);
    } catch (err) {
      console.error('[Paywall] Failed to load products:', err);
      setError('Failed to load products');
    } finally {
      setLoading(false);
    }
  };

  const handlePurchase = async (productId: ProductId) => {
    try {
      setLoading(true);
      setError(null);
      setSelectedProduct(productId);
      
      const result = await iapClient.purchase(productId);
      
      if (result.success) {
        console.log('[Paywall] Purchase successful');
        onPurchaseComplete?.();
        onClose();
      } else {
        setError(result.error || 'Purchase failed');
      }
    } catch (err) {
      console.error('[Paywall] Purchase error:', err);
      setError(err instanceof Error ? err.message : 'Purchase failed');
    } finally {
      setLoading(false);
      setSelectedProduct(null);
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

  const getProductPrice = (productId: ProductId): string => {
    const product = products.find(p => p.productId === productId);
    return product?.localizedPrice || '...';
  };

  return (
    <Modal
      visible={visible}
      animationType="slide"
      presentationStyle="pageSheet"
      onRequestClose={onClose}
    >
      <View style={styles.container}>
        <ScrollView contentContainerStyle={styles.scrollContent}>
          {/* Header */}
          <View style={styles.header}>
            <Text style={styles.title}>Boondocking Pro</Text>
            <Text style={styles.subtitle}>
              Unlock premium features for advanced backcountry planning
            </Text>
          </View>

          {/* Benefits */}
          <View style={styles.benefits}>
            <BenefitItem icon="⚡" text="Solar power forecasting" />
            <BenefitItem icon="🔥" text="Propane usage calculator" />
            <BenefitItem icon="💧" text="Water budget planner" />
            <BenefitItem icon="⛰️" text="Terrain shade analysis" />
            <BenefitItem icon="🌪️" text="Wind shelter assessment" />
            <BenefitItem icon="🚙" text="Road passability simulator" />
            <BenefitItem icon="📡" text="Cell & Starlink coverage" />
            <BenefitItem icon="⭐" text="Campsite quality index" />
            <BenefitItem icon="📝" text="Claim log tracking" />
          </View>

          {/* Pricing */}
          <View style={styles.pricing}>
            <TouchableOpacity
              style={[
                styles.priceButton,
                selectedProduct === 'boondocking_pro_yearly' && styles.priceButtonSelected,
              ]}
              onPress={() => handlePurchase('boondocking_pro_yearly')}
              disabled={loading}
            >
              <View style={styles.badge}>
                <Text style={styles.badgeText}>BEST VALUE</Text>
              </View>
              <Text style={styles.priceTitle}>Yearly</Text>
              <Text style={styles.priceAmount}>
                {getProductPrice('boondocking_pro_yearly')}
              </Text>
              <Text style={styles.pricePer}>/year</Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={[
                styles.priceButton,
                selectedProduct === 'boondocking_pro_monthly' && styles.priceButtonSelected,
              ]}
              onPress={() => handlePurchase('boondocking_pro_monthly')}
              disabled={loading}
            >
              <Text style={styles.priceTitle}>Monthly</Text>
              <Text style={styles.priceAmount}>
                {getProductPrice('boondocking_pro_monthly')}
              </Text>
              <Text style={styles.pricePer}>/month</Text>
            </TouchableOpacity>
          </View>

          {/* Error */}
          {error && (
            <View style={styles.errorBox}>
              <Text style={styles.errorText}>{error}</Text>
            </View>
          )}

          {/* Loading */}
          {loading && (
            <View style={styles.loadingBox}>
              <ActivityIndicator size="large" color="#007AFF" />
              <Text style={styles.loadingText}>Processing...</Text>
            </View>
          )}

          {/* Restore */}
          <TouchableOpacity
            style={styles.restoreButton}
            onPress={handleRestore}
            disabled={loading}
          >
            <Text style={styles.restoreText}>Restore Purchases</Text>
          </TouchableOpacity>

          {/* Close */}
          <TouchableOpacity style={styles.closeButton} onPress={onClose}>
            <Text style={styles.closeText}>Maybe Later</Text>
          </TouchableOpacity>
        </ScrollView>
      </View>
    </Modal>
  );
}

function BenefitItem({ icon, text }: { icon: string; text: string }) {
  return (
    <View style={styles.benefitItem}>
      <Text style={styles.benefitIcon}>{icon}</Text>
      <Text style={styles.benefitText}>{text}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#fff',
  },
  scrollContent: {
    padding: 20,
  },
  header: {
    marginTop: 20,
    marginBottom: 30,
    alignItems: 'center',
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
  },
  benefits: {
    marginBottom: 30,
  },
  benefitItem: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#eee',
  },
  benefitIcon: {
    fontSize: 24,
    marginRight: 16,
  },
  benefitText: {
    fontSize: 16,
    color: '#333',
    flex: 1,
  },
  pricing: {
    flexDirection: 'row',
    gap: 12,
    marginBottom: 20,
  },
  priceButton: {
    flex: 1,
    backgroundColor: '#f5f5f5',
    borderRadius: 12,
    padding: 20,
    alignItems: 'center',
    borderWidth: 2,
    borderColor: '#f5f5f5',
    position: 'relative',
  },
  priceButtonSelected: {
    borderColor: '#007AFF',
    backgroundColor: '#E3F2FF',
  },
  badge: {
    position: 'absolute',
    top: -8,
    backgroundColor: '#FF6B00',
    paddingHorizontal: 12,
    paddingVertical: 4,
    borderRadius: 12,
  },
  badgeText: {
    color: '#fff',
    fontSize: 10,
    fontWeight: 'bold',
  },
  priceTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: '#000',
    marginBottom: 8,
    marginTop: 8,
  },
  priceAmount: {
    fontSize: 28,
    fontWeight: 'bold',
    color: '#007AFF',
  },
  pricePer: {
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
  loadingBox: {
    alignItems: 'center',
    padding: 20,
  },
  loadingText: {
    marginTop: 12,
    fontSize: 14,
    color: '#666',
  },
  restoreButton: {
    paddingVertical: 16,
    alignItems: 'center',
    marginBottom: 12,
  },
  restoreText: {
    fontSize: 16,
    color: '#007AFF',
    fontWeight: '600',
  },
  closeButton: {
    paddingVertical: 16,
    alignItems: 'center',
    marginBottom: 20,
  },
  closeText: {
    fontSize: 16,
    color: '#999',
  },
});
