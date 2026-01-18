import React, { useState } from 'react';
import { View, Text, ScrollView, SafeAreaView, TouchableOpacity, StyleSheet } from 'react-native';
import { useRoute, useNavigation } from '@react-navigation/native';
import { Ionicons } from '@expo/vector-icons';

interface RouteData {
  trucker_warnings: string[];
  origin: string;
  destination: string;
}

export default function TruckerAlertsScreen() {
  const navigation = useNavigation();
  const route = useRoute();
  const routeData = (route.params as { routeData: string })?.routeData 
    ? JSON.parse((route.params as { routeData: string }).routeData)
    : null;

  if (!routeData) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.header}>
          <TouchableOpacity onPress={() => navigation.goBack()}>
            <Ionicons name="chevron-back" size={24} color="#e4e4e7" />
          </TouchableOpacity>
          <Text style={styles.headerTitle}>🚛 Trucker Alerts</Text>
          <View style={{ width: 24 }} />
        </View>
        <View style={styles.centerContent}>
          <Text style={styles.emptyText}>No route data available</Text>
        </View>
      </SafeAreaView>
    );
  }

  const warnings = routeData.trucker_warnings || [];
  const hasWarnings = warnings && warnings.length > 0;

  return (
    <SafeAreaView style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => navigation.goBack()}>
          <Ionicons name="chevron-back" size={24} color="#e4e4e7" />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>🚛 Trucker Alerts</Text>
        <View style={{ width: 24 }} />
      </View>

      {/* Route Info */}
      <View style={styles.routeInfo}>
        <Text style={styles.routeText}>
          {routeData.origin} → {routeData.destination}
        </Text>
      </View>

      {/* Warnings Content */}
      <ScrollView contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
        {hasWarnings ? (
          <View style={styles.warningsContainer}>
            <Text style={styles.warningCount}>
              {warnings.length} {warnings.length === 1 ? 'Alert' : 'Alerts'}
            </Text>
            <View style={styles.warningsBox}>
              {warnings.map((warning: string, idx: number) => (
                <View key={idx} style={styles.warningItem}>
                  <Text style={styles.warningText}>{warning}</Text>
                  {idx < warnings.length - 1 && <View style={styles.divider} />}
                </View>
              ))}
            </View>
          </View>
        ) : (
          <View style={styles.noWarningsContainer}>
            <Text style={styles.noWarningsIcon}>✓</Text>
            <Text style={styles.noWarningsTitle}>No Trucker Alerts</Text>
            <Text style={styles.noWarningsText}>
              Safe conditions for high-profile vehicles along this route.
            </Text>
          </View>
        )}

        {/* Safety Tips */}
        <View style={styles.tipsSection}>
          <Text style={styles.tipsTitle}>💡 Trucker Safety Tips</Text>
          <View style={styles.tipItem}>
            <Text style={styles.tipIcon}>⚠️</Text>
            <Text style={styles.tipText}>Always check actual clearances when unsure about bridge height</Text>
          </View>
          <View style={styles.tipItem}>
            <Text style={styles.tipIcon}>💨</Text>
            <Text style={styles.tipText}>High winds can affect handling of large vehicles - reduce speed</Text>
          </View>
          <View style={styles.tipItem}>
            <Text style={styles.tipIcon}>🧊</Text>
            <Text style={styles.tipText}>Bridges and overpasses freeze before regular road surfaces</Text>
          </View>
          <View style={styles.tipItem}>
            <Text style={styles.tipIcon}>📏</Text>
            <Text style={styles.tipText}>Keep updated on your vehicle's exact height for accurate warnings</Text>
          </View>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0a0a0a',
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
  routeInfo: {
    paddingHorizontal: 16,
    paddingVertical: 12,
    backgroundColor: '#27272a',
    borderRadius: 8,
    marginHorizontal: 16,
    marginTop: 12,
  },
  routeText: {
    color: '#a1a1aa',
    fontSize: 12,
    fontWeight: '500',
  },
  scrollContent: {
    paddingHorizontal: 16,
    paddingVertical: 16,
    gap: 20,
  },
  warningsContainer: {
    gap: 12,
  },
  warningCount: {
    fontSize: 14,
    fontWeight: '600',
    color: '#f59e0b',
  },
  warningsBox: {
    backgroundColor: '#27272a',
    borderRadius: 12,
    borderLeftWidth: 4,
    borderLeftColor: '#f59e0b',
    overflow: 'hidden',
  },
  warningItem: {
    paddingHorizontal: 14,
    paddingVertical: 12,
  },
  warningText: {
    color: '#e4e4e7',
    fontSize: 13,
    lineHeight: 20,
    fontWeight: '500',
  },
  divider: {
    height: 1,
    backgroundColor: '#3f3f46',
    marginTop: 12,
  },
  noWarningsContainer: {
    alignItems: 'center',
    paddingVertical: 40,
  },
  noWarningsIcon: {
    fontSize: 48,
    marginBottom: 12,
  },
  noWarningsTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: '#10b981',
    marginBottom: 8,
  },
  noWarningsText: {
    fontSize: 13,
    color: '#a1a1aa',
    textAlign: 'center',
    paddingHorizontal: 20,
    lineHeight: 20,
  },
  tipsSection: {
    backgroundColor: '#27272a',
    borderRadius: 12,
    padding: 16,
    gap: 12,
  },
  tipsTitle: {
    fontSize: 14,
    fontWeight: '700',
    color: '#eab308',
    marginBottom: 4,
  },
  tipItem: {
    flexDirection: 'row',
    gap: 10,
    alignItems: 'flex-start',
  },
  tipIcon: {
    fontSize: 18,
    marginTop: 2,
  },
  tipText: {
    flex: 1,
    color: '#a1a1aa',
    fontSize: 12,
    lineHeight: 18,
  },
  centerContent: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  emptyText: {
    color: '#a1a1aa',
    fontSize: 14,
  },
});
