import React, { useState, useEffect, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  SafeAreaView,
  Switch,
  ScrollView,
  ActivityIndicator,
} from 'react-native';
import { router } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import MapLibreGL from '@rnmapbox/maps';
import { WeatherLayerManager, LAYER_PRESETS } from './services/WeatherLayerManager';

// Configure MapLibre (no API key needed!)
MapLibreGL.setConnected(true);

export default function WeatherMapScreen() {
  const [layerManager] = useState(() => new WeatherLayerManager());
  const [layers, setLayers] = useState(layerManager.getLayers());
  const [loading, setLoading] = useState(true);
  const [showControls, setShowControls] = useState(true);
  const [radarTimestamp, setRadarTimestamp] = useState<string | null>(null);
  const [alertsData, setAlertsData] = useState<any>(null);

  useEffect(() => {
    // Subscribe to layer changes
    const unsubscribe = layerManager.subscribe(() => {
      setLayers([...layerManager.getLayers()]);
    });

    // Start auto-updates
    layerManager.startAutoUpdate();

    // Initial data fetch
    const initializeData = async () => {
      setLoading(true);
      const radarUrl = await layerManager.updateRadarTimestamp();
      const alerts = await layerManager.updateSevereAlerts();
      setRadarTimestamp(radarUrl);
      setAlertsData(alerts);
      setLoading(false);
    };

    initializeData();

    return () => {
      unsubscribe();
      layerManager.cleanup();
    };
  }, []);

  const toggleLayer = (layerId: string) => {
    layerManager.toggleLayer(layerId);
  };

  const setOpacity = (layerId: string, opacity: number) => {
    layerManager.setOpacity(layerId, opacity);
  };

  const applyPreset = (presetName: string) => {
    layerManager.applyPreset(presetName);
  };

  const radarLayer = layers.find(l => l.id === 'radar-precipitation');
  const alertsLayer = layers.find(l => l.id === 'severe-alerts');

  return (
    <SafeAreaView style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()}>
          <Ionicons name="chevron-back" size={24} color="#e4e4e7" />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Weather Radar Map</Text>
        <TouchableOpacity onPress={() => setShowControls(!showControls)}>
          <Ionicons name="layers" size={24} color="#e4e4e7" />
        </TouchableOpacity>
      </View>

      {/* Map */}
      <View style={styles.mapContainer}>
        {loading ? (
          <View style={styles.loadingContainer}>
            <ActivityIndicator size="large" color="#3b82f6" />
            <Text style={styles.loadingText}>Loading weather data...</Text>
          </View>
        ) : (
          <MapLibreGL.MapView
            style={styles.map}
            styleURL="https://demotiles.maplibre.org/style.json"
          >
            <MapLibreGL.Camera
              zoomLevel={5}
              centerCoordinate={[-93.5, 41.5]} // Iowa center
              animationDuration={1000}
            />

            {/* Radar Layer */}
            {radarLayer?.visible && radarTimestamp && (
              <MapLibreGL.RasterSource
                id="radar-source"
                tileUrlTemplates={[radarTimestamp]}
                tileSize={256}
              >
                <MapLibreGL.RasterLayer
                  id="radar-layer"
                  sourceID="radar-source"
                  style={{
                    rasterOpacity: radarLayer.opacity,
                  }}
                />
              </MapLibreGL.RasterSource>
            )}

            {/* Severe Weather Alerts Layer */}
            {alertsLayer?.visible && alertsData?.features && (
              <MapLibreGL.ShapeSource
                id="alerts-source"
                shape={alertsData}
              >
                <MapLibreGL.FillLayer
                  id="alerts-fill"
                  sourceID="alerts-source"
                  style={{
                    fillColor: [
                      'match',
                      ['get', 'severity'],
                      'Extreme', '#8B0000',
                      'Severe', '#FF4500',
                      'Moderate', '#FFA500',
                      'Minor', '#FFD700',
                      '#FFD700',
                    ],
                    fillOpacity: alertsLayer.opacity,
                  }}
                />
                <MapLibreGL.LineLayer
                  id="alerts-outline"
                  sourceID="alerts-source"
                  style={{
                    lineColor: '#FF0000',
                    lineWidth: 2,
                    lineOpacity: 0.8,
                  }}
                />
              </MapLibreGL.ShapeSource>
            )}

            {/* User Location */}
            <MapLibreGL.UserLocation
              animated={true}
              androidRenderMode="compass"
              showsUserHeadingIndicator={true}
            />
          </MapLibreGL.MapView>
        )}
      </View>

      {/* Layer Controls */}
      {showControls && (
        <View style={styles.controlsContainer}>
          <ScrollView style={styles.controlsScroll} showsVerticalScrollIndicator={false}>
            {/* Presets */}
            <Text style={styles.controlsTitle}>Quick Presets</Text>
            <View style={styles.presetButtons}>
              {Object.keys(LAYER_PRESETS).map(preset => (
                <TouchableOpacity
                  key={preset}
                  style={styles.presetButton}
                  onPress={() => applyPreset(preset)}
                >
                  <Text style={styles.presetButtonText}>
                    {preset.charAt(0).toUpperCase() + preset.slice(1)}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>

            {/* Layer Toggles */}
            <Text style={styles.controlsTitle}>Weather Layers</Text>
            {layers.map(layer => (
              <View key={layer.id} style={styles.layerControl}>
                <View style={styles.layerHeader}>
                  <Switch
                    value={layer.visible}
                    onValueChange={() => toggleLayer(layer.id)}
                    trackColor={{ false: '#3f3f46', true: '#3b82f6' }}
                    thumbColor={layer.visible ? '#60a5fa' : '#d4d4d8'}
                  />
                  <Text style={styles.layerName}>{layer.name}</Text>
                  <Text style={styles.layerOpacity}>{Math.round(layer.opacity * 100)}%</Text>
                </View>
                {layer.visible && (
                  <View style={styles.opacitySlider}>
                    <TouchableOpacity
                      style={styles.sliderButton}
                      onPress={() => setOpacity(layer.id, Math.max(0, layer.opacity - 0.1))}
                    >
                      <Ionicons name="remove" size={16} color="#fff" />
                    </TouchableOpacity>
                    <View style={styles.sliderTrack}>
                      <View
                        style={[
                          styles.sliderFill,
                          { width: `${layer.opacity * 100}%` }
                        ]}
                      />
                    </View>
                    <TouchableOpacity
                      style={styles.sliderButton}
                      onPress={() => setOpacity(layer.id, Math.min(1, layer.opacity + 0.1))}
                    >
                      <Ionicons name="add" size={16} color="#fff" />
                    </TouchableOpacity>
                  </View>
                )}
              </View>
            ))}

            {/* Legend */}
            <Text style={styles.controlsTitle}>Radar Legend</Text>
            <View style={styles.legend}>
              <View style={styles.legendItem}>
                <View style={[styles.legendColor, { backgroundColor: '#00FF00' }]} />
                <Text style={styles.legendText}>Light Rain</Text>
              </View>
              <View style={styles.legendItem}>
                <View style={[styles.legendColor, { backgroundColor: '#FFFF00' }]} />
                <Text style={styles.legendText}>Moderate Rain</Text>
              </View>
              <View style={styles.legendItem}>
                <View style={[styles.legendColor, { backgroundColor: '#FF0000' }]} />
                <Text style={styles.legendText}>Heavy Rain</Text>
              </View>
              <View style={styles.legendItem}>
                <View style={[styles.legendColor, { backgroundColor: '#FF00FF' }]} />
                <Text style={styles.legendText}>Severe</Text>
              </View>
            </View>

            {/* Data Sources */}
            <Text style={styles.dataSource}>
              📡 Radar: RainViewer (Free) • Alerts: NOAA/NWS (Free)
            </Text>
          </ScrollView>
        </View>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#18181b',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#27272a',
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: '#ffffff',
  },
  mapContainer: {
    flex: 1,
  },
  map: {
    flex: 1,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#18181b',
  },
  loadingText: {
    marginTop: 12,
    color: '#9ca3af',
    fontSize: 14,
  },
  controlsContainer: {
    position: 'absolute',
    top: 80,
    right: 16,
    backgroundColor: 'rgba(24, 24, 27, 0.95)',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#3f3f46',
    maxHeight: '70%',
    width: 280,
  },
  controlsScroll: {
    padding: 16,
  },
  controlsTitle: {
    fontSize: 14,
    fontWeight: '700',
    color: '#e5e7eb',
    marginBottom: 12,
    marginTop: 8,
  },
  presetButtons: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginBottom: 16,
  },
  presetButton: {
    backgroundColor: '#3b82f6',
    borderRadius: 8,
    paddingHorizontal: 16,
    paddingVertical: 8,
  },
  presetButtonText: {
    color: '#fff',
    fontSize: 13,
    fontWeight: '600',
  },
  layerControl: {
    marginBottom: 16,
  },
  layerHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  layerName: {
    flex: 1,
    color: '#fff',
    fontSize: 14,
    fontWeight: '600',
  },
  layerOpacity: {
    color: '#9ca3af',
    fontSize: 12,
    minWidth: 35,
    textAlign: 'right',
  },
  opacitySlider: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginTop: 8,
    marginLeft: 48,
  },
  sliderButton: {
    width: 24,
    height: 24,
    borderRadius: 12,
    backgroundColor: '#3f3f46',
    justifyContent: 'center',
    alignItems: 'center',
  },
  sliderTrack: {
    flex: 1,
    height: 6,
    backgroundColor: '#3f3f46',
    borderRadius: 3,
    overflow: 'hidden',
  },
  sliderFill: {
    height: '100%',
    backgroundColor: '#3b82f6',
  },
  legend: {
    gap: 8,
  },
  legendItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  legendColor: {
    width: 20,
    height: 20,
    borderRadius: 4,
  },
  legendText: {
    color: '#d4d4d8',
    fontSize: 12,
  },
  dataSource: {
    marginTop: 16,
    color: '#6b7280',
    fontSize: 10,
    textAlign: 'center',
    fontStyle: 'italic',
  },
});
