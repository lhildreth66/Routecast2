import { useState } from 'react';
import { API_BASE } from '../apiConfig';

export interface RoadPassabilityRequest {
  precip_72h: number;      // Precipitation in last 72h (mm)
  slope_pct: number;       // Road grade percentage
  min_temp_f: number;      // Minimum temperature (°F)
  soil_type: string;       // clay, sand, rocky, loam
}

export interface RoadPassabilityResponse {
  passability_score: number;          // 0-100
  condition_assessment: string;       // Excellent, Good, Fair, Poor, Impassable
  advisory: string;                   // Human-readable advisory with emoji
  min_clearance_cm: number;           // Minimum ground clearance needed
  recommended_vehicle_type: string;   // sedan, suv, 4x4
  needs_four_x_four: boolean;
  risks: {
    mud_risk: boolean;
    ice_risk: boolean;
    deep_rut_risk: boolean;
    high_clearance_recommended: boolean;
    four_x_four_recommended: boolean;
  };
}

export interface UseRoadPassabilityReturn {
  assess: (request: RoadPassabilityRequest) => Promise<RoadPassabilityResponse>;
  loading: boolean;
  error: string | null;
  result: RoadPassabilityResponse | null;
  clearResult: () => void;
}

/**
 * Hook for assessing road passability conditions
 * 
 * Features:
 * - Comprehensive risk assessment (mud, ice, clearance)
 * - Vehicle recommendations
 * - Pure deterministic calculations
 */
export const useRoadPassability = (): UseRoadPassabilityReturn => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<RoadPassabilityResponse | null>(null);

  const assess = async (
    request: RoadPassabilityRequest
  ): Promise<RoadPassabilityResponse> => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE}/api/road-passability`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          precip_72h: request.precip_72h,
          slope_pct: request.slope_pct,
          min_temp_f: request.min_temp_f,
          soil_type: request.soil_type,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(
          errorData.detail || `API error: ${response.status}`
        );
      }

      const data: RoadPassabilityResponse = await response.json();
      setResult(data);
      return data;
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : 'Unknown error assessing road conditions';
      setError(errorMessage);
      console.error('[RoadPassability] Assessment error:', errorMessage);
      throw err;
    } finally {
      setLoading(false);
    }
  };

  const clearResult = () => {
    setResult(null);
    setError(null);
  };

  return {
    assess,
    loading,
    error,
    result,
    clearResult,
  };
};
