import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ScrollView,
  Platform,
} from 'react-native';
import { Ionicons, MaterialCommunityIcons } from '@expo/vector-icons';
import { router } from 'expo-router';

const FAQ_ITEMS = [
  {
    q: 'What is Basic Route Weather?',
    a: 'Enter an origin and destination to see weather conditions along the entire route. Temperature, precipitation, wind speed, and road conditions are shown at each point. This is the core route-weather function.',
  },
  {
    q: 'What are Unlimited Alerts?',
    a: 'Receive NWS severe weather alerts for your route with no cap on the number of alerts you can receive. Alerts trigger when watches or warnings are active along your route path and refresh every 15 minutes.',
  },
  {
    q: 'What is Route Monitoring?',
    a: 'The app monitors your active route as you travel. Route conditions and weather update during the trip so you stay informed about changes without re-entering your route.',
  },
  {
    q: 'How do Push Notifications work?',
    a: 'Alerts can be sent as push notifications for important route and weather updates, including severe weather warnings when the app is running in the background.',
  },
  {
    q: 'What is included in Advanced Weather?',
    a: 'Advanced Weather includes a live precipitation radar overlay on your route map. View rain, snow, and storm cells in real-time with a timeline slider to see forecast movement ahead on your route.',
  },
  {
    q: 'What are Truck Features?',
    a: 'Truck route tools including bridge height alerts, truck stop finder, weigh station locations, truck parking, truck services, and truck restriction information for weight, height, and hazmat routes.',
  },
  {
    q: 'What are Boondocking Features?',
    a: 'Tools for off-grid camping and RV trips including free camping finder, dump station and water locator, last-chance supply finder, solar forecast, propane usage calculator, water budget planner, wind shelter advisor, connectivity checker, and campsite quality scoring.',
  },
  {
    q: 'What is Export Routes?',
    a: 'Share your route forecast to send route weather information to co-drivers or dispatch for coordinated trip planning.',
  },
];

export default function FAQPage() {
  const [activeItem, setActiveItem] = useState<number | null>(null);

  return (
    <View style={styles.container}>
      {/* Navbar — website only: the app has its own back navigation */}
      {Platform.OS === 'web' && (
        <View style={styles.navbar}>
          <View style={styles.navContent}>
            <TouchableOpacity style={styles.logoRow} onPress={() => router.push('/landing')}>
              <MaterialCommunityIcons name="weather-lightning-rainy" size={26} color="#eab308" />
              <Text style={styles.logoText}>RouteCast</Text>
            </TouchableOpacity>
            <View style={styles.navLinks}>
              <TouchableOpacity onPress={() => router.push('/landing')}>
                <Text style={styles.navLink}>Home</Text>
              </TouchableOpacity>
              <TouchableOpacity onPress={() => router.push('/contact')}>
                <Text style={styles.navLink}>Contact</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      )}

      <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.pageTitle}>Frequently Asked Questions</Text>
        <Text style={styles.pageSubtitle}>
          Everything you need to know about RouteCast features.
        </Text>

        <View style={styles.faqList}>
          {FAQ_ITEMS.map((item, index) => (
            <TouchableOpacity
              key={index}
              style={styles.faqItem}
              onPress={() => setActiveItem(activeItem === index ? null : index)}
            >
              <View style={styles.faqQuestion}>
                <Text style={styles.faqQuestionText}>{item.q}</Text>
                <Ionicons
                  name={activeItem === index ? 'chevron-up' : 'chevron-down'}
                  size={20}
                  color="#a1a1aa"
                />
              </View>
              {activeItem === index && (
                <Text style={styles.faqAnswer}>{item.a}</Text>
              )}
            </TouchableOpacity>
          ))}
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
    marginHorizontal: 'auto' as any,
    width: '100%',
  },
  logoRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  logoText: {
    color: '#ffffff',
    fontSize: 20,
    fontWeight: '700',
  },
  navLinks: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 24,
  },
  navLink: {
    color: '#a1a1aa',
    fontSize: 14,
    fontWeight: '500',
  },
  content: {
    maxWidth: 760,
    marginHorizontal: 'auto' as any,
    width: '100%',
    paddingHorizontal: 24,
    paddingTop: 48,
    paddingBottom: 80,
  },
  pageTitle: {
    color: '#ffffff',
    fontSize: 32,
    fontWeight: '700',
    marginBottom: 12,
  },
  pageSubtitle: {
    color: '#a1a1aa',
    fontSize: 16,
    lineHeight: 26,
    marginBottom: 40,
  },
  faqList: {
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
});
