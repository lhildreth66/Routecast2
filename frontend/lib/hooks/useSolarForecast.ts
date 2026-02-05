import { useState } from 'react';
import { API_BASE } from '../apiConfig';

export interface SolarForecastRequest {
  lat: number;                // Latitude (-90 to 90)
  lon: number;                // Longitude (-180 to 180)
  date_range: string[];       // ISO format dates (e.g., ["2026-01-20"])
  panel_watts: number;        // Solar panel capacity in watts (>0)
  shade_pct: number;          // Average shade percentage (0-100)
  cloud_cover: number[];      // Cloud cover % per date (0-100)
}

export interface SolarForecastResponse {
  daily_wh?: number[];        // Wh/day for each date
  dates?: string[];
  panel_watts?: number;
  shade_pct?: number;
  advisory?: string;          // Human-readable advisory with emoji
}

export interface UseSolarForecastReturn {
  forecast: (request: SolarForecastRequest) => Promise<SolarForecastResponse>;
  loading: boolean;
  error: string | null;
  result: SolarForecastResponse | null;
  clearResult: () => void;
}

/**
 * Hook for forecasting daily solar energy generation
 * 
 * Features:
 * - Pure deterministic calculations
 * - Accounts for latitude, season, cloud cover, and shade
 * - Returns Wh/day estimates for multi-day forecasts
 */
export const useSolarForecast = (): UseSolarForecastReturn => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<SolarForecastResponse | null>(null);

  const forecast = async (
    request: SolarForecastRequest
  ): Promise<SolarForecastResponse> => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE}/api/solar-forecast`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          lat: request.lat,
          lon: request.lon,
          date_range: request.date_range,
          panel_watts: request.panel_watts,
          shade_pct: request.shade_pct,
          cloud_cover: request.cloud_cover,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(
          errorData.detail || `API error: ${response.status}`
        );
      }

      const data: SolarForecastResponse = await response.json();
      setResult(data);
      return data;
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : 'Unknown error forecasting solar energy';
      setError(errorMessage);
      console.error('[SolarForecast] Forecast error:', errorMessage);
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
    forecast,
    loading,
    error,
    result,
    clearResult,
  };
};
