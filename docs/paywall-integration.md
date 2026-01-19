# Paywall Integration Reference

This document shows how to wire the billing system to your paywall UI component.

## Overview

The billing system is designed to be framework-agnostic. Your React Native components should:

1. Call `onPaywallShown()` when paywall is displayed
2. Call `billing.purchase()` when user taps subscribe button  
3. Call `onPurchaseSuccess()` when purchase succeeds
4. Handle failure cases appropriately

## Example Paywall Component

```typescript
import React, { useState } from 'react';
import { View, Text, Button, Alert } from 'react-native';
import { ReactNativeIapBilling } from '../core/billing/ReactNativeIapBilling';
import { onPaywallShown, onPurchaseSuccess } from '../core/usecases/paywall';
import type { Feature } from '../core/billing/PremiumLockedError';
import type { CachedEntitlements } from '../core/billing/CachedEntitlements';

interface PaywallScreenProps {
  feature: Feature;
  source: string;
  entitlements: CachedEntitlements;
  onDismiss: () => void;
}

export function PaywallScreen({ feature, source, entitlements, onDismiss }: PaywallScreenProps) {
  const [isLoading, setIsLoading] = useState(false);
  const [billing] = useState(() => new ReactNativeIapBilling());

  // Track analytics when paywall shown
  React.useEffect(() => {
    onPaywallShown(feature, source);
  }, [feature, source]);

  const handleSubscribe = async (plan: 'monthly' | 'yearly') => {
    setIsLoading(true);

    try {
      // Initialize billing if not already done
      await billing.init();

      // Trigger purchase flow
      const result = await billing.purchase(plan);

      if (result.ok) {
        // Purchase succeeded - grant entitlements and track analytics
        await onPurchaseSuccess(entitlements, feature, result.plan, source);

        // Success! Close paywall
        Alert.alert('Success!', 'Welcome to Boondocking Pro!', [
          { text: 'OK', onPress: onDismiss }
        ]);
      } else if (result.code === 'cancelled') {
        // User cancelled - no action needed (just return)
        // Could optionally show a message
      } else {
        // Purchase failed
        Alert.alert(
          'Purchase Failed',
          result.message || 'Unable to complete purchase. Please try again.',
          [{ text: 'OK' }]
        );
      }
    } catch (error) {
      Alert.alert('Error', 'An unexpected error occurred. Please try again.');
      console.error('[PaywallScreen] Purchase error:', error);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <View style={{ flex: 1, padding: 20 }}>
      <Text style={{ fontSize: 24, fontWeight: 'bold' }}>Upgrade to Pro</Text>
      <Text style={{ marginTop: 10 }}>
        Unlock {feature.replace(/_/g, ' ')} and all premium features!
      </Text>

      <View style={{ marginTop: 30 }}>
        <Button
          title="Subscribe Yearly - $99.99/year"
          onPress={() => handleSubscribe('yearly')}
          disabled={isLoading}
        />
        <View style={{ height: 10 }} />
        <Button
          title="Subscribe Monthly - $9.99/month"
          onPress={() => handleSubscribe('monthly')}
          disabled={isLoading}
        />
        <View style={{ height: 20 }} />
        <Button
          title="Not Now"
          onPress={onDismiss}
          disabled={isLoading}
        />
      </View>

      {isLoading && <Text style={{ marginTop: 20 }}>Processing...</Text>}
    </View>
  );
}
```

## App Initialization

Initialize entitlements and verify subscriptions on app start:

```typescript
// App.tsx or _layout.tsx
import React, { useEffect, useState } from 'react';
import { AsyncStorageEntitlementsStore } from './src/core/billing/EntitlementsStore';
import { CachedEntitlements } from './src/core/billing/CachedEntitlements';
import { ReactNativeIapBilling } from './src/core/billing/ReactNativeIapBilling';
import { initEntitlements } from './src/core/billing/initEntitlements';
import { verifyEntitlements } from './src/core/billing/verifyEntitlements';

export default function App() {
  const [entitlements, setEntitlements] = useState<CachedEntitlements | null>(null);

  useEffect(() => {
    initializeBilling();
  }, []);

  const initializeBilling = async () => {
    try {
      // 1. Create entitlements store and cache
      const store = new AsyncStorageEntitlementsStore();
      const ents = new CachedEntitlements(store);

      // 2. Load persisted entitlements from storage
      await initEntitlements(ents);

      // 3. Verify subscription status with Play Store
      const billing = new ReactNativeIapBilling();
      await verifyEntitlements(billing, ents);

      setEntitlements(ents);

      console.log('[App] Billing initialized');
    } catch (error) {
      console.error('[App] Failed to initialize billing:', error);
      // App should continue even if billing fails
    }
  };

  if (!entitlements) {
    return <LoadingScreen />;
  }

  return (
    <EntitlementsContext.Provider value={entitlements}>
      {/* Your app content */}
    </EntitlementsContext.Provider>
  );
}
```

