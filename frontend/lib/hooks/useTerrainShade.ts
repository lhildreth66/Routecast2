/**
 * useTerrainShade - React Hook for Terrain Shade Estimation
 *
 * Custom hook for calling the solar path and shade blocking API endpoints.
 * Calculates sunlight availability and shade factor for camping locations.
 */

import { useState } from 'react';

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
}

export interface TerrainShadeResponse {
  sun_path_slots?: SunPathSlot[] | null;
  shade_factor?: number | null; // 0.0-1.0
  exposure_hours?: number | null; // Effective sunlight hours
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
      const response = await fetch(`${API_BASE}/api/terrain/sun-path`, {
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

      const data: TerrainShadeResponse = await response.json();
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
