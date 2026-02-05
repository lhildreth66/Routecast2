/**
 * usePropaneUsage - React Hook for Propane Consumption Estimation
 *
 * Custom hook for calling the propane usage API endpoint and managing state.
 */

import { useState } from 'react';

const API_BASE = process.env.EXPO_PUBLIC_API_BASE || 'http://localhost:8000';

// Type-safe interfaces matching API models

export interface PropaneUsageRequest {
  furnace_btu: number;
  duty_cycle_pct: number;
  nights_temp_f: number[];
  people?: number;
}

export interface PropaneUsageResponse {
  daily_lbs?: number[] | null;
  nights_temp_f?: number[] | null;
  furnace_btu?: number | null;
  duty_cycle_pct?: number | null;
  people?: number | null;
  advisory?: string | null;
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
      const response = await fetch(`${API_BASE}/api/propane-usage`, {
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

      const data: PropaneUsageResponse = await response.json();
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
