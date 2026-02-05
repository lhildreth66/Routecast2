import React, { useState, useEffect, useCallback } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, ActivityIndicator, Alert } from 'react-native';
import * as Location from 'expo-location';
import { Ionicons } from '@expo/vector-icons';

interface LocationDisplayProps {
  onLocationChange: (lat: number, lon: number) => void;
  compact?: boolean;
}

export default function LocationDisplay({ onLocationChange, compact = false }: LocationDisplayProps) {
  const [latitude, setLatitude] = useState<number | null>(null);
  const [longitude, setLongitude] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchLocation = useCallback(async (showAlert = false) => {
    setLoading(true);
    setError(null);
    try {
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== 'granted') {
        setError('Location permission denied');
        if (showAlert) {
          Alert.alert(
            'Location Permission Required',
            'Please enable location permissions in your device settings.',
            [{ text: 'OK' }]
          );
        }
        setLoading(false);
        return;
      }

      const location = await Location.getCurrentPositionAsync({
        accuracy: Location.Accuracy.Balanced,
      });
      
      const lat = location.coords.latitude;
      const lon = location.coords.longitude;
      
      setLatitude(lat);
      setLongitude(lon);
      onLocationChange(lat, lon);
      
      if (showAlert) {
        Alert.alert('Location Updated', `${lat.toFixed(4)}, ${lon.toFixed(4)}`);
      }
    } catch (err: any) {
      setError('Unable to get location');
      if (showAlert) {
        Alert.alert('Location Error', err.message || 'Unable to get your location');
      }
    } finally {
      setLoading(false);
    }
  }, [onLocationChange]);

  useEffect(() => {
    fetchLocation(false);
  }, []);

  if (compact) {
    return (
      <View style={styles.compactContainer}>
        <View style={styles.compactLocation}>
          <Ionicons name="location" size={16} color="#06b6d4" />
          {loading ? (
            <ActivityIndicator size="small" color="#06b6d4" style={{ marginLeft: 8 }} />
          ) : error ? (
            <Text style={styles.compactError}>{error}</Text>
          ) : (
            <Text style={styles.compactText}>
              {latitude?.toFixed(4)}, {longitude?.toFixed(4)}
            </Text>
          )}
        </View>
        <TouchableOpacity 
          onPress={() => fetchLocation(true)} 
          style={styles.refreshButton}
          disabled={loading}
        >
          {loading ? (
            <ActivityIndicator size="small" color="#06b6d4" />
          ) : (
            <Ionicons name="refresh" size={18} color="#06b6d4" />
          )}
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <View style={styles.iconContainer}>
          <Ionicons name="location" size={20} color="#06b6d4" />
        </View>
        <Text style={styles.title}>Your Location</Text>
        <TouchableOpacity 
          onPress={() => fetchLocation(true)} 
          style={styles.refreshButtonLarge}
          disabled={loading}
        >
          {loading ? (
            <ActivityIndicator size="small" color="#06b6d4" />
          ) : (
            <Ionicons name="refresh" size={20} color="#06b6d4" />
          )}
        </TouchableOpacity>
      </View>
      
      {loading ? (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="small" color="#06b6d4" />
          <Text style={styles.loadingText}>Detecting location...</Text>
        </View>
      ) : error ? (
        <TouchableOpacity onPress={() => fetchLocation(true)} style={styles.errorContainer}>
          <Ionicons name="alert-circle" size={16} color="#ef4444" />
          <Text style={styles.errorText}>{error}</Text>
          <Text style={styles.retryText}>Tap to retry</Text>
        </TouchableOpacity>
      ) : (
        <View style={styles.coordsContainer}>
          <View style={styles.coordBox}>
            <Text style={styles.coordLabel}>LAT</Text>
            <Text style={styles.coordValue}>{latitude?.toFixed(4)}</Text>
          </View>
          <View style={styles.coordBox}>
            <Text style={styles.coordLabel}>LON</Text>
            <Text style={styles.coordValue}>{longitude?.toFixed(4)}</Text>
          </View>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: '#1a1a1a',
    borderRadius: 12,
    padding: 16,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: '#27272a',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 12,
  },
  iconContainer: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: 'rgba(6, 182, 212, 0.15)',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 10,
  },
  title: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '600',
    flex: 1,
  },
  refreshButtonLarge: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: 'rgba(6, 182, 212, 0.15)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 8,
  },
  loadingText: {
    color: '#9ca3af',
    fontSize: 14,
    marginLeft: 8,
  },
  errorContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 8,
    gap: 6,
  },
  errorText: {
    color: '#ef4444',
    fontSize: 14,
  },
  retryText: {
    color: '#6b7280',
    fontSize: 12,
  },
  coordsContainer: {
    flexDirection: 'row',
    gap: 12,
  },
  coordBox: {
    flex: 1,
    backgroundColor: '#27272a',
    borderRadius: 8,
    padding: 12,
    alignItems: 'center',
  },
  coordLabel: {
    color: '#9ca3af',
    fontSize: 11,
    fontWeight: '600',
    letterSpacing: 1,
    marginBottom: 4,
  },
  coordValue: {
    color: '#06b6d4',
    fontSize: 16,
    fontWeight: '600',
    fontFamily: 'monospace',
  },
  // Compact styles
  compactContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1a1a1a',
    borderRadius: 8,
    paddingVertical: 8,
    paddingHorizontal: 12,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: '#27272a',
  },
  compactLocation: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
  },
  compactText: {
    color: '#9ca3af',
    fontSize: 13,
    marginLeft: 8,
    fontFamily: 'monospace',
  },
  compactError: {
    color: '#ef4444',
    fontSize: 13,
    marginLeft: 8,
  },
  refreshButton: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: 'rgba(6, 182, 212, 0.1)',
    justifyContent: 'center',
    alignItems: 'center',
  },
});
