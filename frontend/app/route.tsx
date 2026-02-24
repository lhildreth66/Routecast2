import React, { useState, useEffect, useMemo } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
  SafeAreaView,
  Platform,
  Share,
  Linking,
  Modal,
  TextInput,
  Dimensions,
} from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { useLocalSearchParams, router } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import * as Speech from 'expo-speech';
import { format, parseISO } from 'date-fns';
import axios from 'axios';
import { WebView } from 'react-native-webview';

const API_BASE = process.env.EXPO_PUBLIC_BACKEND_URL || '';
const { width: SCREEN_WIDTH } = Dimensions.get('window');

// Types
interface RoadCondition {
  condition: string;
  severity: number;
  label: string;
  icon: string;
  color: string;
  description: string;
  recommendation: string;
}

interface TurnByTurnStep {
  instruction: string;
  distance_miles: number;
  duration_minutes: number;
  road_name: string;
  maneuver: string;
  road_condition: RoadCondition | null;
  weather_at_step: string | null;
  temperature: number | null;
  has_alert: boolean;
}

interface WeatherData {
  temperature: number | null;
  conditions: string | null;
  wind_speed: string | null;
  humidity: number | null;
}

interface WeatherAlert {
  event: string;
  headline: string;
  severity: string;
}

interface WaypointWeather {
  waypoint: {
    lat: number;
    lon: number;
    name: string;
    distance_from_start: number | null;
    eta_minutes: number | null;
    arrival_time: string | null;
  };
  weather: WeatherData | null;
  alerts: WeatherAlert[];
}

interface SafetyScore {
  overall_score: number;
  risk_level: string;
  vehicle_type: string;
  factors: string[];
  recommendations: string[];
}

interface HazardAlert {
  type: string;
  severity: string;
  distance_miles: number;
  eta_minutes: number;
  message: string;
  recommendation: string;
  countdown_text: string;
  id?: string;
  alert_id?: string;
  event?: string;
  headline?: string;
  full_description?: string;
  description?: string;
  instruction?: string;
  areaDesc?: string;
  onset?: string;
  expires?: string;
  location_name?: string;
  driver_action?: string;
  properties?: {
    event?: string;
    headline?: string;
    description?: string;
    instruction?: string;
    areaDesc?: string;
    onset?: string;
    expires?: string;
  };
  source?: string;
  alert_level?: string;
}

interface BridgeClearanceAlert {
  bridge_name: string;
  clearance_ft: number;
  vehicle_height_ft: number;
  distance_miles: number;
  latitude: number;
  longitude: number;
  warning: string;
}

interface RouteData {
  id: string;
  origin: string;
  destination: string;
  total_duration_minutes: number | null;
  total_distance_miles: number | null;
  waypoints: WaypointWeather[];
  safety_score: SafetyScore | null;
  hazard_alerts: HazardAlert[];
  bridge_clearance_alerts?: BridgeClearanceAlert[];
  turn_by_turn: TurnByTurnStep[];
  road_condition_summary: string | null;
  worst_road_condition: string | null;
  reroute_recommended: boolean;
  reroute_reason: string | null;
  trucker_warnings: string[];
  ai_summary: string | null;
}

const formatDuration = (minutes: number): string => {
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  if (hours === 0) return `${mins} min`;
  return mins > 0 ? `${hours}h ${mins}m` : `${hours}h`;
};

const getManeuverIcon = (maneuver: string): string => {
  const icons: { [key: string]: string } = {
    'turn-right': 'arrow-forward',
    'turn-left': 'arrow-back',
    'merge': 'git-merge-outline',
    'straight': 'arrow-up',
    'depart': 'navigate',
    'arrive': 'flag',
    'roundabout': 'reload',
    'exit': 'exit-outline',
    'fork': 'git-branch-outline',
  };
  return icons[maneuver] || 'arrow-forward';
};

// Generate radar map HTML using IEM WMS layer for NWS Watch/Warning/Advisory colored zones
const generateRadarMapHtml = (centerLat: number, centerLon: number): string => {
  const usLat = Math.max(25, Math.min(48, centerLat));
  const usLon = Math.max(-124, Math.min(-68, centerLon));
  
  return `
    <!DOCTYPE html>
    <html>
    <head>
      <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
      <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
      <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
      <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        html, body { width: 100%; height: 100%; background: #f0f0f0; }
        #map { width: 100%; height: calc(100% - 120px); }
        .legend-box {
          position: fixed;
          bottom: 0;
          left: 0;
          right: 0;
          background: #003366;
          padding: 8px 12px;
          z-index: 1000;
          font-family: -apple-system, BlinkMacSystemFont, sans-serif;
        }
        .legend-title {
          color: #fff;
          font-size: 13px;
          font-weight: 700;
          margin-bottom: 6px;
          text-align: center;
        }
        .legend-grid {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 4px;
        }
        .legend-item {
          display: flex;
          align-items: center;
          gap: 6px;
        }
        .legend-color {
          width: 18px;
          height: 12px;
          border-radius: 2px;
          border: 1px solid rgba(255,255,255,0.3);
        }
        .legend-text {
          color: #fff;
          font-size: 10px;
          font-weight: 500;
        }
        .controls-row {
          position: absolute;
          bottom: 125px;
          left: 10px;
          z-index: 1000;
        }
        .toggle-btn {
          background: rgba(0,51,102,0.9);
          border: 1px solid #4fc3f7;
          color: #4fc3f7;
          padding: 2px 6px;
          border-radius: 8px;
          font-size: 8px;
          font-weight: 600;
          cursor: pointer;
        }
        .toggle-btn.active { background: #4fc3f7; color: #003366; }
        .time-display {
          color: #fff;
          font-size: 11px;
          font-weight: 500;
        }
        .zoom-controls {
          position: absolute;
          top: 10px;
          right: 10px;
          background: #fff;
          border-radius: 8px;
          box-shadow: 0 2px 8px rgba(0,0,0,0.25);
          z-index: 1000;
          overflow: hidden;
        }
        .zoom-btn {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 44px;
          height: 44px;
          background: #fff;
          border: none;
          font-size: 24px;
          font-weight: bold;
          cursor: pointer;
          color: #003366;
        }
        .zoom-btn:first-child { border-bottom: 1px solid #ddd; }
        .zoom-btn:active { background: #e0e0e0; }
        .leaflet-control-zoom { display: none !important; }
        #alertOverlay {
          position: absolute;
          top: 0;
          left: 0;
          right: 0;
          bottom: 120px;
          pointer-events: none;
          z-index: 500;
        }
      </style>
    </head>
    <body>
      <div id="map"></div>
      <img id="alertOverlay" src="" style="display:none;" />
      <div class="zoom-controls">
        <button class="zoom-btn" id="zoomInBtn">+</button>
        <button class="zoom-btn" id="zoomOutBtn">−</button>
      </div>
      <div class="controls-row">
        <button class="toggle-btn active" id="radarBtn">☁️ Radar</button>
      </div>
      <div class="legend-box">
        <div class="legend-title">⚠️ NWS WATCH / WARNING / ADVISORY</div>
        <div class="legend-grid">
          <div class="legend-item">
            <div class="legend-color" style="background: #ff69b4;"></div>
            <span class="legend-text">Winter Storm</span>
          </div>
          <div class="legend-item">
            <div class="legend-color" style="background: #9400d3;"></div>
            <span class="legend-text">Special Statement</span>
          </div>
          <div class="legend-item">
            <div class="legend-color" style="background: #00ffff;"></div>
            <span class="legend-text">Extreme Cold</span>
          </div>
          <div class="legend-item">
            <div class="legend-color" style="background: #00ff00;"></div>
            <span class="legend-text">Flood</span>
          </div>
          <div class="legend-item">
            <div class="legend-color" style="background: #ff0000;"></div>
            <span class="legend-text">Tornado</span>
          </div>
          <div class="legend-item">
            <div class="legend-color" style="background: #ffa500;"></div>
            <span class="legend-text">Severe T-Storm</span>
          </div>
        </div>
      </div>
      <script>
        var map = L.map('map', { 
          zoomControl: false,
          attributionControl: false,
          minZoom: 3,
          maxZoom: 10
        }).setView([${usLat}, ${usLon}], 5);
        
        // Light base map
        L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
          maxZoom: 19
        }).addTo(map);
        
        // IEM WMS Layer - using correct layer names and version
        var alertsLayer = L.tileLayer.wms('https://mesonet.agron.iastate.edu/cgi-bin/wms/us/wwa.cgi', {
          layers: 'warnings_c',
          format: 'image/png',
          transparent: true,
          version: '1.3.0',
          opacity: 0.8
        }).addTo(map);
        
        var radarLayer = null;
        var showRadar = true;
        
        // Load radar overlay
        fetch('https://api.rainviewer.com/public/weather-maps.json')
          .then(r => r.json())
          .then(data => {
            var frames = data.radar.past;
            if (frames.length > 0) {
              var latest = frames[frames.length - 1];
              radarLayer = L.tileLayer(
                'https://tilecache.rainviewer.com' + latest.path + '/512/{z}/{x}/{y}/2/1_1.png',
                { opacity: 0.5, zIndex: 50, tileSize: 512, zoomOffset: -1 }
              );
              if (showRadar) radarLayer.addTo(map);
            }
          });
        // Toggle radar layer
        document.getElementById('radarBtn').onclick = function() {
          showRadar = !showRadar;
          this.classList.toggle('active', showRadar);
          if (showRadar && radarLayer) {
            radarLayer.addTo(map);
          } else if (radarLayer) {
            map.removeLayer(radarLayer);
          }
        };
        
        document.getElementById('zoomInBtn').onclick = function() { map.zoomIn(); };
        document.getElementById('zoomOutBtn').onclick = function() { map.zoomOut(); };
        
        // Debug: Log when tiles load
        alertsLayer.on('tileload', function(e) {
          console.log('Alert tile loaded:', e.url);
        });
        alertsLayer.on('tileerror', function(e) {
          console.log('Alert tile error:', e.error);
        });
      </script>
    </body>
    </html>
  `;
};

