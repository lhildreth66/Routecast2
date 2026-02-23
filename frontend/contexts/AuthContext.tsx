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

// ─── module-level mutex ───────────────────────────────────────────────────────
let LOGIN_IN_FLIGHT = false;

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
  await AsyncStorage.multiSet([
    ['accessToken', access_token],
    ['refreshToken', refresh_token],
    ['access_token', access_token],
    ['refresh_token', refresh_token],
  ]);
}

async function clearTokens(): Promise<void> {
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
        const [[, at], [, rt]] = await AsyncStorage.multiGet(['accessToken', 'refreshToken']);
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
  const fetchUserProfile = async (token: string): Promise<boolean> => {
    try {
      const response = await axios.get(buildUrl('auth/me'), {
        headers: { Authorization: `Bearer ${token}` },
      });
      setUser(response.data);
      __DEV__ && console.log('[auth] /auth/me success');
      return true;
    } catch (err: any) {
      console.warn('[auth] /auth/me failed', err?.response?.status ?? err?.message);
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

  // Block rendering until hydration is done to prevent hook-order and
  // state-update-during-render React crashes (#418 / #422).
  if (!hasHydrated) {
    return null;
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
