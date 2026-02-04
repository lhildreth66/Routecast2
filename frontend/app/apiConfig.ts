import Constants from 'expo-constants';

export const API_BASE = 
  Constants.expoConfig?.extra?.API_BASE || 
  process.env.EXPO_PUBLIC_BACKEND_URL || 
  'https://routecast-backend.onrender.com';

// Log once at module load to confirm which backend the app will use.
(() => {
  console.log('[Routecast] Backend base URL:', API_BASE || '(not set)');
})();
