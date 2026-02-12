import React, { useCallback, useState } from 'react';
import { View, Text, FlatList, StyleSheet, TouchableOpacity, RefreshControl } from 'react-native';
import { useFocusEffect, router } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import {
  loadNotificationHistory,
  markNotificationHistoryViewed,
  NotificationEntry,
  saveNotificationHistory,
} from './notificationHistory';

function formatTime(ts: number): string {
  const d = new Date(ts);
  return d.toLocaleString();
}

export default function NotificationHistoryScreen() {
  const [items, setItems] = useState<NotificationEntry[]>([]);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    setRefreshing(true);
    const history = await loadNotificationHistory();
    setItems(history);
    await markNotificationHistoryViewed(history[0]?.timestamp);
    setRefreshing(false);
  }, []);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load]),
  );

  const onClear = useCallback(async () => {
    await saveNotificationHistory([]);
    setItems([]);
    await markNotificationHistoryViewed();
  }, []);

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton} accessibilityRole="button" accessibilityLabel="Go back">
          <Ionicons name="arrow-back" size={22} color="#fff" />
        </TouchableOpacity>
        <Text style={styles.title}>Notifications</Text>
        <TouchableOpacity onPress={onClear} style={styles.clearButton} accessibilityRole="button" accessibilityLabel="Clear notifications">
          <Ionicons name="trash-outline" size={20} color="#ccc" />
        </TouchableOpacity>
      </View>
      <FlatList
        data={items}
        keyExtractor={(item) => item.id}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={load} tintColor="#fff" />}
        contentContainerStyle={items.length === 0 ? styles.emptyContainer : undefined}
        ListEmptyComponent={<Text style={styles.emptyText}>No notifications yet.</Text>}
        renderItem={({ item }) => (
          <TouchableOpacity
            style={styles.card}
            activeOpacity={0.8}
            onPress={async () => {
              await markNotificationHistoryViewed(item.timestamp);
              setRefreshing(true);
              const history = await loadNotificationHistory();
              setItems(history);
              setRefreshing(false);
            }}
          >
            <View style={styles.row}>
              <Text style={styles.cardTitle}>{item.title || 'Alert'}</Text>
              <Text style={styles.timestamp}>{formatTime(item.timestamp)}</Text>
            </View>
            {item.body ? <Text style={styles.body}>{item.body}</Text> : null}
            {item.routeId ? <Text style={styles.route}>Route: {item.routeId}</Text> : null}
          </TouchableOpacity>
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0a0a0a', paddingHorizontal: 16, paddingTop: 48 },
  header: { flexDirection: 'row', alignItems: 'center', marginBottom: 16 },
  backButton: { padding: 8, marginRight: 8 },
  title: { color: '#fff', fontSize: 20, fontWeight: '700', flex: 1 },
  clearButton: { padding: 8 },
  card: { backgroundColor: '#111', borderRadius: 12, padding: 12, marginBottom: 12, borderWidth: 1, borderColor: '#1f1f1f' },
  row: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 },
  cardTitle: { color: '#fff', fontSize: 16, fontWeight: '600' },
  timestamp: { color: '#bbb', fontSize: 12, marginLeft: 8 },
  body: { color: '#ddd', fontSize: 14, marginBottom: 4 },
  route: { color: '#aaa', fontSize: 12 },
  emptyContainer: { flexGrow: 1, alignItems: 'center', justifyContent: 'center' },
  emptyText: { color: '#888', fontSize: 14 },
});
