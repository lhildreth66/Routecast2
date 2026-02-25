import React, { useState } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, TextInput, ActivityIndicator, ScrollView, Alert, Linking, RefreshControl } from 'react-native';
import axios from 'axios';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { API_BASE, buildUrl } from '../lib/apiConfig';
import InfoBanner from '../lib/components/InfoBanner';
import { useLocationSearch } from '../lib/useLocationSearch';
import LocationSearchBox from '../lib/components/LocationSearchBox';

interface TruckService {
  name: string;
  service_type: string;
  distance_miles: number;
  latitude: number;
  longitude: number;
  services_offered: string[];
  brands_serviced: string[];
  phone?: string;
  website?: string;
  hours?: string;
}

export default function TruckServicesScreen() {
  const router = useRouter();

  // ── Location (manual search + explicit GPS only) ────────────────────
  const {
    lat: latitude, lon: longitude,
    locationLabel, locationLoading,
    locationQuery, suggestions, showSuggestions,
    handleLocationQueryChange, selectSuggestion,
    clearManualLocation, triggerGps, setShowSuggestions,
  } = useLocationSearch('truckServicesLoc');

  const [searchRadius, setSearchRadius] = useState('50');
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [services, setServices] = useState<TruckService[]>([]);
  const [error, setError] = useState<string>('');
  const [expandedServices, setExpandedServices] = useState(new Set<number>());



  const refreshLocation = async () => {
    await triggerGps();
  };

  const searchServices = async () => {
    setLoading(true);
    setServices([]);
    setError('');
    try {
      const resp = await axios.post(buildUrl('truck-services/search'), {
        latitude: parseFloat(latitude),
        longitude: parseFloat(longitude),
        radius_miles: parseInt(searchRadius, 10),
      });
      setServices(resp.data.services || []);
      if (resp.data.services && resp.data.services.length === 0) {
        setError('No truck services found in this area. Try increasing the search radius.');
      }
    } catch (err: any) {
      console.error('Truck services search error:', err);
      setError(err?.response?.data?.detail || 'Failed to find truck services. Tap to retry.');
    } finally {
      setLoading(false);
    }
  };

  const onRefresh = async () => {
    setRefreshing(true);
    await searchServices();
    setRefreshing(false);
  };

  const toggleServiceExpand = (index: number) => {
    const newExpanded = new Set(expandedServices);
    if (newExpanded.has(index)) {
      newExpanded.delete(index);
    } else {
      newExpanded.add(index);
    }
    setExpandedServices(newExpanded);
  };

  const openInMaps = (service: TruckService) => {
    const url = `https://www.google.com/maps/dir/?api=1&destination=${service.latitude},${service.longitude}`;
    Linking.openURL(url);
  };

  const callPhone = (phone: string) => {
    Linking.openURL(`tel:${phone}`);
  };

  const openWebsite = (url: string) => {
    Linking.openURL(url);
  };

  const getServiceIcon = (type: string) => {
    switch (type) {
      case 'repair': return 'construct';
      case 'tire': return 'disc';
      case 'wash': return 'water';
      case 'scale': return 'scale';
      default: return 'build';
    }
  };

  const getServiceColor = (type: string) => {
    switch (type) {
      case 'repair': return '#ef4444';
      case 'tire': return '#8b5cf6';
      case 'wash': return '#06b6d4';
      case 'scale': return '#22c55e';
      default: return '#6b7280';
    }
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#f59e0b" />}
      >
        <View style={styles.header}>
          <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
            <Ionicons name="arrow-back" size={24} color="#fff" />
          </TouchableOpacity>
          <Text style={styles.title}>🔧 Truck Services</Text>
          <Text style={styles.subtitle}>Repair, tires, washes, and scales</Text>
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
            accentColor="#f59e0b"
          />

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
            onPress={searchServices}
            style={[styles.searchButton, loading && styles.buttonDisabled]}
            disabled={loading}
          >
            {loading ? (
              <ActivityIndicator size="small" color="#fff" />
            ) : (
              <>
                <Ionicons name="search" size={20} color="#fff" />
                <Text style={styles.searchButtonText}>Find Services</Text>
              </>
            )}
          </TouchableOpacity>

          <InfoBanner
            message={'ℹ️ To keep subscription costs low, we use free mapping data. Some locations may show as "Store" or generic names. When you tap "Directions" and open in Google Maps, the full business name will appear at your destination.'}
            style={{ marginTop: 12, marginBottom: 8 }}
          />

          {error ? (
            <TouchableOpacity style={styles.errorBox} onPress={searchServices}>
              <Ionicons name="alert-circle" size={20} color="#ef4444" />
              <Text style={styles.errorText}>{error}</Text>
            </TouchableOpacity>
          ) : null}
        </View>

        {services.length > 0 && (
          <View style={styles.resultsContainer}>
            <Text style={styles.resultsTitle}>Found {services.length} Service{services.length !== 1 ? 's' : ''}</Text>
            
            {services.map((service, index) => {
              const isExpanded = expandedServices.has(index);
              const serviceColor = getServiceColor(service.service_type);
              
              return (
                <TouchableOpacity
                  key={index}
                  style={[styles.serviceCard, { borderLeftColor: serviceColor }]}
                  onPress={() => toggleServiceExpand(index)}
                  activeOpacity={0.8}
                >
                  <View style={styles.serviceHeader}>
                    <View style={styles.serviceHeaderLeft}>
                      <View style={styles.nameRow}>
                        <Ionicons name={getServiceIcon(service.service_type) as any} size={20} color={serviceColor} />
                        <Text style={styles.serviceName}>{service.name}</Text>
                      </View>
                      <View style={[styles.typeBadge, { backgroundColor: serviceColor }]}>
                        <Text style={styles.typeBadgeText}>{service.service_type.toUpperCase()}</Text>
                      </View>
                    </View>
                    <Ionicons name={isExpanded ? "chevron-up" : "chevron-down"} size={24} color="#9ca3af" />
                  </View>

                  <View style={styles.serviceQuickInfo}>
                    <View style={styles.quickInfoItem}>
                      <Ionicons name="navigate" size={16} color="#06b6d4" />
                      <Text style={styles.quickInfoText}>{service.distance_miles.toFixed(1)} mi</Text>
                    </View>
                  </View>

                  {isExpanded && (
                    <View style={styles.serviceDetails}>
                      {service.services_offered.length > 0 && (
                        <View style={styles.detailSection}>
                          <Text style={styles.detailLabel}>Services Offered</Text>
                          <View style={styles.tagContainer}>
                            {service.services_offered.map((offered, i) => (
                              <View key={i} style={styles.tag}>
                                <Text style={styles.tagText}>{offered}</Text>
                              </View>
                            ))}
                          </View>
                        </View>
                      )}

                      {service.hours && (
                        <View style={styles.detailSection}>
                          <Text style={styles.detailLabel}>Hours</Text>
                          <Text style={styles.detailValue}>{service.hours}</Text>
                        </View>
                      )}

                      <View style={styles.actionButtons}>
                        <TouchableOpacity style={styles.actionButton} onPress={() => openInMaps(service)}>
                          <Ionicons name="navigate" size={20} color="#fff" />
                          <Text style={styles.actionButtonText}>Directions</Text>
                        </TouchableOpacity>
                        {service.phone && (
                          <TouchableOpacity style={styles.actionButton} onPress={() => callPhone(service.phone!)}>
                            <Ionicons name="call" size={20} color="#fff" />
                            <Text style={styles.actionButtonText}>Call</Text>
                          </TouchableOpacity>
                        )}
                        {service.website && (
                          <TouchableOpacity style={styles.actionButton} onPress={() => openWebsite(service.website!)}>
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
    borderColor: '#f59e0b20',
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
    backgroundColor: '#f59e0b15',
    justifyContent: 'center',
    alignItems: 'center',
  },
  locationBoxCoords: {
    color: '#f59e0b',
    fontSize: 15,
    fontWeight: '600',
    fontFamily: 'monospace',
  },
  locationButton: {
    backgroundColor: '#f59e0b',
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
  serviceCard: {
    backgroundColor: '#1a1a1a',
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
    borderLeftWidth: 4,
  },
  serviceHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 12,
  },
  serviceHeaderLeft: {
    flex: 1,
  },
  nameRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 8,
  },
  serviceName: {
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
    color: '#fff',
    fontSize: 11,
    fontWeight: '700',
  },
  serviceQuickInfo: {
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
  serviceDetails: {
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
