import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, TextInput, ActivityIndicator, ScrollView, Alert, Linking, RefreshControl } from 'react-native';
import axios from 'axios';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import * as Location from 'expo-location';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { API_BASE } from './apiConfig';

interface ParkingSpot {
  name: string;
  type: string;
  distance_miles: number;
  latitude: number;
  longitude: number;
  capacity?: number;
  amenities: string[];
  restrictions: string[];
  hours?: string;
  fee?: string;
}

export default function TruckParkingScreen() {
  const router = useRouter();
  const [latitude, setLatitude] = useState('');
  const [longitude, setLongitude] = useState('');
  const [searchRadius, setSearchRadius] = useState('25');
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [locationLoading, setLocationLoading] = useState(false);
  const [spots, setSpots] = useState<ParkingSpot[]>([]);
  const [error, setError] = useState<string>('');
  const [expandedSpots, setExpandedSpots] = useState(new Set<number>());

  useEffect(() => {
    getCurrentLocation();
  }, []);

  const getCurrentLocation = async () => {
    try {
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status === 'granted') {
        const location = await Location.getCurrentPositionAsync({});
        setLatitude(location.coords.latitude.toFixed(4));
        setLongitude(location.coords.longitude.toFixed(4));
      }
    } catch (err) {
      console.log('Could not get current location:', err);
      // Set default location (center of US) if location fails
      setLatitude('39.8283');
      setLongitude('-98.5795');
    }
  };

  const useCurrentLocation = async () => {
    setLocationLoading(true);
    try {
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== 'granted') {
        Alert.alert('Location Permission Required', 'Please enable location permissions.');
        setLocationLoading(false);
        return;
      }

      const location = await Location.getCurrentPositionAsync({
        accuracy: Location.Accuracy.Balanced,
      });
      setLatitude(location.coords.latitude.toFixed(4));
      setLongitude(location.coords.longitude.toFixed(4));
      setLocationLoading(false);
    } catch (err: any) {
      setLocationLoading(false);
      Alert.alert('Location Error', err.message || 'Unable to get your location.');
    }
  };

  const searchParking = async () => {
    setLoading(true);
    setSpots([]);
    setError('');
    try {
      const resp = await axios.post(`${API_BASE}/api/pro/truck-parking/search`, {
        latitude: parseFloat(latitude),
        longitude: parseFloat(longitude),
        radius_miles: parseInt(searchRadius, 10),
      });
      setSpots(resp.data.spots || []);
      if (resp.data.spots && resp.data.spots.length === 0) {
        setError('No truck parking found in this area. Try increasing the search radius.');
      }
    } catch (err: any) {
      console.error('Truck parking search error:', err);
      setError(err?.response?.data?.detail || 'Failed to find truck parking. Tap to retry.');
    } finally {
      setLoading(false);
    }
  };

  const onRefresh = async () => {
    setRefreshing(true);
    await searchParking();
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

  const openInMaps = (spot: ParkingSpot) => {
    const url = `https://www.google.com/maps/dir/?api=1&destination=${spot.latitude},${spot.longitude}`;
    Linking.openURL(url);
  };

  const getTypeColor = (type: string) => {
    switch (type) {
      case 'rest_area': return '#22c55e';
      case 'parking_lot': return '#3b82f6';
      case 'truck_stop': return '#f59e0b';
      default: return '#6b7280';
    }
  };

  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'rest_area': return 'bed';
      case 'parking_lot': return 'car';
      case 'truck_stop': return 'business';
      default: return 'location';
    }
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#22c55e" />}
      >
        <View style={styles.header}>
          <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
            <Ionicons name="arrow-back" size={24} color="#fff" />
          </TouchableOpacity>
          <Text style={styles.title}>🅿️ Truck Parking</Text>
          <Text style={styles.subtitle}>Rest areas and safe parking zones</Text>
        </View>

        <View style={styles.formContainer}>
          <TouchableOpacity
            style={styles.locationButton}
            onPress={useCurrentLocation}
            disabled={locationLoading}
          >
            {locationLoading ? (
              <ActivityIndicator size="small" color="#fff" />
            ) : (
              <>
                <Ionicons name="locate" size={20} color="#fff" />
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
            onPress={searchParking}
            style={[styles.searchButton, loading && styles.buttonDisabled]}
            disabled={loading}
          >
            {loading ? (
              <ActivityIndicator size="small" color="#fff" />
            ) : (
              <>
                <Ionicons name="search" size={20} color="#fff" />
                <Text style={styles.searchButtonText}>Find Parking</Text>
              </>
            )}
          </TouchableOpacity>

          {error ? (
            <TouchableOpacity style={styles.errorBox} onPress={searchParking}>
              <Ionicons name="alert-circle" size={20} color="#ef4444" />
              <Text style={styles.errorText}>{error}</Text>
            </TouchableOpacity>
          ) : null}
        </View>

        {spots.length > 0 && (
          <View style={styles.resultsContainer}>
            <Text style={styles.resultsTitle}>Found {spots.length} Parking Spot{spots.length !== 1 ? 's' : ''}</Text>
            
            {spots.map((spot, index) => {
              const isExpanded = expandedSpots.has(index);
              const typeColor = getTypeColor(spot.type);
              
              return (
                <TouchableOpacity
                  key={index}
                  style={[styles.spotCard, isExpanded && styles.spotCardExpanded]}
                  onPress={() => toggleSpotExpand(index)}
                  activeOpacity={0.8}
                >
                  <View style={styles.spotHeader}>
                    <View style={styles.spotHeaderLeft}>
                      <View style={styles.nameRow}>
                        <Ionicons name={getTypeIcon(spot.type) as any} size={20} color={typeColor} />
                        <Text style={styles.spotName}>{spot.name}</Text>
                      </View>
                      <View style={styles.typeBadge} style={{ backgroundColor: typeColor + '20' }}>
                        <Text style={[styles.typeBadgeText, { color: typeColor }]}>
                          {spot.type.replace('_', ' ').toUpperCase()}
                        </Text>
                      </View>
                    </View>
                    <Ionicons name={isExpanded ? "chevron-up" : "chevron-down"} size={24} color="#9ca3af" />
                  </View>

                  <View style={styles.spotQuickInfo}>
                    <View style={styles.quickInfoItem}>
                      <Ionicons name="navigate" size={16} color="#06b6d4" />
                      <Text style={styles.quickInfoText}>{spot.distance_miles.toFixed(1)} mi</Text>
                    </View>
                    {spot.capacity && (
                      <View style={styles.quickInfoItem}>
                        <Ionicons name="car" size={16} color="#22c55e" />
                        <Text style={styles.quickInfoText}>{spot.capacity} spaces</Text>
                      </View>
                    )}
                    {spot.fee && (
                      <View style={styles.quickInfoItem}>
                        <Ionicons name="cash" size={16} color={spot.fee === 'Free' ? '#22c55e' : '#f59e0b'} />
                        <Text style={styles.quickInfoText}>{spot.fee}</Text>
                      </View>
                    )}
                  </View>

                  {isExpanded && (
                    <View style={styles.spotDetails}>
                      {spot.amenities.length > 0 && (
                        <View style={styles.detailSection}>
                          <Text style={styles.detailLabel}>Amenities</Text>
                          <View style={styles.tagContainer}>
                            {spot.amenities.map((amenity, i) => (
                              <View key={i} style={styles.tag}>
                                <Text style={styles.tagText}>{amenity}</Text>
                              </View>
                            ))}
                          </View>
                        </View>
                      )}

                      {spot.restrictions.length > 0 && (
                        <View style={styles.detailSection}>
                          <Text style={styles.detailLabel}>Restrictions</Text>
                          <View style={styles.tagContainer}>
                            {spot.restrictions.map((restriction, i) => (
                              <View key={i} style={[styles.tag, styles.restrictionTag]}>
                                <Text style={styles.tagText}>{restriction}</Text>
                              </View>
                            ))}
                          </View>
                        </View>
                      )}

                      {spot.hours && (
                        <View style={styles.detailSection}>
                          <Text style={styles.detailLabel}>Hours</Text>
                          <Text style={styles.detailValue}>{spot.hours}</Text>
                        </View>
                      )}

                      <TouchableOpacity style={styles.directionsButton} onPress={() => openInMaps(spot)}>
                        <Ionicons name="navigate" size={20} color="#fff" />
                        <Text style={styles.directionsButtonText}>Get Directions</Text>
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
    backgroundColor: '#0a0a0a',
  },
  scrollContent: {
    paddingBottom: 40,
  },
  header: {
    backgroundColor: '#1a1a1a',
    paddingHorizontal: 20,
    paddingTop: 12,
    paddingBottom: 24,
    borderBottomWidth: 1,
    borderBottomColor: '#27272a',
  },
  backButton: {
    marginBottom: 16,
  },
  title: {
    fontSize: 28,
    fontWeight: 'bold',
    color: '#fff',
    marginBottom: 8,
  },
  subtitle: {
    fontSize: 14,
    color: '#a1a1aa',
  },
  formContainer: {
    padding: 20,
    backgroundColor: '#1a1a1a',
    margin: 16,
    borderRadius: 12,
  },
  locationButton: {
    backgroundColor: '#22c55e',
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 14,
    borderRadius: 10,
    marginBottom: 20,
    gap: 8,
  },
  locationButtonText: {
    color: '#fff',
    fontSize: 15,
    fontWeight: '600',
  },
  inputRow: {
    marginBottom: 16,
  },
  label: {
    color: '#d4d4d8',
    fontSize: 13,
    fontWeight: '600',
    marginBottom: 8,
  },
  input: {
    backgroundColor: '#27272a',
    color: '#fff',
    padding: 12,
    borderRadius: 8,
    fontSize: 15,
  },
  searchButton: {
    backgroundColor: '#3b82f6',
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 14,
    borderRadius: 10,
    gap: 8,
  },
  buttonDisabled: {
    opacity: 0.5,
  },
  searchButtonText: {
    color: '#fff',
    fontSize: 15,
    fontWeight: '700',
  },
  errorBox: {
    backgroundColor: '#422006',
    padding: 12,
    borderRadius: 8,
    marginTop: 12,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  errorText: {
    color: '#f59e0b',
    fontSize: 13,
    flex: 1,
  },
  resultsContainer: {
    padding: 16,
  },
  resultsTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: '#fff',
    marginBottom: 16,
  },
  spotCard: {
    backgroundColor: '#1a1a1a',
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
    borderLeftWidth: 4,
    borderLeftColor: '#22c55e',
  },
  spotCardExpanded: {
    borderLeftColor: '#3b82f6',
  },
  spotHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 12,
  },
  spotHeaderLeft: {
    flex: 1,
  },
  nameRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 8,
  },
  spotName: {
    fontSize: 17,
    fontWeight: '700',
    color: '#fff',
    flex: 1,
  },
  typeBadge: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 6,
    alignSelf: 'flex-start',
  },
  typeBadgeText: {
    fontSize: 11,
    fontWeight: '700',
  },
  spotQuickInfo: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 16,
  },
  quickInfoItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  quickInfoText: {
    color: '#a1a1aa',
    fontSize: 13,
  },
  spotDetails: {
    marginTop: 16,
    paddingTop: 16,
    borderTopWidth: 1,
    borderTopColor: '#27272a',
  },
  detailSection: {
    marginBottom: 12,
  },
  detailLabel: {
    color: '#d4d4d8',
    fontSize: 13,
    fontWeight: '600',
    marginBottom: 8,
  },
  detailValue: {
    color: '#a1a1aa',
    fontSize: 14,
  },
  tagContainer: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  tag: {
    backgroundColor: '#27272a',
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 6,
  },
  restrictionTag: {
    backgroundColor: '#7c2d12',
  },
  tagText: {
    color: '#d4d4d8',
    fontSize: 12,
  },
  directionsButton: {
    backgroundColor: '#3b82f6',
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 12,
    borderRadius: 8,
    gap: 6,
    marginTop: 12,
  },
  directionsButtonText: {
    color: '#fff',
    fontSize: 14,
    fontWeight: '600',
  },
});
