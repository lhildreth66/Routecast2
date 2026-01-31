import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  TextInput,
  ScrollView,
  ActivityIndicator,
} from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { API_BASE } from '../apiConfig';
import { requirePro } from '../billing/guard';
import { useEntitlementsContext } from '../billing/EntitlementsProvider';
import { Paywall } from '../billing/paywall';

interface CampPrepChatProps {
  onClose: () => void;
}

interface PremiumInfo {
  required: boolean;
  locked: boolean;
  feature?: string;
}

interface CampPrepResponse {
  mode: string;
  command: string;
  human: string;
  payload: any;
  premium: PremiumInfo;
  error?: string;
}

interface Message {
  role: 'user' | 'assistant';
  text: string;
  payload?: any;
  premium?: PremiumInfo;
  error?: string;
}

const QUICK_COMMANDS = [
  { cmd: '/prep-checklist', label: '📋 Checklist', free: true, desc: 'Basic camping prep tasks' },
  { cmd: '/power-forecast', label: '⚡ Power', free: false, desc: 'Estimate solar output at your campsite' },
  { cmd: '/propane-usage', label: '🔥 Propane', free: false, desc: 'Calculate fuel consumption' },
  { cmd: '/water-plan', label: '💧 Water', free: false, desc: 'Plan water usage and storage' },
  { cmd: '/terrain-shade', label: '🌄 Shade', free: false, desc: 'Analyze terrain shading' },
  { cmd: '/wind-shelter', label: '💨 Wind', free: false, desc: 'Assess wind protection' },
  { cmd: '/road-sim', label: '🚙 Road', free: false, desc: 'Check road passability' },
  { cmd: '/cell-starlink', label: '📡 Signal', free: false, desc: 'Predict connectivity strength' },
  { cmd: '/camp-index', label: '⭐ Index', free: false, desc: 'Score campsite quality' },
  { cmd: '/claim-log', label: '📄 Claim', free: false, desc: 'Generate insurance claim log' },
];

