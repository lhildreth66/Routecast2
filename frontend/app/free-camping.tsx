import React, { useState, useEffect, useRef } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, TextInput, ActivityIndicator, ScrollView, Alert, Linking, RefreshControl, Platform } from 'react-native';
import axios from 'axios';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import * as Location from 'expo-location';
import { API_BASE, buildUrl } from '../lib/apiConfig';
import InfoBanner from '../lib/components/InfoBanner';

interface CampingSpot {
  name: string;
  type: string; // 'BLM', 'National Forest', 'Bureau of Reclamation', etc.
  distance_miles: number;
  latitude: number;
  longitude: number;
  description: string;
  amenities: string[];
  stay_limit: string;
  cell_coverage: string; // 'none', 'poor', 'fair', 'good'
  access_difficulty: string; // 'easy', 'moderate', 'difficult', '4wd-required'
  elevation_ft: number;
  rating: number; // 0-5
  free: boolean;
  source_id?: string;
  phone?: string;
  website?: string;
  contact?: string;
}

const dedupeSpots = (spots: CampingSpot[]): CampingSpot[] => {
  const seen = new Map<string, CampingSpot>();

  const makeKey = (spot: CampingSpot): string => {
    if (spot.source_id) return String(spot.source_id);
    const lat = spot.latitude?.toFixed(4);
    const lon = spot.longitude?.toFixed(4);
    return `${spot.name?.toLowerCase() || 'unknown'}:${lat}:${lon}`;
  };

  for (const spot of spots) {
    const key = makeKey(spot);
    if (!seen.has(key)) {
      seen.set(key, spot);
    }
  }

  return Array.from(seen.values());
};

