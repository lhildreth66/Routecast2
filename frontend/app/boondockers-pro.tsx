import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity, ScrollView, SafeAreaView } from 'react-native';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';

export default function BoondockersProScreen() {
  const router = useRouter();

  const features = [
    { id: 'checklist', icon: 'list', title: 'Camp Prep Checklist', route: '/camp-prep-checklist' },
    { id: 'camping', icon: 'bonfire', title: 'Free Camping Finder', route: '/free-camping' },
    { id: 'dump', icon: 'water-outline', title: 'Dump Station Finder', route: '/dump-station' },
    { id: 'supplies', icon: 'cart', title: 'Last Chance Supplies', route: '/last-chance' },
    { id: 'dealership', icon: 'car-sport', title: 'RV Dealerships', route: '/rv-dealership' },
    { id: 'power', icon: 'flash', title: 'Solar Forecast', route: '/solar-forecast' },
    { id: 'propane', icon: 'flame', title: 'Propane Usage', route: '/propane-usage' },
    { id: 'water', icon: 'water', title: 'Water Planning', route: '/water-budget' },
    { id: 'wind', icon: 'leaf', title: 'Wind Shelter', route: '/wind-shelter' },
    { id: 'connectivity', icon: 'wifi', title: 'Connectivity', route: '/connectivity' },
    { id: 'index', icon: 'analytics', title: 'Campsite Index', route: '/campsite-index' },
  ];

  const handleFeatureTap = (feature: typeof features[0]) => {
    if (feature.route) {
      router.push(feature.route);
    } else {
      // For features without dedicated screens, you could show a modal or toast
      console.log(`Feature ${feature.title} not yet implemented`);
    }
  };

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="arrow-back" size={24} color="#fff" />
          <Text style={styles.backText}>Back</Text>
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Boondockers Pro</Text>
        <View style={styles.placeholder} />
      </View>

      <ScrollView style={styles.content} showsVerticalScrollIndicator={false}>
        <View style={styles.intro}>
          <Ionicons name="bonfire" size={48} color="#8b4513" />
          <Text style={styles.introTitle}>Boondockers Pro</Text>
          <Text style={styles.introDesc}>
            Boondockers Pro helps you prepare for off-grid travel with utilities tracking, checklists, and smart trip tools—all in one place.
          </Text>
        </View>

        <View style={styles.featureGrid}>
          {features.map((feature) => (
            <TouchableOpacity
              key={feature.id}
              style={styles.featureCard}
              onPress={() => handleFeatureTap(feature)}
              activeOpacity={0.7}
            >
              <View style={styles.featureIconContainer}>
                <Ionicons name={feature.icon as any} size={28} color="#8b4513" />
              </View>
              <Text style={styles.featureTitle}>{feature.title}</Text>
              <Ionicons name="chevron-forward" size={20} color="#a1a1aa" />
            </TouchableOpacity>
          ))}
        </View>
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
    justifyContent: 'space-between',
    paddingHorizontal: 12,
    paddingTop: 12,
    paddingBottom: 16,
    backgroundColor: '#27272a',
    borderBottomWidth: 1,
    borderBottomColor: '#3f3f46',
  },
  backButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    padding: 6,
  },
  backText: {
    color: '#60a5fa',
    fontSize: 16,
    fontWeight: '600',
  },
  headerTitle: {
    color: '#fff',
    fontSize: 18,
    fontWeight: '700',
  },
  placeholder: {
    width: 60,
  },
  content: {
    flex: 1,
  },
  intro: {
    alignItems: 'center',
    paddingVertical: 32,
    paddingHorizontal: 20,
  },
  introTitle: {
    color: '#fff',
    fontSize: 24,
    fontWeight: '700',
    marginTop: 16,
    marginBottom: 8,
  },
  introDesc: {
    color: '#a1a1aa',
    fontSize: 14,
    textAlign: 'center',
    lineHeight: 20,
  },
  featureGrid: {
    paddingHorizontal: 16,
    paddingBottom: 32,
    gap: 12,
  },
  featureCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1f1f23',
    borderRadius: 12,
    padding: 16,
    borderWidth: 1,
    borderColor: '#3f3f46',
    gap: 12,
  },
  featureIconContainer: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: '#fef3c7',
    justifyContent: 'center',
    alignItems: 'center',
  },
  featureTitle: {
    flex: 1,
    color: '#fff',
    fontSize: 16,
    fontWeight: '600',
  },
});
