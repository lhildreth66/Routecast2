import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import { router } from 'expo-router';

export default function SubscribeCancel() {
  return (
    <View style={styles.container}>
      <View style={styles.card}>
        <Text style={styles.title}>Checkout Canceled</Text>
        <Text style={styles.text}>No charges were made. You can restart checkout anytime.</Text>
        <TouchableOpacity style={styles.button} onPress={() => router.replace('/subscription')}>
          <Text style={styles.buttonText}>Back to Subscription</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0a0a0a',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 20,
  },
  card: {
    backgroundColor: '#111827',
    borderRadius: 12,
    padding: 20,
    width: '100%',
    maxWidth: 480,
    borderWidth: 1,
    borderColor: '#1f2937',
    alignItems: 'center',
    gap: 12,
  },
  title: {
    color: '#fff',
    fontSize: 20,
    fontWeight: '700',
    textAlign: 'center',
  },
  text: {
    color: '#9ca3af',
    fontSize: 14,
    textAlign: 'center',
  },
  button: {
    marginTop: 8,
    backgroundColor: '#eab308',
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: 8,
  },
  buttonText: {
    color: '#0a0a0a',
    fontWeight: '700',
    fontSize: 14,
  },
});
