/**
 * route-alerts.tsx  – full-screen Route Alerts viewer
 *
 * Opened by tapping the "Alerts" tab on the Route screen.
 * Shows two sections:
 *   1. Low Clearance / Bridge Height  (from routeData.bridge_clearance_alerts)
 *   2. Weather / Hazard Alerts        (from routeData.alerts / hazard_alerts)
 *
 * Receives the stringified routeData as a navigation param and fires the
 * same follow-up NWS-alerts fetch so weather data is always live.
 */
import React, { useState, useEffect, useMemo } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
  SafeAreaView,
} from 'react-native';
import { useLocalSearchParams, router } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import axios from 'axios';

const API_BASE = process.env.EXPO_PUBLIC_BACKEND_URL || '';

// ─── minimal types (kept inline so no import from route.tsx needed) ─────────
interface BridgeClearanceAlert {
  bridge_name: string;
  clearance_ft: number;
  vehicle_height_ft: number;
  distance_miles: number;
  warning: string;
}

interface HazardAlert {
  id?: string;
  alert_id?: string;
  event?: string;
  headline?: string;
  message?: string;
  description?: string;
  full_description?: string;
  instruction?: string;
  areaDesc?: string;
  location_name?: string;
  onset?: string;
  effective?: string;
  expires?: string;
  alert_level?: string;
  severity?: string;
  type?: string;
  recommendation?: string;
  distance_miles?: number;
  eta_minutes?: number;
  properties?: {
    event?: string;
    headline?: string;
    description?: string;
    instruction?: string;
    areaDesc?: string;
    onset?: string;
    effective?: string;
    expires?: string;
    ends?: string;
    senderName?: string;
    source?: string;
  };
}

interface RouteData {
  id?: string;
  alerts?: HazardAlert[];
  hazard_alerts?: HazardAlert[];
  hazard_status?: string;
  bridge_clearance_alerts?: BridgeClearanceAlert[];
  trucker_warnings?: string[];
  [key: string]: any;
}

// ─── helpers ────────────────────────────────────────────────────────────────
const fmtTime = (iso?: string): string | null => {
  if (!iso) return null;
  try {
    return new Date(iso).toLocaleDateString('en-US', {
      weekday: 'short', month: 'short', day: 'numeric',
      hour: 'numeric', minute: '2-digit',
    });
  } catch { return iso; }
};