## Using Premium Features

Wrap premium features with entitlement checks:

```typescript
import { getSolarForecast } from './src/core/usecases/energy/getSolarForecast';
import { PremiumLockedError } from './src/core/billing/PremiumLockedError';

function SolarForecastScreen() {
  const entitlements = useEntitlements(); // Get from context
  const [showPaywall, setShowPaywall] = useState(false);

  const loadForecast = async () => {
    try {
      // This will throw PremiumLockedError if user doesn't have entitlement
      const forecast = getSolarForecast(
        entitlements,
        {
          lat: 28.5,
          lon: -81.5,
          dateRange: [1, 2, 3],
          panelWatts: 200,
          shadePct: 10,
          cloudCover: [20, 30, 25],
        },
        'solar_screen'
      );

      // Use forecast data
      console.log('Forecast:', forecast);
    } catch (error) {
      if (error instanceof PremiumLockedError) {
        // Show paywall
        setShowPaywall(true);
      } else {
        // Handle other errors
        Alert.alert('Error', 'Failed to load forecast');
      }
    }
  };

  return (
    <View>
      <Button title="Get Solar Forecast" onPress={loadForecast} />

      {showPaywall && (
        <PaywallScreen
          feature="solar_forecast"
          source="solar_screen"
          entitlements={entitlements}
          onDismiss={() => setShowPaywall(false)}
        />
      )}
    </View>
  );
}
```

## Testing the Integration

### Unit Tests

Test the paywall handler logic using FakeStoreBilling:

```typescript
import { FakeStoreBilling } from '../core/billing/FakeStoreBilling';
import { CachedEntitlements } from '../core/billing/CachedEntitlements';
import { onPurchaseSuccess } from '../core/usecases/paywall/onPurchaseSuccess';

describe('Paywall purchase flow', () => {
  it('grants entitlements on successful purchase', async () => {
    const billing = new FakeStoreBilling();
    const entitlements = new CachedEntitlements(/* mock store */);
    
    await billing.init();
    const result = await billing.purchase('yearly');
    
    expect(result.ok).toBe(true);
    
    if (result.ok) {
      await onPurchaseSuccess(entitlements, 'solar_forecast', result.plan, 'test');
      expect(entitlements.has('solar_forecast')).toBe(true);
    }
  });

  it('handles cancelled purchase gracefully', async () => {
    const billing = new FakeStoreBilling();
    billing.setPurchaseCancellation(true);
    
    await billing.init();
    const result = await billing.purchase('monthly');
    
    expect(result.ok).toBe(false);
    expect(result.code).toBe('cancelled');
  });
});
```

### Integration Tests

Test with development build on real device:

1. Build development build: `eas build --profile development --platform android`
2. Install on device
3. Configure as license tester in Play Console
4. Test purchase flow end-to-end

See `docs/billing-testing.md` for comprehensive testing guide.

## Analytics Events

The system automatically tracks these events:

| Event | When | Params |
|-------|------|--------|
| `feature_intent_used` | User tries to access premium feature | `{ feature, source }` |
| `feature_locked_shown` | User sees lock message | `{ feature, source }` |
| `paywall_viewed` | Paywall screen shown | `{ feature, source }` |
| `purchase_success` | Purchase completes | `{ feature, plan, source }` |

No additional analytics calls needed in your UI code - the use cases handle it.

## Best Practices

1. **Initialize once**: Create billing instance once, reuse throughout app
2. **Context for entitlements**: Use React Context to share entitlements globally
3. **Handle errors gracefully**: Don't crash on billing failures
4. **Test with FakeStoreBilling**: Unit test paywall logic without real store
5. **Use development builds**: Test react-native-iap on real devices
6. **Add license testers**: Configure Play Console before testing

## Common Pitfalls

❌ **Don't** try to test in Expo Go (native module required)  
❌ **Don't** call `onPurchaseSuccess` if purchase failed/cancelled  
❌ **Don't** forget to initialize billing before purchase  
❌ **Don't** assume purchase always succeeds (handle failures)  

✅ **Do** use EAS development builds for testing  
✅ **Do** handle all PurchaseResult cases (ok, cancelled, failed)  
✅ **Do** test with license testers before production  
✅ **Do** provide clear error messages to users  
