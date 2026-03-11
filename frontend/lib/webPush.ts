import AsyncStorage from '@react-native-async-storage/async-storage';
import Constants from 'expo-constants';

const logPrefix = '[web-push]';

const urlBase64ToUint8Array = (base64String: string): Uint8Array => {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
  const rawData = atob(base64);
  const outputArray = new Uint8Array(rawData.length);
  for (let i = 0; i < rawData.length; ++i) {
    outputArray[i] = rawData.charCodeAt(i);
  }
  return outputArray;
};

export type WebPushRegisterResult = {
  supported: boolean;
  permission: NotificationPermission;
  subscription?: PushSubscription | null;
  saved?: boolean;
  responseStatus?: number;
  responseBody?: any;
};

async function postSubscription(
  backendUrl: string,
  authToken: string | null | undefined,
  subscription: PushSubscription,
) {
  const json = subscription.toJSON();
  const body = {
    ...json,
    platform: 'web',
    user_agent: navigator.userAgent,
  };

  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (authToken) {
    headers['Authorization'] = `Bearer ${authToken}`;
  }

  const resp = await fetch(`${backendUrl.replace(/\/$/, '')}/push/web-subscription`, {
    method: 'POST',
    headers,
    credentials: 'include',
    body: JSON.stringify(body),
  });

  let responseBody: any;
  try {
    responseBody = await resp.json();
  } catch {
    responseBody = await resp.text();
  }

  console.log(`${logPrefix} post subscription status=${resp.status}`, responseBody);

  return { ok: resp.ok, status: resp.status, body: responseBody };
}

export async function registerWebPush(
  backendUrl: string,
  authToken?: string | null,
): Promise<WebPushRegisterResult> {
  console.log(`${logPrefix} start backend=${backendUrl}`);

  if (typeof window === 'undefined' || typeof navigator === 'undefined') {
    console.log(`${logPrefix} not in browser`);
    return { supported: false, permission: 'default' } as const;
  }

  if (!('Notification' in window) || !navigator.serviceWorker || !('PushManager' in window)) {
    console.warn(`${logPrefix} unsupported environment`);
    return { supported: false, permission: 'default' } as const;
  }

  const vapid = process.env.EXPO_PUBLIC_VAPID_PUBLIC_KEY || (Constants?.expoConfig as any)?.extra?.vapidPublicKey;
  if (!vapid) {
    console.error(`${logPrefix} missing VAPID public key (EXPO_PUBLIC_VAPID_PUBLIC_KEY)`);
    return { supported: false, permission: Notification.permission } as const;
  }

  let registration: ServiceWorkerRegistration;
  try {
    registration = await navigator.serviceWorker.register('/push-sw.js');
    console.log(`${logPrefix} service worker registered scope=${registration.scope}`);
  } catch (err) {
    console.error(`${logPrefix} service worker registration failed`, err);
    return { supported: true, permission: Notification.permission } as const;
  }

  const permission = await Notification.requestPermission();
  console.log(`${logPrefix} permission result=${permission}`);
  if (permission !== 'granted') {
    return { supported: true, permission };
  }

  let existing = await registration.pushManager.getSubscription();
  console.log(`${logPrefix} existing subscription`, existing ? 'present' : 'none');

  let subscription = existing;
  if (!subscription) {
    try {
      subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(vapid),
      });
      console.log(`${logPrefix} new subscription created endpoint=${subscription.endpoint}`);
    } catch (err) {
      console.error(`${logPrefix} subscribe failed`, err);
      return { supported: true, permission, subscription: null };
    }
  }

  let responseStatus: number | undefined;
  let responseBody: any;
  try {
    const resp = await postSubscription(backendUrl, authToken, subscription);
    responseStatus = resp.status;
    responseBody = resp.body;
    console.log(`${logPrefix} save response status=${resp.status}`, responseBody);
    return {
      supported: true,
      permission,
      subscription,
      saved: resp.ok,
      responseStatus,
      responseBody,
    };
  } catch (err) {
    console.error(`${logPrefix} save error`, err);
    return { supported: true, permission, subscription, saved: false };
  }
}

export async function deleteWebPushSubscription(
  backendUrl: string,
  authToken?: string | null,
): Promise<boolean> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (authToken) headers['Authorization'] = `Bearer ${authToken}`;
  try {
    const resp = await fetch(`${backendUrl.replace(/\/$/, '')}/push/web-subscription`, {
      method: 'DELETE',
      headers,
      credentials: 'include',
    });
    console.log(`${logPrefix} delete response status=${resp.status}`);
    return resp.ok;
  } catch (err) {
    console.error(`${logPrefix} delete error`, err);
    return false;
  }
}
