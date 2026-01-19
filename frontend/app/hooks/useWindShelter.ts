/**
 * useWindShelter - React Hook for Wind Shelter Orientation Recommendation
 *
 * Custom hook for calling the wind shelter API endpoint.
 * Recommends RV orientation based on local ridge terrain and wind conditions.
 */

import { useState } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';

const API_BASE = process.env.EXPO_PUBLIC_API_BASE || 'http://localhost:8000';

// Type-safe interfaces matching API models

export interface WindShelterRidge {
  bearing_deg: number; // 0-360°
  strength: 'low' | 'med' | 'high';
  name?: string;
}

export interface WindShelterRequest {
  predominant_dir_deg: number; // Wind direction (0-360°)
  gust_mph: number; // Peak wind gust speed
  local_ridges?: WindShelterRidge[] | null;
  subscription_id?: string;
}

export interface WindShelterResponse {
  recommended_bearing_deg?: number | null;
  rationale_text?: string | null;
  risk_level?: 'low' | 'medium' | 'high' | null;
  shelter_available?: boolean | null;
  estimated_wind_reduction_pct?: number | null;
  is_premium_locked: boolean;
  premium_message?: string | null;
}

export interface UseWindShelterReturn {
  estimate: (request: WindShelterRequest) => Promise<WindShelterResponse | null>;
  loading: boolean;
  error: string | null;
  result: WindShelterResponse | null;
  clearResult: () => void;
}

/**
 * Hook for wind shelter orientation recommendation
 *
 * Usage:
 * ```typescript
 * const { estimate, loading, error, result } = useWindShelter();
 *
 * await estimate({
 *   predominant_dir_deg: 270, // Wind from west
 *   gust_mph: 35,
 *   local_ridges: [
 *     { bearing_deg: 90, strength: 'high', name: 'Rock formation' }
 *   ],
 * });
 *
 * if (result?.is_premium_locked) {
 *   // Show paywall modal
 * } else if (result?.recommended_bearing_deg !== undefined) {
 *   // Display orientation recommendation
 * }
 * ```
 */
export const useWindShelter = (): UseWindShelterReturn => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<WindShelterResponse | null>(null);

  const estimate = async (
    request: WindShelterRequest
  ): Promise<WindShelterResponse | null> => {
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

      // Call API endpoint for wind shelter recommendation
      const response = await fetch(`${API_BASE}/api/pro/wind-shelter/orientation`, {
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

      const data: WindShelterResponse = await response.json();

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
      console.error('Error in useWindShelter:', errorMessage);
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
