import AsyncStorage from '@react-native-async-storage/async-storage';
import Constants from 'expo-constants';
import * as Device from 'expo-device';
import * as Notifications from 'expo-notifications';
import axios from 'axios';
import { Platform } from 'react-native';
import { API_BASE } from './apiConfig';

let inFlight: Promise<void> | null = null;

const log = (message: string, extra?: Record<string, any>) => {
  if (extra) {
    console.log(`[push-auto] ${message}`, extra);
  } else {
    console.log(`[push-auto] ${message}`);
  }
};

const getProjectId = (): string | null => {
  const envProjectId = process.env.EXPO_PUBLIC_EAS_PROJECT_ID;
  const configProjectId = Constants?.expoConfig?.extra?.eas?.projectId;
  return envProjectId || configProjectId || null;
};

const shouldSkip = () => {
  if (Platform.OS === 'web') {
    log('skip on web platform');
    return true;
  }
  if (!Device.isDevice) {
    log('skip on emulator/simulator - push not supported');
    return true;
  }
  return false;
};

const ensureAndroidChannel = async () => {
  if (Platform.OS !== 'android') return;
  try {
    await Notifications.setNotificationChannelAsync('default', {
      name: 'default',
      importance: Notifications.AndroidImportance.MAX,
    });
  } catch (err) {
    log('failed to set android channel', { error: String(err) });
  }
};

const doRegister = async () => {
  if (shouldSkip()) return;

  try {
    const { status: existingStatus } = await Notifications.getPermissionsAsync();
    let finalStatus = existingStatus;

    if (existingStatus !== 'granted') {
      const permissionResponse = await Notifications.requestPermissionsAsync();
      finalStatus = permissionResponse.status;
    }

    log('permission status', { status: finalStatus });
    if (finalStatus !== 'granted') return;

    const projectId = getProjectId();
    if (!projectId) {
      log('missing EAS projectId - set EXPO_PUBLIC_EAS_PROJECT_ID');
      return;
    }

    const tokenResponse = await Notifications.getExpoPushTokenAsync({ projectId });
    const token = tokenResponse?.data;
    if (!token) {
      log('no push token returned');
      return;
    }

    await ensureAndroidChannel();
    await AsyncStorage.setItem('expoPushToken', token);

    const url = `${API_BASE}/api/notifications/register`;
    log('registering token with backend', { url });
    await axios.post(url, {
      expoPushToken: token,
    });

    log('token registered successfully');
  } catch (err) {
    log('error during auto registration', { error: String(err) });
  }
};

export const registerDevicePushTokenOnce = async () => {
  if (inFlight) return inFlight;
  inFlight = doRegister().finally(() => {
    inFlight = null;
  });
  return inFlight;
};
