import Constants from 'expo-constants';

const DEFAULT_API_BASE = 'https://routecast-backend.onrender.com';

const normalize = (value?: string | null): string => (typeof value === 'string' ? value.trim() : '');

const ensureApiSuffix = (base: string): string => {
  const stripped = base.replace(/\/+$/, '');
  if (stripped.toLowerCase().endsWith('/api')) return stripped;
  return `${stripped}/api`;
};

const resolveApiBase = (): string => {
  const envBase = normalize(process.env.EXPO_PUBLIC_BACKEND_URL);
  const configBase = normalize((Constants?.expoConfig as any)?.extra?.API_BASE);

  const candidates = [envBase, configBase, DEFAULT_API_BASE];
  for (const candidate of candidates) {
    if (candidate && /^https?:\/\//.test(candidate)) {
      return ensureApiSuffix(candidate);
    }
  }
  return ensureApiSuffix(DEFAULT_API_BASE);
};

export const API_BASE = resolveApiBase();

export const buildUrl = (path: string): string => {
  const trimmed = path.startsWith('/') ? path.slice(1) : path;
  return `${API_BASE}/${trimmed}`;
};

// Log once at module load to confirm which backend the app will use.
(() => {
  console.log('[Routecast] Backend base URL:', API_BASE || '(not set)');
})();
