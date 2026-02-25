import React, { useState } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, TextInput, ActivityIndicator, ScrollView, Alert, Linking, RefreshControl } from 'react-native';
import axios from 'axios';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { API_BASE, buildUrl } from '../lib/apiConfig';
import InfoBanner from '../lib/components/InfoBanner';
import { useLocationSearch } from '../lib/useLocationSearch';
import LocationSearchBox from '../lib/components/LocationSearchBox';

interface TruckStop {
  name: string;
  brand?: string;
  distance_miles: number;
  latitude: number;
  longitude: number;
  amenities: string[];
  fuel_types: string[];
  services: string[];
  rating?: number;
  phone?: string;
  website?: string;
  hours?: string;
}

export default function TruckStopsScreen() {
  const router = useRouter();

  // ── Location (manual search + explicit GPS only) ────────────────────
  const {
    lat: latitude, lon: longitude,
    locationLabel, locationLoading,
    locationQuery, suggestions, showSuggestions,
    handleLocationQueryChange, selectSuggestion,
    clearManualLocation, triggerGps, setShowSuggestions,
  } = useLocationSearch('truckStopsLoc');

  const [searchRadius, setSearchRadius] = useState('15');
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [stops, setStops] = useState<TruckStop[]>([]);
  const [error, setError] = useState<string>('');
  const [expandedStops, setExpandedStops] = useState(new Set<number>());



  const refreshLocation = async () => {
    await triggerGps();
  };

  const searchTruckStops = async () => {
    setLoading(true);
    setStops([]);
    setError('');
    try {
      const resp = await axios.post(buildUrl('truck-stops/search'), {
        latitude: parseFloat(latitude),
        longitude: parseFloat(longitude),
        radius_miles: parseInt(searchRadius, 10),
      }, {
        timeout: 65000, // 65 second timeout
      });
      setStops(resp.data.stops || []);
      if (resp.data.stops && resp.data.stops.length === 0) {
        setError('No truck stops found in this area. Try increasing the search radius.');
      }
    } catch (err: any) {
      console.error('Truck stops search error:', err);
      setError(err?.response?.data?.detail || 'Failed to find truck stops. Tap to retry.');
    } finally {
      setLoading(false);
    }
  };

  const onRefresh = async () => {
    setRefreshing(true);
    await searchTruckStops();
    setRefreshing(false);
  };

  const toggleStopExpand = (index: number) => {
    const newExpanded = new Set(expandedStops);
    if (newExpanded.has(index)) {
      newExpanded.delete(index);
    } else {
      newExpanded.add(index);
    }
    setExpandedStops(newExpanded);
  };

  const openInMaps = (stop: TruckStop) => {
    const url = `https://www.google.com/maps/dir/?api=1&destination=${stop.latitude},${stop.longitude}`;
    Linking.openURL(url);
  };

  const callPhone = (phone: string) => {
    Linking.openURL(`tel:${phone}`);
  };

  const openWebsite = (url: string) => {
    Linking.openURL(url);
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#3b82f6" />}
      >
        <View style={styles.header}>
          <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
            <Ionicons name="arrow-back" size={24} color="#fff" />
          </TouchableOpacity>
          <Text style={styles.title}>⛽ Truck Stops & Fuel</Text>
          <Text style={styles.subtitle}>Find Flying J, Love's, TA, Pilot, and more</Text>
        </View>

        <View style={styles.formContainer}>
          <LocationSearchBox
            lat={latitude}
            lon={longitude}
            locationLabel={locationLabel}
            locationLoading={locationLoading}
            locationQuery={locationQuery}
            suggestions={suggestions}
            showSuggestions={showSuggestions}
            handleLocationQueryChange={handleLocationQueryChange}
            selectSuggestion={selectSuggestion}
            clearManualLocation={clearManualLocation}
            triggerGps={triggerGps}
            setShowSuggestions={setShowSuggestions}
            accentColor="#3b82f6"
          />

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
            onPress={searchTruckStops}
            style={[styles.searchButton, loading && styles.buttonDisabled]}
            disabled={loading}
          >
            {loading ? (
              <ActivityIndicator size="small" color="#fff" />
            ) : (
              <>
                <Ionicons name="search" size={20} color="#fff" />
                <Text style={styles.searchButtonText}>Find Truck Stops</Text>
              </>
            )}
          </TouchableOpacity>

          <InfoBanner
            message={'ℹ️ To keep subscription costs low, we use free mapping data. Some locations may show as "Store" or generic names. When you tap "Directions" and open in Google Maps, the full business name will appear at your destination.'}
            style={{ marginTop: 12, marginBottom: 8 }}
          />

          {error ? (
            <TouchableOpacity style={styles.errorBox} onPress={searchTruckStops}>
              <Ionicons name="alert-circle" size={20} color="#ef4444" />
              <Text style={styles.errorText}>{error}</Text>
            </TouchableOpacity>
          ) : null}
        </View>

        {stops.length > 0 && (
          <View style={styles.resultsContainer}>
            <Text style={styles.resultsTitle}>Found {stops.length} Truck Stop{stops.length !== 1 ? 's' : ''}</Text>
            
            {stops.map((stop, index) => {
              const isExpanded = expandedStops.has(index);
              
              return (
                <TouchableOpacity
                  key={index}
                  style={[styles.stopCard, isExpanded && styles.stopCardExpanded]}
                  onPress={() => toggleStopExpand(index)}
                  activeOpacity={0.8}
                >
                  <View style={styles.stopHeader}>
                    <View style={styles.stopHeaderLeft}>
                      <Text style={styles.stopName}>{stop.name}</Text>
                      {stop.brand && (
                        <View style={styles.brandBadge}>
                          <Text style={styles.brandBadgeText}>{stop.brand}</Text>
                        </View>
                      )}
                    </View>
                    <Ionicons name={isExpanded ? "chevron-up" : "chevron-down"} size={24} color="#9ca3af" />
                  </View>

                  <View style={styles.stopQuickInfo}>
                    <View style={styles.quickInfoItem}>
                      <Ionicons name="navigate" size={16} color="#06b6d4" />
                      <Text style={styles.quickInfoText}>{stop.distance_miles.toFixed(1)} mi</Text>
                    </View>
                    {stop.fuel_types.length > 0 && (
                      <View style={styles.quickInfoItem}>
                        <Ionicons name="water" size={16} color="#22c55e" />
                        <Text style={styles.quickInfoText}>{stop.fuel_types.join(', ')}</Text>
                      </View>
                    )}
                  </View>

                  {isExpanded && (
                    <View style={styles.stopDetails}>
                      {stop.amenities.length > 0 && (
                        <View style={styles.detailSection}>
                          <Text style={styles.detailLabel}>Amenities</Text>
                          <View style={styles.tagContainer}>
                            {stop.amenities.map((amenity, i) => (
                              <View key={i} style={styles.tag}>
                                <Text style={styles.tagText}>{amenity}</Text>
                              </View>
                            ))}
                          </View>
                        </View>
                      )}

                      {stop.services.length > 0 && (
                        <View style={styles.detailSection}>
                          <Text style={styles.detailLabel}>Services</Text>
                          <View style={styles.tagContainer}>
                            {stop.services.map((service, i) => (
                              <View key={i} style={[styles.tag, styles.serviceTag]}>
                                <Text style={styles.tagText}>{service}</Text>
                              </View>
                            ))}
                          </View>
                        </View>
                      )}

                      {stop.hours && (
                        <View style={styles.detailSection}>
                          <Text style={styles.detailLabel}>Hours</Text>
                          <Text style={styles.detailValue}>{stop.hours}</Text>
                        </View>
                      )}

                      <View style={styles.actionButtons}>
                        <TouchableOpacity style={styles.actionButton} onPress={() => openInMaps(stop)}>
                          <Ionicons name="navigate" size={20} color="#fff" />
                          <Text style={styles.actionButtonText}>Directions</Text>
                        </TouchableOpacity>
                        {stop.phone && (
                          <TouchableOpacity style={styles.actionButton} onPress={() => callPhone(stop.phone!)}>
                            <Ionicons name="call" size={20} color="#fff" />
                            <Text style={styles.actionButtonText}>Call</Text>
                          </TouchableOpacity>
                        )}
                        {stop.website && (
                          <TouchableOpacity style={styles.actionButton} onPress={() => openWebsite(stop.website!)}>
                            <Ionicons name="globe" size={20} color="#fff" />
                            <Text style={styles.actionButtonText}>Website</Text>
                          </TouchableOpacity>
                        )}
                      </View>
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
  locationBox: {
    backgroundColor: '#1f1f23',
    borderRadius: 12,
    padding: 14,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: '#3b82f620',
  },
  locationBoxHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 8,
    gap: 8,
  },
  locationBoxLabel: {
    color: '#9ca3af',
    fontSize: 13,
    fontWeight: '500',
    flex: 1,
  },
  refreshLocationBtn: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: '#3b82f615',
    justifyContent: 'center',
    alignItems: 'center',
  },
  locationBoxCoords: {
    color: '#3b82f6',
    fontSize: 15,
    fontWeight: '600',
    fontFamily: 'monospace',
  },
  locationRow: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    gap: 8,
    marginBottom: 16,
  },
  refreshButton: {
    padding: 10,
    justifyContent: 'center',
    alignItems: 'center',
  },
  inputRow: {
    flex: 1,
    marginBottom: 0,
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
    backgroundColor: '#22c55e',
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
  stopCard: {
    backgroundColor: '#1a1a1a',
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
    borderLeftWidth: 4,
    borderLeftColor: '#3b82f6',
  },
  stopCardExpanded: {
    borderLeftColor: '#22c55e',
  },
  stopHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 12,
  },
  stopHeaderLeft: {
    flex: 1,
  },
  stopName: {
    fontSize: 18,
    fontWeight: '700',
    color: '#fff',
    marginBottom: 6,
  },
  brandBadge: {
    backgroundColor: '#3b82f6',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 6,
    alignSelf: 'flex-start',
  },
  brandBadgeText: {
    color: '#fff',
    fontSize: 12,
    fontWeight: '600',
  },
  stopQuickInfo: {
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
  stopDetails: {
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
  serviceTag: {
    backgroundColor: '#166534',
  },
  tagText: {
    color: '#d4d4d8',
    fontSize: 12,
  },
  actionButtons: {
    flexDirection: 'row',
    gap: 8,
    marginTop: 16,
  },
  actionButton: {
    flex: 1,
    backgroundColor: '#27272a',
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 12,
    borderRadius: 8,
    gap: 6,
  },
  actionButtonText: {
    color: '#fff',
    fontSize: 13,
    fontWeight: '600',
  },
});
