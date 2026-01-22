import React, { useState } from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { router } from 'expo-router';

interface PremiumFeaturesPanelProps {
  onRoadPassability?: () => void;
  onConnectivity?: () => void;
  onCampsiteIndex?: () => void;  onTractorTrailerPro: () => void;}

export default function PremiumFeaturesPanel({
  onRoadPassability,
  onConnectivity,
  onCampsiteIndex,
}: PremiumFeaturesPanelProps) {
  const [expanded, setExpanded] = useState(false);

  const handleRoadPassability = () => {
    if (onRoadPassability) {
      onRoadPassability();
    } else {
      router.push('/road-passability');
    }
  };

  const handleConnectivity = () => {
    if (onConnectivity) {
      onConnectivity();
    } else {
      router.push('/connectivity');
    }
  };

  const handleCampsiteIndex = () => {
    if (onCampsiteIndex) {
      onCampsiteIndex();
    } else {
      router.push('/campsite-index');
    }
  };

  return (
    <View style={styles.container}>
      {/* Header */}
      <TouchableOpacity
        style={styles.header}
        onPress={() => setExpanded(!expanded)}
        activeOpacity={0.7}
      >
        <View style={styles.headerLeft}>
          <Ionicons name="diamond" size={18} color="#eab308" />
          <Text style={styles.headerTitle}>Premium Features</Text>
        </View>
        <Ionicons
          name={expanded ? 'chevron-up' : 'chevron-down'}
          size={20}
          color="#71717a"
        />
      </TouchableOpacity>

      {/* Expanded Content */}
      {expanded && (
        <View style={styles.buttonsContainer}>
          <TouchableOpacity
            onPress={handleRoadPassability}
            style={styles.proButton}
          >
            <Ionicons name="navigate-circle" size={20} color="#1a1a1a" />
            <Text style={styles.proButtonText}>Assess Road Passability</Text>
            <View style={styles.proBadge}>
              <Text style={styles.proBadgeText}>PRO</Text>
            </View>
          </TouchableOpacity>

          <TouchableOpacity
            onPress={handleConnectivity}
            style={styles.proButton}
          >
            <Ionicons name="signal" size={20} color="#1a1a1a" />
            <Text style={styles.proButtonText}>Predict Connectivity</Text>
            <View style={styles.proBadge}>
              <Text style={styles.proBadgeText}>PRO</Text>
            </View>
          </TouchableOpacity>

          <TouchableOpacity
            onPress={handleCampsiteIndex}
            style={styles.proButton}
          >
            <Ionicons name="location" size={20} color="#1a1a1a" />
            <Text style={styles.proButtonText}>Calculate Campsite Index</Text>
            <View style={styles.proBadge}>
              <Text style={styles.proBadgeText}>PRO</Text>
            </View>
          </TouchableOpacity>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: '#18181b',
    borderRadius: 12,
    marginHorizontal: 16,
    marginTop: 12,
    overflow: 'hidden',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 14,
    backgroundColor: '#27272a',
  },
  headerLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  headerTitle: {
    color: '#ffffff',
    fontSize: 16,
    fontWeight: '600',
  },
  buttonsContainer: {
    padding: 12,
    gap: 8,
  },
  proButton: {
    backgroundColor: '#eab308',
    paddingVertical: 12,
    paddingHorizontal: 16,
    borderRadius: 8,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  proButtonText: {
    color: '#1a1a1a',
    fontWeight: '700',
    fontSize: 15,
    flex: 1,
  },
  proBadge: {
    backgroundColor: '#1a1a1a',
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 4,
  },
  proBadgeText: {
    color: '#eab308',
    fontSize: 11,
    fontWeight: '700',
  },
});
