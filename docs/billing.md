# Billing Setup — Google Play Subscriptions (Expo + EAS Build)

This document describes how to set up and configure Google Play subscriptions for the Routecast2 Android app using Expo and EAS Build.

## ⚠️ Important: Expo Go Limitation

**react-native-iap requires native modules and WILL NOT work in Expo Go.**

You must use:
- **EAS Build** to create custom development builds for testing
- **Production builds (AAB)** for Play Store submission

See the "Building with EAS" section below for instructions.

## Overview

The app uses **react-native-iap** for subscription management with the following products:

- `boondocking_pro_monthly` - Monthly subscription  
- `boondocking_pro_yearly` - Yearly subscription

## Prerequisites

1. **Expo Account**
   - Sign up at https://expo.dev
   - Install EAS CLI: `npm install -g eas-cli`
   - Login: `eas login`

2. **Google Play Console Access**
   - Developer account with app registered
   - Billing permissions for the app

3. **EAS Build Configuration**
   - `eas.json` configured in project root
   - Android credentials set up

## Google Play Console Configuration

### 1. Create Subscription Products

1. Navigate to **Monetize > Products > Subscriptions**
2. Click **Create subscription**
3. Create monthly subscription:
   - **Product ID**: `boondocking_pro_monthly`
   - **Name**: Boondocking Pro Monthly
   - **Description**: Monthly access to all Boondocking Pro features
   - **Base plan**: Create with monthly billing period
   - **Price**: Set your monthly price (e.g., $9.99/month)

4. Create yearly subscription:
   - **Product ID**: `boondocking_pro_yearly`
   - **Name**: Boondocking Pro Yearly
   - **Description**: Annual access to all Boondocking Pro features (best value!)
   - **Base plan**: Create with yearly billing period
   - **Price**: Set your yearly price (e.g., $99.99/year)

5. **Activate** both subscriptions

### 2. Configure License Testers

To test subscriptions during development:

1. Navigate to **Setup > License testing**
2. Add tester email addresses (Gmail accounts work best)
3. Save changes

**Important**: License testers can make test purchases that:
- Don't charge real money
- Complete immediately (no waiting for payment processing)
- Can be cancelled/refunded easily

### 3. Internal Testing Track Setup

1. Navigate to **Testing > Internal testing**
2. Create a new release or use existing internal track
3. Upload your app bundle (use `eas build --platform android`)
4. Add license testers to internal testing group
5. Publish the release

## Building with EAS

### Why EAS Build is Required

`react-native-iap` is a **native module** that accesses Android/iOS billing APIs. This means:

- ❌ **Does NOT work in Expo Go** (managed runtime)
- ✅ **Requires custom native build** using EAS Build or `expo prebuild`

### 1. Install Dependencies

Already installed in `package.json`:

```bash
npm install react-native-iap
```

### 2. EAS Configuration

Ensure `eas.json` is configured with build profiles:

```json
{
  "build": {
    "development": {
      "developmentClient": true,
      "distribution": "internal",
      "android": {
        "buildType": "apk"
      }
    },
    "preview": {
      "distribution": "internal",
      "android": {
        "buildType": "apk"
      }
    },
    "production": {
      "android": {
        "buildType": "app-bundle"
      }
    }
  }
}
```

### 3. Build Development Client (for Testing)

To test subscriptions during development, create a development build:

```bash
# Build development client (includes dev tools)
eas build --profile development --platform android

# Install on device/emulator
# Download APK from build page and install manually
```

**What is a development build?**
- Custom Expo app with your native modules included
- Includes dev menu and debugging tools
- Can connect to Metro bundler for hot reload
- Allows testing react-native-iap on real device

### 4. Build Preview/Production

```bash
# Internal testing APK (faster builds)
eas build --profile preview --platform android

# Production AAB (for Play Store)
eas build --profile production --platform android

# Submit to Play Store
eas submit --platform android --latest
```

### 5. App Signing

EAS Build handles signing automatically:

1. First build: EAS generates keystore or you provide your own
2. **Google Play App Signing** (recommended): Let Google manage upload key
3. Subsequent builds use same keystore (stored securely by EAS)

### 6. Testing on Device

**Option A: Development Build (Recommended)**
```bash
# 1. Build development client
eas build --profile development --platform android

# 2. Install on device
# Download APK and install via adb or direct download

# 3. Start Metro bundler
npm start

# 4. Open dev build on device → connects to Metro
```

