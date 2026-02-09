import axios from 'axios';
import Constants from 'expo-constants';

const DEFAULT_API_BASE = 'https://routecast-backend.onrender.com';

type ApiBaseResolution = {
  base: string;
  source: string;
  error?: string;
};

const normalize = (value?: string | null): string => (typeof value === 'string' ? value.trim() : '');

const ensureApiSuffix = (base: string): string => {
  // Remove trailing slashes to normalize, then ensure single /api suffix
  const stripped = base.replace(/\/+$/, '');
  if (stripped.toLowerCase().endsWith('/api')) {
    return stripped;
  }
  return `${stripped}/api`;
};

const resolveApiBase = (): ApiBaseResolution => {
  const envBase = normalize(process.env.EXPO_PUBLIC_BACKEND_URL);
  const configBase = normalize(
    // Supports both expoConfig (dev/build) and manifest (runtime) shapes
    (Constants?.expoConfig?.extra as any)?.API_BASE || (Constants?.manifest?.extra as any)?.API_BASE
  );

  const candidates = [
    { base: envBase, source: 'env:EXPO_PUBLIC_BACKEND_URL' },
    { base: configBase, source: 'config:extra.API_BASE' },
    { base: DEFAULT_API_BASE, source: 'fallback:render-default' },
  ];

  for (const candidate of candidates) {
    if (candidate.base && /^https?:\/\//.test(candidate.base)) {
      const resolved = ensureApiSuffix(candidate.base);
      const error = candidate.source.startsWith('fallback')
        ? 'Using default backend URL; env/config not set.'
        : '';
      return { base: resolved, source: candidate.source, error };
    }
  }

  const resolved = ensureApiSuffix(DEFAULT_API_BASE);
  return {
    base: resolved,
    source: 'fallback:render-default',
    error: 'Using default backend URL; no valid candidate found.',
  };
};

const apiBaseResolution = resolveApiBase();

export const API_BASE = apiBaseResolution.base;
export const API_BASE_SOURCE = apiBaseResolution.source;
export const API_BASE_ERROR = apiBaseResolution.error || '';

export const buildUrl = (path: string): string => {
  const trimmed = path.startsWith('/') ? path.slice(1) : path;
  return `${API_BASE}/${trimmed}`;
};

console.log('[apiConfig] API_BASE resolved', {
  base: API_BASE,
  source: API_BASE_SOURCE,
  error: API_BASE_ERROR || 'none',
});
console.log(`[api] API_BASE=${API_BASE}`);

// Global fetch logging wrapper for network triage
if (typeof global !== 'undefined' && typeof global.fetch === 'function') {
  const originalFetch = global.fetch;
  global.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === 'string' || input instanceof URL ? input.toString() : String(input);
    const method = (init?.method || 'GET').toUpperCase();
    console.log('[net]', method, url);
    try {
      const response = await originalFetch(input as any, init as any);
      const contentType = response.headers.get('content-type') || '';
      const isHtml = contentType.includes('text/html');
      const status = response.status;
      console.log('[net] request', { method, url, status, isHtml });

      if (isHtml || status >= 300) {
        try {
          const text = await response.clone().text();
          if (text.includes('<!DOCTYPE') || text.includes('<html')) {
            console.warn('[net] HTML response detected', { url, status, snippet: text.slice(0, 200) });
          }
        } catch (e) {
          console.warn('[net] unable to read response text', { url, status, error: String(e) });
        }
      }

      return response;
    } catch (err: any) {
      console.warn('[net] fetch error', { method, url, error: String(err) });
      throw err;
    }
  };
}

// Axios request/response logging (no secrets)
axios.interceptors.request.use((config) => {
  const fullUrl = config.baseURL ? `${config.baseURL}${config.url}` : config.url;
  const method = (config.method || 'get').toUpperCase();
  const hasAuth = !!config.headers?.Authorization;
  console.log('[net]', method, fullUrl);
  console.log('[api] request', { method, url: fullUrl, auth: hasAuth });
  return config;
});

axios.interceptors.response.use(
  (response) => {
    const fullUrl = response.config.baseURL ? `${response.config.baseURL}${response.config.url}` : response.config.url;
    const method = (response.config.method || 'get').toUpperCase();
    console.log('[api] response', { method, url: fullUrl, status: response.status });
    return response;
  },
  (error) => {
    const cfg = error.config || {};
    const fullUrl = cfg.baseURL ? `${cfg.baseURL}${cfg.url}` : cfg.url;
    const method = (cfg.method || 'get').toUpperCase();
    const status = error.response?.status;
    const headers = error.response?.headers;
    const body = error.response?.data;

    const summarizeBody = () => {
      if (!body) return '[empty body]';
      if (typeof body === 'string') return body.slice(0, 500);
      try {
        return JSON.stringify(body).slice(0, 500);
      } catch {
        return '[unserializable body]';
      }
    };

    console.warn('[api] error', {
      method,
      url: fullUrl,
      status,
      headers: headers ? { 'content-type': headers['content-type'], 'content-length': headers['content-length'] } : undefined,
      body: summarizeBody(),
    });
    return Promise.reject(error);
  }
);
