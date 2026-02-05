import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { useEffect } from 'react';
import * as Notifications from 'expo-notifications';
import { Platform } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';

// Configure notifications
Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
    shouldSetBadge: false,
    shouldShowBanner: true,
    shouldShowList: true,
  }),
});

export default function RootLayout() {
  useEffect(() => {
    // Request notification permissions and get token
    async function setupNotifications() {
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
        
        {/* Hub Screens */}
        <Stack.Screen name="boondockers" />
        <Stack.Screen name="tractor-trailer" />
        <Stack.Screen name="user-guide" />
        <Stack.Screen name="radar-map" />
        
        {/* Boondockers Sub-Features */}
        <Stack.Screen name="camp-prep-checklist" />
        <Stack.Screen name="free-camping" />
        <Stack.Screen name="dump-station" />
        <Stack.Screen name="last-chance" />
        <Stack.Screen name="rv-dealership" />
        <Stack.Screen name="solar-forecast" />
        <Stack.Screen name="propane-usage" />
        <Stack.Screen name="water-budget" />
        <Stack.Screen name="wind-shelter" />
        <Stack.Screen name="connectivity" />
        <Stack.Screen name="campsite-index" />
        
        {/* Tractor Trailer Sub-Features */}
        <Stack.Screen name="truck-stops" />
        <Stack.Screen name="weigh-stations" />
        <Stack.Screen name="truck-parking" />
        <Stack.Screen name="low-clearance" />
        <Stack.Screen name="truck-services" />
        <Stack.Screen name="truck-restrictions" />
        
        {/* Other Screens */}
        <Stack.Screen name="road-passability" />
        <Stack.Screen name="claim-log" />
      </Stack>
    </>
  );
}
