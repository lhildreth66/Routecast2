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
  ToastAndroid,
} from 'react-native';
import * as Clipboard from 'expo-clipboard';

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
import { router, useFocusEffect, usePathname, useSegments } from 'expo-router';
import Constants from 'expo-constants';
import * as Notifications from 'expo-notifications';
import axios from 'axios';
import AsyncStorage from '@react-native-async-storage/async-storage';
import DateTimePicker from '@react-native-community/datetimepicker';
import { format } from 'date-fns';
import { WebView } from 'react-native-webview';
import { API_BASE, API_BASE_ERROR, API_BASE_SOURCE, buildUrl } from './apiConfig';
import { getNotificationCounts } from './notificationHistory';

const { width: SCREEN_WIDTH } = Dimensions.get('window');

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
  const [origin, setOrigin] = useState('');
  const [destination, setDestination] = useState('');
  const [loading, setLoading] = useState(false);
  const perfRef = useRef<{ submit?: number; request?: number; response?: number }>({});
  const [error, setError] = useState('');
  const [alertsEnabled, setAlertsEnabled] = useState(false);
  const [recentRoutes, setRecentRoutes] = useState<SavedRoute[]>([]);
  const [favoriteRoutes, setFavoriteRoutes] = useState<SavedRoute[]>([]);
  const [favoriteIds, setFavoriteIds] = useState<Set<string>>(new Set());
  const [favoriteSignatures, setFavoriteSignatures] = useState<Set<string>>(new Set());
  const [showFavorites, setShowFavorites] = useState(false);
  const [saveMessage, setSaveMessage] = useState('');
  const [pushToken, setPushToken] = useState<string | null>(null);
  const [pushPermissionStatus, setPushPermissionStatus] = useState<Notifications.PermissionStatus | 'unsupported' | 'error' | null>(null);
  const [pushToggleLoading, setPushToggleLoading] = useState(false);
  const [pushDebugLines, setPushDebugLines] = useState<string[]>([]);
  const [lastToggleAt, setLastToggleAt] = useState<string | null>(null);
  const [lastRegisterResult, setLastRegisterResult] = useState<string | null>(null);
  const [lastTestResult, setLastTestResult] = useState<string | null>(null);
  const [notificationTotal, setNotificationTotal] = useState(0);
  const [notificationUnseen, setNotificationUnseen] = useState(0);
  const [healthStatus, setHealthStatus] = useState<string>('pending');
  const [healthSnippet, setHealthSnippet] = useState<string>('');
  const [healthStatusCode, setHealthStatusCode] = useState<number | null>(null);
  
  // Autocomplete state
  const [originSuggestions, setOriginSuggestions] = useState<AutocompleteSuggestion[]>([]);
  const [destSuggestions, setDestSuggestions] = useState<AutocompleteSuggestion[]>([]);
  const [showOriginSuggestions, setShowOriginSuggestions] = useState(false);
  const [showDestSuggestions, setShowDestSuggestions] = useState(false);
  const [autocompleteLoading, setAutocompleteLoading] = useState(false);
  
  // Vehicle & Trucker mode
  const [vehicleType, setVehicleType] = useState('car');
  const [truckerMode, setTruckerMode] = useState(false);
  const [vehicleHeightFt, setVehicleHeightFt] = useState('13.5');
  const [showVehicleSelector, setShowVehicleSelector] = useState(false);
  
  // Departure time
  const [departureTime, setDepartureTime] = useState(new Date());
  const [showDatePicker, setShowDatePicker] = useState(false);
  const [useCustomTime, setUseCustomTime] = useState(false);
  
  // Multi-stop
  const [stops, setStops] = useState<StopPoint[]>([]);
  const [showAddStop, setShowAddStop] = useState(false);
  const [newStopLocation, setNewStopLocation] = useState('');
  const [newStopType, setNewStopType] = useState('stop');
  
  // Radar map state
  const [showRadarMap, setShowRadarMap] = useState(false);

  const pathname = usePathname();
  const segments = useSegments();

  const isProductionEnv = process.env.EXPO_PUBLIC_ENVIRONMENT === 'production' || process.env.NODE_ENV === 'production';
  const showDebugPanels = !isProductionEnv && (__DEV__ || process.env.EXPO_PUBLIC_SHOW_DEBUG_PANELS === 'true');
  const showApiBaseError = __DEV__ && !!API_BASE_ERROR;
  const showTruckSpecs = truckerMode || ['semi', 'truck', 'trailer'].includes(vehicleType);

  useEffect(() => {
    fetchRecentRoutes();
    fetchFavoriteRoutes();
    loadCachedRoute();
    console.log('BACKEND:', process.env.EXPO_PUBLIC_BACKEND_URL);
    console.log('[startup] API_BASE', API_BASE, 'source', API_BASE_SOURCE);
    runHealthCheck();
  }, []);

  useEffect(() => {
    const loadPushPreferences = async () => {
      try {
        const storedEnabled = await AsyncStorage.getItem('pushAlertsEnabled');
        if (storedEnabled !== null) {
          setAlertsEnabled(storedEnabled === 'true');
        }
        const storedToken = await AsyncStorage.getItem('expoPushToken');
        if (storedToken) {
          setPushToken(storedToken);
        }
        const storedDebug = await AsyncStorage.getItem('pushDebugLog');
        if (storedDebug) {
          setPushDebugLines(JSON.parse(storedDebug));
        }
        const storedToggle = await AsyncStorage.getItem('pushLastToggleAt');
        if (storedToggle) {
          setLastToggleAt(storedToggle);
        }
        const storedRegister = await AsyncStorage.getItem('pushLastRegisterResult');
        if (storedRegister) {
          setLastRegisterResult(storedRegister);
        }
        const storedTest = await AsyncStorage.getItem('pushLastTestResult');
        if (storedTest) {
          setLastTestResult(storedTest);
        }
      } catch (e) {
        console.log('[push] error loading stored preferences', e);
      }
    };

    loadPushPreferences();

    if (Platform.OS === 'android') {
      Notifications.setNotificationChannelAsync('default', {
        name: 'default',
        importance: Notifications.AndroidImportance.MAX,
      }).catch((err) => console.log('[push] channel setup error', err));

      Notifications.setNotificationChannelAsync('weather-alerts', {
        name: 'Weather Alerts',
        importance: Notifications.AndroidImportance.MAX,
        vibrationPattern: [0, 250, 250, 250],
        sound: 'default',
        lightColor: '#FF0000',
        lockscreenVisibility: Notifications.AndroidNotificationVisibility.PUBLIC,
        bypassDnd: true,
      }).catch((err) => console.log('[push] weather channel error', err));
    }
  }, []);

  const refreshNotificationCounts = useCallback(async () => {
    const { total, unseen } = await getNotificationCounts();
    setNotificationTotal(total);
    setNotificationUnseen(unseen);
  }, []);

  useFocusEffect(
    useCallback(() => {
      refreshNotificationCounts();
    }, [refreshNotificationCounts]),
  );

  useEffect(() => {
    refreshNotificationCounts();
    const sub = Notifications.addNotificationReceivedListener(() => {
      refreshNotificationCounts();
    });
    return () => {
      sub.remove();
    };
  }, [refreshNotificationCounts]);

  const loadCachedRoute = async () => {
    try {
      const cached = await AsyncStorage.getItem('lastRoute');
      if (cached) {
        const data = JSON.parse(cached);
        // Optionally pre-fill from cache
      }
    } catch (e) {
      // ignore cache errors
    }
  };

  const runHealthCheck = async () => {
    const url = buildUrl('health');
    try {
      const res = await fetch(url, { method: 'GET' });
      const text = await res.text();
      const snippet = text.slice(0, 120);
      setHealthStatusCode(res.status);
      setHealthSnippet(snippet);
      setHealthStatus(res.ok ? 'ok' : 'error');
      console.log('[net] health', { base: API_BASE, status: res.status, body: snippet });
    } catch (err) {
      setHealthStatus('error');
      setHealthSnippet(String(err).slice(0, 120));
      console.log('[net] health error', { base: API_BASE, error: String(err) });
    }
  };

  const showToast = (message: string) => {
    if (Platform.OS === 'android') {
      ToastAndroid.show(message, ToastAndroid.SHORT);
    } else {
      Alert.alert('Favorites', message);
    }
  };

  const showPushMessage = (message: string) => {
    if (Platform.OS === 'android') {
      ToastAndroid.show(message, ToastAndroid.SHORT);
    } else {
      Alert.alert('Push Notifications', message);
    }
  };

  const pushDebugLog = async (message: string) => {
    console.log(message);
    setPushDebugLines((prev) => {
      const next = [...prev, `${new Date().toISOString()} ${message}`].slice(-50);
      AsyncStorage.setItem('pushDebugLog', JSON.stringify(next)).catch((err) =>
        console.log('[push] failed to persist debug log', err)
      );
      return next;
    });
  };

  const registerForPushNotificationsAsync = async (): Promise<{
    status: Notifications.PermissionStatus | 'unsupported' | 'error';
    token: string | null;
  }> => {
    if (Platform.OS === 'web') {
      pushDebugLog('[push] web platform - notifications unsupported');
      setPushPermissionStatus('unsupported');
      return { status: 'unsupported', token: null };
    }

    pushDebugLog('[push] before requesting permissions');
    try {
      const { status: existingStatus } = await Notifications.getPermissionsAsync();
      let finalStatus = existingStatus;

      if (existingStatus !== 'granted') {
        const permissionResponse = await Notifications.requestPermissionsAsync();
        finalStatus = permissionResponse.status;
      }

      pushDebugLog(`[push] permission status ${finalStatus}`);
      setPushPermissionStatus(finalStatus);

      if (finalStatus !== 'granted') {
        return { status: finalStatus, token: null };
      }

      const projectId = Constants?.expoConfig?.extra?.eas?.projectId;
      const tokenResponse = await Notifications.getExpoPushTokenAsync(
        projectId ? { projectId } : undefined
      );
      pushDebugLog(`[push] obtained expo push token ${tokenResponse?.data}`);
      setPushToken(tokenResponse?.data || null);
      await AsyncStorage.setItem('expoPushToken', tokenResponse?.data || '');

      return { status: finalStatus, token: tokenResponse?.data || null };
    } catch (err) {
      pushDebugLog(`[push] error during registration ${String(err)}`);
      setPushPermissionStatus('error');
      return { status: 'error', token: null };
    }
  };

  const handleTogglePushNotifications = async (nextValue: boolean) => {
    const previousValue = alertsEnabled;
    setLastToggleAt(new Date().toISOString());
    AsyncStorage.setItem('pushLastToggleAt', new Date().toISOString()).catch(() => {});
    pushDebugLog(`[push] toggle pressed old=${previousValue} new=${nextValue}`);
    setAlertsEnabled(nextValue);
    setPushToggleLoading(true);

    try {
      if (nextValue) {
        const { status, token } = await registerForPushNotificationsAsync();

        if (status !== 'granted' || !token) {
          pushDebugLog(`[push] permission denied or token missing status=${status}`);
          setAlertsEnabled(false);
          await AsyncStorage.setItem('pushAlertsEnabled', 'false');
          showPushMessage(
            status === 'unsupported'
              ? 'Push notifications require a physical device; web/emulator will not prompt. Please try on a real device.'
              : 'Push notifications need permission. Please enable in Settings.'
          );
          return;
        }

        pushDebugLog(`[push] saving token to backend token=${token}`);
        try {
          const response = await axios.post(buildUrl('notifications/register'), {
            expoPushToken: token,
            enabled: true,
          });
          const msg = JSON.stringify(response?.data || {});
          setLastRegisterResult(msg);
          AsyncStorage.setItem('pushLastRegisterResult', msg).catch(() => {});
          pushDebugLog(`[push] backend save response ${msg}`);
          await AsyncStorage.setItem('pushAlertsEnabled', 'true');
          showPushMessage('Push weather alerts enabled');
        } catch (backendErr) {
          const errMsg = (backendErr as any)?.message || String(backendErr);
          setLastRegisterResult(errMsg);
          AsyncStorage.setItem('pushLastRegisterResult', errMsg).catch(() => {});
          pushDebugLog(`[push] backend save failed ${errMsg}`);
          setAlertsEnabled(false);
          await AsyncStorage.setItem('pushAlertsEnabled', 'false');
          showPushMessage('Could not save push token. Try again.');
        }
      } else {
        pushDebugLog('[push] toggled off - clearing local state');
        await AsyncStorage.setItem('pushAlertsEnabled', 'false');
        setPushPermissionStatus(null);

        if (pushToken) {
          try {
            const disableResponse = await axios.post(buildUrl('notifications/register'), {
              expoPushToken: pushToken,
              enabled: false,
            });
            const msg = JSON.stringify(disableResponse?.data || {});
            setLastRegisterResult(msg);
            AsyncStorage.setItem('pushLastRegisterResult', msg).catch(() => {});
            pushDebugLog(`[push] backend disable response ${msg}`);
          } catch (disableErr) {
            const errMsg = (disableErr as any)?.message || String(disableErr);
            setLastRegisterResult(errMsg);
            AsyncStorage.setItem('pushLastRegisterResult', errMsg).catch(() => {});
            pushDebugLog(`[push] backend disable failed ${errMsg}`);
          }
        }
      }
    } catch (err) {
      pushDebugLog(`[push] toggle error ${String(err)}`);
      setAlertsEnabled(previousValue);
      showPushMessage('Unable to update push notifications right now.');
    } finally {
      setPushToggleLoading(false);
    }
  };

  const handleSendTestNotification = async () => {
    if (!pushToken) {
      showPushMessage('Enable push alerts first so we can generate a token.');
      return;
    }

    pushDebugLog(`[push] sending test notification for token ${pushToken}`);
    try {
      const response = await axios.post(buildUrl('notifications/send'), {});
      const msg = JSON.stringify(response?.data || {});
      setLastTestResult(msg);
      AsyncStorage.setItem('pushLastTestResult', msg).catch(() => {});
      pushDebugLog(`[push] test notification response ${msg}`);
      showPushMessage(response?.data?.success ? 'Test notification sent (check device)' : 'Test notification failed');
    } catch (err) {
      const errMsg = (err as any)?.message || String(err);
      setLastTestResult(errMsg);
      AsyncStorage.setItem('pushLastTestResult', errMsg).catch(() => {});
      pushDebugLog(`[push] test notification error ${errMsg}`);
      showPushMessage('Test notification failed');
    }
  };

  const copyPushDebugLogs = async () => {
    const payload = [
      `API_BASE: ${API_BASE}`,
      `lastToggleAt: ${lastToggleAt || 'n/a'}`,
      `permission: ${pushPermissionStatus || 'unknown'}`,
      `tokenPresent: ${!!pushToken}`,
      `lastRegister: ${lastRegisterResult || 'n/a'}`,
      `lastTest: ${lastTestResult || 'n/a'}`,
      'recentLogs:',
      ...pushDebugLines.slice(-6),
    ].join('\n');
    await Clipboard.setStringAsync(payload);
    showPushMessage('Push debug logs copied');
  };

  const stopsKey = (list?: StopPoint[]) => JSON.stringify(list || []);

  const routeSignature = (route: { origin: string; destination: string; stops?: StopPoint[] }) =>
    `${route.origin.trim()}__${route.destination.trim()}__${stopsKey(route.stops || [])}`;

  const routesMatch = (route: SavedRoute, originText: string, destinationText: string, compareStops: StopPoint[]) => {
    return (
      route.origin === originText &&
      route.destination === destinationText &&
      stopsKey(route.stops) === stopsKey(compareStops)
    );
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
      const response = await axios.get(buildUrl('geocode/autocomplete'), {
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
      console.warn('Autocomplete error');
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
    try {
      const path = buildUrl('routes/history');
      const response = await axios.get(path);
      setRecentRoutes(response.data.slice(0, 5));
    } catch (err) {
      console.warn('Error fetching history');
    }
  };

  const fetchFavoriteRoutes = async () => {
    try {
      const path = buildUrl('routes/favorites');
      const response = await axios.get(path);
      setFavoriteRoutes(response.data);
      setFavoriteIds(new Set(response.data.map((r: SavedRoute) => r.id)));
      setFavoriteSignatures(new Set(response.data.map((r: SavedRoute) => routeSignature(r))));
    } catch (err) {
      console.warn('Error fetching favorites');
    }
  };

  const handleGetWeather = async () => {
    if (!origin.trim() || !destination.trim()) {
      setError('Please enter both origin and destination');
      return;
    }

    Keyboard.dismiss();
    setLoading(true);
    perfRef.current.submit = Date.now();
    setError('');

    let requestData: any;

    try {
      const parsedHeight = parseFloat(vehicleHeightFt);
      const vehicleHeight = Number.isFinite(parsedHeight) && parsedHeight > 0 ? parsedHeight : 13.5;
      const resolvedMode = truckerMode || vehicleType === 'semi' || vehicleType === 'truck' ? 'truck' : vehicleType === 'rv' ? 'boondocker' : 'standard';
      const truckProfile = resolvedMode === 'truck'
        ? {
            vehicle_height_ft: vehicleHeight,
            vehicle_weight_lbs: 80000,
            vehicle_length_ft: 53,
            axle_count: 5,
            hazmat: false,
          }
        : undefined;
      const boondockerPrefs = resolvedMode === 'boondocker'
        ? {
            avoid_highways: true,
            avoid_tolls: true,
            prefer_campgrounds: true,
          }
        : undefined;

      requestData = {
        origin: origin.trim(),
        destination: destination.trim(),
        stops: stops,
        push_token: pushToken || undefined,
        vehicle_type: vehicleType,
        trucker_mode: truckerMode,
        mode: resolvedMode,
        ...truckProfile,
        ...boondockerPrefs,
      };
      
      if (useCustomTime) {
        requestData.departure_time = departureTime.toISOString();
      }

      perfRef.current.request = Date.now();
      console.log('[route-request]', {
        endpoint: buildUrl('route/weather'),
        mode: resolvedMode,
        vehicleType,
        trucker_mode: truckerMode,
        truckProfile,
        boondockerPrefs,
        perf: { submit: perfRef.current.submit, request: perfRef.current.request },
      });

      const response = await axios.post(buildUrl('route/weather'), requestData);
      perfRef.current.response = Date.now();
      console.log('[route-response]', {
        endpoint: buildUrl('route/weather'),
        ms_total: perfRef.current.response - (perfRef.current.submit || perfRef.current.response),
        ms_to_response: perfRef.current.response - (perfRef.current.request || perfRef.current.response),
      });

      // Cache the route for offline
      await AsyncStorage.setItem('lastRoute', JSON.stringify(response.data));

      router.push({
        pathname: '/route',
        params: { routeData: JSON.stringify(response.data), perf: JSON.stringify(perfRef.current) },
      });
    } catch (err: any) {
      const status = err?.response?.status;
      const body = err?.response?.data;

      const summarizeBody = () => {
        if (!body) return '';
        if (typeof body === 'string') return body.slice(0, 500);
        try {
          return JSON.stringify(body).slice(0, 500);
        } catch {
          return '[unserializable body]';
        }
      };

      const detail = summarizeBody();
      console.error('[route/weather] request failed', {
        status,
        url: buildUrl('route/weather'),
        detail: detail || err?.message,
        request: requestData,
      });

      setError(
        (typeof body === 'object' && body?.detail) ||
          detail ||
          err?.message ||
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

  const toggleFavorite = async (route: SavedRoute) => {
    if (!route?.id) {
      return;
    }

    const currentlyFavorite = favoriteIds.has(route.id);
    const signature = routeSignature(route);

    console.log('[fav] pressed', {
      id: route.id,
      origin: route.origin,
      destination: route.destination,
      wasFavorited: currentlyFavorite,
      newFavorited: !currentlyFavorite,
      signature,
    });

    // Optimistic UI update
    setFavoriteIds((prev) => {
      const next = new Set(prev);
      if (currentlyFavorite) {
        next.delete(route.id);
      } else {
        next.add(route.id);
      }
      return next;
    });

    setFavoriteSignatures((prev) => {
      const next = new Set(prev);
      if (currentlyFavorite) {
        next.delete(signature);
      } else {
        next.add(signature);
      }
      return next;
    });

    setFavoriteRoutes((prev) => {
      if (currentlyFavorite) {
        return prev.filter((r) => r.id !== route.id);
      }
      const exists = prev.some((r) => r.id === route.id);
      return exists ? prev : [...prev, route];
    });

    try {
      if (currentlyFavorite) {
        await axios.delete(buildUrl(`routes/favorites/${route.id}`));
      } else {
        await axios.post(buildUrl('routes/favorites'), {
          origin: route.origin,
          destination: route.destination,
          stops: route.stops || [],
        });
      }

      // Sync store with server response
      fetchFavoriteRoutes();
      console.log('[fav] save result', { ok: true, status: 'success' });
    } catch (err) {
      // Revert optimistic change on error
      setFavoriteIds((prev) => {
        const next = new Set(prev);
        if (currentlyFavorite) {
          next.add(route.id);
        } else {
          next.delete(route.id);
        }
        return next;
      });

      setFavoriteSignatures((prev) => {
        const next = new Set(prev);
        if (currentlyFavorite) {
          next.add(signature);
        } else {
          next.delete(signature);
        }
        return next;
      });

      setFavoriteRoutes((prev) => {
        if (currentlyFavorite) {
          const exists = prev.some((r) => r.id === route.id);
          return exists ? prev : [...prev, route];
        }
        return prev.filter((r) => r.id !== route.id);
      });

      console.error('Error updating favorite:', err);
      console.log('[fav] save result', { ok: false, status: 'error', body: String(err) });
      showToast('Failed to update favorite. Please try again.');
    }
  };

  const toggleCurrentRouteFavorite = async () => {
    const trimmedOrigin = origin.trim();
    const trimmedDestination = destination.trim();

    if (!trimmedOrigin || !trimmedDestination) {
      setError('Enter a route first to save as favorite');
      return;
    }

    const existing = favoriteRoutes.find((r) =>
      routesMatch(r, trimmedOrigin, trimmedDestination, stops)
    );

    const tempId = `temp-${Date.now()}`;
    const optimisticRoute: SavedRoute = existing || {
      id: tempId,
      origin: trimmedOrigin,
      destination: trimmedDestination,
      stops,
      created_at: new Date().toISOString(),
      is_favorite: true,
    };

    const currentlyFavorite = !!existing;
    const signature = routeSignature({ origin: trimmedOrigin, destination: trimmedDestination, stops });

    console.log('[fav] pressed', {
      id: existing?.id || null,
      origin: trimmedOrigin,
      destination: trimmedDestination,
      stopsCount: stops.length,
      wasFavorited: currentlyFavorite,
      newFavorited: !currentlyFavorite,
      signature,
    });

    // Optimistic state change
    setFavoriteIds((prev) => {
      const next = new Set(prev);
      if (currentlyFavorite && existing) {
        next.delete(existing.id);
      } else {
        next.add(optimisticRoute.id);
      }
      return next;
    });

    setFavoriteSignatures((prev) => {
      const next = new Set(prev);
      if (currentlyFavorite) {
        next.delete(signature);
      } else {
        next.add(signature);
      }
      return next;
    });

    setFavoriteRoutes((prev) => {
      if (currentlyFavorite && existing) {
        return prev.filter((r) => r.id !== existing.id);
      }
      return [...prev, optimisticRoute];
    });

    try {
      if (currentlyFavorite && existing) {
        await axios.delete(buildUrl(`routes/favorites/${existing.id}`));
      } else {
        const res = await axios.post(buildUrl('routes/favorites'), {
          origin: trimmedOrigin,
          destination: trimmedDestination,
          stops,
        });

        if (res?.data?.id) {
          const savedRoute: SavedRoute = res.data;
          setFavoriteIds((prev) => {
            const next = new Set(prev);
            next.delete(optimisticRoute.id);
            next.add(savedRoute.id);
            return next;
          });

          setFavoriteRoutes((prev) =>
            prev.map((r) => (r.id === optimisticRoute.id ? savedRoute : r))
          );
        }
      }

      fetchFavoriteRoutes();
      console.log('[fav] save result', { ok: true, status: 'success' });
    } catch (err) {
      console.log('[fav] save result', { ok: false, status: 'error', body: String(err) });
      // Revert on failure
      setFavoriteIds((prev) => {
        const next = new Set(prev);
        if (currentlyFavorite && existing) {
          next.add(existing.id);
        } else {
          next.delete(optimisticRoute.id);
        }
        return next;
      });

      setFavoriteSignatures((prev) => {
        const next = new Set(prev);
        if (currentlyFavorite) {
          next.add(signature);
        } else {
          next.delete(signature);
        }
        return next;
      });

      setFavoriteRoutes((prev) => {
        if (currentlyFavorite && existing) {
          const exists = prev.some((r) => r.id === existing.id);
          return exists ? prev : [...prev, existing];
        }
        return prev.filter((r) => r.id !== optimisticRoute.id);
      });

      console.error('Error saving favorite:', err);
      showToast('Failed to update favorite. Please try again.');
    }
  };

  const removeFavorite = async (routeId: string) => {
    const route = favoriteRoutes.find((r) => r.id === routeId);
    const signature = route ? routeSignature(route) : null;

    console.log('[fav] pressed remove', { id: routeId, signature });

    setFavoriteRoutes((prev) => prev.filter((r) => r.id !== routeId));
    setFavoriteIds((prev) => {
      const next = new Set(prev);
      next.delete(routeId);
      return next;
    });
    if (signature) {
      setFavoriteSignatures((prev) => {
        const next = new Set(prev);
        next.delete(signature);
        return next;
      });
    }

    try {
      await axios.delete(buildUrl(`routes/favorites/${routeId}`));
      fetchFavoriteRoutes();
      console.log('[fav] save result', { ok: true, status: 'removed', id: routeId });
    } catch (err) {
      console.log('[fav] save result', { ok: false, status: 'remove-error', body: String(err) });
      if (route) {
        setFavoriteRoutes((prev) => [...prev, route]);
        setFavoriteIds((prev) => {
          const next = new Set(prev);
          next.add(routeId);
          return next;
        });
        if (signature) {
          setFavoriteSignatures((prev) => {
            const next = new Set(prev);
            next.add(signature);
            return next;
          });
        }
      }
      showToast('Failed to remove favorite. Please try again.');
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

  const trimmedOrigin = origin.trim();
  const trimmedDestination = destination.trim();
  const currentFavoriteForInput = favoriteRoutes.find((r) =>
    routesMatch(r, trimmedOrigin, trimmedDestination, stops)
  );
  const currentRouteSignature = routeSignature({ origin: trimmedOrigin, destination: trimmedDestination, stops });
  const isCurrentRouteFavorite = favoriteSignatures.has(currentRouteSignature) || !!currentFavoriteForInput;

  return (
    <View style={styles.container}>
      {showApiBaseError && (
        <View style={styles.bannerError}>
          <Text style={styles.bannerErrorText}>Backend URL missing. Set EXPO_PUBLIC_BACKEND_URL.</Text>
        </View>
      )}
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
                  style={styles.favoriteButton}
                  onPress={toggleCurrentRouteFavorite}
                >
                  <Ionicons
                    name={isCurrentRouteFavorite ? 'heart' : 'heart-outline'}
                    size={24}
                    color={isCurrentRouteFavorite ? '#ef4444' : '#eab308'}
                  />
                </TouchableOpacity>
              </View>

              {/* App Description */}
              <View style={styles.descriptionBox}>
                <Text style={styles.descriptionText}>
                  Weather-aware routing with live alerts and hazard intelligence for every mile. Start your 7-day free trial and drive with confidence.
                </Text>
              </View>

              <View style={styles.ctaRow}>
                <TouchableOpacity style={styles.primaryCta} onPress={() => router.push('/subscription')}>
                  <Ionicons name="sparkles" size={20} color="#0f172a" />
                  <View style={styles.ctaTextGroup}>
                    <Text style={styles.primaryCtaText}>Start Free Trial</Text>
                    <Text style={styles.primaryCtaSub}>7-day premium access, cancel anytime</Text>
                  </View>
                  <Ionicons name="arrow-forward" size={18} color="#0f172a" />
                </TouchableOpacity>

                <TouchableOpacity style={styles.secondaryCta} onPress={() => router.push('/user-guide')}>
                  <Text style={styles.secondaryCtaText}>Learn More</Text>
                </TouchableOpacity>
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
                  />
                  {autocompleteLoading && origin.length >= 2 && (
                    <ActivityIndicator size="small" color="#eab308" style={{ marginRight: 8 }} />
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
                  />
                  {autocompleteLoading && destination.length >= 2 && (
                    <ActivityIndicator size="small" color="#eab308" style={{ marginRight: 8 }} />
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
                    onPress={() => setShowDatePicker(true)}
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
                    <Text style={styles.truckerSubtext}>Wind & height warnings</Text>
                  </View>
                </View>
                <Switch
                  value={truckerMode}
                  onValueChange={setTruckerMode}
                  trackColor={{ false: '#3f3f46', true: '#f59e0b80' }}
                  thumbColor={truckerMode ? '#f59e0b' : '#71717a'}
                />
              </View>

              {showTruckSpecs && (
                <View style={styles.truckerSpecs}>
                  <Text style={styles.truckerLabel}>Vehicle Height (ft)</Text>
                  <TextInput
                    value={vehicleHeightFt}
                    onChangeText={setVehicleHeightFt}
                    keyboardType="decimal-pad"
                    placeholder="e.g., 13.5"
                    placeholderTextColor="#6b7280"
                    style={styles.truckerInput}
                  />
                  <Text style={styles.truckerHelper}>Used for low-clearance routing and warnings.</Text>
                </View>
              )}

              {showDebugPanels && (
                <View style={styles.healthCard}>
                  <Text style={styles.healthTitle}>Health Check</Text>
                  <Text style={styles.healthLine}>API Base: {API_BASE}</Text>
                  <Text style={styles.healthLine}>Source: {API_BASE_SOURCE}</Text>
                  {API_BASE_ERROR ? <Text style={styles.healthLine}>Base Warning: {API_BASE_ERROR}</Text> : null}
                  <Text style={styles.healthLine}>Status: {healthStatus} ({healthStatusCode ?? 'n/a'})</Text>
                  <Text style={styles.healthLine}>Body: {healthSnippet || 'pending...'}</Text>
                  <TouchableOpacity style={styles.healthButton} onPress={runHealthCheck}>
                    <Ionicons name="refresh" size={16} color="#0f172a" />
                    <Text style={styles.healthButtonText}>Refresh Health</Text>
                  </TouchableOpacity>
                </View>
              )}

              {/* Weather Alerts Toggle */}
              <View style={styles.alertsToggle}>
                <View style={styles.alertsLeft}>
                  <Ionicons name="notifications-outline" size={22} color="#eab308" />
                  <Text style={styles.alertsText}>Push Weather Alerts</Text>
                </View>
                <View style={styles.alertsActions}>
                  <TouchableOpacity
                    style={styles.notificationButton}
                    onPress={() => router.push('/notifications' as any)}
                    accessibilityRole="button"
                    accessibilityLabel="Open notification history"
                  >
                    <Ionicons name="notifications" size={20} color="#eab308" />
                    <Text style={styles.notificationText}>
                      {notificationTotal ? `${notificationTotal}` : 'History'}
                    </Text>
                    {notificationUnseen > 0 ? (
                      <View style={styles.notificationBadge}>
                        <Text style={styles.notificationBadgeText}>
                          {notificationUnseen > 99 ? '99+' : notificationUnseen}
                        </Text>
                      </View>
                    ) : null}
                  </TouchableOpacity>
                  <Switch
                    value={alertsEnabled}
                    onValueChange={handleTogglePushNotifications}
                    disabled={pushToggleLoading}
                    trackColor={{ false: '#3f3f46', true: '#eab30880' }}
                    thumbColor={alertsEnabled ? '#eab308' : '#71717a'}
                  />
                </View>
              </View>

              <View style={styles.pushActionsRow}>
                <Text style={styles.pushStatusText}>
                  {alertsEnabled
                    ? `Push alerts on${pushPermissionStatus ? ` (perm: ${pushPermissionStatus})` : ''}`
                    : 'Push alerts off'}
                </Text>
                {__DEV__ && (
                  <TouchableOpacity
                    style={[
                      styles.pushTestButton,
                      (!pushToken || !alertsEnabled || pushToggleLoading) && styles.pushTestButtonDisabled,
                    ]}
                    onPress={handleSendTestNotification}
                    disabled={!pushToken || !alertsEnabled || pushToggleLoading}
                  >
                    <Ionicons name="paper-plane-outline" size={16} color="#eab308" />
                    <Text style={styles.pushTestButtonText}>Send Test Notification</Text>
                  </TouchableOpacity>
                )}
              </View>

              {showDebugPanels && (
                <View style={styles.pushDebugSection}>
                  <Text style={styles.debugTitle}>Push Debug</Text>
                  <Text style={styles.debugLine}>Last toggle: {lastToggleAt || 'n/a'}</Text>
                  <Text style={styles.debugLine}>Permission: {pushPermissionStatus || 'unknown'}</Text>
                  <Text style={styles.debugLine}>Token present: {pushToken ? 'yes' : 'no'}</Text>
                  <Text style={styles.debugLine}>Last register: {lastRegisterResult || 'n/a'}</Text>
                  <Text style={styles.debugLine}>Last test: {lastTestResult || 'n/a'}</Text>
                  <Text style={styles.debugLine}>Recent logs:</Text>
                  {pushDebugLines.slice(-6).map((line, idx) => (
                    <Text key={idx} style={styles.debugLine}>• {line}</Text>
                  ))}
                  <TouchableOpacity style={styles.copyLogsButton} onPress={copyPushDebugLogs}>
                    <Ionicons name="copy-outline" size={16} color="#0f172a" />
                    <Text style={styles.copyLogsButtonText}>Copy Debug Logs</Text>
                  </TouchableOpacity>
                </View>
              )}

              {/* Error Message */}
              {error ? (
                <View style={styles.errorContainer}>
                  <Ionicons name="alert-circle" size={18} color="#ef4444" />
                  <Text style={styles.errorText}>{error}</Text>
                </View>
              ) : null}

              {loading && (
                <View style={styles.skeletonContainer}>
                  <View style={styles.skeletonRow}>
                    <View style={styles.skeletonBadge} />
                    <View style={styles.skeletonLineLong} />
                  </View>
                  <View style={styles.skeletonRow}>
                    <View style={styles.skeletonBadge} />
                    <View style={styles.skeletonLineShort} />
                  </View>
                  <View style={styles.skeletonRow}>
                    <View style={styles.skeletonLineLong} />
                  </View>
                </View>
              )}

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

      {/* Date Time Picker Modal */}
      {showDatePicker && (
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
                // Native DateTimePicker for iOS/Android
                <DateTimePicker
                  value={departureTime}
                  mode="datetime"
                  display="spinner"
                  onChange={(event, date) => {
                    if (date) setDepartureTime(date);
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
  bannerError: {
    backgroundColor: '#ef4444',
    padding: 10,
    alignItems: 'center',
  },
  bannerErrorText: {
    color: '#fff',
    fontWeight: '700',
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
  ctaRow: {
    gap: 10,
    marginBottom: 16,
  },
  primaryCta: {
    backgroundColor: '#22c55e',
    borderRadius: 12,
    padding: 14,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    justifyContent: 'space-between',
  },
  ctaTextGroup: {
    flex: 1,
    gap: 2,
  },
  primaryCtaText: {
    color: '#0f172a',
    fontSize: 16,
    fontWeight: '800',
  },
  primaryCtaSub: {
    color: '#0f172a',
    fontSize: 12,
    fontWeight: '600',
  },
  secondaryCta: {
    borderRadius: 12,
    padding: 12,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#3f3f46',
    backgroundColor: '#18181b',
  },
  secondaryCtaText: {
    color: '#e5e7eb',
    fontSize: 14,
    fontWeight: '700',
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
  alertsActions: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  notificationButton: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 8,
    paddingHorizontal: 10,
    backgroundColor: '#0b1224',
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#1f2937',
  },
  notificationText: { color: '#e5e7eb', marginLeft: 6, fontSize: 14, fontWeight: '600' },
  notificationBadge: {
    marginLeft: 6,
    backgroundColor: '#ef4444',
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 8,
    minWidth: 24,
    alignItems: 'center',
    justifyContent: 'center',
  },
  notificationBadgeText: { color: '#fff', fontSize: 12, fontWeight: '700' },
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
  pushDebugSection: {
    backgroundColor: '#1f2937',
    borderRadius: 10,
    padding: 10,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: '#374151',
    gap: 4,
  },
  debugTitle: {
    color: '#e5e7eb',
    fontWeight: '700',
    fontSize: 13,
  },
  debugLine: {
    color: '#cbd5e1',
    fontSize: 12,
  },
  copyLogsButton: {
    marginTop: 6,
    backgroundColor: '#eab308',
    borderRadius: 8,
    paddingVertical: 8,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
  },
  copyLogsButtonText: {
    color: '#0f172a',
    fontWeight: '700',
    fontSize: 13,
  },
  pushActionsRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 12,
    gap: 10,
  },
  pushStatusText: {
    color: '#a1a1aa',
    fontSize: 12,
    flex: 1,
  },
  pushTestButton: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#27272a',
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 8,
    gap: 6,
    borderWidth: 1,
    borderColor: '#3f3f46',
  },
  pushTestButtonDisabled: {
    opacity: 0.6,
  },
  pushTestButtonText: {
    color: '#eab308',
    fontSize: 12,
    fontWeight: '600',
  },
  healthCard: {
    backgroundColor: '#1f2937',
    borderRadius: 10,
    padding: 10,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: '#374151',
    gap: 4,
  },
  healthTitle: {
    color: '#e5e7eb',
    fontWeight: '700',
    fontSize: 13,
  },
  healthLine: {
    color: '#cbd5e1',
    fontSize: 12,
  },
  healthButton: {
    marginTop: 6,
    backgroundColor: '#22c55e',
    borderRadius: 8,
    paddingVertical: 8,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
  },
  healthButtonText: {
    color: '#0f172a',
    fontWeight: '700',
    fontSize: 13,
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
  skeletonContainer: {
    backgroundColor: '#1f2937',
    padding: 12,
    borderRadius: 12,
    marginBottom: 10,
    gap: 8,
  },
  skeletonRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  skeletonBadge: {
    width: 28,
    height: 28,
    borderRadius: 8,
    backgroundColor: '#334155',
  },
  skeletonLineLong: {
    flex: 1,
    height: 12,
    borderRadius: 6,
    backgroundColor: '#334155',
  },
  skeletonLineShort: {
    width: 120,
    height: 12,
    borderRadius: 6,
    backgroundColor: '#334155',
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
  truckerSpecs: {
    backgroundColor: '#111827',
    borderRadius: 10,
    padding: 12,
    borderWidth: 1,
    borderColor: '#f59e0b20',
    marginBottom: 12,
    gap: 8,
  },
  truckerLabel: {
    color: '#e5e7eb',
    fontSize: 12,
    fontWeight: '600',
  },
  truckerInput: {
    backgroundColor: '#1f2937',
    color: '#fff',
    padding: 12,
    borderRadius: 8,
    fontSize: 15,
  },
  truckerHelper: {
    color: '#9ca3af',
    fontSize: 12,
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
});
