import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ScrollView,
  Platform,
  Dimensions,
  Linking,
  Image,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons, MaterialCommunityIcons } from '@expo/vector-icons';
import { router } from 'expo-router';
import { LinearGradient } from 'expo-linear-gradient';

const { width: SCREEN_WIDTH } = Dimensions.get('window');
const isWideScreen = SCREEN_WIDTH > 768;

// All pricing CTAs route to /signup - Stripe checkout handled post-signup

export default function LandingPage() {
  const [activeFaq, setActiveFaq] = useState<number | null>(null);

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
              <TouchableOpacity onPress={() => scrollToSection('features')}>
                <Text style={[styles.navLink, !isWideScreen && styles.navLinkMobile]}>Features</Text>
              </TouchableOpacity>
              <TouchableOpacity onPress={() => scrollToSection('pricing')}>
                <Text style={[styles.navLink, !isWideScreen && styles.navLinkMobile]}>Pricing</Text>
              </TouchableOpacity>
              <TouchableOpacity onPress={() => scrollToSection('faq')}>
                <Text style={[styles.navLink, !isWideScreen && styles.navLinkMobile]}>FAQ</Text>
              </TouchableOpacity>
              <TouchableOpacity 
                style={styles.navLoginBtn}
                onPress={() => router.push('/login')}
              >
                <Text style={styles.navLoginText}>Log In</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>

        {/* Hero Section */}
        <View style={styles.heroSection}>
          <LinearGradient
            colors={['#0f0f0f', '#1a1a2e', '#16213e']}
            style={styles.heroGradient}
          >
            <View style={styles.heroContent}>
              <View style={styles.heroBadge}>
                <Ionicons name="shield-checkmark" size={14} color="#22c55e" />
                <Text style={styles.heroBadgeText}>Drive with confidence</Text>
              </View>
              
              <Text style={styles.heroTitle}>
                Weather along your route—{'\n'}
                <Text style={styles.heroTitleAccent}>before you drive.</Text>
              </Text>
              
              <Text style={styles.heroSubtitle}>
                See conditions, alerts, and road hazards for your entire journey. 
                Plan smarter. Arrive safer.
              </Text>

              <View style={styles.heroCtas}>
                <TouchableOpacity 
                  style={styles.primaryCta}
                  onPress={() => scrollToSection('pricing')}
                  data-testid="hero-start-trial"
                >
                  <Ionicons name="rocket" size={20} color="#0f0f0f" />
                  <Text style={styles.primaryCtaText}>Start Free Trial</Text>
                </TouchableOpacity>
                
                <TouchableOpacity 
                  style={styles.secondaryCta}
                  onPress={() => scrollToSection('pricing')}
                  data-testid="hero-view-pricing"
                >
                  <Text style={styles.secondaryCtaText}>View Pricing</Text>
                  <Ionicons name="arrow-down" size={18} color="#eab308" />
                </TouchableOpacity>
              </View>

              <View style={styles.trustBullets}>
                <View style={styles.trustBullet}>
                  <Ionicons name="checkmark-circle" size={16} color="#22c55e" />
                  <Text style={styles.trustBulletText}>7-day free trial</Text>
                </View>
                <View style={styles.trustBullet}>
                  <Ionicons name="checkmark-circle" size={16} color="#22c55e" />
                  <Text style={styles.trustBulletText}>Cancel anytime</Text>
                </View>
                <View style={styles.trustBullet}>
                  <Ionicons name="checkmark-circle" size={16} color="#22c55e" />
                  <Text style={styles.trustBulletText}>Premium unlocks instantly</Text>
                </View>
              </View>
            </View>

            {/* Hero Visual */}
            <View style={styles.heroVisual}>
              <View style={styles.phoneFrame}>
                <View style={styles.phoneScreen}>
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
                <View style={[styles.calloutBubble, styles.calloutLeft]}>
                  <Ionicons name="alert-circle" size={14} color="#ef4444" />
                  <Text style={styles.calloutText}>Severe weather alerts</Text>
                </View>
                <View style={[styles.calloutBubble, styles.calloutRight]}>
                  <Ionicons name="time" size={14} color="#eab308" />
                  <Text style={styles.calloutText}>Hour-by-hour timeline</Text>
                </View>
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

        {/* How It Works Video */}
        <View style={styles.videoSection}>
          <Text style={styles.videoTitle}>How RouteCast Works</Text>
          <Text style={styles.videoSubtitle}>
            Watch this quick walkthrough to see how to use RouteCast and plan safer drives with weather ahead of you.
          </Text>
          <View style={styles.videoContainer}>
            <iframe
              src="https://www.youtube.com/embed/fS-wJRoVlzc?rel=0"
              title="How to Use RouteCast"
              frameBorder="0"
              allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
              allowFullScreen
              style={styles.videoIframe as any}
            />
          </View>
        </View>

        {/* Features Section */}
        <View style={styles.featuresSection} nativeID="features">
          <Text style={styles.sectionTitle}>Everything you need for safer drives</Text>
          <Text style={styles.sectionSubtitle}>
            From departure to destination, we've got you covered
          </Text>
          
          <View style={styles.featuresGrid}>
            <View style={styles.featureCard}>
              <View style={[styles.featureIcon, { backgroundColor: '#422006' }]}>
                <Ionicons name="map" size={24} color="#eab308" />
              </View>
              <Text style={styles.featureTitle}>Route-Based Forecast</Text>
              <Text style={styles.featureDesc}>
                See weather conditions at every point along your route, not just your destination.
              </Text>
            </View>

            <View style={styles.featureCard}>
              <View style={[styles.featureIcon, { backgroundColor: '#14532d' }]}>
                <Ionicons name="warning" size={24} color="#22c55e" />
              </View>
              <Text style={styles.featureTitle}>Weather Alerts</Text>
              <Text style={styles.featureDesc}>
                Get NWS severe weather warnings for your exact route with countdown timers.
              </Text>
            </View>

            <View style={styles.featureCard}>
              <View style={[styles.featureIcon, { backgroundColor: '#1e3a5f' }]}>
                <Ionicons name="speedometer" size={24} color="#3b82f6" />
              </View>
              <Text style={styles.featureTitle}>Road Conditions</Text>
              <Text style={styles.featureDesc}>
                Know when roads are wet, icy, or have low visibility before you encounter them.
              </Text>
            </View>

            <View style={styles.featureCard}>
              <View style={[styles.featureIcon, { backgroundColor: '#4a1d6a' }]}>
                <Ionicons name="time" size={24} color="#a855f7" />
              </View>
              <Text style={styles.featureTitle}>Departure Optimizer</Text>
              <Text style={styles.featureDesc}>
                Find the best time to leave to avoid storms and hazardous conditions.
              </Text>
            </View>

            <View style={styles.featureCard}>
              <View style={[styles.featureIcon, { backgroundColor: '#7c2d12' }]}>
                <Ionicons name="star" size={24} color="#f97316" />
              </View>
              <Text style={styles.featureTitle}>Saved Routes</Text>
              <Text style={styles.featureDesc}>
                Save your frequent trips and check conditions with one tap.
              </Text>
            </View>

            <View style={styles.featureCard}>
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

        {/* Pricing Section */}
        <View style={styles.pricingSection} nativeID="pricing">
          <Text style={styles.sectionTitle}>Simple, transparent pricing</Text>
          <Text style={styles.sectionSubtitle}>
            Start with a 7-day free trial. Cancel anytime.
          </Text>

          <View style={styles.pricingGrid}>
            {/* Monthly Plan */}
            <View style={styles.pricingCard}>
              <Text style={styles.pricingPlan}>Monthly</Text>
              <View style={styles.pricingAmount}>
                <Text style={styles.pricingDollar}>$</Text>
                <Text style={styles.pricingPrice}>9</Text>
                <Text style={styles.pricingCents}>.99</Text>
                <Text style={styles.pricingPeriod}>/month</Text>
              </View>
              <Text style={styles.pricingTrial}>7-day free trial included</Text>
              
              <View style={styles.pricingFeatures}>
                <View style={styles.pricingFeatureRow}>
                  <Ionicons name="checkmark" size={18} color="#22c55e" />
                  <Text style={styles.pricingFeatureText}>Unlimited route forecasts</Text>
                </View>
                <View style={styles.pricingFeatureRow}>
                  <Ionicons name="checkmark" size={18} color="#22c55e" />
                  <Text style={styles.pricingFeatureText}>Real-time weather alerts</Text>
                </View>
                <View style={styles.pricingFeatureRow}>
                  <Ionicons name="checkmark" size={18} color="#22c55e" />
                  <Text style={styles.pricingFeatureText}>Road condition insights</Text>
                </View>
                <View style={styles.pricingFeatureRow}>
                  <Ionicons name="checkmark" size={18} color="#22c55e" />
                  <Text style={styles.pricingFeatureText}>Trucker & RV features</Text>
                </View>
              </View>

              <TouchableOpacity 
                style={styles.pricingButton}
                onPress={() => router.push('/signup?plan=monthly')}
                data-testid="pricing-monthly-btn"
              >
                <Text style={styles.pricingButtonText}>Start Monthly Trial</Text>
              </TouchableOpacity>
            </View>

            {/* Annual Plan */}
            <View style={[styles.pricingCard, styles.pricingCardFeatured]}>
              <View style={styles.pricingBadge}>
                <Text style={styles.pricingBadgeText}>BEST VALUE</Text>
              </View>
              <Text style={styles.pricingPlan}>Annual</Text>
              <View style={styles.pricingAmount}>
                <Text style={styles.pricingDollar}>$</Text>
                <Text style={styles.pricingPrice}>59</Text>
                <Text style={styles.pricingCents}>.99</Text>
                <Text style={styles.pricingPeriod}>/year</Text>
              </View>
              <Text style={styles.pricingTrial}>7-day free trial included</Text>
              <Text style={styles.pricingSavings}>Save $60/year (2 months free)</Text>
              
              <View style={styles.pricingFeatures}>
                <View style={styles.pricingFeatureRow}>
                  <Ionicons name="checkmark" size={18} color="#22c55e" />
                  <Text style={styles.pricingFeatureText}>Everything in Monthly</Text>
                </View>
                <View style={styles.pricingFeatureRow}>
                  <Ionicons name="checkmark" size={18} color="#22c55e" />
                  <Text style={styles.pricingFeatureText}>Priority support</Text>
                </View>
                <View style={styles.pricingFeatureRow}>
                  <Ionicons name="checkmark" size={18} color="#22c55e" />
                  <Text style={styles.pricingFeatureText}>Extended forecast (7 days)</Text>
                </View>
                <View style={styles.pricingFeatureRow}>
                  <Ionicons name="checkmark" size={18} color="#22c55e" />
                  <Text style={styles.pricingFeatureText}>Export routes</Text>
                </View>
              </View>

              <TouchableOpacity 
                style={[styles.pricingButton, styles.pricingButtonFeatured]}
                onPress={() => router.push('/signup?plan=yearly')}
                data-testid="pricing-annual-btn"
              >
                <Text style={styles.pricingButtonTextFeatured}>Start Annual Trial</Text>
              </TouchableOpacity>
            </View>
          </View>

          <Text style={styles.pricingDisclaimer}>
            You'll be redirected to Stripe to complete checkout. Premium access activates automatically after payment confirmation.
          </Text>
        </View>

        {/* Comparison Table */}
        <View style={styles.comparisonSection}>
          <Text style={styles.sectionTitle}>Free vs Premium</Text>
          
          <View style={styles.comparisonTable}>
            <View style={styles.comparisonHeader}>
              <Text style={styles.comparisonHeaderText}>Feature</Text>
              <Text style={styles.comparisonHeaderText}>Free</Text>
              <Text style={styles.comparisonHeaderText}>Premium</Text>
            </View>
            
            <View style={styles.comparisonRow}>
              <Text style={styles.comparisonFeature}>Route weather forecast</Text>
              <Text style={styles.comparisonValue}>Basic</Text>
              <Text style={styles.comparisonValuePremium}>Extended</Text>
            </View>
            
            <View style={styles.comparisonRow}>
              <Text style={styles.comparisonFeature}>Weather alerts</Text>
              <Ionicons name="checkmark-circle" size={18} color="#22c55e" />
              <Ionicons name="checkmark-circle" size={18} color="#22c55e" />
            </View>
            
            <View style={styles.comparisonRow}>
              <Text style={styles.comparisonFeature}>Route monitoring</Text>
              <Text style={styles.comparisonValue}>1 route</Text>
              <Text style={styles.comparisonValuePremium}>Unlimited</Text>
            </View>
            
            <View style={styles.comparisonRow}>
              <Text style={styles.comparisonFeature}>Push notifications</Text>
              <Ionicons name="close-circle" size={18} color="#6b7280" />
              <Ionicons name="checkmark-circle" size={18} color="#22c55e" />
            </View>
            
            <View style={styles.comparisonRow}>
              <Text style={styles.comparisonFeature}>Trucker features</Text>
              <Ionicons name="close-circle" size={18} color="#6b7280" />
              <Ionicons name="checkmark-circle" size={18} color="#22c55e" />
            </View>
            
            <View style={styles.comparisonRow}>
              <Text style={styles.comparisonFeature}>Boondocking tools</Text>
              <Ionicons name="close-circle" size={18} color="#6b7280" />
              <Ionicons name="checkmark-circle" size={18} color="#22c55e" />
            </View>
          </View>
        </View>

        {/* FAQ Section */}
        <View style={styles.faqSection} nativeID="faq">
          <Text style={styles.sectionTitle}>Frequently Asked Questions</Text>
          
          <View style={styles.faqList}>
            {[
              {
                q: 'How does the free trial work?',
                a: 'Start your 7-day free trial by creating an account. You get full access to all premium features. No credit card required to start—you only pay when you choose to subscribe.'
              },
              {
                q: 'How do I cancel my subscription?',
                a: 'You can cancel anytime from your account settings or directly through Stripe. Your premium access continues until the end of your billing period.'
              },
              {
                q: 'How do I get premium access after paying?',
                a: 'Premium access is activated automatically within seconds after Stripe confirms your payment. Just log back in and you\'ll see your premium status updated.'
              },
              {
                q: 'What if I change my email address?',
                a: 'Your subscription is linked to your account by email. If you need to change your email, please contact support so we can update your records and ensure uninterrupted access.'
              },
              {
                q: 'Is my payment secure?',
                a: 'Yes! All payments are processed securely through Stripe. We never see or store your credit card details.'
              },
              {
                q: 'What weather data sources do you use?',
                a: 'We use official NOAA/National Weather Service data for the most accurate forecasts and alerts available for US routes.'
              }
            ].map((faq, index) => (
              <TouchableOpacity 
                key={index}
                style={styles.faqItem}
                onPress={() => setActiveFaq(activeFaq === index ? null : index)}
              >
                <View style={styles.faqQuestion}>
                  <Text style={styles.faqQuestionText}>{faq.q}</Text>
                  <Ionicons 
                    name={activeFaq === index ? 'chevron-up' : 'chevron-down'} 
                    size={20} 
                    color="#a1a1aa" 
                  />
                </View>
                {activeFaq === index && (
                  <Text style={styles.faqAnswer}>{faq.a}</Text>
                )}
              </TouchableOpacity>
            ))}
          </View>
        </View>

        {/* Final CTA */}
        <View style={styles.finalCtaSection}>
          <LinearGradient
            colors={['#1a1a2e', '#16213e', '#0f0f0f']}
            style={styles.finalCtaGradient}
          >
            <Text style={styles.finalCtaTitle}>Ready to drive smarter?</Text>
            <Text style={styles.finalCtaSubtitle}>
              Join thousands of drivers who plan their trips with confidence.
            </Text>
            <TouchableOpacity 
              style={styles.finalCtaButton}
              onPress={() => router.push('/signup')}
              data-testid="final-cta-btn"
            >
              <Text style={styles.finalCtaButtonText}>Start Your Free Trial</Text>
              <Ionicons name="arrow-forward" size={20} color="#0f0f0f" />
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
            <View style={styles.footerStripe}>
              <Ionicons name="lock-closed" size={14} color="#6b7280" />
              <Text style={styles.footerStripeText}>Payments secured by Stripe</Text>
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
  videoSection: {
    paddingHorizontal: 24,
    paddingVertical: 40,
    alignItems: 'center',
    backgroundColor: '#0f0f0f',
  },
  videoTitle: {
    color: '#ffffff',
    fontSize: 28,
    fontWeight: '800',
    textAlign: 'center',
    marginBottom: 8,
  },
  videoSubtitle: {
    color: '#a1a1aa',
    fontSize: 16,
    textAlign: 'center',
    marginBottom: 20,
    maxWidth: 720,
  },
  videoContainer: {
    position: 'relative',
    width: '100%',
    maxWidth: 900,
    paddingBottom: '56.25%',
    height: 0,
    marginTop: 10,
    marginBottom: 10,
    overflow: 'hidden',
  },
  videoIframe: {
    position: 'absolute',
    top: 0,
    left: 0,
    width: '100%',
    height: '100%',
    borderRadius: 12,
    borderWidth: 0,
  },
  navLoginBtn: {
    backgroundColor: '#27272a',
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 8,
  },
  navLoginText: {
    color: '#ffffff',
    fontSize: 14,
    fontWeight: '600',
  },

  // Hero Section
  heroSection: {
    minHeight: 600,
  },
  heroGradient: {
    paddingTop: 40,
    paddingBottom: 60,
    paddingHorizontal: 24,
  },
  heroContent: {
    maxWidth: 600,
    marginHorizontal: 'auto',
    alignItems: 'center',
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
  heroCtas: {
    flexDirection: 'row',
    gap: 16,
    marginBottom: 32,
    flexWrap: 'wrap',
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
  secondaryCta: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    backgroundColor: 'transparent',
    borderWidth: 2,
    borderColor: '#eab308',
    paddingHorizontal: 24,
    paddingVertical: 14,
    borderRadius: 12,
  },
  secondaryCtaText: {
    color: '#eab308',
    fontSize: 16,
    fontWeight: '600',
  },
  trustBullets: {
    flexDirection: 'row',
    gap: 24,
    flexWrap: 'wrap',
    justifyContent: 'center',
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
  phoneScreen: {
    flex: 1,
    backgroundColor: '#0f0f0f',
    borderRadius: 24,
    padding: 16,
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
  featureCard: {
    width: 300,
    backgroundColor: '#1a1a1a',
    borderRadius: 16,
    padding: 24,
    borderWidth: 1,
    borderColor: '#27272a',
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

  // Pricing Section
  pricingSection: {
    backgroundColor: '#141414',
    paddingVertical: 80,
    paddingHorizontal: 24,
  },
  pricingGrid: {
    flexDirection: 'row',
    justifyContent: 'center',
    gap: 24,
    flexWrap: 'wrap',
    marginBottom: 32,
  },
  pricingCard: {
    width: 320,
    backgroundColor: '#1a1a1a',
    borderRadius: 20,
    padding: 32,
    borderWidth: 1,
    borderColor: '#27272a',
    position: 'relative',
  },
  pricingCardFeatured: {
    borderColor: '#eab308',
    borderWidth: 2,
  },
  pricingBadge: {
    position: 'absolute',
    top: -12,
    right: 24,
    backgroundColor: '#eab308',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 12,
  },
  pricingBadgeText: {
    color: '#0f0f0f',
    fontSize: 11,
    fontWeight: '700',
  },
  pricingPlan: {
    color: '#a1a1aa',
    fontSize: 14,
    fontWeight: '600',
    textTransform: 'uppercase',
    letterSpacing: 1,
    marginBottom: 8,
  },
  pricingAmount: {
    flexDirection: 'row',
    alignItems: 'baseline',
    marginBottom: 8,
  },
  pricingDollar: {
    color: '#ffffff',
    fontSize: 20,
    fontWeight: '600',
  },
  pricingPrice: {
    color: '#ffffff',
    fontSize: 48,
    fontWeight: '700',
  },
  pricingCents: {
    color: '#ffffff',
    fontSize: 20,
    fontWeight: '600',
  },
  pricingPeriod: {
    color: '#6b7280',
    fontSize: 16,
    marginLeft: 4,
  },
  pricingTrial: {
    color: '#22c55e',
    fontSize: 13,
    fontWeight: '500',
    marginBottom: 4,
  },
  pricingSavings: {
    color: '#eab308',
    fontSize: 13,
    fontWeight: '600',
    marginBottom: 24,
  },
  pricingFeatures: {
    gap: 12,
    marginBottom: 24,
  },
  pricingFeatureRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  pricingFeatureText: {
    color: '#d4d4d8',
    fontSize: 14,
  },
  pricingButton: {
    backgroundColor: '#27272a',
    paddingVertical: 14,
    borderRadius: 10,
    alignItems: 'center',
  },
  pricingButtonFeatured: {
    backgroundColor: '#eab308',
  },
  pricingButtonText: {
    color: '#ffffff',
    fontSize: 15,
    fontWeight: '600',
  },
  pricingButtonTextFeatured: {
    color: '#0f0f0f',
    fontSize: 15,
    fontWeight: '700',
  },
  pricingDisclaimer: {
    color: '#6b7280',
    fontSize: 12,
    textAlign: 'center',
    maxWidth: 500,
    marginHorizontal: 'auto',
    lineHeight: 18,
  },

  // Comparison Section
  comparisonSection: {
    paddingVertical: 80,
    paddingHorizontal: 24,
  },
  comparisonTable: {
    maxWidth: 600,
    marginHorizontal: 'auto',
    backgroundColor: '#1a1a1a',
    borderRadius: 16,
    overflow: 'hidden',
    borderWidth: 1,
    borderColor: '#27272a',
  },
  comparisonHeader: {
    flexDirection: 'row',
    backgroundColor: '#27272a',
    paddingVertical: 16,
    paddingHorizontal: 20,
  },
  comparisonHeaderText: {
    flex: 1,
    color: '#ffffff',
    fontSize: 13,
    fontWeight: '700',
    textAlign: 'center',
  },
  comparisonRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 14,
    paddingHorizontal: 20,
    borderBottomWidth: 1,
    borderBottomColor: '#27272a',
  },
  comparisonFeature: {
    flex: 1,
    color: '#d4d4d8',
    fontSize: 14,
  },
  comparisonValue: {
    flex: 1,
    color: '#6b7280',
    fontSize: 13,
    textAlign: 'center',
  },
  comparisonValuePremium: {
    flex: 1,
    color: '#22c55e',
    fontSize: 13,
    fontWeight: '600',
    textAlign: 'center',
  },

  // FAQ Section
  faqSection: {
    backgroundColor: '#141414',
    paddingVertical: 80,
    paddingHorizontal: 24,
  },
  faqList: {
    maxWidth: 700,
    marginHorizontal: 'auto',
    gap: 12,
  },
  faqItem: {
    backgroundColor: '#1a1a1a',
    borderRadius: 12,
    padding: 20,
    borderWidth: 1,
    borderColor: '#27272a',
  },
  faqQuestion: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  faqQuestionText: {
    color: '#ffffff',
    fontSize: 15,
    fontWeight: '600',
    flex: 1,
    paddingRight: 16,
  },
  faqAnswer: {
    color: '#a1a1aa',
    fontSize: 14,
    lineHeight: 22,
    marginTop: 12,
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
  footerStripe: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  footerStripeText: {
    color: '#6b7280',
    fontSize: 12,
  },
  footerCopyright: {
    color: '#52525b',
    fontSize: 12,
    textAlign: 'center',
  },
});
