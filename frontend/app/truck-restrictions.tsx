import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, TextInput, ActivityIndicator, ScrollView, Alert, RefreshControl } from 'react-native';
import axios from 'axios';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import * as Location from 'expo-location';
import { API_BASE } from './apiConfig';

interface TruckRestriction {
  name: string;
  type: string;
  distance_miles: number;
  latitude: number;
  longitude: number;
  restriction: string;
  value?: string;
  details?: string;
  city?: string;
  state?: string;
}

export default function TruckRestrictionsScreen() {
  const router = useRouter();
  const [latitude, setLatitude] = useState('');
  const [longitude, setLongitude] = useState('');
  const [searchRadius, setSearchRadius] = useState('25');
  const [restrictions, setRestrictions] = useState<TruckRestriction[]>([]);
  const [loading, setLoading] = useState(false);
  const [locationLoading, setLocationLoading] = useState(false);
  const [error, setError] = useState('');
  const [expandedRestrictions, setExpandedRestrictions] = useState<Set<number>>(new Set());
  const [refreshing, setRefreshing] = useState(false);

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
      Alert.alert('Location Updated', 'Your current location has been set.');
    } catch (err: any) {
      setLocationLoading(false);
      Alert.alert('Location Error', err.message || 'Unable to get your location.');
    }
  };

  const searchRestrictions = async () => {
    setLoading(true);
    setRestrictions([]);
    setError('');
    try {
      const resp = await axios.post(`${API_BASE}/api/pro/truck-restrictions/search`, {
        latitude: parseFloat(latitude),
        longitude: parseFloat(longitude),
        radius_miles: parseInt(searchRadius, 10),
      }, {
        timeout: 25000,
      });
      setRestrictions(resp.data.restrictions || []);
      if (resp.data.restrictions && resp.data.restrictions.length === 0) {
        setError('No truck restrictions found in this area. Try increasing the search radius.');
      }
    } catch (err: any) {
      console.error('Truck restrictions search error:', err);
      setError(err?.response?.data?.detail || 'Failed to find truck restrictions. Tap to retry.');
    } finally {
      setLoading(false);
    }
  };

  const onRefresh = async () => {
    setRefreshing(true);
    await searchRestrictions();
    setRefreshing(false);
  };

  const toggleRestriction = (index: number) => {
    setExpandedRestrictions(prev => {
      const newSet = new Set(prev);
      if (newSet.has(index)) {
        newSet.delete(index);
      } else {
        newSet.add(index);
      }
      return newSet;
    });
  };

  const getRestrictionIcon = (type: string) => {
    switch (type) {
      case 'weight': return 'scale-outline';
      case 'height': return 'resize-outline';
      case 'width': return 'contract-outline';
      case 'hazmat': return 'nuclear-outline';
      case 'truck_ban': return 'ban-outline';
      case 'tunnel': return 'locate-outline';
      default: return 'alert-circle-outline';
    }
  };

  const getRestrictionColor = (type: string) => {
    switch (type) {
      case 'weight': return '#f59e0b';
      case 'height': return '#ef4444';
      case 'width': return '#3b82f6';
      case 'hazmat': return '#ec4899';
      case 'truck_ban': return '#dc2626';
      case 'tunnel': return '#8b5cf6';
      default: return '#6b7280';
    }
  };

  const getRestrictionLabel = (type: string) => {
    switch (type) {
      case 'weight': return 'Weight Limit';
      case 'height': return 'Height Limit';
      case 'width': return 'Width Limit';
      case 'hazmat': return 'Hazmat Restricted';
      case 'truck_ban': return 'No Trucks';
      case 'tunnel': return 'Tunnel Restriction';
      default: return 'Restriction';
    }
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ScrollView 
        contentContainerStyle={styles.scrollContent}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#ec4899" />
        }
      >
        <View style={styles.header}>
          <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
            <Ionicons name="arrow-back" size={24} color="#fff" />
          </TouchableOpacity>
          <Text style={styles.title}>🚫 Truck Restrictions</Text>
          <Text style={styles.subtitle}>Weight, height, hazmat, and route restrictions</Text>
        </View>

        <View style={styles.content}>
          <View style={styles.searchCard}>
            <Text style={styles.searchTitle}>Search Location</Text>
            
            <View style={styles.inputGroup}>
              <Text style={styles.label}>Latitude</Text>
              <TextInput
                style={styles.input}
                value={latitude}
                onChangeText={setLatitude}
                placeholder="39.7392"
                placeholderTextColor="#6b7280"
                keyboardType="decimal-pad"
              />
            </View>

            <View style={styles.inputGroup}>
              <Text style={styles.label}>Longitude</Text>
              <TextInput
                style={styles.input}
                value={longitude}
                onChangeText={setLongitude}
                placeholder="-104.9903"
                placeholderTextColor="#6b7280"
                keyboardType="decimal-pad"
              />
            </View>

            <View style={styles.inputGroup}>
              <Text style={styles.label}>Search Radius (miles)</Text>
              <TextInput
                style={styles.input}
                value={searchRadius}
                onChangeText={setSearchRadius}
                placeholder="25"
                placeholderTextColor="#6b7280"
                keyboardType="number-pad"
              />
            </View>

            <TouchableOpacity
              style={styles.locationButton}
              onPress={useCurrentLocation}
              disabled={locationLoading}
            >
              {locationLoading ? (
                <ActivityIndicator color="#fff" />
              ) : (
                <>
                  <Ionicons name="locate" size={18} color="#fff" />
                  <Text style={styles.locationButtonText}>Use Current Location</Text>
                </>
              )}
            </TouchableOpacity>

            <TouchableOpacity
              style={styles.searchButton}
              onPress={searchRestrictions}
              disabled={loading || !latitude || !longitude}
            >
              {loading ? (
                <ActivityIndicator color="#fff" />
              ) : (
                <>
                  <Ionicons name="search" size={18} color="#fff" />
                  <Text style={styles.searchButtonText}>Search Restrictions</Text>
                </>
              )}
            </TouchableOpacity>
          </View>

          {error && !loading && (
            <TouchableOpacity style={styles.errorCard} onPress={searchRestrictions}>
              <Ionicons name="alert-circle" size={20} color="#f59e0b" />
              <Text style={styles.errorText}>{error}</Text>
            </TouchableOpacity>
          )}

          {restrictions.length > 0 && (
            <View style={styles.resultsHeader}>
              <Text style={styles.resultsCount}>
                {restrictions.length} Restriction{restrictions.length !== 1 ? 's' : ''} Found
              </Text>
            </View>
          )}

          {restrictions.map((restriction, index) => {
            const isExpanded = expandedRestrictions.has(index);
            const color = getRestrictionColor(restriction.type);

            return (
              <TouchableOpacity
                key={index}
                style={[styles.restrictionCard, { borderLeftColor: color }]}
                onPress={() => toggleRestriction(index)}
                activeOpacity={0.7}
              >
                <View style={styles.restrictionHeader}>
                  <View style={[styles.iconBadge, { backgroundColor: color }]}>
                    <Ionicons name={getRestrictionIcon(restriction.type) as any} size={20} color="#fff" />
                  </View>
                  <View style={styles.restrictionInfo}>
                    <Text style={styles.restrictionName} numberOfLines={1}>
                      {restriction.name || 'Unnamed Road'}
                    </Text>
                    {(restriction.city || restriction.state) && (
                      <Text style={styles.restrictionLocation} numberOfLines={1}>
                        📍 {restriction.city}{restriction.city && restriction.state ? ', ' : ''}{restriction.state}
                      </Text>
                    )}
                    <View style={styles.restrictionMetaRow}>
                      <View style={[styles.typeBadge, { backgroundColor: `${color}20`, borderColor: color }]}>
                        <Text style={[styles.typeText, { color }]}>
                          {getRestrictionLabel(restriction.type)}
                        </Text>
                      </View>
                      <Text style={styles.distance}>{restriction.distance_miles} mi</Text>
                    </View>
                  </View>
                  <Ionicons 
                    name={isExpanded ? 'chevron-up' : 'chevron-down'} 
                    size={20} 
                    color="#71717a" 
                  />
                </View>

                {isExpanded && (
                  <View style={styles.restrictionDetails}>
                    <View style={styles.detailRow}>
                      <Ionicons name="information-circle" size={16} color="#a1a1aa" />
                      <Text style={styles.detailLabel}>Restriction:</Text>
                      <Text style={styles.detailValue}>{restriction.restriction}</Text>
                    </View>
                    {restriction.value && (
                      <View style={styles.detailRow}>
                        <Ionicons name="swap-horizontal" size={16} color="#a1a1aa" />
                        <Text style={styles.detailLabel}>Limit:</Text>
                        <Text style={styles.detailValue}>{restriction.value}</Text>
                      </View>
                    )}
                    {restriction.details && (
                      <View style={styles.detailRow}>
                        <Ionicons name="document-text" size={16} color="#a1a1aa" />
                        <Text style={styles.detailLabel}>Details:</Text>
                        <Text style={styles.detailValue}>{restriction.details}</Text>
                      </View>
                    )}
                  </View>
                )}
              </TouchableOpacity>
            );
          })}
        </View>
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
  content: {
    padding: 20,
  },
  searchCard: {
    backgroundColor: '#1a1a1a',
    borderRadius: 12,
    padding: 20,
    marginBottom: 20,
  },
  searchTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: '#fff',
    marginBottom: 16,
  },
  inputGroup: {
    marginBottom: 16,
  },
  label: {
    fontSize: 12,
    fontWeight: '600',
    color: '#a1a1aa',
    marginBottom: 6,
  },
  input: {
    backgroundColor: '#27272a',
    borderRadius: 8,
    padding: 12,
    color: '#fff',
    fontSize: 15,
  },
  locationButton: {
    backgroundColor: '#3b82f6',
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 12,
    borderRadius: 8,
    gap: 8,
    marginBottom: 12,
  },
  locationButtonText: {
    color: '#fff',
    fontSize: 14,
    fontWeight: '600',
  },
  searchButton: {
    backgroundColor: '#ec4899',
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 14,
    borderRadius: 8,
    gap: 8,
  },
  searchButtonText: {
    color: '#fff',
    fontSize: 15,
    fontWeight: '700',
  },
  errorCard: {
    backgroundColor: '#422006',
    borderRadius: 8,
    padding: 12,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    marginBottom: 20,
  },
  errorText: {
    color: '#f59e0b',
    fontSize: 13,
    flex: 1,
  },
  resultsHeader: {
    marginBottom: 16,
  },
  resultsCount: {
    fontSize: 14,
    fontWeight: '600',
    color: '#a1a1aa',
  },
  restrictionCard: {
    backgroundColor: '#1a1a1a',
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
    borderLeftWidth: 4,
  },
  restrictionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  iconBadge: {
    width: 40,
    height: 40,
    borderRadius: 20,
    justifyContent: 'center',
    alignItems: 'center',
  },
  restrictionInfo: {
    flex: 1,
  },
  restrictionName: {
    fontSize: 15,
    fontWeight: '700',
    color: '#fff',
    marginBottom: 4,
  },
  restrictionLocation: {
    fontSize: 12,
    color: '#a1a1aa',
    marginBottom: 6,
  },
  restrictionMetaRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  typeBadge: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 4,
    borderWidth: 1,
  },
  typeText: {
    fontSize: 11,
    fontWeight: '600',
  },
  distance: {
    fontSize: 12,
    color: '#71717a',
  },
  restrictionDetails: {
    marginTop: 16,
    paddingTop: 16,
    borderTopWidth: 1,
    borderTopColor: '#27272a',
    gap: 10,
  },
  detailRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 8,
  },
  detailLabel: {
    fontSize: 13,
    color: '#a1a1aa',
    fontWeight: '600',
    width: 80,
  },
  detailValue: {
    fontSize: 13,
    color: '#d4d4d8',
    flex: 1,
  },
});
