import React, { useState } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  Modal,
  ScrollView,
  SafeAreaView,
  ActivityIndicator,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';

interface PaywallModalProps {
  visible: boolean;
  onClose: () => void;
  onSubscribe: (planId: string) => Promise<void>;
  featureName?: string;
  featureDescription?: string;
}

export default function PaywallModal({
  visible,
  onClose,
  onSubscribe,
  featureName = 'Premium Feature',
  featureDescription = 'This feature is only available with Routecast Pro',
}: PaywallModalProps) {
  const [loading, setLoading] = useState(false);
  const [selectedPlan, setSelectedPlan] = useState('monthly');

  const handleSubscribe = async () => {
    try {
      setLoading(true);
      await onSubscribe(selectedPlan);
    } catch (err) {
      console.log('Subscription error:', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal visible={visible} animationType="slide" transparent={true}>
      <SafeAreaView style={{ flex: 1, backgroundColor: '#0a0a0a' }}>
        <View style={{ flex: 1, backgroundColor: '#0a0a0a' }}>
          {/* Header */}
          <View
            style={{
              flexDirection: 'row',
              justifyContent: 'space-between',
              alignItems: 'center',
              paddingHorizontal: 16,
              paddingVertical: 12,
              borderBottomWidth: 1,
              borderBottomColor: '#27272a',
            }}
          >
            <Text style={{ fontSize: 18, fontWeight: '700', color: '#ffffff' }}>
              Routecast Pro
            </Text>
            <TouchableOpacity onPress={onClose} disabled={loading}>
              <Ionicons name="close" size={24} color="#71717a" />
            </TouchableOpacity>
          </View>

          <ScrollView
            contentContainerStyle={{ paddingHorizontal: 16, paddingVertical: 20 }}
            showsVerticalScrollIndicator={false}
          >
            {/* Feature highlight */}
            {featureName && (
              <View
                style={{
                  backgroundColor: '#27272a',
                  borderRadius: 12,
                  padding: 16,
                  marginBottom: 24,
                  borderLeftWidth: 4,
                  borderLeftColor: '#f59e0b',
                }}
              >
                <Text style={{ fontSize: 16, fontWeight: '600', color: '#eab308' }}>
                  🔒 {featureName}
                </Text>
                <Text
                  style={{
                    fontSize: 13,
                    color: '#a1a1aa',
                    marginTop: 8,
                    lineHeight: 20,
                  }}
                >
                  {featureDescription}
                </Text>
              </View>
            )}

            {/* Premium features list */}
            <Text
              style={{
                fontSize: 16,
                fontWeight: '700',
                color: '#ffffff',
                marginBottom: 12,
              }}
            >
              What's Included
            </Text>

            <View style={{ gap: 10, marginBottom: 24 }}>
              {[
                { icon: '⏰', text: 'Future weather forecasts (ETA-based)' },
                { icon: '📹', text: 'Radar playback (2-6 hour history)' },
                { icon: '🔔', text: 'Advanced alerts (hail, freezing rain, wind)' },
                { icon: '⛈️', text: 'Storm intercept predictions' },
              ].map((item, idx) => (
                <View key={idx} style={{ flexDirection: 'row', gap: 12, alignItems: 'flex-start' }}>
                  <Text style={{ fontSize: 18, marginTop: 2 }}>{item.icon}</Text>
                  <Text style={{ fontSize: 14, color: '#e4e4e7', flex: 1, lineHeight: 20 }}>
                    {item.text}
                  </Text>
                </View>
              ))}
            </View>

            {/* Pricing */}
            <Text
              style={{
                fontSize: 16,
                fontWeight: '700',
                color: '#ffffff',
                marginBottom: 12,
              }}
            >
              Choose Your Plan
            </Text>

            {/* Monthly Plan */}
            <TouchableOpacity
              style={{
                borderWidth: 2,
                borderColor: selectedPlan === 'monthly' ? '#eab308' : '#27272a',
                borderRadius: 12,
                padding: 16,
                marginBottom: 12,
                backgroundColor: selectedPlan === 'monthly' ? '#eab30810' : '#27272a',
              }}
              onPress={() => setSelectedPlan('monthly')}
              disabled={loading}
            >
              <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
                <View>
                  <Text style={{ fontSize: 16, fontWeight: '600', color: '#ffffff' }}>
                    Monthly
                  </Text>
                  <Text style={{ fontSize: 12, color: '#a1a1aa', marginTop: 4 }}>
                    $4.99 / month
                  </Text>
                </View>
                <View
                  style={{
                    width: 20,
                    height: 20,
                    borderRadius: 10,
                    borderWidth: 2,
                    borderColor: selectedPlan === 'monthly' ? '#eab308' : '#52525b',
                    justifyContent: 'center',
                    alignItems: 'center',
                  }}
                >
                  {selectedPlan === 'monthly' && (
                    <View
                      style={{
                        width: 10,
                        height: 10,
                        borderRadius: 5,
                        backgroundColor: '#eab308',
                      }}
                    />
                  )}
                </View>
              </View>
            </TouchableOpacity>

            {/* Annual Plan */}
            <TouchableOpacity
              style={{
                borderWidth: 2,
                borderColor: selectedPlan === 'annual' ? '#eab308' : '#27272a',
                borderRadius: 12,
                padding: 16,
                marginBottom: 24,
                backgroundColor: selectedPlan === 'annual' ? '#eab30810' : '#27272a',
              }}
              onPress={() => setSelectedPlan('annual')}
              disabled={loading}
            >
              <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
                <View>
                  <Text style={{ fontSize: 16, fontWeight: '600', color: '#ffffff' }}>
                    Annual{' '}
                    <Text style={{ fontSize: 12, color: '#10b981', fontWeight: '700' }}>
                      (Save 40%)
                    </Text>
                  </Text>
                  <Text style={{ fontSize: 12, color: '#a1a1aa', marginTop: 4 }}>
                    $29.99 / year
                  </Text>
                </View>
                <View
                  style={{
                    width: 20,
                    height: 20,
                    borderRadius: 10,
                    borderWidth: 2,
                    borderColor: selectedPlan === 'annual' ? '#eab308' : '#52525b',
                    justifyContent: 'center',
                    alignItems: 'center',
                  }}
                >
                  {selectedPlan === 'annual' && (
                    <View
                      style={{
                        width: 10,
                        height: 10,
                        borderRadius: 5,
                        backgroundColor: '#eab308',
                      }}
                    />
                  )}
                </View>
              </View>
            </TouchableOpacity>

            {/* Subscribe button */}
            <TouchableOpacity
              style={{
                backgroundColor: '#eab308',
                borderRadius: 10,
                paddingVertical: 14,
                justifyContent: 'center',
                alignItems: 'center',
                marginBottom: 12,
                opacity: loading ? 0.7 : 1,
              }}
              onPress={handleSubscribe}
              disabled={loading}
            >
              {loading ? (
                <ActivityIndicator color="#000000" />
              ) : (
                <Text style={{ fontSize: 16, fontWeight: '700', color: '#000000' }}>
                  Start Free Trial
                </Text>
              )}
            </TouchableOpacity>

            {/* Info text */}
            <Text
              style={{
                fontSize: 11,
                color: '#71717a',
                textAlign: 'center',
                lineHeight: 16,
              }}
            >
              7-day free trial. Cancel anytime. First 3 days completely free.
            </Text>
          </ScrollView>
        </View>
      </SafeAreaView>
    </Modal>
  );
}
