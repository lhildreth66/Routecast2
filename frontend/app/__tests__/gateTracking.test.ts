/**
 * Tests for Gate Tracking
 *
 * Tests soft/hard gate logic and attempt tracking.
 */

import { jest } from '@jest/globals';
import AsyncStorage from '@react-native-async-storage/async-storage';
import {
  getGateMode,
  recordAttempt,
  resetTracking,
  getTrackingStats,
} from '../billing/gateTracking';

// Mock AsyncStorage
jest.mock('@react-native-async-storage/async-storage', () => ({
  getItem: jest.fn(),
  setItem: jest.fn(),
  removeItem: jest.fn(),
}));

const storageMock = AsyncStorage as unknown as {
  getItem: jest.Mock;
  setItem: jest.Mock;
  removeItem: jest.Mock;
};

describe('Gate Tracking', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    storageMock.getItem.mockResolvedValue(null);
  });

  describe('getGateMode', () => {
    it('returns soft for first attempt', async () => {
      storageMock.getItem.mockResolvedValue(null);

      const mode = await getGateMode('solar_forecast');

      expect(mode).toBe('soft');
    });

    it('returns soft for zero attempts', async () => {
      const tracking = {
        locked_attempt_count: 0,
        attempts: [],
      };
      storageMock.getItem.mockResolvedValue(JSON.stringify(tracking));

      const mode = await getGateMode('solar_forecast');

      expect(mode).toBe('soft');
    });

    it('returns hard for second attempt within window', async () => {
      const now = new Date();
      const tracking = {
        locked_attempt_count: 1,
        first_locked_attempt_at: now.toISOString(),
        last_locked_attempt_at: now.toISOString(),
        attempts: [
          { feature: 'solar_forecast', timestamp: now.toISOString() },
        ],
      };
      storageMock.getItem.mockResolvedValue(JSON.stringify(tracking));

      const mode = await getGateMode('solar_forecast');

      expect(mode).toBe('hard');
    });

    it('returns soft when window expired (>7 days)', async () => {
      const eightDaysAgo = new Date(Date.now() - 8 * 24 * 60 * 60 * 1000);
      const tracking = {
        locked_attempt_count: 5,
        first_locked_attempt_at: eightDaysAgo.toISOString(),
        last_locked_attempt_at: eightDaysAgo.toISOString(),
        attempts: [],
      };
      storageMock.getItem.mockResolvedValue(JSON.stringify(tracking));

      const mode = await getGateMode('solar_forecast');

      expect(mode).toBe('soft');
    });

    it('returns hard for third attempt within window', async () => {
      const now = new Date();
      const tracking = {
        locked_attempt_count: 2,
        first_locked_attempt_at: now.toISOString(),
        last_locked_attempt_at: now.toISOString(),
        attempts: [
          { feature: 'solar_forecast', timestamp: now.toISOString() },
          { feature: 'propane_usage', timestamp: now.toISOString() },
        ],
      };
      storageMock.getItem.mockResolvedValue(JSON.stringify(tracking));

      const mode = await getGateMode('road_sim');

      expect(mode).toBe('hard');
    });
  });

  describe('recordAttempt', () => {
    it('creates first attempt record', async () => {
      storageMock.getItem.mockResolvedValue(null);

      await recordAttempt('solar_forecast');

      expect(storageMock.setItem).toHaveBeenCalled();
      const savedData = JSON.parse(storageMock.setItem.mock.calls[0][1]);
      expect(savedData.locked_attempt_count).toBe(1);
      expect(savedData.first_locked_attempt_at).toBeTruthy();
      expect(savedData.attempts).toHaveLength(1);
      expect(savedData.attempts[0].feature).toBe('solar_forecast');
    });

    it('increments attempt count', async () => {
      const now = new Date();
      const tracking = {
        locked_attempt_count: 1,
        first_locked_attempt_at: now.toISOString(),
        last_locked_attempt_at: now.toISOString(),
        attempts: [
          { feature: 'solar_forecast', timestamp: now.toISOString() },
        ],
      };
      storageMock.getItem.mockResolvedValue(JSON.stringify(tracking));

      await recordAttempt('propane_usage');

      const savedData = JSON.parse(storageMock.setItem.mock.calls[0][1]);
      expect(savedData.locked_attempt_count).toBe(2);
      expect(savedData.attempts).toHaveLength(2);
    });

    it('resets when window expired', async () => {
      const eightDaysAgo = new Date(Date.now() - 8 * 24 * 60 * 60 * 1000);
      const tracking = {
        locked_attempt_count: 3,
        first_locked_attempt_at: eightDaysAgo.toISOString(),
        last_locked_attempt_at: eightDaysAgo.toISOString(),
        attempts: [],
      };
      storageMock.getItem.mockResolvedValue(JSON.stringify(tracking));

      await recordAttempt('solar_forecast');

      const savedData = JSON.parse(storageMock.setItem.mock.calls[0][1]);
      expect(savedData.locked_attempt_count).toBe(1); // Reset to 1
      expect(savedData.attempts).toHaveLength(1);
    });
  });

  describe('resetTracking', () => {
    it('removes tracking data', async () => {
      await resetTracking();

      expect(storageMock.removeItem).toHaveBeenCalledWith('routecast_gate_tracking');
    });
  });

  describe('getTrackingStats', () => {
    it('returns current tracking', async () => {
      const tracking = {
        locked_attempt_count: 2,
        first_locked_attempt_at: new Date().toISOString(),
        attempts: [],
      };
      storageMock.getItem.mockResolvedValue(JSON.stringify(tracking));

      const stats = await getTrackingStats();

      expect(stats.locked_attempt_count).toBe(2);
    });

    it('returns empty tracking when none exists', async () => {
      storageMock.getItem.mockResolvedValue(null);

      const stats = await getTrackingStats();

      expect(stats.locked_attempt_count).toBe(0);
      expect(stats.attempts).toEqual([]);
    });
  });
});
