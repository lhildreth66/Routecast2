import { useState, useEffect } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';

export interface PremiumFeature {
  id: string;
  name: string;
  isPremium: boolean;
  description: string;
}

export const FEATURES = {
  // Free features
  WEATHER_WARNINGS: { id: 'weather_warnings', name: 'Weather Warnings', isPremium: false, description: 'Real-time weather alerts along your route' },
  ROAD_SURFACE_WARNINGS: { id: 'road_surface', name: 'Road Surface Warnings', isPremium: false, description: 'Ice, flooding, and road condition alerts' },
  BRIDGE_HEIGHT_ALERTS: { id: 'bridge_alerts', name: 'Bridge Height Alerts', isPremium: false, description: 'RV/Trucker clearance warnings' },
  LIVE_RADAR: { id: 'live_radar', name: 'Live Radar', isPremium: false, description: 'Current weather radar map' },
  TIME_DEPARTURE: { id: 'time_departure', name: 'Departure Time Changes', isPremium: false, description: 'Adjust departure time and date' },
  BASIC_AI_CHAT: { id: 'basic_ai_chat', name: 'Basic AI Chat', isPremium: false, description: 'Ask about driving safety' },
  MAJOR_WEATHER_ALERTS: { id: 'major_alerts', name: 'Major Weather Alerts', isPremium: false, description: 'Severe weather notifications' },
  GOOGLE_MAPS: { id: 'google_maps', name: 'Google Maps Integration', isPremium: false, description: 'Full map features' },
  RECENT_FAVORITES: { id: 'recent_favorites', name: 'Recent & Favorites', isPremium: false, description: 'Save and access favorite routes' },
  BASIC_PUSH_ALERTS: { id: 'basic_push', name: 'Basic Push Alerts', isPremium: false, description: 'Weather notifications on your device' },
  
  // Premium features
  FUTURE_WEATHER: { id: 'future_weather', name: 'Future Weather Forecast', isPremium: true, description: 'Weather predictions along your ETA route' },
  RADAR_PLAYBACK: { id: 'radar_playback', name: 'Radar Playback & History', isPremium: true, description: 'Review past 2-6 hours of radar' },
  ADVANCED_PUSH_ALERTS: { id: 'advanced_push', name: 'Advanced Push Alerts', isPremium: true, description: 'Hail, freezing rain, wind gust alerts' },
  PREDICTIVE_STORM: { id: 'predictive_storm', name: 'Predictive Storm Intercept', isPremium: true, description: 'Storm path predictions' },
};

export const usePremium = () => {
  const [isPremium, setIsPremium] = useState(false);
  const [loading, setLoading] = useState(true);
  const [subscriptionId, setSubscriptionId] = useState<string | null>(null);

  useEffect(() => {
    loadPremiumStatus();
  }, []);

  const loadPremiumStatus = async () => {
    try {
      setLoading(true);
      const status = await AsyncStorage.getItem('routecast_premium_status');
      const subId = await AsyncStorage.getItem('routecast_subscription_id');
      
      if (status === 'active') {
        setIsPremium(true);
        setSubscriptionId(subId);
      } else {
        setIsPremium(false);
        setSubscriptionId(null);
      }
    } catch (err) {
      console.log('Error loading premium status:', err);
      setIsPremium(false);
    } finally {
      setLoading(false);
    }
  };

  const setPremiumStatus = async (status: boolean, subId?: string) => {
    try {
      if (status) {
        await AsyncStorage.setItem('routecast_premium_status', 'active');
        if (subId) {
          await AsyncStorage.setItem('routecast_subscription_id', subId);
        }
      } else {
        await AsyncStorage.removeItem('routecast_premium_status');
        await AsyncStorage.removeItem('routecast_subscription_id');
      }
      
      setIsPremium(status);
      setSubscriptionId(subId || null);
    } catch (err) {
      console.log('Error setting premium status:', err);
    }
  };

  const canAccessFeature = (featureId: string): boolean => {
    const feature = Object.values(FEATURES).find(f => f.id === featureId);
    
    if (!feature) {
      console.warn(`Unknown feature: ${featureId}`);
      return true; // Default to allowed if feature unknown
    }

    // Free features always accessible
    if (!feature.isPremium) {
      console.log(`[FREE] Accessing feature: ${feature.name}`);
      return true;
    }

    // Premium features require subscription
    if (isPremium) {
      console.log(`[PREMIUM] Accessing feature: ${feature.name}`);
      return true;
    }

    console.log(`[GATED] Premium feature blocked: ${feature.name}`);
    return false;
  };

  return {
    isPremium,
    loading,
    subscriptionId,
    canAccessFeature,
    setPremiumStatus,
    refreshStatus: loadPremiumStatus,
  };
};
