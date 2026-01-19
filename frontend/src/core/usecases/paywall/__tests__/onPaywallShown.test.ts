import { onPaywallShown } from '../onPaywallShown';
import { trackPaywallViewed } from '../../../analytics/paywall';

// Mock paywall analytics
jest.mock('../../../analytics/paywall');
const mockTrackPaywallViewed = trackPaywallViewed as jest.MockedFunction<typeof trackPaywallViewed>;

describe('onPaywallShown', () => {
  beforeEach(() => {
    mockTrackPaywallViewed.mockClear();
  });

  it('calls trackPaywallViewed with feature and source', () => {
    onPaywallShown('solar_forecast', 'dashboard');

    expect(mockTrackPaywallViewed).toHaveBeenCalledTimes(1);
    expect(mockTrackPaywallViewed).toHaveBeenCalledWith({
      feature: 'solar_forecast',
      source: 'dashboard',
    });
  });

  it('handles undefined source', () => {
    onPaywallShown('road_passability');

    expect(mockTrackPaywallViewed).toHaveBeenCalledWith({
      feature: 'road_passability',
      source: undefined,
    });
  });

  it('does not throw when trackPaywallViewed throws', () => {
    mockTrackPaywallViewed.mockImplementationOnce(() => {
      throw new Error('Analytics failure');
    });

    expect(() => {
      onPaywallShown('battery_forecast', 'route_screen');
    }).not.toThrow();
  });

  it('works with all feature types', () => {
    const features: Array<'solar_forecast' | 'road_passability' | 'propane_forecast' | 'battery_forecast' | 'water_plan' | 'cell_starlink' | 'camp_index' | 'claim_log'> = [
      'solar_forecast',
      'road_passability',
      'propane_forecast',
      'battery_forecast',
      'water_plan',
      'cell_starlink',
      'camp_index',
      'claim_log',
    ];

    features.forEach((feature) => {
      mockTrackPaywallViewed.mockClear();
      onPaywallShown(feature, 'test_source');

      expect(mockTrackPaywallViewed).toHaveBeenCalledWith({
        feature,
        source: 'test_source',
      });
    });
  });

  it('passes through source verbatim', () => {
    onPaywallShown('camp_index', 'complex/source/path');

    expect(mockTrackPaywallViewed).toHaveBeenCalledWith({
      feature: 'camp_index',
      source: 'complex/source/path',
    });
  });
});
