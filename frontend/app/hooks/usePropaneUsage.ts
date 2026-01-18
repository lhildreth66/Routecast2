"""
usePropaneUsage - React Hook for Propane Consumption Estimation

Custom hook for calling the propane usage API endpoint and managing state.
Follows the same pattern as useSolarForecast.
"""

import { useState } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';

const API_BASE = process.env.EXPO_PUBLIC_API_BASE || 'http://localhost:8000';

// Type-safe interfaces matching API models

export interface PropaneUsageRequest {
  furnace_btu: number;
  duty_cycle_pct: number;
  nights_temp_f: number[];
  people?: number;
  subscription_id?: string;
}

export interface PropaneUsageResponse {
  daily_lbs?: number[] | null;
  nights_temp_f?: number[] | null;
  furnace_btu?: number | null;
  duty_cycle_pct?: number | null;
  people?: number | null;
  advisory?: string | null;
  is_premium_locked: boolean;
  premium_message?: string | null;
}

export interface UsePropaneUsageReturn {
  estimate: (request: PropaneUsageRequest) => Promise<PropaneUsageResponse | null>;
  loading: boolean;
  error: string | null;
  result: PropaneUsageResponse | null;
  clearResult: () => void;
}

/**
 * Hook for propane usage estimation
 *
 * Usage:
 * ```typescript
 * const { estimate, loading, error, result } = usePropaneUsage();
 *
 * await estimate({
 *   furnace_btu: 20000,
 *   duty_cycle_pct: 50,
 *   nights_temp_f: [35, 25, 45],
 *   people: 2,
 * });
 *
 * if (result?.is_premium_locked) {
 *   // Show paywall modal
 * } else if (result?.daily_lbs) {
 *   // Display results
 * }
 * ```
 */
export const usePropaneUsage = (): UsePropaneUsageReturn => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<PropaneUsageResponse | null>(null);

  const estimate = async (
    request: PropaneUsageRequest
  ): Promise<PropaneUsageResponse | null> => {
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
      const response = await fetch(`${API_BASE}/api/pro/propane-usage`, {
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

      const data: PropaneUsageResponse = await response.json();

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
      console.error('Error in usePropaneUsage:', errorMessage);
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
