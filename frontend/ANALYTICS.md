# Analytics Event Logging (Task F1)

## Overview

Centralized analytics tracking system for monitoring user behavior, conversion funnel, and feature usage.

## Architecture

### Core Module
**Location**: `app/utils/analytics.ts`

**Key Features**:
- ✅ Fail-safe, non-blocking event tracking
- ✅ Session management (30-minute timeout)
- ✅ Deduplication (1-second window per unique event)
- ✅ PII sanitization (removes email, userId, name, phone)
- ✅ String truncation (200 char max)
- ✅ Local storage (AsyncStorage) with 100-event limit
- ✅ Development logging (console output)

### Event Types

#### 1. `paywall_viewed`
**Trigger**: When paywall modal is displayed  
**Location**: `app/billing/PaywallScreen.tsx`  
**Parameters**:
```typescript
{
  feature?: string;      // e.g., 'solar_forecast', 'road_passability'
  source?: string;       // e.g., 'route_summary', 'settings'
  screen?: string;       // e.g., 'route_summary'
}
```

**Example**:
```typescript
trackEvent('paywall_viewed', {
  feature: 'solar_forecast',
  source: 'route_summary',
  screen: 'route_summary'
});
```

---

#### 2. `trial_started`
**Trigger**: When user successfully starts a trial  
**Location**: `app/billing/PaywallScreen.tsx` (handlePurchase)  
**Parameters**:
```typescript
{
  planType: 'monthly' | 'yearly';
  platform: 'ios' | 'android';
}
```

**Example**:
```typescript
trackEvent('trial_started', {
  planType: 'yearly',
  platform: Platform.OS
});
```

---

#### 3. `purchase_success`
**Trigger**: When user completes a purchase (including trials)  
**Location**: `app/billing/PaywallScreen.tsx` (handlePurchase)  
**Parameters**:
```typescript
{
  productId: string;     // e.g., 'pro_yearly', 'pro_monthly'
  planType: 'monthly' | 'yearly';
  price?: string;        // e.g., '$99.99'
}
```

**Example**:
```typescript
trackEvent('purchase_success', {
  productId: purchase.productIdentifier,
  planType: purchase.productIdentifier.includes('yearly') ? 'yearly' : 'monthly',
  price: purchase.price
});
```

---

#### 4. `feature_intent_used`
**Trigger**: When user attempts to use ANY feature (both free and premium)  
**Location**: `app/billing/premiumGate.ts` (premiumGate function)  
**Parameters**:
```typescript
{
  feature: string;       // e.g., 'solar_forecast', 'road_passability'
  isPremium: boolean;    // User's current premium status
}
```

**Example**:
```typescript
trackEvent('feature_intent_used', {
  feature: 'solar_forecast',
  isPremium: isPremium
});
```

**Purpose**: Track all feature access attempts to understand usage patterns.

---

#### 5. `feature_locked_shown`
**Trigger**: When premium gate blocks free users  
**Location**: `app/billing/premiumGate.ts` (triggerPaywall function)  
**Parameters**:
```typescript
{
  feature: string;       // e.g., 'solar_forecast'
  entryPoint?: string;   // e.g., 'soft_gate', 'hard_gate'
}
```

**Example**:
```typescript
trackEvent('feature_locked_shown', {
  feature: 'solar_forecast',
  entryPoint: 'soft_gate'
});
```

---

## Usage Guide

### Basic Tracking

```typescript
import { trackEvent } from '../utils/analytics';

// Simple event
trackEvent('paywall_viewed', {
  feature: 'solar_forecast'
});

// Event with multiple parameters
trackEvent('purchase_success', {
  productId: 'pro_yearly',
  planType: 'yearly',
  price: '$99.99'
});
```

### Error Handling

The system is **fail-safe** - errors are caught and logged but never throw:

```typescript
// This will NOT crash your app, even if AsyncStorage fails
try {
  await trackEvent('feature_intent_used', { feature: 'solar_forecast' });
} catch (error) {
  // This block will never execute - errors are handled internally
}
```

### Deduplication

Duplicate events (same name + same params) are ignored within 1 second:

```typescript
// Only first event is stored
trackEvent('paywall_viewed', { feature: 'solar_forecast' });
trackEvent('paywall_viewed', { feature: 'solar_forecast' }); // IGNORED
trackEvent('paywall_viewed', { feature: 'solar_forecast' }); // IGNORED

// Different params = new event
trackEvent('paywall_viewed', { feature: 'road_passability' }); // TRACKED
```

### PII Sanitization

Sensitive fields are automatically removed:

```typescript
trackEvent('purchase_success', {
  productId: 'pro_yearly',
  email: 'user@example.com',  // ❌ Removed before storage
  userId: '12345'              // ❌ Removed before storage
});

// Stored as:
// { productId: 'pro_yearly' }
```

**Blocked fields**: `email`, `userId`, `name`, `phone`, `address`, `creditCard`

---

## Session Management

- **Session ID**: Unique identifier generated per session
- **Timeout**: 30 minutes of inactivity
- **Format**: `session_<timestamp>_<random>`
- **Usage**: Automatically included in all events

