import { Stack, router, useRootNavigationState, usePathname } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { useEffect, useRef } from 'react';
import * as Notifications from 'expo-notifications';
import { Platform } from 'react-native';
import { AuthProvider, useAuth } from '../contexts/AuthContext';
import { hasActiveSubscription, shouldForcePaywall, isWebAllowed } from './routing/billingGuards';

/**
 * WebGate: routecastweather.com is informational/verification only.
 * On web, any route that isn't an allowed static page redirects to /landing.
 * This prevents browser-based login, signup, or any app content access.
 */
function WebGate() {
  const rootNavState = useRootNavigationState();
  const pathname = usePathname();

  useEffect(() => {
    if (Platform.OS !== 'web') return;
    if (!rootNavState?.key) return;

    if (!isWebAllowed(pathname)) {
      __DEV__ && console.log('[WebGate] blocking web access to', pathname, '→ /landing');
      router.replace('/landing');
    }
  }, [rootNavState?.key, pathname]);

  return null;
}

const UNAUTHED_OPEN_ROUTES = new Set([
  '/landing', '/welcome', '/contact', '/privacy', '/terms', '/login', '/signup', '/forgot-password', '/reset-password', '/verify-email',
]);

const AUTH_ENTRY_ROUTES = new Set([
  '/', '/landing', '/login', '/signup', '/verify-email', '/forgot-password', '/reset-password', '/subscription', '/welcome',
]);

// Global paywall guard: renders null (never blocks Stack from mounting).
// Fires once per session after user loads.
function PaywallGuard() {
  const { user, hasHydrated, isLoading: authLoading, accessToken } = useAuth();
  const rootNavState = useRootNavigationState();
  const pathname = usePathname();
  const firedRef = useRef(false);

  useEffect(() => {
    if (!rootNavState?.key) return;
    if (!hasHydrated || authLoading) return;

    // Signed-out users are handled by NativeAuthGuard.
    if (!accessToken) {
      firedRef.current = false;
      return;
    }

    if (hasActiveSubscription(user)) { firedRef.current = false; return; } // reset when user pays
    if (!user) { firedRef.current = false; return; } // wait for user to load before firing
    if (firedRef.current) return;

    if (!shouldForcePaywall(pathname, accessToken, user)) return;

    firedRef.current = true;
    __DEV__ && console.log('[paywall] blocking', pathname, '→ /subscription');
    router.replace('/subscription');
  }, [
    rootNavState?.key,
    hasHydrated,
    authLoading,
    accessToken,
    user,
    user?.is_premium,
    user?.email_verified,
    user?.subscription_status,
    pathname,
  ]);

  return null;
}

// Native-only auth/subscription guard. No-op during hydration to avoid flicker.
function NativeAuthGuard() {
  const { accessToken, user, hasHydrated, isLoading: authLoading, refreshUser } = useAuth();
  const rootNavState = useRootNavigationState();
  const pathname = usePathname();

  useEffect(() => {
    if (!hasHydrated || authLoading) return;
    if (!accessToken || user) return;

    refreshUser();
  }, [accessToken, authLoading, hasHydrated, refreshUser, user]);

  useEffect(() => {
    if (!rootNavState?.key) return; // navigator not ready
    if (!hasHydrated || authLoading) return; // still hydrating

    const seg = '/' + (pathname.split('/').filter(Boolean)[0] ?? '');

    // Unauthenticated users: force landing unless already on an allowlisted marketing/auth route.
    if (!accessToken) {
      if (pathname === '/' || (!UNAUTHED_OPEN_ROUTES.has(pathname) && !UNAUTHED_OPEN_ROUTES.has(seg))) {
        router.replace('/landing');
      }
      return;
    }

    // Restored entitled sessions should bypass landing/auth/paywall entry routes.
    if (pathname !== '/' && hasActiveSubscription(user) && (AUTH_ENTRY_ROUTES.has(pathname) || AUTH_ENTRY_ROUTES.has(seg))) {
      router.replace('/');
    }
  }, [accessToken, authLoading, hasHydrated, pathname, rootNavState?.key, user?.email_verified, user?.is_premium, user?.subscription_status]);

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
      <WebGate />
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
