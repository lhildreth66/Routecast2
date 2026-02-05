/**
 * useWindShelter - React Hook for Wind Shelter Orientation Recommendation
 *
 * Custom hook for calling the wind shelter API endpoint.
 * Recommends RV orientation based on local ridge terrain and wind conditions.
 */

import { useState } from 'react';

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
}

export interface WindShelterResponse {
  recommended_bearing_deg?: number | null;
  rationale_text?: string | null;
  risk_level?: 'low' | 'medium' | 'high' | null;
  shelter_available?: boolean | null;
  estimated_wind_reduction_pct?: number | null;
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
      const response = await fetch(`${API_BASE}/api/wind-shelter/orientation`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(request),
      });

      if (!response.ok) {
        let errorDetail = `HTTP ${response.status}`;
        try {
          const errorData = await response.json();
          if (errorData.detail) {
            errorDetail = errorData.detail;
          }
        } catch {
          errorDetail = response.statusText || `HTTP ${response.status}`;
        }
        throw new Error(errorDetail);
      }

      const data: WindShelterResponse = await response.json();
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
