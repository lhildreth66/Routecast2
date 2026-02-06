import axios from 'axios';

// Determine API base URL with strict validation
// Priority: 1) EAS build env
const getApiBase = (): string => {
  // Only use the EAS environment variable (set in eas.json / .env)
  const apiBase = process.env.EXPO_PUBLIC_BACKEND_URL;
  
  // REQUIRE a valid backend URL; no fallback to avoid misrouting traffic
  if (!apiBase) {
    const errorMsg = '❌ CRITICAL: No backend URL configured! Set EXPO_PUBLIC_BACKEND_URL in your env (.env or eas.json).';
    console.error('[apiConfig]', errorMsg);
    throw new Error(errorMsg);
  }
  
  return apiBase;
};

export const API_BASE = getApiBase();
export const API_BASE_SOURCE = process.env.EXPO_PUBLIC_BACKEND_URL ? 'env:EXPO_PUBLIC_BACKEND_URL' : 'missing';
export const API_BASE_ERROR = !API_BASE ? 'No backend URL configured' : '';

console.log('[apiConfig] API_BASE resolved', { base: API_BASE, source: API_BASE_SOURCE });

// Axios request/response logging (no secrets)
axios.interceptors.request.use((config) => {
  const fullUrl = config.baseURL ? `${config.baseURL}${config.url}` : config.url;
  const method = (config.method || 'get').toUpperCase();
  const hasAuth = !!config.headers?.Authorization;
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
    const body = error.response?.data;
    let truncatedBody = body;
    if (typeof body === 'string') {
      truncatedBody = body.slice(0, 200);
    } else if (body) {
      try {
        truncatedBody = JSON.stringify(body).slice(0, 200);
      } catch (e) {
        truncatedBody = '[unserializable body]';
      }
    }
    console.warn('[api] error', { method, url: fullUrl, status, body: truncatedBody });
    return Promise.reject(error);
  }
);
