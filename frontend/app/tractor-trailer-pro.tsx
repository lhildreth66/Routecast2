import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
} from 'react-native';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { SafeAreaView } from 'react-native-safe-area-context';

export default function TractorTrailerProScreen() {
  const router = useRouter();

  const categories = [
    {
      id: 'truck-stops',
      title: 'Truck Stops & Fuel',
      icon: 'business' as const,
      description: 'Find Flying J, Love\'s, TA, Pilot, and independent truck stops',
      color: '#3b82f6',
      route: '/truck-stops',
    },
    {
      id: 'weigh-stations',
      title: 'Weigh Stations',
      icon: 'scale' as const,
      description: 'Locate weigh stations and check bypass status',
      color: '#8b5cf6',
      route: '/weigh-stations',
    },
    {
      id: 'truck-parking',
      title: 'Truck Parking',
      icon: 'car' as const,
      description: 'Rest areas, truck parking lots, and safe parking zones',
      color: '#22c55e',
      route: '/truck-parking',
    },
    {
      id: 'low-clearance',
      title: 'Low Clearance Alerts',
      icon: 'warning' as const,
      description: 'Bridges and overpasses with height restrictions',
      color: '#ef4444',
      route: '/low-clearance',
    },
    {
      id: 'truck-services',
      title: 'Truck Services',
      icon: 'construct' as const,
      description: 'Repair shops, tire services, truck washes, and CAT scales',
      color: '#f59e0b',
      route: '/truck-services',
    },
    {
      id: 'truck-routes',
      title: 'Truck-Restricted Routes',
      icon: 'close-circle' as const,
      description: 'Roads with truck restrictions, hazmat routes, and detours',
      color: '#ec4899',
      route: '/truck-restrictions',
    },
  ];

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ScrollView contentContainerStyle={styles.scrollContent}>
        <View style={styles.header}>
          <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
            <Ionicons name="arrow-back" size={24} color="#fff" />
          </TouchableOpacity>
          <Text style={styles.title}>🚛 Tractor Trailer Pro</Text>
          <Text style={styles.subtitle}>Professional tools for commercial drivers</Text>
        </View>

        <View style={styles.categoriesContainer}>
          {categories.map((category) => (
            <TouchableOpacity
              key={category.id}
              style={[styles.categoryCard, { borderLeftColor: category.color }]}
              onPress={() => router.push(category.route as any)}
              activeOpacity={0.7}
            >
              <View style={styles.categoryHeader}>
                <View style={[styles.iconContainer, { backgroundColor: category.color }]}>
                  <Ionicons name={category.icon} size={28} color="#fff" />
                </View>
                <Ionicons name="chevron-forward" size={24} color="#71717a" />
              </View>
              <Text style={styles.categoryTitle}>{category.title}</Text>
              <Text style={styles.categoryDescription}>{category.description}</Text>
            </TouchableOpacity>
          ))}
        </View>

        <View style={styles.footer}>
          <Text style={styles.footerText}>
            All data sourced from OpenStreetMap and state DOT databases
          </Text>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}
    setExpandedCards(prev => {
      const newSet = new Set(prev);
      if (newSet.has(index)) {
        newSet.delete(index);
      } else {
        newSet.add(index);
      }
      return newSet;
    });
  };

  const getAlertIcon = (type: string) => {
    switch (type) {
      case 'hazmat': return '☢️';
      case 'weigh_station': return '⚖️';
      case 'parking': return '🅿️';
      case 'steep_grade': return '⛰️';
      case 'sharp_turn': return '↪️';
      case 'toll': return '💰';
      default: return '🚛';
    }
  };

  const getAlertColor = (severity: string) => {
    switch (severity) {
      case 'critical': return '#ef4444';
      case 'warning': return '#f59e0b';
      case 'info': return '#3b82f6';
      default: return '#6b7280';
    }
  };

  const getFilteredAlerts = () => {
    if (activeFilter === 'all') return alerts;
    return alerts.filter(alert => alert.type === activeFilter);
  };

  const filteredAlerts = getFilteredAlerts();

  return (
    <ScrollView style={styles.container}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
          <Text style={styles.backText}>← Back</Text>
        </TouchableOpacity>
        <Text style={styles.title}>🚛 Tractor Trailer Pro</Text>
        <Text style={styles.subtitle}>Professional-grade alerts for commercial drivers</Text>
        
        {totalDistance > 0 && (
          <View style={styles.distanceInfo}>
            <Ionicons name="navigate-outline" size={16} color="#a1a1aa" />
            <Text style={styles.distanceText}>{totalDistance.toFixed(0)} miles along route</Text>
          </View>
        )}

        {error && (
          <View style={styles.errorBanner}>
            <Ionicons name="information-circle" size={16} color="#f59e0b" />
            <Text style={styles.errorText}>{error}</Text>
          </View>
        )}
      </View>

      {loading ? (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#3b82f6" />
          <Text style={styles.loadingText}>Analyzing route for truck alerts...</Text>
        </View>
      ) : (
        <>
          {/* Filter Buttons */}
          <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.filterContainer}>
        <TouchableOpacity
          style={[styles.filterButton, activeFilter === 'all' && styles.filterButtonActive]}
          onPress={() => setActiveFilter('all')}
        >
          <Text style={[styles.filterText, activeFilter === 'all' && styles.filterTextActive]}>
            All ({alerts.length})
          </Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.filterButton, activeFilter === 'weigh_station' && styles.filterButtonActive]}
          onPress={() => setActiveFilter('weigh_station')}
        >
          <Text style={[styles.filterText, activeFilter === 'weigh_station' && styles.filterTextActive]}>
            ⚖️ Weigh Stations
          </Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.filterButton, activeFilter === 'steep_grade' && styles.filterButtonActive]}
          onPress={() => setActiveFilter('steep_grade')}
        >
          <Text style={[styles.filterText, activeFilter === 'steep_grade' && styles.filterTextActive]}>
            ⛰️ Grades
          </Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.filterButton, activeFilter === 'sharp_turn' && styles.filterButtonActive]}
          onPress={() => setActiveFilter('sharp_turn')}
        >
          <Text style={[styles.filterText, activeFilter === 'sharp_turn' && styles.filterTextActive]}>
            ↪️ Sharp Turns
          </Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.filterButton, activeFilter === 'toll' && styles.filterButtonActive]}
          onPress={() => setActiveFilter('toll')}
        >
          <Text style={[styles.filterText, activeFilter === 'toll' && styles.filterTextActive]}>
            💰 Tolls
          </Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.filterButton, activeFilter === 'parking' && styles.filterButtonActive]}
          onPress={() => setActiveFilter('parking')}
        >
          <Text style={[styles.filterText, activeFilter === 'parking' && styles.filterTextActive]}>
            🅿️ Parking
          </Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.filterButton, activeFilter === 'hazmat' && styles.filterButtonActive]}
          onPress={() => setActiveFilter('hazmat')}
        >
          <Text style={[styles.filterText, activeFilter === 'hazmat' && styles.filterTextActive]}>
            ☢️ Hazmat
          </Text>
        </TouchableOpacity>
      </ScrollView>

      {/* Alert Cards */}
      <View style={styles.content}>
        {filteredAlerts.length > 0 ? (
          filteredAlerts.map((alert, index) => {
            const isExpanded = expandedCards.has(index);
            const alertColor = getAlertColor(alert.severity);

            return (
              <TouchableOpacity
                key={index}
                style={[styles.alertCard, { borderLeftColor: alertColor }]}
                onPress={() => toggleCard(index)}
                activeOpacity={0.7}
              >
                <View style={styles.alertHeader}>
                  <View style={styles.mileMarker}>
                    <Text style={styles.mileMarkerLabel}>MILE</Text>
                    <Text style={styles.mileMarkerNumber}>{alert.mile_marker}</Text>
                  </View>
                  <View style={styles.alertIcon}>
                    <Text style={styles.iconText}>{getAlertIcon(alert.type)}</Text>
                  </View>
                  <View style={styles.alertInfo}>
                    <Text style={styles.alertTitle}>{alert.title}</Text>
                    <Text style={styles.alertDescription}>{alert.description}</Text>
                    {alert.cost && (
                      <Text style={styles.alertCost}>Cost: ${alert.cost.toFixed(2)}</Text>
                    )}
                  </View>
                  <Ionicons
                    name={isExpanded ? 'chevron-up' : 'chevron-down'}
                    size={24}
                    color="#71717a"
                  />
                </View>

                {isExpanded && alert.details && (
                  <View style={styles.alertDetails}>
                    <Text style={styles.detailsText}>{alert.details}</Text>
                  </View>
                )}
              </TouchableOpacity>
            );
          })
        ) : (
          <View style={styles.emptyState}>
            <Ionicons name="checkmark-circle" size={64} color="#22c55e" />
            <Text style={styles.emptyTitle}>No Alerts</Text>
            <Text style={styles.emptyText}>No {activeFilter !== 'all' ? activeFilter.replace('_', ' ') : ''} alerts for this route</Text>
          </View>
        )}
      </View>
        </>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0a0a0a',
  },
  header: {
    backgroundColor: '#1a1a1a',
    paddingTop: 16,
    paddingHorizontal: 16,
    paddingBottom: 20,
    borderBottomWidth: 1,
    borderBottomColor: '#27272a',
  },
  backButton: {
    marginBottom: 12,
  },
  backText: {
    color: '#3b82f6',
    fontSize: 16,
    fontWeight: '600',
  },
  title: {
    fontSize: 28,
    fontWeight: 'bold',
    color: '#fff',
    marginBottom: 8,
  },
  subtitle: {
    fontSize: 14,
    color: '#a1a1aa',
    marginBottom: 12,
  },
  distanceInfo: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginTop: 8,
  },
  distanceText: {
    color: '#a1a1aa',
    fontSize: 13,
  },
  errorBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    backgroundColor: '#422006',
    padding: 10,
    borderRadius: 8,
    marginTop: 12,
  },
  errorText: {
    color: '#f59e0b',
    fontSize: 12,
    flex: 1,
  },
  filterContainer: {
    paddingHorizontal: 16,
    paddingVertical: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#27272a',
  },
  filterButton: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 20,
    backgroundColor: '#27272a',
    marginRight: 8,
  },
  filterButtonActive: {
    backgroundColor: '#3b82f6',
  },
  filterText: {
    color: '#a1a1aa',
    fontSize: 14,
    fontWeight: '600',
  },
  filterTextActive: {
    color: '#fff',
  },
  content: {
    padding: 16,
  },
  loadingContainer: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 40,
  },
  loadingText: {
    color: '#a1a1aa',
    marginTop: 12,
    fontSize: 14,
  },
  alertCard: {
    backgroundColor: '#1a1a1a',
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
    borderLeftWidth: 4,
  },
  alertHeader: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  mileMarker: {
    backgroundColor: '#27272a',
    borderRadius: 8,
    padding: 8,
    marginRight: 12,
    alignItems: 'center',
    minWidth: 60,
  },
  mileMarkerLabel: {
    color: '#71717a',
    fontSize: 10,
    fontWeight: '600',
  },
  mileMarkerNumber: {
    color: '#fff',
    fontSize: 18,
    fontWeight: 'bold',
  },
  alertIcon: {
    marginRight: 12,
  },
  iconText: {
    fontSize: 32,
  },
  alertInfo: {
    flex: 1,
  },
  alertTitle: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '700',
    marginBottom: 4,
  },
  alertDescription: {
    color: '#a1a1aa',
    fontSize: 14,
  },
  alertCost: {
    color: '#22c55e',
    fontSize: 14,
    fontWeight: '600',
    marginTop: 4,
  },
  alertDetails: {
    marginTop: 12,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: '#27272a',
  },
  detailsText: {
    color: '#d4d4d8',
    fontSize: 14,
    lineHeight: 20,
  },
  emptyState: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 60,
  },
  emptyTitle: {
    color: '#fff',
    fontSize: 20,
    fontWeight: '700',
    marginTop: 16,
    marginBottom: 8,
  },
  emptyText: {
    color: '#71717a',
    fontSize: 14,
    textAlign: 'center',
  },
});
