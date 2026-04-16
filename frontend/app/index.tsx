import React, { useState, useEffect, forwardRef, useCallback, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TextInput,
  TextInputProps,
  TouchableOpacity,
  ScrollView,
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  Keyboard,
  Switch,
  Modal,
  Dimensions,
  Alert,
} from 'react-native';

// Custom TextInput that disables browser autofill on web
const NoAutofillInput = forwardRef<any, TextInputProps>((props, ref) => {
  if (Platform.OS === 'web') {
    return (
      <TextInput
        {...props}
        ref={ref}
        // @ts-ignore - web-specific attributes
        autoComplete="off"
        autoCorrect={false}
        autoCapitalize="none"
        data-form-type="other"
        data-lpignore="true"
        data-1p-ignore="true"
        aria-autocomplete="none"
        spellCheck={false}
      />
    );
  }
  return <TextInput {...props} ref={ref} />;
});
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons, MaterialCommunityIcons } from '@expo/vector-icons';
import { router, usePathname, useRootNavigationState } from 'expo-router';
import axios from 'axios';
import AsyncStorage from '@react-native-async-storage/async-storage';
import DateTimePicker from '@react-native-community/datetimepicker';
import { format } from 'date-fns';
import { WebView } from 'react-native-webview';
import { useAuth } from '../contexts/AuthContext';
import * as Notifications from 'expo-notifications';
import { registerWebPush, deleteWebPushSubscription } from '../lib/webPush';
import Constants from 'expo-constants';

const { width: SCREEN_WIDTH } = Dimensions.get('window');

const API_BASE = process.env.EXPO_PUBLIC_BACKEND_URL || '';
const IS_WEB = Platform.OS === 'web';

// ─ client-side persistence keys ──────────────────────────────────────────
const RECENT_ROUTES_KEY = 'rc_recent_routes_v1';
const FAVORITES_KEY = 'rc_favorite_routes_v1';

// Vehicle types for safety scoring
const VEHICLE_TYPES = [
  { id: 'car', label: 'Car/Sedan', icon: 'car-sport-outline' },
  { id: 'suv', label: 'SUV', icon: 'car-outline' },
  { id: 'truck', label: 'Pickup Truck', icon: 'car-outline' },
  { id: 'semi', label: 'Semi Truck', icon: 'bus-outline' },
  { id: 'rv', label: 'RV/Motorhome', icon: 'home-outline' },
  { id: 'motorcycle', label: 'Motorcycle', icon: 'bicycle-outline' },
  { id: 'trailer', label: 'Vehicle + Trailer', icon: 'train-outline' },
];

interface StopPoint {
  location: string;
  type: string;
}

interface SavedRoute {
  id: string;
  origin: string;
  destination: string;
  stops?: StopPoint[];
  is_favorite?: boolean;
  created_at: string;
}

interface AutocompleteSuggestion {
  place_name: string;
  short_name: string;
  coordinates: number[];
}

