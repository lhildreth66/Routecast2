# Premium Gating Integration Checklist

## This checklist guides where to add `canAccessFeature()` checks throughout the codebase.

## Frontend Changes Required

### ✅ COMPLETED
- [x] Feature registry created (`usePremium.ts`)
- [x] Paywall modal component (`PaywallModal.tsx`)
- [x] Billing service stubs (`BillingService.ts`)
- [x] Push notification system
- [x] Premium status management

### 📍 TO DO - Route Screen (frontend/app/route.tsx)

**RADAR PLAYBACK** (Premium Feature):
```typescript
// Location: Lines ~400-500 (radar controls section)
// BEFORE showing radar playback controls, add:

if (routeData.waypoints[0]) {
  if (!canAccessFeature(FEATURES.RADAR_PLAYBACK.id)) {
    return <UpgradePrompt feature={FEATURES.RADAR_PLAYBACK} />;
  }
}

// Then show: Play button, rewind, speed controls for historical radar
```

**ADVANCED PUSH ALERTS** (Premium Feature):
```typescript
// Location: Lines ~800-900 (alerts section)
// BEFORE showing advanced alert types:

const showAdvancedAlerts = canAccessFeature(FEATURES.ADVANCED_PUSH_ALERTS.id);

// Filter alerts to show only if premium or non-advanced
{routeData.hazard_alerts.map(alert => {
  if (alert.type === 'advanced' && !showAdvancedAlerts) {
    return <UpgradePrompt />;
  }
  return <AlertComponent alert={alert} />;
})}
```

**FUTURE WEATHER** (Premium Feature):
```typescript
// Location: Lines ~600-700 (waypoint rendering)
// BEFORE showing future weather in waypoint details:

const canShowFutureWeather = canAccessFeature(FEATURES.FUTURE_WEATHER.id);

{waypoint.future_weather && canShowFutureWeather ? (
  <Text>Future: {waypoint.future_weather}</Text>
) : waypoint.future_weather ? (
  <UpgradePrompt feature={FEATURES.FUTURE_WEATHER} />
) : null}
```

### 📍 TO DO - Home Screen (frontend/app/index.tsx)

**AI CHAT** (Free, but could show upsell for advanced features):
```typescript
// Location: Lines ~1200-1300 (chat section)
// Chat is free, but in future could upsell advanced AI analysis

// For now: Just use basic AI chat
// TODO: In future, add "Advanced AI Analysis" as premium feature
```

### 📍 TO DO - New Feature: Settings/Premium Screen

Create `frontend/app/settings.tsx`:
```typescript
// Show:
// 1. Current subscription status
// 2. Feature comparison table
// 3. Manage subscription button
// 4. Restore purchases button
// 5. Cancel subscription (if premium)
```

## Backend Changes Required

### ✅ COMPLETED
- [x] Subscription validation endpoint
- [x] Feature gating info endpoint
- [x] Logging infrastructure

### 📍 TO DO - Route Weather Endpoint (backend/server.py)

**Future Weather Forecasting** (Premium Only):
```python
# Location: Lines ~1400 (in get_route_weather)
# BEFORE including future weather:

if request.include_future_weather:
    is_premium = await check_user_premium_status(request.user_id)
    if not is_premium:
        logger.warning("[PREMIUM] User attempted future weather without subscription")
        request.include_future_weather = False
        weather_response.future_weather = None
    else:
        logger.info("[PREMIUM] Including future weather for premium subscriber")
        # Include future weather calculations
```

**Advanced Radar History** (Premium Only):
```python
# Location: Lines ~1450 (radar data section)
# BEFORE returning radar history:

if request.include_radar_history:
    is_premium = await check_user_premium_status(request.user_id)
    if not is_premium:
        logger.warning("[PREMIUM] User attempted radar history without subscription")
        # Only return current radar, not history
        weather_response.radar_history = None
    else:
        logger.info("[PREMIUM] Returning radar history to premium subscriber")
        # Include 2-6 hour radar history
```

