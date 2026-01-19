/**
 * Hook for smart departure & hazard alerts (Task E1 - Pro)
 *
 * Handles:
 * - Requesting notification permissions
 * - Getting Expo push token
 * - Registering push token with backend
 * - Registering planned trips
 */

import { useState, useCallback, useEffect } from 'react';
import * as Notifications from 'expo-notifications';
import AsyncStorage from '@react-native-async-storage/async-storage';
import axios from 'axios';

const API_URL = process.env.EXPO_PUBLIC_BACKEND_URL || 'http://localhost:8000/api';

interface RouteWaypoint {
  latitude: number;
  longitude: number;
  name?: string;
}

interface PlannedTrip {
  route_waypoints: RouteWaypoint[];
  planned_departure_local: string; // ISO datetime string
  user_timezone: string;
  destination_name?: string;
}

interface UseSmartDelayReturn {
  // Permissions
  requestPermissions: () => Promise<boolean>;
  permissionsGranted: boolean;
  permissionError: string | null;

  // Push token
  pushToken: string | null;
  getPushToken: () => Promise<string | null>;
  registerToken: (subscriptionId: string) => Promise<boolean>;
  tokenError: string | null;

  // Planned trips
  registerPlannedTrip: (
    trip: PlannedTrip,
    subscriptionId: string
  ) => Promise<string | null>;
  registrationLoading: boolean;
  registrationError: string | null;
}

/**
 * Hook for managing smart delay notifications
 */
export const useSmartDelay = (): UseSmartDelayReturn => {
  const [permissionsGranted, setPermissionsGranted] = useState(false);
  const [permissionError, setPermissionError] = useState<string | null>(null);
  const [pushToken, setPushToken] = useState<string | null>(null);
  const [tokenError, setTokenError] = useState<string | null>(null);
  const [registrationLoading, setRegistrationLoading] = useState(false);
  const [registrationError, setRegistrationError] = useState<string | null>(null);

  // Request notification permissions
  const requestPermissions = useCallback(async (): Promise<boolean> => {
    try {
      setPermissionError(null);

      const { status } = await Notifications.requestPermissionsAsync();
      const granted = status === 'granted';
      setPermissionsGranted(granted);

      if (granted) {
        // Get and store push token
        const token = await getPushToken();
        return !!token;
      }

      return false;
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      setPermissionError(message);
      return false;
    }
  }, []);

  // Get Expo push token
  const getPushToken = useCallback(async (): Promise<string | null> => {
    try {
      setTokenError(null);

      const projectId = process.env.EXPO_PUBLIC_EAS_PROJECT_ID;
      if (!projectId) {
        throw new Error('EXPO_PUBLIC_EAS_PROJECT_ID not configured');
      }

      const token = (
        await Notifications.getExpoPushTokenAsync({
          projectId,
        })
      ).data;

      // Cache token
      await AsyncStorage.setItem('expo_push_token', token);
      setPushToken(token);

      return token;
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      setTokenError(message);
      return null;
    }
  }, []);

  // Register push token with backend
  const registerToken = useCallback(
    async (subscriptionId: string): Promise<boolean> => {
      try {
        setTokenError(null);

        let token = pushToken;
        if (!token) {
          token = await getPushToken();
        }

        if (!token) {
          throw new Error('Failed to get push token');
        }

        const response = await axios.post(`${API_URL}/push/register`, {
          token,
          subscription_id: subscriptionId,
        });

        return response.data.success === true;
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Unknown error';
        setTokenError(message);
        return false;
      }
    },
    [pushToken]
  );

  // Register planned trip
  const registerPlannedTrip = useCallback(
    async (trip: PlannedTrip, subscriptionId: string): Promise<string | null> => {
      try {
        setRegistrationLoading(true);
        setRegistrationError(null);

        const response = await axios.post(`${API_URL}/trips/planned`, {
          ...trip,
          subscription_id: subscriptionId,
        });

        if (response.data.trip_id) {
          return response.data.trip_id;
        }

        throw new Error('No trip_id in response');
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Unknown error';
        setRegistrationError(message);
        return null;
      } finally {
        setRegistrationLoading(false);
      }
    },
    []
  );

  // Load cached push token on mount
  useEffect(() => {
    const loadCachedToken = async () => {
      try {
        const cached = await AsyncStorage.getItem('expo_push_token');
        if (cached) {
          setPushToken(cached);
        }
      } catch (error) {
        console.warn('Failed to load cached push token:', error);
      }
    };

    loadCachedToken();
  }, []);

  return {
    requestPermissions,
    permissionsGranted,
    permissionError,
    pushToken,
    getPushToken,
    registerToken,
    tokenError,
    registerPlannedTrip,
    registrationLoading,
    registrationError,
  };
};

/**
 * Set up notification handler (call once in app root)
 */
export const setupNotificationHandler = () => {
  // Set notification handler
  Notifications.setNotificationHandler({
    handleNotification: async (notification) => {
      // Allow notification to show in foreground
      return {
        shouldShowAlert: true,
        shouldPlaySound: true,
        shouldSetBadge: true,
      };
    },
  });

  // Listen for received notifications
  const subscription = Notifications.addNotificationReceivedListener((notification) => {
    console.log('[SmartDelay] Notification received:', notification.request.content.body);
  });

  // Listen for notification responses (when user taps)
  const responseSubscription = Notifications.addNotificationResponseReceivedListener(
    (response) => {
      const data = response.notification.request.content.data;
      console.log('[SmartDelay] Notification tapped with data:', data);

      // Handle smart delay navigation
      if (data.type === 'smart_delay' && data.tripId) {
        console.log(`Navigate to trip ${data.tripId}`);
        // TODO: Navigate to trip details or settings screen
      }
    }
  );

  return () => {
    subscription.remove();
    responseSubscription.remove();
  };
};
