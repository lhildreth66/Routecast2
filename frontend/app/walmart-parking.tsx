import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, TextInput, ActivityIndicator, ScrollView, Alert, Linking, RefreshControl } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import * as Location from 'expo-location';
import axios from 'axios';
import { buildUrl } from '../lib/apiConfig';
import InfoBanner from '../lib/components/InfoBanner';

interface OvernightSpot {
  name: string;
  category: string;
  distance_miles: number;
  latitude: number;
  longitude: number;
  address?: string;
  phone?: string;
  website?: string;
  hours?: string;
  notes?: string;
}

export default function WalmartParkingScreen() {
  const router = useRouter();
  const [latitude, setLatitude] = useState('34.05');
  const [longitude, setLongitude] = useState('-111.03');
  const [searchRadius, setSearchRadius] = useState('75');
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [locationLoading, setLocationLoading] = useState(true);
  const [spots, setSpots] = useState<OvernightSpot[]>([]);
  const [error, setError] = useState('');

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
      } finally {
        setLocationLoading(false);
      }
    })();
  }, []);

  const useCurrentLocation = async () => {
    setLocationLoading(true);
    try {
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== 'granted') {
        Alert.alert('Location Permission Required', 'Please enable location permissions in your device settings to use this feature.', [{ text: 'OK' }]);
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
      Alert.alert('Location Error', err?.message || 'Unable to get your location. Make sure GPS is enabled and you have a clear view of the sky.', [{ text: 'OK' }]);
    }
  };

  const searchWalmart = async () => {
    setLoading(true);
    setSpots([]);
    setError('');
    try {
      const resp = await axios.post(buildUrl('walmart-parking/search'), {
        latitude: parseFloat(latitude),
        longitude: parseFloat(longitude),
        radius_miles: parseInt(searchRadius, 10),
      });
      setSpots(resp.data.spots || []);
      if (!resp.data.spots || resp.data.spots.length === 0) {
        setError('No Walmart stores with overnight parking found nearby. Try increasing the search radius.');
      }
    } catch (err: any) {
      console.error('Walmart parking search error:', err);
      setError(err?.response?.data?.detail || err?.message || 'Failed to find Walmart overnight parking. Tap to retry.');
    } finally {
      setLoading(false);
    }
  };

  const onRefresh = async () => {
    setRefreshing(true);
    await searchWalmart();
    setRefreshing(false);
  };

  const openInMaps = (spot: OvernightSpot) => {
    const url = `https://www.google.com/maps/dir/?api=1&destination=${spot.latitude},${spot.longitude}`;
    Linking.openURL(url);
  };

  return (
    <SafeAreaView style={styles.container}>
      <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
        <Ionicons name="arrow-back" size={24} color="#fff" />
        <Text style={styles.backText}>Back</Text>
      </TouchableOpacity>

      <ScrollView style={styles.content} refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#22c55e" colors={["#22c55e"]} />
      }>
        <View style={styles.card}>
          <Text style={styles.title}>🛒 Walmart Overnight Parking</Text>
          <Text style={styles.subtitle}>Free overnight RV stays welcome</Text>

          <View style={styles.locationBox}>
            <View style={styles.locationHeader}>
              <Ionicons name="location" size={18} color="#22c55e" />
              <Text style={styles.locationLabel}>Your Location</Text>
              <TouchableOpacity onPress={useCurrentLocation} style={styles.refreshLocationBtn} disabled={locationLoading}>
                {locationLoading ? <ActivityIndicator size="small" color="#22c55e" /> : <Ionicons name="refresh" size={18} color="#22c55e" />}
              </TouchableOpacity>
            </View>
            <Text style={styles.locationCoords}>{locationLoading ? 'Detecting...' : `${latitude}, ${longitude}`}</Text>
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

          <TouchableOpacity onPress={searchWalmart} style={[styles.calculateButton, loading && styles.buttonDisabled]} disabled={loading}>
            {loading ? (
              <ActivityIndicator size="small" color="#fff" />
            ) : (
              <>
                <Ionicons name="search" size={20} color="#fff" />
                <Text style={styles.calculateButtonText}>Find Walmart Overnight</Text>
              </>
            )}
          </TouchableOpacity>

          <InfoBanner
            message={'ℹ️ To keep subscription costs low, we use free mapping data. Some locations may show as "Store" or generic names. When you tap "Directions" and open in Google Maps, the full business name will appear at your destination.'}
            style={{ marginTop: 12, marginBottom: 8 }}
          />

          {error ? (
            <TouchableOpacity style={styles.errorBox} onPress={searchWalmart} activeOpacity={0.7}>
              <Ionicons name="alert-circle" size={20} color="#ef4444" />
              <Text style={styles.errorText}>{error}</Text>
              <Text style={styles.retryText}>Tap to retry</Text>
            </TouchableOpacity>
          ) : null}
        </View>

        {spots.length > 0 && (
          <View style={styles.resultsContainer}>
            <Text style={styles.resultsTitle}>Found {spots.length} Walmart Location{spots.length !== 1 ? 's' : ''}</Text>

            {spots.map((spot, index) => (
              <View key={`${spot.name}-${spot.latitude}-${spot.longitude}-${index}`} style={styles.spotCard}>
                <View style={styles.spotHeader}>
                  <View style={styles.spotHeaderLeft}>
                    <Text style={styles.spotName}>{spot.name}</Text>
                    <View style={styles.spotTypeRow}>
                      <View style={styles.spotTypeBadge}>
                        <Text style={styles.spotTypeBadgeText}>{spot.category}</Text>
                      </View>
                    </View>
                  </View>
                  <Ionicons name="car" size={22} color="#22c55e" />
                </View>

                <View style={styles.spotQuickInfo}>
                  <View style={styles.quickInfoItem}>
                    <Ionicons name="map" size={16} color="#22c55e" />
                    <Text style={styles.quickInfoText}>{spot.distance_miles.toFixed(1)} mi</Text>
                  </View>
                  {spot.address ? (
                    <View style={styles.quickInfoItem}>
                      <Ionicons name="location" size={16} color="#9ca3af" />
                      <Text style={styles.quickInfoText} numberOfLines={1}>{spot.address}</Text>
                    </View>
                  ) : null}
                </View>

                <View style={styles.spotDetails}>
                  <Text style={styles.spotDescription}>{spot.notes || 'Free overnight RV stays welcome. Call ahead to confirm with store manager.'}</Text>
                  {spot.hours ? (
                    <View style={styles.detailSection}>
                      <Text style={styles.detailLabel}>Hours:</Text>
                      <Text style={styles.detailValue}>{spot.hours}</Text>
                    </View>
                  ) : null}
                  {spot.phone ? (
                    <View style={styles.detailSection}>
                      <Text style={styles.detailLabel}>Phone:</Text>
                      <TouchableOpacity onPress={() => Linking.openURL(`tel:${spot.phone}`)}>
                        <Text style={[styles.detailValue, styles.link]}>{spot.phone}</Text>
                      </TouchableOpacity>
                    </View>
                  ) : null}
                  {spot.website ? (
                    <View style={styles.detailSection}>
                      <Text style={styles.detailLabel}>Website:</Text>
                      <TouchableOpacity onPress={() => Linking.openURL(spot.website!)}>
                        <Text style={[styles.detailValue, styles.link]}>Open site</Text>
                      </TouchableOpacity>
                    </View>
                  ) : null}

                  <TouchableOpacity style={styles.navigateButton} onPress={() => openInMaps(spot)}>
                    <Ionicons name="navigate" size={18} color="#fff" />
                    <Text style={styles.navigateButtonText}>Directions in Google Maps</Text>
                  </TouchableOpacity>
                </View>
              </View>
            ))}
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
  },
  locationHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  locationLabel: {
    color: '#e5e7eb',
    fontSize: 14,
    fontWeight: '600',
    flex: 1,
  },
  refreshLocationBtn: {
    padding: 6,
    borderRadius: 8,
    backgroundColor: '#22c55e20',
  },
  locationCoords: {
    color: '#9ca3af',
    fontSize: 13,
    marginTop: 8,
  },
  inputRow: {
    marginTop: 12,
    marginBottom: 12,
  },
  label: {
    color: '#d1d5db',
    marginBottom: 6,
  },
  input: {
    backgroundColor: '#1f1f23',
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 10,
    color: '#fff',
    borderWidth: 1,
    borderColor: '#3f3f46',
  },
  calculateButton: {
    backgroundColor: '#22c55e',
    paddingVertical: 14,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
    flexDirection: 'row',
    gap: 8,
  },
  buttonDisabled: {
    opacity: 0.6,
  },
  calculateButtonText: {
    color: '#0f172a',
    fontSize: 16,
    fontWeight: '700',
  },
  errorBox: {
    marginTop: 12,
    backgroundColor: '#3f3f46',
    borderRadius: 10,
    padding: 12,
    borderWidth: 1,
    borderColor: '#ef4444',
    gap: 6,
  },
  errorText: {
    color: '#ef4444',
  },
  retryText: {
    color: '#eab308',
    fontSize: 12,
  },
  resultsContainer: {
    backgroundColor: '#18181b',
    paddingBottom: 32,
  },
  resultsTitle: {
    color: '#e5e7eb',
    fontSize: 18,
    fontWeight: '700',
    marginBottom: 12,
    paddingHorizontal: 4,
  },
  spotCard: {
    backgroundColor: '#1f1f23',
    borderRadius: 14,
    padding: 16,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: '#3f3f46',
  },
  spotHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  spotHeaderLeft: {
    flex: 1,
    gap: 6,
  },
  spotName: {
    color: '#fff',
    fontSize: 18,
    fontWeight: '700',
  },
  spotTypeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  spotTypeBadge: {
    backgroundColor: '#22c55e33',
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#22c55e',
  },
  spotTypeBadgeText: {
    color: '#22c55e',
    fontWeight: '700',
  },
  spotQuickInfo: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    marginTop: 8,
  },
  quickInfoItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  quickInfoText: {
    color: '#d1d5db',
  },
  spotDetails: {
    marginTop: 12,
    gap: 10,
  },
  spotDescription: {
    color: '#e5e7eb',
    lineHeight: 20,
  },
  detailSection: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  detailLabel: {
    color: '#9ca3af',
    fontWeight: '600',
  },
  detailValue: {
    color: '#e5e7eb',
    flexShrink: 1,
  },
  link: {
    color: '#22c55e',
    textDecorationLine: 'underline',
  },
  navigateButton: {
    marginTop: 8,
    backgroundColor: '#22c55e',
    borderRadius: 12,
    paddingVertical: 12,
    alignItems: 'center',
    flexDirection: 'row',
    justifyContent: 'center',
    gap: 8,
  },
  navigateButtonText: {
    color: '#0f172a',
    fontWeight: '700',
  },
});