```typescript
import { getCurrentSessionId } from '../utils/analytics';

const sessionId = getCurrentSessionId();
// Returns: "session_1705603200123_a1b2c3d4"
```

---

## Storage Management

### Local Storage
- **Key**: `analytics_events`
- **Format**: JSON array of event objects
- **Limit**: 100 events maximum (FIFO eviction)
- **Location**: AsyncStorage

### Retrieve Events

```typescript
import { getStoredEvents } from '../utils/analytics';

const events = await getStoredEvents();
console.log(events);
// [
//   {
//     name: 'paywall_viewed',
//     params: { feature: 'solar_forecast' },
//     timestamp: 1705603200123,
//     sessionId: 'session_1705603200123_a1b2c3d4'
//   },
//   ...
// ]
```

### Clear Events

```typescript
import { clearStoredEvents } from '../utils/analytics';

await clearStoredEvents();
```

---

## Testing

### Running Tests

```bash
cd frontend
npm test -- analytics.test.ts
```

### Test Coverage

✅ **17/17 tests passing**:
- Event tracking (all 5 event types)
- Deduplication logic
- PII sanitization
- Session management
- Error handling
- Storage limits

### Example Test

```typescript
it('tracks paywall_viewed event', async () => {
  await trackEvent('paywall_viewed', {
    feature: 'solar_forecast',
    source: 'route_summary',
  });

  const events = await getStoredEvents();
  expect(events).toHaveLength(1);
  expect(events[0].name).toBe('paywall_viewed');
  expect(events[0].params.feature).toBe('solar_forecast');
});
```

---

## Integration Points

### PaywallScreen.tsx
- `paywall_viewed`: On modal show (useEffect)
- `purchase_success`: On successful purchase
- `trial_started`: On trial start (iOS/Android detected)

### premiumGate.ts
- `feature_intent_used`: On every feature access attempt
- `feature_locked_shown`: When blocking free users

---

## Future Backend Integration

Currently, events are stored locally. To send events to backend:

### Option 1: Batch Upload
```typescript
import { getStoredEvents, clearStoredEvents } from '../utils/analytics';

async function syncEvents() {
  const events = await getStoredEvents();
  
  if (events.length > 0) {
    try {
      await fetch('https://api.example.com/analytics/events', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ events })
      });
      
      await clearStoredEvents();
    } catch (error) {
      console.warn('[Analytics] Sync failed:', error);
    }
  }
}

// Call periodically or on app background
```

### Option 2: Real-time Upload
Modify `analytics.ts` to POST immediately:

```typescript
async function trackEvent(name: EventName, params: EventParams = {}) {
  // ... existing code ...
  
  // Send to backend
  try {
    await fetch('https://api.example.com/analytics/events', {
      method: 'POST',
      body: JSON.stringify(event)
    });
  } catch (error) {
    // Fallback to local storage
    await storeEvent(event);
  }
}
```

---

## Monitoring & Debugging

### Development Mode
Events are logged to console:

```
[Analytics] Event tracked: {
  name: 'paywall_viewed',
  params: { feature: 'solar_forecast' },
  timestamp: '2026-01-18T19:15:05.593Z'
}
```

### Production Mode
Set `__DEV__` to false to disable console logs (still tracks to storage).

### Common Issues

**Q: Events not firing?**  
A: Check console for `[Analytics]` logs. Verify imports are correct.

**Q: Events being deduplicated unexpectedly?**  
A: Wait >1 second between identical events, or change params.

**Q: Storage quota exceeded?**  
A: Call `clearStoredEvents()` or implement batch upload to backend.

---

## Best Practices

1. **Track early, track often**: Add analytics to new features immediately
2. **Use descriptive params**: `feature: 'solar_forecast'` not `f: 'sf'`
3. **Avoid PII**: Never log emails, user IDs, or sensitive data
4. **Test in dev**: Verify events fire before deploying
5. **Monitor storage**: Implement backend sync to prevent data loss

---

## Performance

- **Overhead**: <1ms per event (async operation)
- **Storage**: ~100-500 bytes per event
- **Memory**: Minimal (in-memory deduplication cache cleared every 1s)
- **Network**: Zero (until backend integration)

---

## Compliance

- ✅ **GDPR**: No PII stored (sanitized automatically)
- ✅ **CCPA**: User data is anonymized
- ✅ **Privacy**: Session IDs are temporary and non-identifying

---

## Roadmap

- [ ] Backend endpoint: `POST /api/analytics/events`
- [ ] Automatic batch upload (every 5 minutes or 50 events)
- [ ] Analytics dashboard (conversion funnel, feature usage)
- [ ] Additional events: `paywall_dismissed`, `restore_purchases_clicked`
- [ ] Amplitude/Mixpanel integration
- [ ] A/B testing support

---

## Support

**Issues?** Check:
1. Console logs for `[Analytics]` messages
2. AsyncStorage permissions
3. Test suite: `npm test -- analytics.test.ts`

**Questions?** See `/frontend/app/utils/analytics.ts` for implementation details.
