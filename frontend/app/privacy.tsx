import React from 'react';
import { View, Text, StyleSheet, ScrollView } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

export default function PrivacyPolicy() {
  return (
    <SafeAreaView style={styles.container}>
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.title}>Privacy Policy</Text>
        <Text style={styles.updated}>Last updated: 2026-02-23</Text>

        <Text style={styles.heading}>1. Information We Collect</Text>
        <Text style={styles.body}>
          We collect account details you provide (like name and email) and usage data to improve RouteCast. We do not sell your data.
        </Text>

        <Text style={styles.heading}>2. How We Use Data</Text>
        <Text style={styles.body}>
          We use data to provide weather insights, deliver notifications you request, and improve reliability of the service. Emails may be used for account and transactional messages.
        </Text>

        <Text style={styles.heading}>3. Sharing</Text>
        <Text style={styles.body}>
          We share data only with trusted vendors required to operate RouteCast (for example, cloud hosting and analytics). We do not sell or rent personal data.
        </Text>

        <Text style={styles.heading}>4. Security</Text>
        <Text style={styles.body}>
          We use encryption in transit, access controls, and monitoring to protect your data. No system is perfectly secure; contact us if you believe your account is compromised.
        </Text>

        <Text style={styles.heading}>5. Your Choices</Text>
        <Text style={styles.body}>
          You can request deletion of your account or data at any time. Manage notification preferences in the app settings.
        </Text>

        <Text style={styles.heading}>6. Contact</Text>
        <Text style={styles.body}>
          Questions about this policy? Reach us at support@routecastweather.com.
        </Text>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0b0b12' },
  content: { padding: 20, gap: 14 },
  title: { fontSize: 28, fontWeight: '700', color: '#f8fafc' },
  updated: { fontSize: 14, color: '#94a3b8' },
  heading: { fontSize: 18, fontWeight: '600', color: '#e2e8f0', marginTop: 8 },
  body: { fontSize: 16, color: '#cbd5e1', lineHeight: 22 },
});
