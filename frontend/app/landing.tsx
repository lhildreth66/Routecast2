import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ScrollView,
  Platform,
  Linking,
  Image,
  useWindowDimensions,
} from 'react-native';
import { Ionicons, MaterialCommunityIcons } from '@expo/vector-icons';
import { router, Link } from 'expo-router';
import { LinearGradient } from 'expo-linear-gradient';

const GOOGLE_PLAY_URL = 'https://play.google.com/store/apps/details?id=com.routecast.app';

export default function LandingPage() {
  const [mounted, setMounted] = useState(false);
  const { width } = useWindowDimensions();
  const isWideScreen = !mounted || width > 768;
  const isMobile = mounted && width <= 480;

  useEffect(() => { setMounted(true); }, []);

  const handleStartTrial = () => {
    if (Platform.OS === 'web') {
      Linking.openURL(GOOGLE_PLAY_URL);
      return;
    }

    router.push('/signup');
  };

  const scrollToSection = (sectionId: string) => {
    // For web, use anchor scrolling
    if (Platform.OS === 'web') {
      const element = document.getElementById(sectionId);
      element?.scrollIntoView({ behavior: 'smooth' });
    }
  };

  return (
    <View style={styles.container}>
      <ScrollView
        style={styles.scrollView}
        contentContainerStyle={[styles.scrollContent, isMobile && styles.scrollContentMobile]}
        showsVerticalScrollIndicator={false}
      >
        {/* Navigation Bar */}
        <View style={styles.navbar}>
          <View style={[styles.navContent, !isWideScreen && styles.navContentMobile]}>
            <View style={[styles.logoContainer, !isWideScreen && styles.logoContainerMobile]}>
              <MaterialCommunityIcons name="weather-lightning-rainy" size={28} color="#eab308" />
              <Text style={[styles.logoText, !isWideScreen && styles.logoTextMobile]}>RouteCast</Text>
            </View>
            <View style={[styles.navLinks, !isWideScreen && styles.navLinksMobile]}>
              <Link href="/faq" style={[styles.navLink, !isWideScreen && styles.navLinkMobile]}>FAQ</Link>
              <Link href="/contact" style={[styles.navLink, !isWideScreen && styles.navLinkMobile]}>Contact</Link>
            </View>
          </View>
        </View>

        {/* Hero Section */}
        <View style={[styles.heroSection, isMobile && styles.heroSectionMobile]}>
          <LinearGradient
            colors={['#0f0f0f', '#1a1a2e', '#16213e']}
            style={[styles.heroGradient, isMobile && styles.heroGradientMobile]}
          >
            <View style={[styles.heroContent, isMobile && styles.heroContentMobile]}>
              <View style={styles.heroBadge}>
                <Ionicons name="shield-checkmark" size={14} color="#22c55e" />
                <Text style={styles.heroBadgeText}>Drive with confidence</Text>
              </View>
              
              <Text style={[styles.heroTitle, isMobile && styles.heroTitleMobile]}>
                Weather along your route—{'\n'}
                <Text style={styles.heroTitleAccent}>before you drive.</Text>
              </Text>
              
              <Text style={[styles.heroSubtitle, isMobile && styles.heroSubtitleMobile]}>
                See conditions, alerts, and road hazards for your entire journey.
                Available for iPhone and Android.
              </Text>

              <View style={[styles.heroCtas, isMobile && styles.heroCtasMobile]}>
                <TouchableOpacity 
                  style={styles.primaryCta}
                  onPress={handleStartTrial}
                  data-testid="hero-start-trial"
                >
                  <Ionicons name="rocket" size={20} color="#0f0f0f" />
                  <Text style={styles.primaryCtaText}>{Platform.OS === 'web' ? 'Download RouteCast Weather' : 'Start Free Trial'}</Text>
                </TouchableOpacity>
              </View>

              <TouchableOpacity
                style={styles.learnMoreLink}
                onPress={() => scrollToSection('features')}
                data-testid="hero-learn-more"
              >
                <Text style={styles.learnMoreLinkText}>Learn More</Text>
                <Ionicons name="arrow-down" size={16} color="#a1a1aa" />
              </TouchableOpacity>

              <View style={[styles.trustBullets, isMobile && styles.trustBulletsMobile]}>
                <View style={styles.trustBullet}>
                  <Ionicons name="checkmark-circle" size={16} color="#22c55e" />
                  <Text style={styles.trustBulletText}>Available for iPhone &amp; Android</Text>
                </View>
                <View style={styles.trustBullet}>
                  <Ionicons name="checkmark-circle" size={16} color="#22c55e" />
                  <Text style={styles.trustBulletText}>Subscription handled in-app</Text>
                </View>
                <View style={styles.trustBullet}>
                  <Ionicons name="checkmark-circle" size={16} color="#22c55e" />
                  <Text style={styles.trustBulletText}>Built for safer drives</Text>
                </View>
              </View>
            </View>

            {/* Hero Visual */}
            <View style={[styles.heroVisual, isMobile && styles.heroVisualMobile]}>
              <View style={[styles.phoneFrame, isMobile && styles.phoneFrameMobile]}>
                <View style={[styles.phoneScreen, isMobile && styles.phoneScreenMobile]}>
                  <View style={styles.mockHeader}>
                    <Text style={styles.mockHeaderText}>Denver → Las Vegas</Text>
                    <View style={styles.mockSafetyBadge}>
                      <Text style={styles.mockSafetyText}>Safe</Text>
                    </View>
                  </View>
                  <View style={styles.mockWeatherCard}>
                    <View style={styles.mockWeatherRow}>
                      <Ionicons name="sunny" size={24} color="#fbbf24" />
                      <Text style={styles.mockTemp}>72°F</Text>
                      <Text style={styles.mockCondition}>Clear</Text>
                    </View>
                    <View style={styles.mockAlertRow}>
                      <Ionicons name="warning" size={16} color="#f59e0b" />
                      <Text style={styles.mockAlertText}>Wind advisory at mile 180</Text>
                    </View>
                  </View>
                  <View style={styles.mockTimeline}>
                    <View style={styles.mockTimelineItem}>
                      <View style={[styles.mockTimelineDot, { backgroundColor: '#22c55e' }]} />
                      <Text style={styles.mockTimelineText}>Now - Clear</Text>
                    </View>
                    <View style={styles.mockTimelineItem}>
                      <View style={[styles.mockTimelineDot, { backgroundColor: '#f59e0b' }]} />
                      <Text style={styles.mockTimelineText}>2h - Windy</Text>
                    </View>
                    <View style={styles.mockTimelineItem}>
                      <View style={[styles.mockTimelineDot, { backgroundColor: '#22c55e' }]} />
                      <Text style={styles.mockTimelineText}>4h - Clear</Text>
                    </View>
                  </View>
                </View>
                {/* Callout bubbles */}
                {!isMobile && (
                  <>
                    <View style={[styles.calloutBubble, styles.calloutLeft]}>
                      <Ionicons name="alert-circle" size={14} color="#ef4444" />
                      <Text style={styles.calloutText}>Severe weather alerts</Text>
                    </View>
                    <View style={[styles.calloutBubble, styles.calloutRight]}>
                      <Ionicons name="time" size={14} color="#eab308" />
                      <Text style={styles.calloutText}>Hour-by-hour timeline</Text>
                    </View>
                  </>
                )}
              </View>
            </View>
          </LinearGradient>
        </View>

        {/* Social Proof Band */}
        <View style={styles.socialProofSection}>
          <Text style={styles.socialProofTitle}>Designed for road trippers & professionals</Text>
          <View style={styles.socialProofGrid}>
            <View style={styles.socialProofItem}>
              <MaterialCommunityIcons name="car-side" size={32} color="#eab308" />
              <Text style={styles.socialProofLabel}>Road Trippers</Text>
            </View>
            <View style={styles.socialProofItem}>
              <MaterialCommunityIcons name="rv-truck" size={32} color="#eab308" />
              <Text style={styles.socialProofLabel}>RV & Boondockers</Text>
            </View>
            <View style={styles.socialProofItem}>
              <MaterialCommunityIcons name="truck" size={32} color="#eab308" />
              <Text style={styles.socialProofLabel}>Truck Drivers</Text>
            </View>
            <View style={styles.socialProofItem}>
              <MaterialCommunityIcons name="briefcase" size={32} color="#eab308" />
              <Text style={styles.socialProofLabel}>Business Travelers</Text>
            </View>
          </View>
        </View>

        {/* Features Section */}
          <View style={[styles.featuresSection, isMobile && styles.featuresSectionMobile]} nativeID="features">
          <Text style={styles.sectionTitle}>Everything you need for safer drives</Text>
          <Text style={styles.sectionSubtitle}>
            From departure to destination, we've got you covered
          </Text>
          
          <View style={[styles.featuresGrid, isMobile && styles.featuresGridMobile]}>
            <View style={[styles.featureCard, !isWideScreen && styles.featureCardMobile]}>
              <View style={[styles.featureIcon, { backgroundColor: '#422006' }]}>
                <Ionicons name="map" size={24} color="#eab308" />
              </View>
              <Text style={styles.featureTitle}>Route-Based Forecast</Text>
              <Text style={styles.featureDesc}>
                See weather conditions at every point along your route, not just your destination.
              </Text>
            </View>

            <View style={[styles.featureCard, !isWideScreen && styles.featureCardMobile]}>
              <View style={[styles.featureIcon, { backgroundColor: '#14532d' }]}>
                <Ionicons name="warning" size={24} color="#22c55e" />
              </View>
              <Text style={styles.featureTitle}>Weather Alerts</Text>
              <Text style={styles.featureDesc}>
                Get NWS severe weather warnings for your exact route with countdown timers.
              </Text>
            </View>

            <View style={[styles.featureCard, !isWideScreen && styles.featureCardMobile]}>
              <View style={[styles.featureIcon, { backgroundColor: '#1e3a5f' }]}>
                <Ionicons name="speedometer" size={24} color="#3b82f6" />
              </View>
              <Text style={styles.featureTitle}>Road Conditions</Text>
              <Text style={styles.featureDesc}>
                Know when roads are wet, icy, or have low visibility before you encounter them.
              </Text>
            </View>

            <View style={[styles.featureCard, !isWideScreen && styles.featureCardMobile]}>
              <View style={[styles.featureIcon, { backgroundColor: '#4a1d6a' }]}>
                <Ionicons name="time" size={24} color="#a855f7" />
              </View>
              <Text style={styles.featureTitle}>Departure Optimizer</Text>
              <Text style={styles.featureDesc}>
                Find the best time to leave to avoid storms and hazardous conditions.
              </Text>
            </View>

            <View style={[styles.featureCard, !isWideScreen && styles.featureCardMobile]}>
              <View style={[styles.featureIcon, { backgroundColor: '#7c2d12' }]}>
                <Ionicons name="star" size={24} color="#f97316" />
              </View>
              <Text style={styles.featureTitle}>Saved Routes</Text>
              <Text style={styles.featureDesc}>
                Save your frequent trips and check conditions with one tap.
              </Text>
            </View>

            <View style={[styles.featureCard, !isWideScreen && styles.featureCardMobile]}>
              <View style={[styles.featureIcon, { backgroundColor: '#134e4a' }]}>
                <Ionicons name="shield-checkmark" size={24} color="#14b8a6" />
              </View>
              <Text style={styles.featureTitle}>Safety Score</Text>
              <Text style={styles.featureDesc}>
                Get an at-a-glance safety rating based on your vehicle type and conditions.
              </Text>
            </View>
          </View>
        </View>

        {/* Final CTA */}
        <View style={styles.finalCtaSection}>
          <LinearGradient
            colors={['#1a1a2e', '#16213e', '#0f0f0f']}
            style={styles.finalCtaGradient}
          >
            <Text style={styles.finalCtaTitle}>Get RouteCast Weather</Text>
            <Text style={styles.finalCtaSubtitle}>
              Available for iPhone and Android. Download the app and start a free 7-day trial.
            </Text>
            <TouchableOpacity 
              style={styles.finalCtaButton}
              onPress={handleStartTrial}
              data-testid="final-cta-btn"
            >
              <Text style={styles.finalCtaButtonText}>Download RouteCast Weather</Text>
              <Ionicons name="download" size={20} color="#0f0f0f" />
            </TouchableOpacity>
          </LinearGradient>
        </View>

        {/* Footer */}
        <View style={styles.footer}>
          <View style={styles.footerContent}>
            <View style={styles.footerBrand}>
              <MaterialCommunityIcons name="weather-lightning-rainy" size={24} color="#eab308" />
              <Text style={styles.footerBrandText}>RouteCast</Text>
            </View>
            <View style={styles.footerLinks}>
              <TouchableOpacity onPress={() => router.push('/privacy')}>
                <Text style={styles.footerLink}>Privacy Policy</Text>
              </TouchableOpacity>
              <TouchableOpacity onPress={() => router.push('/terms')}>
                <Text style={styles.footerLink}>Terms of Service</Text>
              </TouchableOpacity>
              <TouchableOpacity onPress={() => router.push('/contact')}>
                <Text style={styles.footerLink}>Contact</Text>
              </TouchableOpacity>
            </View>
          </View>
          <Text style={styles.footerCopyright}>
            © {new Date().getFullYear()} RouteCast. All rights reserved.
          </Text>
        </View>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0f0f0f',
  },
  scrollView: {
    flex: 1,
  },
  scrollContent: {
    paddingBottom: 48,
  },
  scrollContentMobile: {
    paddingBottom: 72,
  },

  // Navbar
  navbar: {
    backgroundColor: '#0f0f0f',
    borderBottomWidth: 1,
    borderBottomColor: 'rgba(255,255,255,0.1)',
  },
  navContent: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 24,
    paddingVertical: 16,
    maxWidth: 1200,
    marginHorizontal: 'auto',
    width: '100%',
  },
  navContentMobile: {
    flexDirection: 'column',
    alignItems: 'flex-start',
    gap: 12,
    paddingHorizontal: 16,
    paddingVertical: 12,
  },
  logoContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  logoContainerMobile: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    gap: 10,
  },
  logoText: {
    color: '#ffffff',
    fontSize: 20,
    fontWeight: '700',
  },
  logoTextMobile: {
    fontSize: 18,
  },
  navLinks: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 24,
  },
  navLinksMobile: {
    width: '100%',
    flexWrap: 'wrap',
    gap: 16,
    justifyContent: 'flex-start',
  },
  navLink: {
    color: '#a1a1aa',
    fontSize: 14,
    fontWeight: '500',
  },
  navLinkMobile: {
    fontSize: 13,
    paddingVertical: 2,
  },

  // Hero Section
  heroSection: {
    minHeight: 600,
    marginBottom: 32,
  },
  heroSectionMobile: {
    minHeight: 0,
    marginBottom: 24,
  },
  heroGradient: {
    paddingTop: 40,
    paddingBottom: 60,
    paddingHorizontal: 24,
    overflow: 'hidden',
  },
  heroGradientMobile: {
    paddingTop: 32,
    paddingBottom: 44,
    paddingHorizontal: 16,
  },
  heroContent: {
    maxWidth: 600,
    marginHorizontal: 'auto',
    alignItems: 'center',
  },
  heroContentMobile: {
    maxWidth: 500,
  },
  heroBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: 'rgba(34, 197, 94, 0.15)',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 20,
    marginBottom: 24,
  },
  heroBadgeText: {
    color: '#22c55e',
    fontSize: 13,
    fontWeight: '600',
  },
  heroTitle: {
    fontSize: 42,
    fontWeight: '800',
    color: '#ffffff',
    textAlign: 'center',
    lineHeight: 52,
    marginBottom: 20,
  },
  heroTitleMobile: {
    fontSize: 30,
    lineHeight: 38,
  },
  heroTitleAccent: {
    color: '#eab308',
  },
  heroSubtitle: {
    fontSize: 18,
    color: '#a1a1aa',
    textAlign: 'center',
    lineHeight: 28,
    marginBottom: 32,
    maxWidth: 500,
  },
  heroSubtitleMobile: {
    fontSize: 15,
    lineHeight: 24,
    marginBottom: 20,
  },
  heroCtas: {
    flexDirection: 'row',
    gap: 16,
    marginBottom: 32,
    flexWrap: 'wrap',
    justifyContent: 'center',
  },
  heroCtasMobile: {
    flexDirection: 'column',
    gap: 12,
    width: '100%',
    justifyContent: 'center',
  },
  primaryCta: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    backgroundColor: '#eab308',
    paddingHorizontal: 28,
    paddingVertical: 16,
    borderRadius: 12,
  },
  primaryCtaText: {
    color: '#0f0f0f',
    fontSize: 16,
    fontWeight: '700',
  },
  learnMoreLink: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 28,
  },
  learnMoreLinkText: {
    color: '#a1a1aa',
    fontSize: 14,
    fontWeight: '600',
  },
  trustBullets: {
    flexDirection: 'row',
    gap: 24,
    flexWrap: 'wrap',
    justifyContent: 'center',
  },
  trustBulletsMobile: {
    gap: 10,
  },
  trustBullet: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  trustBulletText: {
    color: '#a1a1aa',
    fontSize: 13,
  },

  // Hero Visual
  heroVisual: {
    alignItems: 'center',
    marginTop: 48,
  },
  heroVisualMobile: {
    marginTop: 20,
  },
  phoneFrame: {
    width: 280,
    height: 400,
    backgroundColor: '#1a1a1a',
    borderRadius: 32,
    padding: 12,
    borderWidth: 3,
    borderColor: '#333',
    position: 'relative',
  },
  phoneFrameMobile: {
    width: 210,
    height: 300,
    borderRadius: 24,
    padding: 10,
  },
  phoneScreen: {
    flex: 1,
    backgroundColor: '#0f0f0f',
    borderRadius: 24,
    padding: 16,
  },
  phoneScreenMobile: {
    borderRadius: 20,
    padding: 12,
  },
  mockHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
  },
  mockHeaderText: {
    color: '#fff',
    fontSize: 14,
    fontWeight: '600',
  },
  mockSafetyBadge: {
    backgroundColor: '#14532d',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 8,
  },
  mockSafetyText: {
    color: '#22c55e',
    fontSize: 11,
    fontWeight: '700',
  },
  mockWeatherCard: {
    backgroundColor: '#1a1a1a',
    borderRadius: 12,
    padding: 12,
    marginBottom: 12,
  },
  mockWeatherRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    marginBottom: 8,
  },
  mockTemp: {
    color: '#fff',
    fontSize: 24,
    fontWeight: '700',
  },
  mockCondition: {
    color: '#a1a1aa',
    fontSize: 14,
  },
  mockAlertRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  mockAlertText: {
    color: '#f59e0b',
    fontSize: 12,
  },
  mockTimeline: {
    gap: 10,
  },
  mockTimelineItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  mockTimelineDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
  },
  mockTimelineText: {
    color: '#a1a1aa',
    fontSize: 12,
  },
  calloutBubble: {
    position: 'absolute',
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: '#27272a',
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: '#3f3f46',
  },
  calloutLeft: {
    left: -100,
    top: 80,
  },
  calloutRight: {
    right: -90,
    bottom: 120,
  },
  calloutText: {
    color: '#fff',
    fontSize: 11,
    fontWeight: '500',
  },

  // Social Proof
  socialProofSection: {
    backgroundColor: '#141414',
    paddingVertical: 48,
    paddingHorizontal: 24,
  },
  socialProofTitle: {
    color: '#a1a1aa',
    fontSize: 14,
    fontWeight: '600',
    textAlign: 'center',
    textTransform: 'uppercase',
    letterSpacing: 1,
    marginBottom: 32,
  },
  socialProofGrid: {
    flexDirection: 'row',
    justifyContent: 'center',
    gap: 48,
    flexWrap: 'wrap',
  },
  socialProofItem: {
    alignItems: 'center',
    gap: 12,
  },
  socialProofLabel: {
    color: '#d4d4d8',
    fontSize: 14,
    fontWeight: '500',
  },

  // Features Section
  featuresSection: {
    paddingVertical: 80,
    paddingHorizontal: 24,
  },
  featuresSectionMobile: {
    paddingVertical: 56,
    paddingHorizontal: 16,
  },
  sectionTitle: {
    color: '#ffffff',
    fontSize: 32,
    fontWeight: '700',
    textAlign: 'center',
    marginBottom: 12,
  },
  sectionSubtitle: {
    color: '#a1a1aa',
    fontSize: 16,
    textAlign: 'center',
    marginBottom: 48,
  },
  featuresGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'center',
    gap: 24,
    maxWidth: 1000,
    marginHorizontal: 'auto',
  },
  featuresGridMobile: {
    gap: 16,
  },
  featureCard: {
    width: 300,
    backgroundColor: '#1a1a1a',
    borderRadius: 16,
    padding: 24,
    borderWidth: 1,
    borderColor: '#27272a',
  },
  featureCardMobile: {
    width: '100%',
    maxWidth: 360,
  },
  featureIcon: {
    width: 48,
    height: 48,
    borderRadius: 12,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 16,
  },
  featureTitle: {
    color: '#ffffff',
    fontSize: 18,
    fontWeight: '600',
    marginBottom: 8,
  },
  featureDesc: {
    color: '#a1a1aa',
    fontSize: 14,
    lineHeight: 22,
  },

  // Final CTA
  finalCtaSection: {
    paddingHorizontal: 24,
    paddingVertical: 48,
  },
  finalCtaGradient: {
    borderRadius: 24,
    paddingVertical: 64,
    paddingHorizontal: 32,
    alignItems: 'center',
  },
  finalCtaTitle: {
    color: '#ffffff',
    fontSize: 32,
    fontWeight: '700',
    textAlign: 'center',
    marginBottom: 12,
  },
  finalCtaSubtitle: {
    color: '#a1a1aa',
    fontSize: 16,
    textAlign: 'center',
    marginBottom: 32,
  },
  finalCtaButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    backgroundColor: '#eab308',
    paddingHorizontal: 32,
    paddingVertical: 18,
    borderRadius: 12,
  },
  finalCtaButtonText: {
    color: '#0f0f0f',
    fontSize: 17,
    fontWeight: '700',
  },

  // Footer
  footer: {
    backgroundColor: '#0a0a0a',
    paddingVertical: 48,
    paddingHorizontal: 24,
    borderTopWidth: 1,
    borderTopColor: '#1a1a1a',
  },
  footerContent: {
    maxWidth: 1000,
    marginHorizontal: 'auto',
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: 24,
    marginBottom: 24,
  },
  footerBrand: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  footerBrandText: {
    color: '#ffffff',
    fontSize: 18,
    fontWeight: '600',
  },
  footerLinks: {
    flexDirection: 'row',
    gap: 32,
  },
  footerLink: {
    color: '#6b7280',
    fontSize: 14,
  },
  footerCopyright: {
    color: '#52525b',
    fontSize: 12,
    textAlign: 'center',
  },
});
