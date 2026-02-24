/**
 * AuthContext – clean-room rewrite
 *
 * Rules enforced here:
 *  1. Hydration is PASSIVE – only reads tokens from storage, never calls APIs.
 *  2. /auth/me is called ONLY after a successful login or signup.
 *  3. All auth state mutations go through setAuthState().
 *  4. Module-level LOGIN_IN_FLIGHT mutex prevents double-submits even if the
 *     component re-renders or the button is tapped twice.
 *  5. No redirects live here – redirects are the responsibility of screens.
 */

import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  ReactNode,
} from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import axios from 'axios';
import { buildUrl } from '../app/apiConfig';
import { Platform, View, ActivityIndicator } from 'react-native';

// ─── module-level mutex ───────────────────────────────────────────────────────
let LOGIN_IN_FLIGHT = false;

// Guard: timestamp (ms) of last /auth/me 401.  Prevents re-fetch loops when
// a stale token survives storage but the backend rejects it.
let LAST_AUTH_ME_401_AT = 0;
const AUTH_ME_RETRY_COOLDOWN_MS = 30_000; // 30 s cool-down after a 401

// ─── web localStorage helpers (reliable backup for AsyncStorage on web) ───────
const WEB_AT_KEY = 'rc_access_token';
const WEB_RT_KEY = 'rc_refresh_token';

function webSetTokens(at: string, rt: string) {
  if (Platform.OS !== 'web') return;
  try {
    window.localStorage.setItem(WEB_AT_KEY, at);
    window.localStorage.setItem(WEB_RT_KEY, rt);
  } catch { /* quota / private-mode – non-fatal */ }
}

// Legacy keys written by versions prior to eaa4d296 that must also be cleared.
const WEB_LEGACY_KEYS = ['accessToken', 'access_token', 'refreshToken', 'refresh_token'];

function webClearTokens() {
  if (Platform.OS !== 'web') return;
  try {
    window.localStorage.removeItem(WEB_AT_KEY);
    window.localStorage.removeItem(WEB_RT_KEY);
    WEB_LEGACY_KEYS.forEach(k => window.localStorage.removeItem(k));
  } catch { /* non-fatal */ }
}

function webGetTokens(): [string | null, string | null] {
  if (Platform.OS !== 'web') return [null, null];
  try {
    return [
      window.localStorage.getItem(WEB_AT_KEY),
      window.localStorage.getItem(WEB_RT_KEY),
    ];
  } catch { return [null, null]; }
}

// ─── types ────────────────────────────────────────────────────────────────────
interface User {
  user_id: string;
  email: string;
  name?: string;
  email_verified: boolean;
  subscription_status: string;
  subscription_plan: string;
  subscription_provider?: string;
  subscription_expiration?: string;
  is_premium: boolean;
  entitlements: string[];
  trial_available: boolean;
  trial_days_remaining?: number;
}

interface AuthState {
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
}

interface AuthContextType extends AuthState {
  hasHydrated: boolean;
  isLoading: boolean;
  isAuthenticated: boolean;
  isPremium: boolean;
  login: (email: string, password: string) => Promise<{ success: boolean; error?: string }>;
  signup: (email: string, password: string, name?: string) => Promise<{ success: boolean; error?: string }>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
  refreshAccessToken: () => Promise<boolean>;
}

// ─── context ──────────────────────────────────────────────────────────────────
const AuthContext = createContext<AuthContextType | undefined>(undefined);

// ─── token storage helpers ────────────────────────────────────────────────────
const TOKEN_KEYS = ['accessToken', 'refreshToken', 'access_token', 'refresh_token'] as const;

async function persistTokens(access_token: string, refresh_token: string): Promise<void> {
  // Write to localStorage first (reliable on web) then AsyncStorage.
  webSetTokens(access_token, refresh_token);
  await AsyncStorage.multiSet([
    ['accessToken', access_token],
    ['refreshToken', refresh_token],
    ['access_token', access_token],
    ['refresh_token', refresh_token],
  ]);
}

async function clearTokens(): Promise<void> {
  webClearTokens();
  await AsyncStorage.multiRemove([...TOKEN_KEYS]);
}

