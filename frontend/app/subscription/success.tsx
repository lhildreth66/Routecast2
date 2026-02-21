import React from 'react';
import { View, Text, StyleSheet } from 'react-native';

export default function SubscriptionSuccessScreen() {
  return (
    <View style={styles.container}>
      <Text style={styles.title}>Trial Activated</Text>
      <Text style={styles.message}>Your 7-day premium trial has started. You can close this page and return to Routecast.</Text>
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
    color: '#f0fdf4',
    fontSize: 22,
    fontWeight: '800',
  },
  message: {
    color: '#d1d5db',
    fontSize: 15,
    textAlign: 'center',
    lineHeight: 22,
  },
});
