import React, { useState } from 'react';
import { View, Text, StyleSheet, TextInput, TouchableOpacity, ScrollView, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { buildUrl } from './apiConfig';

export default function ContactPage() {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [message, setMessage] = useState('');
  const [company, setCompany] = useState(''); // honeypot
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState('');

  const onSubmit = async () => {
    if (submitting) return;
    setSubmitting(true);
    setSuccess(false);
    setError('');
    try {
      const response = await fetch(buildUrl('contact'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, email, message, company }),
      });

      if (response.ok) {
        setSuccess(true);
        setName('');
        setEmail('');
        setMessage('');
        setCompany('');
      } else {
        const text = await response.text();
        setError(text || 'Unable to send message. Please try again.');
      }
    } catch (err) {
      setError('Unable to send message. Please check your connection.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
        <Text style={styles.title}>Contact Us</Text>
        <Text style={styles.subtitle}>Have a question? We usually reply within one business day.</Text>

        <View style={styles.form}>
          <Text style={styles.label}>Name</Text>
          <TextInput
            style={styles.input}
            value={name}
            onChangeText={setName}
            placeholder="Your name"
            placeholderTextColor="#64748b"
            editable={!submitting}
          />

          <Text style={styles.label}>Email</Text>
          <TextInput
            style={styles.input}
            value={email}
            onChangeText={setEmail}
            placeholder="you@example.com"
            placeholderTextColor="#64748b"
            autoCapitalize="none"
            keyboardType="email-address"
            editable={!submitting}
          />

          <Text style={styles.label}>Message</Text>
          <TextInput
            style={[styles.input, styles.textarea]}
            value={message}
            onChangeText={setMessage}
            placeholder="How can we help?"
            placeholderTextColor="#64748b"
            multiline
            numberOfLines={5}
            editable={!submitting}
          />

          {/* Honeypot */}
          <TextInput
            style={styles.honeypot}
            value={company}
            onChangeText={setCompany}
            placeholder="Company"
            accessible={false}
            editable={!submitting}
          />

          {error ? <Text style={styles.error}>{error}</Text> : null}
          {success ? <Text style={styles.success}>Message sent — we'll reply within 1 business day.</Text> : null}

          <TouchableOpacity style={styles.submitButton} onPress={onSubmit} disabled={submitting}>
            {submitting ? (
              <ActivityIndicator color="#0f172a" />
            ) : (
              <>
                <Ionicons name="send" size={18} color="#0f172a" />
                <Text style={styles.submitText}>Send Message</Text>
              </>
            )}
          </TouchableOpacity>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0b0b12' },
  content: { padding: 20, gap: 16 },
  title: { fontSize: 28, fontWeight: '700', color: '#f8fafc' },
  subtitle: { fontSize: 16, color: '#cbd5e1', lineHeight: 22 },
  form: { marginTop: 12, gap: 12 },
  label: { color: '#e2e8f0', fontSize: 15, fontWeight: '600' },
  input: {
    borderWidth: 1,
    borderColor: '#1f2937',
    backgroundColor: '#111827',
    color: '#e5e7eb',
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 15,
  },
  textarea: {
    minHeight: 120,
    textAlignVertical: 'top',
  },
  honeypot: {
    height: 0,
    opacity: 0,
    padding: 0,
    margin: 0,
  },
  submitButton: {
    marginTop: 4,
    backgroundColor: '#facc15',
    borderRadius: 10,
    paddingVertical: 14,
    alignItems: 'center',
    justifyContent: 'center',
    flexDirection: 'row',
    gap: 8,
  },
  submitText: { color: '#0f172a', fontWeight: '700', fontSize: 16 },
  error: { color: '#f87171', fontSize: 14 },
  success: { color: '#34d399', fontSize: 14 },
});
