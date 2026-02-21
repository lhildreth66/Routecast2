import React from 'react';
import { View, Text, StyleSheet } from 'react-native';

export default function SubscriptionCanceledScreen() {
  return (
    <View style={styles.container}>
      <Text style={styles.title}>Checkout Canceled</Text>
      <Text style={styles.message}>No charges were made. You can restart the trial anytime from the subscription page.</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0a0a0a',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
    gap: 12,
  },
  title: {
    color: '#fee2e2',
    fontSize: 22,
    fontWeight: '800',
  },
  message: {
    color: '#e5e7eb',
    fontSize: 15,
    textAlign: 'center',
    lineHeight: 22,
  },
});
