import React, { useMemo, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Platform,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useLocalSearchParams, router } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';

function pickAlertDetails(a: any): string {
  const p = a?.properties ?? a ?? {};
  const clean = (s?: string) => (typeof s === 'string' ? s.trim() : '');
  return clean(p.description) || clean(p.summary) || clean(p.headline) || '';
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
  properties?: {
    event?: string;
    headline?: string;
    description?: string;
    instruction?: string;
    areaDesc?: string;
    onset?: string;
    expires?: string;
  };
  road_name?: string;
  span_miles?: number;
  alert_level?: string;
  driver_action?: string;
}

interface TruckerWarning {
  warning: string;
}

export default function WeatherAlertsScreen() {
  const insets = useSafeAreaInsets();
  const goHome = () => router.replace('/');
  const params = useLocalSearchParams();
  const routeData = params.routeData ? JSON.parse(params.routeData as string) : null;
  const bridgeAlertsEnabled = params.bridgeAlertsEnabled === 'true';
  const [expandedBridge, setExpandedBridge] = useState<Set<number>>(new Set());
  
  const alerts = useMemo(() => {
    const list =
      (routeData?.alerts as HazardAlert[] | undefined) ||
      (routeData?.hazard_alerts as HazardAlert[] | undefined) ||
      [];
    return Array.isArray(list) ? list : [];
  }, [routeData]);

  const severityFromConditions = (alert: HazardAlert) => {
    const tempMatch = pickAlertDetails(alert).match(/(-?\d{1,3})\s*°?F/i);
    const temp = tempMatch ? parseInt(tempMatch[1], 10) : null;
    const type = (alert.type || '').toLowerCase();
    const severity = (alert.severity || '').toLowerCase();

    if (type === 'ice' || type === 'whiteout' || (temp !== null && temp < 15)) return { label: 'CRITICAL', emoji: '🔴' };
    if ((type === 'snow' && temp !== null && temp < 25) || type === 'ice') return { label: 'HIGH', emoji: '🔴' };
    if (type === 'snow' && temp !== null && temp >= 25 && temp <= 32) return { label: 'MEDIUM-HIGH', emoji: '🟠' };
    if (temp !== null && temp >= 30 && temp <= 35 && ['snow', 'rain'].includes(type)) return { label: 'CAUTION', emoji: '🟡' };
    if (severity === 'extreme') return { label: 'CRITICAL', emoji: '🔴' };
    if (severity === 'high') return { label: 'HIGH', emoji: '🔴' };
    if (severity === 'medium') return { label: 'MEDIUM-HIGH', emoji: '🟠' };
    return { label: 'CAUTION', emoji: '🟡' };
  };

  const inferPrecip = (alert: HazardAlert) => {
    const type = (alert.type || '').toLowerCase();
    if (!type) return null;
    const detail = pickAlertDetails(alert).toLowerCase();
    const intensity = detail.includes('heavy') ? 'Heavy' : detail.includes('moderate') ? 'Moderate' : detail.includes('light') ? 'Light' : null;
    const label = type === 'ice' ? 'Ice' : type === 'snow' || type === 'whiteout' ? 'Snow' : type === 'rain' ? 'Rain' : type === 'wind' ? 'Wind' : type;
    return { label, intensity };
  };

  const inferWind = (alert: HazardAlert) => {
    const detail = pickAlertDetails(alert);
    const windMatch = detail.match(/(\d{1,3})\s?mph/gi);
    if (!windMatch) return null;
    const speeds = windMatch.map((m) => parseInt(m, 10)).filter((n) => !Number.isNaN(n));
    if (!speeds.length) return null;
    const max = Math.max(...speeds);
    return { speed: max, gust: speeds.length > 1 ? Math.max(...speeds.slice(1)) : null };
  };

  const inferVisibility = (alert: HazardAlert) => {
    const detail = pickAlertDetails(alert).toLowerCase();
    if (!detail) return null;
    if (detail.includes('whiteout') || detail.includes('blizzard') || detail.includes('zero visibility')) return 'Severely Reduced';
    if (detail.includes('reduced visibility') || detail.includes('low visibility') || detail.includes('fog')) return 'Reduced';
    if (detail.includes('visibility')) return 'Reduced';
    return null;
  };

  const pickDriverAction = (alert: HazardAlert) => {
    if (alert.driver_action) return alert.driver_action;
    if (alert.recommendation) return alert.recommendation;
    const type = (alert.type || '').toLowerCase();
    if (type === 'ice') return 'Reduce speed, avoid sudden steering, and increase following distance by 8-10 seconds.';
    if (type === 'snow' || type === 'whiteout') return 'Slow to conditions, use low beams, and be prepared for rapid visibility drops.';
    if (type === 'rain') return 'Reduce speed on wet pavement and avoid hard braking on slick sections.';
    if (type === 'wind') return 'Keep both hands on the wheel and reduce speed, especially on exposed sections.';
    return 'Adjust speed to conditions and leave extra space.';
  };

  if (!routeData) {
    return (
      <View style={styles.container}>
        <View style={[styles.header, { paddingTop: Platform.OS === 'ios' ? insets.top + 8 : 16 }]}>
          <Text style={styles.headerTitle}>Weather Alerts</Text>
        </View>
        <View style={styles.errorContainer}>
          <Text style={styles.errorText}>No route data available</Text>
          <TouchableOpacity onPress={goHome} style={styles.errorHomeButton}>
            <Ionicons name="home" size={20} color="#fff" />
            <Text style={styles.errorHomeText}>Return to Home</Text>
          </TouchableOpacity>
        </View>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <View style={[styles.header, { paddingTop: Platform.OS === 'ios' ? insets.top + 8 : 16 }]}>
        <Text style={styles.headerTitle}>⚠️ Weather Alerts</Text>
      </View>

      <ScrollView style={styles.content} showsVerticalScrollIndicator={false}>
        {/* Route Context */}
        <View style={styles.routeContext}>
          <Text style={styles.routeContextTitle}>Your Route</Text>
          {/* Weather Alerts Section */}
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>⚠️ Weather Hazards on This Route</Text>
            <Text style={styles.sectionSubtitle}>Sorted by nearest hazard using live route weather data</Text>

            {alerts.length > 0 ? (
              alerts.map((alert: HazardAlert, index: number) => {
                const props = alert.properties || {};
                const eventTitle = alert.message || alert.event || props.event || alert.headline || 'Weather Alert';
                const subtitle = alert.recommendation || alert.driver_action || props.headline || '';
                const detailText = pickAlertDetails(alert);
                const severity = severityFromConditions(alert);
                const precip = inferPrecip(alert);
                const wind = inferWind(alert);
                const visibility = inferVisibility(alert);
                const roadName = alert.road_name || alert.location_name || 'Unknown road';
                const spanMiles = alert.span_miles;
                const driverAction = pickDriverAction(alert);
                const alertKey = alert.id || (alert as any).alert_id || (props as any).id || index;

                return (
                  <View key={alertKey} style={[styles.alertCard, styles.alertCardNew]}>
                    <Text style={styles.alertTitle}>
                      {severity.emoji} ALERT {index + 1} — {severity.label} ({roadName})
                    </Text>
                    <Text style={styles.alertCondition}>❄️ {eventTitle}</Text>
                    {subtitle ? <Text style={styles.alertSubtitle}>{subtitle}</Text> : null}

                    <View style={styles.conditionsBlock}>
                      <Text style={styles.blockTitle}>Conditions</Text>
                      {detailText ? <Text style={styles.detailLine}>{detailText}</Text> : null}
                      {precip ? (
                        <Text style={styles.metricLine}>
                          {precip.intensity ? `${precip.label}: ${precip.intensity}` : precip.label}
                        </Text>
                      ) : null}
                      {wind ? (
                        <Text style={styles.metricLine}>
                          Wind: {wind.speed} mph{wind.gust ? ` (gusts ${wind.gust}+)` : ''}
                        </Text>
                      ) : null}
                      {visibility ? <Text style={styles.metricLine}>Visibility: {visibility}</Text> : null}
                    </View>

                    <View style={styles.actionBlock}>
                      <Text style={styles.blockTitle}>✅ Driver Action</Text>
                      <Text style={styles.actionText}>{driverAction}</Text>
                    </View>

                    <View style={styles.footerMeta}>
                      <Text style={styles.metaLine}>📍 Location: {roadName}</Text>
                      {typeof spanMiles === 'number' ? (
                        <Text style={styles.metaLine}>🛣️ Affected Distance: {spanMiles.toFixed(1)} miles</Text>
                      ) : null}
                      <Text style={styles.metaLine}>⏱️ Time to Hazard: ~{alert.eta_minutes} min</Text>
                    </View>
                  </View>
                );
              })
            ) : (
              <View style={styles.noAlerts}>
                <Ionicons name="checkmark-circle" size={64} color="#22c55e" />
                <Text style={styles.noAlertsTitle}>All Clear!</Text>
                <Text style={styles.noAlertsText}>No significant hazards on your route</Text>
              </View>
            )}
          </View>

        {/* Bridge Alerts Section - Only show if enabled */}
        {bridgeAlertsEnabled && (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>🌉 Bridge Height Warnings</Text>
            <Text style={styles.sectionSubtitle}>Low clearance bridges on your route</Text>
          
            {routeData.trucker_warnings && routeData.trucker_warnings.length > 0 ? (
              routeData.trucker_warnings.map((warning: string, index: number) => {
                const isBridgeExpanded = expandedBridge.has(index);

                const toggle = () => {
                  const next = new Set(expandedBridge);
                  if (next.has(index)) next.delete(index);
                  else next.add(index);
                  setExpandedBridge(next);
                };

                return (
                  <TouchableOpacity
                    key={index}
                    style={[styles.bridgeAlertCard, isBridgeExpanded && styles.bridgeAlertCardExpanded]}
                    onPress={toggle}
                    activeOpacity={0.9}
                  >
                    <View style={styles.bridgeAlertHeader}>
                      <View style={styles.bridgeAlertIconContainer}>
                        <Text style={styles.bridgeAlertIcon}>🌉</Text>
                      </View>
                      <View style={styles.bridgeAlertInfo}>
                        <Text style={styles.bridgeAlertTitle}>Low Clearance Bridge</Text>
                        <Text style={styles.bridgeAlertSubtitle}>Bridge #{index + 1}</Text>
                      </View>
                      <Ionicons
                        name={isBridgeExpanded ? 'chevron-up' : 'chevron-down'}
                        size={20}
                        color="#eab308"
                      />
                    </View>

                    {isBridgeExpanded && (
                      <View style={styles.bridgeAlertDetails}>
                        <Text style={styles.bridgeAlertWarningText}>{warning}</Text>
                        <View style={styles.bridgeAlertTip}>
                          <Ionicons name="information-circle" size={16} color="#eab308" />
                          <Text style={styles.bridgeAlertTipText}>
                            Ensure your vehicle height is within safe limits before proceeding
                          </Text>
                        </View>
                      </View>
                    )}
                  </TouchableOpacity>
                );
              })
            ) : (
              <View style={styles.noAlerts}>
                <Ionicons name="checkmark-circle" size={64} color="#22c55e" />
                <Text style={styles.noAlertsTitle}>All Clear!</Text>
                <Text style={styles.noAlertsText}>No bridge height warnings on your route</Text>
              </View>
            )}
          </View>
        )}

        </View>

        <TouchableOpacity onPress={goHome} style={styles.bottomHomeButton}>
          <Ionicons name="home-outline" size={18} color="#a1a1aa" />
          <Text style={styles.bottomHomeText}>Return to RouteCast Home</Text>
        </TouchableOpacity>

        <View style={[styles.bottomPadding, { paddingBottom: insets.bottom + 16 }]} />
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#18181b',
  },
  header: {
    backgroundColor: '#18181b',
    paddingHorizontal: 8,
    paddingBottom: 8,
    flexDirection: 'row',
    alignItems: 'center',
  },
  headerTitle: {
    color: '#e4e4e7',
    fontSize: 17,
    fontWeight: '600',
    marginLeft: 8,
  },
  errorContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    gap: 16,
  },
  errorText: {
    color: '#e5e7eb',
    fontSize: 16,
  },
  errorHomeButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    paddingHorizontal: 20,
    paddingVertical: 12,
    backgroundColor: '#27272a',
    borderRadius: 8,
    marginTop: 8,
  },
  errorHomeText: {
    color: '#fff',
    fontSize: 15,
    fontWeight: '600',
  },
  backButton: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingVertical: 10,
    gap: 6,
    minHeight: 44,
  },
  backText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '600',
  },
  bottomHomeButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: 16,
    marginHorizontal: 16,
    marginTop: 8,
    borderTopWidth: 1,
    borderTopColor: '#27272a',
  },
  bottomHomeText: {
    color: '#a1a1aa',
    fontSize: 14,
  },
  content: {
    flex: 1,
    paddingHorizontal: 16,
  },
  routeContext: {
    backgroundColor: '#27272a',
    borderRadius: 12,
    padding: 16,
    marginBottom: 20,
    marginTop: 8,
    borderLeftWidth: 4,
    borderLeftColor: '#3b82f6',
  },
  routeContextTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: '#e5e7eb',
    marginBottom: 12,
  },
  routeContextRow: {
    flexDirection: 'row',
    marginBottom: 6,
  },
  routeContextLabel: {
    fontSize: 14,
    color: '#9ca3af',
    width: 80,
  },
  routeContextValue: {
    fontSize: 14,
    color: '#fff',
    fontWeight: '600',
    flex: 1,
  },
  section: {
    marginBottom: 24,
  },
  sectionTitle: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#e5e7eb',
    marginBottom: 4,
  },
  sectionSubtitle: {
    fontSize: 14,
    color: '#9ca3af',
    marginBottom: 12,
  },
  alertCard: {
    backgroundColor: '#0f172a',
    borderRadius: 14,
    padding: 16,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: '#1f2937',
    shadowColor: '#000',
    shadowOpacity: 0.15,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 4 },
  },
  alertCardNew: {
    gap: 10,
  },
  alertTitle: {
    color: '#fecaca',
    fontWeight: '800',
    fontSize: 15,
    letterSpacing: 0.2,
  },
  alertCondition: {
    color: '#e2e8f0',
    fontSize: 16,
    fontWeight: '700',
  },
  alertSubtitle: {
    color: '#cbd5e1',
    fontSize: 13,
  },
  conditionsBlock: {
    backgroundColor: '#111827',
    borderRadius: 10,
    padding: 12,
    gap: 6,
    borderWidth: 1,
    borderColor: '#1f2937',
  },
  blockTitle: {
    color: '#a5b4fc',
    fontWeight: '700',
    fontSize: 13,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  detailLine: {
    color: '#e5e7eb',
    fontSize: 13,
    lineHeight: 18,
  },
  metricLine: {
    color: '#cbd5e1',
    fontSize: 13,
  },
  actionBlock: {
    backgroundColor: '#0b1727',
    borderRadius: 10,
    padding: 12,
    borderWidth: 1,
    borderColor: '#1d4ed8',
  },
  actionText: {
    color: '#e0f2fe',
    fontSize: 13,
    lineHeight: 18,
  },
  footerMeta: {
    gap: 4,
  },
  metaLine: {
    color: '#cbd5e1',
    fontSize: 13,
  },
  noAlerts: {
    alignItems: 'center',
    paddingVertical: 40,
  },
  noAlertsTitle: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#22c55e',
    marginTop: 16,
    marginBottom: 8,
  },
  noAlertsText: {
    fontSize: 14,
    color: '#9ca3af',
  },
  bridgeAlertCard: {
    backgroundColor: '#27272a',
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
    borderLeftWidth: 4,
    borderLeftColor: '#eab308',
  },
  bridgeAlertCardExpanded: {
    backgroundColor: '#2d2d30',
  },
  bridgeAlertHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  bridgeAlertIconContainer: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: '#3f3f46',
    justifyContent: 'center',
    alignItems: 'center',
  },
  bridgeAlertIcon: {
    fontSize: 24,
  },
  bridgeAlertInfo: {
    flex: 1,
  },
  bridgeAlertTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#fff',
    marginBottom: 2,
  },
  bridgeAlertSubtitle: {
    fontSize: 13,
    color: '#9ca3af',
  },
  bridgeAlertDetails: {
    marginTop: 12,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: '#3f3f46',
  },
  bridgeAlertWarningText: {
    fontSize: 14,
    color: '#e5e7eb',
    lineHeight: 20,
    marginBottom: 12,
  },
  bridgeAlertTip: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 8,
    backgroundColor: '#3f3f46',
    borderRadius: 8,
    padding: 12,
  },
  bridgeAlertTipText: {
    flex: 1,
    fontSize: 13,
    color: '#d1d5db',
    lineHeight: 18,
  },
  bottomPadding: {
    height: 40,
  },
});
