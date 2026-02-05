import Constants from 'expo-constants';

// Determine API base URL with strict validation
// Priority: 1) EAS build env, 2) app.json extra, 3) ERROR in production
const getApiBase = (): string => {
  // First: Check EAS environment variable (set in eas.json production profile)
  const easEnvUrl = process.env.EXPO_PUBLIC_BACKEND_URL;
  
  // Second: Check app.json extra config
  const appJsonUrl = Constants.expoConfig?.extra?.API_BASE;
  
  // Determine which to use
  const apiBase = easEnvUrl || appJsonUrl;
  
  // In production builds, REQUIRE a valid backend URL
  // Do NOT silently fall back to prevent shipping wrong backend
  if (!apiBase) {
    const errorMsg = '❌ CRITICAL: No backend URL configured! Set EXPO_PUBLIC_BACKEND_URL in eas.json';
    console.error('[apiConfig]', errorMsg);
    
    // In production, this should never happen if eas.json is correct
    // For dev/testing, you can temporarily use a fallback, but we force awareness:
    if (__DEV__) {
      console.warn('[apiConfig] DEV MODE: Using localhost fallback');
      return 'http://localhost:8000';
    }
    
    throw new Error(errorMsg);
  }
  
  return apiBase;
};

export const API_BASE = getApiBase();

// Log once at module load to confirm which backend the app will use
console.log('[apiConfig] Backend URL:', API_BASE);
console.log('[apiConfig] Source:', process.env.EXPO_PUBLIC_BACKEND_URL ? 'EAS env' : 'app.json');
