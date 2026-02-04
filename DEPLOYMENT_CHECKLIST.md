# Routecast Deployment Checklist

## 1. CRITICAL CONFIGURATION

### Backend URL (PRIMARY)
```
https://routecast-backend.onrender.com
```

### ❌ NEVER USE (SUSPENDED SERVICE)
```
https://routecast2.onrender.com
```

### Health Endpoint
- **Path:** `/health`
- **Response:** `{"status": "ok", "timestamp": "2026-02-04T..."}`
- **Purpose:** App connection testing, liveness checks

---

## 2. FILES TO VERIFY BEFORE ANY BUILD

### Backend URL Configuration Files:
1. **`frontend/app/apiConfig.ts`** (Lines 3-6)
   - Primary: `Constants.expoConfig?.extra?.API_BASE`
   - Fallback: `'https://routecast-backend.onrender.com'`
   - ⚠️ CRITICAL: Verify fallback URL is correct

2. **`frontend/app.json`** (Line 62)
   - `"extra": { "API_BASE": "https://routecast-backend.onrender.com" }`

3. **`frontend/eas.json`** (Lines 18, 27)
   - Preview build: `"EXPO_PUBLIC_BACKEND_URL": "https://routecast-backend.onrender.com"`
   - Production build: `"EXPO_PUBLIC_BACKEND_URL": "https://routecast-backend.onrender.com"`

### Template Literal Issues:
4. **`frontend/app/radar-map.tsx`** (Lines 279-287)
   - ⚠️ Verify popup content uses string concatenation, NOT nested template literals
   - CORRECT: `'<div>' + variable + '</div>'`
   - WRONG: `` `<div>${variable}</div>` `` (inside another template literal)

---

## 3. WORKING BUILD INFO

### Version Details
- **App Version:** 1.0.109
- **Version Code:** 113
- **Git Commit:** `0b3b8bd903a94c95a34b62c56fe8cdc4b6cf2ebb`
- **Git Tag:** `v1.0.113-working`
- **Build Date:** February 4, 2026

### EAS Build
- **Platform:** Android (AAB)
- **Profile:** Production
- **Download:** https://expo.dev/artifacts/eas/tLXG3gzfDRRN41715Cd7ih.aab
- **Build Logs:** https://expo.dev/accounts/promedtrans01/projects/routecast2/builds/e0edca42-fd8f-4c79-8665-ff9bca83f662

### Key Fixes Included
- ✅ Correct backend URL in all configuration files
- ✅ Fixed radar map popup template literal syntax
- ✅ Enhanced debugging logs for radar map WebView
- ✅ Backend `/health` endpoint added

---

## 4. TO RESTORE THIS VERSION

### Checkout Tagged Version
```bash
git checkout v1.0.113-working
```

### Rebuild from Tag
```bash
cd frontend
eas build --platform android --profile production
```

### Verify Configuration
```bash
# Check API_BASE in app.json
grep -A 2 '"API_BASE"' frontend/app.json

# Check fallback in apiConfig.ts
grep -A 2 'API_BASE' frontend/app/apiConfig.ts
```

---

## 5. BACKEND ENDPOINTS THAT MUST EXIST

### Health & Status
- `GET /health` - Root health check (non-prefixed)
- `GET /api/health` - API health check
- `GET /api/` - API info

### Radar & Weather Alerts
- `GET /api/radar/alerts/map` - Weather alerts with geometries (CRITICAL for radar map)
- `GET /api/radar/tiles` - Radar tile information
- `GET /api/radar/alert-types` - Available alert types

### Route & Weather
- `POST /api/route/weather` - Get weather along route
- `GET /api/routes/favorites` - Get favorite routes (CRITICAL for home screen)
- `POST /api/routes/favorites` - Add favorite
- `DELETE /api/routes/favorites/{route_id}` - Remove favorite

### Geocoding
- Endpoints under `/api/geocode/` (used for location autocomplete)

### Billing & Premium
- `POST /api/billing/verify` - Verify purchase
- `POST /api/billing/validate-subscription` - Check subscription status
- `GET /api/billing/features` - Get feature availability

---

## 6. PRE-BUILD VERIFICATION SCRIPT

