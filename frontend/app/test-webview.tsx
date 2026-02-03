import React from 'react';
import { View, Text, StyleSheet, SafeAreaView } from 'react-native';
import { WebView } from 'react-native-webview';

export default function TestWebView() {
  const html = `
    <!DOCTYPE html>
    <html>
    <head>
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <style>
        body { 
          background: #1a1a1a; 
          color: #fff; 
          font-family: sans-serif;
          padding: 20px;
        }
      </style>
    </head>
    <body>
      <h1>WebView Test</h1>
      <p>If you can see this, WebView is working!</p>
      <script>
        window.ReactNativeWebView?.postMessage('WebView loaded successfully');
      </script>
    </body>
    </html>
  `;

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>WebView Test</Text>
      </View>
      <WebView
        source={{ html }}
        style={styles.webview}
        javaScriptEnabled={true}
        onMessage={(event) => {
          console.log('Message from WebView:', event.nativeEvent.data);
        }}
        onError={(syntheticEvent) => {
          console.error('WebView Error:', syntheticEvent.nativeEvent);
        }}
        onLoadEnd={() => {
          console.log('WebView loaded');
        }}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#18181b',
  },
  header: {
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#27272a',
  },
  title: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#fff',
  },
  webview: {
    flex: 1,
  },
});
