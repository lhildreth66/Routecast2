import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import axios from 'axios';
import { buildUrl, API_BASE } from '../app/apiConfig';

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

interface AuthContextType {
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  isLoading: boolean;
  hasHydrated: boolean;
  isAuthenticated: boolean;
  isPremium: boolean;
  login: (email: string, password: string) => Promise<{ success: boolean; error?: string }>;
  signup: (email: string, password: string, name?: string) => Promise<{ success: boolean; error?: string }>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
  refreshAccessToken: () => Promise<boolean>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [refreshToken, setRefreshToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [hasHydrated, setHasHydrated] = useState(false);

  // Load stored tokens on mount
  useEffect(() => {
    loadStoredAuth();
  }, []);

  const loadStoredAuth = async () => {
    try {
      const storedAccess = await AsyncStorage.getItem('accessToken');
      const storedRefresh = await AsyncStorage.getItem('refreshToken');

      if (storedAccess && storedRefresh) {
        setAccessToken(storedAccess);
        setRefreshToken(storedRefresh);

        // Fetch user profile
        await fetchUserProfile(storedAccess);
      }
    } catch (error) {
      console.log('Error loading stored auth:', error);
    } finally {
      setHasHydrated(true);
      setIsLoading(false);
    }
  };

  const fetchUserProfile = async (token: string) => {
    try {
      const response = await axios.get(buildUrl('auth/me'), {
        headers: { Authorization: `Bearer ${token}` }
      });
      setUser(response.data);
    } catch (error: any) {
      // Token might be expired, try refresh
      if (error.response?.status === 401) {
        const refreshed = await refreshAccessToken();
        if (!refreshed) {
          await logout();
        }
      }
    }
  };

  const login = async (email: string, password: string): Promise<{ success: boolean; error?: string }> => {
    try {
      const response = await axios.post(buildUrl('auth/login'), {
        email,
        password
      });

      const { access_token, refresh_token } = response.data;

      await AsyncStorage.setItem('accessToken', access_token);
      await AsyncStorage.setItem('refreshToken', refresh_token);
      await AsyncStorage.setItem('access_token', access_token);
      await AsyncStorage.setItem('refresh_token', refresh_token);

      setAccessToken(access_token);
      setRefreshToken(refresh_token);

      await fetchUserProfile(access_token);

      return { success: true };
    } catch (error: any) {
      const message = error.response?.data?.detail || 'Login failed. Please try again.';
      return { success: false, error: message };
    }
  };

  const signup = async (email: string, password: string, name?: string): Promise<{ success: boolean; error?: string }> => {
    try {
      const response = await fetch(buildUrl('auth/signup'), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email, password, name }),
      });

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        const detail = data?.detail;
        const message = typeof detail === 'string'
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

      await AsyncStorage.setItem('accessToken', access_token);
      await AsyncStorage.setItem('refreshToken', refresh_token);
      await AsyncStorage.setItem('access_token', access_token);
      await AsyncStorage.setItem('refresh_token', refresh_token);

      setAccessToken(access_token);
      setRefreshToken(refresh_token);

      await fetchUserProfile(access_token);

      return { success: true };
    } catch (error: any) {
      const message = typeof error?.message === 'string' ? error.message : 'Signup failed. Please try again.';
      return { success: false, error: message };
    }
  };

  const logout = async () => {
    try {
      await AsyncStorage.multiRemove([
        'accessToken',
        'refreshToken',
        'access_token',
        'refresh_token',
      ]);
    } catch (error) {
      console.log('Error clearing auth tokens:', error);
    } finally {
      setAccessToken(null);
      setRefreshToken(null);
      setUser(null);
    }
  };

  const refreshUser = async () => {
    if (accessToken) {
      await fetchUserProfile(accessToken);
    }
  };

  const refreshAccessToken = async (): Promise<boolean> => {
    try {
      if (!refreshToken) return false;

      const response = await axios.post(buildUrl('auth/refresh'), {
        refresh_token: refreshToken
      });

      const { access_token, refresh_token: new_refresh } = response.data;

      await AsyncStorage.setItem('accessToken', access_token);
      await AsyncStorage.setItem('refreshToken', new_refresh);
      await AsyncStorage.setItem('access_token', access_token);
      await AsyncStorage.setItem('refresh_token', new_refresh);

      setAccessToken(access_token);
      setRefreshToken(new_refresh);

      await fetchUserProfile(access_token);

      return true;
    } catch (error) {
      return false;
    }
  };

  const value: AuthContextType = {
    user,
    accessToken,
    refreshToken,
    isLoading,
    hasHydrated,
    isAuthenticated: !!user,
    isPremium: user?.is_premium || false,
    login,
    signup,
    logout,
    refreshUser,
    refreshAccessToken
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
