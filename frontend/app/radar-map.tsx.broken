import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ActivityIndicator,
  SafeAreaView,
  Platform,
} from 'react-native';
import { WebView } from 'react-native-webview';
import { router } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import axios from 'axios';
import * as Location from 'expo-location';
import { API_BASE } from './apiConfig';

interface AlertFeature {
  id: string;
  event: string;
  headline: string;
  description: string;
  severity: string;
  urgency: string;
  areas: string[];
  effective: string | null;
  expires: string | null;
  color: string;
  category: string;
  priority: number;
  geometry: any | null;
}

export default function RadarMapScreen() {
  const [loading, setLoading] = useState(true);
  const [alerts, setAlerts] = useState<AlertFeature[]>([]);
  const [userLocation, setUserLocation] = useState<{ lat: number; lon: number } | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    setError('');

    try {
      // Get user location
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status === 'granted') {
        const location = await Location.getCurrentPositionAsync({});
        setUserLocation({
          lat: location.coords.latitude,
          lon: location.coords.longitude,
        });
      }

      // Fetch alerts from our backend (not directly from NWS)
      const response = await axios.get(`${API_BASE}/api/radar/alerts/map`);
      setAlerts(response.data.alerts || []);
    } catch (err: any) {
      console.error('Error loading radar data:', err);
      setError('Failed to load weather radar data');
    } finally {
      setLoading(false);
    }
  };

  // Generate self-contained Leaflet map HTML
  const generateMapHTML = () => {
    const alertsJSON = JSON.stringify(alerts);
    const userLoc = userLocation ? JSON.stringify(userLocation) : 'null';

    return `
<!DOCTYPE html>
<html>
<head>
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    html, body { height: 100%; width: 100%; overflow: hidden; }
    #map { height: 100%; width: 100%; background: #1a1a1a; }
    .leaflet-container { background: #1a1a1a; }
    .legend {
      position: absolute;
      bottom: 10px;
      left: 10px;
      background: rgba(26, 26, 26, 0.95);
      color: #fff;
      padding: 10px;
      border-radius: 8px;
      box-shadow: 0 2px 8px rgba(0,0,0,0.4);
      z-index: 1000;
      font-family: -apple-system, BlinkMacSystemFont, sans-serif;
      font-size: 11px;
    }
    .legend-title {
      font-weight: bold;
      margin-bottom: 6px;
      font-size: 12px;
      color: #eab308;
    }
    .legend-item {
      display: flex;
      align-items: center;
      margin: 4px 0;
    }
    .legend-color {
      width: 16px;
      height: 12px;
      margin-right: 6px;
      border-radius: 3px;
      border: 1px solid rgba(255,255,255,0.3);
    }
    .alert-popup {
      min-width: 200px;
      max-width: 280px;
      background: #27272a;
      color: #fff;
      border-radius: 8px;
      padding: 12px;
    }
    .alert-popup h3 {
      margin: 0 0 8px 0;
      font-size: 14px;
      color: #eab308;
    }
    .alert-popup p {
      margin: 4px 0;
      font-size: 12px;
      color: #d4d4d8;
    }
    .radar-toggle {
      position: absolute;
      top: 10px;
      right: 10px;
      background: rgba(26, 26, 26, 0.95);
      color: #eab308;
      padding: 8px 14px;
      border-radius: 6px;
      font-size: 12px;
      font-weight: 600;
      cursor: pointer;
      z-index: 1000;
      box-shadow: 0 2px 6px rgba(0,0,0,0.4);
      border: 1px solid #eab308;
    }
    .radar-toggle.active {
      background: #eab308;
      color: #1a1a1a;
    }
  </style>
</head>
<body>
  <div id="map"></div>
  <div class="radar-toggle" onclick="toggleRadar()" id="radarBtn">🌧️ Radar</div>
  <div class="legend">
    <div class="legend-title">Weather Alerts</div>
    <div class="legend-item">
      <div class="legend-color" style="background: #FF69B4;"></div>
      <span>Snow/Winter</span>
    </div>
    <div class="legend-item">
      <div class="legend-color" style="background: #0000FF;"></div>
      <span>Ice/Cold</span>
    </div>
    <div class="legend-item">
      <div class="legend-color" style="background: #228B22;"></div>
      <span>Rain/Flood</span>
    </div>
    <div class="legend-item">
      <div class="legend-color" style="background: #FFA500;"></div>
      <span>Thunderstorm</span>
    </div>
    <div class="legend-item">
      <div class="legend-color" style="background: #FF0000;"></div>
      <span>Tornado</span>
    </div>
    <div class="legend-item">
      <div class="legend-color" style="background: #DC143C;"></div>
      <span>Hurricane</span>
    </div>
  </div>
  
  <script>
    const alerts = ${alertsJSON};
    const userLocation = ${userLoc};
    
    // Initialize map
    const map = L.map('map', {
      zoomControl: true,
      attributionControl: true,
    }).setView(userLocation ? [userLocation.lat, userLocation.lon] : [39.8283, -98.5795], userLocation ? 8 : 4);
    
    // Add dark base layer
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
      attribution: '&copy; OpenStreetMap, &copy; CARTO',
      subdomains: 'abcd',
      maxZoom: 20
    }).addTo(map);
    
    // Add user location marker
    if (userLocation) {
      L.circleMarker([userLocation.lat, userLocation.lon], {
        radius: 8,
        color: '#eab308',
        fillColor: '#eab308',
        fillOpacity: 0.8,
        weight: 2
      }).addTo(map).bindPopup('<b style="color:#eab308">Your Location</b>');
    }
    
    // Add alert polygons
    alerts.forEach(alert => {
      if (alert.geometry && alert.geometry.coordinates) {
        const style = {
          color: alert.color,
          weight: 2,
          opacity: 0.8,
          fillColor: alert.color,
          fillOpacity: 0.3
        };
        
        try {
          const layer = L.geoJSON(alert.geometry, { style }).addTo(map);
          
          const popupContent = \`
            <div class="alert-popup">
              <h3>\${alert.event}</h3>
              <p><strong>Severity:</strong> \${alert.severity}</p>
              <p><strong>Areas:</strong> \${alert.areas.slice(0, 3).join(', ')}</p>
              <p><strong>Expires:</strong> \${alert.expires ? new Date(alert.expires).toLocaleString() : 'Unknown'}</p>
            </div>
          \`;
          
          layer.bindPopup(popupContent);
        } catch (e) {
          console.error('Failed to add alert layer:', e);
        }
      }
    });
    
    // Radar layer
    let radarLayer = null;
    let radarVisible = false;
    
    async function toggleRadar() {
      const btn = document.getElementById('radarBtn');
      
      if (radarVisible) {
        // Hide radar
        if (radarLayer) {
          map.removeLayer(radarLayer);
          radarLayer = null;
        }
        radarVisible = false;
        btn.classList.remove('active');
        btn.textContent = '🌧️ Radar';
      } else {
        // Show radar
        btn.textContent = 'Loading...';
        try {
          const response = await fetch('${API_BASE}/api/radar/tiles');
          const data = await response.json();
          
          if (data.tile_url) {
            radarLayer = L.tileLayer(data.tile_url, {
              opacity: 0.7,
              attribution: 'RainViewer'
            }).addTo(map);
            radarVisible = true;
            btn.classList.add('active');
            btn.textContent = '🌧️ Radar ON';
          } else {
            btn.textContent = '🌧️ Radar (N/A)';
          }
        } catch (e) {
          console.error('Failed to load radar:', e);
          btn.textContent = '🌧️ Radar (Error)';
        }
      }
    }
  </script>
</body>
</html>
    `;
  };

  if (loading) {
    return (
      <SafeAreaView style={styles.loadingContainer}>
        <View style={styles.header}>
          <TouchableOpacity onPress={() => router.back()}>
            <Ionicons name="chevron-back" size={24} color="#e4e4e7" />
          </TouchableOpacity>
          <Text style={styles.headerTitle}>Weather Radar</Text>
          <View style={{ width: 24 }} />
        </View>
        <View style={styles.loadingContent}>
          <ActivityIndicator size="large" color="#eab308" />
          <Text style={styles.loadingText}>Loading radar data...</Text>
        </View>
      </SafeAreaView>
    );
  }

  if (error) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.header}>
          <TouchableOpacity onPress={() => router.back()}>
            <Ionicons name="chevron-back" size={24} color="#e4e4e7" />
          </TouchableOpacity>
          <Text style={styles.headerTitle}>Weather Radar</Text>
          <View style={{ width: 24 }} />
        </View>
        <View style={styles.errorContainer}>
          <Ionicons name="alert-circle" size={48} color="#ef4444" />
          <Text style={styles.errorText}>{error}</Text>
          <TouchableOpacity style={styles.retryButton} onPress={loadData}>
            <Text style={styles.retryButtonText}>Retry</Text>
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()}>
          <Ionicons name="chevron-back" size={24} color="#e4e4e7" />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Weather Radar & Alerts</Text>
        <TouchableOpacity onPress={loadData}>
          <Ionicons name="refresh" size={22} color="#eab308" />
        </TouchableOpacity>
      </View>

      <WebView
        source={{ html: generateMapHTML() }}
        style={styles.webview}
        javaScriptEnabled={true}
        domStorageEnabled={true}
        startInLoadingState={true}
        scalesPageToFit={true}
        originWhitelist={['*']}
      />

      <View style={styles.footer}>
        <Text style={styles.footerText}>
          🌧️ Radar & {alerts.length} active alert{alerts.length !== 1 ? 's' : ''} • Live NWS data
        </Text>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#18181b',
  },
  loadingContainer: {
    flex: 1,
    backgroundColor: '#18181b',
  },
  loadingContent: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#27272a',
    backgroundColor: '#18181b',
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: '#ffffff',
  },
  webview: {
    flex: 1,
  },
  footer: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    backgroundColor: '#27272a',
    borderTopWidth: 1,
    borderTopColor: '#3f3f46',
  },
  footerText: {
    color: '#9ca3af',
    fontSize: 12,
    textAlign: 'center',
  },
  loadingText: {
    color: '#9ca3af',
    fontSize: 14,
    marginTop: 12,
  },
  errorContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
  },
  errorText: {
    color: '#ef4444',
    fontSize: 16,
    textAlign: 'center',
    marginTop: 16,
    marginBottom: 24,
  },
  retryButton: {
    backgroundColor: '#eab308',
    paddingHorizontal: 24,
    paddingVertical: 12,
    borderRadius: 8,
  },
  retryButtonText: {
    color: '#1a1a1a',
    fontSize: 16,
    fontWeight: '600',
  },
});
