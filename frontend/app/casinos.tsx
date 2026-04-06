import React, { useState } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, TextInput, ActivityIndicator, ScrollView, Alert, Linking, RefreshControl } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import axios from 'axios';
import { buildUrl } from '../lib/apiConfig';
import InfoBanner from '../lib/components/InfoBanner';
import { useLocationSearch } from '../lib/useLocationSearch';
import LocationSearchBox from '../lib/components/LocationSearchBox';

interface OvernightSpot {
  name: string;
  category: string;
  label: string;
  distance_miles: number;
  latitude: number;
  longitude: number;
  address?: string;
  phone?: string;
  website?: string;
  hours?: string;
  notes?: string;
  rating?: number;
  user_ratings_total?: number;
  open_now?: boolean;
  place_id?: string;
}

function groupSpots(items: OvernightSpot[]) {
  const buckets: { [label: string]: OvernightSpot[] } = {};
  items.forEach((spot) => {
    const bucketStart = Math.max(0, Math.floor(spot.distance_miles / 10) * 10);
    const label = bucketStart === 0 ? 'Within 10 miles' : `${bucketStart}-${bucketStart + 10} miles`;
    if (!buckets[label]) buckets[label] = [];
    buckets[label].push(spot);
  });
  return Object.entries(buckets).map(([label, group]) => ({ label, items: group }));
}