export default function RouteScreen() {
  const params = useLocalSearchParams();
  const [routeData, setRouteData] = useState<RouteData | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'conditions' | 'directions' | 'alerts' | 'bridges'>('conditions');
  const [isSpeaking, setIsSpeaking] = useState(false);
  const alerts = useMemo(() => {
    const list = (routeData as any)?.alerts ?? routeData?.hazard_alerts ?? [];
    return Array.isArray(list) ? list : [];
  }, [routeData]);
  const hazardSegments = useMemo(() => {
    return Array.isArray(routeData?.turn_by_turn)
      ? routeData.turn_by_turn.filter(step => step?.has_alert)
      : [];
  }, [routeData]);
  const showAllClear = alerts.length === 0 && hazardSegments.length === 0;

  useEffect(() => {
    console.log('Alerts screen data', {
      alertsLength: alerts?.length ?? 0,
      firstEvent: alerts?.[0]?.event || alerts?.[0]?.properties?.event || null,
      firstHeadline: alerts?.[0]?.headline || alerts?.[0]?.properties?.headline || null,
      hazardSegmentsLength: hazardSegments.length,
      filtersApplied: {
        severity: false,
        type: false,
        note: 'No client-side filtering applied to alerts payload.',
      },
    });
  }, [alerts, hazardSegments]);
  
  // Radar map state
  const [showRadarMap, setShowRadarMap] = useState(false);

  useEffect(() => {
    if (params.routeData) {
      try {
        const data = JSON.parse(params.routeData as string);
        setRouteData(data);
      } catch (e) {
        console.error('Error parsing route data:', e);
      }
    }
    setLoading(false);
  }, [params.routeData]);

  // Heartbeat: keep last_seen_at fresh while the route page is open
  useEffect(() => {
    let interval: ReturnType<typeof setInterval>;
    const sendHeartbeat = async () => {
      try {
        const pushToken = await AsyncStorage.getItem('expoPushToken');
        if (!pushToken) return;
        await axios.post(`${API_BASE}/api/notifications/route-monitor/heartbeat`, {
          push_token: pushToken,
        });
      } catch {
        // silently ignore — offline or no monitor registered yet
      }
    };
    sendHeartbeat();
    interval = setInterval(sendHeartbeat, 2 * 60 * 1000); // every 2 min
    return () => clearInterval(interval);
  }, []);

  // Follow-up: fetch NWS hazard alerts — keeps badge count live
  useEffect(() => {
    const routeId = routeData?.id;
    if (!routeId) return;
    axios
      .get(`${API_BASE}/api/route/weather/alerts/${routeId}`)
      .then((res) => {
        const payload = res.data || {};
        const fetched: HazardAlert[] = payload.alerts ?? payload.hazard_alerts ?? [];
        if (fetched.length > 0) {
          setRouteData((prev) =>
            prev
              ? { ...prev, hazard_alerts: fetched, alerts: fetched, hazard_status: 'ready' } as any
              : prev
          );
        }
      })
      .catch((e) => console.warn('Alerts follow-up failed:', e.message));
  }, [routeData?.id]);

  const speakSummary = async () => {
    if (!routeData) return;
    
    if (isSpeaking) {
      await Speech.stop();
      setIsSpeaking(false);
      return;
    }

    setIsSpeaking(true);
    
    const parts: string[] = [];
    parts.push(`Route from ${routeData.origin} to ${routeData.destination}.`);
    
    if (routeData.total_distance_miles) {
      parts.push(`Total distance: ${Math.round(routeData.total_distance_miles)} miles.`);
    }
    if (routeData.total_duration_minutes) {
      parts.push(`Estimated time: ${formatDuration(routeData.total_duration_minutes)}.`);
    }
    
    // Safety score
    if (routeData.safety_score) {
      parts.push(`Safety score: ${routeData.safety_score.overall_score} out of 100. Risk level: ${routeData.safety_score.risk_level}.`);
    }
    
    // Road conditions
    if (routeData.road_condition_summary) {
      parts.push(routeData.road_condition_summary);
    }
    
    // Reroute recommendation
    if (routeData.reroute_recommended && routeData.reroute_reason) {
      parts.push(`Warning! Reroute recommended. ${routeData.reroute_reason}`);
    }
    
    // Hazards
    if (alerts?.length > 0) {
      parts.push(`${alerts.length} weather hazards along your route.`);
      alerts.slice(0, 3).forEach(alert => {
        parts.push(`${alert.countdown_text}. ${alert.recommendation}`);
      });
    }
    
    Speech.speak(parts.join(' '), {
      language: 'en-US',
      rate: 0.9,
      onDone: () => setIsSpeaking(false),
      onError: () => setIsSpeaking(false),
    });
  };

  const openInMaps = () => {
    if (!routeData) return;
    const url = Platform.select({
      ios: `maps://app?saddr=${encodeURIComponent(routeData.origin)}&daddr=${encodeURIComponent(routeData.destination)}`,
      android: `google.navigation:q=${encodeURIComponent(routeData.destination)}`,
      default: `https://www.google.com/maps/dir/${encodeURIComponent(routeData.origin)}/${encodeURIComponent(routeData.destination)}`,
    });
    Linking.openURL(url);
  };

  const shareRoute = async () => {
    if (!routeData) return;
    
    let message = `🚗 ROUTECAST ROAD CONDITIONS\n\n`;
    message += `📍 ${routeData.origin} → ${routeData.destination}\n`;
    message += `📏 ${routeData.total_distance_miles} mi | ⏱ ${routeData.total_duration_minutes ? formatDuration(routeData.total_duration_minutes) : 'N/A'}\n\n`;
    
    if (routeData.safety_score) {
      message += `🛡 Safety Score: ${routeData.safety_score.overall_score}/100 (${routeData.safety_score.risk_level.toUpperCase()})\n`;
    }
    
    message += `\n🛣 Road Conditions:\n${routeData.road_condition_summary || 'Good conditions'}\n`;
    
    if (routeData.reroute_recommended) {
      message += `\n⚠️ REROUTE RECOMMENDED: ${routeData.reroute_reason}\n`;
    }
    
    try {
      if (Platform.OS === 'web' && navigator.clipboard) {
        await navigator.clipboard.writeText(message);
        alert('Copied to clipboard!');
      } else {
        await Share.share({ message, title: 'Routecast Road Conditions' });
      }
    } catch (e) {
      console.error('Share error:', e);
    }
  };

  if (loading) {
    return (
      <SafeAreaView style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#eab308" />
        <Text style={styles.loadingText}>Loading route conditions...</Text>
      </SafeAreaView>
    );
  }

  if (!routeData) {
    return (
      <SafeAreaView style={styles.errorContainer}>
        <Ionicons name="alert-circle" size={48} color="#ef4444" />
        <Text style={styles.errorText}>Unable to load route data</Text>
        <TouchableOpacity style={styles.backButton} onPress={() => router.back()}>
          <Text style={styles.backButtonText}>Go Back</Text>
        </TouchableOpacity>
      </SafeAreaView>
    );
  }

  const getSafetyColor = (score: number) => {
    if (score >= 80) return '#22c55e';
    if (score >= 60) return '#eab308';
    if (score >= 40) return '#f97316';
    return '#ef4444';
  };

  return (
    <SafeAreaView style={styles.container}>
      {/* Compact Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
          <Ionicons name="arrow-back" size={24} color="#fff" />
          <Text style={styles.backText}>Back</Text>
        </TouchableOpacity>
        <View style={styles.headerActions}>
          <TouchableOpacity onPress={() => setShowRadarMap(true)} style={styles.radarBtn}>
            <Ionicons name="radio-outline" size={18} color="#22c55e" />
            <Text style={styles.radarBtnText}>Radar</Text>
          </TouchableOpacity>
          <TouchableOpacity onPress={speakSummary} style={styles.speakBtn}>
            <Ionicons name={isSpeaking ? "stop-circle" : "volume-high"} size={22} color={isSpeaking ? "#ef4444" : "#60a5fa"} />
          </TouchableOpacity>
          <TouchableOpacity onPress={shareRoute} style={styles.shareBtn}>
            <Ionicons name="share-outline" size={22} color="#fff" />
          </TouchableOpacity>
        </View>
      </View>

      {/* Route Stats Bar */}
      <View style={styles.statsBar}>
        <View style={styles.statItem}>
          <Ionicons name="speedometer-outline" size={16} color="#60a5fa" />
          <Text style={styles.statValue}>{routeData.total_distance_miles ? `${Math.round(routeData.total_distance_miles)} mi` : '--'}</Text>
        </View>
        <View style={styles.statDivider} />
        <View style={styles.statItem}>
          <Ionicons name="time-outline" size={16} color="#60a5fa" />
          <Text style={styles.statValue}>{routeData.total_duration_minutes ? formatDuration(routeData.total_duration_minutes) : '--'}</Text>
        </View>
      </View>

      {/* Radar Map Modal */}
      {showRadarMap && (
        <Modal transparent animationType="slide">
          <View style={styles.radarModalOverlay}>
            <View style={styles.radarModalContent}>
              <View style={styles.radarHeader}>
                <View style={styles.radarHeaderLeft}>
                  <Ionicons name="radio-outline" size={24} color="#22c55e" />
                  <Text style={styles.radarTitle}>Live Weather Radar</Text>
                </View>
                <TouchableOpacity onPress={() => setShowRadarMap(false)}>
                  <Ionicons name="close" size={28} color="#fff" />
                </TouchableOpacity>
              </View>
              
              {Platform.OS === 'web' ? (
                <iframe
                  srcDoc={generateRadarMapHtml(
                    routeData.waypoints[Math.floor(routeData.waypoints.length / 2)]?.waypoint.lat || 39.8283,
                    routeData.waypoints[Math.floor(routeData.waypoints.length / 2)]?.waypoint.lon || -98.5795
                  )}
                  style={{ flex: 1, border: 'none', width: '100%', height: '100%', touchAction: 'none' }}
                  allowFullScreen
                />
              ) : (
                <WebView
                  source={{ html: generateRadarMapHtml(
                    routeData.waypoints[Math.floor(routeData.waypoints.length / 2)]?.waypoint.lat || 39.8283,
                    routeData.waypoints[Math.floor(routeData.waypoints.length / 2)]?.waypoint.lon || -98.5795
                  )}}
                  style={styles.radarWebView}
                  javaScriptEnabled={true}
                  domStorageEnabled={true}
                  scalesPageToFit={true}
                  scrollEnabled={false}
                  bounces={false}
                  overScrollMode="never"
                  nestedScrollEnabled={false}
                  setBuiltInZoomControls={false}
                  setDisplayZoomControls={false}
                />
              )}
            </View>
          </View>
        </Modal>
      )}

      {/* Reroute Warning */}
      {routeData.reroute_recommended && (
        <TouchableOpacity style={styles.rerouteWarning} onPress={openInMaps}>
          <View style={styles.rerouteIcon}>
            <Ionicons name="warning" size={24} color="#fff" />
          </View>
          <View style={styles.rerouteText}>
            <Text style={styles.rerouteTitle}>⚠️ REROUTE RECOMMENDED</Text>
            <Text style={styles.rerouteReason} numberOfLines={2}>{routeData.reroute_reason}</Text>
          </View>
          <Ionicons name="navigate" size={20} color="#fff" />
        </TouchableOpacity>
      )}

      {/* Features Row */}
      <View style={styles.proFeaturesRow}>
        {/* Boondockers */}
        <TouchableOpacity 
          style={styles.proFeatureCard}
          onPress={() => router.push('/boondockers')}
        >
          <View style={[styles.proFeatureIcon, { backgroundColor: '#8b4513' }]}>
            <Ionicons name="bonfire" size={20} color="#fff" />
          </View>
          <Text style={styles.proFeatureTitle}>Boondockers</Text>
        </TouchableOpacity>

        {/* Tractor Trailer */}
        <TouchableOpacity 
          style={styles.proFeatureCard}
          onPress={() => router.push('/tractor-trailer')}
        >
          <View style={[styles.proFeatureIcon, { backgroundColor: '#3b82f6' }]}>
            <Ionicons name="bus" size={20} color="#fff" />
          </View>
          <Text style={styles.proFeatureTitle}>Tractor Trailer</Text>
        </TouchableOpacity>

        {/* How To Use */}
        <TouchableOpacity 
          style={styles.proFeatureCard}
          onPress={() => router.push('/how-to-use')}
        >
          <View style={[styles.proFeatureIcon, { backgroundColor: '#8b5cf6' }]}>
            <Ionicons name="help-circle" size={20} color="#fff" />
          </View>
          <Text style={styles.proFeatureTitle}>How To Use</Text>
        </TouchableOpacity>
      </View>

      {/* Tabs */}
      <View style={styles.tabs}>
        <TouchableOpacity 
          style={[styles.tab, activeTab === 'conditions' && styles.tabActive]}
          onPress={() => setActiveTab('conditions')}
        >
          <Ionicons name="car" size={16} color={activeTab === 'conditions' ? '#eab308' : '#6b7280'} />
          <Text style={[styles.tabText, activeTab === 'conditions' && styles.tabTextActive]}>Road</Text>
        </TouchableOpacity>
        <TouchableOpacity 
          style={[styles.tab, activeTab === 'bridges' && styles.tabActive]}
          onPress={() => setActiveTab('bridges')}
        >
          <Ionicons name="git-commit-outline" size={16} color={activeTab === 'bridges' ? '#f59e0b' : '#6b7280'} />
          <Text style={[styles.tabText, activeTab === 'bridges' && styles.tabTextActive]}>Bridges</Text>
          {routeData.bridge_clearance_alerts && routeData.bridge_clearance_alerts.length > 0 && (
            <View style={[styles.tabBadge, { backgroundColor: '#f59e0b' }]}>
              <Text style={styles.tabBadgeText}>{routeData.bridge_clearance_alerts.length}</Text>
            </View>
          )}
        </TouchableOpacity>
        <TouchableOpacity 
          style={styles.tab}
          onPress={() => router.push({ pathname: '/route-alerts', params: { routeData: params.routeData as string } })}
        >
          <Ionicons name="warning" size={16} color={activeTab === 'alerts' ? '#ef4444' : '#6b7280'} />
          <Text style={[styles.tabText, activeTab === 'alerts' && styles.tabTextActive]}>Alerts</Text>
          {alerts?.length > 0 && (
            <View style={styles.tabBadge}>
              <Text style={styles.tabBadgeText}>{alerts.length}</Text>
            </View>
          )}
        </TouchableOpacity>
        <TouchableOpacity 
          style={[styles.tab, activeTab === 'directions' && styles.tabActive]}
          onPress={() => setActiveTab('directions')}
        >
          <Ionicons name="navigate" size={16} color={activeTab === 'directions' ? '#eab308' : '#6b7280'} />
          <Text style={[styles.tabText, activeTab === 'directions' && styles.tabTextActive]}>Nav</Text>
        </TouchableOpacity>
      </View>

      {/* Content */}
      <ScrollView style={styles.content} showsVerticalScrollIndicator={false}>
        
        {/* Road Conditions Tab */}
        {activeTab === 'conditions' && (
          <View style={styles.conditionsTab}>
            {/* Road Condition Summary */}
            <View style={styles.conditionSummary}>
              <Text style={styles.conditionSummaryText}>
                {routeData.road_condition_summary || '✅ Good road conditions expected'}
              </Text>
            </View>

            {/* Trucker / Bridge Warnings – compact callout; full detail in Alerts screen */}
            {(routeData.trucker_warnings?.length > 0 || routeData.bridge_clearance_alerts?.length > 0) && (
              <TouchableOpacity
                style={styles.truckerBox}
                onPress={() => router.push({ pathname: '/route-alerts', params: { routeData: params.routeData as string } })}
                activeOpacity={0.8}
              >
                <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
                  <Text style={styles.truckerTitle}>🚛 TRUCKER ALERTS</Text>
                  <Text style={{ color: '#f59e0b', fontSize: 12, fontWeight: '600' }}>View All →</Text>
                </View>
                {routeData.bridge_clearance_alerts && routeData.bridge_clearance_alerts.length > 0 && (
                  <Text style={styles.truckerWarning}>
                    ⚠️ {routeData.bridge_clearance_alerts.length} low-clearance bridge{routeData.bridge_clearance_alerts.length > 1 ? 's' : ''} on route
                  </Text>
                )}
                {routeData.trucker_warnings?.slice(0, 2).map((warning: string, idx: number) => (
                  <Text key={idx} style={styles.truckerWarning}>{warning}</Text>
                ))}
                {(routeData.trucker_warnings?.length ?? 0) > 2 && (
                  <Text style={{ color: '#9ca3af', fontSize: 12, marginTop: 3 }}>
                    +{(routeData.trucker_warnings?.length ?? 0) - 2} more in Alerts
                  </Text>
                )}
              </TouchableOpacity>
            )}

            {/* Waypoint Road Conditions */}
            <Text style={styles.sectionTitle}>🛣️ Road Conditions Along Route</Text>
            <Text style={styles.sectionSubtitle}>Weather-based road surface conditions</Text>
            {routeData.waypoints.map((wp, index) => {
              // Derive road condition from weather ONLY (no alerts shown here)
              const temp = wp.weather?.temperature || 50;
              const conditions = (wp.weather?.conditions || '').toLowerCase();
              const windSpeed = wp.weather?.wind_speed ? parseInt(wp.weather.wind_speed) : 0;
              
              let condIcon = '✓';
              let condLabel = 'DRY';
              let condColor = '#22c55e';
              let condDesc = 'Clear';
              let roadSurface = 'Normal driving conditions';
              
              // Road conditions based ONLY on weather - NO alerts here
              if (temp <= 32 && (conditions.includes('rain') || conditions.includes('freezing') || conditions.includes('drizzle'))) {
                condIcon = '🧊';
                condLabel = 'ICY';
                condColor = '#ef4444';
                condDesc = `Black ice likely`;
                roadSurface = `${temp}°F - Reduce speed significantly`;
              } else if (temp <= 32 && conditions.includes('snow')) {
                condIcon = '❄️';
                condLabel = 'SNOW';
                condColor = '#60a5fa';
                condDesc = `Snow-covered`;
                roadSurface = `${temp}°F - Use caution`;
              } else if (temp > 32 && temp <= 40 && conditions.includes('snow')) {
                condIcon = '🌨️';
                condLabel = 'SLUSH';
                condColor = '#f59e0b';
                condDesc = `Slushy`;
                roadSurface = `${temp}°F - Reduced traction`;
              } else if (conditions.includes('fog') || conditions.includes('mist')) {
                condIcon = '🌫️';
                condLabel = 'FOG';
                condColor = '#9ca3af';
                condDesc = 'Low visibility';
                roadSurface = 'Use low beams';
              } else if (conditions.includes('rain') || conditions.includes('shower') || conditions.includes('drizzle')) {
                condIcon = '💧';
                condLabel = 'WET';
                condColor = '#3b82f6';
                condDesc = 'Wet roads';
                roadSurface = 'Watch for hydroplaning';
              } else if (conditions.includes('thunder') || conditions.includes('storm')) {
                condIcon = '⛈️';
                condLabel = 'STORM';
                condColor = '#7c3aed';
                condDesc = 'Storm conditions';
                roadSurface = 'Heavy rain possible';
              } else if (windSpeed > 30) {
                condIcon = '💨';
                condLabel = 'WINDY';
                condColor = '#f59e0b';
                condDesc = `Windy - ${windSpeed} mph`;
                roadSurface = 'Watch for crosswinds';
              }
              
              const mileMarker = Math.round(wp.waypoint.distance_from_start || 0);
              const locationName = wp.waypoint.name || 'Unknown';
              
              return (
                <View key={index} style={styles.conditionCard}>
                  <View style={styles.conditionCardMain}>
                    <View style={styles.mileMarkerBox}>
                      <Text style={styles.mileMarkerLabel}>MILE</Text>
                      <Text style={styles.mileMarkerNumber}>{mileMarker}</Text>
                    </View>
                    <View style={[styles.conditionBadge, { backgroundColor: condColor }]}>
                      <Text style={styles.conditionIcon}>{condIcon}</Text>
                      <Text style={styles.conditionLabel}>{condLabel}</Text>
                    </View>
                    <View style={styles.conditionInfo}>
                      <Text style={styles.conditionLocation} numberOfLines={1}>
                        {locationName}
                      </Text>
                      <Text style={styles.conditionDesc}>{condDesc}</Text>
                      <Text style={styles.roadSurface}>{roadSurface}</Text>
                      <Text style={styles.conditionWeather}>
                        {wp.weather?.temperature}°F • {wp.weather?.conditions || 'Clear'}
                      </Text>
                    </View>
                  </View>
                </View>
              );
            })}
          </View>
        )}

        {/* Bridge Height Hazards Tab */}
        {activeTab === 'bridges' && (
          <View style={styles.bridgesTab}>
            <Text style={styles.sectionTitle}>Bridge Height Hazards</Text>
            <Text style={styles.sectionSubtitle}>Low clearances that may affect your vehicle</Text>
            
            {routeData.bridge_clearance_alerts && routeData.bridge_clearance_alerts.length > 0 ? (
              <>
                {routeData.bridge_clearance_alerts.map((alert, index) => (
                  <View key={index} style={styles.bridgeCard}>
                    <View style={styles.bridgeHeader}>
                      <View style={styles.bridgeIconBox}>
                        <Ionicons name="warning" size={24} color="#f59e0b" />
                      </View>
                      <View style={styles.bridgeInfo}>
                        <Text style={styles.bridgeName}>{alert.bridge_name}</Text>
                        <Text style={styles.bridgeDistance}>{Math.round(alert.distance_miles)} miles ahead</Text>
                      </View>
                    </View>
                    
                    <View style={styles.bridgeClearanceRow}>
                      <View style={styles.clearanceBox}>
                        <Text style={styles.clearanceLabel}>CLEARANCE</Text>
                        <Text style={styles.clearanceValue}>{alert.clearance_ft.toFixed(1)} ft</Text>
                      </View>
                      <View style={styles.clearanceDivider} />
                      <View style={styles.clearanceBox}>
                        <Text style={styles.clearanceLabel}>YOUR HEIGHT</Text>
                        <Text style={styles.clearanceValueDanger}>{alert.vehicle_height_ft.toFixed(1)} ft</Text>
                      </View>
                    </View>
                    
                    <View style={styles.bridgeWarning}>
                      <Ionicons name="alert-circle" size={18} color="#fecaca" />
                      <Text style={styles.bridgeWarningText}>{alert.warning}</Text>
                    </View>
                  </View>
                ))}
              </>
            ) : (
              <View style={styles.noBridgeAlerts}>
                <Ionicons name="checkmark-circle" size={64} color="#22c55e" />
                <Text style={styles.noBridgeTitle}>All Clear!</Text>
                <Text style={styles.noBridgeText}>
                  {routeData.trucker_warnings?.length > 0 
                    ? "No low bridges detected for your vehicle height."
                    : "Enable Trucker Mode and enter your vehicle height on the home screen to see bridge clearance alerts."}
                </Text>
              </View>
            )}
            
            <View style={styles.bridgeDisclaimer}>
              <Ionicons name="information-circle" size={18} color="#6b7280" />
              <Text style={styles.bridgeDisclaimerText}>
                Bridge data is for reference only. Always verify with current signage. Some temporary restrictions may not be reflected.
              </Text>
            </View>
          </View>
        )}

        {/* Turn-by-Turn Directions Tab */}
        {activeTab === 'directions' && (
          <View style={styles.directionsTab}>
            <TouchableOpacity style={styles.openMapsBtn} onPress={openInMaps}>
              <Ionicons name="navigate" size={20} color="#fff" />
              <Text style={styles.openMapsText}>Open in Maps App</Text>
            </TouchableOpacity>

            <Text style={styles.sectionTitle}>Turn-by-Turn with Road Conditions</Text>
            
            {routeData.turn_by_turn && routeData.turn_by_turn.length > 0 ? (
              routeData.turn_by_turn.map((step, index) => (
                <View key={index} style={[styles.stepCard, step.has_alert && styles.stepCardAlert]}>
                  <View style={styles.stepIcon}>
                    <Ionicons 
                      name={getManeuverIcon(step.maneuver) as any} 
                      size={20} 
                      color={step.has_alert ? '#ef4444' : '#60a5fa'} 
                    />
                  </View>
                  <View style={styles.stepContent}>
                    <Text style={styles.stepInstruction}>{step.instruction}</Text>
                    <Text style={styles.stepRoad}>{step.road_name}</Text>
                    <View style={styles.stepMeta}>
                      <Text style={styles.stepDistance}>{step.distance_miles} mi</Text>
                      {step.road_condition && (
                        <View style={[styles.stepConditionBadge, { backgroundColor: step.road_condition.color }]}>
                          <Text style={styles.stepConditionText}>
                            {step.road_condition.icon} {step.road_condition.label}
                          </Text>
                        </View>
                      )}
                      {step.temperature && (
                        <Text style={styles.stepTemp}>{step.temperature}°F</Text>
                      )}
                    </View>
                  </View>
                </View>
              ))
            ) : (
              <View style={styles.noDirections}>
                <Ionicons name="navigate-outline" size={48} color="#6b7280" />
                <Text style={styles.noDirectionsText}>Tap "Open in Maps App" for navigation</Text>
              </View>
            )}
          </View>
        )}

        {/* Alerts Tab – navigates to full-screen route-alerts.tsx */}

                <View style={styles.bottomPadding} />
      </ScrollView>

      {/* Bottom Action Bar */}
      <View style={styles.actionBar}>
        <TouchableOpacity style={styles.actionBtn} onPress={shareRoute}>
          <Ionicons name="share-outline" size={22} color="#fff" />
          <Text style={styles.actionText}>Share</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.navBtn} onPress={openInMaps}>
          <Ionicons name="navigate" size={24} color="#fff" />
          <Text style={styles.navText}>Start Navigation</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.actionBtn} onPress={speakSummary}>
          <Ionicons name={isSpeaking ? "stop" : "volume-high"} size={22} color="#fff" />
          <Text style={styles.actionText}>{isSpeaking ? 'Stop' : 'Listen'}</Text>
        </TouchableOpacity>
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
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingText: {
    color: '#a1a1aa',
    marginTop: 16,
    fontSize: 14,
  },
  errorContainer: {
    flex: 1,
    backgroundColor: '#18181b',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 20,
  },
  errorText: {
    color: '#ef4444',
    fontSize: 16,
    marginTop: 12,
  },
  backButton: {
    marginTop: 20,
    paddingHorizontal: 20,
    paddingVertical: 10,
    backgroundColor: '#3f3f46',
    borderRadius: 8,
  },
  backButtonText: {
    color: '#fff',
    fontSize: 14,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 12,
    paddingVertical: 10,
    backgroundColor: '#27272a',
    borderBottomWidth: 1,
    borderBottomColor: '#3f3f46',
  },
  backBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 6,
    gap: 4,
  },
  backText: {
    color: '#60a5fa',
    fontSize: 14,
    fontWeight: '600',
  },
  headerActions: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  shareBtn: {
    padding: 6,
  },
  statsBar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#1f1f23',
    paddingVertical: 10,
    paddingHorizontal: 16,
    gap: 16,
  },
  statItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  statValue: {
    color: '#fff',
    fontSize: 14,
    fontWeight: '600',
  },
  statDivider: {
    width: 1,
    height: 16,
    backgroundColor: '#3f3f46',
  },
  headerCenter: {
    flex: 1,
    marginHorizontal: 12,
  },
  headerTitle: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '700',
  },
  headerSubtitle: {
    color: '#a1a1aa',
    fontSize: 12,
    marginTop: 2,
  },
  speakBtn: {
    padding: 6,
  },
  safetyBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#27272a',
    marginHorizontal: 16,
    marginTop: 12,
    borderRadius: 12,
    padding: 14,
    borderLeftWidth: 5,
  },
  safetyLeft: {
    alignItems: 'center',
    marginRight: 16,
  },
  safetyScore: {
    fontSize: 32,
    fontWeight: '800',
  },
  safetyLabel: {
    color: '#6b7280',
    fontSize: 10,
    fontWeight: '600',
  },
  safetyRight: {
    flex: 1,
  },
  safetyRisk: {
    color: '#fff',
    fontSize: 14,
    fontWeight: '700',
  },
  safetyVehicle: {
    color: '#a1a1aa',
    fontSize: 12,
    marginTop: 2,
  },
  rerouteWarning: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#b91c1c',
    marginHorizontal: 16,
    marginTop: 12,
    borderRadius: 12,
    padding: 14,
  },
  rerouteIcon: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: 'rgba(255,255,255,0.2)',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  rerouteText: {
    flex: 1,
  },
  rerouteTitle: {
    color: '#fff',
    fontSize: 14,
    fontWeight: '800',
  },
  rerouteReason: {
    color: '#fecaca',
    fontSize: 12,
    marginTop: 2,
  },
  conditionSummary: {
    backgroundColor: '#27272a',
    marginHorizontal: 16,
    marginTop: 12,
    borderRadius: 10,
    padding: 12,
  },
  conditionSummaryText: {
    color: '#e4e4e7',
    fontSize: 13,
    textAlign: 'center',
  },
  tabs: {
    flexDirection: 'row',
    marginHorizontal: 16,
    marginTop: 12,
    backgroundColor: '#27272a',
    borderRadius: 10,
    padding: 4,
  },
  tab: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingVertical: 10,
    borderRadius: 8,
  },
  tabActive: {
    backgroundColor: '#3f3f46',
  },
  tabText: {
    color: '#6b7280',
    fontSize: 13,
    fontWeight: '600',
  },
  tabTextActive: {
    color: '#eab308',
  },
  tabBadge: {
    backgroundColor: '#ef4444',
    borderRadius: 10,
    minWidth: 18,
    height: 18,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 4,
  },
  tabBadgeText: {
    color: '#fff',
    fontSize: 10,
    fontWeight: '700',
  },
  content: {
    flex: 1,
    paddingHorizontal: 16,
    marginTop: 12,
  },
  sectionTitle: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '700',
    marginBottom: 4,
  },
  sectionSubtitle: {
    color: '#6b7280',
    fontSize: 12,
    marginBottom: 12,
  },
  conditionsTab: {},
  truckerBox: {
    backgroundColor: '#422006',
    borderRadius: 12,
    padding: 14,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: '#f59e0b',
  },
  truckerTitle: {
    color: '#fbbf24',
    fontSize: 14,
    fontWeight: '700',
    marginBottom: 8,
  },
  truckerWarning: {
    color: '#fde68a',
    fontSize: 12,
    marginBottom: 4,
  },
  conditionCard: {
    backgroundColor: '#27272a',
    borderRadius: 10,
    padding: 10,
    marginBottom: 8,
  },
  conditionCardExpanded: {
    borderWidth: 1,
    borderColor: '#fbbf24',
  },
  conditionCardMain: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  expandIndicator: {
    padding: 4,
  },
  alertDetailBox: {
    marginTop: 12,
    padding: 12,
    backgroundColor: '#1f1f23',
    borderRadius: 8,
    borderLeftWidth: 3,
    borderLeftColor: '#fbbf24',
  },
  alertDetailHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 8,
  },
  alertDetailTitle: {
    color: '#fbbf24',
    fontSize: 14,
    fontWeight: '700',
  },
  alertDetailDesc: {
    color: '#d4d4d8',
    fontSize: 13,
    lineHeight: 20,
  },
  alertDetailInstruction: {
    marginTop: 10,
    padding: 10,
    backgroundColor: '#27272a',
    borderRadius: 6,
  },
  alertDetailInstructionLabel: {
    color: '#22c55e',
    fontSize: 11,
    fontWeight: '700',
    marginBottom: 4,
  },
  alertDetailInstructionText: {
    color: '#a1a1aa',
    fontSize: 12,
    lineHeight: 18,
  },
  alertDetailExpires: {
    marginTop: 8,
    color: '#6b7280',
    fontSize: 11,
  },
  mileMarkerBox: {
    backgroundColor: '#3f3f46',
    borderRadius: 8,
    paddingVertical: 6,
    paddingHorizontal: 8,
    alignItems: 'center',
    minWidth: 50,
  },
  mileMarkerLabel: {
    color: '#6b7280',
    fontSize: 8,
    fontWeight: '700',
    letterSpacing: 1,
  },
  mileMarkerNumber: {
    color: '#fff',
    fontSize: 18,
    fontWeight: '800',
  },
  conditionBadge: {
    width: 50,
    alignItems: 'center',
    paddingVertical: 6,
    borderRadius: 8,
    marginRight: 12,
  },
  conditionIcon: {
    fontSize: 20,
  },
  conditionLabel: {
    color: '#fff',
    fontSize: 9,
    fontWeight: '700',
    marginTop: 2,
  },
  conditionInfo: {
    flex: 1,
  },
  conditionLocation: {
    color: '#fff',
    fontSize: 14,
    fontWeight: '600',
  },
  conditionDesc: {
    color: '#fbbf24',
    fontSize: 13,
    fontWeight: '600',
    marginTop: 2,
  },
  roadSurface: {
    color: '#a1a1aa',
    fontSize: 11,
    marginTop: 2,
    fontStyle: 'italic',
  },
  conditionWeather: {
    color: '#6b7280',
    fontSize: 10,
    marginTop: 4,
  },
  conditionMeta: {
    alignItems: 'flex-end',
  },
  conditionMiles: {
    color: '#60a5fa',
    fontSize: 12,
    fontWeight: '600',
  },
  directionsTab: {},
  openMapsBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#2563eb',
    borderRadius: 10,
    padding: 14,
    marginBottom: 16,
    gap: 8,
  },
  openMapsText: {
    color: '#fff',
    fontSize: 15,
    fontWeight: '700',
  },
  stepCard: {
    flexDirection: 'row',
    backgroundColor: '#27272a',
    borderRadius: 10,
    padding: 12,
    marginBottom: 8,
  },
  stepCardAlert: {
    borderLeftWidth: 3,
    borderLeftColor: '#ef4444',
  },
  stepIcon: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: '#3f3f46',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  stepContent: {
    flex: 1,
  },
  stepInstruction: {
    color: '#fff',
    fontSize: 14,
    fontWeight: '600',
  },
  stepRoad: {
    color: '#a1a1aa',
    fontSize: 12,
    marginTop: 2,
  },
  stepMeta: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 6,
    gap: 8,
  },
  stepDistance: {
    color: '#6b7280',
    fontSize: 11,
  },
  stepConditionBadge: {
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
  },
  stepConditionText: {
    color: '#fff',
    fontSize: 10,
    fontWeight: '600',
  },
  stepTemp: {
    color: '#eab308',
    fontSize: 11,
    fontWeight: '600',
  },
  noDirections: {
    alignItems: 'center',
    paddingVertical: 40,
  },
  noDirectionsText: {
    color: '#6b7280',
    fontSize: 14,
    marginTop: 12,
  },
  alertsTab: {},
  // ── WeatherBug-style alert cards ────────────────────────────────────────
  wbTabHeader: {
    marginBottom: 12,
  },
  wbLoadingRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginTop: 6,
  },
  wbLoadingText: {
    color: '#f59e0b',
    fontSize: 12,
  },
  wbCard: {
    borderRadius: 12,
    marginBottom: 12,
    overflow: 'hidden',
    backgroundColor: '#1e2433',
    borderWidth: 1,
    borderColor: '#374151',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.35,
    shadowRadius: 5,
    elevation: 4,
  },
  wbBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 14,
    paddingVertical: 13,
    gap: 12,
  },
  wbBannerTextCol: {
    flex: 1,
  },
  wbEventTitle: {
    color: '#fff',
    fontSize: 15,
    fontWeight: '800',
    letterSpacing: 0.4,
  },
  wbIssuedBy: {
    color: 'rgba(255,255,255,0.75)',
    fontSize: 11,
    marginTop: 3,
  },
  wbBody: {
    paddingHorizontal: 14,
    paddingTop: 10,
    paddingBottom: 10,
    gap: 7,
  },
  wbTimeRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 5,
  },
  wbTimeText: {
    color: '#d1d5db',
    fontSize: 11.5,
    flex: 1,
    lineHeight: 17,
  },
  wbAreaRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 5,
  },
  wbAreaText: {
    color: '#d1d5db',
    fontSize: 11.5,
    flex: 1,
    lineHeight: 17,
  },
  wbHeadline: {
    color: '#f9fafb',
    fontSize: 13,
    lineHeight: 19,
    marginTop: 4,
  },
  wbExpandedSection: {
    marginTop: 6,
    paddingTop: 10,
    borderTopWidth: 1,
    borderTopColor: '#374151',
  },
  wbSectionLabel: {
    color: '#fbbf24',
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 0.8,
    marginBottom: 5,
    textTransform: 'uppercase',
  },
  wbSectionText: {
    color: '#e5e7eb',
    fontSize: 12.5,
    lineHeight: 19,
  },
  wbActionRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 7,
    marginTop: 10,
    backgroundColor: 'rgba(34,197,94,0.1)',
    borderRadius: 8,
    padding: 10,
  },
  wbActionText: {
    color: '#bbf7d0',
    fontSize: 12,
    flex: 1,
    lineHeight: 18,
  },
  wbFooter: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    marginTop: 8,
    paddingTop: 8,
    borderTopWidth: 1,
    borderTopColor: '#374151',
  },
  wbFooterItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 3,
  },
  wbFooterText: {
    color: '#6b7280',
    fontSize: 11,
  },
  wbLevelPill: {
    paddingHorizontal: 9,
    paddingVertical: 4,
    borderRadius: 12,
  },
  wbLevelPillText: {
    color: '#fff',
    fontSize: 10,
    fontWeight: '800',
    letterSpacing: 0.6,
  },
  noAlerts: {
    alignItems: 'center',
    paddingVertical: 40,
  },
  hazardSegmentsOnly: {
    alignItems: 'center',
    paddingVertical: 40,
    gap: 8,
  },
  hazardSegmentsTitle: {
    color: '#f59e0b',
    fontSize: 18,
    fontWeight: '700',
  },
  hazardSegmentsText: {
    color: '#fbbf24',
    fontSize: 14,
    textAlign: 'center',
    paddingHorizontal: 24,
  },
  noAlertsTitle: {
    color: '#22c55e',
    fontSize: 20,
    fontWeight: '700',
    marginTop: 12,
  },
  noAlertsText: {
    color: '#6b7280',
    fontSize: 14,
    marginTop: 4,
  },
  bottomPadding: {
    height: 100,
  },
  actionBar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-around',
    backgroundColor: '#27272a',
    paddingVertical: 12,
    paddingHorizontal: 16,
    borderTopWidth: 1,
    borderTopColor: '#3f3f46',
  },
  actionBtn: {
    alignItems: 'center',
    padding: 8,
  },
  actionText: {
    color: '#a1a1aa',
    fontSize: 11,
    marginTop: 4,
  },
  navBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#2563eb',
    paddingVertical: 12,
    paddingHorizontal: 24,
    borderRadius: 25,
    gap: 8,
  },
  navText: {
    color: '#fff',
    fontSize: 14,
    fontWeight: '700',
  },
  // Radar Map styles
  radarBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#14532d',
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 16,
    marginRight: 8,
    gap: 4,
  },
  radarBtnText: {
    color: '#22c55e',
    fontSize: 12,
    fontWeight: '600',
  },
  radarModalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.9)',
  },
  radarModalContent: {
    flex: 1,
    backgroundColor: '#18181b',
  },
  radarHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 16,
    backgroundColor: '#27272a',
    borderBottomWidth: 1,
    borderBottomColor: '#3f3f46',
  },
  radarHeaderLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  radarTitle: {
    color: '#fff',
    fontSize: 18,
    fontWeight: '700',
  },
  radarWebView: {
    flex: 1,
  },
  // Chat styles
  chatFab: {
    position: 'absolute',
    right: 20,
    bottom: 100,
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: '#eab308',
    justifyContent: 'center',
    alignItems: 'center',
    elevation: 5,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.3,
    shadowRadius: 4,
  },
  chatModalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.7)',
    justifyContent: 'flex-end',
  },
  chatModalContent: {
    backgroundColor: '#1f1f23',
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    height: '75%',
    paddingBottom: 20,
  },
  chatHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#3f3f46',
  },
  chatHeaderLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  chatTitle: {
    color: '#fff',
    fontSize: 18,
    fontWeight: '700',
  },
  chatMessages: {
    flex: 1,
    padding: 16,
  },
  chatWelcome: {
    alignItems: 'center',
    paddingVertical: 30,
  },
  chatWelcomeText: {
    color: '#fff',
    fontSize: 18,
    fontWeight: '600',
  },
  chatWelcomeSubtext: {
    color: '#6b7280',
    fontSize: 14,
    marginTop: 8,
    textAlign: 'center',
  },
  chatBubble: {
    maxWidth: '85%',
    padding: 12,
    borderRadius: 16,
    marginBottom: 10,
  },
  userBubble: {
    backgroundColor: '#2563eb',
    alignSelf: 'flex-end',
    borderBottomRightRadius: 4,
  },
  aiBubble: {
    backgroundColor: '#3f3f46',
    alignSelf: 'flex-start',
    borderBottomLeftRadius: 4,
  },
  chatBubbleText: {
    color: '#fff',
    fontSize: 14,
    lineHeight: 20,
  },
  chatTyping: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    padding: 8,
  },
  chatTypingText: {
    color: '#6b7280',
    fontSize: 12,
  },
  chatSuggestions: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    padding: 12,
    gap: 8,
    borderTopWidth: 1,
    borderTopColor: '#3f3f46',
  },
  chatSuggestionBtn: {
    backgroundColor: '#27272a',
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: '#3f3f46',
  },
  chatSuggestionText: {
    color: '#a1a1aa',
    fontSize: 12,
  },
  listeningIndicator: {
    alignItems: 'center',
    paddingVertical: 8,
  },
  listeningText: {
    color: '#fecaca',
    fontSize: 14,
    fontWeight: '600',
  },
  chatInputRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingTop: 8,
    gap: 10,
  },
  chatInput: {
    flex: 1,
    backgroundColor: '#27272a',
    borderRadius: 24,
    paddingHorizontal: 16,
    paddingVertical: 12,
    color: '#fff',
    fontSize: 14,
    borderWidth: 1,
    borderColor: '#3f3f46',
  },
  chatSendBtn: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: '#eab308',
    justifyContent: 'center',
    alignItems: 'center',
  },
  chatSendBtnDisabled: {
    backgroundColor: '#3f3f46',
  },
  micBtn: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: '#3f3f46',
    justifyContent: 'center',
    alignItems: 'center',
  },
  micBtnActive: {
    backgroundColor: '#7f1d1d',
  },
  // Features Row Styles
  proFeaturesRow: {
    flexDirection: 'row',
    gap: 12,
    paddingHorizontal: 16,
    marginTop: 12,
    marginBottom: 8,
  },
  proFeatureCard: {
    flex: 1,
    backgroundColor: '#1a1a1a',
    borderRadius: 12,
    padding: 12,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#27272a',
  },
  proFeatureIcon: {
    width: 40,
    height: 40,
    borderRadius: 20,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 8,
  },
  proFeatureTitle: {
    color: '#fff',
    fontSize: 13,
    fontWeight: '600',
    textAlign: 'center',
  },
  // Bridge Height Hazards Tab Styles
  bridgesTab: {},
  bridgeCard: {
    backgroundColor: '#422006',
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: '#f59e0b',
  },
  bridgeHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 12,
  },
  bridgeIconBox: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: 'rgba(245, 158, 11, 0.2)',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  bridgeInfo: {
    flex: 1,
  },
  bridgeName: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '700',
  },
  bridgeDistance: {
    color: '#fbbf24',
    fontSize: 13,
    marginTop: 2,
  },
  bridgeClearanceRow: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(0,0,0,0.3)',
    borderRadius: 10,
    padding: 12,
    marginBottom: 12,
  },
  clearanceBox: {
    flex: 1,
    alignItems: 'center',
  },
  clearanceLabel: {
    color: '#9ca3af',
    fontSize: 10,
    fontWeight: '600',
    letterSpacing: 0.5,
    marginBottom: 4,
  },
  clearanceValue: {
    color: '#fbbf24',
    fontSize: 24,
    fontWeight: '800',
  },
  clearanceValueDanger: {
    color: '#ef4444',
    fontSize: 24,
    fontWeight: '800',
  },
  clearanceDivider: {
    width: 1,
    height: 40,
    backgroundColor: '#3f3f46',
  },
  bridgeWarning: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 8,
    backgroundColor: '#7f1d1d',
    borderRadius: 8,
    padding: 12,
  },
  bridgeWarningText: {
    color: '#fecaca',
    fontSize: 13,
    flex: 1,
    lineHeight: 18,
  },
  noBridgeAlerts: {
    alignItems: 'center',
    paddingVertical: 40,
    backgroundColor: '#27272a',
    borderRadius: 12,
  },
  noBridgeTitle: {
    color: '#22c55e',
    fontSize: 20,
    fontWeight: '700',
    marginTop: 12,
  },
  noBridgeText: {
    color: '#6b7280',
    fontSize: 14,
    marginTop: 8,
    textAlign: 'center',
    paddingHorizontal: 20,
    lineHeight: 20,
  },
  bridgeDisclaimer: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 8,
    backgroundColor: '#1c1917',
    borderRadius: 8,
    padding: 12,
    marginTop: 8,
  },
  bridgeDisclaimerText: {
    color: '#6b7280',
    fontSize: 12,
    flex: 1,
    lineHeight: 16,
  },
});
