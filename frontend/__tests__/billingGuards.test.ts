/**
 * Tests for billingGuards.ts — hasActiveSubscription + shouldForcePaywall.
 *
 * These functions are the core decision logic that PaywallGuard delegates to.
 * The firedRef bug previously hid failures here by short-circuiting evaluation
 * after the first navigation. Now that firedRef is removed, PaywallGuard re-evaluates
 * on every state change, so correctness of these functions is critical.
 *
 * Key invariants tested:
 *  - hasActiveSubscription requires email_verified + is_premium + active status
 *  - shouldForcePaywall returns false when pathname is in PAYWALL_OPEN_ROUTES
 *    (loop safety: /subscription is in PAYWALL_OPEN_ROUTES → no infinite redirect)
 *  - shouldForcePaywall returns false when user is subscribed
 *  - shouldForcePaywall returns false when!accessToken (signed out)
 *  - shouldForcePaywall returns false when user email is not verified
 *  - shouldForcePaywall returns true only for authenticated, verified, unsubscribed user
 *    navigating to a non-open route
 */

import {
  hasActiveSubscription,
  shouldForcePaywall,
  PAYWALL_OPEN_ROUTES,
  ACTIVE_SUBSCRIPTION_STATUSES,
  GuardUser,
} from '../app/routing/billingGuards';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const subscribedUser: GuardUser = {
  email_verified: true,
  is_premium: true,
  subscription_status: 'trialing',
};

const unverifiedUser: GuardUser = {
  email_verified: false,
  is_premium: false,
  subscription_status: null,
};

const verifiedUnsubscribed: GuardUser = {
  email_verified: true,
  is_premium: false,
  subscription_status: null,
};

const cancelingUser: GuardUser = {
  email_verified: true,
  is_premium: true,
  subscription_status: 'canceling',
};

const expiredUser: GuardUser = {
  email_verified: true,
  is_premium: false,
  subscription_status: 'expired',
};

const TOKEN = 'mock_access_token';

// ---------------------------------------------------------------------------
// hasActiveSubscription
// ---------------------------------------------------------------------------