export default function CasinosScreen() {
  const router = useRouter();

  // ── Location (manual search + explicit GPS only) ────────────────────
  const {
    lat: latitude, lon: longitude,
    locationLabel, locationLoading,
    locationQuery, suggestions, showSuggestions,
    handleLocationQueryChange, selectSuggestion,
    clearManualLocation, triggerGps, setShowSuggestions,
  } = useLocationSearch('casinosLoc');

  const [searchRadius, setSearchRadius] = useState('50');
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [spots, setSpots] = useState<OvernightSpot[]>([]);
  const [error, setError] = useState('');
  const [dataSource, setDataSource] = useState<string>('');
  const [overpassUnavailable, setOverpassUnavailable] = useState(false);


  const useCurrentLocation = async () => {
    await triggerGps();
  };

  const searchCasinos = async () => {
    const parsedLat = parseFloat(latitude);
    const parsedLon = parseFloat(longitude);
    if (isNaN(parsedLat) || isNaN(parsedLon)) {
      setError('Please enter a location or tap "Use My Location" before searching.');
      return;
    }

    setLoading(true);
    setSpots([]);
    setError('');
    setDataSource('');
    setOverpassUnavailable(false);
    try {
      const resp = await axios.post(buildUrl('casinos/search'), {
        latitude: parsedLat,
        longitude: parsedLon,
        radius_miles: parseInt(searchRadius, 10),
      });
      const data = resp.data || {};
      const results = (data.spots || data.results || []) as OvernightSpot[];
      setSpots(results);
      setDataSource(data.source || '');
      setOverpassUnavailable(data.source === 'overpass_unavailable');

      if (results.length === 0 && data.source === 'overpass_unavailable') {
        setError('');
      } else if (results.length === 0) {
        setError('No casinos found nearby. Try increasing the search radius.');
      }
    } catch (err: any) {
      console.error('Casino search error:', err);
      setError(err?.response?.data?.detail || err?.message || 'Failed to find casinos. Tap to retry.');
    } finally {
      setLoading(false);
    }
  };

  const onRefresh = async () => {
    setRefreshing(true);
    await searchCasinos();
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
        <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#0ea5e9" colors={["#0ea5e9"]} />
      }>
        <View style={styles.card}>
          <Text style={styles.title}>🎰 Casinos Near Me</Text>
          <Text style={styles.subtitle}>Free overnight RV parking welcome</Text>

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
            accentColor="#0ea5e9"
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

          <TouchableOpacity onPress={searchCasinos} style={[styles.calculateButton, loading && styles.buttonDisabled]} disabled={loading}>
            {loading ? (
              <ActivityIndicator size="small" color="#fff" />
            ) : (
              <>
                <Ionicons name="search" size={20} color="#fff" />
                <Text style={styles.calculateButtonText}>Find Casinos</Text>
              </>
            )}
          </TouchableOpacity>

          <InfoBanner
            message={'ℹ️ To keep subscription costs low, we use free mapping data. Some locations may show as "Store" or generic names. When you tap "Directions" and open in Google Maps, the full business name will appear at your destination.'}
            style={{ marginTop: 12, marginBottom: 8 }}
          />
          {overpassUnavailable ? (
            <InfoBanner
              message={'Overpass data is temporarily unavailable. Results may be limited—please try again in a few minutes.'}
              style={{ marginBottom: 8 }}
              testID="overpass-unavailable-banner"
            />
          ) : null}

          {error ? (
            <TouchableOpacity style={styles.errorBox} onPress={searchCasinos} activeOpacity={0.7}>
              <Ionicons name="alert-circle" size={20} color="#ef4444" />
              <Text style={styles.errorText}>{error}</Text>
              <Text style={styles.retryText}>Tap to retry</Text>
            </TouchableOpacity>
          ) : null}
        </View>

        {spots.length > 0 && (
          <View style={styles.resultsContainer}>
            <View style={styles.resultsHeaderRow}>
              <Text style={styles.resultsTitle}>Found {spots.length} Casino{spots.length !== 1 ? 's' : ''}</Text>
              {dataSource === 'google_places' && (
                <View style={styles.sourceTag}>
                  <Text style={styles.sourceTagText}>Powered by Google</Text>
                </View>
              )}
            </View>
            {groupSpots(spots).map((group) => (
              <View key={group.label} style={styles.groupSection}>
                <Text style={styles.groupLabel}>{group.label}</Text>
                {group.items.map((spot, index) => (
                  <View key={`${spot.name}-${spot.latitude}-${spot.longitude}-${index}`} style={styles.spotCard}>
                    <View style={styles.spotHeader}>
                      <View style={styles.spotHeaderLeft}>
                        <Text style={styles.spotName}>{spot.name}</Text>
                        <View style={styles.spotTypeRow}>
                          <View style={styles.spotTypeBadge}>
                            <Text style={styles.spotTypeBadgeText}>{spot.category}</Text>
                          </View>
                          <Text style={styles.distancePill}>{spot.distance_miles.toFixed(1)} mi</Text>
                          {spot.open_now === true && (
                            <View style={styles.openPill}>
                              <Text style={styles.openPillText}>OPEN</Text>
                            </View>
                          )}
                          {spot.open_now === false && (
                            <View style={styles.closedPill}>
                              <Text style={styles.closedPillText}>CLOSED</Text>
                            </View>
                          )}
                        </View>
                        {spot.rating != null && (
                          <View style={styles.ratingRow}>
                            <Ionicons name="star" size={13} color="#eab308" />
                            <Text style={styles.ratingText}>
                              {spot.rating.toFixed(1)}
                              {spot.user_ratings_total != null ? ` (${spot.user_ratings_total.toLocaleString()})` : ''}
                            </Text>
                          </View>
                        )}
                      </View>
                      <TouchableOpacity onPress={() => openInMaps(spot)}>
                        <Ionicons name="navigate" size={22} color="#0ea5e9" />
                      </TouchableOpacity>
                    </View>

                    <View style={styles.spotQuickInfo}>
                      {spot.address ? (
                        <View style={styles.quickInfoItem}>
                          <Ionicons name="location" size={16} color="#9ca3af" />
                          <Text style={styles.quickInfoText} numberOfLines={1}>{spot.address}</Text>
                        </View>
                      ) : null}
                    </View>

                    <View style={styles.spotDetails}>
                      <Text style={styles.spotDescription}>{spot.notes || 'Free overnight RV parking welcome.'}</Text>
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
    backgroundColor: '#0ea5e920',
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
    backgroundColor: '#0ea5e9',
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
  resultsHeaderRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 12,
    paddingHorizontal: 4,
  },
  resultsTitle: {
    color: '#e5e7eb',
    fontSize: 18,
    fontWeight: '700',
  },
  sourceTag: {
    backgroundColor: '#1e3a5f',
    borderRadius: 8,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderWidth: 1,
    borderColor: '#2563eb',
  },
  sourceTagText: {
    color: '#93c5fd',
    fontSize: 11,
    fontWeight: '600',
  },
  groupSection: {
    marginBottom: 12,
    gap: 8,
  },
  groupLabel: {
    color: '#9ca3af',
    fontSize: 13,
    marginBottom: 4,
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
    backgroundColor: '#0ea5e933',
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#0ea5e9',
  },
  spotTypeBadgeText: {
    color: '#0ea5e9',
    fontWeight: '700',
  },
  distancePill: {
    backgroundColor: '#0b1224',
    color: '#e5e7eb',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 8,
    fontSize: 12,
  },
  openPill: {
    backgroundColor: '#14532d',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 8,
  },
  openPillText: {
    color: '#4ade80',
    fontSize: 11,
    fontWeight: '700',
  },
  closedPill: {
    backgroundColor: '#450a0a',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 8,
  },
  closedPillText: {
    color: '#f87171',
    fontSize: 11,
    fontWeight: '700',
  },
  ratingRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    marginTop: 4,
  },
  ratingText: {
    color: '#fbbf24',
    fontSize: 12,
    fontWeight: '600',
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
    color: '#0ea5e9',
    textDecorationLine: 'underline',
  },
  navigateButton: {
    marginTop: 8,
    backgroundColor: '#0ea5e9',
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
