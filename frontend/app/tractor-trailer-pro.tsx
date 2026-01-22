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

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0a0a0a',
  },
  scrollContent: {
    paddingBottom: 20,
  },
  header: {
    backgroundColor: '#1a1a1a',
    paddingTop: 16,
    paddingHorizontal: 16,
    paddingBottom: 24,
    borderBottomWidth: 1,
    borderBottomColor: '#27272a',
  },
  backButton: {
    marginBottom: 12,
  },
  title: {
    fontSize: 32,
    fontWeight: 'bold',
    color: '#fff',
    marginBottom: 8,
  },
  subtitle: {
    fontSize: 15,
    color: '#a1a1aa',
    lineHeight: 22,
  },
  categoriesContainer: {
    padding: 16,
  },
  categoryCard: {
    backgroundColor: '#1a1a1a',
    borderRadius: 16,
    padding: 16,
    marginBottom: 12,
    borderLeftWidth: 4,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.25,
    shadowRadius: 3.84,
    elevation: 5,
  },
  categoryHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  iconContainer: {
    width: 56,
    height: 56,
    borderRadius: 28,
    justifyContent: 'center',
    alignItems: 'center',
  },
  categoryTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: '#fff',
    marginBottom: 6,
  },
  categoryDescription: {
    fontSize: 14,
    color: '#a1a1aa',
    lineHeight: 20,
  },
  footer: {
    padding: 16,
    paddingTop: 8,
  },
  footerText: {
    fontSize: 12,
    color: '#71717a',
    textAlign: 'center',
    fontStyle: 'italic',
  },
});
