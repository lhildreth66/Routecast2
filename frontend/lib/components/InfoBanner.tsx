import React, { useEffect, useRef, useState } from 'react';
import { Animated, StyleSheet, Text, TouchableOpacity, ViewStyle, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

interface InfoBannerProps {
  message: string;
  duration?: number; // milliseconds before auto-dismiss
  style?: ViewStyle;
  testID?: string;
}

export default function InfoBanner({ message, duration = 5000, style, testID }: InfoBannerProps) {
  const [visible, setVisible] = useState(true);
  const opacity = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    Animated.timing(opacity, {
      toValue: 1,
      duration: 200,
      useNativeDriver: true,
    }).start();

    const timer = setTimeout(() => {
      Animated.timing(opacity, {
        toValue: 0,
        duration: 220,
        useNativeDriver: true,
      }).start(({ finished }) => {
        if (finished) setVisible(false);
      });
    }, duration);

    return () => clearTimeout(timer);
  }, [duration, opacity]);

  if (!visible) return null;

  const dismiss = () => {
    Animated.timing(opacity, {
      toValue: 0,
      duration: 180,
      useNativeDriver: true,
    }).start(() => setVisible(false));
  };

  return (
    <Animated.View style={[styles.banner, { opacity }, style]} accessibilityRole="alert" testID={testID}>
      <View style={styles.iconWrapper}>
        <Ionicons name="information-circle" size={16} color="#0f172a" />
      </View>
      <Text style={styles.text}>{message}</Text>
      <TouchableOpacity onPress={dismiss} style={styles.close} hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}>
        <Ionicons name="close" size={14} color="#0f172a" />
      </TouchableOpacity>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  banner: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#dbeafe',
    borderColor: '#93c5fd',
    borderWidth: 1,
    borderRadius: 12,
    paddingVertical: 10,
    paddingHorizontal: 12,
    gap: 10,
  },
  iconWrapper: {
    width: 18,
    alignItems: 'center',
  },
  text: {
    flex: 1,
    color: '#0b1224',
    fontSize: 12,
    lineHeight: 17,
  },
  close: {
    paddingLeft: 6,
  },
});
