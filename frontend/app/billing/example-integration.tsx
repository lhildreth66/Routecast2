/**
 * Paywall Integration Example
 * 
 * Shows how to integrate the paywall system with soft/hard gating in your app root.
 */

import React, { useState } from 'react';
import { EntitlementsProvider } from './EntitlementsProvider';
import { PaywallScreen } from './PaywallScreen';
import { setPaywallTrigger } from './premiumGate';
import { resetTracking, type GateMode } from './gateTracking';
import type { PremiumFeature } from './types';

/**
 * Root component that wraps your app with entitlements and paywall.
 */
export function AppWithPaywall({ children }: { children: React.ReactNode }) {
  const [paywallVisible, setPaywallVisible] = useState(false);
  const [lockedFeature, setLockedFeature] = useState<PremiumFeature | null>(null);
  const [gateMode, setGateMode] = useState<GateMode>('soft');

  // Set up global paywall trigger
  React.useEffect(() => {
    setPaywallTrigger((feature: PremiumFeature, mode: GateMode) => {
      console.log('[Paywall] Triggered for feature:', feature, 'mode:', mode);
      setLockedFeature(feature);
      setGateMode(mode);
      setPaywallVisible(true);
    });
  }, []);

  const handlePaywallClose = () => {
    // Only allow close if soft gate
    if (gateMode === 'soft') {
      setPaywallVisible(false);
      setLockedFeature(null);
    }
  };

  const handlePurchaseComplete = async () => {
    console.log('[Paywall] Purchase completed');
    
    // Reset gate tracking after successful purchase
    await resetTracking();
    
    setPaywallVisible(false);
    setLockedFeature(null);
    
    // Entitlements hook will auto-refresh
  };

  return (
    <EntitlementsProvider>
      {children}
      
      <PaywallScreen
        visible={paywallVisible}
        feature={lockedFeature || undefined}
        gateMode={gateMode}
        onClose={handlePaywallClose}
        onPurchaseComplete={handlePurchaseComplete}
      />
    </EntitlementsProvider>
  );
}

/**
 * Example usage in a feature component
 */
export function ExampleFeatureScreen() {
  const { premiumGate, premiumApiCall } = require('./premiumGate');
  const { SOLAR_FORECAST } = require('./features');
  
  const handleLoadSolarForecast = async () => {
    try {
      // Option 1: Wrap the API call
      const data = await premiumApiCall(SOLAR_FORECAST, async () => {
        const response = await fetch('/api/pro/solar-forecast', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            lat: 34.05,
            lon: -111.03,
            dates: ['2026-01-20'],
            panel_watts: 400,
            shade_pct: 20,
            cloud_cover: [0],
            subscription_id: await getSubscriptionId(), // Your auth helper
          }),
        });
        return response;
      });
      
      console.log('Solar forecast:', data);
    } catch (error) {
      console.error('Error loading solar forecast:', error);
      // Paywall automatically triggered if premium_locked
    }
  };

  // Option 2: Gate a local function
  const calculateLocalData = async () => {
    await premiumGate(SOLAR_FORECAST, async () => {
      // This code only runs if user has Pro
      console.log('User has Pro access');
      // ... do premium calculation
    });
  };

  return null; // Your UI here
}

async function getSubscriptionId(): Promise<string | null> {
  // Example: Load from AsyncStorage
  const AsyncStorage = (await import('@react-native-async-storage/async-storage')).default;
  return await AsyncStorage.getItem('subscription_id');
}
