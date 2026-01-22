import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  SafeAreaView,
} from 'react-native';
import { useLocalSearchParams, router } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';

interface HazardAlert {
  type: string;
  severity: string;
  distance_miles: number;
  eta_minutes: number;
  message: string;
  recommendation: string;
  countdown_text: string;
  full_description?: string;
  description?: string;
  instruction?: string;
  location_name?: string;
}

interface TruckerWarning {
  warning: string;
}

export default function WeatherAlertsScreen() {
  const params = useLocalSearchParams();
  const routeData = params.routeData ? JSON.parse(params.routeData as string) : null;
  const bridgeAlertsEnabled = params.bridgeAlertsEnabled === 'true';
  
  const [expandedCards, setExpandedCards] = useState(new Set<number>());

  const toggleCardExpand = (index: number) => {
    const newExpanded = new Set(expandedCards);
    if (newExpanded.has(index)) {
      newExpanded.delete(index);
    } else {
      newExpanded.add(index);
    }
    setExpandedCards(newExpanded);
  };

  if (!routeData) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.errorContainer}>
          <Text style={styles.errorText}>No route data available</Text>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
        <Ionicons name="arrow-back" size={24} color="#fff" />
        <Text style={styles.backText}>Back to Route</Text>
      </TouchableOpacity>

      <ScrollView style={styles.content} showsVerticalScrollIndicator={false}>
        {/* Route Context */}
        <View style={styles.routeContext}>
          <Text style={styles.routeContextTitle}>Your Route</Text>
          <View style={styles.routeContextRow}>
            <Text style={styles.routeContextLabel}>From:</Text>
            <Text style={styles.routeContextValue}>{routeData.origin}</Text>
          </View>
          <View style={styles.routeContextRow}>
            <Text style={styles.routeContextLabel}>To:</Text>
            <Text style={styles.routeContextValue}>{routeData.destination}</Text>
          </View>
          {routeData.total_distance_miles && (
            <View style={styles.routeContextRow}>
              <Text style={styles.routeContextLabel}>Distance:</Text>
              <Text style={styles.routeContextValue}>{Math.round(routeData.total_distance_miles)} miles</Text>
            </View>
          )}
        </View>

        {/* Weather Alerts Section */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>⚠️ Weather Hazards on This Route</Text>
          <Text style={styles.sectionSubtitle}>Each alert shows the specific location along your route</Text>
        
          {routeData.hazard_alerts && routeData.hazard_alerts.length > 0 ? (
            routeData.hazard_alerts.map((alert: HazardAlert, index: number) => {
              const isExpanded = expandedCards.has(index);
              
              return (
                <TouchableOpacity 
                  key={index} 
                  style={[
                    styles.alertCard,
                    alert.severity === 'extreme' ? styles.alertExtreme :
                    alert.severity === 'high' ? styles.alertHigh : styles.alertMedium,
                    isExpanded && styles.alertCardExpanded
                  ]}
                  onPress={() => toggleCardExpand(index)}
                  activeOpacity={0.8}
                >
                  <View style={styles.alertHeader}>
                    <Ionicons 
                      name={
                        alert.type === 'ice' ? 'snow' :
                        alert.type === 'rain' ? 'rainy' :
                        alert.type === 'wind' ? 'cloudy' :
                        'warning'
                      } 
                      size={28} 
                      color="#fff" 
                    />
                    <View style={styles.alertInfo}>
                      {alert.location_name && (
                        <Text style={styles.alertLocation}>📍 {alert.location_name}</Text>
                      )}
                      <Text style={styles.alertMessage}>{alert.message}</Text>
                      <Text style={styles.alertCountdown}>{alert.countdown_text}</Text>
                    </View>
                    <Ionicons 
                      name={isExpanded ? "chevron-up" : "chevron-down"} 
                      size={20} 
                      color="#fff" 
                    />
                  </View>
                  
                  {/* Expanded Alert Details */}
                  {isExpanded && (
                    <View style={styles.alertExpandedContent}>
                      <View style={styles.alertFullDescription}>
                        <Text style={styles.alertFullTitle}>Full Alert Details:</Text>
                        <Text style={styles.alertFullText}>
                          {alert.full_description || alert.description || 
                           `This ${alert.message || 'weather alert'} is active for your route area. ` +
                           `Exercise caution and monitor local weather updates. ` +
                           `Conditions may include reduced visibility, slippery roads, or other hazards.`}
                        </Text>
                      </View>
                      
                      {alert.instruction && (
                        <View style={styles.alertInstructionBox}>
                          <Text style={styles.alertInstructionTitle}>📋 What To Do:</Text>
                          <Text style={styles.alertInstructionText}>{alert.instruction}</Text>
                        </View>
                      )}
                      
                      <View style={styles.alertAction}>
                        <Ionicons name="checkmark-circle" size={16} color="#22c55e" />
                        <Text style={styles.alertRec}>{alert.recommendation}</Text>
                      </View>
                    </View>
                  )}
                  
                  {!isExpanded && (
                    <>
                      <View style={styles.alertAction}>
                        <Ionicons name="checkmark-circle" size={16} color="#22c55e" />
                        <Text style={styles.alertRec}>{alert.recommendation}</Text>
                      </View>
                      <View style={styles.alertMeta}>
                        <Text style={styles.alertDistance}>{Math.round(alert.distance_miles)} mi from start</Text>
                        <Text style={styles.alertEta}>ETA: {alert.eta_minutes} min</Text>
                      </View>
                    </>
                  )}
                  
                  {isExpanded && (
                    <View style={styles.alertMeta}>
                      <Text style={styles.alertDistance}>{Math.round(alert.distance_miles)} mi from start</Text>
                      <Text style={styles.alertEta}>ETA: {alert.eta_minutes} min</Text>
                    </View>
                  )}
                </TouchableOpacity>
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
                const isBridgeExpanded = expandedCards.has(index + 1000);
                
                return (
                  <TouchableOpacity 
                    key={index}
                    style={[
                      styles.bridgeAlertCard,
                      isBridgeExpanded && styles.bridgeAlertCardExpanded
                    ]}
                    onPress={() => toggleCardExpand(index + 1000)}
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
                        name={isBridgeExpanded ? "chevron-up" : "chevron-down"} 
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

        <View style={styles.bottomPadding} />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#18181b',
  },
  errorContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  errorText: {
    color: '#e5e7eb',
    fontSize: 16,
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
    backgroundColor: '#27272a',
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
    borderLeftWidth: 4,
  },
  alertExtreme: {
    borderLeftColor: '#dc2626',
  },
  alertHigh: {
    borderLeftColor: '#f97316',
  },
  alertMedium: {
    borderLeftColor: '#eab308',
  },
  alertCardExpanded: {
    backgroundColor: '#2d2d30',
  },
  alertHeader: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 12,
    marginBottom: 12,
  },
  alertInfo: {
    flex: 1,
  },
  alertCountdown: {
    fontSize: 12,
    color: '#9ca3af',
    marginTop: 2,
  },
  alertMessage: {
    fontSize: 15,
    fontWeight: '600',
    color: '#fff',
    marginBottom: 4,
  },
  alertLocation: {
    fontSize: 14,
    fontWeight: '600',
    color: '#60a5fa',
    marginBottom: 6,
  },
  alertExpandedContent: {
    marginTop: 8,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: '#3f3f46',
  },
  alertFullDescription: {
    marginBottom: 12,
  },
  alertFullTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: '#e5e7eb',
    marginBottom: 6,
  },
  alertFullText: {
    fontSize: 14,
    color: '#d1d5db',
    lineHeight: 20,
  },
  alertInstructionBox: {
    backgroundColor: '#3f3f46',
    borderRadius: 8,
    padding: 12,
    marginBottom: 12,
  },
  alertInstructionTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: '#fbbf24',
    marginBottom: 6,
  },
  alertInstructionText: {
    fontSize: 13,
    color: '#e5e7eb',
    lineHeight: 18,
  },
  alertAction: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 8,
  },
  alertRec: {
    fontSize: 14,
    color: '#22c55e',
    flex: 1,
  },
  alertMeta: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  alertDistance: {
    fontSize: 13,
    color: '#9ca3af',
  },
  alertEta: {
    fontSize: 13,
    color: '#9ca3af',
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
