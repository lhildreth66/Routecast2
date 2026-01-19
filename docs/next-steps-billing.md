# Next Steps After Implementation

This checklist covers what you need to do immediately after Copilot finishes implementing the billing system.

## ✅ Immediate Actions (Required Before Testing)

### 1. Create Subscriptions in Google Play Console

**Location:** [Google Play Console](https://play.google.com/console) → Your App → **Monetize** → **Products** → **Subscriptions**

Create two subscriptions with these **exact** Product IDs:

#### Monthly Subscription
- **Product ID:** `boondocking_pro_monthly` (must match exactly)
- **Name:** Boondocking Pro Monthly
- **Description:** Monthly access to all Boondocking Pro features
- **Billing Period:** 1 month
- **Price:** Your choice (e.g., $9.99/month)
- **Base Plan:** Create with monthly renewal
- **Status:** ✅ **Active**

#### Yearly Subscription
- **Product ID:** `boondocking_pro_yearly` (must match exactly)
- **Name:** Boondocking Pro Yearly  
- **Description:** Annual access to all Boondocking Pro features (best value!)
- **Billing Period:** 1 year
- **Price:** Your choice (e.g., $99.99/year)
- **Base Plan:** Create with yearly renewal
- **Status:** ✅ **Active**

**⚠️ Important:**
- Product IDs must match exactly (case-sensitive)
- Both must be **Active** (not Draft)
- Wait 2-4 hours after creation for propagation to store

### 2. Add License Testers

**Location:** Play Console → Your App → **Setup** → **License testing**

1. Click "Add license testers"
2. Add your Gmail address(es)
3. Add team members' Gmail addresses
4. Save changes

**Why:** License testers can make test purchases without being charged.

### 3. Build Development Build for Testing

Since `react-native-iap` is a native module, you **cannot test in Expo Go**.

```bash
# Install EAS CLI (if not already)
npm install -g eas-cli

# Login to Expo
eas login

# Build development client
eas build --profile development --platform android
```

**What happens:**
1. Build starts (check build page for progress)
2. Download APK when complete
3. Install on Android device/emulator
4. Device must have Google Play Services

**Installation:**
```bash
# Download APK from build page, then:
adb install path/to/build.apk

# OR transfer APK to device and install manually
```

### 4. Run Development Build

```bash
# Start Metro bundler
npm start

# Open the development build app on your device
# It will connect to Metro automatically
```

## 🧪 Testing Checklist

Once development build is installed:

- [ ] Open app on device (signed in with license tester account)
- [ ] Navigate to a premium feature (e.g., Solar Forecast)
- [ ] Verify paywall is shown
- [ ] Tap "Subscribe" → select yearly or monthly
- [ ] Complete test purchase (won't be charged)
- [ ] Verify features unlock immediately
- [ ] Close app and reopen
- [ ] Verify subscription is restored automatically

## 📋 Before Production Launch

- [ ] Implement server-side receipt validation (see docs/billing.md)
- [ ] Test subscription lifecycle (renewal, cancellation, expiration)
- [ ] Add iOS App Store support
- [ ] Configure Play Store listing with subscription details
- [ ] Create internal testing track release
- [ ] Get beta testers to verify
- [ ] Submit production build to Play Store

## 🔍 Troubleshooting

### "Item not available for purchase"

**Cause:** Products not found in Play Store

**Fix:**
1. Verify product IDs in Play Console match exactly
2. Ensure products are **Active** (not Draft)
3. Wait 2-4 hours after creating products
4. Clear Google Play Store cache on device

### "You are not eligible to purchase this item"

**Cause:** Not configured as license tester

**Fix:**
1. Add your Gmail to License Testing in Play Console
2. Ensure device signed in with same Gmail
3. Wait a few minutes after adding

### "react-native-iap is null"

**Cause:** Testing in Expo Go or module not included in build

**Fix:**
1. Must use development build (not Expo Go)
2. Rebuild with `eas build --profile development --platform android`

### Development build won't install

**Cause:** Unsigned or signature mismatch

**Fix:**
1. Uninstall any previous versions first
2. Enable "Install from unknown sources" on device
3. Rebuild with `eas build --clear-cache`

## 📚 Documentation

- [Billing Setup](./billing.md) - Complete setup guide
- [Billing Testing](./billing-testing.md) - Testing procedures
- [Paywall Integration](./paywall-integration.md) - Code examples

## 🚨 Common Mistakes

❌ Trying to test in Expo Go → Must use development build  
❌ Forgetting to activate subscriptions in Play Console  
❌ Using wrong product IDs → Must match exactly  
❌ Not adding yourself as license tester → Can't make test purchases  
❌ Testing with non-tester account → Will attempt real charge  

## ✅ Success Criteria

You'll know everything is working when:

1. Development build installs and runs on device
2. Paywall displays when accessing premium feature
3. Tapping subscribe opens Play Store purchase flow
4. Test purchase completes without charging
5. Features unlock immediately after purchase
6. App restart restores subscription automatically
7. Analytics events appear in logs

## 🆘 Need Help?

See comprehensive troubleshooting in `docs/billing-testing.md` or check:

- [react-native-iap Docs](https://react-native-iap.dooboolab.com/)
- [Google Play Billing Docs](https://developer.android.com/google/play/billing)
- [Expo EAS Build Docs](https://docs.expo.dev/build/introduction/)
