import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, TextInput, ActivityIndicator, ScrollView, Alert, Linking, RefreshControl } from 'react-native';
import axios from 'axios';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import * as Location from 'expo-location';
import { API_BASE } from './apiConfig';

interface DumpStation {
  name: string;
  type: string; // 'RV Park', 'Rest Stop', 'Gas Station', 'Standalone'
  distance_miles: number;
  latitude: number;
  longitude: number;
  description: string;
  has_potable_water: boolean;
  is_free: boolean;
  cost: string;
  hours: string;
  restrictions: string[];
  access: string; // 'easy', 'moderate', 'difficult'
  rating: number;
  address?: string;
  website?: string;
  phone?: string;
}

export default function DumpStationScreen() {
  const router = useRouter();
  const [latitude, setLatitude] = useState('34.05');
  const [longitude, setLongitude] = useState('-111.03');
  const [searchRadius, setSearchRadius] = useState('50'); // miles - larger default for dump stations
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [locationLoading, setLocationLoading] = useState(false);
  const [stations, setStations] = useState<DumpStation[]>([]);
  const [error, setError] = useState<string>('');
  const [expandedStations, setExpandedStations] = useState(new Set<number>());

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

  const searchDumpStations = async () => {
    setLoading(true);
    setStations([]);
    setError('');
    try {
      const resp = await axios.post(`${API_BASE}/api/pro/dump-stations/search`, {
        latitude: parseFloat(latitude),
        longitude: parseFloat(longitude),
        radius_miles: parseInt(searchRadius, 10),
        subscription_id: 'test',
      });
      setStations(resp.data.stations || []);
      if (resp.data.stations && resp.data.stations.length === 0) {
        setError('No dump stations found in this area. Try increasing the search radius.');
      }
    } catch (err: any) {
      console.error('Dump station search error:', err);
      setError(err?.response?.data?.detail || err?.message || 'Failed to find dump stations. Tap to retry.');
    } finally {
      setLoading(false);
    }
  };

  const onRefresh = async () => {
    setRefreshing(true);
    await searchDumpStations();
    setRefreshing(false);
  };

  const toggleStationExpand = (index: number) => {
    const newExpanded = new Set(expandedStations);
    if (newExpanded.has(index)) {
      newExpanded.delete(index);
    } else {
      newExpanded.add(index);
    }
    setExpandedStations(newExpanded);
  };

  const openInMaps = (station: DumpStation) => {
    const url = `https://www.google.com/maps/dir/?api=1&destination=${station.latitude},${station.longitude}`;
    Linking.openURL(url);
  };

  return (
    <SafeAreaView style={styles.container}>
      <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
        <Ionicons name="arrow-back" size={24} color="#fff" />
        <Text style={styles.backText}>Back</Text>
      </TouchableOpacity>

      <ScrollView style={styles.content}>
        <View style={styles.card}>
          <Text style={styles.title}>🚿 Dump Station Finder</Text>
          <Text style={styles.subtitle}>Locate RV dump stations and fresh water fill points</Text>
          <Text style={styles.infoNote}>💡 Tip: The station name will typically appear in Google Maps when you navigate to the location.</Text>

          <View style={styles.locationInfo}>
            <Ionicons name="location" size={16} color="#8b5cf6" />
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
              <ActivityIndicator size="small" color="#8b5cf6" />
            ) : (
              <>
                <Ionicons name="locate" size={18} color="#8b5cf6" />
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
              placeholder="e.g., 50"
              placeholderTextColor="#9ca3af"
            />
          </View>

          <TouchableOpacity
            onPress={searchDumpStations}
            style={[styles.calculateButton, loading && styles.buttonDisabled]}
            disabled={loading}
          >
            {loading ? (
              <ActivityIndicator size="small" color="#fff" />
            ) : (
              <>
                <Ionicons name="search" size={20} color="#fff" />
                <Text style={styles.calculateButtonText}>Find Dump Stations</Text>
              </>
            )}
          </TouchableOpacity>

          {error ? (
            <View style={styles.errorBox}>
              <Ionicons name="alert-circle" size={20} color="#ef4444" />
              <Text style={styles.errorText}>{error}</Text>
            </View>
          ) : null}
        </View>

        {/* Results */}
        {stations.length > 0 && (
          <View style={styles.resultsContainer}>
            <Text style={styles.resultsTitle}>Found {stations.length} Dump Station{stations.length !== 1 ? 's' : ''}</Text>
            
            {stations.map((station, index) => {
              const isExpanded = expandedStations.has(index);
              
              return (
                <TouchableOpacity
                  key={index}
                  style={[styles.stationCard, isExpanded && styles.stationCardExpanded]}
                  onPress={() => toggleStationExpand(index)}
                  activeOpacity={0.8}
                >
                  <View style={styles.stationHeader}>
                    <View style={styles.stationHeaderLeft}>
                      <Text style={styles.stationName}>{station.name}</Text>
                      <View style={styles.stationTypeRow}>
                        <View style={styles.stationTypeBadge}>
                          <Text style={styles.stationTypeBadgeText}>{station.type}</Text>
                        </View>
                        {station.is_free && (
                          <View style={styles.freeBadge}>
                            <Text style={styles.freeBadgeText}>FREE</Text>
                          </View>
                        )}
                        {station.has_potable_water && (
                          <View style={styles.waterBadge}>
                            <Ionicons name="water" size={12} color="#fff" />
                            <Text style={styles.waterBadgeText}>Water</Text>
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

                  <View style={styles.stationQuickInfo}>
                    <View style={styles.quickInfoItem}>
                      <Ionicons name="navigate" size={16} color="#8b5cf6" />
                      <Text style={styles.quickInfoText}>{station.distance_miles.toFixed(1)} mi</Text>
                    </View>
                    {!station.is_free && (
                      <View style={styles.quickInfoItem}>
                        <Ionicons name="cash" size={16} color="#eab308" />
                        <Text style={styles.quickInfoText}>{station.cost}</Text>
                      </View>
                    )}
                    <View style={styles.quickInfoItem}>
                      <Ionicons name="star" size={16} color="#eab308" />
                      <Text style={styles.quickInfoText}>{station.rating.toFixed(1)}</Text>
                    </View>
                  </View>

                  {isExpanded && (
                    <View style={styles.stationDetails}>
                      <Text style={styles.stationDescription}>{station.description}</Text>
                      
                      <View style={styles.detailSection}>
                        <Text style={styles.detailLabel}>📍 Coordinates:</Text>
                        <Text style={styles.detailValue}>{station.latitude.toFixed(4)}, {station.longitude.toFixed(4)}</Text>
                      </View>

                      <View style={styles.detailSection}>
                        <Text style={styles.detailLabel}>💰 Cost:</Text>
                        <Text style={styles.detailValue}>{station.is_free ? 'Free' : station.cost}</Text>
                      </View>

                      <View style={styles.detailSection}>
                        <Text style={styles.detailLabel}>🕐 Hours:</Text>
                        <Text style={styles.detailValue}>{station.hours}</Text>
                      </View>

                      <View style={styles.detailSection}>
                        <Text style={styles.detailLabel}>💧 Potable Water:</Text>
                        <Text style={styles.detailValue}>{station.has_potable_water ? 'Yes - Fresh water fill available' : 'No'}</Text>
                      </View>

                      {station.address && (
                        <View style={styles.detailSection}>
                          <Text style={styles.detailLabel}>📍 Address:</Text>
                          <Text style={styles.detailValue}>{station.address}</Text>
                        </View>
                      )}

                      {station.phone && (
                        <View style={styles.detailSection}>
                          <Text style={styles.detailLabel}>📞 Phone:</Text>
                          <TouchableOpacity onPress={() => Linking.openURL(`tel:${station.phone}`)}>
                            <Text style={[styles.detailValue, { color: '#06b6d4' }]}>{station.phone}</Text>
                          </TouchableOpacity>
                        </View>
                      )}

                      {station.website && (
                        <View style={styles.detailSection}>
                          <Text style={styles.detailLabel}>🌐 Website:</Text>
                          <TouchableOpacity onPress={() => Linking.openURL(station.website!)}>
                            <Text style={[styles.detailValue, { color: '#06b6d4', textDecorationLine: 'underline' }]}>
                              {station.website}
                            </Text>
                          </TouchableOpacity>
                        </View>
                      )}

                      {station.restrictions.length > 0 && (
                        <View style={styles.detailSection}>
                          <Text style={styles.detailLabel}>⚠️ Restrictions:</Text>
                          <View style={styles.restrictionsList}>
                            {station.restrictions.map((restriction, i) => (
                              <View key={i} style={styles.restrictionItem}>
                                <Ionicons name="alert-circle-outline" size={14} color="#f97316" />
                                <Text style={styles.restrictionText}>{restriction}</Text>
                              </View>
                            ))}
                          </View>
                        </View>
                      )}

                      <View style={styles.infoNote}>
                        <Ionicons name="information-circle-outline" size={14} color="#9ca3af" />
                        <Text style={styles.infoNoteText}>The station name and details will be shown in Google Maps when you navigate to this location.</Text>
                      </View>

                      <TouchableOpacity
                        style={styles.navigateButton}
                        onPress={() => openInMaps(station)}
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
    color: '#8b5cf6',
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
    backgroundColor: '#8b5cf6',
    borderRadius: 12,
    padding: 16,
    marginTop: 8,
    gap: 8,
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
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#27272a',
    borderRadius: 8,
    padding: 12,
    marginTop: 16,
    gap: 8,
    borderLeftWidth: 4,
    borderLeftColor: '#ef4444',
  },
  errorText: {
    fontSize: 14,
    color: '#ef4444',
    flex: 1,
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
  stationCard: {
    backgroundColor: '#27272a',
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
    borderLeftWidth: 4,
    borderLeftColor: '#8b5cf6',
  },
  stationCardExpanded: {
    backgroundColor: '#2d2d30',
  },
  stationHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 8,
  },
  stationHeaderLeft: {
    flex: 1,
  },
  stationName: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#e5e7eb',
    marginBottom: 6,
  },
  stationTypeRow: {
    flexDirection: 'row',
    gap: 8,
    flexWrap: 'wrap',
  },
  stationTypeBadge: {
    backgroundColor: '#3f3f46',
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 4,
  },
  stationTypeBadgeText: {
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
  waterBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#06b6d4',
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 4,
    gap: 4,
  },
  waterBadgeText: {
    fontSize: 12,
    fontWeight: 'bold',
    color: '#fff',
  },
  stationQuickInfo: {
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
  },
  stationDetails: {
    marginTop: 12,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: '#3f3f46',
  },
  stationDescription: {
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
  restrictionsList: {
    marginTop: 4,
    gap: 6,
  },
  restrictionItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  restrictionText: {
    fontSize: 13,
    color: '#f97316',
    flex: 1,
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
    backgroundColor: '#8b5cf6',
    borderRadius: 8,
    padding: 12,
    marginTop: 12,
    gap: 8,
  },
  navigateButtonText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#fff',
  },
});