export default function CampPrepChat({ onClose }: CampPrepChatProps) {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: 'assistant',
      text: '🏕️ Welcome to Off-Grid!\n\nYour all-in-one campsite planning assistant. Type a command or ask questions about your camping setup, resource planning, and site conditions.',
    },
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [showPaywall, setShowPaywall] = useState(false);

  const { refresh } = useEntitlementsContext();

  const isPremiumCommand = (command: string): boolean => {
    const normalized = command.trim().split(/\s+/)[0];
    return normalized !== '/prep-checklist';
  };

  const sendCommand = async (command: string) => {
    setMessages((prev) => [...prev, { role: 'user', text: command }]);
    setInput('');
    setLoading(true);

    try {
      if (isPremiumCommand(command)) {
        const guard = await requirePro();
        if (!guard.allowed) {
          setShowPaywall(true);
          setMessages((prev) => [
            ...prev,
            {
              role: 'assistant',
              text: 'This command requires a premium subscription. Unlock to continue.',
              premium: { required: true, locked: true, feature: 'camp_prep' },
              error: 'premium_locked',
            },
          ]);
          return;
        }
      }

      const subscriptionId = await AsyncStorage.getItem('routecast_subscription_id');

      const response = await fetch(`${API_BASE}/api/chat/camp-prep`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: command,
          subscription_id: subscriptionId,
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const data: CampPrepResponse = await response.json();

      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          text: data.human,
          payload: data.payload,
          premium: data.premium,
          error: data.error,
        },
      ]);
    } catch (err: any) {
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          text: `Error: ${err.message || 'Failed to send command'}`,
          error: 'network_error',
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const renderPayload = (payload: any) => {
    if (!payload) return null;

    // Handle checklist
    if (payload.checklist) {
      return (
        <View style={styles.payloadCard}>
          {payload.checklist.map((item: string, idx: number) => (
            <Text key={idx} style={styles.checklistItem}>
              {item}
            </Text>
          ))}
        </View>
      );
    }

    // Handle numeric data
    return (
      <View style={styles.payloadCard}>
        {Object.entries(payload).map(([key, value]) => {
          if (typeof value === 'object' && !Array.isArray(value)) {
            return null; // Skip nested objects for now
          }
          if (Array.isArray(value)) {
            return null; // Skip arrays for simple rendering
          }
          return (
            <Text key={key} style={styles.payloadRow}>
              <Text style={styles.payloadKey}>{key}:</Text> {String(value)}
            </Text>
          );
        })}
      </View>
    );
  };

  return (
    <View style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <View>
          <Text style={styles.headerTitle}>🏕️ Off-Grid</Text>
          <Text style={styles.headerSubtitle}>Premium campsite planning tools</Text>
        </View>
        <TouchableOpacity onPress={onClose} style={styles.closeButton}>
          <Text style={styles.closeButtonText}>✕</Text>
        </TouchableOpacity>
      </View>

      {/* Quick Commands Info */}
      <View style={styles.commandsInfo}>
        <Text style={styles.commandsTitle}>Available Commands</Text>
        <View style={styles.commandsList}>
          <Text style={styles.commandItem}>💧 /water-plan • 🌄 /terrain-shade • 💨 /wind-shelter</Text>
          <Text style={styles.commandItem}>🚙 /road-sim • 📡 /cell-starlink • ⭐ /camp-index</Text>
        </View>
      </View>

      {/* Messages */}
      <ScrollView style={styles.messagesContainer}>
        {messages.map((msg, idx) => (
          <View
            key={idx}
            style={[
              styles.messageBubble,
              msg.role === 'user' ? styles.userBubble : styles.assistantBubble,
            ]}
          >
            <Text
              style={[
                styles.messageText,
                msg.role === 'user' && styles.userMessageText,
              ]}
            >
              {msg.text}
            </Text>

            {msg.premium?.locked && (
              <View style={styles.premiumLockBanner}>
                <Text style={styles.premiumLockText}>
                  🔒 Upgrade to premium to unlock this feature
                </Text>
              </View>
            )}

            {msg.payload && !msg.premium?.locked && renderPayload(msg.payload)}
          </View>
        ))}

        {loading && (
          <View style={styles.loadingBubble}>
            <ActivityIndicator color="#8b4513" />
          </View>
        )}
      </ScrollView>

      {/* Input */}
      <View style={styles.inputContainer}>
        <TextInput
          style={styles.input}
          value={input}
          onChangeText={setInput}
          placeholder="Type a command like /water-plan or ask a question"
          placeholderTextColor="#999"
          onSubmitEditing={() => input.trim() && sendCommand(input.trim())}
        />
        <TouchableOpacity
          style={styles.sendButton}
          onPress={() => input.trim() && sendCommand(input.trim())}
          disabled={!input.trim() || loading}
        >
          <Text style={styles.sendButtonText}>Send</Text>
        </TouchableOpacity>
      </View>

      <Paywall
        visible={showPaywall}
        onClose={() => setShowPaywall(false)}
        onPurchaseComplete={async () => {
          await refresh();
          setShowPaywall(false);
        }}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#1a1a1a',
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 16,
    paddingBottom: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#333',
  },
  headerTitle: {
    fontSize: 22,
    fontWeight: 'bold',
    color: '#fff',
  },
  headerSubtitle: {
    fontSize: 13,
    color: '#999',
    marginTop: 2,
  },
  closeButton: {
    padding: 8,
  },
  closeButtonText: {
    fontSize: 24,
    color: '#fff',
  },
  commandsInfo: {
    backgroundColor: '#2a2a2a',
    marginHorizontal: 16,
    marginTop: 12,
    marginBottom: 8,
    padding: 12,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#8b4513',
  },
  commandsTitle: {
    fontSize: 13,
    fontWeight: '700',
    color: '#d4a574',
    marginBottom: 8,
  },
  commandsList: {
    gap: 4,
  },
  commandItem: {
    fontSize: 11,
    color: '#999',
    lineHeight: 16,
  },
  messagesContainer: {
    flex: 1,
    padding: 16,
  },
  messageBubble: {
    marginBottom: 12,
    maxWidth: '85%',
  },
  userBubble: {
    alignSelf: 'flex-end',
    backgroundColor: '#8b4513',
    borderRadius: 16,
    padding: 12,
  },
  assistantBubble: {
    alignSelf: 'flex-start',
    backgroundColor: '#2a2a2a',
    borderRadius: 16,
    padding: 12,
  },
  messageText: {
    color: '#fff',
    fontSize: 14,
    lineHeight: 20,
  },
  userMessageText: {
    color: '#fff',
  },
  premiumLockBanner: {
    marginTop: 8,
    padding: 8,
    backgroundColor: '#3a2a1a',
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#8b4513',
  },
  premiumLockText: {
    color: '#d4a574',
    fontSize: 12,
    textAlign: 'center',
  },
  payloadCard: {
    marginTop: 8,
    padding: 8,
    backgroundColor: '#1a1a1a',
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#444',
  },
  checklistItem: {
    color: '#ccc',
    fontSize: 13,
    marginBottom: 4,
  },
  payloadRow: {
    color: '#ccc',
    fontSize: 12,
    marginBottom: 4,
  },
  payloadKey: {
    fontWeight: 'bold',
    color: '#8b4513',
  },
  loadingBubble: {
    alignSelf: 'flex-start',
    padding: 16,
  },
  inputContainer: {
    flexDirection: 'row',
    padding: 16,
    paddingBottom: 20,
    borderTopWidth: 1,
    borderTopColor: '#333',
    alignItems: 'center',
  },
  input: {
    flex: 1,
    backgroundColor: '#2a2a2a',
    color: '#fff',
    paddingHorizontal: 12,
    paddingVertical: 10,
    borderRadius: 20,
    marginRight: 8,
    fontSize: 13,
  },
  sendButton: {
    backgroundColor: '#8b4513',
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: 20,
  },
  sendButtonText: {
    color: '#fff',
    fontWeight: 'bold',
  },
});
