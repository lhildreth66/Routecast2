# Routecast Premium Paywall Implementation Guide

## Overview

This guide explains the premium paywall system, feature gating architecture, and how to integrate real Google Play Billing.

## Architecture

### 1. Feature Gating System

**Location**: `frontend/app/hooks/usePremium.ts`

All features are defined in a central registry:

```typescript
export const FEATURES = {
  // Free features
  WEATHER_WARNINGS: { id: 'weather_warnings', isPremium: false, ... },
  LIVE_RADAR: { id: 'live_radar', isPremium: false, ... },
  
  // Premium features
  RADAR_PLAYBACK: { id: 'radar_playback', isPremium: true, ... },
  PREDICTIVE_STORM: { id: 'predictive_storm', isPremium: true, ... },
};
```

### 2. Checking Feature Access

```typescript
import { usePremium, FEATURES } from '../hooks/usePremium';

function MyComponent() {
  const { canAccessFeature } = usePremium();
  
  // Check if user can access a feature
  if (!canAccessFeature(FEATURES.RADAR_PLAYBACK.id)) {
    return <PaywallModal />;
  }
  
  // Feature code here
}
```

### 3. Premium Status Management

The premium status is stored in AsyncStorage:

```typescript
// Load status on app start
const { isPremium, loading, refreshStatus } = usePremium();

// Set premium status after purchase
setPremiumStatus(true, 'routecast_pro_monthly');

// Refresh status (e.g., after app resumes)
await refreshStatus();
```

## Billing Service

**Location**: `frontend/app/services/BillingService.ts`

### Stub Implementation (Current)

The billing service currently stubs Google Play Billing to allow development:

```typescript
// Test subscription IDs
const testIds = [
  'routecast_pro_monthly',
  'routecast_pro_annual',
];

// Simulate purchase
await BillingService.purchase('routecast_pro_monthly');
// Returns true, stores subscription locally
```

### Integration Checklist (Google Play Billing)

When Google Play Billing is ready:

1. **Install Google Play Billing Library**
   ```bash
   npm install react-native-google-play-billing
   ```

2. **Replace initialization** in `BillingService.ts`:
   ```typescript
   async initializeBilling() {
     // Call react-native-google-play-billing setup
     // Connect to Google Play Store
   }
   ```

3. **Replace purchase flow**:
   ```typescript
   async purchase(subscriptionId: string) {
     // Call launchBillingFlow()
     // Handle PurchaseFlowResult
     // Validate with backend
   }
   ```

4. **Replace query flow**:
   ```typescript
   async restorePurchases() {
     // Call queryPurchasesAsync()
     // Sync with server
   }
   ```

5. **Validate purchases on backend**:
   ```python
   # In backend, verify with Google Play API
   # using purchase token and subscription ID
   ```

## Frontend Integration

### Using the Paywall Modal

```typescript
import PaywallModal from '../components/PaywallModal';
import { BillingService } from '../services/BillingService';

function FeatureScreen() {
  const [showPaywall, setShowPaywall] = useState(false);
  const { isPremium } = usePremium();
  
  if (!isPremium) {
    return (
      <>
        <PaywallModal
          visible={showPaywall}
          onClose={() => setShowPaywall(false)}
          onSubscribe={handleSubscribe}
          featureName="Radar Playback"
          featureDescription="Review past 2-6 hours of radar"
        />
        <Button onPress={() => setShowPaywall(true)}>
          Unlock Feature
        </Button>
      </>
    );
  }
  
  return <PremiumFeatureContent />;
}

async function handleSubscribe(planId: string) {
  const success = await BillingService.purchase(planId);
  if (success) {
    // Refresh premium status
    await usePremium().refreshStatus();
  }
}
```

### Where to Add Gating

**Route Playback**:
```typescript
// frontend/app/route.tsx
if (!canAccessFeature(FEATURES.RADAR_PLAYBACK.id)) {
  return <PaywallModal onSubscribe={handleSubscribe} />;
}
// Show radar playback controls
```

**Advanced Alerts**:
```typescript
// When fetching route data
if (request.include_advanced_alerts && !isPremium) {
  // Don't request advanced alerts from backend
  request.include_advanced_alerts = false;
}
```

**Future Weather**:
```typescript
// frontend/app/route.tsx - in waypoint rendering
if (isPremium && waypoint.future_weather) {
  <Text>Future: {waypoint.future_weather}</Text>
}
```

