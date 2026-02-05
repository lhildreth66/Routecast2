import { useEffect, useRef, useState } from 'react';
import { AppState, AppStateStatus } from 'react-native';
import * as Notifications from 'expo-notifications';
import {
  registerForPushNotificationsAsync,
  sendPushTokenToBackend,
  addNotificationReceivedListener,
  addNotificationResponseReceivedListener,
  removeNotificationSubscription,
} from '../services/notifications';
import { API_BASE } from '../apiConfig';

interface UseNotificationsReturn {
  expoPushToken: string | null;
  notification: Notifications.Notification | null;
  isRegistered: boolean;
  error: string | null;
  registerForNotifications: () => Promise<void>;
}

/**
 * Hook for managing push notifications
 * 
 * Usage:
 * ```tsx
 * const { expoPushToken, notification, isRegistered, registerForNotifications } = useNotifications();
 * 
 * useEffect(() => {
 *   if (notification) {
 *     // Handle incoming notification
 *     console.log('Received:', notification.request.content.body);
 *   }
 * }, [notification]);
 * ```
 */
export function useNotifications(): UseNotificationsReturn {
  const [expoPushToken, setExpoPushToken] = useState<string | null>(null);
  const [notification, setNotification] = useState<Notifications.Notification | null>(null);
  const [isRegistered, setIsRegistered] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const notificationListener = useRef<Notifications.Subscription>();
  const responseListener = useRef<Notifications.Subscription>();
  const appState = useRef(AppState.currentState);

  const registerForNotifications = async () => {
    try {
      setError(null);
      const token = await registerForPushNotificationsAsync();
      
      if (token) {
        setExpoPushToken(token);
        setIsRegistered(true);
        
        // Send token to backend if API_BASE is configured
        if (API_BASE) {
          await sendPushTokenToBackend(token, API_BASE);
        }
      } else {
        setError('Could not get push notification token');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    }
  };

  useEffect(() => {
    // Register for notifications on mount
    registerForNotifications();

    // Set up notification listeners
    notificationListener.current = addNotificationReceivedListener((notif) => {
      setNotification(notif);
    });

    responseListener.current = addNotificationResponseReceivedListener((response) => {
      // Handle notification tap - navigate to relevant screen
      const data = response.notification.request.content.data;
      console.log('Notification tapped:', data);
      
      // You can add navigation logic here based on data.screen or data.route
    });

    // Handle app state changes to refresh token when app comes to foreground
    const handleAppStateChange = (nextAppState: AppStateStatus) => {
      if (
        appState.current.match(/inactive|background/) &&
        nextAppState === 'active'
      ) {
        // App has come to the foreground - refresh registration if needed
        if (!isRegistered) {
          registerForNotifications();
        }
      }
      appState.current = nextAppState;
    };

    const subscription = AppState.addEventListener('change', handleAppStateChange);

    // Cleanup
    return () => {
      if (notificationListener.current) {
        removeNotificationSubscription(notificationListener.current);
      }
      if (responseListener.current) {
        removeNotificationSubscription(responseListener.current);
      }
      subscription.remove();
    };
  }, []);

  return {
    expoPushToken,
    notification,
    isRegistered,
    error,
    registerForNotifications,
  };
}
