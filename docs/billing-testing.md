# Billing Testing Guide (Expo + EAS Build)

How to test Google Play subscriptions in development using Expo development builds and internal testing.

## ⚠️ Critical: Cannot Test in Expo Go

**react-native-iap requires native modules.**

You MUST use one of these:
- ✅ **EAS development build** (recommended for testing)
- ✅ **EAS preview/production build**
- ✅ **Local prebuild + native build**
- ❌ **Expo Go** (will not work)

## Quick Start

### 1. Set Up License Tester

1. Go to [Google Play Console](https://play.google.com/console)
2. Select your app → **Setup** → **License testing**
3. Add your Gmail account(s)
4. Save changes

**What this gives you:**
- Test purchases that don't charge real money
- Immediate purchase completion (no payment processing delay)
- Easy cancellation/refund
- Access to subscription management in Play Store

### 2. Create Development Build

```bash
# Build development client with react-native-iap included
eas build --profile development --platform android

# Wait for build to complete (check build page)
# Download APK from build page
# Install on device: adb install <build>.apk
# OR transfer APK to device and install manually
```

**Why development build?**
- Includes native modules (react-native-iap)
- Can connect to Metro bundler for hot reload
- Includes dev menu (shake device)
- Faster iteration during development

### 3. Install and Run

```bash
# 1. Install development build on device (one-time)

# 2. Start Metro bundler
npm start

# 3. Open dev build on device
# It will connect to Metro automatically
# Changes to JS code will hot reload
```

### 4. Test Purchase Flow

1. Open app on test device (logged in with license tester account)
2. Navigate to a premium feature (e.g., Solar Forecast)
3. Tap on the feature → should see paywall
4. Tap "Subscribe" → select plan (monthly or yearly)
5. Complete test purchase flow
6. Verify feature unlocks immediately

## Build Types for Testing

## Testing Scenarioscommended)

**Best for:** Active development, debugging, testing features

```bash
eas build --profile development --platform android
```

**Pros:**
- ✅ Connects to Metro bundler (hot reload)
- ✅ Dev menu available (shake device)
- ✅ Can test subscriptions
- ✅ Faster iteration

**Cons:**
- ❌ Larger APK size
- ❌ Not suitable for production
- ❌ Must rebuild when native deps change

### Preview Build

**Best for:** Internal testing, beta testing, QA

```bash
eas build --profile preview --platform android
```

**Pros:**
- ✅ Standalone APK
- ✅ Can test subscriptions
- ✅ Closer to production
- ✅ No Metro needed

**Cons:**
- ❌ No hot reload
- ❌ Rebuild required for any code change
- ❌ Slower iteration

### Production Build

**Best for:** Play Store submission

```bash
eas build --profile production --platform android
```

**Output:** AAB (Android App Bundle) for Play Store

### ✅ Successful Purchase

**Steps:**
1. Fresh install (or clear app data)
2. Navigate to premium feature
3. Tap subscribe → complete purchase
4. Verify:
   - Purchase completes successfully
   - Features unlock immediately
   - Can access all premium features
   - Purchase appears in Play Store subscriptions

**Expected Analytics:**
- `feature_intent_used`
- `feature_locked_shown`
- `paywall_viewed`
- `purchase_success`

### ❌ Cancelled Purchase

**Steps:**
1. Navigate to premium feature
2. Tap subscribe → back button or cancel
3. Verify:
   - Returns to previous screen
   - Features remain locked
   - No error message shown

**Expected Analytics:**
- `feature_intent_used`
- `feature_locked_shown`
- `paywall_viewed`
- (No `purchase_success`)

### 🔄 Restore Purchases

**Steps:**
1. Install app on device A → purchase subscription
2. Uninstall app (or clear data)
3. Reinstall app
4. App should automatically restore subscription on launch
5. Verify features are unlocked without repurchase

**Expected Behavior:**
- `verifyEntitlements` runs on app start
- Detects active subscription from Play Store
- Grants all features automatically
- No paywall shown

### 📱 Multi-Device Sync

**Steps:**
1. Purchase subscription on device A
2. Install app on device B (same Google account)
3. Launch app on device B
4. Verify subscription automatically detected

**Expected Behavior:**
- Subscription tied to Google account, not device
- Works across all devices with same account
- Features unlock automatically on new device

### ⏰ Expiration Testing

**Note:** Test subscriptions expire faster than production:

| Plan | Production | Test Mode |
|------|------------|-----------|
| Monthly | 30 days | ~5 minutes |
| Yearly | 365 days | ~30 minutes |

**Steps:**
1. Purchase test subscription
2. Wait for expiration (~5-30 min depending on plan)
3. Relaunch app
4. Verify features are locked again

**Expected Behavior:**
- Subscription expires quickly in test mode
- App detects expiration on next launch
- Features lock automatically
- User must repurchase

## Troubleshooting

### "Cannot test in Expo Go"

**Cause:** react-native-iap is a native module

**Solution:**
```bash
# Create development build
eas build --profile development --platform android
# Install on device and run
```

### "Expo Go doesn't support native modules"

This is expected behavior. See solution above.

### Development build won't connect to Metro

**Solutions:**
1. Ensure device and computer on same network
2. Check `npm start` is running
3. Shake device → Dev menu → "Reload"
4. Try `npm start --tunnel` if on different networks

### "react-native-iap is null or undefined"

**Cause:** Module not included in build

**Solutions:**
1. Verify `react-native-iap` in `dependencies` (not `devDependencies`)
2. Rebuild: `eas build --profile development --platform android`
3. Clear cache: `eas build --profile development --platform android --clear-cache`

### "Item not available for purchase"

**Cause:** Product not found in Play Store

**Solutions:**
1. Verify product IDs match exactly:
   - `boondocking_pro_monthly`
   - `boondocking_pro_yearly`
2. Ensure products are **Active** in Play Console
3. Check app is using correct package name
4. Wait 2-4 hours after creating products (propagation delay)
5. Clear Play Store cache on device

### "You already own this item"

**Cause:** Previous test purchase still active

**Solutions:**
1. Cancel subscription in Play Store → Subscriptions
2. Wait for cancellation to process (~1 minute)
3. Clear app data and retry
4. Use different test account if urgent

### Purchase flow doesn't start

**Cause:** Billing not initialized

**Solutions:**
1. Check console logs for init errors
2. Verify `react-native-iap` installed correctly
3. Rebuild app with `eas build`
4. Check device has Play Store and Google Play Services updated

### "Payment declined"

**Cause:** Test account not configured properly

**Solutions:**
1. Verify email is added to License Testing list
2. Ensure device logged into correct Google account
3. Check account is joined to internal testing track
4. Try with different Gmail account

### Features don't unlock after purchase

**Cause:** Entitlements not granted

**Solutions:**
1. Check console logs for `onPurchaseSuccess` calls
2. Verify `verifyEntitlements` runs on app start
3. Check AsyncStorage for `entitlements_v1` key
4. Force close and reopen app
5. Clear app data and restore purchase

### iOS Crashes

**Cause:** iOS not fully supported yet

**Solutions:**
1. Test on Android only for now
2. iOS uses stub implementation (won't crash)
3. Full iOS support coming in future update

## Manual Testing Checklist

Use this checklist for comprehensive testing before release:

- [ ] Fresh install → purchase → features unlock
- [ ] Uninstall → reinstall → purchase restored
- [ ] Cancel purchase flow → features stay locked
- [ ] Purchase on device A → sync to device B
- [ ] Offline purchase attempt → error shown
- [ ] Invalid product ID → error handled gracefully
- [ ] Purchase during poor network → retry works
- [ ] Subscription expiration → features lock
- [ ] Manage subscription in Play Store → works
- [ ] Refund subscription → features revoke

## Analytics Verification

After testing, verify these events in your analytics dashboard:

1. **Paywall viewed**: `paywall_viewed`
   - Params: `{ feature, source }`

2. **Feature intent**: `feature_intent_used`
   - Params: `{ feature, source }`

3. **Locked shown**: `feature_locked_shown`
   - Params: `{ feature, source }`

4. **Purchase success**: `purchase_success`
   - Params: `{ feature, plan, source }`

## Testing Best Practices

1. **Use dedicated test accounts**
   - Don't test with your primary Google account
   - Create separate Gmail accounts for testing

2. **Clear app data between tests**
   - Ensures clean state
   - Prevents cached entitlements interfering

3. **Test on multiple devices**
   - Different Android versions
   - Different screen sizes
   - Physical devices (not just emulator)

4. **Monitor console logs**
   - Watch for billing errors
   - Check analytics events firing
   - Look for crash logs

5. **Test edge cases**
   - Airplane mode
   - Low memory
   - Background/foreground transitions
   - App updates with active subscription

## Known Limitations

Current implementation limitations:

⚠️ **Client-side only** - No server receipt validation
⚠️ **Can be bypassed** - On rooted/modified devices  
⚠️ **No subscription webhooks** - Won't detect cancellations in real-time  
⚠️ **No grace periods** - Expired = immediately locked  
⚠️ **No promotional offers** - Basic subscriptions only  

These will be addressed in production version with server-side validation.

## Resources

- [Google Play Console](https://play.google.com/console)
- [License Testing Setup](https://developer.android.com/google/play/billing/test)
- [Test Subscription Periods](https://developer.android.com/google/play/billing/test#test-subscriptions)
- [react-native-iap Testing](https://react-native-iap.dooboolab.com/docs/guides/testing)
