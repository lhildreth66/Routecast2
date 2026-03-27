import { Stack, router, useRootNavigationState, usePathname } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { useEffect, useRef } from 'react';
import * as Notifications from 'expo-notifications';
import { Platform } from 'react-native';
import { AuthProvider, useAuth } from '../contexts/AuthContext';
import { useBilling } from './hooks/useBilling';

// Routes that unpaid-but-verified users are allowed to visit.
// Everything else redirects to /subscription (the paywall).
const PAYWALL_OPEN_ROUTES = new Set([
  '/login', '/signup', '/verify-email', '/subscription',
  '/landing', '/terms', '/privacy', '/contact',
  '/forgot-password', '/reset-password',
  '/welcome',   // post-Stripe activation page (issues JWT before redirect)
  '/account',   // users need account access to manage billing / cancel
]);

// Global paywall guard: renders null (never blocks Stack from mounting).
// Fires once per session after user loads.
function PaywallGuard() {
  const { user, hasHydrated, isLoading: authLoading, accessToken } = useAuth();
  const rootNavState = useRootNavigationState();
  const pathname = usePathname();
  const firedRef = useRef(false);

  // STRIPE DISABLED - Google Play submission - do not delete
  /*
  useEffect(() => {
    if (!rootNavState?.key) return;
    if (!hasHydrated || authLoading) return;
    if (!accessToken || !user) return;     // not authenticated or not loaded
    if (user.is_premium) { firedRef.current = false; return; } // reset when user pays
    if (!user.email_verified) return;     // pre-verification handled by verify-email itself
    if (firedRef.current) return;

    // Normalise pathname to its first segment so /subscription/success still passes.
    const seg = '/' + (pathname.split('/').filter(Boolean)[0] ?? '');
    if (PAYWALL_OPEN_ROUTES.has(pathname) || PAYWALL_OPEN_ROUTES.has(seg)) return;

    firedRef.current = true;
    __DEV__ && console.log('[paywall] blocking', pathname, '→ /subscription');
    router.replace('/subscription');
  }, [rootNavState?.key, hasHydrated, authLoading, accessToken, user?.is_premium, user?.email_verified, pathname]);
  */

  return null;
}

// Native-only auth/subscription guard. No-op during hydration to avoid flicker.
function NativeAuthGuard() {
  const { accessToken, hasHydrated, isLoading: authLoading } = useAuth();
  const { entitlementActive, isLoading: billingLoading } = useBilling();
  const rootNavState = useRootNavigationState();
  const pathname = usePathname();

  useEffect(() => {
    if (Platform.OS === 'web') return;
    if (!rootNavState?.key) return; // navigator not ready
    if (!hasHydrated || authLoading || billingLoading) return; // still hydrating

    const seg = '/' + (pathname.split('/').filter(Boolean)[0] ?? '');

    // Allow unauthenticated users to reach subscription and purchase via Play Billing.
    if (!accessToken) {
      const allowlist = new Set(['/subscription', '/login', '/signup', '/landing', '/welcome']);
      if (!entitlementActive && !allowlist.has(pathname) && !allowlist.has(seg)) {
        router.replace('/subscription');
      }
      // If entitlement is active (purchased as guest), permit app access without forcing login.
      return;
    }

    // Authenticated but not subscribed: route to subscription.
    if (!entitlementActive && seg !== '/subscription' && seg !== '/login' && seg !== '/signup') {
      router.replace('/subscription');
    }
  }, [accessToken, authLoading, billingLoading, entitlementActive, hasHydrated, pathname, rootNavState?.key]);

  return null;
}

// Configure notifications
Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
    shouldSetBadge: false,
    shouldShowBanner: true,
    shouldShowList: true,
  }),
});

export default function RootLayout() {
  useEffect(() => {
    // Request notification permissions
    async function requestPermissions() {
      if (Platform.OS !== 'web') {
        const { status } = await Notifications.requestPermissionsAsync();
        if (status !== 'granted') {
          console.log('Notification permissions not granted');
        }
      }
    }
    requestPermissions();
  }, []);

  return (
    <AuthProvider>
      <StatusBar style="light" />
      <NativeAuthGuard />
      <PaywallGuard />
      <Stack
        screenOptions={{
          headerShown: false,
          contentStyle: { backgroundColor: '#0a0a0a' },
          // 'slide_from_right' is not supported on web and causes Expo Router
          // to generate undefined navigation keys (?__EXPO_ROUTER_key=undefined),
          // which triggers a full page reload instead of SPA navigation.
          animation: Platform.OS === 'web' ? 'none' : 'slide_from_right',
        }}
      >
        <Stack.Screen name="landing" />
        <Stack.Screen name="index" redirect={false} options={{ href: '/landing' }} />
        <Stack.Screen name="route" />
        {/* Auth Screens */}
        <Stack.Screen name="login" />
        <Stack.Screen name="signup" />
        <Stack.Screen name="verify-email" />
        <Stack.Screen name="forgot-password" />
        <Stack.Screen name="reset-password" />
        <Stack.Screen name="subscription" />
        <Stack.Screen name="account" />
        {/* Boondockers Screens */}
        <Stack.Screen name="boondockers" />
        <Stack.Screen name="camp-prep-checklist" />
        <Stack.Screen name="free-camping" />
        <Stack.Screen name="casinos" />
        <Stack.Screen name="walmart-parking" />
        <Stack.Screen name="cracker-barrel" />
        <Stack.Screen name="dump-station" />
        <Stack.Screen name="last-chance" />
        <Stack.Screen name="rv-dealership" />
        <Stack.Screen name="solar-forecast" />
        <Stack.Screen name="propane-usage" />
        <Stack.Screen name="wind-shelter" />
        <Stack.Screen name="connectivity" />
        <Stack.Screen name="campsite-index" />
        {/* Tractor Trailer Screens */}
        <Stack.Screen name="tractor-trailer" />
        <Stack.Screen name="truck-stops" />
        <Stack.Screen name="weigh-stations" />
        <Stack.Screen name="truck-parking" />
        <Stack.Screen name="low-clearance" />
        <Stack.Screen name="truck-services" />
        <Stack.Screen name="truck-restrictions" />
        {/* Shared/Supporting Screens */}
        <Stack.Screen name="truckerAlerts" />
        <Stack.Screen name="radar-map" />
        <Stack.Screen name="route-alerts" />
        <Stack.Screen name="weather-alerts" />
        <Stack.Screen name="how-to-use" />
      </Stack>
    </AuthProvider>
  );
}