export default function HomeScreen() {
  const { user, isAuthenticated, accessToken, isPremium, isLoading: authLoading, hasHydrated, refreshUser, refreshAccessToken } = useAuth();
  const isMobileWeb = IS_WEB && SCREEN_WIDTH < 768;
  const pathname = usePathname();

  // Gate navigation on the root navigator being mounted.
  // Now that AuthProvider always renders children unconditionally, Stack mounts
  // immediately. We guard with useRootNavigationState so router.replace is
  // never called before the navigator is ready.
  const rootNavState = useRootNavigationState();

  // Cold-start: tokens restored from storage but user object not yet fetched.
  // index.tsx is the first screen most authenticated users land on, so fetch
  // the user profile here. The 30s cooldown inside refreshUser() prevents loops.
  useEffect(() => {
    if (accessToken && !user && !authLoading) {
      refreshUser();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accessToken, authLoading]); // intentionally omit user to avoid re-run after user loads

  useEffect(() => {
    __DEV__ && console.log('[guard] check – navReady:', !!rootNavState?.key, 'hydrated:', hasHydrated, 'authLoading:', authLoading, 'accessToken:', !!accessToken, 'platform:', Platform.OS);
    if (!rootNavState?.key) return; // navigator not yet mounted – skip
    if (Platform.OS === 'web' && hasHydrated && !authLoading && !accessToken) {
      const path = pathname || '/';
      if (path === '/landing') return;
      if (path === '/') {
        router.replace('/landing');
        return;
      }
      __DEV__ && console.log('[guard] redirecting to /login');
      router.replace('/login');
    }
  }, [rootNavState?.key, accessToken, authLoading, hasHydrated, pathname]);

  // Subscription gate removed: replaced by global PaywallGuard in _layout.tsx.
  // PaywallGuard handles verified+!premium users on ALL routes, not just /.
  // This avoids the need for a per-screen ref and removes the ping-pong.

  const [origin, setOrigin] = useState('');
  const [destination, setDestination] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [alertsEnabled, setAlertsEnabled] = useState(false);
  const [recentRoutes, setRecentRoutes] = useState<SavedRoute[]>([]);
  const [favoriteRoutes, setFavoriteRoutes] = useState<SavedRoute[]>([]);
  const [showFavorites, setShowFavorites] = useState(false);
  const [saveMessage, setSaveMessage] = useState('');
  
  // Autocomplete state
  const [originSuggestions, setOriginSuggestions] = useState<AutocompleteSuggestion[]>([]);
  const [destSuggestions, setDestSuggestions] = useState<AutocompleteSuggestion[]>([]);
  const [showOriginSuggestions, setShowOriginSuggestions] = useState(false);
  const [showDestSuggestions, setShowDestSuggestions] = useState(false);
  const [autocompleteLoading, setAutocompleteLoading] = useState(false);
  
  // Vehicle & Trucker mode
  const [vehicleType, setVehicleType] = useState('car');
  const [truckerMode, setTruckerMode] = useState(false);
  const [showVehicleSelector, setShowVehicleSelector] = useState(false);
  const [vehicleHeight, setVehicleHeight] = useState('13.6'); // Default truck height in feet
  
  // Departure time
  const [departureTime, setDepartureTime] = useState(new Date());
  const [showDatePicker, setShowDatePicker] = useState(false);
  const [pickerMode, setPickerMode] = useState<'date' | 'time'>('date');
  const [pendingDate, setPendingDate] = useState<Date>(new Date());
  const [useCustomTime, setUseCustomTime] = useState(false);
  
  // Multi-stop
  const [stops, setStops] = useState<StopPoint[]>([]);
  const [showAddStop, setShowAddStop] = useState(false);
  const [newStopLocation, setNewStopLocation] = useState('');
  const [newStopType, setNewStopType] = useState('stop');
  
  // Radar map state
  const [showRadarMap, setShowRadarMap] = useState(false);
  
  // Push notification state
  const [pushLoading, setPushLoading] = useState(false);

  const getAuthToken = async (): Promise<string | null> => {
    // Prefer in-memory context token; fall back to persisted keys for resilience
    if (isAuthenticated && accessToken) return accessToken;
    const tokens = await AsyncStorage.multiGet(['accessToken', 'access_token']);
    const found = tokens.map(([, v]) => v).find((v) => !!v) || null;
    return found;
  };

  // Load push notification settings on mount
  useEffect(() => {
    loadPushSettings();
  }, [isAuthenticated]);

  const loadPushSettings = async () => {
    if (!isAuthenticated) return;
    try {
      const token = await getAuthToken();
      if (!token) return;
      
      const response = await axios.get(`${API_BASE}/api/push/settings`, {
        headers: { Authorization: `Bearer ${token}` },
        withCredentials: true,
      });
      setAlertsEnabled(response.data.push_enabled || false);
    } catch (err) {
      console.log('Failed to load push settings:', err);
    }
  };

  const handleAlertsToggle = async (nextEnabled: boolean) => {
    const authToken = await getAuthToken();

    if (IS_WEB) {
      if (pushLoading) return;
      const prevEnabled = alertsEnabled;
      setAlertsEnabled(nextEnabled); // optimistic UI so toggle moves immediately
      setPushLoading(true);
      try {
        if (!authToken) {
          Alert.alert('Sign In Required', 'Please sign in to manage push notifications.');
          setAlertsEnabled(prevEnabled);
          return;
        }

        if (!nextEnabled) {
          await deleteWebPushSubscription(`${API_BASE}/api`, authToken);
          await axios.post(
            `${API_BASE}/api/push/settings`,
            { push_enabled: false, push_token: null, platform: 'web' },
            { headers: { Authorization: `Bearer ${authToken}` }, withCredentials: true },
          );
          await AsyncStorage.removeItem('expoPushToken');
          setAlertsEnabled(false);
          return;
        }

        const result = await registerWebPush(`${API_BASE}/api`, authToken);
        console.log('[push-toggle] web register result', result);

        // If the initial save failed but we still have a subscription, retry the POST once to ensure it reaches the backend.
        if (!result.saved && result.subscription) {
          try {
            const retry = await registerWebPush(`${API_BASE}/api`, authToken);
            __DEV__ && console.log('[push-toggle] web register retry result', retry);
            if (retry.saved) {
              result.saved = true;
              result.responseStatus = retry.responseStatus;
              result.responseBody = retry.responseBody;
            }
          } catch (retryErr) {
            __DEV__ && console.log('[push-toggle] web register retry failed', retryErr);
          }
        }

        if (!result.supported) {
          Alert.alert('Notifications Unsupported', 'This browser does not support Web Push.');
          setAlertsEnabled(false);
          return;
        }

        if (result.permission !== 'granted') {
          Alert.alert(
            'Enable Notifications',
            'Please allow notifications. On iPhone/iPad, use Safari, add Routecast to your Home Screen, open it, then allow notifications.',
          );
          setAlertsEnabled(false);
          return;
        }

        const pseudoToken = result.subscription?.endpoint
          ? `web:${result.subscription.endpoint.slice(-24)}`
          : undefined;

        console.log('[push-toggle] about to save settings push_enabled=', nextEnabled, 'pseudoToken=', pseudoToken);
        await axios.post(
          `${API_BASE}/api/push/settings`,
          { push_enabled: nextEnabled && !!result.saved, push_token: pseudoToken, platform: 'web' },
          { headers: { Authorization: `Bearer ${authToken}` }, withCredentials: true },
        );
        if (pseudoToken) {
          await AsyncStorage.setItem('expoPushToken', pseudoToken);
        }
        const finalState = nextEnabled && !!result.saved;
        setAlertsEnabled(finalState);
      } catch (err: any) {
        console.warn('[push-toggle] web push error', err?.message ?? err);
        setAlertsEnabled(prevEnabled);
        Alert.alert('Error', 'Could not enable web push notifications.');
      } finally {
        setPushLoading(false);
      }
      return;
    }

    if (!isAuthenticated) {
      Alert.alert('Sign In Required', 'Please sign in to enable push notifications.');
      return;
    }

    // Android/mobile path only
    if (Platform.OS !== 'android') {
      Alert.alert('Unsupported', 'Push alerts are currently supported on Android mobile only.');
      return;
    }

    setPushLoading(true);
    try {
      let pushToken: string | null = null;

      if (nextEnabled) {
        const { status: existingStatus } = await Notifications.getPermissionsAsync();
        let finalStatus = existingStatus;
        __DEV__ && console.log('[push-toggle] existing permission status:', existingStatus);

        if (existingStatus !== 'granted') {
          const { status } = await Notifications.requestPermissionsAsync();
          finalStatus = status;
          __DEV__ && console.log('[push-toggle] after request, status:', finalStatus);
        }

        if (finalStatus !== 'granted') {
          setAlertsEnabled(false);
          Alert.alert(
            'Enable Notifications',
            'Notifications are currently disabled for this app. Please enable them in Settings to receive route alerts.',
            [{ text: 'OK' }],
          );
          return;
        }

        try {
          const tokenData = await Notifications.getExpoPushTokenAsync({
            projectId: Constants.expoConfig?.extra?.eas?.projectId,
          });
          pushToken = tokenData.data;
          __DEV__ && console.log('[push-toggle] push token obtained:', pushToken?.slice(0, 20), '...');
          await AsyncStorage.setItem('expoPushToken', pushToken);
        } catch (tokenErr) {
          console.warn('[push-toggle] push token unavailable (Android)', tokenErr);
          setAlertsEnabled(false);
          Alert.alert('Push Setup Failed', 'Could not get a push token. Please try again after enabling notifications.');
          return;
        }
      } else {
        // Disable: clear stored token
        await AsyncStorage.removeItem('expoPushToken');
      }

      await (async () => {
        const doPost = async (token: string) =>
          axios.post(
            `${API_BASE}/api/push/settings`,
            { push_enabled: nextEnabled, push_token: pushToken, platform: Platform.OS },
            { headers: { Authorization: `Bearer ${token}` }, withCredentials: true },
          );
        try {
          await doPost(authToken!);
        } catch (firstErr: any) {
          if (firstErr?.response?.status === 401) {
            // Token expired — refresh once and retry
            __DEV__ && console.log('[push-toggle] 401 on settings — refreshing token');
            const refreshed = await refreshAccessToken();
            const freshToken = refreshed ? await getAuthToken() : null;
            if (freshToken) {
              await doPost(freshToken);
            } else {
              throw firstErr;
            }
          } else {
            throw firstErr;
          }
        }
      })();
      setAlertsEnabled(nextEnabled && !!pushToken);
      __DEV__ && console.log('[push-toggle] saved to backend – push_enabled:', nextEnabled, 'hasToken:', !!pushToken);
    } catch (err: any) {
      console.warn('[push-toggle] backend save error – reverting:', err?.message ?? err);
      setAlertsEnabled(false);
      const detail = err?.response?.data?.detail;
      const message = typeof detail === 'string' ? detail : 'Could not save notification settings. Please try again.';
      Alert.alert('Push Setup Failed', message);
    } finally {
      setPushLoading(false);
    }
  };

  useEffect(() => {
    fetchRecentRoutes();
    fetchFavoriteRoutes();
    loadCachedRoute();
  }, []);

  const loadCachedRoute = async () => {
    try {
      const cached = await AsyncStorage.getItem('lastRoute');
      if (cached) {
        const data = JSON.parse(cached);
        // Optionally pre-fill from cache
      }
    } catch (e) {
      console.log('No cached route');
    }
  };

  // Debounced autocomplete function
  const fetchAutocomplete = async (query: string, type: 'origin' | 'destination') => {
    if (query.length < 2) {
      if (type === 'origin') {
        setOriginSuggestions([]);
        setShowOriginSuggestions(false);
      } else {
        setDestSuggestions([]);
        setShowDestSuggestions(false);
      }
      return;
    }

    setAutocompleteLoading(true);
    try {
      const response = await axios.get(`${API_BASE}/api/geocode/autocomplete`, {
        params: { query, limit: 5 }
      });
      
      if (type === 'origin') {
        setOriginSuggestions(response.data);
        setShowOriginSuggestions(response.data.length > 0);
      } else {
        setDestSuggestions(response.data);
        setShowDestSuggestions(response.data.length > 0);
      }
    } catch (err) {
      console.log('Autocomplete error:', err);
    } finally {
      setAutocompleteLoading(false);
    }
  };

  // Debounce timer refs
  const originDebounceRef = React.useRef<ReturnType<typeof setTimeout> | null>(null);
  const destDebounceRef = React.useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleOriginChange = (text: string) => {
    setOrigin(text);
    
    // Debounce autocomplete
    if (originDebounceRef.current) {
      clearTimeout(originDebounceRef.current);
    }
    originDebounceRef.current = setTimeout(() => {
      fetchAutocomplete(text, 'origin');
    }, 300);
  };

  const handleDestinationChange = (text: string) => {
    setDestination(text);
    
    // Debounce autocomplete
    if (destDebounceRef.current) {
      clearTimeout(destDebounceRef.current);
    }
    destDebounceRef.current = setTimeout(() => {
      fetchAutocomplete(text, 'destination');
    }, 300);
  };

  const selectOriginSuggestion = (suggestion: AutocompleteSuggestion) => {
    setOrigin(suggestion.place_name);
    setShowOriginSuggestions(false);
    setOriginSuggestions([]);
  };

  const selectDestSuggestion = (suggestion: AutocompleteSuggestion) => {
    setDestination(suggestion.place_name);
    setShowDestSuggestions(false);
    setDestSuggestions([]);
  };

  const fetchRecentRoutes = async () => {
    // 1. Try backend; if it returns data cache it locally
    try {
      const response = await axios.get(`${API_BASE}/api/routes/history`, { timeout: 8000 });
      const routes: SavedRoute[] = (response.data || []).slice(0, 10);
      if (routes.length > 0) {
        setRecentRoutes(routes.slice(0, 5));
        try { await AsyncStorage.setItem(RECENT_ROUTES_KEY, JSON.stringify(routes)); } catch {}
        return;
      }
    } catch (err) {
      console.log('fetchRecentRoutes backend error (falling back to local):', err);
    }
    // 2. Fall back to AsyncStorage
    try {
      const raw = await AsyncStorage.getItem(RECENT_ROUTES_KEY);
      if (raw) {
        const local: SavedRoute[] = JSON.parse(raw);
        setRecentRoutes(local.slice(0, 5));
      }
    } catch { /* corrupt storage – silently ignore */ }
  };

  const saveToLocalRecents = async (org: string, dest: string, stps: StopPoint[]) => {
    try {
      const raw = await AsyncStorage.getItem(RECENT_ROUTES_KEY);
      const existing: SavedRoute[] = raw ? JSON.parse(raw) : [];
      const entry: SavedRoute = {
        id: String(Date.now()),
        origin: org,
        destination: dest,
        stops: stps,
        is_favorite: false,
        created_at: new Date().toISOString(),
      };
      // Deduplicate by origin+destination, newest first
      const deduped = [entry, ...existing.filter(
        (r) => !(r.origin === org && r.destination === dest)
      )].slice(0, 10);
      await AsyncStorage.setItem(RECENT_ROUTES_KEY, JSON.stringify(deduped));
      setRecentRoutes(deduped.slice(0, 5));
    } catch { /* non-fatal */ }
  };

  const fetchFavoriteRoutes = async () => {
    // 1. Try backend
    try {
      const response = await axios.get(`${API_BASE}/api/routes/favorites`, { timeout: 8000 });
      const routes: SavedRoute[] = response.data || [];
      if (routes.length > 0) {
        setFavoriteRoutes(routes);
        try { await AsyncStorage.setItem(FAVORITES_KEY, JSON.stringify(routes)); } catch {}
        return;
      }
    } catch (err) {
      console.log('fetchFavoriteRoutes backend error (falling back to local):', err);
    }
    // 2. Fall back to AsyncStorage
    try {
      const raw = await AsyncStorage.getItem(FAVORITES_KEY);
      if (raw) {
        const local: SavedRoute[] = JSON.parse(raw);
        setFavoriteRoutes(local);
      }
    } catch { /* corrupt storage – silently ignore */ }
  };

  const handleGetWeather = async () => {
    if (!origin.trim() || !destination.trim()) {
      setError('Please enter both origin and destination');
      return;
    }

    Keyboard.dismiss();
    setLoading(true);
    setError('');

    try {
      const requestData: any = {
        origin: origin.trim(),
        destination: destination.trim(),
        stops: stops,
        vehicle_type: vehicleType,
        trucker_mode: truckerMode,
        vehicle_height_ft: truckerMode ? parseFloat(vehicleHeight) || 13.6 : null,
      };

      const savedPushToken = await AsyncStorage.getItem('expoPushToken');
      const hasSavedPushToken = !!savedPushToken;
      const pushTokenPrefix = savedPushToken ? savedPushToken.slice(0, 12) : null;
      if (savedPushToken) {
        requestData.push_token = savedPushToken;
        requestData.push_alerts_enabled = !!alertsEnabled;
      }
      
      if (useCustomTime) {
        requestData.departure_time = departureTime.toISOString();
      }

      const routeWeatherUrl = `${API_BASE}/api/route/weather`;
      console.log('[route-request]', {
        url: routeWeatherUrl,
        alertsEnabled,
        hasSavedPushToken,
        pushTokenPrefix,
        includesPushToken: Boolean(requestData.push_token),
      });

      const response = await axios.post(routeWeatherUrl, requestData);
      let routeData = response.data ?? {};

      // Follow-up call: fetch NWS hazard alerts (deferred from the main route call)
      const routeId = routeData?.id;
      if (routeId) {
        try {
          const alertsResp = await axios.get(
            `${API_BASE}/api/route/weather/alerts/${routeId}`,
            { timeout: 30000 }
          );
          const alertsData = alertsResp.data;
          if (alertsData) {
            const mergedAlerts =
              alertsData.alerts ??
              alertsData.hazard_alerts ??
              routeData.alerts ??
              [];
            routeData = {
              ...routeData,
              hazard_alerts: alertsData.hazard_alerts ?? routeData.hazard_alerts ?? [],
              alerts: mergedAlerts,
              road_conditions: alertsData.road_conditions ?? routeData.road_conditions ?? [],
              weather_conditions: alertsData.weather_conditions ?? routeData.weather_conditions ?? [],
              hazard_status: alertsData.hazard_status ?? 'ready',
            };
          }
        } catch (alertsErr: any) {
          console.warn('Alerts follow-up fetch failed; continuing with base route data:', alertsErr?.message);
        }
      }

      const alertsList = routeData?.alerts ?? routeData?.hazard_alerts ?? [];
      const hazardAlertsLength = Array.isArray(routeData?.hazard_alerts)
        ? routeData.hazard_alerts.length
        : 0;
      const rawLength = JSON.stringify(routeData || {}).length;
      console.log('Route response data (raw)', routeData);
      console.log('Route response ←', {
        url: response.request?.responseURL || routeWeatherUrl,
        status: response.status,
        rawLength,
        alertsLength: Array.isArray(alertsList) ? alertsList.length : 0,
        hazardAlertsLength,
        firstAlertEvent:
          (alertsList?.[0]?.event) ||
          (alertsList?.[0]?.headline) ||
          (alertsList?.[0]?.properties?.event) ||
          null,
      });
      
      // Cache the route for offline
      await AsyncStorage.setItem('lastRoute', JSON.stringify(routeData));
      // Save to local recents (ensures list updates even if backend history is unavailable)
      await saveToLocalRecents(origin.trim(), destination.trim(), stops);

      router.push({
        pathname: '/route',
        params: { routeData: JSON.stringify(routeData) },
      });
    } catch (err: any) {
      console.error('Error:', err);
      setError(
        err.response?.data?.detail ||
          'Failed to get weather data. Please try again.'
      );
    } finally {
      setLoading(false);
    }
  };

  const handleRecentRoute = (route: SavedRoute) => {
    setOrigin(route.origin);
    setDestination(route.destination);
    if (route.stops) {
      setStops(route.stops);
    }
  };

  const addToFavorites = async () => {
    if (!origin.trim() || !destination.trim()) {
      setError('Enter a route first to save as favorite');
      return;
    }
    const newFav: SavedRoute = {
      id: String(Date.now()),
      origin: origin.trim(),
      destination: destination.trim(),
      stops,
      is_favorite: true,
      created_at: new Date().toISOString(),
    };
    // Optimistic local save – always works even without backend
    try {
      const raw = await AsyncStorage.getItem(FAVORITES_KEY);
      const existing: SavedRoute[] = raw ? JSON.parse(raw) : [];
      const deduped = [newFav, ...existing.filter(
        (f) => !(f.origin === newFav.origin && f.destination === newFav.destination)
      )];
      await AsyncStorage.setItem(FAVORITES_KEY, JSON.stringify(deduped));
      setFavoriteRoutes(deduped);
    } catch { /* non-fatal */ }
    // Fire-and-forget backend save
    try {
      await axios.post(`${API_BASE}/api/routes/favorites`, {
        origin: origin.trim(),
        destination: destination.trim(),
        stops,
      });
    } catch (err) {
      console.log('addToFavorites backend save failed (local save succeeded):', err);
    }
  };

  const removeFavorite = async (id: string) => {
    // Optimistic local remove first
    try {
      const raw = await AsyncStorage.getItem(FAVORITES_KEY);
      const existing: SavedRoute[] = raw ? JSON.parse(raw) : [];
      const updated = existing.filter((f) => f.id !== id);
      await AsyncStorage.setItem(FAVORITES_KEY, JSON.stringify(updated));
      setFavoriteRoutes(updated);
    } catch { /* non-fatal */ }
    // Fire-and-forget backend delete
    try {
      await axios.delete(`${API_BASE}/api/routes/favorites/${id}`);
    } catch (err) {
      console.log('removeFavorite backend delete failed (local remove succeeded):', err);
    }
  };

  const addStop = () => {
    if (newStopLocation.trim()) {
      setStops([...stops, { location: newStopLocation.trim(), type: newStopType }]);
      setNewStopLocation('');
      setShowAddStop(false);
    }
  };

  const removeStop = (index: number) => {
    setStops(stops.filter((_, i) => i !== index));
  };

  const swapLocations = () => {
    const temp = origin;
    setOrigin(destination);
    setDestination(temp);
  };

  const stopTypeIcons: Record<string, string> = {
    stop: 'location',
    gas: 'car',
    food: 'restaurant',
    rest: 'bed',
  };

  // Generate radar map HTML using IEM WMS layer for NWS Watch/Warning/Advisory colored zones
  const generateRadarMapHtml = (): string => {
    // Default to center of US
    const usLat = 39.8283;
    const usLon = -98.5795;
    
    return `
      <!DOCTYPE html>
      <html>
      <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
        <style>
          * { margin: 0; padding: 0; box-sizing: border-box; }
          html, body { width: 100%; height: 100%; background: #f0f0f0; }
          #map { width: 100%; height: calc(100% - 120px); }
          .legend-box {
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            background: #003366;
            padding: 8px 12px;
            z-index: 1000;
            font-family: -apple-system, BlinkMacSystemFont, sans-serif;
          }
          .legend-title {
            color: #fff;
            font-size: 13px;
            font-weight: 700;
            margin-bottom: 6px;
            text-align: center;
          }
          .legend-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 4px;
          }
          .legend-item {
            display: flex;
            align-items: center;
            gap: 6px;
          }
          .legend-color {
            width: 18px;
            height: 12px;
            border-radius: 2px;
            border: 1px solid rgba(255,255,255,0.3);
          }
          .legend-text {
            color: #fff;
            font-size: 10px;
            font-weight: 500;
          }
          .controls-row {
            position: absolute;
            bottom: 125px;
            left: 10px;
            z-index: 1000;
          }
          .toggle-btn {
            background: rgba(0,51,102,0.9);
            border: 1px solid #4fc3f7;
            color: #4fc3f7;
            padding: 2px 6px;
            border-radius: 8px;
            font-size: 8px;
            font-weight: 600;
            cursor: pointer;
          }
          .toggle-btn.active { background: #4fc3f7; color: #003366; }
          .time-display {
            color: #fff;
            font-size: 11px;
            font-weight: 500;
          }
          .zoom-controls {
            position: absolute;
            top: 10px;
            right: 10px;
            background: #fff;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.25);
            z-index: 1000;
            overflow: hidden;
          }
          .zoom-btn {
            display: flex;
            align-items: center;
            justify-content: center;
            width: 44px;
            height: 44px;
            background: #fff;
            border: none;
            font-size: 24px;
            font-weight: bold;
            cursor: pointer;
            color: #003366;
          }
          .zoom-btn:first-child { border-bottom: 1px solid #ddd; }
          .zoom-btn:active { background: #e0e0e0; }
          .leaflet-control-zoom { display: none !important; }
        </style>
      </head>
      <body>
        <div id="map"></div>
        <div class="zoom-controls">
          <button class="zoom-btn" id="zoomInBtn">+</button>
          <button class="zoom-btn" id="zoomOutBtn">−</button>
        </div>
        <div class="controls-row">
          <button class="toggle-btn active" id="radarBtn">☁️ Radar</button>
        </div>
        <div class="legend-box">
          <div class="legend-title">⚠️ NWS WATCH / WARNING / ADVISORY</div>
          <div class="legend-grid">
            <div class="legend-item">
              <div class="legend-color" style="background: #ff69b4;"></div>
              <span class="legend-text">Winter Storm</span>
            </div>
            <div class="legend-item">
              <div class="legend-color" style="background: #9400d3;"></div>
              <span class="legend-text">Special Statement</span>
            </div>
            <div class="legend-item">
              <div class="legend-color" style="background: #00ffff;"></div>
              <span class="legend-text">Extreme Cold</span>
            </div>
            <div class="legend-item">
              <div class="legend-color" style="background: #00ff00;"></div>
              <span class="legend-text">Flood</span>
            </div>
            <div class="legend-item">
              <div class="legend-color" style="background: #ff0000;"></div>
              <span class="legend-text">Tornado</span>
            </div>
            <div class="legend-item">
              <div class="legend-color" style="background: #ffa500;"></div>
              <span class="legend-text">Severe T-Storm</span>
            </div>
          </div>
        </div>
        <script>
          var map = L.map('map', { 
            zoomControl: false,
            attributionControl: false,
            minZoom: 3,
            maxZoom: 10
          }).setView([${usLat}, ${usLon}], 4);
          
          // Light base map
          L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
            maxZoom: 19
          }).addTo(map);
          
          // IEM WMS Layer - using correct layer names and version
          var alertsLayer = L.tileLayer.wms('https://mesonet.agron.iastate.edu/cgi-bin/wms/us/wwa.cgi', {
            layers: 'warnings_c',
            format: 'image/png',
            transparent: true,
            version: '1.3.0',
            opacity: 0.8
          }).addTo(map);
          
          var radarLayer = null;
          var showRadar = true;
          
          // Load radar overlay
          fetch('https://api.rainviewer.com/public/weather-maps.json')
            .then(r => r.json())
            .then(data => {
              var frames = data.radar.past;
              if (frames.length > 0) {
                var latest = frames[frames.length - 1];
                radarLayer = L.tileLayer(
                  'https://tilecache.rainviewer.com' + latest.path + '/512/{z}/{x}/{y}/2/1_1.png',
                  { opacity: 0.5, zIndex: 50, tileSize: 512, zoomOffset: -1 }
                );
                if (showRadar) radarLayer.addTo(map);
              }
            });
          
          // Toggle radar layer
          document.getElementById('radarBtn').onclick = function() {
            showRadar = !showRadar;
            this.classList.toggle('active', showRadar);
            if (showRadar && radarLayer) {
              radarLayer.addTo(map);
            } else if (radarLayer) {
              map.removeLayer(radarLayer);
            }
          };
          
          document.getElementById('zoomInBtn').onclick = function() { map.zoomIn(); };
          document.getElementById('zoomOutBtn').onclick = function() { map.zoomOut(); };
        </script>
      </body>
      </html>
    `;
  };

  return (
    <View style={styles.container}>
      <View style={styles.mapBackground}>
        <View style={styles.mapOverlay} />
      </View>

      <SafeAreaView style={styles.safeArea}>
        <KeyboardAvoidingView
          behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
          style={styles.keyboardView}
        >
          <ScrollView
            contentContainerStyle={styles.scrollContent}
            keyboardShouldPersistTaps="handled"
            showsVerticalScrollIndicator={false}
          >
            {/* Main Card */}
            <View style={styles.mainCard}>
              {/* Header */}
              <View style={styles.header}>
                <View style={styles.iconContainer}>
                  <MaterialCommunityIcons name="routes" size={28} color="#1a1a1a" />
                </View>
                <View style={styles.headerText}>
                  <Text style={styles.title}>Routecast</Text>
                  <Text style={styles.subtitle}>Weather forecasts for your journey</Text>
                </View>
                <TouchableOpacity 
                  style={styles.radarHomeBtn}
                  onPress={() => setShowRadarMap(true)}
                >
                  <Ionicons name="radio-outline" size={18} color="#22c55e" />
                  <Text style={styles.radarHomeBtnText}>Radar</Text>
                </TouchableOpacity>
                <TouchableOpacity 
                  style={styles.accountButton}
                  onPress={() => router.push('/account')}
                  data-testid="account-btn"
                >
                  {isAuthenticated ? (
                    <View style={styles.accountLoggedIn}>
                      <Ionicons name="person" size={18} color="#eab308" />
                      {isPremium && <View style={styles.premiumDot} />}
                    </View>
                  ) : (
                    <Ionicons name="person-outline" size={22} color="#a1a1aa" />
                  )}
                </TouchableOpacity>
              </View>

              {/* App Description */}
              <View style={styles.descriptionBox}>
                <Text style={styles.descriptionText}>
                  Plan your road trip with confidence. See real-time weather conditions, alerts, and AI-powered recommendations for every mile of your drive.
                </Text>
              </View>

              {/* Origin Input */}
              <View style={styles.inputSection}>
                <Text style={styles.inputLabel}>ORIGIN</Text>
                <View style={styles.inputWrapper}>
                  <View style={styles.originIcon}>
                    <Ionicons name="location" size={20} color="#22c55e" />
                  </View>
                  <NoAutofillInput
                    style={styles.input}
                    placeholder="Enter starting location"
                    placeholderTextColor="#6b7280"
                    value={origin}
                    onChangeText={handleOriginChange}
                    onFocus={() => origin.length >= 2 && setShowOriginSuggestions(originSuggestions.length > 0)}
                    onBlur={() => setTimeout(() => setShowOriginSuggestions(false), 200)}
                    returnKeyType="next"
                    data-testid="origin-input"
                  />
                  {autocompleteLoading && origin.length >= 2 && (
                    <ActivityIndicator size="small" color="#eab308" style={{ marginRight: 8 }} />
                  )}
                  {origin.length > 0 && (
                    <TouchableOpacity 
                      onPress={() => { setOrigin(''); setOriginSuggestions([]); setShowOriginSuggestions(false); }} 
                      style={styles.clearButton}
                      data-testid="clear-origin-btn"
                    >
                      <Ionicons name="close-circle" size={18} color="#6b7280" />
                    </TouchableOpacity>
                  )}
                </View>
                {/* Origin Suggestions Dropdown */}
                {showOriginSuggestions && originSuggestions.length > 0 && (
                  <View style={styles.suggestionsDropdown}>
                    {originSuggestions.map((suggestion, index) => (
                      <TouchableOpacity
                        key={index}
                        style={styles.suggestionItem}
                        onPress={() => selectOriginSuggestion(suggestion)}
                      >
                        <Ionicons name="location-outline" size={16} color="#a1a1aa" />
                        <View style={styles.suggestionTextContainer}>
                          <Text style={styles.suggestionShortName}>{suggestion.short_name}</Text>
                          <Text style={styles.suggestionFullName} numberOfLines={1}>{suggestion.place_name}</Text>
                        </View>
                      </TouchableOpacity>
                    ))}
                  </View>
                )}
              </View>

              {/* Stops */}
              {stops.length > 0 && (
                <View style={styles.stopsContainer}>
                  {stops.map((stop, index) => (
                    <View key={index} style={styles.stopItem}>
                      <Ionicons 
                        name={stopTypeIcons[stop.type] as any || 'location'} 
                        size={16} 
                        color="#f59e0b" 
                      />
                      <Text style={styles.stopText} numberOfLines={1}>{stop.location}</Text>
                      <TouchableOpacity onPress={() => removeStop(index)}>
                        <Ionicons name="close-circle" size={18} color="#6b7280" />
                      </TouchableOpacity>
                    </View>
                  ))}
                </View>
              )}

              {/* Add Stop Button */}
              <TouchableOpacity 
                style={styles.addStopButton}
                onPress={() => setShowAddStop(true)}
              >
                <Ionicons name="add-circle-outline" size={18} color="#60a5fa" />
                <Text style={styles.addStopText}>Add Stop</Text>
              </TouchableOpacity>

              {/* Destination Input */}
              <View style={styles.inputSection}>
                <Text style={styles.inputLabel}>DESTINATION</Text>
                <View style={styles.inputWrapper}>
                  <View style={styles.destinationIcon}>
                    <Ionicons name="navigate" size={20} color="#ef4444" />
                  </View>
                  <NoAutofillInput
                    style={styles.input}
                    placeholder="Enter destination"
                    placeholderTextColor="#6b7280"
                    value={destination}
                    onChangeText={handleDestinationChange}
                    onFocus={() => destination.length >= 2 && setShowDestSuggestions(destSuggestions.length > 0)}
                    onBlur={() => setTimeout(() => setShowDestSuggestions(false), 200)}
                    returnKeyType="done"
                    onSubmitEditing={handleGetWeather}
                    data-testid="destination-input"
                  />
                  {autocompleteLoading && destination.length >= 2 && (
                    <ActivityIndicator size="small" color="#eab308" style={{ marginRight: 8 }} />
                  )}
                  {destination.length > 0 && (
                    <TouchableOpacity 
                      onPress={() => { setDestination(''); setDestSuggestions([]); setShowDestSuggestions(false); }} 
                      style={styles.clearButton}
                      data-testid="clear-destination-btn"
                    >
                      <Ionicons name="close-circle" size={18} color="#6b7280" />
                    </TouchableOpacity>
                  )}
                  <TouchableOpacity onPress={swapLocations} style={styles.swapButton}>
                    <Ionicons name="swap-vertical" size={20} color="#60a5fa" />
                  </TouchableOpacity>
                </View>
                {/* Destination Suggestions Dropdown */}
                {showDestSuggestions && destSuggestions.length > 0 && (
                  <View style={styles.suggestionsDropdown}>
                    {destSuggestions.map((suggestion, index) => (
                      <TouchableOpacity
                        key={index}
                        style={styles.suggestionItem}
                        onPress={() => selectDestSuggestion(suggestion)}
                      >
                        <Ionicons name="location-outline" size={16} color="#a1a1aa" />
                        <View style={styles.suggestionTextContainer}>
                          <Text style={styles.suggestionShortName}>{suggestion.short_name}</Text>
                          <Text style={styles.suggestionFullName} numberOfLines={1}>{suggestion.place_name}</Text>
                        </View>
                      </TouchableOpacity>
                    ))}
                  </View>
                )}
              </View>

              {/* Departure Time */}
              <View style={styles.departureSection}>
                <View style={styles.departureToggle}>
                  <Ionicons name="time-outline" size={20} color="#a1a1aa" />
                  <Text style={styles.departureLabel}>Custom Departure Time</Text>
                  <Switch
                    value={useCustomTime}
                    onValueChange={setUseCustomTime}
                    trackColor={{ false: '#3f3f46', true: '#eab30880' }}
                    thumbColor={useCustomTime ? '#eab308' : '#71717a'}
                  />
                </View>
                {useCustomTime && (
                  <TouchableOpacity 
                    style={styles.timeButton}
                    onPress={() => {
                      setPendingDate(new Date(departureTime));
                      setPickerMode('date');
                      setShowDatePicker(true);
                    }}
                  >
                    <Text style={styles.timeButtonText}>
                      {format(departureTime, 'MMM d, h:mm a')}
                    </Text>
                    <Ionicons name="chevron-forward" size={18} color="#6b7280" />
                  </TouchableOpacity>
                )}
              </View>

              {/* Vehicle Type Selector */}
              <TouchableOpacity 
                style={styles.vehicleSelector}
                onPress={() => setShowVehicleSelector(true)}
              >
                <View style={styles.vehicleSelectorLeft}>
                  <Ionicons name={VEHICLE_TYPES.find(v => v.id === vehicleType)?.icon as any || 'car-sport-outline'} size={22} color="#60a5fa" />
                  <View>
                    <Text style={styles.vehicleLabel}>Vehicle Type</Text>
                    <Text style={styles.vehicleValue}>{VEHICLE_TYPES.find(v => v.id === vehicleType)?.label || 'Car'}</Text>
                  </View>
                </View>
                <Ionicons name="chevron-forward" size={18} color="#6b7280" />
              </TouchableOpacity>

              {/* Trucker Mode Toggle */}
              <View style={styles.truckerToggle}>
                <View style={styles.alertsLeft}>
                  <Ionicons name="bus-outline" size={22} color="#f59e0b" />
                  <View>
                    <Text style={styles.alertsText}>Trucker Mode</Text>
                    <Text style={styles.truckerSubtext}>Bridge clearance & wind warnings</Text>
                  </View>
                </View>
                <Switch
                  value={truckerMode}
                  onValueChange={setTruckerMode}
                  trackColor={{ false: '#3f3f46', true: '#f59e0b80' }}
                  thumbColor={truckerMode ? '#f59e0b' : '#71717a'}
                />
              </View>

              {/* Vehicle Height Input - shows when Trucker Mode is on */}
              {truckerMode && (
                <View style={styles.vehicleHeightContainer}>
                  <View style={styles.vehicleHeightRow}>
                    <Ionicons name="resize-outline" size={20} color="#f59e0b" />
                    <Text style={styles.vehicleHeightLabel}>Vehicle Height</Text>
                  </View>
                  <View style={styles.vehicleHeightInputRow}>
                    <TextInput
                      style={styles.vehicleHeightInput}
                      value={vehicleHeight}
                      onChangeText={setVehicleHeight}
                      keyboardType="decimal-pad"
                      placeholder="13.6"
                      placeholderTextColor="#6b7280"
                    />
                    <Text style={styles.vehicleHeightUnit}>feet</Text>
                  </View>
                  <Text style={styles.vehicleHeightHint}>Enter total height for bridge clearance alerts</Text>
                </View>
              )}

              {/* Weather Alerts Toggle */}
              {IS_WEB && !isMobileWeb ? (
                <View style={styles.alertsToggleDisabled}>
                  <View style={styles.alertsLeft}>
                    <Ionicons name="notifications-off-outline" size={22} color="#f97316" />
                    <View>
                      <Text style={styles.alertsText}>Push Weather Alerts</Text>
                      <Text style={styles.webOnlyText}>Push notifications available on mobile app only.</Text>
                    </View>
                  </View>
                </View>
              ) : (
                <View style={styles.alertsToggle}>
                  <View style={styles.alertsLeft}>
                    <Ionicons name="notifications-outline" size={22} color="#eab308" />
                    <Text style={styles.alertsText}>Push Weather Alerts</Text>
                  </View>
                  {pushLoading ? (
                    <ActivityIndicator size="small" color="#eab308" />
                  ) : (
                    <Switch
                      value={alertsEnabled}
                      onValueChange={(next) => {
                        __DEV__ && console.log('[push-toggle] render value=', alertsEnabled, '→ onValueChange next=', next);
                        handleAlertsToggle(next);
                      }}
                      trackColor={{ false: '#3f3f46', true: '#eab30880' }}
                      thumbColor={alertsEnabled ? '#eab308' : '#71717a'}
                    />
                  )}
                </View>
              )}

              {/* Error Message */}
              {error ? (
                <View style={styles.errorContainer}>
                  <Ionicons name="alert-circle" size={18} color="#ef4444" />
                  <Text style={styles.errorText}>{error}</Text>
                </View>
              ) : null}

              {/* Check Route Button */}
              <TouchableOpacity
                style={[styles.button, loading && styles.buttonDisabled]}
                onPress={handleGetWeather}
                disabled={loading}
                activeOpacity={0.8}
              >
                {loading ? (
                  <ActivityIndicator color="#1a1a1a" size="small" />
                ) : (
                  <>
                    <Ionicons name="navigate" size={22} color="#1a1a1a" />
                    <Text style={styles.buttonText}>CHECK ROUTE WEATHER</Text>
                  </>
                )}
              </TouchableOpacity>

              {/* Quick Access Buttons */}
              <View style={styles.quickAccessRow}>
                <TouchableOpacity
                  style={styles.quickAccessBtn}
                  onPress={() => router.push('/boondockers')}
                  activeOpacity={0.85}
                >
                  <View style={styles.quickAccessIconCircle}>
                    <Ionicons name="bonfire" size={22} color="#10b981" />
                  </View>
                  <Text style={styles.quickAccessText} numberOfLines={1}>Boondockers</Text>
                </TouchableOpacity>
                <TouchableOpacity
                  style={styles.quickAccessBtn}
                  onPress={() => router.push('/tractor-trailer')}
                  activeOpacity={0.85}
                >
                  <View style={styles.quickAccessIconCircle}>
                    <Ionicons name="bus" size={22} color="#f59e0b" />
                  </View>
                  <Text style={styles.quickAccessText} numberOfLines={1}>Truck Drivers</Text>
                </TouchableOpacity>
                <TouchableOpacity
                  style={styles.quickAccessBtn}
                  onPress={() => router.push('/how-to-use')}
                  activeOpacity={0.85}
                  data-testid="how-to-use-btn"
                >
                  <View style={styles.quickAccessIconCircle}>
                    <Ionicons name="help-circle" size={22} color="#8b5cf6" />
                  </View>
                  <Text style={styles.quickAccessText} numberOfLines={1}>How To Use</Text>
                </TouchableOpacity>
              </View>
            </View>

            {/* Tabs for Recent/Favorites */}
            <View style={styles.tabsContainer}>
              <TouchableOpacity 
                style={[styles.tab, !showFavorites && styles.tabActive]}
                onPress={() => setShowFavorites(false)}
              >
                <Ionicons name="time-outline" size={18} color={!showFavorites ? '#eab308' : '#6b7280'} />
                <Text style={[styles.tabText, !showFavorites && styles.tabTextActive]}>Recent</Text>
              </TouchableOpacity>
              <TouchableOpacity 
                style={[styles.tab, showFavorites && styles.tabActive]}
                onPress={() => setShowFavorites(true)}
              >
                <Ionicons name="heart" size={18} color={showFavorites ? '#eab308' : '#6b7280'} />
                <Text style={[styles.tabText, showFavorites && styles.tabTextActive]}>Favorites</Text>
              </TouchableOpacity>
            </View>

            {/* Routes List */}
            <View style={styles.routesSection}>
              {(showFavorites ? favoriteRoutes : recentRoutes).length === 0 ? (
                <View style={styles.emptyState}>
                  <Ionicons 
                    name={showFavorites ? "heart-outline" : "map-outline"} 
                    size={48} 
                    color="#374151" 
                  />
                  <Text style={styles.emptyText}>
                    {showFavorites ? 'No favorite routes' : 'No recent routes'}
                  </Text>
                </View>
              ) : (
                (showFavorites ? favoriteRoutes : recentRoutes).map((route) => (
                  <TouchableOpacity
                    key={route.id}
                    style={styles.routeCard}
                    onPress={() => handleRecentRoute(route)}
                    activeOpacity={0.7}
                  >
                    <View style={styles.routeInfo}>
                      <View style={styles.routeLocations}>
                        <View style={styles.routeLocation}>
                          <View style={styles.routeDot} />
                          <Text style={styles.routeText} numberOfLines={1}>
                            {route.origin}
                          </Text>
                        </View>
                        {route.stops && route.stops.length > 0 && (
                          <View style={styles.routeStops}>
                            <Text style={styles.routeStopsText}>
                              +{route.stops.length} stop{route.stops.length > 1 ? 's' : ''}
                            </Text>
                          </View>
                        )}
                        <View style={styles.routeLocation}>
                          <View style={[styles.routeDot, styles.routeDotEnd]} />
                          <Text style={styles.routeText} numberOfLines={1}>
                            {route.destination}
                          </Text>
                        </View>
                      </View>
                    </View>
                    {showFavorites ? (
                      <TouchableOpacity onPress={() => removeFavorite(route.id)}>
                        <Ionicons name="heart-dislike" size={20} color="#ef4444" />
                      </TouchableOpacity>
                    ) : (
                      <Ionicons name="chevron-forward" size={20} color="#6b7280" />
                    )}
                  </TouchableOpacity>
                ))
              )}
            </View>
          </ScrollView>
        </KeyboardAvoidingView>
      </SafeAreaView>

      {/* Date Time Picker — Android: bare two-step picker (no Modal), iOS/web: modal */}
      {showDatePicker && Platform.OS === 'android' && (
        <DateTimePicker
          value={pendingDate}
          mode={pickerMode}
          display="default"
          minimumDate={pickerMode === 'date' ? new Date() : undefined}
          onChange={(event, date) => {
            if (event.type === 'dismissed') {
              setShowDatePicker(false);
              return;
            }
            if (event.type === 'set' && date) {
              if (pickerMode === 'date') {
                // Step 1 confirmed: preserve existing time, apply new date, then show time picker
                const merged = new Date(pendingDate);
                merged.setFullYear(date.getFullYear(), date.getMonth(), date.getDate());
                setPendingDate(merged);
                setPickerMode('time');
              } else {
                // Step 2 confirmed: apply selected time to the pending date and commit
                const merged = new Date(pendingDate);
                merged.setHours(date.getHours(), date.getMinutes(), 0, 0);
                setDepartureTime(merged);
                setShowDatePicker(false);
              }
            }
          }}
        />
      )}

      {showDatePicker && Platform.OS !== 'android' && (
        <Modal transparent animationType="slide">
          <View style={styles.modalOverlay}>
            <View style={styles.modalContent}>
              <View style={styles.modalHeader}>
                <Text style={styles.modalTitle}>Select Departure Time</Text>
                <TouchableOpacity onPress={() => setShowDatePicker(false)}>
                  <Ionicons name="close" size={24} color="#fff" />
                </TouchableOpacity>
              </View>

              {Platform.OS === 'web' ? (
                // Web-compatible date/time input
                <View style={styles.webDatePicker}>
                  <Text style={styles.datePickerLabel}>Date</Text>
                  <input
                    type="date"
                    value={departureTime.toISOString().split('T')[0]}
                    min={new Date().toISOString().split('T')[0]}
                    onChange={(e) => {
                      const newDate = new Date(departureTime);
                      const [year, month, day] = e.target.value.split('-');
                      newDate.setFullYear(parseInt(year), parseInt(month) - 1, parseInt(day));
                      setDepartureTime(newDate);
                    }}
                    style={{
                      width: '100%',
                      padding: 12,
                      fontSize: 16,
                      backgroundColor: '#3f3f46',
                      border: '1px solid #52525b',
                      borderRadius: 8,
                      color: '#fff',
                      marginBottom: 16,
                    }}
                  />

                  <Text style={styles.datePickerLabel}>Time</Text>
                  <input
                    type="time"
                    value={`${String(departureTime.getHours()).padStart(2, '0')}:${String(departureTime.getMinutes()).padStart(2, '0')}`}
                    onChange={(e) => {
                      const newDate = new Date(departureTime);
                      const [hours, minutes] = e.target.value.split(':');
                      newDate.setHours(parseInt(hours), parseInt(minutes));
                      setDepartureTime(newDate);
                    }}
                    style={{
                      width: '100%',
                      padding: 12,
                      fontSize: 16,
                      backgroundColor: '#3f3f46',
                      border: '1px solid #52525b',
                      borderRadius: 8,
                      color: '#fff',
                      marginBottom: 16,
                    }}
                  />

                  <Text style={styles.selectedDateTime}>
                    Selected: {format(departureTime, 'MMM d, yyyy h:mm a')}
                  </Text>
                </View>
              ) : (
                // iOS native DateTimePicker (datetime + spinner supported on iOS)
                <DateTimePicker
                  value={departureTime}
                  mode="datetime"
                  display="spinner"
                  onChange={(event, date) => {
                    if (event.type === 'set' && date) setDepartureTime(date);
                  }}
                  textColor="#fff"
                  minimumDate={new Date()}
                />
              )}

              <TouchableOpacity
                style={styles.modalButton}
                onPress={() => setShowDatePicker(false)}
              >
                <Text style={styles.modalButtonText}>Confirm</Text>
              </TouchableOpacity>
            </View>
          </View>
        </Modal>
      )}

      {/* Radar Map Modal */}
      {showRadarMap && (
        <Modal transparent animationType="slide">
          <View style={styles.radarModalOverlay}>
            <View style={styles.radarModalContent}>
              <View style={styles.radarHeader}>
                <View style={styles.radarHeaderLeft}>
                  <Ionicons name="radio-outline" size={24} color="#22c55e" />
                  <Text style={styles.radarTitle}>Live Weather Radar</Text>
                </View>
                <TouchableOpacity onPress={() => setShowRadarMap(false)}>
                  <Ionicons name="close" size={28} color="#fff" />
                </TouchableOpacity>
              </View>
              
              {Platform.OS === 'web' ? (
                <iframe
                  srcDoc={generateRadarMapHtml()}
                  style={{ flex: 1, border: 'none', width: '100%', height: '100%', touchAction: 'none' }}
                  allowFullScreen
                />
              ) : (
                <WebView
                  source={{ html: generateRadarMapHtml() }}
                  style={styles.radarWebView}
                  javaScriptEnabled={true}
                  domStorageEnabled={true}
                  scalesPageToFit={true}
                  scrollEnabled={false}
                  bounces={false}
                  overScrollMode="never"
                  nestedScrollEnabled={false}
                  setBuiltInZoomControls={false}
                  setDisplayZoomControls={false}
                />
              )}
            </View>
          </View>
        </Modal>
      )}

      {/* Add Stop Modal */}
      {showAddStop && (
        <Modal transparent animationType="slide">
          <View style={styles.modalOverlay}>
            <View style={styles.modalContent}>
              <View style={styles.modalHeader}>
                <Text style={styles.modalTitle}>Add Stop</Text>
                <TouchableOpacity onPress={() => setShowAddStop(false)}>
                  <Ionicons name="close" size={24} color="#fff" />
                </TouchableOpacity>
              </View>
              
              <NoAutofillInput
                style={styles.modalInput}
                placeholder="Enter stop location"
                placeholderTextColor="#6b7280"
                value={newStopLocation}
                onChangeText={setNewStopLocation}
              />
              
              <Text style={styles.stopTypeLabel}>Stop Type</Text>
              <View style={styles.stopTypes}>
                {[
                  { type: 'stop', label: 'Stop', icon: 'location' },
                  { type: 'gas', label: 'Gas', icon: 'car' },
                  { type: 'food', label: 'Food', icon: 'restaurant' },
                  { type: 'rest', label: 'Rest', icon: 'bed' },
                ].map((item) => (
                  <TouchableOpacity
                    key={item.type}
                    style={[
                      styles.stopTypeButton,
                      newStopType === item.type && styles.stopTypeButtonActive,
                    ]}
                    onPress={() => setNewStopType(item.type)}
                  >
                    <Ionicons 
                      name={item.icon as any} 
                      size={20} 
                      color={newStopType === item.type ? '#eab308' : '#6b7280'} 
                    />
                    <Text style={[
                      styles.stopTypeText,
                      newStopType === item.type && styles.stopTypeTextActive
                    ]}>{item.label}</Text>
                  </TouchableOpacity>
                ))}
              </View>

              <TouchableOpacity style={styles.modalButton} onPress={addStop}>
                <Text style={styles.modalButtonText}>Add Stop</Text>
              </TouchableOpacity>
            </View>
          </View>
        </Modal>
      )}

      {/* Vehicle Type Selector Modal */}
      {showVehicleSelector && (
        <Modal transparent animationType="slide">
          <View style={styles.modalOverlay}>
            <View style={styles.modalContent}>
              <View style={styles.modalHeader}>
                <Text style={styles.modalTitle}>Select Vehicle Type</Text>
                <TouchableOpacity onPress={() => setShowVehicleSelector(false)}>
                  <Ionicons name="close" size={24} color="#fff" />
                </TouchableOpacity>
              </View>
              
              <Text style={styles.vehicleModalSubtext}>
                Safety scores are customized for your vehicle
              </Text>
              
              <View style={styles.vehicleList}>
                {VEHICLE_TYPES.map((vehicle) => (
                  <TouchableOpacity
                    key={vehicle.id}
                    style={[
                      styles.vehicleOption,
                      vehicleType === vehicle.id && styles.vehicleOptionActive,
                    ]}
                    onPress={() => {
                      setVehicleType(vehicle.id);
                      setShowVehicleSelector(false);
                    }}
                  >
                    <Ionicons 
                      name={vehicle.icon as any} 
                      size={24} 
                      color={vehicleType === vehicle.id ? '#eab308' : '#6b7280'} 
                    />
                    <Text style={[
                      styles.vehicleOptionText,
                      vehicleType === vehicle.id && styles.vehicleOptionTextActive
                    ]}>{vehicle.label}</Text>
                    {vehicleType === vehicle.id && (
                      <Ionicons name="checkmark-circle" size={20} color="#eab308" />
                    )}
                  </TouchableOpacity>
                ))}
              </View>
            </View>
          </View>
        </Modal>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0f0f0f',
  },
  mapBackground: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: '#1a1a1a',
  },
  mapOverlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: 'rgba(0, 0, 0, 0.7)',
  },
  safeArea: {
    flex: 1,
  },
  keyboardView: {
    flex: 1,
  },
  scrollContent: {
    padding: 16,
    paddingTop: 12,
    paddingBottom: 40,
  },
  mainCard: {
    backgroundColor: '#27272a',
    borderRadius: 16,
    padding: 18,
    marginBottom: 16,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 16,
  },
  iconContainer: {
    width: 44,
    height: 44,
    borderRadius: 12,
    backgroundColor: '#eab308',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  headerText: {
    flex: 1,
  },
  title: {
    fontSize: 22,
    fontWeight: '700',
    color: '#ffffff',
    marginBottom: 2,
  },
  subtitle: {
    fontSize: 13,
    color: '#a1a1aa',
  },
  favoriteButton: {
    padding: 8,
  },
  accountButton: {
    padding: 8,
  },
  accountLoggedIn: {
    position: 'relative',
  },
  premiumDot: {
    position: 'absolute',
    top: -2,
    right: -2,
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: '#22c55e',
  },
  descriptionBox: {
    backgroundColor: 'rgba(234, 179, 8, 0.1)',
    borderRadius: 10,
    padding: 12,
    marginBottom: 16,
    borderLeftWidth: 3,
    borderLeftColor: '#eab308',
  },
  descriptionText: {
    color: '#d4d4d8',
    fontSize: 12,
    lineHeight: 18,
  },
  inputSection: {
    marginBottom: 12,
  },
  inputLabel: {
    fontSize: 11,
    fontWeight: '600',
    color: '#a1a1aa',
    letterSpacing: 1,
    marginBottom: 6,
  },
  inputWrapper: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#3f3f46',
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#52525b',
    paddingHorizontal: 12,
  },
  originIcon: {
    marginRight: 10,
  },
  destinationIcon: {
    marginRight: 10,
  },
  input: {
    flex: 1,
    fontSize: 15,
    color: '#ffffff',
    paddingVertical: 12,
    fontWeight: '500',
  },
  clearButton: {
    padding: 6,
    marginRight: 4,
  },
  swapButton: {
    padding: 8,
  },
  stopsContainer: {
    marginBottom: 8,
  },
  stopItem: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#3f3f46',
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 8,
    marginBottom: 6,
    gap: 8,
  },
  stopText: {
    flex: 1,
    color: '#e4e4e7',
    fontSize: 14,
  },
  addStopButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginBottom: 12,
    paddingVertical: 4,
  },
  addStopText: {
    color: '#60a5fa',
    fontSize: 13,
    fontWeight: '500',
  },
  departureSection: {
    marginBottom: 12,
  },
  departureToggle: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  departureLabel: {
    flex: 1,
    color: '#e4e4e7',
    fontSize: 14,
  },
  timeButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: '#3f3f46',
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 10,
    marginTop: 8,
  },
  timeButtonText: {
    color: '#eab308',
    fontSize: 14,
    fontWeight: '500',
  },
  alertsToggle: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 8,
    marginBottom: 12,
  },
  alertsToggleDisabled: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 8,
    marginBottom: 12,
    backgroundColor: 'rgba(249, 115, 22, 0.08)',
    borderRadius: 8,
    paddingHorizontal: 10,
  },
  alertsLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  alertsText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#ffffff',
  },
  webOnlyText: {
    color: '#fbbf24',
    fontSize: 12,
    marginTop: 2,
  },
  errorContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(239, 68, 68, 0.15)',
    padding: 10,
    borderRadius: 8,
    marginBottom: 12,
    gap: 8,
  },
  errorText: {
    color: '#ef4444',
    fontSize: 13,
    flex: 1,
  },
  button: {
    backgroundColor: '#eab308',
    borderRadius: 10,
    paddingVertical: 14,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 10,
  },
  buttonDisabled: {
    opacity: 0.7,
  },
  buttonText: {
    color: '#1a1a1a',
    fontSize: 15,
    fontWeight: '700',
    letterSpacing: 0.5,
  },
  tabsContainer: {
    flexDirection: 'row',
    marginBottom: 12,
    gap: 8,
  },
  tab: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingVertical: 10,
    backgroundColor: '#27272a',
    borderRadius: 10,
  },
  tabActive: {
    backgroundColor: '#3f3f46',
  },
  tabText: {
    color: '#6b7280',
    fontSize: 14,
    fontWeight: '500',
  },
  tabTextActive: {
    color: '#eab308',
  },
  routesSection: {
    minHeight: 100,
  },
  emptyState: {
    alignItems: 'center',
    paddingVertical: 32,
    backgroundColor: '#27272a',
    borderRadius: 12,
  },
  emptyText: {
    color: '#6b7280',
    fontSize: 14,
    marginTop: 12,
  },
  routeCard: {
    backgroundColor: '#27272a',
    borderRadius: 10,
    padding: 12,
    marginBottom: 8,
    flexDirection: 'row',
    alignItems: 'center',
  },
  routeInfo: {
    flex: 1,
  },
  routeLocations: {
    gap: 2,
  },
  routeLocation: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  routeDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: '#22c55e',
  },
  routeDotEnd: {
    backgroundColor: '#ef4444',
  },
  routeText: {
    color: '#e4e4e7',
    fontSize: 13,
    flex: 1,
  },
  routeStops: {
    marginLeft: 16,
    paddingVertical: 2,
  },
  routeStopsText: {
    color: '#f59e0b',
    fontSize: 11,
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.8)',
    justifyContent: 'flex-end',
  },
  modalContent: {
    backgroundColor: '#27272a',
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    padding: 20,
    paddingBottom: Platform.OS === 'ios' ? 40 : 20,
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 20,
  },
  modalTitle: {
    color: '#fff',
    fontSize: 18,
    fontWeight: '700',
  },
  modalInput: {
    backgroundColor: '#3f3f46',
    borderRadius: 10,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 15,
    color: '#fff',
    marginBottom: 16,
  },
  stopTypeLabel: {
    color: '#a1a1aa',
    fontSize: 12,
    fontWeight: '600',
    marginBottom: 10,
    letterSpacing: 0.5,
  },
  stopTypes: {
    flexDirection: 'row',
    gap: 10,
    marginBottom: 20,
  },
  stopTypeButton: {
    flex: 1,
    alignItems: 'center',
    paddingVertical: 12,
    backgroundColor: '#3f3f46',
    borderRadius: 10,
    gap: 4,
  },
  stopTypeButtonActive: {
    backgroundColor: '#52525b',
    borderWidth: 1,
    borderColor: '#eab308',
  },
  stopTypeText: {
    color: '#6b7280',
    fontSize: 11,
  },
  stopTypeTextActive: {
    color: '#eab308',
  },
  modalButton: {
    backgroundColor: '#eab308',
    borderRadius: 10,
    paddingVertical: 14,
    alignItems: 'center',
  },
  modalButtonText: {
    color: '#1a1a1a',
    fontSize: 15,
    fontWeight: '700',
  },
  suggestionsDropdown: {
    backgroundColor: '#3f3f46',
    borderRadius: 10,
    marginTop: 4,
    borderWidth: 1,
    borderColor: '#52525b',
    overflow: 'hidden',
  },
  suggestionItem: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#52525b',
    gap: 10,
  },
  suggestionTextContainer: {
    flex: 1,
  },
  suggestionShortName: {
    color: '#ffffff',
    fontSize: 14,
    fontWeight: '600',
  },
  suggestionFullName: {
    color: '#a1a1aa',
    fontSize: 11,
    marginTop: 2,
  },
  vehicleSelector: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: '#3f3f46',
    borderRadius: 10,
    paddingHorizontal: 14,
    paddingVertical: 12,
    marginBottom: 12,
  },
  vehicleSelectorLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  vehicleLabel: {
    color: '#a1a1aa',
    fontSize: 11,
    fontWeight: '500',
  },
  vehicleValue: {
    color: '#ffffff',
    fontSize: 14,
    fontWeight: '600',
  },
  truckerToggle: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 8,
    marginBottom: 8,
  },
  truckerSubtext: {
    color: '#6b7280',
    fontSize: 11,
  },
  vehicleModalSubtext: {
    color: '#a1a1aa',
    fontSize: 13,
    marginBottom: 16,
  },
  vehicleList: {
    gap: 8,
  },
  vehicleOption: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#3f3f46',
    borderRadius: 10,
    paddingHorizontal: 14,
    paddingVertical: 14,
    gap: 12,
  },
  vehicleOptionActive: {
    backgroundColor: '#52525b',
    borderWidth: 1,
    borderColor: '#eab308',
  },
  vehicleOptionText: {
    color: '#e4e4e7',
    fontSize: 14,
    fontWeight: '500',
    flex: 1,
  },
  vehicleOptionTextActive: {
    color: '#eab308',
  },
  webDatePicker: {
    paddingVertical: 16,
  },
  datePickerLabel: {
    color: '#a1a1aa',
    fontSize: 12,
    fontWeight: '600',
    marginBottom: 8,
    textTransform: 'uppercase',
  },
  selectedDateTime: {
    color: '#eab308',
    fontSize: 16,
    fontWeight: '700',
    textAlign: 'center',
    marginTop: 8,
  },
  // AI Chat styles
  chatFab: {
    position: 'absolute',
    right: 20,
    bottom: 30,
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: '#eab308',
    justifyContent: 'center',
    alignItems: 'center',
    elevation: 5,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.3,
    shadowRadius: 4,
  },
  chatModalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.7)',
    justifyContent: 'flex-end',
  },
  chatModalContent: {
    backgroundColor: '#1f1f23',
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    height: '80%',
    paddingBottom: 20,
  },
  chatHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#3f3f46',
  },
  chatHeaderLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  chatTitle: {
    color: '#fff',
    fontSize: 18,
    fontWeight: '700',
  },
  chatMessages: {
    flex: 1,
    padding: 16,
  },
  chatWelcome: {
    alignItems: 'center',
    paddingVertical: 40,
  },
  chatWelcomeText: {
    color: '#fff',
    fontSize: 18,
    fontWeight: '600',
  },
  chatWelcomeSubtext: {
    color: '#6b7280',
    fontSize: 14,
    marginTop: 8,
    textAlign: 'center',
  },
  chatBubble: {
    maxWidth: '85%',
    padding: 12,
    borderRadius: 16,
    marginBottom: 10,
  },
  userBubble: {
    backgroundColor: '#2563eb',
    alignSelf: 'flex-end',
    borderBottomRightRadius: 4,
  },
  aiBubble: {
    backgroundColor: '#3f3f46',
    alignSelf: 'flex-start',
    borderBottomLeftRadius: 4,
  },
  chatBubbleText: {
    color: '#fff',
    fontSize: 14,
    lineHeight: 20,
  },
  chatTyping: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    padding: 8,
  },
  chatTypingText: {
    color: '#6b7280',
    fontSize: 12,
  },
  chatSuggestions: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    padding: 12,
    gap: 8,
    borderTopWidth: 1,
    borderTopColor: '#3f3f46',
  },
  chatSuggestionBtn: {
    backgroundColor: '#27272a',
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: '#3f3f46',
  },
  chatSuggestionText: {
    color: '#a1a1aa',
    fontSize: 12,
  },
  chatInputRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingTop: 8,
    gap: 10,
  },
  chatInput: {
    flex: 1,
    backgroundColor: '#27272a',
    borderRadius: 24,
    paddingHorizontal: 16,
    paddingVertical: 12,
    color: '#fff',
    fontSize: 14,
    borderWidth: 1,
    borderColor: '#3f3f46',
  },
  chatInputFull: {
    flex: 1,
    backgroundColor: '#27272a',
    borderRadius: 24,
    paddingHorizontal: 20,
    paddingVertical: 14,
    color: '#fff',
    fontSize: 15,
    borderWidth: 1,
    borderColor: '#3f3f46',
  },
  chatSendBtn: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: '#eab308',
    justifyContent: 'center',
    alignItems: 'center',
  },
  chatSendBtnDisabled: {
    backgroundColor: '#3f3f46',
  },
  // Radar button and modal styles
  radarHomeBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#14532d',
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 16,
    marginRight: 8,
    gap: 4,
  },
  radarHomeBtnText: {
    color: '#22c55e',
    fontSize: 12,
    fontWeight: '600',
  },
  radarModalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.9)',
  },
  radarModalContent: {
    flex: 1,
    backgroundColor: '#18181b',
  },
  radarHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 16,
    backgroundColor: '#27272a',
    borderBottomWidth: 1,
    borderBottomColor: '#3f3f46',
  },
  radarHeaderLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  radarTitle: {
    color: '#fff',
    fontSize: 18,
    fontWeight: '700',
  },
  radarWebView: {
    flex: 1,
  },
  quickAccessRow: {
    flexDirection: 'row',
    gap: 12,
    marginTop: 12,
    justifyContent: 'space-between',
  },
  quickAccessBtn: {
    flex: 1,
    aspectRatio: 1,
    minHeight: 110,
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 10,
    backgroundColor: '#27272a',
    padding: 14,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#3f3f46',
    overflow: 'hidden',
  },
  quickAccessIconCircle: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#18181b',
  },
  quickAccessText: {
    color: '#e4e4e7',
    fontSize: 14,
    fontWeight: '700',
    textAlign: 'center',
  },
  vehicleHeightContainer: {
    backgroundColor: '#1c1917',
    borderRadius: 10,
    padding: 14,
    borderWidth: 1,
    borderColor: '#f59e0b30',
  },
  vehicleHeightRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 10,
  },
  vehicleHeightLabel: {
    color: '#f59e0b',
    fontSize: 14,
    fontWeight: '600',
  },
  vehicleHeightInputRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  vehicleHeightInput: {
    flex: 1,
    backgroundColor: '#27272a',
    color: '#fff',
    borderRadius: 8,
    paddingHorizontal: 14,
    paddingVertical: 10,
    fontSize: 18,
    fontWeight: '700',
    textAlign: 'center',
    borderWidth: 1,
    borderColor: '#3f3f46',
  },
  vehicleHeightUnit: {
    color: '#a1a1aa',
    fontSize: 16,
    fontWeight: '500',
  },
  vehicleHeightHint: {
    color: '#6b7280',
    fontSize: 12,
    marginTop: 8,
    textAlign: 'center',
  },
});
