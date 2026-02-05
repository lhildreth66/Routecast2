/**
 * useWaterBudget - React Hook for Water Budget Estimation
 *
 * Custom hook for calling the water budget API endpoint and managing state.
 */

import { useState } from 'react';

const API_BASE = process.env.EXPO_PUBLIC_API_BASE || 'http://localhost:8000';

// Type-safe interfaces matching API models

export interface WaterBudgetRequest {
  fresh_gal: number;
  gray_gal: number;
  black_gal: number;
  people?: number;
  showers_per_week?: number;
  hot_days?: boolean;
}

export interface WaterBudgetResponse {
  days_remaining?: number | null;
  limiting_factor?: string | null;
  daily_fresh_gal?: number | null;
  daily_gray_gal?: number | null;
  daily_black_gal?: number | null;
  advisory?: string | null;
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
      const response = await fetch(`${API_BASE}/api/water-budget`, {
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

      const data: WaterBudgetResponse = await response.json();
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
