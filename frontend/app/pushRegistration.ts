import AsyncStorage from '@react-native-async-storage/async-storage';
import Constants from 'expo-constants';
import * as Device from 'expo-device';
import * as Notifications from 'expo-notifications';
import axios from 'axios';
import { Platform } from 'react-native';
import { API_BASE, buildUrl } from './apiConfig';

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
  log('doRegister called', { platform: Platform.OS, isDevice: Device.isDevice });
  if (shouldSkip()) return;

  try {
    const { status: existingStatus } = await Notifications.getPermissionsAsync();
    log('Requesting push permission', { existingStatus });
    let finalStatus = existingStatus;

    if (existingStatus !== 'granted') {
      const permissionResponse = await Notifications.requestPermissionsAsync();
      finalStatus = permissionResponse.status;
    }

    if (finalStatus === 'granted') {
      log('Permission granted');
    } else {
      log('Permission denied', { status: finalStatus });
    }
    if (finalStatus !== 'granted') return;

    const projectId = getProjectId();
    if (!projectId) {
      log('missing EAS projectId - set EXPO_PUBLIC_EAS_PROJECT_ID');
      return;
    }
    log('Using projectId', { projectId });

    const tokenResponse = await Notifications.getExpoPushTokenAsync({ projectId });
    const token = tokenResponse?.data;
    if (!token) {
      log('no push token returned');
      return;
    }
    log('Expo token retrieved', { token });

    await ensureAndroidChannel();
    await AsyncStorage.setItem('expoPushToken', token);

    const url = buildUrl('notifications/register');
    log('Sending token to backend', { url });
    const response = await axios.post(url, {
      expoPushToken: token,
    });
    log('Register success', { status: response.status, data: response.data });
  } catch (err: any) {
    log('Register failure', { error: String(err), status: err?.response?.status, data: err?.response?.data });
  }
};

export const registerDevicePushTokenOnce = async () => {
  if (inFlight) return inFlight;
  inFlight = doRegister().finally(() => {
    inFlight = null;
  });
  return inFlight;
};