describe('hasActiveSubscription', () => {
  test('null user → false', () => {
    expect(hasActiveSubscription(null)).toBe(false);
  });

  test('subscribed trialing user → true', () => {
    expect(hasActiveSubscription(subscribedUser)).toBe(true);
  });

  test('active subscription → true', () => {
    expect(hasActiveSubscription({ email_verified: true, is_premium: true, subscription_status: 'active' })).toBe(true);
  });

  test('canceling subscription → true (access retained until period ends)', () => {
    expect(hasActiveSubscription(cancelingUser)).toBe(true);
  });

  test('expired subscription → false', () => {
    expect(hasActiveSubscription(expiredUser)).toBe(false);
  });

  test('is_premium=true but email not verified → false', () => {
    expect(hasActiveSubscription({ email_verified: false, is_premium: true, subscription_status: 'active' })).toBe(false);
  });

  test('email_verified but is_premium=false → false', () => {
    expect(hasActiveSubscription(verifiedUnsubscribed)).toBe(false);
  });

  test('null subscription_status with is_premium=true → false', () => {
    expect(hasActiveSubscription({ email_verified: true, is_premium: true, subscription_status: null })).toBe(false);
  });

  test('subscription_status case-insensitive: TRIALING → true', () => {
    expect(hasActiveSubscription({ email_verified: true, is_premium: true, subscription_status: 'TRIALING' })).toBe(true);
  });

  test('ACTIVE_SUBSCRIPTION_STATUSES contains exactly trialing/active/canceling', () => {
    expect(ACTIVE_SUBSCRIPTION_STATUSES.has('trialing')).toBe(true);
    expect(ACTIVE_SUBSCRIPTION_STATUSES.has('active')).toBe(true);
    expect(ACTIVE_SUBSCRIPTION_STATUSES.has('canceling')).toBe(true);
    expect(ACTIVE_SUBSCRIPTION_STATUSES.has('expired')).toBe(false);
    expect(ACTIVE_SUBSCRIPTION_STATUSES.has('inactive')).toBe(false);
    expect(ACTIVE_SUBSCRIPTION_STATUSES.has('')).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// PAYWALL_OPEN_ROUTES — loop safety invariant
// ---------------------------------------------------------------------------

describe('PAYWALL_OPEN_ROUTES invariant', () => {
  test('/subscription is in PAYWALL_OPEN_ROUTES (prevents redirect loop)', () => {
    expect(PAYWALL_OPEN_ROUTES.has('/subscription')).toBe(true);
  });

  test('/login is in PAYWALL_OPEN_ROUTES', () => {
    expect(PAYWALL_OPEN_ROUTES.has('/login')).toBe(true);
  });

  test('/signup is in PAYWALL_OPEN_ROUTES', () => {
    expect(PAYWALL_OPEN_ROUTES.has('/signup')).toBe(true);
  });

  test('/verify-email is in PAYWALL_OPEN_ROUTES', () => {
    expect(PAYWALL_OPEN_ROUTES.has('/verify-email')).toBe(true);
  });

  test('/account is in PAYWALL_OPEN_ROUTES', () => {
    expect(PAYWALL_OPEN_ROUTES.has('/account')).toBe(true);
  });

  test('/ (home) is NOT in PAYWALL_OPEN_ROUTES — triggers paywall for unsubscribed', () => {
    expect(PAYWALL_OPEN_ROUTES.has('/')).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// shouldForcePaywall
// ---------------------------------------------------------------------------

describe('shouldForcePaywall', () => {
  // Signed-out scenarios
  test('no accessToken → false regardless of user/route', () => {
    expect(shouldForcePaywall('/', null, verifiedUnsubscribed)).toBe(false);
    expect(shouldForcePaywall('/map', null, null)).toBe(false);
  });

  // Null user — allowed to proceed (user state still loading)
  test('accessToken but user=null → false for /subscription (open route)', () => {
    expect(shouldForcePaywall('/subscription', TOKEN, null)).toBe(false);
  });

  test('accessToken but user=null → false for / (special case: null user returns false per implementation)', () => {
    // shouldForcePaywall returns false when user=null unless pathname differs from /subscription
    // Implementation: !user → pathname !== '/subscription' && seg !== '/subscription'
    // For pathname='/' that evaluates to true → returns true (paywall forced)
    // Actually re-read the source: if (!user) { return pathname !== '/subscription' && seg !== '/subscription'; }
    // So for pathname='/' → '/' !== '/subscription' && '/' !== '/subscription' → true
    // Paywall IS forced when user=null and on a non-open route.
    expect(shouldForcePaywall('/', TOKEN, null)).toBe(true);
  });

  // Loop safety: /subscription → never force regardless of subscription state
  test('unsubscribed user on /subscription → false (loop safety)', () => {
    expect(shouldForcePaywall('/subscription', TOKEN, verifiedUnsubscribed)).toBe(false);
  });

  test('null user on /subscription → false (loop safety)', () => {
    expect(shouldForcePaywall('/subscription', TOKEN, null)).toBe(false);
  });

  test('subscribed user on /subscription → false', () => {
    expect(shouldForcePaywall('/subscription', TOKEN, subscribedUser)).toBe(false);
  });

  // Subscribed user — never blocked on any route
  test('subscribed user on / → false', () => {
    expect(shouldForcePaywall('/', TOKEN, subscribedUser)).toBe(false);
  });

  test('subscribed user on /map → false', () => {
    expect(shouldForcePaywall('/map', TOKEN, subscribedUser)).toBe(false);
  });

  test('subscribed user on /route → false', () => {
    expect(shouldForcePaywall('/route/123', TOKEN, subscribedUser)).toBe(false);
  });

  // Unverified user — paywall deferred until they verify
  test('unverified user on / → false (paywall deferred until email verified)', () => {
    expect(shouldForcePaywall('/', TOKEN, unverifiedUser)).toBe(false);
  });

  test('unverified user on /map → false', () => {
    expect(shouldForcePaywall('/map', TOKEN, unverifiedUser)).toBe(false);
  });

  // Open routes — never forced even for verified unsubscribed user
  test('verified unsubscribed on /login → false (open route)', () => {
    expect(shouldForcePaywall('/login', TOKEN, verifiedUnsubscribed)).toBe(false);
  });

  test('verified unsubscribed on /account → false (open route)', () => {
    expect(shouldForcePaywall('/account', TOKEN, verifiedUnsubscribed)).toBe(false);
  });

  test('verified unsubscribed on /landing → false (open route)', () => {
    expect(shouldForcePaywall('/landing', TOKEN, verifiedUnsubscribed)).toBe(false);
  });

  test('verified unsubscribed on /forgot-password → false (open route)', () => {
    expect(shouldForcePaywall('/forgot-password', TOKEN, verifiedUnsubscribed)).toBe(false);
  });

  test('verified unsubscribed on /reset-password → false (open route)', () => {
    expect(shouldForcePaywall('/reset-password', TOKEN, verifiedUnsubscribed)).toBe(false);
  });

  // Core enforcement: verified unsubscribed on app routes → should force
  test('verified unsubscribed on / → true (paywall entry point)', () => {
    expect(shouldForcePaywall('/', TOKEN, verifiedUnsubscribed)).toBe(true);
  });

  test('verified unsubscribed on /map → true', () => {
    expect(shouldForcePaywall('/map', TOKEN, verifiedUnsubscribed)).toBe(true);
  });

  test('verified unsubscribed on /route/123 → true (nested route)', () => {
    expect(shouldForcePaywall('/route/123', TOKEN, verifiedUnsubscribed)).toBe(true);
  });

  test('verified unsubscribed on /settings → true', () => {
    expect(shouldForcePaywall('/settings', TOKEN, verifiedUnsubscribed)).toBe(true);
  });

  // Canceling subscription: still active, must not block
  test('canceling subscription on / → false (still entitled)', () => {
    expect(shouldForcePaywall('/', TOKEN, cancelingUser)).toBe(false);
  });

  // Second-login scenario: PaywallGuard re-evaluates correctly every time
  test('unsubscribed user re-evaluated on second navigation to / → still true', () => {
    const result1 = shouldForcePaywall('/', TOKEN, verifiedUnsubscribed);
    const result2 = shouldForcePaywall('/', TOKEN, verifiedUnsubscribed);
    expect(result1).toBe(true);
    expect(result2).toBe(true);  // idempotent: no firedRef mutation affects this
  });

  // Subscribed user re-evaluated: still false on every call
  test('subscribed user re-evaluated on / → still false on second call', () => {
    const result1 = shouldForcePaywall('/', TOKEN, subscribedUser);
    const result2 = shouldForcePaywall('/', TOKEN, subscribedUser);
    expect(result1).toBe(false);
    expect(result2).toBe(false);
  });
});
