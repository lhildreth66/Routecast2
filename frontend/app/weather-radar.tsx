import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  SafeAreaView,
} from 'react-native';
import { router } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { WebView } from 'react-native-webview';

export default function WeatherRadarScreen() {
  // RainViewer embeddable map - shows live precipitation radar
  const radarUrl = 'https://www.rainviewer.com/map.html';

  return (
    <SafeAreaView style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()}>
          <Ionicons name="chevron-back" size={24} color="#e4e4e7" />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Weather Radar</Text>
        <View style={{ width: 24 }} />
      </View>

      {/* Radar Map */}
      <WebView
        source={{ uri: radarUrl }}
        style={styles.webview}
        javaScriptEnabled={true}
        domStorageEnabled={true}
        startInLoadingState={true}
        scalesPageToFit={true}
      />

      {/* Info Footer */}
      <View style={styles.footer}>
        <Text style={styles.footerText}>
          🌧️ Live precipitation radar • Powered by RainViewer (Free)
        </Text>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#18181b',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#27272a',
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: '#ffffff',
  },
  webview: {
    flex: 1,
  },
  footer: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    backgroundColor: '#27272a',
    borderTopWidth: 1,
    borderTopColor: '#3f3f46',
  },
  footerText: {
    color: '#9ca3af',
    fontSize: 12,
    textAlign: 'center',
  },
});
