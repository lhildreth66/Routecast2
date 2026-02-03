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

      // Fetch alerts from backend if available
      if (API_BASE) {
        try {
          const response = await axios.get(`${API_BASE}/api/radar/alerts/map`);
          setAlerts(response.data.alerts || []);
        } catch (alertErr: any) {
          console.warn('Failed to load weather alerts, continuing without alerts:', alertErr);
          // Continue without alerts - map will still work
        }
      } else {
        console.warn('Backend URL not configured, radar map will work without weather alerts');
      }
    } catch (err: any) {
      console.error('Error loading radar data:', err);
      setError('Failed to load location data');
    } finally {
      setLoading(false);
    }
  };

  // Generate self-contained Leaflet map HTML with alerts and radar
  const generateMapHTML = () => {
    const alertsJSON = JSON.stringify(alerts);
    const userLoc = userLocation ? JSON.stringify(userLocation) : 'null';

    // TEST: Simple HTML first to verify WebView works
    const testHtml = `
<!DOCTYPE html>
<html>
<head>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    body { 
      margin: 0; 
      padding: 20px; 
      background: #1a1a1a; 
      color: #fff;
      font-family: -apple-system, BlinkMacSystemFont, sans-serif;
    }
    h1 { color: #eab308; }
  </style>
</head>
<body>
  <h1>WebView Test</h1>
  <p>If you see this, WebView is working!</p>
  <p>Alerts: ${alerts.length}</p>
  <p>Location: ${userLoc}</p>
  <script>
    window.ReactNativeWebView?.postMessage(JSON.stringify({ type: 'log', message: 'WebView loaded and running' }));
  </script>
</body>
</html>
    `;

    console.log('MAP HTML LENGTH:', testHtml.length);
    console.log('MAP HTML PREVIEW:', testHtml.substring(0, 200));
    
    return testHtml;
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

      {/* Platform-specific rendering: iframe for web, WebView for native */}
      {Platform.OS === 'web' ? (
        <iframe
          srcDoc={generateMapHTML()}
          style={{
            width: '100%',
            flex: 1,
            border: 'none',
          }}
          title="Weather Radar Map"
        />
      ) : (
        <WebView
          source={{ 
            html: generateMapHTML(),
            baseUrl: 'https://routecastweather.com'
          }}
          style={styles.webview}
          javaScriptEnabled={true}
          domStorageEnabled={true}
          startInLoadingState={true}
          scalesPageToFit={true}
          originWhitelist={['*']}
          allowFileAccessFromFileURLs={true}
          allowUniversalAccessFromFileURLs={true}
          mixedContentMode="always"
          onError={(syntheticEvent) => {
            const { nativeEvent } = syntheticEvent;
            console.error('WebView error:', nativeEvent);
          }}
          onMessage={(event) => {
            console.log('WebView message:', event.nativeEvent.data);
          }}
          onLoadEnd={() => {
            console.log('WebView loaded successfully');
          }}
        />
      )}

      <View style={styles.footer}>
        <Text style={styles.footerText}>
          🌧️ Radar {alerts.length > 0 ? `& ${alerts.length} active alert${alerts.length !== 1 ? 's' : ''}` : '(alerts unavailable)'} • {API_BASE ? 'Live NWS data' : 'Limited mode - backend not connected'}
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
