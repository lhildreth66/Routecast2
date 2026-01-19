# Billing Testing & AAB Launch — Quick Start

**Follow this exact order** for testing Google Play subscriptions and launching.

## ✅ 1. Google Play Console — Create Subscriptions

**Path:** Play Console → **Monetize with Play** → **Products** → **Subscriptions**

Create two subscriptions with **exact** IDs:
- `boondocking_pro_monthly`
- `boondocking_pro_yearly`

For each:
1. Activate at least one **base plan**
2. Set price (can be anything for testing)
3. **Save + activate**

⚠️ **IDs must match exactly (case-sensitive).**

---

## ✅ 2. Add Yourself as License Tester (CRITICAL)

**Path:** Play Console → **Settings** → **License testing**

**Add:**
- The Google account email on your test phone

**This prevents:**
- ❌ "Item not available"
- ❌ Purchase silently failing

---

## ✅ 3. Create Internal Testing Track

**Path:** Play Console → **Testing** → **Internal testing**

1. Create track
2. Add yourself as tester
3. Save the Play Store install link (bookmark it)

---

## ✅ 4. Build the Android AAB with EAS (Production Build)

From your repo:

```bash
eas build -p android --profile production
```

**This will:**
- ✅ Include react-native-iap
- ✅ Produce a signed .aab
- ⏱️ Take ~10-20 minutes

**Wait for build to complete**, then download the AAB.

---

## ✅ 5. Upload AAB to Internal Testing

**Back in Play Console:**

1. Upload the AAB to **Internal testing**
2. Submit for review (usually minutes-hours)
3. Once ready → use the tester install link

⚠️ **Do NOT sideload the APK for billing tests.**  
Billing only works correctly when installed from Play Store.

---

## ✅ 6. Test the Full Paid Flow on Real Device

**On your phone (installed from Play Store internal link):**

Test both plans:
- [ ] Monthly
- [ ] Yearly

**Confirm:**
- [ ] ✅ Paywall opens
- [ ] ✅ Purchase completes
- [ ] ✅ App unlocks immediately
- [ ] ✅ Kill app → reopen → still unlocked
- [ ] ✅ Restore purchases works

---

## 🧠 What "Ready for Launch" Looks Like

You are **launch-ready** when:
- ✅ Internal testing purchase succeeds
- ✅ Unlock persists across restart
- ✅ No crashes in billing flow

**At that point:**  
➡️ You can promote **Internal → Production**  
(or do a **Closed test** first if you want extra safety)

---

## 🚨 Common Issues

### "Item not available for purchase"

**Cause:** Product IDs don't match or not activated

**Fix:**
1. Verify IDs in Play Console: `boondocking_pro_monthly`, `boondocking_pro_yearly`
2. Ensure both subscriptions are **Active** (not Draft)
3. Wait 2-4 hours after creating for propagation

### "You are not eligible to purchase"

**Cause:** Not added as license tester

**Fix:**
1. Play Console → Settings → License testing
2. Add your Gmail address
3. Wait a few minutes

### Purchase silently fails

**Cause:** Testing with sideloaded APK instead of Play Store install

**Fix:**
1. Uninstall app
2. Install from Play Store internal testing link only
3. Ensure device has Google Play Services

### Features don't unlock after purchase

**Cause:** Entitlement verification not running

**Fix:**
1. Check console logs for errors
2. Verify `verifyEntitlements` runs on app start
3. Force close and reopen app
4. Check AsyncStorage for `entitlements_v1` key

---

## 📱 Testing Checklist

Use this before promoting to production:

**Fresh Install:**
- [ ] Install from Play Store internal link
- [ ] Navigate to premium feature
- [ ] Paywall shows
- [ ] Complete purchase (monthly)
- [ ] Features unlock immediately
- [ ] All 8 premium features accessible

**Persistence:**
- [ ] Close app completely
- [ ] Reopen app
- [ ] Features still unlocked
- [ ] No paywall shown

**Restore:**
- [ ] Uninstall app
- [ ] Reinstall from Play Store
- [ ] Features unlock on first launch (no purchase needed)

**Second Plan:**
- [ ] Cancel first subscription (Play Store → Subscriptions)
- [ ] Wait for cancellation
- [ ] Purchase yearly plan
- [ ] Verify unlock

**Multi-Device:**
- [ ] Install on second device with same Google account
- [ ] Subscription detected automatically
- [ ] Features unlock without purchase

---

## ⏭️ After Internal Testing Succeeds

1. **Optional:** Run Closed Testing
   - Invite beta testers
   - Get feedback on billing flow
   - Fix any issues

2. **Promote to Production:**
   - Play Console → Testing → Internal testing
   - Click "Promote to Production"
   - Submit for review
   - Usually approved within 24-48 hours

3. **Monitor:**
   - Check crash reports
   - Monitor subscription metrics
   - Watch for billing-related support requests

---

## 📚 Detailed Documentation

For more details, see:
- [docs/billing.md](./billing.md) - Complete setup guide
- [docs/billing-testing.md](./billing-testing.md) - Comprehensive testing procedures
- [docs/paywall-integration.md](./paywall-integration.md) - Code integration examples
- [docs/next-steps-billing.md](./next-steps-billing.md) - Detailed next steps

---

## 🎯 Success Criteria Summary

**You're ready for production when:**

✅ All 6 steps above completed without errors  
✅ Both subscription plans work  
✅ Unlock persists across restarts  
✅ Restore purchases works  
✅ No crashes in billing flow  
✅ Analytics events tracked correctly  

**Then:** Promote to Production and launch! 🚀
