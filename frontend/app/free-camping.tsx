import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, TextInput, ActivityIndicator, ScrollView, Alert, Linking, RefreshControl } from 'react-native';
import axios from 'axios';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import * as Location from 'expo-location';
import { API_BASE } from './apiConfig';

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
  phone?: string;
  website?: string;
  contact?: string;
}

export default function FreeCampingScreen() {
  const router = useRouter();
  const [latitude, setLatitude] = useState('34.05');
  const [longitude, setLongitude] = useState('-111.03');
  const [searchRadius, setSearchRadius] = useState('25'); // miles
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [locationLoading, setLocationLoading] = useState(false);
  const [spots, setSpots] = useState<CampingSpot[]>([]);
  const [error, setError] = useState<string>('');
  const [expandedSpots, setExpandedSpots] = useState(new Set<number>());

  // Automatically get current location on mount
  useEffect(() => {
    (async () => {
      try {
        const { status } = await Location.requestForegroundPermissionsAsync();
        if (status === 'granted') {
          const location = await Location.getCurrentPositionAsync({});
          setLatitude(location.coords.latitude.toFixed(4));
          setLongitude(location.coords.longitude.toFixed(4));
        }
      } catch (err) {
        // Silently fail and use default coordinates
        console.log('Could not get current location, using defaults');
      }
    })();
  }, []);

  const useCurrentLocation = async () => {
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
      Alert.alert('Location Updated', 'Your current location has been set.');
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
      const resp = await axios.post(`${API_BASE}/api/pro/free-camping/search`, {
        latitude: parseFloat(latitude),
        longitude: parseFloat(longitude),
        radius_miles: parseInt(searchRadius, 10),
        subscription_id: 'test',
      });
      setSpots(resp.data.spots || []);
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
          <Text style={styles.infoNote}>💡 Tip: The campsite name will typically appear in Google Maps when you navigate to the location.</Text>

          <View style={styles.locationInfo}>
            <Ionicons name="location" size={16} color="#06b6d4" />
            <Text style={styles.locationText}>
              Searching near: {latitude}, {longitude}
            </Text>
          </View>

          <TouchableOpacity 
            onPress={useCurrentLocation} 
            style={styles.locationButton}
            disabled={locationLoading}
          >
            {locationLoading ? (
              <ActivityIndicator size="small" color="#06b6d4" />
            ) : (
              <>
                <Ionicons name="locate" size={18} color="#06b6d4" />
                <Text style={styles.locationButtonText}>Use Current Location</Text>
              </>
            )}
          </TouchableOpacity>

          <View style={styles.inputRow}>
            <Text style={styles.label}>Latitude</Text>
            <TextInput
              value={latitude}
              onChangeText={setLatitude}
              keyboardType="numeric"
              style={styles.input}
              placeholder="e.g., 34.05"
              placeholderTextColor="#9ca3af"
            />
          </View>

          <View style={styles.inputRow}>
            <Text style={styles.label}>Longitude</Text>
            <TextInput
              value={longitude}
              onChangeText={setLongitude}
              keyboardType="numeric"
              style={styles.input}
              placeholder="e.g., -111.03"
              placeholderTextColor="#9ca3af"
            />
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
            <Text style={styles.resultsTitle}>Found {spots.length} Free Camping Spot{spots.length !== 1 ? 's' : ''}</Text>
            
            {spots.map((spot, index) => {
              const isExpanded = expandedSpots.has(index);
              
              return (
                <TouchableOpacity
                  key={index}
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
  infoNote: {
    fontSize: 12,
    color: '#fbbf24',
    marginBottom: 16,
    fontStyle: 'italic',
    lineHeight: 18,
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
