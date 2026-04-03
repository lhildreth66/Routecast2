import {
  hasActiveSubscription,
  shouldForcePaywall,
  verifySuccessRoute,
  isWebAllowed,
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
      };      expect(shouldForcePaywall('/route', 'token-1', user)).toBe(false);
    });
  });

  describe('isWebAllowed - website is informational only (Android app only)', () => {
    // These routes must NEVER be accessible on the web build.
    // The website (routecastweather.com) has no login, no signup, no app content.
    it.each([
      ['/'],
      ['/login'],
      ['/signup'],
      ['/subscription'],
      ['/account'],
      ['/route'],
      ['/boondockers'],
      ['/free-camping'],
      ['/solar-forecast'],
      ['/truck-stops'],
      ['/radar-map'],
    ])('blocks %s on web (redirects to /landing)', (route) => {
      expect(isWebAllowed(route)).toBe(false);
    });

    // These are the only routes served on the website.
    it.each([
      ['/landing'],
      ['/verify-email'],
      ['/terms'],
      ['/privacy'],
      ['/contact'],
      ['/welcome'],
    ])('allows %s on web (informational/verification page)', (route) => {
      expect(isWebAllowed(route)).toBe(true);
    });
  });
});
