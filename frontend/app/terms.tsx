import React from 'react';
import { View, Text, StyleSheet, ScrollView } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

export default function TermsOfService() {
  return (
    <SafeAreaView style={styles.container}>
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.title}>Terms of Service</Text>
        <Text style={styles.updated}>Last updated: 2026-02-23</Text>

        <Text style={styles.heading}>1. Your Agreement</Text>
        <Text style={styles.body}>
          By using RouteCast, you agree to these terms. If you do not agree, do not use the service.
        </Text>

        <Text style={styles.heading}>2. Use of Service</Text>
        <Text style={styles.body}>
          RouteCast provides route-based weather insights. You are responsible for safe driving decisions and complying with local laws.
        </Text>

        <Text style={styles.heading}>3. Accounts</Text>
        <Text style={styles.body}>
          Keep your login credentials secure. You are responsible for activity under your account. We may suspend accounts for abuse.
        </Text>

        <Text style={styles.heading}>4. Billing</Text>
        <Text style={styles.body}>
          Paid plans auto-renew until canceled. Fees are non-refundable except where required by law. Manage subscriptions in-app.
        </Text>

        <Text style={styles.heading}>5. Disclaimers</Text>
        <Text style={styles.body}>
          Weather data can change. RouteCast provides information "as is" without warranties. We are not liable for indirect or consequential damages.
        </Text>

        <Text style={styles.heading}>6. Contact</Text>
        <Text style={styles.body}>
          Questions about these terms? Email support@routecastweather.com.
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
