# Clean Deploy Instructions

## Files to copy to fresh main branch:

### 1. NEW FILE: frontend/app/landing.tsx
Copy entire file from this branch.

### 2. MODIFIED: frontend/app/_layout.tsx
Add this line after `<Stack.Screen name="index" />`:
```tsx
<Stack.Screen name="landing" />
```

### 3. MODIFIED: frontend/app/index.tsx
Add these imports and useEffect at component start:
- Import `Platform` from react-native (if not already)
- Destructure `isLoading` from useAuth()
- Add redirect useEffect for non-authenticated web users

### 4. MODIFIED: backend/routers/webhooks.py
- Change router prefix from `/webhook` to `/stripe`
- Change @router.post("/stripe") to @router.post("/webhook")
- Fix determine_plan() to return 'yearly' not 'annual'
- Fix handle_subscription_deleted() to set subscription_plan='free'
- Change from BackgroundTasks to synchronous processing

### 5. MODIFIED: backend/services/subscription_service.py
- Add 'canceling' and 'past_due' to premium status check

### 6. MODIFIED: render.yaml
Change these two values only:
- API_URL: https://api.routecastweather.com → https://routecastweather.com
- EXPO_PUBLIC_BACKEND_URL: https://api.routecastweather.com → https://routecastweather.com

## Verification:
- grep -r "api.routecastweather" should return NO results in code files
- Webhook path should be /api/stripe/webhook