## Backend Integration

**Location**: `backend/server.py`

### Subscription Endpoints

1. **Validate Subscription** (`POST /api/billing/validate-subscription`):
   ```python
   # Called when user purchases
   # Validates against Google Play API
   # Returns success/failure
   ```

2. **Feature Gating Info** (`GET /api/billing/features`):
   ```python
   # Returns list of free vs premium features
   # Used by frontend to show accurate UI
   ```

### Adding Premium Gating to Routes

In the route weather calculation:

```python
@api_router.post("/route/weather")
async def get_route_weather(request: RouteRequest):
    # ... existing code ...
    
    # [PREMIUM] Future weather forecasting
    if request.include_future_weather:
        if not is_premium_user(request.user_id):
            logger.warning("[PREMIUM] User attempted premium feature without subscription")
            request.include_future_weather = False
        else:
            logger.info("[PREMIUM] Including future weather for premium user")
            # Include future weather predictions
```

### Logging Pattern

```python
# Free feature
logger.info("[FREE] Road surface warning generated")

# Premium attempt
logger.warning("[PREMIUM] User attempted radar playback without subscription")

# Premium success
logger.info("[PREMIUM] Radar history returned to premium subscriber")
```

## Safety Checks & Fallbacks

### 1. Graceful Degradation

If billing service is unavailable:

```typescript
// App remains fully functional
// All free features work
// Premium features show "Upgrade" UI (not crash)
```

### 2. No Hard Blocking

- Premium features never crash the app
- Always show paywall instead of error
- Navigation always available
- Safety alerts never blocked

### 3. Offline Support

```typescript
// If no internet when checking premium status:
const { isPremium } = usePremium(); // Falls back to last known state
// Free features still work
// Premium features gracefully gated
```

## Feature Matrix

### Free Features (Always Available)
- ✅ Weather warnings along routes
- ✅ Road surface warnings (ice, flooding)
- ✅ Bridge height alerts (RV/Trucker mode)
- ✅ Live radar (current conditions)
- ✅ Time/date departure changes
- ✅ Basic AI chat
- ✅ Major weather alerts
- ✅ Google Maps integration
- ✅ Recent & favorites
- ✅ Basic push weather alerts

### Premium Features (Subscription Required)
- 🔒 Future weather forecasts (ETA-based)
- 🔒 Radar playback & history (2-6 hours)
- 🔒 Advanced push alerts (hail, freezing rain, wind)
- 🔒 Predictive storm intercept alerts

## Testing

### Test Subscriptions

Use these test IDs in development:
```
routecast_pro_monthly
routecast_pro_annual
test_subscription
```

### Toggling Premium Status

```typescript
// In development, toggle premium in console:
import { usePremium } from './hooks/usePremium';
const { setPremiumStatus } = usePremium();
await setPremiumStatus(true, 'routecast_pro_monthly');
```

### Backend Test

```bash
# Validate a test subscription
curl -X POST http://localhost:8000/api/billing/validate-subscription \
  -H "Content-Type: application/json" \
  -d '{"subscription_id": "routecast_pro_monthly"}'
```

## Monitoring & Logging

All premium feature access is logged:

```
[FREE] Road surface warning generated
[PREMIUM] User attempted radar playback without subscription
[PREMIUM] Radar history returned to premium subscriber
[BILLING] Purchase successful (STUB)
[BILLING] Subscription validated: routecast_pro_monthly
```

Monitor these logs to:
- Track feature adoption
- Identify conversion bottlenecks
- Debug billing issues

## Transition to Production

When ready to enable real subscriptions:

1. Enable Google Play Billing in Google Play Console
2. Update `BillingService.ts` to use real API calls
3. Add backend validation with Google Play API
4. Test with real test accounts
5. Gradually roll out (start with 1%, scale to 100%)
6. Monitor: crash rates, conversion rates, churn

## Important Notes

⚠️ **Stability First**:
- App is fully functional in free mode
- Billing unavailability never breaks the app
- Premium gating is graceful, never hard-blocking

⚠️ **Safety Always**:
- Weather/hazard alerts never gated
- Route safety features always free
- No payment walls on emergency information

⚠️ **User Experience**:
- Paywall is informative, not annoying
- Users can try features before paying
- Clear value proposition
- Easy to cancel/manage subscriptions