export default function FreeCampingScreen() {
  const router = useRouter();
  const [latitude, setLatitude] = useState('34.05');
  const [longitude, setLongitude] = useState('-111.03');
  const [searchRadius, setSearchRadius] = useState('25'); // miles
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [locationLoading, setLocationLoading] = useState(true);
  const [spots, setSpots] = useState<CampingSpot[]>([]);
  const [error, setError] = useState<string>('');
  const [expandedSpots, setExpandedSpots] = useState(new Set<number>());

  // Manual location search state
  const [locationLabel, setLocationLabel] = useState<string | null>(null); // "Key West, FL"
  const [locationQuery, setLocationQuery] = useState('');
  const [suggestions, setSuggestions] = useState<Array<{ place_name: string; short_name: string; coordinates: [number, number] }>>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [suggestionsLoading, setSuggestionsLoading] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const SESSION_KEY = 'freeCampingLocation';

  // Restore saved location from sessionStorage on mount
  useEffect(() => {
    if (Platform.OS === 'web' && typeof window !== 'undefined') {
      try {
        const saved = window.sessionStorage.getItem(SESSION_KEY);
        if (saved) {
          const { lat, lon, label } = JSON.parse(saved);
          setLatitude(lat);
          setLongitude(lon);
          setLocationLabel(label);
        }
      } catch { /* ignore */ }
    }
    setLocationLoading(false);
  }, []);

  const fetchSuggestions = async (q: string) => {
    if (q.length < 2) { setSuggestions([]); return; }
    setSuggestionsLoading(true);
    try {
      const res = await axios.get(`${API_BASE}/geocode/autocomplete`, { params: { query: q, limit: 6 } });
      setSuggestions(Array.isArray(res.data) ? res.data : []);
      setShowSuggestions(true);
    } catch {
      setSuggestions([]);
    } finally {
      setSuggestionsLoading(false);
    }
  };

  const handleLocationQueryChange = (text: string) => {
    setLocationQuery(text);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (text.length < 2) { setSuggestions([]); setShowSuggestions(false); return; }
    debounceRef.current = setTimeout(() => fetchSuggestions(text), 300);
  };

  const selectSuggestion = (s: { place_name: string; short_name: string; coordinates: [number, number] }) => {
    const [lon, lat] = s.coordinates;
    const label = s.short_name || s.place_name;
    setLatitude(lat.toFixed(6));
    setLongitude(lon.toFixed(6));
    setLocationLabel(label);
    setLocationQuery('');
    setSuggestions([]);
    setShowSuggestions(false);
    if (Platform.OS === 'web' && typeof window !== 'undefined') {
      try { window.sessionStorage.setItem(SESSION_KEY, JSON.stringify({ lat: lat.toFixed(6), lon: lon.toFixed(6), label })); } catch { /* ignore */ }
    }
  };

  const clearManualLocation = () => {
    setLocationLabel(null);
    setLocationQuery('');
    setSuggestions([]);
    setShowSuggestions(false);
    if (Platform.OS === 'web' && typeof window !== 'undefined') {
      try { window.sessionStorage.removeItem(SESSION_KEY); } catch { /* ignore */ }
    }
  };

  const useCurrentLocation = async () => {
    clearManualLocation();
    setLocationLoading(true);
    try {
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== 'granted') {
        Alert.alert(
          'Location Permission Required', 
          'Please enable location permissions in your device settings to use this feature.',
          [{ text: 'OK' }]
        );
        setLocationLoading(false);
        return;
      }

      const location = await Location.getCurrentPositionAsync({
        accuracy: Location.Accuracy.Balanced,
        timeInterval: 10000,
        distanceInterval: 0,
      });
      setLatitude(location.coords.latitude.toFixed(4));
      setLongitude(location.coords.longitude.toFixed(4));
      setLocationLoading(false);
    } catch (err: any) {
      setLocationLoading(false);
      Alert.alert(
        'Location Error', 
        err.message || 'Unable to get your location. Make sure GPS is enabled and you have a clear view of the sky.',
        [{ text: 'OK' }]
      );
    }
  };

  const searchCamping = async () => {
    setLoading(true);
    setSpots([]);
    setError('');
    try {
      const resp = await axios.post(buildUrl('free-camping/search'), {
        latitude: parseFloat(latitude),
        longitude: parseFloat(longitude),
        radius_miles: parseInt(searchRadius, 10),
      });
      setSpots(dedupeSpots(resp.data.spots || []));
      if (resp.data.spots && resp.data.spots.length === 0) {
        setError('No free camping spots found in this area. Try increasing the search radius or searching a different location.');
      }
    } catch (err: any) {
      console.error('Free camping search error:', err);
      setError(err?.response?.data?.detail || err?.message || 'Failed to find camping spots. Tap to retry.');
    } finally {
      setLoading(false);
    }
  };

  const onRefresh = async () => {
    setRefreshing(true);
    await searchCamping();
    setRefreshing(false);
  };

  const toggleSpotExpand = (index: number) => {
    const newExpanded = new Set(expandedSpots);
    if (newExpanded.has(index)) {
      newExpanded.delete(index);
    } else {
      newExpanded.add(index);
    }
    setExpandedSpots(newExpanded);
  };

  const openInMaps = (spot: CampingSpot) => {
    const url = `https://www.google.com/maps/dir/?api=1&destination=${spot.latitude},${spot.longitude}`;
    Linking.openURL(url);
  };

  const getCellCoverageColor = (coverage: string) => {
    switch (coverage) {
      case 'good': return '#22c55e';
      case 'fair': return '#eab308';
      case 'poor': return '#f97316';
      case 'none': return '#ef4444';
      default: return '#9ca3af';
    }
  };

  const getAccessIcon = (difficulty: string) => {
    switch (difficulty) {
      case 'easy': return 'car';
      case 'moderate': return 'trail-sign';
      case 'difficult': return 'warning';
      case '4wd-required': return 'navigate-circle';
      default: return 'help-circle';
    }
  };

  return (
    <SafeAreaView style={styles.container}>
      <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
        <Ionicons name="arrow-back" size={24} color="#fff" />
        <Text style={styles.backText}>Back</Text>
      </TouchableOpacity>

      <ScrollView style={styles.content} refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#06b6d4" colors={['#06b6d4']} />
      }>
        <View style={styles.card}>
          <Text style={styles.title}>🏕️ Free Camping Finder</Text>
          <Text style={styles.subtitle}>Discover BLM land, National Forest dispersed camping, and other free spots</Text>

          {/* Location Search */}
          <View style={styles.locationBox}>
            {/* Manual search input */}
            <View style={styles.locationSearchRow}>
              <Ionicons name="search" size={16} color="#9ca3af" style={{ marginRight: 6 }} />
              <TextInput
                style={styles.locationSearchInput}
                placeholder="Search city, place… (e.g. Key West, FL)"
                placeholderTextColor="#6b7280"
                value={locationQuery}
                onChangeText={handleLocationQueryChange}
                onFocus={() => { if (suggestions.length > 0) setShowSuggestions(true); }}
                returnKeyType="search"
                autoCorrect={false}
              />
              {suggestionsLoading && <ActivityIndicator size="small" color="#06b6d4" style={{ marginLeft: 4 }} />}
            </View>

            {/* Autocomplete dropdown */}
            {showSuggestions && suggestions.length > 0 && (
              <View style={styles.suggestionsBox}>
                {suggestions.map((s, i) => (
                  <TouchableOpacity
                    key={i}
                    style={[styles.suggestionRow, i > 0 && styles.suggestionDivider]}
                    onPress={() => selectSuggestion(s)}
                    activeOpacity={0.75}
                  >
                    <Ionicons name="location-outline" size={14} color="#06b6d4" style={{ marginRight: 6 }} />
                    <Text style={styles.suggestionText} numberOfLines={2}>{s.place_name}</Text>
                  </TouchableOpacity>
                ))}
              </View>
            )}

            {/* Active location display */}
            <View style={styles.locationActiveRow}>
              {locationLabel ? (
                <View style={styles.locationChip}>
                  <Ionicons name="location" size={14} color="#06b6d4" />
                  <Text style={styles.locationChipText} numberOfLines={1}>{locationLabel}</Text>
                  <TouchableOpacity onPress={clearManualLocation} hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}>
                    <Ionicons name="close-circle" size={16} color="#6b7280" />
                  </TouchableOpacity>
                </View>
              ) : (
                <View style={styles.locationChip}>
                  <Ionicons name="navigate" size={14} color="#06b6d4" />
                  <Text style={styles.locationChipText} numberOfLines={1}>
                    {locationLoading ? 'Detecting GPS…' : `GPS · ${latitude}, ${longitude}`}
                  </Text>
                </View>
              )}
              <TouchableOpacity
                onPress={useCurrentLocation}
                style={styles.useGpsBtn}
                disabled={locationLoading}
              >
                {locationLoading ? (
                  <ActivityIndicator size="small" color="#06b6d4" />
                ) : (
                  <>
                    <Ionicons name="refresh" size={14} color="#06b6d4" />
                    <Text style={styles.useGpsBtnText}>Use my location</Text>
                  </>
                )}
              </TouchableOpacity>
            </View>
          </View>

          <View style={styles.inputRow}>
            <Text style={styles.label}>Search Radius (miles)</Text>
            <TextInput
              value={searchRadius}
              onChangeText={setSearchRadius}
              keyboardType="numeric"
              style={styles.input}
              placeholder="e.g., 25"
              placeholderTextColor="#9ca3af"
            />
          </View>

          <TouchableOpacity
            onPress={searchCamping}
            style={[styles.calculateButton, loading && styles.buttonDisabled]}
            disabled={loading}
          >
            {loading ? (
              <ActivityIndicator size="small" color="#fff" />
            ) : (
              <>
                <Ionicons name="search" size={20} color="#fff" />
                <Text style={styles.calculateButtonText}>Find Free Camping</Text>
              </>
            )}
          </TouchableOpacity>

          <InfoBanner
            message={'ℹ️ To keep subscription costs low, we use free mapping data. Some locations may show as "Store" or generic names. When you tap "Directions" and open in Google Maps, the full business name will appear at your destination.'}
            style={{ marginTop: 12, marginBottom: 8 }}
          />

          {error ? (
            <TouchableOpacity style={styles.errorBox} onPress={searchCamping} activeOpacity={0.7}>
              <Ionicons name="alert-circle" size={20} color="#ef4444" />
              <Text style={styles.errorText}>{error}</Text>
              <Text style={styles.retryText}>Tap to retry</Text>
            </TouchableOpacity>
          ) : null}
        </View>
        {/* Loading Skeletons */}
        {loading && !error && (
          <View style={styles.resultsContainer}>
            <View style={styles.skeletonTitle} />
            {[1, 2, 3].map((i) => (
              <View key={i} style={styles.skeletonCard}>
                <View style={styles.skeletonHeader}>
                  <View style={styles.skeletonTextLarge} />
                  <View style={styles.skeletonCircle} />
                </View>
                <View style={styles.skeletonTextSmall} />
                <View style={styles.skeletonTextSmall} />
              </View>
            ))}
          </View>
        )}
        {/* Results */}
        {spots.length > 0 && (
          <View style={styles.resultsContainer}>
            <Text style={styles.resultsTitle}>
              Found {spots.length} Free Camping Spot{spots.length !== 1 ? 's' : ''}
              {locationLabel ? ` near ${locationLabel}` : ''}
            </Text>
            
            {spots.map((spot, index) => {
              const key = spot.source_id || `${spot.name}-${spot.latitude}-${spot.longitude}`;
              const isExpanded = expandedSpots.has(index);
              
              return (
                <TouchableOpacity
                  key={key}
                  style={[styles.spotCard, isExpanded && styles.spotCardExpanded]}
                  onPress={() => toggleSpotExpand(index)}
                  activeOpacity={0.8}
                >
                  <View style={styles.spotHeader}>
                    <View style={styles.spotHeaderLeft}>
                      <Text style={styles.spotName}>{spot.name}</Text>
                      <View style={styles.spotTypeRow}>
                        <View style={styles.spotTypeBadge}>
                          <Text style={styles.spotTypeBadgeText}>{spot.type}</Text>
                        </View>
                        {spot.free && (
                          <View style={styles.freeBadge}>
                            <Text style={styles.freeBadgeText}>FREE</Text>
                          </View>
                        )}
                      </View>
                    </View>
                    <Ionicons 
                      name={isExpanded ? "chevron-up" : "chevron-down"} 
                      size={24} 
                      color="#9ca3af" 
                    />
                  </View>

                  <View style={styles.spotQuickInfo}>
                    <View style={styles.quickInfoItem}>
                      <Ionicons name="navigate" size={16} color="#06b6d4" />
                      <Text style={styles.quickInfoText}>{spot.distance_miles.toFixed(1)} mi</Text>
                    </View>
                    <View style={styles.quickInfoItem}>
                      <Ionicons 
                        name={getAccessIcon(spot.access_difficulty)} 
                        size={16} 
                        color="#9ca3af" 
                      />
                      <Text style={styles.quickInfoText}>{spot.access_difficulty}</Text>
                    </View>
                    <View style={styles.quickInfoItem}>
                      <Ionicons 
                        name="cellular" 
                        size={16} 
                        color={getCellCoverageColor(spot.cell_coverage)} 
                      />
                      <Text style={[styles.quickInfoText, { color: getCellCoverageColor(spot.cell_coverage) }]}>
                        {spot.cell_coverage}
                      </Text>
                    </View>
                    <View style={styles.quickInfoItem}>
                      <Ionicons name="star" size={16} color="#eab308" />
                      <Text style={styles.quickInfoText}>{spot.rating.toFixed(1)}</Text>
                    </View>
                  </View>

                  {isExpanded && (
                    <View style={styles.spotDetails}>
                      <Text style={styles.spotDescription}>{spot.description}</Text>
                      
                      <View style={styles.detailSection}>
                        <Text style={styles.detailLabel}>📍 Coordinates:</Text>
                        <Text style={styles.detailValue}>{spot.latitude.toFixed(4)}, {spot.longitude.toFixed(4)}</Text>
                      </View>

                      <View style={styles.detailSection}>
                        <Text style={styles.detailLabel}>⏱ Stay Limit:</Text>
                        <Text style={styles.detailValue}>{spot.stay_limit}</Text>
                      </View>

                      <View style={styles.detailSection}>
                        <Text style={styles.detailLabel}>🏔 Elevation:</Text>
                        <Text style={styles.detailValue}>{spot.elevation_ft.toLocaleString()} ft</Text>
                      </View>

                      {spot.contact && (
                        <View style={styles.detailSection}>
                          <Text style={styles.detailLabel}>📞 Contact:</Text>
                          <Text style={styles.detailValue}>{spot.contact}</Text>
                        </View>
                      )}

                      {spot.phone && !spot.contact && (
                        <View style={styles.detailSection}>
                          <Text style={styles.detailLabel}>📞 Phone:</Text>
                          <TouchableOpacity onPress={() => Linking.openURL(`tel:${spot.phone}`)}>
                            <Text style={[styles.detailValue, { color: '#06b6d4' }]}>{spot.phone}</Text>
                          </TouchableOpacity>
                        </View>
                      )}

                      {spot.website && (
                        <View style={styles.detailSection}>
                          <Text style={styles.detailLabel}>🌐 Website:</Text>
                          <TouchableOpacity onPress={() => Linking.openURL(spot.website!)}>
                            <Text style={[styles.detailValue, { color: '#06b6d4', textDecorationLine: 'underline' }]}>
                              {spot.website}
                            </Text>
                          </TouchableOpacity>
                        </View>
                      )}

                      {spot.amenities.length > 0 && (
                        <View style={styles.detailSection}>
                          <Text style={styles.detailLabel}>✨ Amenities:</Text>
                          <View style={styles.amenitiesList}>
                            {spot.amenities.map((amenity, i) => (
                              <View key={i} style={styles.amenityChip}>
                                <Text style={styles.amenityText}>{amenity}</Text>
                              </View>
                            ))}
                          </View>
                        </View>
                      )}

                      <View style={styles.infoNote}>
                        <Ionicons name="information-circle-outline" size={14} color="#9ca3af" />
                        <Text style={styles.infoNoteText}>The campsite name and details will be shown in Google Maps when you navigate to this location.</Text>
                      </View>

                      <TouchableOpacity
                        style={styles.navigateButton}
                        onPress={() => openInMaps(spot)}
                      >
                        <Ionicons name="navigate" size={18} color="#fff" />
                        <Text style={styles.navigateButtonText}>Navigate with Google Maps</Text>
                      </TouchableOpacity>
                    </View>
                  )}
                </TouchableOpacity>
              );
            })}
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#18181b',
  },
  backButton: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 12,
    gap: 8,
  },
  backText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '600',
  },
  content: {
    flex: 1,
    paddingHorizontal: 16,
  },
  card: {
    backgroundColor: '#27272a',
    borderRadius: 16,
    padding: 20,
    marginBottom: 16,
  },
  title: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#e5e7eb',
    marginBottom: 8,
  },
  subtitle: {
    fontSize: 14,
    color: '#9ca3af',
    marginBottom: 16,
  },
  locationBox: {
    backgroundColor: '#1f1f23',
    borderRadius: 12,
    padding: 14,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: '#06b6d420',
  },
  locationSearchRow: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#27272a',
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 8,
    marginBottom: 8,
    borderWidth: 1,
    borderColor: '#3f3f46',
  },
  locationSearchInput: {
    flex: 1,
    color: '#f4f4f5',
    fontSize: 14,
    paddingVertical: 0,
  },
  suggestionsBox: {
    backgroundColor: '#18181b',
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#3f3f46',
    marginBottom: 8,
    overflow: 'hidden',
  },
  suggestionRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingVertical: 10,
  },
  suggestionDivider: {
    borderTopWidth: 1,
    borderTopColor: '#27272a',
  },
  suggestionText: {
    color: '#e4e4e7',
    fontSize: 13,
    flex: 1,
  },
  locationActiveRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 8,
  },
  locationChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    flex: 1,
  },
  locationChipText: {
    color: '#06b6d4',
    fontSize: 13,
    fontWeight: '600',
    flex: 1,
  },
  useGpsBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 8,
    backgroundColor: '#06b6d415',
    borderWidth: 1,
    borderColor: '#06b6d430',
  },
  useGpsBtnText: {
    color: '#06b6d4',
    fontSize: 12,
    fontWeight: '600',
  },
  // legacy styles kept so nothing else breaks
  locationHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 8,
    gap: 8,
  },
  locationLabel: {
    color: '#9ca3af',
    fontSize: 13,
    fontWeight: '500',
    flex: 1,
  },
  refreshLocationBtn: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: '#06b6d415',
    justifyContent: 'center',
    alignItems: 'center',
  },
  locationCoords: {
    color: '#06b6d4',
    fontSize: 15,
    fontWeight: '600',
    fontFamily: 'monospace',
  },
  locationInfo: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#3f3f46',
    borderRadius: 8,
    padding: 12,
    marginBottom: 12,
    gap: 8,
  },
  locationText: {
    fontSize: 14,
    color: '#e5e7eb',
    flex: 1,
  },
  locationButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#3f3f46',
    borderRadius: 8,
    padding: 12,
    marginBottom: 16,
    gap: 8,
  },
  locationButtonText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#06b6d4',
  },
  loadingLocationBox: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#3f3f46',
    borderRadius: 8,
    padding: 12,
    marginBottom: 16,
    gap: 8,
  },
  loadingLocationText: {
    fontSize: 14,
    color: '#9ca3af',
    fontStyle: 'italic',
  },
  inputRow: {
    marginBottom: 16,
  },
  label: {
    fontSize: 14,
    fontWeight: '600',
    color: '#e5e7eb',
    marginBottom: 8,
  },
  input: {
    backgroundColor: '#3f3f46',
    borderRadius: 8,
    padding: 12,
    fontSize: 16,
    color: '#e5e7eb',
  },
  calculateButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#06b6d4',
    borderRadius: 12,
    padding: 16,
    marginTop: 8,
    gap: 8,
    minHeight: 52,
  },
  buttonDisabled: {
    opacity: 0.6,
  },
  calculateButtonText: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#fff',
  },
  errorBox: {
    flexDirection: 'column',
    alignItems: 'center',
    backgroundColor: '#27272a',
    borderRadius: 8,
    padding: 16,
    marginTop: 16,
    gap: 8,
    borderLeftWidth: 4,
    borderLeftColor: '#ef4444',
    minHeight: 60,
  },
  errorText: {
    fontSize: 14,
    color: '#ef4444',
    textAlign: 'center',
  },
  retryText: {
    fontSize: 12,
    color: '#9ca3af',
    marginTop: 4,
    textAlign: 'center',
  },
  resultsContainer: {
    marginBottom: 24,
  },
  resultsTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#e5e7eb',
    marginBottom: 12,
  },
  spotCard: {
    backgroundColor: '#27272a',
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
    borderLeftWidth: 4,
    borderLeftColor: '#06b6d4',
  },
  spotCardExpanded: {
    backgroundColor: '#2d2d30',
  },
  spotHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 8,
  },
  spotHeaderLeft: {
    flex: 1,
  },
  spotName: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#e5e7eb',
    marginBottom: 6,
  },
  spotTypeRow: {
    flexDirection: 'row',
    gap: 8,
  },
  spotTypeBadge: {
    backgroundColor: '#3f3f46',
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 4,
  },
  spotTypeBadgeText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#9ca3af',
  },
  freeBadge: {
    backgroundColor: '#22c55e',
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 4,
  },
  freeBadgeText: {
    fontSize: 12,
    fontWeight: 'bold',
    color: '#fff',
  },
  spotQuickInfo: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
    marginTop: 8,
  },
  quickInfoItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  quickInfoText: {
    fontSize: 13,
    color: '#9ca3af',
    textTransform: 'capitalize',
  },
  spotDetails: {
    marginTop: 12,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: '#3f3f46',
  },
  spotDescription: {
    fontSize: 14,
    color: '#d1d5db',
    lineHeight: 20,
    marginBottom: 12,
  },
  detailSection: {
    marginBottom: 10,
  },
  detailLabel: {
    fontSize: 13,
    fontWeight: '600',
    color: '#9ca3af',
    marginBottom: 4,
  },
  detailValue: {
    fontSize: 14,
    color: '#e5e7eb',
  },
  amenitiesList: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginTop: 4,
  },
  amenityChip: {
    backgroundColor: '#3f3f46',
    borderRadius: 12,
    paddingHorizontal: 10,
    paddingVertical: 5,
  },
  amenityText: {
    fontSize: 12,
    color: '#e5e7eb',
  },
  infoNote: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    backgroundColor: '#3f3f46',
    borderRadius: 6,
    padding: 8,
    marginTop: 8,
    gap: 6,
  },
  infoNoteText: {
    flex: 1,
    fontSize: 11,
    color: '#9ca3af',
    lineHeight: 16,
  },
  navigateButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#06b6d4',
    borderRadius: 8,
    padding: 12,
    marginTop: 12,
    gap: 8,
  },
  navigateButtonText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#fff',
  },  skeletonTitle: {
    width: '50%',
    height: 24,
    backgroundColor: '#3f3f46',
    borderRadius: 6,
    marginBottom: 12,
  },
  skeletonCard: {
    backgroundColor: '#27272a',
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
    borderLeftWidth: 4,
    borderLeftColor: '#3f3f46',
  },
  skeletonHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 12,
  },
  skeletonTextLarge: {
    width: '60%',
    height: 20,
    backgroundColor: '#3f3f46',
    borderRadius: 4,
  },
  skeletonTextSmall: {
    width: '80%',
    height: 16,
    backgroundColor: '#3f3f46',
    borderRadius: 4,
    marginBottom: 8,
  },
  skeletonCircle: {
    width: 24,
    height: 24,
    backgroundColor: '#3f3f46',
    borderRadius: 12,
  },});
