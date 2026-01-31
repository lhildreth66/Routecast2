import React, { useState } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, ScrollView, TextInput } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';

export default function CampPrepChecklistScreen() {
  const router = useRouter();

  const [checklist, setChecklist] = useState([
    { id: 1, text: 'Fresh water tank filled', checked: false },
    { id: 2, text: 'Propane tanks full', checked: false },
    { id: 3, text: 'Batteries charged', checked: false },
    { id: 4, text: 'Grey/black tanks empty', checked: false },
    { id: 5, text: 'Tire pressure checked', checked: false },
    { id: 6, text: 'Hitch and connections secure', checked: false },
    { id: 7, text: 'Food and supplies stocked', checked: false },
    { id: 8, text: 'First aid kit packed', checked: false },
    { id: 9, text: 'Maps and GPS updated', checked: false },
    { id: 10, text: 'Emergency contact list ready', checked: false },
  ]);

  const [newItemText, setNewItemText] = useState('');

  const toggleItem = (id: number) => {
    setChecklist(prev => prev.map(item => item.id === id ? { ...item, checked: !item.checked } : item));
  };

  const addItem = () => {
    if (!newItemText.trim()) return;
    const maxId = Math.max(...checklist.map(i => i.id), 0);
    setChecklist(prev => [...prev, { id: maxId + 1, text: newItemText, checked: false }]);
    setNewItemText('');
  };

  const deleteItem = (id: number) => {
    setChecklist(prev => prev.filter(item => item.id !== id));
  };

  const progress = checklist.length > 0 ? (checklist.filter(i => i.checked).length / checklist.length * 100) : 0;

  return (
    <SafeAreaView style={styles.container}>
      <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
        <Ionicons name="arrow-back" size={24} color="#fff" />
        <Text style={styles.backText}>Back</Text>
      </TouchableOpacity>

      <ScrollView style={styles.content}>
        <View style={styles.card}>
          <Text style={styles.title}>Camp Prep Checklist</Text>
          <Text style={styles.subtitle}>Stay organized for your next adventure</Text>

          <View style={styles.progressBar}>
            <View style={[styles.progressFill, { width: `${progress}%` }]} />
          </View>
          <Text style={styles.progressText}>{Math.round(progress)}% Complete</Text>

          <View style={styles.addRow}>
            <TextInput
              value={newItemText}
              onChangeText={setNewItemText}
              placeholder="Add new item..."
              placeholderTextColor="#9ca3af"
              style={styles.addInput}
              onSubmitEditing={addItem}
            />
            <TouchableOpacity onPress={addItem} style={styles.addButton}>
              <Ionicons name="add" size={24} color="#1a1a1a" />
            </TouchableOpacity>
          </View>

          {checklist.map(item => (
            <View key={item.id} style={styles.checklistItem}>
              <TouchableOpacity onPress={() => toggleItem(item.id)} style={styles.checkRow}>
                <Ionicons
                  name={item.checked ? 'checkbox' : 'square-outline'}
                  size={24}
                  color={item.checked ? '#10b981' : '#d4d4d8'}
                />
                <Text style={[styles.itemText, item.checked && styles.itemTextChecked]}>{item.text}</Text>
              </TouchableOpacity>
              <TouchableOpacity onPress={() => deleteItem(item.id)}>
                <Ionicons name="trash-outline" size={20} color="#ef4444" />
              </TouchableOpacity>
            </View>
          ))}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0a0a0a' },
  backButton: { flexDirection: 'row', alignItems: 'center', padding: 16, gap: 8 },
  backText: { color: '#fff', fontSize: 16, fontWeight: '600' },
  content: { flex: 1 },
  card: { backgroundColor: '#18181b', borderRadius: 12, padding: 16, margin: 16, gap: 12 },
  title: { color: '#fff', fontSize: 20, fontWeight: '800' },
  subtitle: { color: '#d4d4d8', fontSize: 14 },
  progressBar: { height: 8, backgroundColor: '#27272a', borderRadius: 4, overflow: 'hidden' },
  progressFill: { height: '100%', backgroundColor: '#10b981' },
  progressText: { color: '#d4d4d8', fontSize: 12, textAlign: 'center' },
  addRow: { flexDirection: 'row', gap: 8 },
  addInput: { flex: 1, backgroundColor: '#111827', color: '#fff', borderRadius: 8, paddingHorizontal: 12, paddingVertical: 10 },
  addButton: { backgroundColor: '#eab308', width: 44, height: 44, borderRadius: 8, alignItems: 'center', justifyContent: 'center' },
  checklistItem: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingVertical: 8 },
  checkRow: { flexDirection: 'row', alignItems: 'center', gap: 12, flex: 1 },
  itemText: { color: '#e5e7eb', fontSize: 14, flex: 1 },
  itemTextChecked: { textDecorationLine: 'line-through', color: '#9ca3af' },
});
