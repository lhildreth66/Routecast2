import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, ActivityIndicator, ScrollView, Alert, Linking, RefreshControl } from 'react-native';
import axios from 'axios';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import * as Location from 'expo-location';
import { API_BASE } from './apiConfig';

interface RVDealership {
  name: string;
  type: string; // 'Dealership', 'Service Center', 'Parts & Accessories'
  distance_miles: number;
  latitude: number;
  longitude: number;
  description: string;
  hours: string;
  phone: string;
  services: string[];
  brands: string[];
  rating: number;
  address?: string;
  website?: string;
}

export default function RVDealershipScreen() {
  const router = useRouter();
  const [latitude, setLatitude] = useState('');
  const [longitude, setLongitude] = useState('');
  const [loading, setLoading] = useState(true);
  const [locationLoading, setLocationLoading] = useState(true);
  const [dealerships, setDealerships] = useState<RVDealership[]>([]);
  const [error, setError] = useState<string>('');
  const [expandedDealerships, setExpandedDealerships] = useState(new Set<number>());

  // Automatically get current location and search on mount
  useEffect(() => {
    (async () => {
      try {
        const { status } = await Location.requestForegroundPermissionsAsync();
        if (status === 'granted') {
          const location = await Location.getCurrentPositionAsync({});
          const lat = location.coords.latitude.toFixed(4);
          const lon = location.coords.longitude.toFixed(4);
          setLatitude(lat);
          setLongitude(lon);
          setLocationLoading(false);
          
          // Auto-search immediately
          await performSearch(parseFloat(lat), parseFloat(lon));
        } else {
          setLocationLoading(false);
          setLoading(false);
          setError('Location permission required to find nearby RV dealerships');
        }
      } catch (err) {
        setLocationLoading(false);
        setLoading(false);
        setError('Failed to get current location');
      }
    })();
  }, []);

  const performSearch = async (lat: number, lon: number) => {
    setLoading(true);
    setDealerships([]);
    setError('');
    try {
      const resp = await axios.post(`${API_BASE}/api/pro/rv-dealerships/search`, {
        latitude: lat,
        longitude: lon,
        radius_miles: 10,
        subscription_id: 'test',
      });
      setDealerships(resp.data.dealerships || []);
      if (resp.data.dealerships?.length === 0) {
        setError('No RV dealerships found within 10 miles. Try increasing your search radius.');
      }
    } catch (err: any) {
      console.error('RV dealership search error:', err);
      setError(err?.response?.data?.detail || err?.message || 'Failed to find RV dealerships');
    } finally {
      setLoading(false);
    }
  };

  const refreshLocation = async () => {
    setLocationLoading(true);
    try {
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== 'granted') {
        Alert.alert('Permission Denied', 'Location permission is required.');
        setLocationLoading(false);
        return;
      }

      const location = await Location.getCurrentPositionAsync({});
      const lat = location.coords.latitude.toFixed(4);
      const lon = location.coords.longitude.toFixed(4);
      setLatitude(lat);
      setLongitude(lon);
      setLocationLoading(false);
      
      Alert.alert('Location Updated', 'Searching for nearby RV dealerships...');
      await performSearch(parseFloat(lat), parseFloat(lon));
    } catch (err) {
      setLocationLoading(false);
      Alert.alert('Error', 'Failed to get current location');
    }
  };

  const toggleDealershipExpand = (index: number) => {
    const newExpanded = new Set(expandedDealerships);
    if (newExpanded.has(index)) {
      newExpanded.delete(index);
    } else {
      newExpanded.add(index);
    }
    setExpandedDealerships(newExpanded);
  };

  const openInMaps = (dealership: RVDealership) => {
    const url = `https://www.google.com/maps/dir/?api=1&destination=${dealership.latitude},${dealership.longitude}`;
    Linking.openURL(url);
  };

  const callPhone = (phone: string) => {
    if (phone && phone !== 'N/A') {
      Linking.openURL(`tel:${phone}`);
    }
  };

  return (
    <SafeAreaView style={styles.container}>
      <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
        <Ionicons name="arrow-back" size={24} color="#fff" />
        <Text style={styles.backText}>Back</Text>
      </TouchableOpacity>

      <ScrollView style={styles.content}>
        <View style={styles.card}>
          <Text style={styles.title}>🚐 Nearest RV Dealerships</Text>
          <Text style={styles.subtitle}>Find RV dealerships, service centers, and parts within 10 miles</Text>
          <Text style={styles.infoNote}>💡 Tip: The business name will typically appear in Google Maps when you navigate to the location.</Text>

          <TouchableOpacity 
            onPress={refreshLocation} 
            style={styles.locationButton}
            disabled={locationLoading}
          >
            {locationLoading ? (
              <ActivityIndicator size="small" color="#ec4899" />
            ) : (
              <>
                <Ionicons name="refresh" size={18} color="#ec4899" />
                <Text style={styles.locationButtonText}>Refresh Location & Search</Text>
              </>
            )}
          </TouchableOpacity>

          {error && !loading ? (
            <View style={styles.errorBox}>
              <Ionicons name="alert-circle" size={20} color="#ef4444" />
              <Text style={styles.errorText}>{error}</Text>
            </View>
          ) : null}
        </View>

        {/* Loading State */}
        {loading && (
          <View style={styles.loadingContainer}>
            <ActivityIndicator size="large" color="#ec4899" />
            <Text style={styles.loadingText}>Searching for RV dealerships...</Text>
          </View>
        )}

        {/* Results */}
        {!loading && dealerships.length > 0 && (
          <View style={styles.resultsContainer}>
            <Text style={styles.resultsTitle}>Found {dealerships.length} RV Dealership{dealerships.length !== 1 ? 's' : ''}</Text>
            
            {dealerships.map((dealership, index) => {
              const isExpanded = expandedDealerships.has(index);
              
              return (
                <TouchableOpacity
                  key={index}
                  style={[styles.dealershipCard, isExpanded && styles.dealershipCardExpanded]}
                  onPress={() => toggleDealershipExpand(index)}
                  activeOpacity={0.8}
                >
                  <View style={styles.dealershipHeader}>
                    <View style={styles.dealershipIcon}>
                      <Ionicons name="car-sport" size={24} color="#ec4899" />
                    </View>
                    <View style={styles.dealershipHeaderMiddle}>
                      <Text style={styles.dealershipName}>{dealership.name}</Text>
                      <View style={styles.dealershipTypeRow}>
                        <View style={styles.dealershipTypeBadge}>
                          <Text style={styles.dealershipTypeBadgeText}>{dealership.type}</Text>
                        </View>
                      </View>
                    </View>
                    <Ionicons 
                      name={isExpanded ? "chevron-up" : "chevron-down"} 
                      size={24} 
                      color="#9ca3af" 
                    />
                  </View>

                  <View style={styles.dealershipQuickInfo}>
                    <View style={styles.quickInfoItem}>
                      <Ionicons name="navigate" size={16} color="#ec4899" />
                      <Text style={styles.quickInfoText}>{dealership.distance_miles.toFixed(1)} mi</Text>
                    </View>
                    {dealership.phone !== 'N/A' && (
                      <TouchableOpacity 
                        style={styles.quickInfoItem}
                        onPress={() => callPhone(dealership.phone)}
                      >
                        <Ionicons name="call" size={16} color="#06b6d4" />
                        <Text style={[styles.quickInfoText, { color: '#06b6d4' }]}>Call</Text>
                      </TouchableOpacity>
                    )}
                    <View style={styles.quickInfoItem}>
                      <Ionicons name="star" size={16} color="#eab308" />
                      <Text style={styles.quickInfoText}>{dealership.rating.toFixed(1)}</Text>
                    </View>
                  </View>

                  {isExpanded && (
                    <View style={styles.dealershipDetails}>
                      <Text style={styles.dealershipDescription}>{dealership.description}</Text>
                      
                      <View style={styles.detailSection}>
                        <Text style={styles.detailLabel}>📍 Coordinates:</Text>
                        <Text style={styles.detailValue}>{dealership.latitude.toFixed(4)}, {dealership.longitude.toFixed(4)}</Text>
                      </View>

                      <View style={styles.detailSection}>
                        <Text style={styles.detailLabel}>🕐 Hours:</Text>
                        <Text style={styles.detailValue}>{dealership.hours}</Text>
                      </View>

                      {dealership.address && (
                        <View style={styles.detailSection}>
                          <Text style={styles.detailLabel}>📍 Address:</Text>
                          <Text style={styles.detailValue}>{dealership.address}</Text>
                        </View>
                      )}

                      {dealership.phone !== 'N/A' && (
                        <View style={styles.detailSection}>
                          <Text style={styles.detailLabel}>📞 Phone:</Text>
                          <TouchableOpacity onPress={() => callPhone(dealership.phone)}>
                            <Text style={[styles.detailValue, { color: '#06b6d4' }]}>{dealership.phone}</Text>
                          </TouchableOpacity>
                        </View>
                      )}

                      {dealership.website && (
                        <View style={styles.detailSection}>
                          <Text style={styles.detailLabel}>🌐 Website:</Text>
                          <TouchableOpacity onPress={() => Linking.openURL(dealership.website!)}>
                            <Text style={[styles.detailValue, { color: '#06b6d4', textDecorationLine: 'underline' }]}>
                              {dealership.website}
                            </Text>
                          </TouchableOpacity>
                        </View>
                      )}

                      {dealership.brands.length > 0 && (
                        <View style={styles.detailSection}>
                          <Text style={styles.detailLabel}>🏷️ Brands:</Text>
                          <View style={styles.brandsList}>
                            {dealership.brands.map((brand, i) => (
                              <View key={i} style={styles.brandChip}>
                                <Text style={styles.brandText}>{brand}</Text>
                              </View>
                            ))}
                          </View>
                        </View>
                      )}

                      {dealership.services.length > 0 && (
                        <View style={styles.detailSection}>
                          <Text style={styles.detailLabel}>🔧 Services:</Text>
                          <View style={styles.servicesList}>
                            {dealership.services.map((service, i) => (
                              <View key={i} style={styles.serviceItem}>
                                <Ionicons name="checkmark-circle" size={14} color="#22c55e" />
                                <Text style={styles.serviceText}>{service}</Text>
                              </View>
                            ))}
                          </View>
                        </View>
                      )}

                      <View style={styles.infoNote}>
                        <Ionicons name="information-circle-outline" size={14} color="#9ca3af" />
                        <Text style={styles.infoNoteText}>The dealership name and details will be shown in Google Maps when you navigate to this location.</Text>
                      </View>

                      <TouchableOpacity
                        style={styles.navigateButton}
                        onPress={() => openInMaps(dealership)}
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
    gap: 8,
  },
  locationButtonText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#ec4899',
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
  loadingContainer: {
    alignItems: 'center',
    paddingVertical: 40,
  },
  loadingText: {
    fontSize: 16,
    color: '#9ca3af',
    marginTop: 16,
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
  dealershipCard: {
    backgroundColor: '#27272a',
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
    borderLeftWidth: 4,
    borderLeftColor: '#ec4899',
  },
  dealershipCardExpanded: {
    backgroundColor: '#2d2d30',
  },
  dealershipHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 8,
    gap: 12,
  },
  dealershipIcon: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: '#ec489933',
    justifyContent: 'center',
    alignItems: 'center',
  },
  dealershipHeaderMiddle: {
    flex: 1,
  },
  dealershipName: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#e5e7eb',
    marginBottom: 4,
  },
  dealershipTypeRow: {
    flexDirection: 'row',
    gap: 8,
  },
  dealershipTypeBadge: {
    backgroundColor: '#3f3f46',
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 4,
  },
  dealershipTypeBadgeText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#ec4899',
  },
  dealershipQuickInfo: {
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
  dealershipDetails: {
    marginTop: 12,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: '#3f3f46',
  },
  dealershipDescription: {
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
  brandsList: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginTop: 4,
  },
  brandChip: {
    backgroundColor: '#ec489933',
    borderRadius: 12,
    paddingHorizontal: 10,
    paddingVertical: 5,
  },
  brandText: {
    fontSize: 12,
    color: '#ec4899',
    fontWeight: '600',
  },
  servicesList: {
    marginTop: 4,
    gap: 6,
  },
  serviceItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  serviceText: {
    fontSize: 13,
    color: '#e5e7eb',
  },  infoNote: {
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
  },  navigateButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#ec4899',
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
