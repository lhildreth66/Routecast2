import {
  hasActiveSubscription,
  shouldForcePaywall,
  verifySuccessRoute,
} from '../billingGuards';

describe('billingGuards', () => {
  describe('verifySuccessRoute', () => {
    it('uses native deep-link handoff on web verification callback', () => {
      expect(verifySuccessRoute({ isWeb: true, email: 'user@example.com' }))
        .toBe('routecast2://login?verified=1&email=user%40example.com');
    });

    it('uses guarded app login route on native', () => {
      expect(verifySuccessRoute({ isWeb: false, email: 'user@example.com' }))
        .toBe('/login?verified=1&email=user%40example.com');
    });
  });

  describe('hasActiveSubscription', () => {
    it('requires verified + premium + active status', () => {
      expect(hasActiveSubscription({
        email_verified: true,
        is_premium: true,
        subscription_status: 'trialing',
      })).toBe(true);
    });

    it('rejects premium flag with inactive status', () => {
      expect(hasActiveSubscription({
        email_verified: true,
        is_premium: true,
        subscription_status: 'inactive',
      })).toBe(false);
    });
  });

  describe('shouldForcePaywall', () => {
    it('forces verified unsubscribed users through billing on app content routes', () => {
      const user = {
        email_verified: true,
        is_premium: false,
        subscription_status: 'inactive',
      };
      expect(shouldForcePaywall('/route', 'token-1', user)).toBe(true);
    });

    it('keeps signup -> verify -> login -> unsubscribed flow blocked from home content', () => {
      const user = {
        email_verified: true,
        is_premium: false,
        subscription_status: 'inactive',
      };
      expect(shouldForcePaywall('/', 'token-1', user)).toBe(true);
    });

    it('does not block open paywall route for unsubscribed users', () => {
      const user = {
        email_verified: true,
        is_premium: false,
        subscription_status: 'inactive',
      };
      expect(shouldForcePaywall('/subscription', 'token-1', user)).toBe(false);
    });

    it('blocks no-access-without-subscription-initiation route', () => {
      const user = {
        email_verified: true,
        is_premium: false,
        subscription_status: 'inactive',
      };
      expect(shouldForcePaywall('/truck-stops', 'token-1', user)).toBe(true);
    });

    it('does not force paywall for users with active subscription states', () => {
      const user = {
        email_verified: true,
        is_premium: true,
        subscription_status: 'active',
      };
      expect(shouldForcePaywall('/route', 'token-1', user)).toBe(false);
    });
  });
});