// ─── provider ─────────────────────────────────────────────────────────────────
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [refreshToken, setRefreshToken] = useState<string | null>(null);
  const [hasHydrated, setHasHydrated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  // ── single state setter ────────────────────────────────────────────────────
  const setAuthState = (next: Partial<AuthState>) => {
    if ('user' in next) setUser(next.user ?? null);
    if ('accessToken' in next) setAccessToken(next.accessToken ?? null);
    if ('refreshToken' in next) setRefreshToken(next.refreshToken ?? null);
  };

  // ── PASSIVE hydration – no API calls ──────────────────────────────────────
  useEffect(() => {
    let cancelled = false;

    (async () => {
      try {
        // On web, prefer direct localStorage (more reliable than AsyncStorage
        // shim on web build). Fall back to AsyncStorage keys as secondary.
        let at: string | null = null;
        let rt: string | null = null;

        if (Platform.OS === 'web') {
          [at, rt] = webGetTokens();
          if (!at || !rt) {
            // Migrate from old AsyncStorage keys if present
            const [[, asyncAt], [, asyncRt]] = await AsyncStorage.multiGet(['accessToken', 'refreshToken']);
            at = asyncAt;
            rt = asyncRt;
            if (at && rt) {
              webSetTokens(at, rt); // promote to reliable web storage
            }
          }
        } else {
          const [[, asyncAt], [, asyncRt]] = await AsyncStorage.multiGet(['accessToken', 'refreshToken']);
          at = asyncAt;
          rt = asyncRt;
        }

        if (cancelled) return;

        if (at && rt) {
          __DEV__ && console.log('[auth] hydration: tokens found, restoring state (no API call)');
          setAccessToken(at);
          setRefreshToken(rt);
          // NOTE: intentionally NOT calling /auth/me here.
          // Screens that require a user object call refreshUser() explicitly.
        } else {
          __DEV__ && console.log('[auth] hydration: no tokens');
        }
      } catch (err) {
        console.error('[auth] hydration error', err);
      } finally {
        if (!cancelled) {
          __DEV__ && console.log('[auth] hydration complete – hasHydrated = true');
          setHasHydrated(true);
          setIsLoading(false);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  // ── fetch user profile (called only after login / signup / explicit refresh) ─
  // Returns true on success, false on any failure.
  // On 401: clears all tokens + state so the app returns to signed-out UI.
  const fetchUserProfile = async (token: string): Promise<boolean> => {
    try {
      const response = await axios.get(buildUrl('auth/me'), {
        headers: { Authorization: `Bearer ${token}` },
      });
      setUser(response.data);
      LAST_AUTH_ME_401_AT = 0; // clear guard on success
      __DEV__ && console.log('[auth] /auth/me success');
      return true;
    } catch (err: any) {
      const status = err?.response?.status;
      console.warn('[auth] /auth/me failed', status ?? err?.message);

      if (status === 401) {
        // Token is invalid/expired – wipe everything so the app shows signed-out
        // UI immediately and never loops on this token again.
        LAST_AUTH_ME_401_AT = Date.now();
        try { await clearTokens(); } catch { /* best-effort */ }
        setAuthState({ user: null, accessToken: null, refreshToken: null });
        __DEV__ && console.log('[auth] /auth/me 401 – tokens cleared, signed out');
      }

      return false;
    }
  };

  // ── login ─────────────────────────────────────────────────────────────────
  const login = async (
    email: string,
    password: string,
  ): Promise<{ success: boolean; error?: string }> => {
    if (LOGIN_IN_FLIGHT) {
      __DEV__ && console.log('[auth] login blocked – already in flight');
      return { success: false, error: 'Login already in progress' };
    }

    LOGIN_IN_FLIGHT = true;
    __DEV__ && console.log('[auth] POST /auth/login START');

    try {
      const response = await axios.post(buildUrl('auth/login'), { email, password });
      const { access_token, refresh_token } = response.data;

      await persistTokens(access_token, refresh_token);
      setAuthState({ accessToken: access_token, refreshToken: refresh_token });
      __DEV__ && console.log('[auth] tokens stored');

      await fetchUserProfile(access_token);
      __DEV__ && console.log('[auth] POST /auth/login DONE – one /auth/me called');

      return { success: true };
    } catch (err: any) {
      const message = err.response?.data?.detail || 'Login failed. Please try again.';
      console.warn('[auth] POST /auth/login FAILED:', message);
      return { success: false, error: message };
    } finally {
      LOGIN_IN_FLIGHT = false;
    }
  };

  // ── signup ────────────────────────────────────────────────────────────────
  const signup = async (
    email: string,
    password: string,
    name?: string,
  ): Promise<{ success: boolean; error?: string }> => {
    try {
      const response = await fetch(buildUrl('auth/signup'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password, name }),
      });

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        const detail = data?.detail;
        const message =
          typeof detail === 'string'
            ? detail
            : Array.isArray(detail)
            ? detail.map((d: any) => d?.msg || d?.detail).filter(Boolean).join('; ')
            : 'Signup failed. Please try again.';
        return { success: false, error: message || 'Signup failed. Please try again.' };
      }

      const { access_token, refresh_token } = data;
      if (!access_token || !refresh_token) {
        return { success: false, error: 'Signup failed. Please try again.' };
      }

      await persistTokens(access_token, refresh_token);
      setAuthState({ accessToken: access_token, refreshToken: refresh_token });
      await fetchUserProfile(access_token);

      return { success: true };
    } catch (err: any) {
      const message = typeof err?.message === 'string' ? err.message : 'Signup failed. Please try again.';
      return { success: false, error: message };
    }
  };

  // ── logout ────────────────────────────────────────────────────────────────
  const logout = async (): Promise<void> => {
    __DEV__ && console.log('[auth] logout');
    try {
      await clearTokens();
    } catch (err) {
      console.warn('[auth] error clearing tokens during logout:', err);
    }
    setAuthState({ user: null, accessToken: null, refreshToken: null });
  };

  // ── refreshUser – EXPLICIT call only, never automatic ─────────────────────
  const refreshUser = async (): Promise<void> => {
    const token = accessToken;
    if (!token) return;

    // Respect cool-down: if the last /auth/me returned 401 within the window,
    // don't hammer the server and don't loop on mount effects.
    const msSince401 = Date.now() - LAST_AUTH_ME_401_AT;
    if (LAST_AUTH_ME_401_AT > 0 && msSince401 < AUTH_ME_RETRY_COOLDOWN_MS) {
      __DEV__ && console.log(`[auth] refreshUser skipped – 401 cool-down (${Math.round(msSince401 / 1000)}s ago)`);
      return;
    }

    await fetchUserProfile(token);
  };

  // ── refreshAccessToken ────────────────────────────────────────────────────
  const refreshAccessToken = async (): Promise<boolean> => {
    if (!refreshToken) return false;

    try {
      const response = await axios.post(buildUrl('auth/refresh'), {
        refresh_token: refreshToken,
      });
      const { access_token, refresh_token: new_refresh } = response.data;

      await persistTokens(access_token, new_refresh);
      setAuthState({ accessToken: access_token, refreshToken: new_refresh });
      // Note: does NOT call fetchUserProfile – callers can call refreshUser() if needed.
      return true;
    } catch (err) {
      console.warn('[auth] refreshAccessToken failed', err);
      return false;
    }
  };

  // ── value ─────────────────────────────────────────────────────────────────
  const value: AuthContextType = {
    user,
    accessToken,
    refreshToken,
    hasHydrated,
    isLoading,
    // Consider authenticated if we have tokens OR a resolved user object.
    // Passive hydration restores tokens without fetching the user, so we
    // must not treat a token-holding session as "unauthenticated".
    isAuthenticated: !!(user || accessToken),
    isPremium: user?.is_premium ?? false,
    login,
    signup,
    logout,
    refreshUser,
    refreshAccessToken,
  };

  // During initial storage hydration, render a minimal loading indicator
  // instead of null. Returning null causes a blank white screen on slow
  // mobile connections while the async storage read is in flight.
  if (!hasHydrated) {
    return (
      <View style={{ flex: 1, backgroundColor: '#0a0a0a', justifyContent: 'center', alignItems: 'center' }}>
        <ActivityIndicator size="large" color="#22c55e" />
      </View>
    );
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// ─── hook ─────────────────────────────────────────────────────────────────────
export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