**Option B: Preview/Production Build**
```bash
# Build standalone APK
eas build --profile preview --platform android

# Install on device (no Metro connection)
```

### 7. Prebuild (Alternative to EAS)

If you want local native builds:

```bash
# Generate native android/ and ios/ directories
npx expo prebuild

# Run locally
npm run android
```

**Note:** Most developers use EAS Build instead of local prebuild for subscription testing.

## Code Integration

### Billing Flow

The billing system is integrated in the following layers:

1. **Interface Layer** (`src/core/billing/StoreBilling.ts`)
   - Defines abstract billing operations
   - Platform-agnostic

2. **Implementation** (`src/core/billing/ReactNativeIapBilling.ts`)
   - Uses `react-native-iap` for Google Play
   - Handles purchase acknowledgement
   - Safe error handling

3. **Entitlements** (`src/core/billing/verifyEntitlements.ts`)
   - Syncs purchases with local entitlements
   - Called on app start

4. **Use Cases** (`src/core/usecases/paywall/`)
   - `onPaywallShown`: Tracks analytics when paywall shown
   - `onPurchaseSuccess`: Grants features + tracks purchase

### App Initialization
Common Issues

### "Expo Go doesn't support react-native-iap"

**Solution:** This is expected. You must create a custom development build:
```bash
eas build --profile development --platform android
```

### "Module not found: react-native-iap"

**In Expo Go:** Not supported, use development build  
**In custom build:** Rebuild with `eas build`

### "Build failed: Gradle error"

Check `eas.json` has correct Android SDK versions. Ensure `react-native-iap` is in `dependencies` (not `devDependencies`).

### Testing subscriptions requires physical device?

No, but **emulator must have Google Play Services** installed:
- Use Google Play system images (not AOSP)
- Sign in with test Google account
- Ensure Play Store app is working

## Troubleshooting

See `docs/billing-testing.md` for comprehensive testing procedures and troubleshooting
```typescript
import { ReactNativeIapBilling } from './src/core/billing/ReactNativeIapBilling';
import { verifyEntitlements } from './src/core/billing/verifyEntitlements';
import { initEntitlements } from './src/core/billing/initEntitlements';

// Initialize entitlements store
const entitlements = new CachedEntitlements(store);
await initEntitlements(entitlements);

// Verify subscription status
const billing = new ReactNativeIapBilling();
await verifyEntitlements(billing, entitlements);
```

### Purchase Flow

In your paywall UI component:

```typescript
import { ReactNativeIapBilling } from './src/core/billing/ReactNativeIapBilling';
import { onPaywallShown, onPurchaseSuccess } from './src/core/usecases/paywall/';

// When paywall opens
onPaywallShown(feature, 'paywall_screen');

// When user presses subscribe button
const billing = new ReactNativeIapBilling();
await billing.init();

const result = await billing.purchase('yearly'); // or 'monthly'

if (result.ok) {
  await onPurchaseSuccess(entitlements, feature, result.plan, 'paywall_screen');
  // Close paywall, user is now premium
} else if (result.code === 'cancelled') {
  // User cancelled - no action needed
} else {
  // Show error message
  alert(`Purchase failed: ${result.message}`);
}
```

## Limitations (Current Implementation)

⚠️ **No Server-Side Receipt Validation**

The current implementation is **client-side only**:

- Trust the device to report subscription status
- Can be bypassed on rooted/modified devices
- Suitable for MVP/beta testing only

**Before Production Launch:**

1. Implement server-side receipt validation
2. Use Google Play Developer API to verify purchases
3. Store subscription state on secure backend
4. Implement webhook for real-time subscription updates
5. Handle subscription lifecycle (renewals, cancellations, grace periods)

See `docs/billing-testing.md` for testing procedures.

## Product IDs Reference

| Product ID | Plan | Description |
|------------|------|-------------|
| `boondocking_pro_monthly` | Monthly | $9.99/month (example pricing) |
| `boondocking_pro_yearly` | Yearly | $99.99/year (example pricing) |

## Troubleshooting

See `docs/billing-testing.md` for common issues and solutions.

## Resources

- [react-native-iap Documentation](https://react-native-iap.dooboolab.com/)
- [Google Play Billing Overview](https://developer.android.com/google/play/billing/billing_overview)
- [Expo EAS Build](https://docs.expo.dev/build/introduction/)
- [Google Play Console](https://play.google.com/console)
