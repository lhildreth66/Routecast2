"""
useWaterBudget - React Hook for Water Budget Estimation

Custom hook for calling the water budget API endpoint and managing state.
Follows the same pattern as usePropaneUsage.
"""

import { useState } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';

const API_BASE = process.env.EXPO_PUBLIC_API_BASE || 'http://localhost:8000';

// Type-safe interfaces matching API models

export interface WaterBudgetRequest {
  fresh_gal: number;
  gray_gal: number;
  black_gal: number;
  people?: number;
  showers_per_week?: number;
  hot_days?: boolean;
  subscription_id?: string;
}

export interface WaterBudgetResponse {
  days_remaining?: number | null;
  limiting_factor?: string | null;
  daily_fresh_gal?: number | null;
  daily_gray_gal?: number | null;
  daily_black_gal?: number | null;
  advisory?: string | null;
  is_premium_locked: boolean;
  premium_message?: string | null;
}

export interface UseWaterBudgetReturn {
  estimate: (request: WaterBudgetRequest) => Promise<WaterBudgetResponse | null>;
  loading: boolean;
  error: string | null;
  result: WaterBudgetResponse | null;
  clearResult: () => void;
}

/**
 * Hook for water budget estimation
 *
 * Usage:
 * ```typescript
 * const { estimate, loading, error, result } = useWaterBudget();
 *
 * await estimate({
 *   fresh_gal: 40,
 *   gray_gal: 50,
 *   black_gal: 20,
 *   people: 2,
 *   showers_per_week: 2,
 *   hot_days: false,
 * });
 *
 * if (result?.is_premium_locked) {
 *   // Show paywall modal
 * } else if (result?.days_remaining !== undefined) {
 *   // Display results
 * }
 * ```
 */
export const useWaterBudget = (): UseWaterBudgetReturn => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<WaterBudgetResponse | null>(null);

  const estimate = async (
    request: WaterBudgetRequest
  ): Promise<WaterBudgetResponse | null> => {
    setLoading(true);
    setError(null);

    try {
      // Retrieve subscription ID from AsyncStorage if not provided
      let subscriptionId = request.subscription_id;
      if (!subscriptionId) {
        try {
          subscriptionId = await AsyncStorage.getItem('subscription_id');
        } catch (e) {
          console.log('Could not retrieve subscription ID from storage');
        }
      }

      // Call API endpoint
      const response = await fetch(`${API_BASE}/api/pro/water-budget`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          ...request,
          subscription_id: subscriptionId,
        }),
      });

      if (!response.ok) {
        // Try to parse error detail from response
        let errorDetail = `HTTP ${response.status}`;
        try {
          const errorData = await response.json();
          if (errorData.detail) {
            errorDetail = errorData.detail;
          }
        } catch {
          // If response isn't JSON, use status message
          errorDetail = response.statusText || `HTTP ${response.status}`;
        }
        throw new Error(errorDetail);
      }

      const data: WaterBudgetResponse = await response.json();

      // Detect premium-locked response
      if (data.is_premium_locked && data.premium_message) {
        setError(data.premium_message);
        setResult(data);
        setLoading(false);
        return data;
      }

      // Success
      setResult(data);
      setLoading(false);
      return data;
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error';
      console.error('Error in useWaterBudget:', errorMessage);
      setError(errorMessage);
      setLoading(false);
      return null;
    }
  };

  const clearResult = () => {
    setResult(null);
    setError(null);
  };

  return {
    estimate,
    loading,
    error,
    result,
    clearResult,
  };
};
