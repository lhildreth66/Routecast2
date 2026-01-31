/**
 * useTerrainShade - React Hook for Terrain Shade Estimation
 *
 * Custom hook for calling the solar path and shade blocking API endpoints.
 * Calculates sunlight availability and shade factor for camping locations.
 */

import { useState } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';

const API_BASE = process.env.EXPO_PUBLIC_API_BASE || 'http://localhost:8000';

// Type-safe interfaces matching API models

export interface SunPathSlot {
  hour: number;
  sun_elevation_deg: number;
  usable_sunlight_fraction: number;
  time_label: string;
}

export interface TerrainShadeRequest {
  latitude: number;
  longitude: number;
  date: string; // ISO format: YYYY-MM-DD
  tree_canopy_pct?: number; // 0-100%
  horizon_obstruction_deg?: number; // 0-90°
  subscription_id?: string;
}

export interface TerrainShadeResponse {
  sun_path_slots?: SunPathSlot[] | null;
  shade_factor?: number | null; // 0.0-1.0
  exposure_hours?: number | null; // Effective sunlight hours
  is_premium_locked: boolean;
  premium_message?: string | null;
}

export interface UseTerrainShadeReturn {
  estimate: (request: TerrainShadeRequest) => Promise<TerrainShadeResponse | null>;
  loading: boolean;
  error: string | null;
  result: TerrainShadeResponse | null;
  clearResult: () => void;
}

/**
 * Hook for terrain shade and solar path estimation
 *
 * Usage:
 * ```typescript
 * const { estimate, loading, error, result } = useTerrainShade();
 *
 * await estimate({
 *   latitude: 40.7128,
 *   longitude: -105.1084,
 *   date: '2024-06-21',
 *   tree_canopy_pct: 60,
 *   horizon_obstruction_deg: 15,
 * });
 *
 * if (result?.is_premium_locked) {
 *   // Show paywall modal
 * } else if (result?.sun_path_slots) {
 *   // Display solar path and shade factor
 * }
 * ```
 */
export const useTerrainShade = (): UseTerrainShadeReturn => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<TerrainShadeResponse | null>(null);

  const estimate = async (
    request: TerrainShadeRequest
  ): Promise<TerrainShadeResponse | null> => {
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

      // Call API endpoint for solar path
      const response = await fetch(`${API_BASE}/api/pro/terrain/sun-path`, {
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

      const data: TerrainShadeResponse = await response.json();

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
      console.error('Error in useTerrainShade:', errorMessage);
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
