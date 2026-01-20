# Testing Premium Features - Quick Guide

## Option 1: Dev Toggle (Easiest - Instant)

For development/testing, use the built-in dev toggle function:

### Step 1: Enable Pro Access

Open your browser console (or React Native debugger) and run:

```javascript
// Enable premium features
await AsyncStorage.setItem('entitlements.boondockingPro', 'true');
```

Or reload the app to use the dev toggle function (if you have dev menu access).

### Step 2: Verify Access

All premium features should now be unlocked:
- ⚡ Solar Forecast
- 🔥 Propane Usage
- 💧 Water Budget
- 🌄 Terrain Shade
- 💨 Wind Shelter
- 🚙 Road Passability
- 📡 Connectivity Prediction
- ⭐ Campsite Index
- 📄 Claim Log
- 🏕️ Camp Prep (all commands except /prep-checklist)

### Step 3: Disable Pro Access (Optional)

To test locked state again:

```javascript
await AsyncStorage.setItem('entitlements.boondockingPro', 'false');
// or
await AsyncStorage.removeItem('entitlements.boondockingPro');
```

Then restart the app.

---

## Option 2: Full Billing Flow (For Production Testing)

This requires building a native app (can't use Expo Go):

### Prerequisites
1. **Android device** (iOS uses stub implementation for now)
2. **Google Play Console** account
3. **License tester** account set up in Play Console

### Steps

#### 1. Set Up License Tester
1. Go to [Google Play Console](https://play.google.com/console)
2. Select your app → **Setup** → **License testing**
3. Add your Gmail account
4. Save changes

#### 2. Build Development Client
```bash
cd frontend
eas build --profile development --platform android
```

Wait for build, then download and install APK on device.

#### 3. Test Purchase Flow
1. Open app on test device (logged in with license tester account)
2. Navigate to any premium feature (e.g., Solar Forecast)
3. Tap "Subscribe" → complete test purchase
4. Features should unlock immediately

**Note:** Test purchases don't charge real money when using license tester accounts.

---

## Quick Access via AsyncStorage (Web/Dev)

If running in web or dev mode, you can manually set the entitlement:

1. Open browser DevTools → Console (or React Native Debugger)
2. Run:
   ```javascript
   import AsyncStorage from '@react-native-async-storage/async-storage';
   await AsyncStorage.setItem('entitlements.boondockingPro', 'true');
   ```
3. Reload app

All premium features will be unlocked.

---

## Verify Premium Access

Check if premium is enabled:

```javascript
import { hasBoondockingPro } from './app/utils/entitlements';
const isPro = await hasBoondockingPro();
console.log('Is Pro:', isPro);
```

---

## Troubleshooting

**Features still locked after enabling?**
- Clear app cache/data and try again
- Check AsyncStorage value: `await AsyncStorage.getItem('entitlements.boondockingPro')`
- Should return `"true"` (as string)

**Want to reset everything?**
```javascript
await AsyncStorage.clear();
```

---

## Backend Subscription Validation

For backend API calls (like Camp Prep chat), you also need a subscription ID:

```javascript
await AsyncStorage.setItem('routecast_subscription_id', 'test_subscription_123');
```

This is automatically set during real purchases but must be set manually for dev testing.
