/**
 * LocationSearchBox
 *
 * Drop-in UI component for manual location search + "Use My Location" button.
 * Uses useLocationSearch hook values passed as props.
 */

import React from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  ActivityIndicator,
  StyleSheet,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { LocationSuggestion } from '../useLocationSearch';

interface Props {
  lat: string;
  lon: string;
  locationLabel: string | null;
  locationLoading: boolean;
  locationQuery: string;
  suggestions: LocationSuggestion[];
  showSuggestions: boolean;
  handleLocationQueryChange: (text: string) => void;
  selectSuggestion: (s: LocationSuggestion) => void;
  clearManualLocation: () => void;
  triggerGps: () => void;
  setShowSuggestions: (v: boolean) => void;
  accentColor?: string;
}

export default function LocationSearchBox({
  lat,
  lon,
  locationLabel,
  locationLoading,
  locationQuery,
  suggestions,
  showSuggestions,
  handleLocationQueryChange,
  selectSuggestion,
  clearManualLocation,
  triggerGps,
  setShowSuggestions,
  accentColor = '#06b6d4',
}: Props) {
  const hasLocation = lat && lon;

  return (
    <View style={styles.locationBox}>
      {/* Search input */}
      <View style={[styles.searchRow, { borderColor: accentColor + '30' }]}>
        <Ionicons name="search" size={15} color="#6b7280" style={{ marginRight: 6 }} />
        <TextInput
          style={styles.searchInput}
          placeholder="Search city or place… (e.g. Key West, FL)"
          placeholderTextColor="#6b7280"
          value={locationQuery}
          onChangeText={handleLocationQueryChange}
          onFocus={() => { if (suggestions.length > 0) setShowSuggestions(true); }}
          returnKeyType="search"
          autoCorrect={false}
          autoCapitalize="words"
        />
      </View>

      {/* Autocomplete dropdown */}
      {showSuggestions && suggestions.length > 0 && (
        <View style={styles.suggestionsBox}>
          {suggestions.map((s, i) => (
            <TouchableOpacity
              key={i}
              style={[styles.suggestionRow, i > 0 && styles.suggestionDivider]}
              onPress={() => selectSuggestion(s)}
              activeOpacity={0.75}
            >
              <Ionicons name="location-outline" size={13} color={accentColor} style={{ marginRight: 6 }} />
              <Text style={styles.suggestionText} numberOfLines={2}>{s.place_name}</Text>
            </TouchableOpacity>
          ))}
        </View>
      )}

      {/* Active location row */}
      <View style={styles.activeRow}>
        <View style={styles.chipWrap}>
          {locationLabel ? (
            <>
              <Ionicons name="location" size={13} color={accentColor} />
              <Text style={[styles.chipText, { color: accentColor }]} numberOfLines={1}>{locationLabel}</Text>
              <TouchableOpacity onPress={clearManualLocation} hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}>
                <Ionicons name="close-circle" size={15} color="#6b7280" />
              </TouchableOpacity>
            </>
          ) : hasLocation ? (
            <>
              <Ionicons name="navigate" size={13} color={accentColor} />
              <Text style={[styles.chipText, { color: accentColor }]} numberOfLines={1}>
                GPS · {parseFloat(lat).toFixed(4)}, {parseFloat(lon).toFixed(4)}
              </Text>
            </>
          ) : (
            <>
              <Ionicons name="location-outline" size={13} color="#6b7280" />
              <Text style={styles.noLocText}>No location — search above or use GPS</Text>
            </>
          )}
        </View>

        <TouchableOpacity
          style={[styles.gpsBtn, { borderColor: accentColor + '50', backgroundColor: accentColor + '15' }]}
          onPress={triggerGps}
          disabled={locationLoading}
        >
          {locationLoading ? (
            <ActivityIndicator size="small" color={accentColor} />
          ) : (
            <>
              <Ionicons name="refresh" size={13} color={accentColor} />
              <Text style={[styles.gpsBtnText, { color: accentColor }]}>Use my location</Text>
            </>
          )}
        </TouchableOpacity>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  locationBox: {
    backgroundColor: '#1f1f23',
    borderRadius: 12,
    padding: 12,
    marginBottom: 14,
    borderWidth: 1,
    borderColor: '#27272a',
  },
  searchRow: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#27272a',
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 8,
    marginBottom: 6,
    borderWidth: 1,
  },
  searchInput: {
    flex: 1,
    color: '#f4f4f5',
    fontSize: 14,
    paddingVertical: 0,
  },
  suggestionsBox: {
    backgroundColor: '#18181b',
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#3f3f46',
    marginBottom: 6,
    overflow: 'hidden',
  },
  suggestionRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingVertical: 10,
  },
  suggestionDivider: {
    borderTopWidth: 1,
    borderTopColor: '#27272a',
  },
  suggestionText: {
    color: '#e4e4e7',
    fontSize: 13,
    flex: 1,
  },
  activeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 8,
    marginTop: 2,
  },
  chipWrap: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    flex: 1,
  },
  chipText: {
    fontSize: 12,
    fontWeight: '600',
    flex: 1,
  },
  noLocText: {
    color: '#6b7280',
    fontSize: 12,
    flex: 1,
  },
  gpsBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: 9,
    paddingVertical: 5,
    borderRadius: 7,
    borderWidth: 1,
  },
  gpsBtnText: {
    fontSize: 11,
    fontWeight: '600',
  },
});
