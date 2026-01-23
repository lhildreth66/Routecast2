import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TextInput,
  TouchableOpacity,
  ScrollView,
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  Keyboard,
  Switch,
  Modal,
  Alert,
  Linking,
  Animated,
} from 'react-native';
import * as Calendar from 'expo-calendar';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons, MaterialCommunityIcons } from '@expo/vector-icons';
import { router } from 'expo-router';
import axios from 'axios';
import AsyncStorage from '@react-native-async-storage/async-storage';
import * as Notifications from 'expo-notifications';
import { format } from 'date-fns';
import { API_BASE } from './apiConfig';
import { devToggleProEntitlement } from './utils/entitlements';
import CampPrepChat from './components/CampPrepChat';

// Vehicle types for safety scoring
const VEHICLE_TYPES = [
  { id: 'car', label: 'Car/Sedan', icon: 'car-sport-outline' },
  { id: 'semi', label: 'Semi Truck', icon: 'bus-outline' },
  { id: 'rv', label: 'RV/Motorhome', icon: 'home-outline' },
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

interface CalendarTrip {
  id: string;
  title: string;
  startDate: Date;
  endDate: Date;
  location?: string;
  parsedDestination?: string;
}

export default function HomeScreen() {
  const [origin, setOrigin] = useState('');
  const [destination, setDestination] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [alertsEnabled, setAlertsEnabled] = useState(false);
  const [pushToken, setPushToken] = useState<string | null>(null);
  const [testNotificationLoading, setTestNotificationLoading] = useState(false);
  const [testNotificationMessage, setTestNotificationMessage] = useState('');
  const [recentRoutes, setRecentRoutes] = useState<SavedRoute[]>([]);
  const [favoriteRoutes, setFavoriteRoutes] = useState<SavedRoute[]>([]);
  const [showFavorites, setShowFavorites] = useState(false);
  const [favoriteAdded, setFavoriteAdded] = useState(false);
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
  const [vehicleHeight, setVehicleHeight] = useState('13.5'); // Default semi truck height in feet
  
  // Departure time
  const [departureTime, setDepartureTime] = useState(new Date());
  const [showDatePicker, setShowDatePicker] = useState(false);
  const [useCustomTime, setUseCustomTime] = useState(false);
  
  const [isListening, setIsListening] = useState(false);
  const [speechSupported, setSpeechSupported] = useState(false);
  
  // Boondockers Pro Chat
  const [showCampPrep, setShowCampPrep] = useState(false);
  
  // Calendar integration
  const [calendarTrips, setCalendarTrips] = useState<CalendarTrip[]>([]);
  const [calendarPermission, setCalendarPermission] = useState(false);
  
  // Animations
  const fadeAnim = React.useRef(new Animated.Value(0)).current;
  const scaleAnim = React.useRef(new Animated.Value(1)).current;
  
  // Input focus states
  const [originFocused, setOriginFocused] = useState(false);
  const [destFocused, setDestFocused] = useState(false);

  // Navigation to dedicated Road Passability screen (Pro)
  
  // Multi-stop
  const [stops, setStops] = useState<StopPoint[]>([]);
  const [showAddStop, setShowAddStop] = useState(false);
  const [newStopLocation, setNewStopLocation] = useState('');
  const [newStopType, setNewStopType] = useState('stop');
  const [stopSuggestions, setStopSuggestions] = useState<AutocompleteSuggestion[]>([]);
  const [showStopSuggestions, setShowStopSuggestions] = useState(false);

  // Dev-only: long-press gesture counter for Pro entitlement toggle (5 taps)
  const [devTapCount, setDevTapCount] = useState(0);

  // Check for speech recognition support on web
  useEffect(() => {
    if (Platform.OS === 'web') {
      const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
      setSpeechSupported(!!SpeechRecognition);
    }
  }, []);

  useEffect(() => {
    fetchRecentRoutes();
    fetchFavoriteRoutes();
    loadCachedRoute();
    loadPushToken();
    requestCalendarPermission();
    
    // Fade in animation on mount
    Animated.timing(fadeAnim, {
      toValue: 1,
      duration: 500,
      useNativeDriver: true,
    }).start();
  }, []);

  // Reset favorite indicator when route changes
  useEffect(() => {
    setFavoriteAdded(false);
  }, [origin, destination, stops]);

  const loadPushToken = async () => {
    try {
      const token = await AsyncStorage.getItem('expoPushToken');
      if (token) {
        setPushToken(token);
        console.log('Push token loaded successfully');
      } else {
        // Token not available yet, retry after a delay
        console.log('Push token not yet available, will retry...');
        setTimeout(loadPushToken, 1000);
      }
    } catch (err) {
      console.log('Error loading push token:', err);
    }
  };

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

  // Calendar integration functions
  const requestCalendarPermission = async () => {
    try {
      const { status } = await Calendar.requestCalendarPermissionsAsync();
      if (status === 'granted') {
        setCalendarPermission(true);
        fetchUpcomingTrips();
      }
    } catch (error) {
      console.log('Calendar permission error:', error);
    }
  };

  const fetchUpcomingTrips = async () => {
    try {
      const calendars = await Calendar.getCalendarsAsync(Calendar.EntityTypes.EVENT);
      if (calendars.length === 0) return;

      const now = new Date();
      const futureDate = new Date();
      futureDate.setDate(futureDate.getDate() + 30); // Next 30 days

      const events = await Calendar.getEventsAsync(
        calendars.map(c => c.id),
        now,
        futureDate
      );

      // Parse events for travel-related keywords
      const tripKeywords = ['trip', 'travel', 'vacation', 'visit', 'camping', 'rv', 'road trip', 'drive to', 'flying to'];
      const trips: CalendarTrip[] = events
        .filter(event => {
          const titleLower = event.title.toLowerCase();
          return tripKeywords.some(keyword => titleLower.includes(keyword));
        })
        .map(event => {
          // Try to extract destination from title
          const destination = parseDestinationFromTitle(event.title);
          return {
            id: event.id,
            title: event.title,
            startDate: new Date(event.startDate),
            endDate: new Date(event.endDate),
            location: event.location,
            parsedDestination: destination,
          };
        })
        .slice(0, 3); // Show only first 3

      setCalendarTrips(trips);
    } catch (error) {
      console.log('Error fetching calendar events:', error);
    }
  };

  const parseDestinationFromTitle = (title: string): string | undefined => {
    // Simple parsing: look for "to [Place]" or "[Place] Trip"
    const toMatch = title.match(/to\s+([A-Z][a-zA-Z\s,]+)/);
    if (toMatch) return toMatch[1].trim();
    
    const inMatch = title.match(/in\s+([A-Z][a-zA-Z\s,]+)/);
    if (inMatch) return inMatch[1].trim();
    
    return undefined;
  };

  const useCalendarTrip = (trip: CalendarTrip) => {
    if (trip.parsedDestination) {
      setDestination(trip.parsedDestination);
    } else if (trip.location) {
      setDestination(trip.location);
    }
    // Destination is set, user can fill origin manually
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
        params: { query, limit: 5 },
        timeout: 10000,
      });
      
      const suggestions = Array.isArray(response.data) ? response.data : [];
      
      if (type === 'origin') {
        setOriginSuggestions(suggestions);
        setShowOriginSuggestions(suggestions.length > 0);
      } else {
        setDestSuggestions(suggestions);
        setShowDestSuggestions(suggestions.length > 0);
      }
    } catch (err: any) {
      console.log('Autocomplete error:', err.message || err);
      // Clear suggestions on error
      if (type === 'origin') {
        setOriginSuggestions([]);
        setShowOriginSuggestions(false);
      } else {
        setDestSuggestions([]);
        setShowDestSuggestions(false);
      }
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

  const goToRoadPassability = () => router.push('/road-passability');
  const goToConnectivity = () => router.push('/connectivity');

  // Cleanup debounce timers on unmount
  useEffect(() => {
    return () => {
      if (originDebounceRef.current) {
        clearTimeout(originDebounceRef.current);
      }
      if (destDebounceRef.current) {
        clearTimeout(destDebounceRef.current);
      }
    };
  }, []);

  // Voice-to-text function
  const startVoiceRecognition = () => {
    if (Platform.OS !== 'web') {
      alert('Voice input works in web browsers. On native devices, use the Expo Go app.');
      return;
    }

    // Check if we're in an iframe (which blocks speech recognition)
    const isInIframe = window !== window.parent;
    
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    
    if (!SpeechRecognition) {
      alert('🎤 Speech recognition not supported.\n\nPlease use Chrome, Edge, or Safari browser.');
      return;
    }

    if (isInIframe) {
      alert('🎤 Voice input is blocked in preview mode.\n\nTo use voice:\n1. Open the app in a new tab (click the external link icon)\n2. Or deploy the app and test there\n\nThe feature will work perfectly in the standalone app!');
      return;
    }

    // Already listening, stop it
    if (isListening) {
      setIsListening(false);
      return;
    }

    try {
      const recognition = new SpeechRecognition();
      recognition.continuous = false;
      recognition.interimResults = true;
      recognition.lang = 'en-US';

      recognition.onstart = () => {
        console.log('Voice recognition started');
        setIsListening(true);
        setChatMessage('');
      };

      recognition.onresult = (event: any) => {
        const transcript = Array.from(event.results)
          .map((result: any) => result[0].transcript)
          .join('');
        setChatMessage(transcript);
      };

      recognition.onerror = (event: any) => {
        console.error('Speech recognition error:', event.error);
        setIsListening(false);
        
        if (event.error === 'not-allowed') {
          alert('🎤 Microphone access denied.\n\nClick the lock icon in your address bar to allow microphone access.');
        } else if (event.error === 'no-speech') {
          alert('No speech detected. Please try again.');
        } else {
          alert(`Voice error: ${event.error}`);
        }
      };

      recognition.onend = () => {
        setIsListening(false);
      };

      recognition.start();
    } catch (err) {
      console.error('Failed to start recognition:', err);
      alert('Failed to start voice recognition. Please try a different browser.');
      setIsListening(false);
    }
  };

  const saveToRecentRoutes = async (origin: string, destination: string, stops: StopPoint[]) => {
    try {
      // Load existing recent routes from local storage
      const stored = await AsyncStorage.getItem('recentRoutes');
      let recents: SavedRoute[] = stored ? JSON.parse(stored) : [];
      
      // Create new route entry
      const newRoute: SavedRoute = {
        id: Date.now().toString(),
        origin: origin,
        destination: destination,
        stops: stops,
        is_favorite: false,
        created_at: new Date().toISOString()
      };
      
      // Remove duplicate if it exists (same origin and destination)
      recents = recents.filter(r => 
        !(r.origin === origin && r.destination === destination)
      );
      
      // Add to front of list
      recents.unshift(newRoute);
      
      // Keep only last 10
      recents = recents.slice(0, 10);
      
      // Save back to storage
      await AsyncStorage.setItem('recentRoutes', JSON.stringify(recents));
      
      // Update state
      setRecentRoutes(recents.slice(0, 3));
    } catch (err) {
      console.log('Error saving to recent routes:', err);
    }
  };

  const fetchRecentRoutes = async () => {
    try {
      // Try to fetch from backend first
      const response = await axios.get(`${API_BASE}/api/routes/history`);
      setRecentRoutes(response.data.slice(0, 3));
    } catch (err) {
      console.log('Error fetching from backend, using local storage:', err);
      // Fallback to local storage
      try {
        const stored = await AsyncStorage.getItem('recentRoutes');
        if (stored) {
          const recents = JSON.parse(stored);
          setRecentRoutes(recents.slice(0, 3));
        }
      } catch (localErr) {
        console.log('Error loading local recent routes:', localErr);
      }
    }
  };

  const fetchFavoriteRoutes = async () => {
    try {
      const response = await axios.get(`${API_BASE}/api/routes/favorites`);
      setFavoriteRoutes(response.data);
    } catch (err) {
      console.log('Error fetching favorites:', err);
    }
  };

  const handleAlertsToggle = async (enabled: boolean) => {
    if (enabled) {
      // Request permissions first
      const { status: existingStatus } = await Notifications.getPermissionsAsync();
      let finalStatus = existingStatus;
      
      if (existingStatus !== 'granted') {
        const { status } = await Notifications.requestPermissionsAsync();
        finalStatus = status;
      }
      
      if (finalStatus !== 'granted') {
        Alert.alert(
          'Permission Required',
          'Please enable notifications in your device settings to receive weather alerts.',
          [
            { text: 'Cancel', style: 'cancel' },
            { text: 'Open Settings', onPress: () => Linking.openSettings() }
          ]
        );
        return;
      }
      
      // Get push token
      try {
        const token = (await Notifications.getExpoPushTokenAsync({
          projectId: '7eddbe0f-7b2-4ae3-b25c-cf1c1e67f0e7'
        })).data;
        
        await AsyncStorage.setItem('expoPushToken', token);
        setPushToken(token);
        
        // Register with backend
        await axios.post(`${API_BASE}/api/notifications/register`, {
          push_token: token,
          enabled: true,
        });
        
        setAlertsEnabled(true);
        setTestNotificationMessage('✅ Push alerts enabled!');
        setTimeout(() => setTestNotificationMessage(''), 3000);
      } catch (err) {
        console.error('Error setting up notifications:', err);
        setTestNotificationMessage('❌ Error enabling alerts');
        setTimeout(() => setTestNotificationMessage(''), 3000);
      }
    } else {
      setAlertsEnabled(false);
      setTestNotificationMessage('Push alerts disabled');
      setTimeout(() => setTestNotificationMessage(''), 2000);
    }
  };

  const handleTestNotification = async () => {
    if (!pushToken) {
      setTestNotificationMessage('⚠️ No push token available');
      setTimeout(() => setTestNotificationMessage(''), 3000);
      return;
    }

    try {
      setTestNotificationLoading(true);
      setTestNotificationMessage('Sending test notification...');
      
      const response = await axios.post(`${API_BASE}/api/notifications/test`, {
        push_token: pushToken,
      });
      
      setTestNotificationMessage('✅ Test notification sent!');
      setTimeout(() => setTestNotificationMessage(''), 3000);
    } catch (err) {
      console.log('Error sending test notification:', err);
      setTestNotificationMessage('❌ Failed to send test notification');
      setTimeout(() => setTestNotificationMessage(''), 3000);
    } finally {
      setTestNotificationLoading(false);
    }
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
      };
      // Include vehicle height if in trucker mode
      if (truckerMode && vehicleHeight) {
        requestData.vehicle_height_ft = parseFloat(vehicleHeight);
      }
      if (useCustomTime) {
        requestData.departure_time = departureTime.toISOString();
      }

      const response = await axios.post(`${API_BASE}/api/route/weather`, requestData);
      const data = response.data;

      // Defensive: Ensure required fields exist
      if (!data || !data.origin || !data.destination || !data.waypoints || !Array.isArray(data.waypoints)) {
        setError('Weather route data is incomplete. Please try again.');
        return;
      }

      // Cache the route for offline
      await AsyncStorage.setItem('lastRoute', JSON.stringify(data));
      
      // Save to recent routes
      await saveToRecentRoutes(origin.trim(), destination.trim(), stops);

      router.push({
        pathname: '/route',
        params: { routeData: JSON.stringify(data) },
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
    // Fill in the route details only - user must press Check Route Weather to load
    setOrigin(route.origin);
    setDestination(route.destination);
    if (route.stops) {
      setStops(route.stops);
    }
    
    // Clear any previous errors
    setError('');
  };

  const addToFavorites = async () => {
    if (!origin.trim() || !destination.trim()) {
      Alert.alert('Missing Information', 'Enter origin and destination first to save as favorite');
      return;
    }

    try {
      await axios.post(`${API_BASE}/api/routes/favorites`, {
        origin: origin.trim(),
        destination: destination.trim(),
        stops: stops,
      });
      setFavoriteAdded(true);
      fetchFavoriteRoutes();
      Alert.alert('Saved!', 'Route added to favorites');
    } catch (err: any) {
      console.error('Error saving favorite:', err);
      Alert.alert('Error', err?.response?.data?.detail || 'Failed to save favorite. Please try again.');
    }
  };

  const removeFavorite = async (id: string) => {
    try {
      await axios.delete(`${API_BASE}/api/routes/favorites/${id}`);
      fetchFavoriteRoutes();
    } catch (err) {
      console.error('Error removing favorite:', err);
    }
  };

  const stopDebounceRef = React.useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleStopLocationChange = (text: string) => {
    setNewStopLocation(text);
    
    // Debounce autocomplete
    if (stopDebounceRef.current) {
      clearTimeout(stopDebounceRef.current);
    }
    stopDebounceRef.current = setTimeout(() => {
      fetchStopAutocomplete(text);
    }, 300);
  };

  const fetchStopAutocomplete = async (query: string) => {
    if (query.length < 2) {
      setStopSuggestions([]);
      setShowStopSuggestions(false);
      return;
    }

    try {
      const response = await axios.get(`${API_BASE}/api/geocode/autocomplete`, {
        params: { query, limit: 5 }
      });
      setStopSuggestions(response.data);
      setShowStopSuggestions(response.data.length > 0);
    } catch (err) {
      console.log('Stop autocomplete error:', err);
    }
  };

  const selectStopSuggestion = (suggestion: AutocompleteSuggestion) => {
    setNewStopLocation(suggestion.place_name);
    setShowStopSuggestions(false);
    setStopSuggestions([]);
  };

  const addStop = () => {
    if (newStopLocation.trim()) {
      setStops([...stops, { location: newStopLocation.trim(), type: newStopType }]);
      setNewStopLocation('');
      setStopSuggestions([]);
      setShowStopSuggestions(false);
      setShowAddStop(false);
    }
  };

  const removeStop = (index: number) => {
    setStops(stops.filter((_, i) => i !== index));
  };

  // Dev-only: handle 5 rapid taps on subtitle to toggle Pro entitlement
  const handleDevTap = () => {
    if (!__DEV__) return;
    const newCount = devTapCount + 1;
    setDevTapCount(newCount);
    if (newCount >= 5) {
      setDevTapCount(0);
      devToggleProEntitlement();
    }
    // Reset counter after 2 seconds of inactivity
    setTimeout(() => {
      setDevTapCount(0);
    }, 2000);
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

  return (
    <View style={styles.container}>
      <View style={styles.mapBackground}>
        <View style={styles.mapOverlay} />
      </View>

      <SafeAreaView style={styles.safeArea} edges={['top', 'left', 'right']}>
        <KeyboardAvoidingView
          behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
          style={styles.keyboardView}
        >
          <ScrollView
            contentContainerStyle={styles.scrollContent}
            keyboardShouldPersistTaps="handled"
            showsVerticalScrollIndicator={false}
          >
            {/* Upcoming Trips from Calendar */}
            {calendarTrips.length > 0 && (
              <Animated.View style={[styles.calendarSection, { opacity: fadeAnim }]}>
                <View style={styles.calendarHeader}>
                  <Ionicons name="calendar" size={20} color="#3b82f6" />
                  <Text style={styles.calendarTitle}>Upcoming Trips</Text>
                </View>
                {calendarTrips.map((trip) => (
                  <TouchableOpacity
                    key={trip.id}
                    style={styles.calendarCard}
                    onPress={() => useCalendarTrip(trip)}
                    activeOpacity={0.7}
                  >
                    <View style={styles.calendarCardLeft}>
                      <Text style={styles.calendarCardTitle}>{trip.title}</Text>
                      <Text style={styles.calendarCardDate}>
                        {format(trip.startDate, 'MMM d, yyyy')}
                      </Text>
                      {trip.parsedDestination && (
                        <Text style={styles.calendarCardLocation}>
                          📍 {trip.parsedDestination}
                        </Text>
                      )}
                    </View>
                    <View style={styles.calendarCardRight}>
                      <Ionicons name="arrow-forward-circle" size={28} color="#3b82f6" />
                      <Text style={styles.calendarCardAction}>Check Weather</Text>
                    </View>
                  </TouchableOpacity>
                ))}
              </Animated.View>
            )}

            {/* Main Card */}
            <Animated.View style={[styles.mainCard, { opacity: fadeAnim }]}>
              {/* Header */}
              <View style={styles.header}>
                <View style={styles.iconContainer}>
                  <MaterialCommunityIcons name="routes" size={22} color="#1a1a1a" />
                </View>
                <View style={styles.headerText}>
                  <Text style={styles.title}>Routecast</Text>
                  <TouchableOpacity onPress={handleDevTap} delayPressIn={0}>
                    <Text style={styles.subtitle}>Weather forecasts for your journey</Text>
                  </TouchableOpacity>
                </View>
                <TouchableOpacity 
                  style={styles.favoriteButton}
                  onPress={addToFavorites}
                >
                  <Ionicons 
                    name={favoriteAdded ? "heart" : "heart-outline"} 
                    size={24} 
                    color={favoriteAdded ? "#ef4444" : "#eab308"} 
                  />
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
                <View style={[styles.inputWrapper, originFocused && styles.inputWrapperFocused]}>
                  <View style={styles.originIcon}>
                    <Ionicons name="location" size={20} color="#22c55e" />
                  </View>
                  <TextInput
                    style={styles.input}
                    placeholder="Enter starting location"
                    placeholderTextColor="#6b7280"
                    value={origin}
                    onChangeText={handleOriginChange}
                    onFocus={() => {
                      setOriginFocused(true);
                      origin.length >= 2 && setShowOriginSuggestions(originSuggestions.length > 0);
                    }}
                    onBlur={() => {
                      setOriginFocused(false);
                      setTimeout(() => setShowOriginSuggestions(false), 200);
                    }}
                    returnKeyType="next"
                  />
                  {autocompleteLoading && origin.length >= 2 && (
                    <ActivityIndicator size="small" color="#eab308" style={{ marginRight: 8 }} />
                  )}
                  {origin.length > 0 && !autocompleteLoading && (
                    <TouchableOpacity 
                      onPress={() => {
                        setOrigin('');
                        setOriginSuggestions([]);
                        setShowOriginSuggestions(false);
                      }}
                      style={styles.clearButton}
                    >
                      <Ionicons name="close-circle" size={20} color="#6b7280" />
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
                <View style={[styles.inputWrapper, destFocused && styles.inputWrapperFocused]}>
                  <View style={styles.destinationIcon}>
                    <Ionicons name="navigate" size={20} color="#ef4444" />
                  </View>
                  <TextInput
                    style={styles.input}
                    placeholder="Enter destination"
                    placeholderTextColor="#6b7280"
                    value={destination}
                    onChangeText={handleDestinationChange}
                    onFocus={() => {
                      setDestFocused(true);
                      destination.length >= 2 && setShowDestSuggestions(destSuggestions.length > 0);
                    }}
                    onBlur={() => {
                      setDestFocused(false);
                      setTimeout(() => setShowDestSuggestions(false), 200);
                    }}
                    returnKeyType="done"
                    onSubmitEditing={handleGetWeather}
                  />
                  {autocompleteLoading && destination.length >= 2 && (
                    <ActivityIndicator size="small" color="#eab308" style={{ marginRight: 8 }} />
                  )}
                  {destination.length > 0 && !autocompleteLoading && (
                    <TouchableOpacity 
                      onPress={() => {
                        setDestination('');
                        setDestSuggestions([]);
                        setShowDestSuggestions(false);
                      }}
                      style={styles.clearButton}
                    >
                      <Ionicons name="close-circle" size={20} color="#6b7280" />
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

              {/* Trucker/RV Mode Toggle */}
              <View style={styles.truckerToggle}>
                <View style={styles.alertsLeft}>
                  <Ionicons name="bus-outline" size={22} color="#f59e0b" />
                  <View>
                    <Text style={styles.alertsText}>Trucker/RV Mode</Text>
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

              {/* Vehicle Height Section (shown when trucker mode enabled) */}
              {truckerMode && (
                <View style={styles.heightSection}>
                  <Text style={styles.heightSectionTitle}>⚠️ Bridge Clearance Alert</Text>
                  <Text style={styles.heightSectionSubtitle}>Set your vehicle height to get alerts for bridges you can't drive under</Text>
                  
                  {/* Height Input */}
                  <View style={styles.heightInputContainer}>
                    <TextInput
                      style={styles.heightInputField}
                      placeholder="13.5"
                      placeholderTextColor="#9ca3af"
                      value={vehicleHeight}
                      onChangeText={setVehicleHeight}
                      keyboardType="decimal-pad"
                      editable={truckerMode}
                    />
                    <Text style={styles.heightUnit}>ft</Text>
                  </View>
                  
                  {/* Height Status */}
                  <View style={styles.heightStatus}>
                    <Ionicons name="information-circle" size={18} color="#eab308" />
                    <Text style={styles.heightStatusText}>
                      Current: {vehicleHeight} ft • You'll get alerts for bridges shorter than this
                    </Text>
                  </View>
                  
                  {/* Done Button - Just dismisses keyboard, keeps mode active */}
                  <TouchableOpacity 
                    style={styles.heightDoneButton}
                    onPress={() => Keyboard.dismiss()}
                  >
                    <Text style={styles.heightDoneButtonText}>Done</Text>
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
            </Animated.View>

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

          {/* Premium modal handled in RoadPassability screen */}
        </KeyboardAvoidingView>
      </SafeAreaView>

      {/* Date Time Picker Modal */}
      {showDatePicker && (
        <Modal transparent animationType="slide">
          <SafeAreaView style={styles.modalOverlay}>
            <View style={styles.modalContent}>
              <View style={styles.modalHeader}>
                <Text style={styles.modalTitle}>Select Departure Time</Text>
                <TouchableOpacity onPress={() => setShowDatePicker(false)}>
                  <Ionicons name="close" size={24} color="#fff" />
                </TouchableOpacity>
              </View>
              
              <ScrollView contentContainerStyle={{ gap: 20, paddingVertical: 16 }}>
                {/* Date Section */}
                <View>
                  <Text style={styles.datePickerLabel}>Date</Text>
                  <View style={styles.pickerRow}>
                    <TouchableOpacity 
                      style={styles.pickerButton}
                      onPress={() => {
                        const newDate = new Date(departureTime);
                        newDate.setDate(newDate.getDate() - 1);
                        setDepartureTime(newDate);
                      }}
                    >
                      <Text style={styles.pickerButtonText}>−</Text>
                    </TouchableOpacity>
                    <Text style={styles.pickerValue}>{format(departureTime, 'MMM d, yyyy')}</Text>
                    <TouchableOpacity 
                      style={styles.pickerButton}
                      onPress={() => {
                        const newDate = new Date(departureTime);
                        newDate.setDate(newDate.getDate() + 1);
                        setDepartureTime(newDate);
                      }}
                    >
                      <Text style={styles.pickerButtonText}>+</Text>
                    </TouchableOpacity>
                  </View>
                </View>

                {/* Hour Section */}
                <View>
                  <Text style={styles.datePickerLabel}>Hour</Text>
                  <View style={styles.pickerRow}>
                    <TouchableOpacity 
                      style={styles.pickerButton}
                      onPress={() => {
                        const newDate = new Date(departureTime);
                        newDate.setHours(newDate.getHours() - 1);
                        setDepartureTime(newDate);
                      }}
                    >
                      <Text style={styles.pickerButtonText}>−</Text>
                    </TouchableOpacity>
                    <Text style={styles.pickerValue}>{String(departureTime.getHours()).padStart(2, '0')}</Text>
                    <TouchableOpacity 
                      style={styles.pickerButton}
                      onPress={() => {
                        const newDate = new Date(departureTime);
                        newDate.setHours(newDate.getHours() + 1);
                        setDepartureTime(newDate);
                      }}
                    >
                      <Text style={styles.pickerButtonText}>+</Text>
                    </TouchableOpacity>
                  </View>
                </View>

                {/* Minutes Section */}
                <View>
                  <Text style={styles.datePickerLabel}>Minutes</Text>
                  <View style={styles.pickerRow}>
                    <TouchableOpacity 
                      style={styles.pickerButton}
                      onPress={() => {
                        const newDate = new Date(departureTime);
                        newDate.setMinutes(newDate.getMinutes() - 15);
                        setDepartureTime(newDate);
                      }}
                    >
                      <Text style={styles.pickerButtonText}>−15</Text>
                    </TouchableOpacity>
                    <Text style={styles.pickerValue}>{String(departureTime.getMinutes()).padStart(2, '0')}</Text>
                    <TouchableOpacity 
                      style={styles.pickerButton}
                      onPress={() => {
                        const newDate = new Date(departureTime);
                        newDate.setMinutes(newDate.getMinutes() + 15);
                        setDepartureTime(newDate);
                      }}
                    >
                      <Text style={styles.pickerButtonText}>+15</Text>
                    </TouchableOpacity>
                  </View>
                </View>
                
                {/* Preview */}
                <View style={{ padding: 12, backgroundColor: '#3f3f46', borderRadius: 8 }}>
                  <Text style={styles.selectedDateTime}>
                    Selected: {format(departureTime, 'MMM d, yyyy h:mm a')}
                  </Text>
                </View>
              </ScrollView>
              
              <TouchableOpacity 
                style={styles.modalButton}
                onPress={() => {
                  try {
                    setShowDatePicker(false);
                  } catch (e) {
                    console.error('Error closing date picker:', e);
                  }
                }}
              >
                <Text style={styles.modalButtonText}>Confirm</Text>
              </TouchableOpacity>
            </View>
          </SafeAreaView>
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
              
              <TextInput
                style={styles.modalInput}
                placeholder="City, address, or landmark"
                placeholderTextColor="#6b7280"
                value={newStopLocation}
                onChangeText={handleStopLocationChange}
              />
              
              {/* Stop Autocomplete Suggestions */}
              {showStopSuggestions && stopSuggestions.length > 0 && (
                <View style={styles.suggestions}>
                  {stopSuggestions.map((suggestion, idx) => (
                    <TouchableOpacity
                      key={idx}
                      style={styles.suggestionItem}
                      onPress={() => selectStopSuggestion(suggestion)}
                    >
                      <Ionicons name="location-outline" size={18} color="#6b7280" />
                      <Text style={styles.suggestionText}>{suggestion.place_name}</Text>
                    </TouchableOpacity>
                  ))}
                </View>
              )}
              
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

      {/* Boondockers Pro Modal */}
      {showCampPrep && (
        <Modal
          visible={showCampPrep}
          animationType="slide"
          onRequestClose={() => setShowCampPrep(false)}
        >
          <CampPrepChat onClose={() => setShowCampPrep(false)} />
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
    paddingTop: Platform.OS === 'android' ? 48 : 12,
    paddingBottom: 40,
  },
  mainCard: {
    backgroundColor: '#27272a',
    borderRadius: 20,
    padding: 20,
    marginBottom: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.3,
    shadowRadius: 12,
    elevation: 8,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 16,
  },
  iconContainer: {
    width: 36,
    height: 36,
    borderRadius: 10,
    backgroundColor: '#eab308',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 10,
  },
  headerText: {
    flex: 1,
  },
  title: {
    fontSize: 24,
    fontWeight: '800',
    color: '#ffffff',
    marginBottom: 2,
    letterSpacing: 0.5,
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
    borderRadius: 12,
    borderWidth: 2,
    borderColor: '#52525b',
    paddingHorizontal: 14,
    shadowColor: '#3b82f6',
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0,
    shadowRadius: 8,
    elevation: 0,
  },
  inputWrapperFocused: {
    borderColor: '#3b82f6',
    shadowOpacity: 0.3,
    elevation: 4,
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
    padding: 4,
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
  testButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#eab30820',
    borderRadius: 10,
    paddingHorizontal: 16,
    paddingVertical: 12,
    marginBottom: 12,
    gap: 8,
    borderWidth: 1,
    borderColor: '#eab308',
  },
  testButtonText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#eab308',
  },
  notificationStatusContainer: {
    backgroundColor: '#27272a',
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 10,
    marginBottom: 12,
    borderLeftWidth: 3,
    borderLeftColor: '#eab308',
  },
  notificationStatusText: {
    color: '#e4e4e7',
    fontSize: 13,
    fontWeight: '500',
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
    borderRadius: 14,
    paddingVertical: 16,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 10,
    shadowColor: '#eab308',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.4,
    shadowRadius: 8,
    elevation: 6,
    minHeight: 52,
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
    flex: 1,
    maxHeight: '90%',
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
  customDatePicker: {
    marginVertical: 16,
    gap: 12,
  },
  datePickerLabel: {
    color: '#a1a1aa',
    fontSize: 12,
    fontWeight: '600',
    letterSpacing: 0.5,
  },
  pickerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 12,
    marginTop: 8,
  },
  pickerButton: {
    backgroundColor: '#3f3f46',
    borderRadius: 8,
    paddingHorizontal: 16,
    paddingVertical: 10,
    minWidth: 50,
    alignItems: 'center',
  },
  pickerButtonText: {
    color: '#eab308',
    fontSize: 18,
    fontWeight: 'bold',
  },
  pickerValue: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '600',
    minWidth: 100,
    textAlign: 'center',
  },
  dateInput: {
    backgroundColor: '#3f3f46',
    borderRadius: 10,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 15,
    color: '#fff',
    borderWidth: 1,
    borderColor: '#52525b',
  },
  selectedDateTime: {
    color: '#eab308',
    fontSize: 14,
    fontWeight: '600',
    textAlign: 'center',
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
  heightInput: {
    backgroundColor: '#3f3f46',
    borderRadius: 10,
    paddingHorizontal: 14,
    paddingVertical: 12,
    marginBottom: 12,
    borderLeftWidth: 3,
    borderLeftColor: '#f59e0b',
  },
  heightSection: {
    backgroundColor: '#422006',
    borderRadius: 12,
    padding: 12,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: '#f59e0b',
  },
  heightSectionTitle: {
    color: '#fbbf24',
    fontSize: 14,
    fontWeight: '700',
    marginBottom: 3,
  },
  heightSectionSubtitle: {
    color: '#fde68a',
    fontSize: 11,
    marginBottom: 10,
    lineHeight: 16,
  },
  heightLabel: {
    color: '#e4e4e7',
    fontSize: 13,
    fontWeight: '600',
    marginBottom: 8,
  },
  heightInputContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 10,
  },
  heightInputField: {
    flex: 1,
    backgroundColor: '#27272a',
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 10,
    color: '#ffffff',
    fontSize: 16,
    borderWidth: 1,
    borderColor: '#f59e0b',
  },
  heightUnit: {
    color: '#fbbf24',
    fontSize: 14,
    fontWeight: '700',
  },
  presetsContainer: {
    marginBottom: 10,
  },
  presetsLabel: {
    color: '#fde68a',
    fontSize: 11,
    fontWeight: '600',
    marginBottom: 6,
  },
  presetsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  presetBtn: {
    flex: 1,
    minWidth: '48%',
    backgroundColor: '#1f2937',
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#f59e0b',
    paddingHorizontal: 8,
    paddingVertical: 8,
    alignItems: 'center',
    justifyContent: 'center',
  },
  presetBtnText: {
    color: '#fde68a',
    fontSize: 11,
    fontWeight: '600',
  },
  presetBtnHeight: {
    color: '#fbbf24',
    fontSize: 13,
    fontWeight: '700',
    marginTop: 2,
  },
  heightStatus: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1f2937',
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 8,
    gap: 8,
    marginTop: 4,
  },
  heightStatusText: {
    color: '#fde68a',
    fontSize: 12,
    flex: 1,
  },
  heightDoneButton: {
    backgroundColor: '#f59e0b',
    borderRadius: 8,
    paddingVertical: 10,
    alignItems: 'center',
    marginTop: 12,
  },
  heightDoneButtonText: {
    color: '#1a1a1a',
    fontSize: 14,
    fontWeight: '700',
  },
  heightHint: {
    color: '#71717a',
    fontSize: 11,
    marginTop: 6,
    fontStyle: 'italic',
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
  calendarSection: {
    marginBottom: 16,
  },
  calendarHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 12,
  },
  calendarTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: '#e5e7eb',
  },
  calendarCard: {
    backgroundColor: '#1e293b',
    borderRadius: 16,
    padding: 16,
    marginBottom: 10,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    borderLeftWidth: 4,
    borderLeftColor: '#3b82f6',
    shadowColor: '#3b82f6',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.2,
    shadowRadius: 8,
    elevation: 4,
  },
  calendarCardLeft: {
    flex: 1,
  },
  calendarCardTitle: {
    fontSize: 15,
    fontWeight: '700',
    color: '#e5e7eb',
    marginBottom: 4,
  },
  calendarCardDate: {
    fontSize: 12,
    color: '#94a3b8',
    marginBottom: 4,
  },
  calendarCardLocation: {
    fontSize: 12,
    color: '#60a5fa',
  },
  calendarCardRight: {
    alignItems: 'center',
    gap: 4,
  },
  calendarCardAction: {
    fontSize: 10,
    color: '#60a5fa',
    fontWeight: '600',
  },
});