```bash
#!/bin/bash
# Run this before every build

echo "Checking backend URL configuration..."

# Check app.json
API_BASE_APP_JSON=$(grep -A 1 '"API_BASE"' frontend/app.json | grep 'routecast-backend.onrender.com')
if [ -z "$API_BASE_APP_JSON" ]; then
    echo "❌ ERROR: Wrong backend URL in app.json"
    exit 1
fi

# Check apiConfig.ts fallback
API_BASE_CONFIG=$(grep 'routecast-backend.onrender.com' frontend/app/apiConfig.ts)
if [ -z "$API_BASE_CONFIG" ]; then
    echo "❌ ERROR: Wrong fallback URL in apiConfig.ts"
    exit 1
fi

# Check eas.json
EAS_BACKEND=$(grep 'EXPO_PUBLIC_BACKEND_URL.*routecast-backend.onrender.com' frontend/eas.json | wc -l)
if [ "$EAS_BACKEND" -lt 2 ]; then
    echo "❌ ERROR: Wrong backend URL in eas.json"
    exit 1
fi

# Check for nested template literals in radar-map
NESTED_LITERALS=$(grep -n '\\\${' frontend/app/radar-map.tsx)
if [ ! -z "$NESTED_LITERALS" ]; then
    echo "⚠️  WARNING: Found escaped template literals in radar-map.tsx:"
    echo "$NESTED_LITERALS"
    echo "Verify these are intentional (not in popup content)"
fi

echo "✅ All checks passed!"
echo "Backend URL: https://routecast-backend.onrender.com"
```

---

## 7. COMMON ISSUES & SOLUTIONS

### Issue: "No backend connectivity"
**Cause:** Wrong backend URL configured  
**Solution:**
1. Check all 3 files: `app.json`, `apiConfig.ts`, `eas.json`
2. Verify NOT using `routecast2.onrender.com`
3. Rebuild app with correct URL

### Issue: "Radar map shows white screen"
**Cause:** Template literal syntax error in popup content  
**Solution:**
1. Check `frontend/app/radar-map.tsx` lines 279-287
2. Ensure using string concatenation: `'<div>' + variable + '</div>'`
3. NOT nested template literals: `` `<div>${variable}</div>` ``

### Issue: "Test Backend Connection fails"
**Cause:** Backend `/health` endpoint not deployed  
**Solution:**
1. Verify backend has `/health` endpoint (commit `0b3b8bd`)
2. Check Render dashboard for successful deployment
3. Test: `curl https://routecast-backend.onrender.com/health`

### Issue: "Backend shows as suspended"
**Cause:** Using wrong backend URL (`routecast2.onrender.com`)  
**Solution:**
1. Update to `routecast-backend.onrender.com`
2. Search entire codebase: `grep -r "routecast2.onrender.com" frontend/`
3. Replace all instances

---

## 8. DEPLOYMENT WORKFLOW

### Standard Deployment
1. Make code changes
2. Run pre-build verification script
3. Commit and push to main
4. Wait for backend to auto-deploy (if backend changed)
5. Build app: `eas build --platform android --profile production`
6. Download AAB from provided link
7. Upload to Google Play Console
8. Test on device before promoting to production

### Emergency Rollback
```bash
# Revert to last working version
git checkout v1.0.113-working

# Rebuild
cd frontend
eas build --platform android --profile production

# Deploy to Play Store immediately
```

---

## 9. TESTING CHECKLIST

Before uploading to Play Store, verify:

- [ ] Debug panel shows correct backend URL
- [ ] "Test Backend Connection" succeeds
- [ ] Favorites load on home screen
- [ ] Location autocomplete works
- [ ] Route weather check completes
- [ ] Radar map displays (not white screen)
- [ ] Radar map shows weather alerts (if any active)
- [ ] Premium features accessible (if subscribed)

---

## 10. MONITORING

### Backend Health
- Check: `https://routecast-backend.onrender.com/health`
- Should return: `{"status": "ok", "timestamp": "..."}`
- Monitor Render dashboard for uptime

### App Performance
- Monitor Google Play Console for crash reports
- Check user reviews for connectivity issues
- Watch for "backend connection failed" reports

---

**Last Updated:** February 4, 2026  
**Maintained By:** Development Team  
**Questions:** Contact repository owner
