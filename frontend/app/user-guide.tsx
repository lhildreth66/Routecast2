import React, { useState } from 'react';
import { 
  View, 
  Text, 
  StyleSheet, 
  TouchableOpacity, 
  ScrollView, 
  Dimensions 
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';

const { width } = Dimensions.get('window');

interface GuideSection {
  id: string;
  title: string;
  icon: string;
  color: string;
  description: string;
  features: {
    name: string;
    icon: string;
    description: string;
    tips?: string[];
  }[];
}

const guideSections: GuideSection[] = [
  {
    id: 'getting-started',
    title: 'Getting Started',
    icon: 'rocket',
    color: '#8b5cf6',
    description: 'Welcome to RouteCast! Your complete weather and route planning companion.',
    features: [
      {
        name: 'Enter Your Route',
        icon: 'navigate',
        description: 'Enter origin and destination addresses on the home screen. Use the microphone for voice input.',
        tips: ['Enable location services for automatic starting point', 'Use landmarks or city names for faster entry']
      },
      {
        name: 'Select Vehicle Type',
        icon: 'car',
        description: 'Choose Car, Semi Truck, RV, Motorcycle, or Vehicle with Trailer to get customized safety scores and route recommendations.',
        tips: ['Different vehicles get different hazard scores', 'Change vehicle type anytime']
      },
      {
        name: 'Add Stops',
        icon: 'location',
        description: 'Add waypoints by tapping "Add Stop" on the home screen. Perfect for multi-leg road trips.',
        tips: ['Unlimited stops supported', 'Drag to reorder stops', 'Weather calculated for each segment']
      },
      {
        name: 'Push Notifications',
        icon: 'notifications',
        description: 'Get real-time weather alerts for severe conditions along your route. Never miss tornado, flash flood, or blizzard warnings.',
        tips: ['Enable notifications when prompted', 'Critical alerts for tornado/flash flood', 'Customize in device settings']
      },
      {
        name: 'AI Chat Assistant',
        icon: 'chatbubbles',
        description: 'Ask questions about your route, weather, or get travel recommendations. The AI knows your current route context.',
        tips: ['Ask "What should I watch out for?"', 'Request rest stop recommendations', 'Get advice on best travel times', 'Tap chat bubble in bottom right']
      }
    ]
  },
  {
    id: 'hazards-alerts',
    title: 'Hazards & Safety Alerts',
    icon: 'alert-circle',
    color: '#ef4444',
    description: 'Stay informed about road hazards and safety concerns.',
    features: [
      {
        name: 'Bridge Height Alerts',
        icon: 'git-commit',
        description: 'Warnings for low clearance bridges on your route. Essential for RVs and commercial trucks. Shows exact height in feet and inches.',
        tips: ['Critical for RVs and semi trucks', 'Shows exact clearance height', 'Plan alternate routes in advance']
      },
      {
        name: 'Tornado Warnings',
        icon: 'warning',
        description: 'Real-time tornado warnings from NWS with exact location and expiration time. Immediate push notifications.',
        tips: ['Take shelter immediately', 'Check weather alerts tab', 'Monitor until warning expires']
      },
      {
        name: 'Flash Flood Warnings',
        icon: 'water',
        description: 'Critical flood alerts along your route. Never drive through standing water—turn around, don\'t drown.',
        tips: ['Avoid low-lying areas', 'Never drive through water', 'Seek higher ground']
      },
      {
        name: 'Winter Storm Warnings',
        icon: 'snow',
        description: 'Blizzard, ice storm, and winter weather alerts with snowfall predictions and ice accumulation.',
        tips: ['Carry emergency supplies', 'Reduce speed in snow/ice', 'Consider delaying travel']
      },
      {
        name: 'Severe Thunderstorms',
        icon: 'thunderstorm',
        description: 'High wind, hail, and lightning warnings. Includes predicted hail size and wind speeds.',
        tips: ['Pull over for large hail', 'Wait out severe storms', 'Avoid open areas in lightning']
      }
    ]
  },
  {
    id: 'boondockers',
    title: 'Boondockers Tools',
    icon: 'bonfire',
    color: '#8b4513',
    description: 'Complete toolkit for off-grid camping and RV living.',
    features: [
      {
        name: 'Free Camping Finder',
        icon: 'leaf',
        description: 'Discover BLM land, National Forest dispersed camping, and other free camping spots near your location.',
        tips: ['Results sorted by distance', 'Shows access road conditions', 'Tap Navigate for directions']
      },
      {
        name: 'Dump Station Finder',
        icon: 'water',
        description: 'Locate RV dump stations and fresh water fill points. Includes fee info and hours when available.',
        tips: ['Filter by free vs paid', 'Shows potable water availability', 'Distance in miles from your location']
      },
      {
        name: 'Last Chance Supplies',
        icon: 'cart',
        description: 'Find grocery stores, propane refill, hardware stores, and other essential supply stops before heading to remote areas.',
        tips: ['Search before leaving cell coverage', 'Shows store types and distances', 'Includes 24-hour options']
      },
      {
        name: 'RV Dealerships',
        icon: 'construct',
        description: 'Locate nearby RV dealerships for repairs, parts, and service. Useful for emergencies on the road.',
        tips: ['Shows service types offered', 'Includes phone numbers', 'Results within 10 mile radius']
      },
      {
        name: 'Solar Forecast',
        icon: 'sunny',
        description: 'Predict daily solar energy generation based on your location, panel size, shade, and weather forecast.',
        tips: ['Enter your panel wattage', 'Accounts for cloud cover', 'Shows Wh/day estimates']
      },
      {
        name: 'Propane Usage Calculator',
        icon: 'flame',
        description: 'Estimate propane consumption based on furnace BTU, overnight temperatures, and usage patterns.',
        tips: ['Enter your furnace BTU rating', 'Accounts for duty cycle', 'Shows lbs/day consumption']
      },
      {
        name: 'Water Budget Planner',
        icon: 'water',
        description: 'Calculate how many days your fresh, gray, and black tanks will last based on usage patterns.',
        tips: ['Enter tank capacities in gallons', 'Adjust for people count', 'Shows daily usage rates']
      },
      {
        name: 'Wind & Shelter Analysis',
        icon: 'cloudy',
        description: 'Plan campsite orientation based on forecasted wind direction. Minimize wind exposure for comfort.',
        tips: ['Points RV in optimal direction', 'Accounts for terrain', 'Reduces propane usage']
      },
      {
        name: 'Connectivity Prediction',
        icon: 'wifi',
        description: 'Predict cell signal strength at your destination using crowd-sourced data and tower locations.',
        tips: ['Shows carrier coverage', 'Useful for remote work', 'Plan communication needs']
      },
      {
        name: 'Campsite Suitability Index',
        icon: 'star',
        description: 'Score potential campsites based on shade, wind, terrain, and accessibility. Find the perfect spot.',
        tips: ['Combines multiple factors', 'Weather-based scoring', 'Updated with conditions']
      },
      {
        name: 'Camp Prep Checklist',
        icon: 'checkbox',
        description: 'Interactive checklist for setting up camp. Never forget to check wheels, level, or connect utilities.',
      }
    ]
  },
  {
    id: 'tractor-trailer',
    title: 'Tractor Trailer Features',
    icon: 'bus',
    color: '#3b82f6',
    description: 'Professional tools designed for commercial truck drivers.',
    features: [
      {
        name: 'Truck Stops & Fuel',
        icon: 'speedometer',
        description: 'Find truck stops with diesel, DEF, and amenities. Shows major chains and independent stops.',
        tips: ['Filter by amenities', 'Shows current fuel prices when available', 'Includes parking availability']
      },
      {
        name: 'Weigh Stations',
        icon: 'scale',
        description: 'Locate weigh stations along highways. Shows open/closed status when available and bypass info.',
        tips: ['Check before route planning', 'Shows PrePass/Drivewyze info', 'Distance from current location']
      },
      {
        name: 'Truck Parking',
        icon: 'car',
        description: 'Find safe overnight parking at rest areas, truck stops, and designated parking lots.',
        tips: ['Essential for HOS compliance', 'Shows security features', 'Reserve spots when available']
      },
      {
        name: 'Low Clearance Alerts',
        icon: 'alert',
        description: 'Warnings for bridges, tunnels, and overpasses with height restrictions. Critical for preventing strikes.',
        tips: ['Enter your trailer height', 'Shows exact clearance in ft/in', 'Alerts well in advance']
      },
      {
        name: 'Truck Services',
        icon: 'build',
        description: 'Find repair shops, tire services, truck washes, and CAT scales near your location.',
        tips: ['Filter by service type', 'Shows 24-hour availability', 'Includes phone numbers']
      },
      {
        name: 'Truck Restrictions',
        icon: 'close-circle',
        description: 'View weight limits, height restrictions, hazmat restrictions, and truck-banned routes in your area.',
        tips: ['Check before unfamiliar routes', 'Shows restriction type and limit', 'Includes tunnel restrictions']
      }
    ]
  },
  {
    id: 'tips-tricks',
    title: 'Tips & Tricks',
    icon: 'star',
    color: '#22c55e',
    description: 'Get the most out of RouteCast.',
    features: [
      {
        name: 'Voice Input',
        icon: 'mic',
        description: 'Tap the microphone icon to speak your origin and destination instead of typing.',
      },
      {
        name: 'Pull to Refresh',
        icon: 'refresh',
        description: 'Pull down on any screen to refresh data with the latest information.',
      },
      {
        name: 'Location Auto-Detect',
        icon: 'locate',
        description: 'All location-based features automatically detect your position. Tap the refresh icon to update.',
      },
      {
        name: 'Offline Planning',
        icon: 'download',
        description: 'View previously loaded routes even without internet. Data refreshes when connected.',
      },
      {
        name: 'Share Routes',
        icon: 'share',
        description: 'Share your route forecast with co-drivers or dispatch for coordinated planning.',
      }
    ]
  }
];

export default function UserGuideScreen() {
  const router = useRouter();
  const [expandedSection, setExpandedSection] = useState<string | null>('getting-started');

  const toggleSection = (sectionId: string) => {
    setExpandedSection(expandedSection === sectionId ? null : sectionId);
  };

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="arrow-back" size={24} color="#fff" />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>User Guide</Text>
        <View style={{ width: 40 }} />
      </View>

      <ScrollView style={styles.content} showsVerticalScrollIndicator={false}>
        {/* Welcome Banner */}
        <View style={styles.welcomeBanner}>
          <View style={styles.welcomeIconRow}>
            <View style={[styles.welcomeIcon, { backgroundColor: '#eab30820' }]}>
              <Ionicons name="partly-sunny" size={28} color="#eab308" />
            </View>
            <View style={[styles.welcomeIcon, { backgroundColor: '#3b82f620' }]}>
              <Ionicons name="navigate" size={28} color="#3b82f6" />
            </View>
            <View style={[styles.welcomeIcon, { backgroundColor: '#22c55e20' }]}>
              <Ionicons name="shield-checkmark" size={28} color="#22c55e" />
            </View>
          </View>
          <Text style={styles.welcomeTitle}>Welcome to RouteCast</Text>
          <Text style={styles.welcomeSubtitle}>
            Weather-smart route planning for RVers, truckers, and travelers
          </Text>
        </View>

        {/* Quick Stats */}
        <View style={styles.statsRow}>
          <View style={styles.statCard}>
            <Text style={styles.statNumber}>10+</Text>
            <Text style={styles.statLabel}>Features</Text>
          </View>
          <View style={styles.statCard}>
            <Text style={styles.statNumber}>5</Text>
            <Text style={styles.statLabel}>Boondocker Tools</Text>
          </View>
          <View style={styles.statCard}>
            <Text style={styles.statNumber}>6</Text>
            <Text style={styles.statLabel}>Trucker Tools</Text>
          </View>
          <View style={styles.statCard}>
            <Text style={styles.statNumber}>24/7</Text>
            <Text style={styles.statLabel}>Weather Alerts</Text>
          </View>
        </View>

        {/* Feature Sections */}
        {guideSections.map((section) => (
          <TouchableOpacity
            key={section.id}
            style={styles.sectionCard}
            onPress={() => toggleSection(section.id)}
            activeOpacity={0.7}
          >
            <View style={styles.sectionTop}>
              <View style={[styles.sectionIcon, { backgroundColor: `${section.color}20` }]}>
                <Ionicons name={section.icon as any} size={24} color={section.color} />
              </View>
              <View style={styles.sectionInfo}>
                <Text style={styles.sectionTitle}>{section.title}</Text>
                <Text style={styles.sectionDesc} numberOfLines={expandedSection === section.id ? undefined : 1}>
                  {section.description}
                </Text>
              </View>
              <View style={styles.expandIndicator}>
                <Text style={styles.featureCount}>{section.features.length}</Text>
                <Ionicons 
                  name={expandedSection === section.id ? 'chevron-up' : 'chevron-down'} 
                  size={20} 
                  color="#9ca3af" 
                />
              </View>
            </View>

            {expandedSection === section.id && (
              <View style={styles.sectionExpanded}>
                {section.features.map((feature, index) => (
                  <View key={index} style={styles.featureItem}>
                    <View style={[styles.featureIcon, { backgroundColor: `${section.color}15` }]}>
                      <Ionicons name={feature.icon as any} size={18} color={section.color} />
                    </View>
                    <View style={styles.featureContent}>
                      <Text style={styles.featureName}>{feature.name}</Text>
                      <Text style={styles.featureDesc}>{feature.description}</Text>
                      {feature.tips && feature.tips.length > 0 && (
                        <View style={styles.tipsBox}>
                          {feature.tips.map((tip, tipIndex) => (
                            <View key={tipIndex} style={styles.tipRow}>
                              <Ionicons name="checkmark-circle" size={14} color="#22c55e" />
                              <Text style={styles.tipText}>{tip}</Text>
                            </View>
                          ))}
                        </View>
                      )}
                    </View>
                  </View>
                ))}
              </View>
            )}
          </TouchableOpacity>
        ))}

        {/* Important Notes */}
        <View style={styles.notesCard}>
          <View style={styles.notesHeader}>
            <Ionicons name="information-circle" size={20} color="#06b6d4" />
            <Text style={styles.notesTitle}>Important Notes</Text>
          </View>
          <View style={styles.noteItem}>
            <Text style={styles.noteText}>• Weather alerts are capped at 10 alerts from the last 2 hours along your route</Text>
          </View>
          <View style={styles.noteItem}>
            <Text style={styles.noteText}>• Location services must be enabled for auto-detect features</Text>
          </View>
          <View style={styles.noteItem}>
            <Text style={styles.noteText}>• Push notifications require a one-time permission grant</Text>
          </View>
          <View style={styles.noteItem}>
            <Text style={styles.noteText}>• All features included with your subscription - no paywalls</Text>
          </View>
        </View>

        {/* Pricing */}
        <View style={styles.pricingCard}>
          <View style={styles.pricingHeader}>
            <Ionicons name="diamond" size={24} color="#eab308" />
            <Text style={styles.pricingTitle}>Subscription Plans</Text>
          </View>
          <Text style={styles.pricingSubtitle}>Start with a FREE 1-week trial</Text>

          <View style={styles.pricingOptions}>
            <View style={styles.pricingOption}>
              <Text style={styles.pricingAmount}>$9.99</Text>
              <Text style={styles.pricingPeriod}>per month</Text>
              <Text style={styles.pricingNote}>Billed monthly</Text>
            </View>
            
            <View style={styles.pricingDivider} />
            
            <View style={[styles.pricingOption, styles.pricingBest]}>
              <View style={styles.saveBadge}>
                <Text style={styles.saveBadgeText}>SAVE 50%</Text>
              </View>
              <Text style={styles.pricingAmount}>$59.99</Text>
              <Text style={styles.pricingPeriod}>per year</Text>
              <Text style={styles.pricingNote}>Just $5/month</Text>
            </View>
          </View>
          
          <Text style={styles.pricingFooter}>
            All features included • Cancel anytime • Managed by Google Play
          </Text>
        </View>

        {/* Support */}
        <View style={styles.supportCard}>
          <Ionicons name="help-buoy" size={24} color="#8b5cf6" />
          <View style={styles.supportInfo}>
            <Text style={styles.supportTitle}>Need Help?</Text>
            <Text style={styles.supportText}>
              Contact support or use the AI chat for assistance with any feature.
            </Text>
          </View>
        </View>

        <View style={{ height: 40 }} />
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
    borderBottomColor: '#1f1f1f',
  },
  backButton: {
    width: 40,
    height: 40,
    justifyContent: 'center',
    alignItems: 'center',
  },
  headerTitle: {
    color: '#fff',
    fontSize: 18,
    fontWeight: '600',
  },
  content: {
    flex: 1,
    padding: 16,
  },
  welcomeBanner: {
    backgroundColor: '#1a1a2e',
    borderRadius: 16,
    padding: 24,
    alignItems: 'center',
    marginBottom: 16,
    borderWidth: 1,
    borderColor: '#8b5cf620',
  },
  welcomeIconRow: {
    flexDirection: 'row',
    gap: 12,
    marginBottom: 16,
  },
  welcomeIcon: {
    width: 56,
    height: 56,
    borderRadius: 28,
    justifyContent: 'center',
    alignItems: 'center',
  },
  welcomeTitle: {
    color: '#fff',
    fontSize: 22,
    fontWeight: '700',
    marginBottom: 8,
  },
  welcomeSubtitle: {
    color: '#9ca3af',
    fontSize: 14,
    textAlign: 'center',
  },
  statsRow: {
    flexDirection: 'row',
    gap: 10,
    marginBottom: 20,
  },
  statCard: {
    flex: 1,
    backgroundColor: '#1a1a1a',
    borderRadius: 12,
    padding: 14,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#27272a',
  },
  statNumber: {
    color: '#eab308',
    fontSize: 22,
    fontWeight: '800',
  },
  statLabel: {
    color: '#9ca3af',
    fontSize: 11,
    marginTop: 4,
    textAlign: 'center',
  },
  sectionCard: {
    backgroundColor: '#1a1a1a',
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: '#27272a',
  },
  sectionTop: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  sectionIcon: {
    width: 48,
    height: 48,
    borderRadius: 12,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  sectionInfo: {
    flex: 1,
  },
  sectionTitle: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '600',
    marginBottom: 4,
  },
  sectionDesc: {
    color: '#9ca3af',
    fontSize: 13,
    lineHeight: 18,
  },
  expandIndicator: {
    alignItems: 'center',
  },
  featureCount: {
    color: '#6b7280',
    fontSize: 12,
    fontWeight: '600',
    marginBottom: 2,
  },
  sectionExpanded: {
    marginTop: 16,
    paddingTop: 16,
    borderTopWidth: 1,
    borderTopColor: '#27272a',
  },
  featureItem: {
    flexDirection: 'row',
    marginBottom: 16,
  },
  featureIcon: {
    width: 36,
    height: 36,
    borderRadius: 10,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  featureContent: {
    flex: 1,
  },
  featureName: {
    color: '#fff',
    fontSize: 15,
    fontWeight: '600',
    marginBottom: 4,
  },
  featureDesc: {
    color: '#a1a1aa',
    fontSize: 13,
    lineHeight: 19,
  },
  tipsBox: {
    marginTop: 10,
    backgroundColor: '#0d2818',
    borderRadius: 8,
    padding: 10,
    borderWidth: 1,
    borderColor: '#22c55e20',
  },
  tipRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    marginBottom: 6,
    gap: 6,
  },
  tipText: {
    color: '#86efac',
    fontSize: 12,
    flex: 1,
    lineHeight: 16,
  },
  notesCard: {
    backgroundColor: '#0c1929',
    borderRadius: 12,
    padding: 16,
    marginTop: 8,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: '#06b6d420',
  },
  notesHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 12,
  },
  notesTitle: {
    color: '#06b6d4',
    fontSize: 15,
    fontWeight: '600',
  },
  noteItem: {
    marginBottom: 8,
  },
  noteText: {
    color: '#94a3b8',
    fontSize: 13,
    lineHeight: 18,
  },
  pricingCard: {
    backgroundColor: '#1a1a1a',
    borderRadius: 12,
    padding: 20,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: '#eab30830',
  },
  pricingHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    marginBottom: 4,
  },
  pricingTitle: {
    color: '#fff',
    fontSize: 18,
    fontWeight: '700',
  },
  pricingSubtitle: {
    color: '#22c55e',
    fontSize: 14,
    fontWeight: '600',
    marginBottom: 16,
  },
  pricingOptions: {
    flexDirection: 'row',
    gap: 12,
    marginBottom: 16,
  },
  pricingOption: {
    flex: 1,
    backgroundColor: '#27272a',
    borderRadius: 12,
    padding: 16,
    alignItems: 'center',
  },
  pricingBest: {
    backgroundColor: '#1c1917',
    borderWidth: 2,
    borderColor: '#eab308',
  },
  saveBadge: {
    position: 'absolute',
    top: -10,
    backgroundColor: '#eab308',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 10,
  },
  saveBadgeText: {
    color: '#000',
    fontSize: 11,
    fontWeight: '800',
  },
  pricingAmount: {
    color: '#fff',
    fontSize: 28,
    fontWeight: '800',
    marginTop: 8,
  },
  pricingPeriod: {
    color: '#9ca3af',
    fontSize: 13,
    marginTop: 2,
  },
  pricingNote: {
    color: '#6b7280',
    fontSize: 12,
    marginTop: 6,
  },
  pricingDivider: {
    width: 1,
    backgroundColor: '#374151',
  },
  pricingFooter: {
    color: '#6b7280',
    fontSize: 12,
    textAlign: 'center',
  },
  supportCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1a1a2e',
    borderRadius: 12,
    padding: 16,
    gap: 12,
    borderWidth: 1,
    borderColor: '#8b5cf620',
  },
  supportInfo: {
    flex: 1,
  },
  supportTitle: {
    color: '#fff',
    fontSize: 15,
    fontWeight: '600',
    marginBottom: 4,
  },
  supportText: {
    color: '#9ca3af',
    fontSize: 13,
  },
});