// ─── screen ─────────────────────────────────────────────────────────────────
export default function RouteAlertsScreen() {
  const params = useLocalSearchParams();

  const [routeData, setRouteData] = useState<RouteData | null>(null);
  const [alertsLoading, setAlertsLoading] = useState(false);
  const [expandedCards, setExpandedCards] = useState<Set<number>>(new Set());

  // Parse routeData param on mount
  useEffect(() => {
    if (params.routeData) {
      try {
        setRouteData(JSON.parse(params.routeData as string));
      } catch (e) {
        console.error('[route-alerts] Failed to parse routeData param:', e);
      }
    }
  }, [params.routeData]);

  // Follow-up fetch – same as route.tsx so we get live NWS alerts
  useEffect(() => {
    const routeId = routeData?.id;
    if (!routeId) return;
    setAlertsLoading(true);
    axios
      .get(`${API_BASE}/api/route/weather/alerts/${routeId}`)
      .then((res) => {
        const payload = res.data || {};
        const fetched: HazardAlert[] = payload.alerts ?? payload.hazard_alerts ?? [];
        if (fetched.length > 0) {
          setRouteData((prev) =>
            prev
              ? { ...prev, hazard_alerts: fetched, alerts: fetched, hazard_status: 'ready' } as RouteData
              : prev
          );
        }
      })
      .catch((e) => console.warn('[route-alerts] follow-up fetch failed:', e.message))
      .finally(() => setAlertsLoading(false));
  }, [routeData?.id]);

  const alerts = useMemo<HazardAlert[]>(() => {
    if (!routeData) return [];
    return (routeData as any).alerts ?? routeData.hazard_alerts ?? [];
  }, [routeData]);

  const hazardSegments = useMemo<any[]>(() => {
    return Array.isArray(routeData?.turn_by_turn)
      ? (routeData!.turn_by_turn as any[]).filter((step: any) => step?.has_alert)
      : [];
  }, [routeData]);

  const bridgeAlerts = useMemo<BridgeClearanceAlert[]>(() => {
    return Array.isArray(routeData?.bridge_clearance_alerts)
      ? (routeData!.bridge_clearance_alerts as BridgeClearanceAlert[])
      : [];
  }, [routeData]);

  const truckerWarnings = useMemo<string[]>(() => {
    return Array.isArray(routeData?.trucker_warnings) ? routeData!.trucker_warnings as string[] : [];
  }, [routeData]);

  const totalAlertCount = alerts.length + bridgeAlerts.length;
  const showAllClear = alerts.length === 0 && hazardSegments.length === 0 && bridgeAlerts.length === 0 && truckerWarnings.length === 0;

  const toggleCardExpand = (index: number) => {
    const next = new Set(expandedCards);
    if (next.has(index)) { next.delete(index); } else { next.add(index); }
    setExpandedCards(next);
  };

  return (
    <SafeAreaView style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
          <Ionicons name="arrow-back" size={24} color="#fff" />
          <Text style={styles.backText}>Back</Text>
        </TouchableOpacity>
        <Text style={styles.headerTitle}>🗺️ Route Alerts</Text>
        {alertsLoading ? (
          <ActivityIndicator size="small" color="#f59e0b" style={styles.spinner} />
        ) : (
          <View style={styles.headerBadgePlaceholder}>
            {totalAlertCount > 0 && (
              <View style={styles.headerBadge}>
                <Text style={styles.headerBadgeText}>{totalAlertCount}</Text>
              </View>
            )}
          </View>
        )}
      </View>

      {/* Scrollable card list */}
      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        {/* ── Low Clearance / Bridge Height Section ──────────────────── */}
        {(bridgeAlerts.length > 0 || truckerWarnings.length > 0) && (
          <View style={styles.sectionBlock}>
            <View style={styles.sectionHeader}>
              <Ionicons name="git-commit-outline" size={18} color="#f59e0b" />
              <Text style={styles.sectionTitle}>Low Clearance / Bridge Height</Text>
              {bridgeAlerts.length > 0 && (
                <View style={[styles.headerBadge, { marginLeft: 8, backgroundColor: '#f59e0b' }]}>
                  <Text style={styles.headerBadgeText}>{bridgeAlerts.length}</Text>
                </View>
              )}
            </View>

            {bridgeAlerts.map((ba, idx) => (
              <View key={idx} style={styles.bridgeCard}>
                <View style={styles.bridgeHeader}>
                  <View style={styles.bridgeIconBox}>
                    <Ionicons name="warning" size={22} color="#f59e0b" />
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.bridgeName}>{ba.bridge_name}</Text>
                    <Text style={styles.bridgeDistance}>{Math.round(ba.distance_miles)} miles ahead</Text>
                  </View>
                </View>
                <View style={styles.bridgeClearanceRow}>
                  <View style={styles.clearanceBox}>
                    <Text style={styles.clearanceLabel}>CLEARANCE</Text>
                    <Text style={styles.clearanceValue}>{ba.clearance_ft.toFixed(1)} ft</Text>
                  </View>
                  <View style={styles.clearanceDivider} />
                  <View style={styles.clearanceBox}>
                    <Text style={styles.clearanceLabel}>YOUR HEIGHT</Text>
                    <Text style={styles.clearanceValueDanger}>{ba.vehicle_height_ft.toFixed(1)} ft</Text>
                  </View>
                </View>
                <View style={styles.bridgeWarningRow}>
                  <Ionicons name="alert-circle" size={16} color="#fecaca" />
                  <Text style={styles.bridgeWarningText}>{ba.warning}</Text>
                </View>
              </View>
            ))}

            {truckerWarnings.map((w, idx) => (
              <View key={`tw-${idx}`} style={styles.truckerWarningRow}>
                <Ionicons name="alert-circle-outline" size={15} color="#f59e0b" />
                <Text style={styles.truckerWarningText}>{w}</Text>
              </View>
            ))}
          </View>
        )}

        {/* ── Weather / Hazard Alerts Section ─────────────────────────── */}
        {!showAllClear ? (
          alerts && alerts.length > 0 ? (
            <>
              {(bridgeAlerts.length > 0 || truckerWarnings.length > 0) && (
                <View style={[styles.sectionHeader, { marginBottom: 10 }]}>
                  <Ionicons name="warning" size={18} color="#ef4444" />
                  <Text style={styles.sectionTitle}>Weather / Hazard Alerts</Text>
                  <View style={[styles.headerBadge, { marginLeft: 8 }]}>
                    <Text style={styles.headerBadgeText}>{alerts.length}</Text>
                  </View>
                </View>
              )}
              {alerts.map((alert, index) => {
              const isExpanded = expandedCards.has(index);
              const ap = alert.properties || ({} as NonNullable<HazardAlert['properties']>);
              const eventTitle =
                alert.event || ap.event || alert.headline || ap.headline || alert.message || 'Weather Alert';
              const what = alert.full_description || alert.description || ap.description || '';
              const where = alert.areaDesc || ap.areaDesc || alert.location_name || '';
              const onset = alert.onset || ap.onset || ap.effective || alert.effective;
              const expires = alert.expires || ap.expires;
              const ends = ap.ends;
              const expiresDisplay = ends || expires;
              const instruction = alert.instruction || ap.instruction || '';
              const headline = alert.headline || ap.headline || '';
              const issuedBy = ap.senderName || ap.source || '';
              const alertKey = alert.id || alert.alert_id || index;

              // ── WeatherBug colour + level ──────────────────────────────
              const lev = (alert.alert_level || '').toLowerCase();
              const sev = (alert.severity || '').toLowerCase();
              const evL = eventTitle.toLowerCase();
              let bannerColor = '#374151';
              let levelLabel = 'ADVISORY';
              if (
                lev === 'warning' || sev === 'extreme' || sev === 'severe' ||
                evL.includes('warning')
              ) { bannerColor = '#B91C1C'; levelLabel = 'WARNING'; }
              else if (lev === 'watch' || evL.includes('watch')) {
                bannerColor = '#C2410C'; levelLabel = 'WATCH';
              } else if (lev === 'advisory' || evL.includes('advisory')) {
                bannerColor = '#B45309'; levelLabel = 'ADVISORY';
              } else if (lev === 'statement' || evL.includes('statement')) {
                bannerColor = '#1D4ED8'; levelLabel = 'STATEMENT';
              } else if (sev === 'high') {
                bannerColor = '#B91C1C'; levelLabel = 'WARNING';
              } else if (sev === 'medium') {
                bannerColor = '#C2410C'; levelLabel = 'WATCH';
              }

              // ── Weather icon ──────────────────────────────────────────
              const evIcon = (alert.event || alert.type || '').toLowerCase();
              let wxIcon: any = 'alert-circle';
              if (evIcon.includes('snow') || evIcon.includes('blizzard') || evIcon.includes('winter') ||
                  evIcon.includes('ice')  || evIcon.includes('freez') || alert.type === 'ice' ||
                  alert.type === 'snow' || alert.type === 'whiteout') wxIcon = 'snow';
              else if (evIcon.includes('tornado')) wxIcon = 'warning';
              else if (evIcon.includes('thunder') || evIcon.includes('lightning') ||
                       evIcon.includes('storm')) wxIcon = 'thunderstorm';
              else if (evIcon.includes('flood') || evIcon.includes('rain') ||
                       alert.type === 'rain') wxIcon = 'rainy';
              else if (evIcon.includes('wind') || evIcon.includes('gale') ||
                       alert.type === 'wind') wxIcon = 'flag';
              else if (evIcon.includes('fog') || evIcon.includes('visib')) wxIcon = 'cloudy';
              else if (evIcon.includes('heat') || evIcon.includes('fire')) wxIcon = 'flame';

              return (
                <TouchableOpacity
                  key={alertKey}
                  style={styles.wbCard}
                  onPress={() => toggleCardExpand(index)}
                  activeOpacity={0.85}
                >
                  {/* ── Colored banner ──────────────────────────────── */}
                  <View style={[styles.wbBanner, { backgroundColor: bannerColor }]}>
                    <Ionicons name={wxIcon} size={28} color="#fff" />
                    <View style={styles.wbBannerTextCol}>
                      <Text style={styles.wbEventTitle}>{eventTitle.toUpperCase()}</Text>
                      {issuedBy ? (
                        <Text style={styles.wbIssuedBy}>{issuedBy}</Text>
                      ) : null}
                    </View>
                    <Ionicons
                      name={isExpanded ? 'chevron-up' : 'chevron-down'}
                      size={20}
                      color="rgba(255,255,255,0.85)"
                    />
                  </View>

                  {/* ── Card body ───────────────────────────────────── */}
                  <View style={styles.wbBody}>
                    {/* Time row */}
                    {(onset || expiresDisplay) ? (
                      <View style={styles.wbTimeRow}>
                        <Ionicons name="time-outline" size={13} color="#9ca3af" />
                        <Text style={styles.wbTimeText}>
                          {onset ? `Effective ${fmtTime(onset)}` : ''}
                          {onset && expiresDisplay ? '  →  ' : ''}
                          {expiresDisplay ? `Expires ${fmtTime(expiresDisplay)}` : ''}
                        </Text>
                      </View>
                    ) : null}

                    {/* Area */}
                    {where ? (
                      <View style={styles.wbAreaRow}>
                        <Ionicons name="location-outline" size={13} color="#9ca3af" />
                        <Text style={styles.wbAreaText} numberOfLines={isExpanded ? undefined : 2}>
                          {where}
                        </Text>
                      </View>
                    ) : null}

                    {/* Headline (collapsed) */}
                    {!isExpanded && headline && headline.toLowerCase() !== eventTitle.toLowerCase() ? (
                      <Text style={styles.wbHeadline} numberOfLines={3}>{headline}</Text>
                    ) : null}

                    {/* Expanded NWS detail */}
                    {isExpanded && (
                      <View style={styles.wbExpandedSection}>
                        {what ? (
                          <>
                            <Text style={styles.wbSectionLabel}>DETAILS</Text>
                            <Text style={styles.wbSectionText}>{what}</Text>
                          </>
                        ) : null}
                        {instruction ? (
                          <>
                            <Text style={[styles.wbSectionLabel, { marginTop: 14, color: '#86efac' }]}>
                              PRECAUTIONARY ACTIONS
                            </Text>
                            <Text style={styles.wbSectionText}>{instruction}</Text>
                          </>
                        ) : null}
                        {alert.recommendation && alert.recommendation !== instruction ? (
                          <View style={styles.wbActionRow}>
                            <Ionicons name="checkmark-circle" size={15} color="#4ade80" />
                            <Text style={styles.wbActionText}>{alert.recommendation}</Text>
                          </View>
                        ) : null}
                      </View>
                    )}

                    {/* Footer: distance + ETA + level pill */}
                    <View style={styles.wbFooter}>
                      {alert.distance_miles != null ? (
                        <View style={styles.wbFooterItem}>
                          <Ionicons name="location" size={12} color="#6b7280" />
                          <Text style={styles.wbFooterText}>{Math.round(alert.distance_miles)} mi</Text>
                        </View>
                      ) : null}
                      {alert.eta_minutes != null ? (
                        <View style={styles.wbFooterItem}>
                          <Ionicons name="time" size={12} color="#6b7280" />
                          <Text style={styles.wbFooterText}>ETA {alert.eta_minutes} min</Text>
                        </View>
                      ) : null}
                      <View style={[styles.wbLevelPill, { backgroundColor: bannerColor, marginLeft: 'auto' }]}>
                        <Text style={styles.wbLevelPillText}>{levelLabel}</Text>
                      </View>
                    </View>
                  </View>
                </TouchableOpacity>
              );
            })}
            </>
          ) : (
            <View style={styles.hazardSegmentsOnly}>
              <Ionicons name="warning" size={48} color="#f59e0b" />
              <Text style={styles.hazardSegmentsTitle}>Hazard segments detected</Text>
              <Text style={styles.hazardSegmentsText}>
                {hazardSegments.length} segment(s) in turn-by-turn have alerts.
              </Text>
            </View>
          )
        ) : (
          <View style={styles.noAlerts}>
            <Ionicons name="checkmark-circle" size={64} color="#22c55e" />
            <Text style={styles.noAlertsTitle}>All Clear!</Text>
            <Text style={styles.noAlertsText}>No significant hazards on your route</Text>
          </View>
        )}

        <View style={{ height: 40 }} />
      </ScrollView>
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
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#27272a',
  },
  backBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginRight: 12,
  },
  backText: {
    color: '#fff',
    fontSize: 16,
  },
  headerTitle: {
    flex: 1,
    color: '#fff',
    fontSize: 17,
    fontWeight: '700',
  },
  spinner: {
    marginLeft: 8,
  },
  headerBadgePlaceholder: {
    width: 32,
    alignItems: 'flex-end',
  },
  headerBadge: {
    backgroundColor: '#ef4444',
    borderRadius: 10,
    minWidth: 20,
    height: 20,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 5,
  },
  headerBadgeText: {
    color: '#fff',
    fontSize: 11,
    fontWeight: '700',
  },
  scroll: {
    flex: 1,
  },
  scrollContent: {
    padding: 16,
  },
  // ── card styles (same values as route.tsx) ───────────────────────────────
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
  noAlerts: {
    alignItems: 'center',
    paddingVertical: 40,
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
  // ── Bridge / Clearance section ──────────────────────────────────────────
  sectionBlock: {
    marginBottom: 20,
  },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 10,
    gap: 8,
  },
  sectionTitle: {
    color: '#f9fafb',
    fontSize: 15,
    fontWeight: '700',
    flex: 1,
  },
  bridgeCard: {
    backgroundColor: '#1e2433',
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#f59e0b44',
    marginBottom: 10,
    overflow: 'hidden',
  },
  bridgeHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 12,
    gap: 10,
  },
  bridgeIconBox: {
    width: 36,
    height: 36,
    borderRadius: 8,
    backgroundColor: 'rgba(245,158,11,0.15)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  bridgeName: {
    color: '#f9fafb',
    fontSize: 14,
    fontWeight: '700',
  },
  bridgeDistance: {
    color: '#9ca3af',
    fontSize: 11.5,
    marginTop: 2,
  },
  bridgeClearanceRow: {
    flexDirection: 'row',
    borderTopWidth: 1,
    borderTopColor: '#374151',
    marginHorizontal: 12,
    paddingVertical: 10,
    gap: 8,
    alignItems: 'center',
  },
  clearanceBox: {
    flex: 1,
    alignItems: 'center',
  },
  clearanceLabel: {
    color: '#6b7280',
    fontSize: 10,
    fontWeight: '700',
    letterSpacing: 0.6,
    textTransform: 'uppercase',
    marginBottom: 3,
  },
  clearanceValue: {
    color: '#22c55e',
    fontSize: 18,
    fontWeight: '800',
  },
  clearanceValueDanger: {
    color: '#ef4444',
    fontSize: 18,
    fontWeight: '800',
  },
  clearanceDivider: {
    width: 1,
    height: 32,
    backgroundColor: '#374151',
  },
  bridgeWarningRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 7,
    backgroundColor: 'rgba(239,68,68,0.1)',
    paddingHorizontal: 12,
    paddingVertical: 9,
    gap: 7,
  },
  bridgeWarningText: {
    color: '#fca5a5',
    fontSize: 12.5,
    flex: 1,
    lineHeight: 18,
  },
  truckerWarningRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 8,
    backgroundColor: 'rgba(245,158,11,0.08)',
    borderRadius: 8,
    padding: 10,
    marginBottom: 6,
  },
  truckerWarningText: {
    color: '#fbbf24',
    fontSize: 12.5,
    flex: 1,
    lineHeight: 18,
  },
});
