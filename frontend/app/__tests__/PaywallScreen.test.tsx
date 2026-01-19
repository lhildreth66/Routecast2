/**
 * Tests for PaywallScreen
 *
 * Tests soft/hard gate UI and dismiss behavior.
 */

import React from 'react';
import { render, fireEvent, waitFor } from '@testing-library/react-native';
import { PaywallScreen } from '../billing/PaywallScreen';

const mockProducts = [
  {
    productId: 'boondocking_pro_monthly',
    title: 'Boondocking Pro Monthly',
    description: 'Monthly subscription',
    price: '$9.99',
    localizedPrice: '$9.99',
    currency: 'USD',
  },
  {
    productId: 'boondocking_pro_yearly',
    title: 'Boondocking Pro Yearly',
    description: 'Yearly subscription',
    price: '$99.99',
    localizedPrice: '$99.99',
    currency: 'USD',
  },
];

jest.mock('../billing/iapClient', () => {
  const mockFetchProducts = jest.fn(async () => mockProducts);

  return {
    __esModule: true,
    iapClient: {
      fetchProducts: mockFetchProducts,
      startPurchaseFlow: jest.fn(),
      restorePurchases: jest.fn(),
    },
    mockFetchProducts,
  };
});

const { mockFetchProducts } = jest.requireMock('../billing/iapClient');

// Mock react-native-iap
jest.mock('react-native-iap', () => ({
  useIAP: () => ({
    connected: true,
    products: mockProducts,
    getProducts: jest.fn(),
    requestPurchase: jest.fn(),
    finishTransaction: jest.fn(),
  }),
  getSubscriptions: jest.fn(async () => mockProducts),
}));

// Mock useEntitlements
jest.mock('../billing/useEntitlements', () => ({
  useEntitlements: () => ({
    isPremium: false,
    isLoading: false,
    refresh: jest.fn(),
  }),
}));

describe('PaywallScreen', () => {
  const mockOnClose = jest.fn();
  const mockOnPurchaseComplete = jest.fn();

  const renderPaywall = async (props: Partial<React.ComponentProps<typeof PaywallScreen>> = {}) => {
    const utils = render(
      <PaywallScreen
        visible={true}
        gateMode="soft"
        onClose={mockOnClose}
        onPurchaseComplete={mockOnPurchaseComplete}
        {...props}
      />
    );

    if (props.visible !== false) {
      await waitFor(() => expect(mockFetchProducts).toHaveBeenCalled());
    }
    return utils;
  };

  beforeEach(() => {
    jest.clearAllMocks();
    mockFetchProducts.mockResolvedValue(mockProducts);
  });

  describe('Soft Gate (dismissible)', () => {
    it('renders "Not Now" button in soft gate mode', async () => {
      const { getByText } = await renderPaywall({ feature: 'solar_forecast', gateMode: 'soft' });

      expect(getByText('Not Now')).toBeTruthy();
    });

    it('does not show hard gate warning in soft mode', async () => {
      const { queryByText } = await renderPaywall({ feature: 'solar_forecast', gateMode: 'soft' });

      expect(queryByText(/upgrade now to continue using/i)).toBeFalsy();
    });

    it('calls onClose when "Not Now" is pressed', async () => {
      const { getByText } = await renderPaywall({ feature: 'solar_forecast', gateMode: 'soft' });

      fireEvent.press(getByText('Not Now'));

      expect(mockOnClose).toHaveBeenCalled();
    });
  });

  describe('Hard Gate (non-dismissible)', () => {
    it('does not render "Not Now" button in hard gate mode', async () => {
      const { queryByText } = await renderPaywall({ feature: 'solar_forecast', gateMode: 'hard' });

      expect(queryByText('Not Now')).toBeFalsy();
    });

    it('shows hard gate warning message', async () => {
      const { getByText } = await renderPaywall({ feature: 'solar_forecast', gateMode: 'hard' });

      expect(getByText(/premium features require an active subscription/i)).toBeTruthy();
    });
  });

  describe('Plan Selection', () => {
    it('defaults to monthly plan', async () => {
      const { getByText } = await renderPaywall();

      expect(getByText('$9.99')).toBeTruthy();
      expect(getByText('per month')).toBeTruthy();
    });

    it('switches to yearly plan when toggled', async () => {
      const { getByText } = await renderPaywall();

      const yearlyButton = getByText(/yearly/i);
      fireEvent.press(yearlyButton);

      expect(getByText('$99.99')).toBeTruthy();
      expect(getByText('per year')).toBeTruthy();
    });
  });

  describe('Value Propositions', () => {
    it('renders all 6 value props', async () => {
      const { getByText } = await renderPaywall();

      expect(getByText(/road passability/i)).toBeTruthy();
      expect(getByText(/connectivity/i)).toBeTruthy();
      expect(getByText(/power/i)).toBeTruthy();
      expect(getByText(/propane/i)).toBeTruthy();
      expect(getByText(/campsite/i)).toBeTruthy();
      expect(getByText(/claim log/i)).toBeTruthy();
    });
  });

  describe('CTA Button', () => {
    it('renders CTA with correct text', async () => {
      const { getByText } = await renderPaywall();

      expect(getByText('Start Boondocking Pro')).toBeTruthy();
    });
  });

  describe('Restore Purchases', () => {
    it('renders restore purchases link', async () => {
      const { getByText } = await renderPaywall();

      expect(getByText('Restore Purchases')).toBeTruthy();
    });
  });

  describe('Legal Links', () => {
    it('renders Terms of Service link', async () => {
      const { getByText } = await renderPaywall();

      expect(getByText('Terms of Service')).toBeTruthy();
    });

    it('renders Privacy Policy link', async () => {
      const { getByText } = await renderPaywall();

      expect(getByText('Privacy Policy')).toBeTruthy();
    });
  });

  describe('Visibility Control', () => {
    it('does not render when visible is false', async () => {
      const { queryByText } = await renderPaywall({ visible: false });

      expect(queryByText('Boondocking Pro')).toBeFalsy();
    });

    it('renders when visible is true', async () => {
      const { getByText } = await renderPaywall({ visible: true });

      expect(getByText('Boondocking Pro')).toBeTruthy();
    });
  });
});
