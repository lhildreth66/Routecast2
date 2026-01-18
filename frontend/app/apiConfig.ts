const API_BASE = process.env.EXPO_PUBLIC_BACKEND_URL || '';

// Log once at module load to confirm which backend the app will use.
(() => {
  console.log('[Routecast] Backend base URL:', API_BASE || '(not set)');
})();

export { API_BASE };
