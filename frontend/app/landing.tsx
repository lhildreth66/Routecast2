import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ScrollView,
  Platform,
  Dimensions,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons, MaterialCommunityIcons } from '@expo/vector-icons';
import { router } from 'expo-router';

const { width: SCREEN_WIDTH } = Dimensions.get('window');

export default function LandingScreen() {
  return (
    <SafeAreaView style={styles.container}>
      <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
        {/* Header */}
        <View style={styles.header}>
          <View style={styles.logoRow}>
            <MaterialCommunityIcons name="weather-lightning-rainy" size={32} color="#eab308" />
            <Text style={styles.logoText}>Routecast</Text>
          </View>
          <TouchableOpacity style={styles.signInBtn} onPress={() => router.push('/login')}>
            <Text style={styles.signInBtnText}>Sign In</Text>
          </TouchableOpacity>
        </View>

        {/* Hero */}
        <View style={styles.hero}>
          <Text style={styles.heroTitle}>Weather-Smart{'\n'}Route Planning</Text>
          <Text style={styles.heroSubtitle}>
            Real-time weather alerts, road hazards, and route optimization built for truck drivers and RV travelers.
          </Text>
          <TouchableOpacity style={styles.ctaBtn} onPress={() => router.push('/register')}>
            <Text style={styles.ctaBtnText}>Start Free Trial</Text>
            <Ionicons name="arrow-forward" size={18} color="#000" />
          </TouchableOpacity>
          <TouchableOpacity onPress={() => router.push('/login')}>
            <Text style={styles.alreadyHaveAccount}>Already have an account? <Text style={styles.alreadyHaveAccountLink}>Sign in</Text></Text>
          </TouchableOpacity>
        </View>

        {/* Features */}
        <View style={styles.features}>
          <FeatureCard
            icon="cloud-outline"
            iconLib="Ionicons"
            title="Live Weather Alerts"
            description="Get notified of severe weather, ice, fog, and high winds along your exact route before you hit the road."
          />
          <FeatureCard
            icon="truck-outline"
            iconLib="Ionicons"
            title="Built for Truckers & RVs"
            description="Trucker mode with height clearance warnings, weigh station alerts, and bridge restrictions."
          />
          <FeatureCard
            icon="map-outline"
            iconLib="Ionicons"
            title="Multi-Stop Routing"
            description="Plan routes with multiple stops including Walmart overnight parking, fuel, and rest areas."
          />
          <FeatureCard
            icon="notifications-outline"
            iconLib="Ionicons"
            title="Push Notifications"
            description="Real-time push alerts when weather conditions change along your active route."
          />
        </View>

        {/* CTA Footer */}
        <View style={styles.footer}>
          <Text style={styles.footerText}>Join thousands of drivers staying safe on the road.</Text>
          <TouchableOpacity style={styles.ctaBtn} onPress={() => router.push('/register')}>
            <Text style={styles.ctaBtnText}>Get Started Free</Text>
            <Ionicons name="arrow-forward" size={18} color="#000" />
          </TouchableOpacity>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

function FeatureCard({ icon, iconLib, title, description }: { icon: string; iconLib: string; title: string; description: string }) {
  return (
    <View style={styles.featureCard}>
      <View style={styles.featureIconWrap}>
        <Ionicons name={icon as any} size={26} color="#eab308" />
      </View>
      <View style={styles.featureText}>
        <Text style={styles.featureTitle}>{title}</Text>
        <Text style={styles.featureDesc}>{description}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#09090b',
  },
  scroll: {
    paddingBottom: 40,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingVertical: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#27272a',
  },
  logoRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  logoText: {
    color: '#fff',
    fontSize: 22,
    fontWeight: '800',
    letterSpacing: -0.5,
  },
  signInBtn: {
    borderWidth: 1,
    borderColor: '#eab308',
    borderRadius: 8,
    paddingHorizontal: 16,
    paddingVertical: 8,
  },
  signInBtnText: {
    color: '#eab308',
    fontSize: 14,
    fontWeight: '600',
  },
  hero: {
    paddingHorizontal: 24,
    paddingTop: 48,
    paddingBottom: 40,
    alignItems: 'center',
  },
  heroTitle: {
    color: '#fff',
    fontSize: 38,
    fontWeight: '800',
    textAlign: 'center',
    lineHeight: 44,
    letterSpacing: -1,
    marginBottom: 16,
  },
  heroSubtitle: {
    color: '#a1a1aa',
    fontSize: 16,
    textAlign: 'center',
    lineHeight: 24,
    marginBottom: 32,
    maxWidth: 340,
  },
  ctaBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    backgroundColor: '#eab308',
    paddingHorizontal: 28,
    paddingVertical: 16,
    borderRadius: 12,
    marginBottom: 16,
  },
  ctaBtnText: {
    color: '#000',
    fontSize: 16,
    fontWeight: '700',
  },
  alreadyHaveAccount: {
    color: '#71717a',
    fontSize: 14,
  },
  alreadyHaveAccountLink: {
    color: '#eab308',
    fontWeight: '600',
  },
  features: {
    paddingHorizontal: 20,
    gap: 12,
  },
  featureCard: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    backgroundColor: '#18181b',
    borderRadius: 12,
    padding: 16,
    gap: 14,
    borderWidth: 1,
    borderColor: '#27272a',
  },
  featureIconWrap: {
    width: 44,
    height: 44,
    borderRadius: 10,
    backgroundColor: '#27272a',
    justifyContent: 'center',
    alignItems: 'center',
  },
  featureText: {
    flex: 1,
  },
  featureTitle: {
    color: '#fff',
    fontSize: 15,
    fontWeight: '700',
    marginBottom: 4,
  },
  featureDesc: {
    color: '#71717a',
    fontSize: 13,
    lineHeight: 19,
  },
  footer: {
    marginTop: 40,
    paddingHorizontal: 24,
    alignItems: 'center',
    gap: 16,
  },
  footerText: {
    color: '#a1a1aa',
    fontSize: 15,
    textAlign: 'center',
  },
});
