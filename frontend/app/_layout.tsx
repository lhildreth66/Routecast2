import { Stack, useRouter } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { useEffect } from 'react';
import * as Notifications from 'expo-notifications';
import { Platform } from 'react-native';
import { AuthProvider } from '../contexts/AuthContext';
import { registerDevicePushTokenOnce } from './pushRegistration';
import { addNotificationToHistory } from './notificationHistory';

// Configure notifications (NATIVE ONLY)
if (Platform.OS !== 'web') {
  Notifications.setNotificationHandler({
    handleNotification: async () => ({
      shouldShowAlert: true,
      shouldPlaySound: true,
      shouldSetBadge: false,
    }),
  });
}

async function ensureAndroidChannel() {
  if (Platform.OS !== 'android') return;

  await Notifications.setNotificationChannelAsync('default', {
    name: 'Default',
    importance: Notifications.AndroidImportance.MAX,
    sound: 'default',
    vibrationPattern: [0, 250, 250, 250],
    lightColor: '#FF231F7C',
  });

  await Notifications.setNotificationChannelAsync('route-alerts', {
    name: 'Route Alerts',
    importance: Notifications.AndroidImportance.HIGH,
    sound: 'default',
    vibrationPattern: [0, 250, 250, 250],
    lockscreenVisibility: Notifications.AndroidNotificationVisibility.PUBLIC,
  });
}

export default function RootLayout() {
  const router = useRouter();

  useEffect(() => {
    // 🚫 WEB: completely skip expo-notifications
    if (Platform.OS === 'web') {
      console.log('[push-auto] skip on web platform');
      return;
    }

    async function requestPermissions() {
      const { status } = await Notifications.requestPermissionsAsync();
      if (status !== 'granted') {
        console.log('Notification permissions not granted');
      }
    }

    void requestPermissions();
    void ensureAndroidChannel();
    void registerDevicePushTokenOnce();

    const sub = Notifications.addNotificationReceivedListener((notification) => {
      console.log(
        '[notifications] received',
        notification.request.identifier,
        notification.request.content?.title
      );
      void addNotificationToHistory(notification);
    });

    const responseSub = Notifications.addNotificationResponseReceivedListener((response) => {
      console.log(
        '[notifications] tapped',
        response.notification?.request?.identifier
      );
      void addNotificationToHistory(response.notification);
      setTimeout(() => {
        try {
          router.push('/notifications' as any);
        } catch (err) {
          console.log('[notifications] navigation failed', err);
        }
      }, 50);
    });

    // Cold-start notification tap (native only)
    void (async () => {
      const last = await Notifications.getLastNotificationResponseAsync();
      if (last) {
        void addNotificationToHistory(last.notification);
        setTimeout(() => {
          try {
            router.push('/notifications' as any);
          } catch (err) {
            console.log('[notifications] navigation failed (launch)', err);
          }
        }, 50);
      }
    })();

    return () => {
      sub.remove();
      responseSub.remove();
    };
  }, [router]);

  return (
    <AuthProvider>
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

        {/* Boondockers */}
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

        {/* Tractor Trailer */}
        <Stack.Screen name="tractor-trailer" />
        <Stack.Screen name="truck-stops" />
        <Stack.Screen name="weigh-stations" />
        <Stack.Screen name="truck-parking" />
        <Stack.Screen name="low-clearance" />
        <Stack.Screen name="truck-services" />
        <Stack.Screen name="truck-restrictions" />

        {/* Shared */}
        <Stack.Screen name="truckerAlerts" />
        <Stack.Screen name="radar-map" />
        <Stack.Screen name="weather-alerts" />
        <Stack.Screen name="user-guide" />
        <Stack.Screen name="notifications" />
      </Stack>
    </AuthProvider>
  );
}
