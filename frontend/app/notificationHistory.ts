import AsyncStorage from '@react-native-async-storage/async-storage';
import * as Notifications from 'expo-notifications';

export type NotificationEntry = {
  id: string;
  title: string;
  body: string;
  routeId?: string;
  timestamp: number;
};

const HISTORY_KEY = 'notificationHistory';
const LAST_VIEWED_KEY = 'notificationHistoryLastViewed';

export async function loadNotificationHistory(): Promise<NotificationEntry[]> {
  try {
    const raw = await AsyncStorage.getItem(HISTORY_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed as NotificationEntry[];
  } catch {
    return [];
  }
}

export async function saveNotificationHistory(entries: NotificationEntry[]): Promise<void> {
  try {
    await AsyncStorage.setItem(HISTORY_KEY, JSON.stringify(entries));
  } catch {
    // ignore
  }
}

export async function addNotificationToHistory(notification: Notifications.Notification): Promise<void> {
  const content = notification.request.content;
  const entry: NotificationEntry = {
    id: notification.request.identifier || `${Date.now()}`,
    title: content.title || 'Notification',
    body: content.body || '',
    routeId: (content.data && (content.data as Record<string, unknown>).routeId as string) || undefined,
    timestamp: Date.now(),
  };

  const existing = await loadNotificationHistory();
  const updated = [entry, ...existing].slice(0, 200);
  await saveNotificationHistory(updated);
}

export async function markNotificationHistoryViewed(timestamp?: number): Promise<void> {
  try {
    await AsyncStorage.setItem(LAST_VIEWED_KEY, String(timestamp ?? Date.now()));
  } catch {
    // ignore
  }
}

export async function getNotificationCounts(): Promise<{ total: number; unseen: number }> {
  try {
    const [history, lastViewedRaw] = await Promise.all([
      loadNotificationHistory(),
      AsyncStorage.getItem(LAST_VIEWED_KEY),
    ]);

    const lastViewed = lastViewedRaw ? parseInt(lastViewedRaw, 10) || 0 : 0;
    const unseen = history.filter((entry) => entry.timestamp > lastViewed).length;
    return { total: history.length, unseen };
  } catch {
    return { total: 0, unseen: 0 };
  }
}
