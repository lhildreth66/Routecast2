import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { useEffect } from 'react';
import * as Notifications from 'expo-notifications';
import { Platform } from 'react-native';

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
    // Request notification permissions
    async function requestPermissions() {
      if (Platform.OS !== 'web') {
        const { status } = await Notifications.requestPermissionsAsync();
        if (status !== 'granted') {
          console.log('Notification permissions not granted');
        }
      }
    }
    requestPermissions();
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
        {/* Boondockers Screens */}
        <Stack.Screen name="boondockers" />
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
        {/* Tractor Trailer Screens */}
        <Stack.Screen name="tractor-trailer" />
        <Stack.Screen name="truck-stops" />
        <Stack.Screen name="weigh-stations" />
        <Stack.Screen name="truck-parking" />
        <Stack.Screen name="low-clearance" />
        <Stack.Screen name="truck-services" />
        <Stack.Screen name="truck-restrictions" />
        {/* Shared/Supporting Screens */}
        <Stack.Screen name="truckerAlerts" />
        <Stack.Screen name="radar-map" />
        <Stack.Screen name="weather-alerts" />
        <Stack.Screen name="user-guide" />
      </Stack>
    </>
  );
}
