# Premium Paywall - Quick Reference Card

## 🚀 Using Premium Features

### In a Component
```typescript
import { usePremium, FEATURES } from '../hooks/usePremium';
import PaywallModal from '../components/PaywallModal';

function MyComponent() {
  const [showPaywall, setShowPaywall] = useState(false);
  const { canAccessFeature } = usePremium();
  
  if (!canAccessFeature(FEATURES.RADAR_PLAYBACK.id)) {
    return <PaywallModal visible={showPaywall} onClose={() => setShowPaywall(false)} />;
  }
  
  return <PremiumFeature />;
}
```

## 🔒 Gating a Feature

### Option 1: Complete Block
```typescript
if (!canAccessFeature(featureId)) {
  return <PaywallModal />;
}
// Feature code here
```

### Option 2: Inline Upsell
```typescript
{isPremium ? (
  <PremiumComponent />
) : (
  <Text>🔒 Unlock with Pro</Text>
)}
```

### Option 3: Graceful Fallback
```typescript
const data = isPremium ? getPremiumData() : getFreeData();
return <Component data={data} />;
```

## 📊 Feature Categories

| Category | Free | Premium |
|----------|------|---------|
| Weather Warnings | ✅ | ✅ |
| Road Surface Alerts | ✅ | ✅ |
| Bridge Height Alerts | ✅ | ✅ |
| Live Radar | ✅ | ✅ |
| Time/Departure Changes | ✅ | ✅ |
| Basic AI Chat | ✅ | ✅ |
| Major Weather Alerts | ✅ | ✅ |
| Maps Integration | ✅ | ✅ |
| Recent & Favorites | ✅ | ✅ |
| Basic Push Alerts | ✅ | ✅ |
| **Future Weather** | ❌ | ✅ |
| **Radar Playback** | ❌ | ✅ |
| **Advanced Push Alerts** | ❌ | ✅ |
| **Storm Predictions** | ❌ | ✅ |

## 💰 Pricing

| Plan | Price | Frequency |
|------|-------|-----------|
| Monthly | $4.99 | Every month |
| Annual | $29.99 | Once per year (40% savings) |
| Trial | FREE | 7 days |

## 🧪 Testing

### Test Subscriptions
```
routecast_pro_monthly    // Test monthly
routecast_pro_annual     // Test annual
test_subscription        // Generic test
```

### Simulate Purchase
```typescript
import { BillingService } from '../services/BillingService';
await BillingService.purchase('routecast_pro_monthly');
// Automatically sets premium status to active
```

### Check Status
```typescript
const { isPremium, loading } = usePremium();
console.log(isPremium ? 'Premium active' : 'Free tier');
```

### Manually Set Premium
```typescript
import AsyncStorage from '@react-native-async-storage/async-storage';
await AsyncStorage.setItem('routecast_premium_status', 'active');
await AsyncStorage.setItem('routecast_subscription_id', 'routecast_pro_monthly');
// Refresh app to see changes
```

### Refresh Status
```typescript
const { refreshStatus } = usePremium();
await refreshStatus(); // Re-check from storage
```

## 📝 Logging Patterns

All premium access is logged:

```
[FREE]     Road surface warning generated
[PREMIUM]  Accessing radar playback
[PREMIUM]  User blocked: Future weather (not subscribed)
[BILLING]  Purchase successful
[BILLING]  Error validating subscription (fallback)
```

Filter logs: `grep "\[PREMIUM\]" logfile.txt`

## 🛡️ Safety Rules

### ✅ ALWAYS Free
- Weather warnings
- Road hazards
- Bridge alerts
- Major alerts
- Route safety

### 🔒 Can Be Premium
- Radar history
- Future forecasts
- Advanced alerts
- Predictions

### ❌ NEVER Block
- App navigation
- Safety features
- Recent/favorites
- Settings

## 📱 Paywall Modal Props

```typescript
interface PaywallModalProps {
  visible: boolean;              // Show/hide modal
  onClose: () => void;           // Close button handler
  onSubscribe: (planId: string) => Promise<void>;
  featureName?: string;          // Feature being gated
  featureDescription?: string;   // Why it's premium
}
```

## 🔌 Backend Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/billing/validate-subscription` | POST | Verify subscription |
| `/api/billing/features` | GET | Get feature matrix |
| `/api/notifications/register` | POST | Register push token |
| `/api/notifications/test` | POST | Send test notification |

## 🐛 Troubleshooting

| Issue | Solution |
|-------|----------|
| Premium status not persisting | Check AsyncStorage permissions |
| Paywall not showing | Verify `visible={showPaywall}` |
| Test purchase not working | Check test subscription ID |
| Billing errors ignored | Expected - graceful fallback |
| Logs not showing [PREMIUM] | Check logging level/filter |
| App crashes on billing error | Should not happen - report bug |

## 📚 Documentation

- **PREMIUM_IMPLEMENTATION.md** - Full integration guide
- **PREMIUM_GATING_CHECKLIST.md** - Where to add gating
- **PREMIUM_SUMMARY.md** - Overview and files
- **REQUIREMENTS_VERIFICATION.md** - Requirements met ✅

## 🎯 Next Steps

1. **Route Screen**: Add gating for radar playback
2. **Create Upgrade Prompt**: Inline component for locked features
3. **Settings Screen**: Subscription management
4. **Google Play**: Configure real billing when ready

## 📞 Support

Questions about premium implementation?

1. Check the docs in this folder
2. Search code for `[PREMIUM]` logging
3. Review inline comments in:
   - `usePremium.ts`
   - `PaywallModal.tsx`
   - `BillingService.ts`
   - `server.py` billing endpoints

## ✅ Stability Guarantee

- ✅ App works 100% in free mode
- ✅ No crashes if billing unavailable  
- ✅ Safety features never gated
- ✅ Graceful fallbacks everywhere
- ✅ Comprehensive logging
- ✅ Clear error messages

**Monetization is secondary. Stability and safety are primary.** 🛡️
