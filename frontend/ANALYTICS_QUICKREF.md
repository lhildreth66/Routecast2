# Analytics Quick Reference

## Import
```typescript
import { trackEvent } from '../utils/analytics';
```

## Event Types

### 1. Paywall Viewed
```typescript
trackEvent('paywall_viewed', {
  feature: 'solar_forecast',  // Which feature triggered paywall
  source: 'route_summary',    // Where user came from
  screen: 'route_summary'     // Current screen name
});
```

### 2. Trial Started
```typescript
import { Platform } from 'react-native';

trackEvent('trial_started', {
  planType: 'yearly',         // or 'monthly'
  platform: Platform.OS       // 'ios' or 'android'
});
```

### 3. Purchase Success
```typescript
trackEvent('purchase_success', {
  productId: 'pro_yearly',    // Product identifier
  planType: 'yearly',         // or 'monthly'
  price: '$99.99'             // Optional: localized price
});
```

### 4. Feature Intent Used
```typescript
trackEvent('feature_intent_used', {
  feature: 'solar_forecast',  // Feature being accessed
  isPremium: false            // User's premium status
});
```

### 5. Feature Locked Shown
```typescript
trackEvent('feature_locked_shown', {
  feature: 'solar_forecast',  // Locked feature
  entryPoint: 'soft_gate'     // 'soft_gate' or 'hard_gate'
});
```

## Helper Functions

### Get Session ID
```typescript
import { getCurrentSessionId } from '../utils/analytics';

const sessionId = getCurrentSessionId();
// Returns: "session_1705603200123_a1b2c3d4"
```

### Get Stored Events
```typescript
import { getStoredEvents } from '../utils/analytics';

const events = await getStoredEvents();
// Returns: Array of { name, params, timestamp, sessionId }
```

### Clear Stored Events
```typescript
import { clearStoredEvents } from '../utils/analytics';

await clearStoredEvents();
```

## Key Features

✅ **Fail-Safe**: Never throws errors, never blocks UI  
✅ **Deduplication**: Ignores duplicate events within 1 second  
✅ **PII Protection**: Auto-removes email, userId, name, phone  
✅ **Session Tracking**: 30-minute timeout, auto-generated IDs  
✅ **Storage Limit**: Max 100 events (FIFO eviction)  

## Common Patterns

### Track Button Click
```typescript
const handleFeatureClick = () => {
  trackEvent('feature_intent_used', {
    feature: 'solar_forecast',
    isPremium: isPremiumUser
  });
  
  if (!isPremiumUser) {
    showPaywall();
  } else {
    openFeature();
  }
};
```

### Track Purchase Flow
```typescript
const handlePurchase = async () => {
  try {
    const purchase = await iapClient.purchase(productId);
    
    trackEvent('purchase_success', {
      productId: purchase.productIdentifier,
      planType: productId.includes('yearly') ? 'yearly' : 'monthly',
      price: purchase.price
    });
    
    if (purchase.isTrial) {
      trackEvent('trial_started', {
        planType: productId.includes('yearly') ? 'yearly' : 'monthly',
        platform: Platform.OS
      });
    }
  } catch (error) {
    // Purchase failed - no tracking needed
  }
};
```

### Track Paywall Display
```typescript
useEffect(() => {
  if (paywallVisible) {
    trackEvent('paywall_viewed', {
      feature: triggeredByFeature,
      source: navigatedFrom,
      screen: currentScreen
    });
  }
}, [paywallVisible]);
```

## Testing

Run tests:
```bash
cd frontend
npm test -- analytics.test.ts
```

Check coverage:
- ✅ 17/17 tests passing
- ✅ All event types covered
- ✅ Deduplication verified
- ✅ PII sanitization tested
- ✅ Error handling validated

## Documentation

**Full Docs**: See `frontend/ANALYTICS.md`  
**Implementation**: See `frontend/app/utils/analytics.ts`  
**Tests**: See `frontend/app/__tests__/analytics.test.ts`  
**Summary**: See `/TASK_F1_SUMMARY.md`
