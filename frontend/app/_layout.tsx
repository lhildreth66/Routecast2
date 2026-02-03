import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { useEffect } from 'react';
import * as Notifications from 'expo-notifications';
import { Platform } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import Constants from 'expo-constants';

export default function RootLayout() {
  useEffect(() => {
    // Request notification permissions and get token
    async function setupNotifications() {
      // Skip notifications in Expo Go - not supported since SDK 53
      const isExpoGo = Constants.appOwnership === 'expo';
      if (isExpoGo) {
        console.log('Push notifications not available in Expo Go - use development build');
        return;
      }
      
      // Only configure notification handler in standalone builds
      Notifications.setNotificationHandler({
        handleNotification: async () => ({
          shouldShowAlert: true,
          shouldPlaySound: true,
          shouldSetBadge: false,
          shouldShowBanner: true,
          shouldShowList: true,
        }),
      });
      
      if (Platform.OS !== 'web') {
        try {
          // Request permissions
          const { status } = await Notifications.requestPermissionsAsync();
          if (status === 'granted') {
            // Get the Expo push token
            const token = await Notifications.getExpoPushTokenAsync();
            console.log('Expo push token:', token.data);
            
            // Save token to AsyncStorage for later use
            await AsyncStorage.setItem('expoPushToken', token.data);
          } else {
            console.log('Notification permissions not granted');
          }
        } catch (err) {
          console.log('Error setting up notifications:', err);
        }
      }
    }
    setupNotifications();
  }, []);

  return (
    <>
      <StatusBar style="light" />
      <Stack
        screenOptions={{
          headerShown: false,
          contentStyle: { backgroundColor: '#0a0a0a' },
          animation: 'slide_from_right',
        }}
      >
        <Stack.Screen name="index" />
        <Stack.Screen name="route" />
        <Stack.Screen name="road-passability" />
        <Stack.Screen name="connectivity" />
        <Stack.Screen name="campsite-index" />
        <Stack.Screen name="claim-log" />
      </Stack>
    </>
  );
}