### 📍 TO DO - AI Chat Endpoint (backend/server.py)

**Basic AI Chat** (Free):
```python
# Location: Lines ~1700 (chat endpoint)
# Currently free - keep as is
# Just add logging:
logger.info("[FREE] User accessing basic AI chat")
```

**Future: Advanced Storm Analysis** (Premium):
```python
# TODO: In future, add premium feature for advanced storm analysis
# For now, basic chat is sufficient
```

## Data Model Additions

### User Document Structure (MongoDB)

```json
{
  "_id": ObjectId,
  "push_token": "ExponentPushToken[...]",
  "premium_status": {
    "is_premium": boolean,
    "subscription_id": "routecast_pro_monthly",
    "purchase_date": ISODate,
    "expiry_date": ISODate,
    "auto_renew": boolean
  },
  "feature_access_log": [
    {
      "feature": "radar_playback",
      "accessed_at": ISODate,
      "was_allowed": boolean
    }
  ]
}
```

### Subscription Document Structure

```json
{
  "_id": ObjectId,
  "subscription_id": "routecast_pro_monthly",
  "status": "active",
  "user_id": ObjectId,
  "created_at": ISODate,
  "last_validated": ISODate,
  "google_purchase_token": "string",
  "auto_renew": boolean
}
```

## UI Components Needed

### ✅ COMPLETED
- [x] PaywallModal (shows feature, pricing, subscribe button)

### 📍 TO DO
- [ ] UpgradePrompt (inline "Upgrade to unlock" text)
- [ ] UpgradeButton (premium badge on feature buttons)
- [ ] FeatureComparison (table of free vs premium features)
- [ ] SubscriptionManager (manage/cancel subscription)

**UpgradePrompt Component**:
```typescript
interface UpgradePromptProps {
  feature: PremiumFeature;
  onUpgrade: () => void;
}

// Show in place of locked features
// Text: "🔒 {feature.name}\n{feature.description}\nTap to upgrade"
```

**UpgradeButton Component**:
```typescript
// Add badge to buttons for premium features
<Button>
  View Radar History
  <Badge color="gold">Pro</Badge>
</Button>
```

## Testing Checklist

- [ ] Free user cannot access radar playback
- [ ] Free user sees paywall when trying to access radar playback
- [ ] Premium user can access all features
- [ ] Switching between free/premium refreshes UI
- [ ] Offline mode: free features work, premium shows "Upgrade"
- [ ] Logging shows "[FREE]" and "[PREMIUM]" tags
- [ ] No crashes if billing service unavailable
- [ ] Recent/Favorites always work (free feature)
- [ ] Push alerts always work (free feature)

## Deployment Checklist

- [ ] All logging statements in place
- [ ] Feature matrix verified with product team
- [ ] Test with 10% of users first
- [ ] Monitor crash rate (should be ~0% impact)
- [ ] Monitor feature adoption metrics
- [ ] Monitor subscription conversion
- [ ] Graceful handling of rollback if needed

## Notes for Engineering

1. **Never Gate Safety Features**: Weather alerts, road conditions, bridge warnings are ALL free
2. **Graceful Degradation**: If premium feature unavailable, show "Upgrade" not error
3. **Logging is Critical**: Use [FREE], [PREMIUM], [BILLING] prefixes for easy filtering
4. **Test Offline**: Ensure app works without network
5. **Fallback Chains**: If billing unavailable → use local status → assume free tier
6. **User Data**: Track which features users try (helps with upsell messaging)

## Timeline

- **Week 1**: Complete frontend/backend integration ✅
- **Week 2**: Add all UI components and gating checks
- **Week 3**: Integrate real Google Play Billing
- **Week 4**: Beta testing with internal users
- **Week 5**: Rollout to 1% of users
- **Week 6+**: Monitor and scale
