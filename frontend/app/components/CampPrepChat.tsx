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
  { cmd: '/prep-checklist', label: '📋 Checklist', free: true },
  { cmd: '/power-forecast', label: '⚡ Power', free: false },
  { cmd: '/propane-usage', label: '🔥 Propane', free: false },
  { cmd: '/water-plan', label: '💧 Water', free: false },
  { cmd: '/terrain-shade', label: '🌄 Shade', free: false },
  { cmd: '/wind-shelter', label: '💨 Wind', free: false },
  { cmd: '/road-sim', label: '🚙 Road', free: false },
  { cmd: '/cell-starlink', label: '📡 Signal', free: false },
  { cmd: '/camp-index', label: '⭐ Index', free: false },
  { cmd: '/claim-log', label: '📄 Claim', free: false },
];

export default function CampPrepChat({ onClose }: CampPrepChatProps) {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: 'assistant',
      text: 'Welcome to Camp Prep! Use the buttons below or type commands like /power-forecast lat=34.05 lon=-111.03 panelWatts=400',
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
              text: 'This command requires Boondocking Pro. Unlock to continue.',
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
        <Text style={styles.headerTitle}>🏕️ Camp Prep</Text>
        <TouchableOpacity onPress={onClose} style={styles.closeButton}>
          <Text style={styles.closeButtonText}>✕</Text>
        </TouchableOpacity>
      </View>

      {/* Quick Commands */}
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.quickCommands}>
        {QUICK_COMMANDS.map((item) => (
          <TouchableOpacity
            key={item.cmd}
            style={[styles.quickButton, !item.free && styles.quickButtonPremium]}
            onPress={() => sendCommand(item.cmd)}
          >
            <Text style={styles.quickButtonText}>{item.label}</Text>
            {!item.free && <Text style={styles.premiumBadge}>PRO</Text>}
          </TouchableOpacity>
        ))}
      </ScrollView>

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
                  🔒 Upgrade to Boondocking Pro to unlock this feature
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
          placeholder="Type a command like /power-forecast lat=34.05..."
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
    borderBottomWidth: 1,
    borderBottomColor: '#333',
  },
  headerTitle: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#fff',
  },
  closeButton: {
    padding: 8,
  },
  closeButtonText: {
    fontSize: 24,
    color: '#fff',
  },
  quickCommands: {
    maxHeight: 60,
    borderBottomWidth: 1,
    borderBottomColor: '#333',
    paddingVertical: 8,
    paddingHorizontal: 8,
  },
  quickButton: {
    backgroundColor: '#2a2a2a',
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 16,
    marginHorizontal: 4,
    flexDirection: 'row',
    alignItems: 'center',
  },
  quickButtonPremium: {
    borderWidth: 1,
    borderColor: '#8b4513',
  },
  quickButtonText: {
    color: '#fff',
    fontSize: 12,
    marginRight: 4,
  },
  premiumBadge: {
    fontSize: 8,
    color: '#8b4513',
    fontWeight: 'bold',
  },
  messagesContainer: {
    flex: 1,
    padding: 16,
  },
  messageBubble: {
    marginBottom: 12,
    maxWidth: '80%',
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
    fontSize: 14,
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
