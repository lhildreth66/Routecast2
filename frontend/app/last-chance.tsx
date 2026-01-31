import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, TextInput, ActivityIndicator, ScrollView, Alert, Linking, RefreshControl } from 'react-native';
import axios from 'axios';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import * as Location from 'expo-location';
import { API_BASE } from './apiConfig';

interface SupplyPoint {
  name: string;
  type: string; // 'Grocery', 'Propane', 'Hardware'
  subtype: string; // 'Supermarket', 'Gas Station', 'Hardware Store', etc.
  distance_miles: number;
  latitude: number;
  longitude: number;
  description: string;
  hours: string;
  phone: string;
  amenities: string[];
  rating: number;
  address?: string;
  website?: string;
}

export default function LastChanceScreen() {
  const router = useRouter();
  const [latitude, setLatitude] = useState('34.05');
  const [longitude, setLongitude] = useState('-111.03');
  const [searchRadius, setSearchRadius] = useState('75'); // miles - large radius for "last chance"
  const [loading, setLoading] = useState(false);
  const [locationLoading, setLocationLoading] = useState(true);
  const [supplies, setSupplies] = useState<SupplyPoint[]>([]);
  const [error, setError] = useState<string>('');
  const [expandedSupplies, setExpandedSupplies] = useState(new Set<number>());
  const [filterType, setFilterType] = useState<'all' | 'grocery' | 'propane' | 'hardware'>('all');

  // Automatically get current location on mount
  useEffect(() => {
    (async () => {
      try {
        const { status} = await Location.requestForegroundPermissionsAsync();
        if (status === 'granted') {
          const location = await Location.getCurrentPositionAsync({});
          setLatitude(location.coords.latitude.toFixed(4));
          setLongitude(location.coords.longitude.toFixed(4));
        }
      } catch (err) {
        console.log('Could not get current location, using defaults');
      } finally {
        setLocationLoading(false);
      }
    })();
  }, []);

  const useCurrentLocation = async () => {
    try {
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== 'granted') {
        Alert.alert('Permission Denied', 'Location permission is required to use current location.');
        return;
      }

      const location = await Location.getCurrentPositionAsync({});
      setLatitude(location.coords.latitude.toFixed(4));
      setLongitude(location.coords.longitude.toFixed(4));
      Alert.alert('Location Updated', `Using current position: ${location.coords.latitude.toFixed(4)}, ${location.coords.longitude.toFixed(4)}`);
    } catch (err) {
      Alert.alert('Error', 'Failed to get current location');
    }
  };

  const searchSupplies = async () => {
    setLoading(true);
    setSupplies([]);
    setError('');
    try {
      const resp = await axios.post(`${API_BASE}/api/pro/last-chance/search`, {
        latitude: parseFloat(latitude),
        longitude: parseFloat(longitude),
        radius_miles: parseInt(searchRadius, 10),
      });
      setSupplies(resp.data.supplies || []);
    } catch (err: any) {
      console.error('Last chance search error:', err);
      setError(err?.response?.data?.detail || err?.message || 'Failed to find supply points');
    } finally {
      setLoading(false);
    }
  };

  const toggleSupplyExpand = (index: number) => {
    const newExpanded = new Set(expandedSupplies);
    if (newExpanded.has(index)) {
      newExpanded.delete(index);
    } else {
      newExpanded.add(index);
    }
    setExpandedSupplies(newExpanded);
  };

  const openInMaps = (supply: SupplyPoint) => {
    const url = `https://www.google.com/maps/dir/?api=1&destination=${supply.latitude},${supply.longitude}`;
    Linking.openURL(url);
  };

  const callPhone = (phone: string) => {
    if (phone && phone !== 'N/A') {
      Linking.openURL(`tel:${phone}`);
    }
  };

  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'Grocery': return 'cart';
      case 'Propane': return 'flame';
      case 'Hardware': return 'hammer';
      default: return 'storefront';
    }
  };

  const getTypeColor = (type: string) => {
    switch (type) {
      case 'Grocery': return '#22c55e';
      case 'Propane': return '#f97316';
      case 'Hardware': return '#3b82f6';
      default: return '#9ca3af';
    }
  };

  const filteredSupplies = supplies.filter(s => 
    filterType === 'all' || s.type.toLowerCase() === filterType
  );

  return (
    <SafeAreaView style={styles.container}>
      <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
        <Ionicons name="arrow-back" size={24} color="#fff" />
        <Text style={styles.backText}>Back</Text>
      </TouchableOpacity>

      <ScrollView style={styles.content}>
        <View style={styles.card}>
          <Text style={styles.title}>🏪 Last Chance Supplies</Text>
          <Text style={styles.subtitle}>Find grocery, propane, and hardware stores before going remote</Text>
          <Text style={styles.infoNote}>💡 TIP: If a result shows "Name" or is missing a title, don't worry—tap Navigate and Google Maps will display the business name in directions. We use free map data to keep costs (and pricing) low.</Text>

          {locationLoading && (
            <View style={styles.loadingLocationBox}>
              <ActivityIndicator size="small" color="#f59e0b" />
              <Text style={styles.loadingLocationText}>Determining your current location...</Text>
            </View>
          )}

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
              placeholder="e.g., 75"
              placeholderTextColor="#9ca3af"
            />
          </View>

          <TouchableOpacity
            onPress={searchSupplies}
            style={[styles.calculateButton, loading && styles.buttonDisabled]}
            disabled={loading}
          >
            {loading ? (
              <ActivityIndicator size="small" color="#fff" />
            ) : (
              <>
                <Ionicons name="search" size={20} color="#fff" />
                <Text style={styles.calculateButtonText}>Find Supply Points</Text>
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

        {/* Filter Buttons */}
        {supplies.length > 0 && (
          <View style={styles.filterContainer}>
            <TouchableOpacity
              style={[styles.filterButton, filterType === 'all' && styles.filterButtonActive]}
              onPress={() => setFilterType('all')}
            >
              <Text style={[styles.filterButtonText, filterType === 'all' && styles.filterButtonTextActive]}>
                All ({supplies.length})
              </Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.filterButton, filterType === 'grocery' && styles.filterButtonActive]}
              onPress={() => setFilterType('grocery')}
            >
              <Ionicons name="cart" size={16} color={filterType === 'grocery' ? '#fff' : '#22c55e'} />
              <Text style={[styles.filterButtonText, filterType === 'grocery' && styles.filterButtonTextActive]}>
                Grocery ({supplies.filter(s => s.type === 'Grocery').length})
              </Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.filterButton, filterType === 'propane' && styles.filterButtonActive]}
              onPress={() => setFilterType('propane')}
            >
              <Ionicons name="flame" size={16} color={filterType === 'propane' ? '#fff' : '#f97316'} />
              <Text style={[styles.filterButtonText, filterType === 'propane' && styles.filterButtonTextActive]}>
                Propane ({supplies.filter(s => s.type === 'Propane').length})
              </Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.filterButton, filterType === 'hardware' && styles.filterButtonActive]}
              onPress={() => setFilterType('hardware')}
            >
              <Ionicons name="hammer" size={16} color={filterType === 'hardware' ? '#fff' : '#3b82f6'} />
              <Text style={[styles.filterButtonText, filterType === 'hardware' && styles.filterButtonTextActive]}>
                Hardware ({supplies.filter(s => s.type === 'Hardware').length})
              </Text>
            </TouchableOpacity>
          </View>
        )}

        {/* Results */}
        {filteredSupplies.length > 0 && (
          <View style={styles.resultsContainer}>
            <Text style={styles.resultsTitle}>
              {filterType === 'all' ? 'All Supply Points' : `${filterType.charAt(0).toUpperCase() + filterType.slice(1)} Stores`}
            </Text>
            
            {filteredSupplies.map((supply, index) => {
              const isExpanded = expandedSupplies.has(index);
              
              return (
                <TouchableOpacity
                  key={index}
                  style={[styles.supplyCard, isExpanded && styles.supplyCardExpanded]}
                  onPress={() => toggleSupplyExpand(index)}
                  activeOpacity={0.8}
                >
                  <View style={styles.supplyHeader}>
                    <View style={[styles.supplyIcon, { backgroundColor: getTypeColor(supply.type) }]}>
                      <Ionicons name={getTypeIcon(supply.type) as any} size={24} color="#fff" />
                    </View>
                    <View style={styles.supplyHeaderMiddle}>
                      <Text style={styles.supplyName}>{supply.name}</Text>
                      <View style={styles.supplyTypeRow}>
                        <View style={[styles.supplyTypeBadge, { backgroundColor: getTypeColor(supply.type) + '33' }]}>
                          <Text style={[styles.supplyTypeBadgeText, { color: getTypeColor(supply.type) }]}>
                            {supply.subtype}
                          </Text>
                        </View>
                      </View>
                    </View>
                    <Ionicons 
                      name={isExpanded ? "chevron-up" : "chevron-down"} 
                      size={24} 
                      color="#9ca3af" 
                    />
                  </View>

                  <View style={styles.supplyQuickInfo}>
                    <View style={styles.quickInfoItem}>
                      <Ionicons name="navigate" size={16} color="#f59e0b" />
                      <Text style={styles.quickInfoText}>{supply.distance_miles.toFixed(1)} mi</Text>
                    </View>
                    {supply.phone !== 'N/A' && (
                      <TouchableOpacity 
                        style={styles.quickInfoItem}
                        onPress={() => callPhone(supply.phone)}
                      >
                        <Ionicons name="call" size={16} color="#06b6d4" />
                        <Text style={[styles.quickInfoText, { color: '#06b6d4' }]}>Call</Text>
                      </TouchableOpacity>
                    )}
                    <View style={styles.quickInfoItem}>
                      <Ionicons name="star" size={16} color="#eab308" />
                      <Text style={styles.quickInfoText}>{supply.rating.toFixed(1)}</Text>
                    </View>
                  </View>

                  {isExpanded && (
                    <View style={styles.supplyDetails}>
                      <Text style={styles.supplyDescription}>{supply.description}</Text>
                      
                      <View style={styles.detailSection}>
                        <Text style={styles.detailLabel}>📍 Coordinates:</Text>
                        <Text style={styles.detailValue}>{supply.latitude.toFixed(4)}, {supply.longitude.toFixed(4)}</Text>
                      </View>

                      <View style={styles.detailSection}>
                        <Text style={styles.detailLabel}>🕐 Hours:</Text>
                        <Text style={styles.detailValue}>{supply.hours}</Text>
                      </View>

                      {supply.address && (
                        <View style={styles.detailSection}>
                          <Text style={styles.detailLabel}>📍 Address:</Text>
                          <Text style={styles.detailValue}>{supply.address}</Text>
                        </View>
                      )}

                      {supply.phone !== 'N/A' && (
                        <View style={styles.detailSection}>
                          <Text style={styles.detailLabel}>📞 Phone:</Text>
                          <TouchableOpacity onPress={() => callPhone(supply.phone)}>
                            <Text style={[styles.detailValue, { color: '#06b6d4' }]}>{supply.phone}</Text>
                          </TouchableOpacity>
                        </View>
                      )}

                      {supply.website && (
                        <View style={styles.detailSection}>
                          <Text style={styles.detailLabel}>🌐 Website:</Text>
                          <TouchableOpacity onPress={() => Linking.openURL(supply.website!)}>
                            <Text style={[styles.detailValue, { color: '#06b6d4', textDecorationLine: 'underline' }]}>
                              {supply.website}
                            </Text>
                          </TouchableOpacity>
                        </View>
                      )}

                      {supply.amenities.length > 0 && (
                        <View style={styles.detailSection}>
                          <Text style={styles.detailLabel}>✨ Services:</Text>
                          <View style={styles.amenitiesList}>
                            {supply.amenities.map((amenity, i) => (
                              <View key={i} style={styles.amenityChip}>
                                <Text style={styles.amenityText}>{amenity}</Text>
                              </View>
                            ))}
                          </View>
                        </View>
                      )}

                      <View style={styles.infoNote}>
                        <Ionicons name="information-circle-outline" size={14} color="#9ca3af" />
                        <Text style={styles.infoNoteText}>The business name and details will be shown in Google Maps when you navigate to this location.</Text>
                      </View>

                      <TouchableOpacity
                        style={styles.navigateButton}
                        onPress={() => openInMaps(supply)}
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

        {supplies.length === 0 && !loading && !error && (
          <View style={styles.emptyState}>
            <Ionicons name="search" size={64} color="#3f3f46" />
            <Text style={styles.emptyStateTitle}>Ready to Search</Text>
            <Text style={styles.emptyStateText}>Enter your location and search radius, then tap "Find Supply Points"</Text>
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
    color: '#f59e0b',
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
    backgroundColor: '#f59e0b',
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
  filterContainer: {
    flexDirection: 'row',
    gap: 8,
    marginBottom: 16,
    flexWrap: 'wrap',
  },
  filterButton: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#27272a',
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 8,
    gap: 6,
  },
  filterButtonActive: {
    backgroundColor: '#f59e0b',
  },
  filterButtonText: {
    fontSize: 13,
    color: '#9ca3af',
    fontWeight: '600',
  },
  filterButtonTextActive: {
    color: '#fff',
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
  supplyCard: {
    backgroundColor: '#27272a',
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
  },
  supplyCardExpanded: {
    backgroundColor: '#2d2d30',
  },
  supplyHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 8,
    gap: 12,
  },
  supplyIcon: {
    width: 48,
    height: 48,
    borderRadius: 24,
    justifyContent: 'center',
    alignItems: 'center',
  },
  supplyHeaderMiddle: {
    flex: 1,
  },
  supplyName: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#e5e7eb',
    marginBottom: 4,
  },
  supplyTypeRow: {
    flexDirection: 'row',
    gap: 8,
  },
  supplyTypeBadge: {
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 4,
  },
  supplyTypeBadgeText: {
    fontSize: 12,
    fontWeight: '600',
  },
  supplyQuickInfo: {
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
  supplyDetails: {
    marginTop: 12,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: '#3f3f46',
  },
  supplyDescription: {
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
    backgroundColor: '#f59e0b',
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
  emptyState: {
    alignItems: 'center',
    paddingVertical: 60,
  },
  emptyStateTitle: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#9ca3af',
    marginTop: 16,
    marginBottom: 8,
  },
  emptyStateText: {
    fontSize: 14,
    color: '#71717a',
    textAlign: 'center',
    paddingHorizontal: 40,
  },
});
