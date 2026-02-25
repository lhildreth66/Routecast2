/**
 * useLocationSearch
 *
 * Shared hook for manual location search across all finder screens.
 *
 * Rules:
 *  - NEVER auto-calls GPS on mount.
 *  - On mount: restores from sessionStorage if a key is supplied (no GPS).
 *  - `triggerGps()` is the ONLY path that requests Location permission.
 *  - `selectSuggestion()` sets lat/lon from Mapbox autocomplete.
 *  - `clearManualLocation()` clears label and sessionStorage.
 */

import { useEffect, useRef, useState } from 'react';
import { Alert, Platform } from 'react-native';
import * as Location from 'expo-location';
import axios from 'axios';
import { API_BASE } from './apiConfig';

export interface LocationSuggestion {
  place_name: string;
  short_name: string;
  coordinates: [number, number]; // [lon, lat]
}

export interface UseLocationSearchResult {
  lat: string;
  lon: string;
  locationLabel: string | null;       // "Key West, FL" or null (= GPS)
  locationLoading: boolean;
  locationQuery: string;
  suggestions: LocationSuggestion[];
  showSuggestions: boolean;
  setLocationQuery: (q: string) => void;
  handleLocationQueryChange: (text: string) => void;
  selectSuggestion: (s: LocationSuggestion) => void;
  clearManualLocation: () => void;
  triggerGps: () => Promise<void>;
  setShowSuggestions: (v: boolean) => void;
}

export function useLocationSearch(sessionKey: string): UseLocationSearchResult {
  const [lat, setLat] = useState('');
  const [lon, setLon] = useState('');
  const [locationLabel, setLocationLabel] = useState<string | null>(null);
  const [locationLoading, setLocationLoading] = useState(false);

  const [locationQuery, setLocationQuery] = useState('');
  const [suggestions, setSuggestions] = useState<LocationSuggestion[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // --- Restore from sessionStorage on mount (NO GPS) ---
  useEffect(() => {
    if (Platform.OS === 'web' && typeof window !== 'undefined') {
      try {
        const saved = window.sessionStorage.getItem(sessionKey);
        if (saved) {
          const parsed = JSON.parse(saved);
          if (parsed?.lat && parsed?.lon) {
            setLat(parsed.lat);
            setLon(parsed.lon);
            setLocationLabel(parsed.label ?? null);
            return; // done – no GPS
          }
        }
      } catch { /* ignore */ }
    }
    // Leave lat/lon empty – user must search or click "Use My Location"
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const persist = (la: string, lo: string, label: string | null) => {
    if (Platform.OS === 'web' && typeof window !== 'undefined') {
      try {
        window.sessionStorage.setItem(sessionKey, JSON.stringify({ lat: la, lon: lo, label }));
      } catch { /* ignore */ }
    }
  };

  const clearPersisted = () => {
    if (Platform.OS === 'web' && typeof window !== 'undefined') {
      try { window.sessionStorage.removeItem(sessionKey); } catch { /* ignore */ }
    }
  };

  // --- Autocomplete ---
  const fetchSuggestions = async (q: string) => {
    if (q.length < 2) { setSuggestions([]); return; }
    try {
      const res = await axios.get(`${API_BASE}/api/geocode/autocomplete`, {
        params: { query: q, limit: 6 },
      });
      setSuggestions(Array.isArray(res.data) ? res.data : []);
      setShowSuggestions(true);
    } catch {
      setSuggestions([]);
    }
  };

  const handleLocationQueryChange = (text: string) => {
    setLocationQuery(text);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (text.length < 2) { setSuggestions([]); setShowSuggestions(false); return; }
    debounceRef.current = setTimeout(() => fetchSuggestions(text), 300);
  };

  const selectSuggestion = (s: LocationSuggestion) => {
    const [lo, la] = s.coordinates;
    const label = s.short_name || s.place_name;
    const laStr = la.toFixed(6);
    const loStr = lo.toFixed(6);
    setLat(laStr);
    setLon(loStr);
    setLocationLabel(label);
    setLocationQuery('');
    setSuggestions([]);
    setShowSuggestions(false);
    persist(laStr, loStr, label);
  };

  const clearManualLocation = () => {
    setLocationLabel(null);
    setLocationQuery('');
    setSuggestions([]);
    setShowSuggestions(false);
    clearPersisted();
    setLat('');
    setLon('');
  };

  // --- GPS: only called explicitly by the user ---
  const triggerGps = async () => {
    clearManualLocation(); // wipe any manual label first
    setLocationLoading(true);
    try {
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== 'granted') {
        Alert.alert(
          'Location Permission Required',
          'Please enable location permissions in your device settings.',
          [{ text: 'OK' }],
        );
        return;
      }
      const loc = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced });
      const laStr = loc.coords.latitude.toFixed(4);
      const loStr = loc.coords.longitude.toFixed(4);
      setLat(laStr);
      setLon(loStr);
      setLocationLabel(null); // GPS – no label
      persist(laStr, loStr, null);
    } catch (err: any) {
      Alert.alert('Location Error', err.message || 'Unable to get your location.', [{ text: 'OK' }]);
    } finally {
      setLocationLoading(false);
    }
  };

  return {
    lat,
    lon,
    locationLabel,
    locationLoading,
    locationQuery,
    suggestions,
    showSuggestions,
    setLocationQuery,
    handleLocationQueryChange,
    selectSuggestion,
    clearManualLocation,
    triggerGps,
    setShowSuggestions,
  };
}
