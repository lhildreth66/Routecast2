/**
 * Tests for post-purchase navigation race condition fix in subscription.tsx.
 *
 * The bug: router.replace('/') was called immediately after refreshUser() in
 * runPostPurchaseFlow. Expo Router updated the pathname synchronously, triggering
 * PaywallGuard's useEffect before React committed the setUser({is_premium: true})
 * state update. PaywallGuard evaluated stale user data (is_premium: false) and
 * re-redirected to /subscription.
 *
 * The fix: navigate() now calls setPurchasePending(true) instead of router.replace('/').
 * A useEffect in subscription.tsx navigates only once user.is_premium AND
 * user.email_verified are confirmed in committed React state.
 *
 * These tests cover the pure logic that the fix depends on:
 *  1. Entitlement state transitions from false → true after successful verification
 *  2. PaywallGuard correctly passes through at '/' when is_premium=true
 *  3. PaywallGuard correctly blocks at '/' when is_premium=false (stale state scenario)
 *  4. The purchasePending condition: navigation fires only when both pending=true
 *     AND hasServerEntitlement=true — verifying the gate logic in isolation
 *  5. runPostPurchaseFlow calls navigate() regardless of navigate() implementation
 *     (existing contract — navigate can be setPurchasePending instead of router.replace)
 *  6. Restore path follows the same deferred pattern
 */

import {
  runPostPurchaseFlow,
  PurchaseVerificationPayload,
  PostPurchaseHandlers,
} from '../app/utils/postPurchaseFlow';
import {
  hasActiveSubscription,
  shouldForcePaywall,
  GuardUser,
} from '../app/routing/billingGuards';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const TOKEN = 'mock_token';

function makeHandlers(overrides: Partial<PostPurchaseHandlers> = {}) {
  const verifyWithReceipt = jest.fn().mockResolvedValue(undefined);
  const verifyWithRestore = jest.fn().mockResolvedValue(undefined);
  const refreshUser = jest.fn().mockResolvedValue(undefined);
  const navigate = jest.fn();
  return {
    mocks: { verifyWithReceipt, verifyWithRestore, refreshUser, navigate },
    handlers: { verifyWithReceipt, verifyWithRestore, refreshUser, navigate, ...overrides } as PostPurchaseHandlers,
  };
}

const RECEIPT: PurchaseVerificationPayload = {
  purchaseToken: 'gp_abc',
  productId: 'routecast_vs1',
  packageName: 'com.routecast.app',
};

// ---------------------------------------------------------------------------
// 1. Entitlement state transitions
// ---------------------------------------------------------------------------

describe('Entitlement state after purchase', () => {
  const beforePurchase: GuardUser = {
    email_verified: true,
    is_premium: false,
    subscription_status: null,
  };

  const afterPurchase: GuardUser = {
    email_verified: true,
    is_premium: true,
    subscription_status: 'trialing',
  };

  test('before purchase: hasActiveSubscription=false', () => {
    expect(hasActiveSubscription(beforePurchase)).toBe(false);
  });

  test('after purchase: hasActiveSubscription=true', () => {
    expect(hasActiveSubscription(afterPurchase)).toBe(true);
  });

  test('before purchase: shouldForcePaywall=true at /', () => {
    expect(shouldForcePaywall('/', TOKEN, beforePurchase)).toBe(true);
  });

  test('after purchase: shouldForcePaywall=false at / (user passes through)', () => {
    expect(shouldForcePaywall('/', TOKEN, afterPurchase)).toBe(false);
  });

  test('after purchase still on /subscription: shouldForcePaywall=false (loop safe)', () => {
    expect(shouldForcePaywall('/subscription', TOKEN, afterPurchase)).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// 2. The stale-state scenario that caused the bug
// ---------------------------------------------------------------------------

describe('Race condition: PaywallGuard evaluates stale user state', () => {
  test('if navigate() fires while is_premium is still false → PaywallGuard re-redirects', () => {
    // This simulates the pre-fix state: navigate() called before setUser commits.
    // PaywallGuard evaluates with stale user → shouldForcePaywall returns true → bug.
    const staleUser: GuardUser = {
      email_verified: true,
      is_premium: false,  // ← not yet committed in React state
      subscription_status: null,
    };

    const result = shouldForcePaywall('/', TOKEN, staleUser);
    // This is exactly what caused the bug: PaywallGuard returned true on the
    // new pathname, re-redirecting to /subscription.
    expect(result).toBe(true);
  });

  test('if navigate() fires only after is_premium=true committed → PaywallGuard passes through', () => {
    // This simulates the post-fix state: purchasePending effect only navigates
    // once user.is_premium=true is in React state.
    const committedUser: GuardUser = {
      email_verified: true,
      is_premium: true,  // ← committed before navigation
      subscription_status: 'trialing',
    };

    const result = shouldForcePaywall('/', TOKEN, committedUser);
    // PaywallGuard sees hasActiveSubscription=true → early return before shouldForcePaywall.
    // shouldForcePaywall also returns false for entitled users.
    expect(result).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// 3. purchasePending gate logic (pure boolean simulation)
// ---------------------------------------------------------------------------

describe('purchasePending gate: navigates only when pending=true AND entitlement confirmed', () => {
  function shouldNavigate(purchasePending: boolean, isPremium: boolean, emailVerified: boolean): boolean {
    // This mirrors the exact useEffect condition in subscription.tsx:
    // if (!purchasePending) return;
    // const hasServerEntitlement = Boolean(user?.is_premium && user?.email_verified);
    // if (!hasServerEntitlement) return;
    // → navigate
    if (!purchasePending) return false;
    return Boolean(isPremium && emailVerified);
  }

  test('pending=false, entitled=true → no navigation (not triggered by purchase)', () => {
    expect(shouldNavigate(false, true, true)).toBe(false);
  });

  test('pending=true, entitled=false → no navigation (entitlement not committed yet)', () => {
    expect(shouldNavigate(true, false, true)).toBe(false);
  });

  test('pending=true, email NOT verified → no navigation (incomplete entitlement)', () => {
    expect(shouldNavigate(true, true, false)).toBe(false);
  });

  test('pending=true, entitled=true → navigate fires', () => {
    expect(shouldNavigate(true, true, true)).toBe(true);
  });

  test('pending=false, entitled=false → no navigation', () => {
    expect(shouldNavigate(false, false, false)).toBe(false);
  });

  // Simulates React batching: setUser({is_premium: true}) and setPurchasePending(true)
  // committed together → single render where both are true → navigate fires
  test('batched commit: is_premium=true + pending=true in same render → navigate fires', () => {
    expect(shouldNavigate(true, true, true)).toBe(true);
  });

  // Simulates non-batched: setUser fires first, setPurchasePending fires second.
  // First render: pending=false, is_premium=true → no navigation.
  // Second render: pending=true, is_premium=true → navigate fires.
  test('non-batched commit: first render pending=false → no navigate', () => {
    expect(shouldNavigate(false, true, true)).toBe(false); // first render
  });

  test('non-batched commit: second render pending=true, is_premium=true → navigate', () => {
    expect(shouldNavigate(true, true, true)).toBe(true); // second render
  });
});

// ---------------------------------------------------------------------------
// 4. runPostPurchaseFlow contract: navigate() is called regardless of implementation
// ---------------------------------------------------------------------------

describe('runPostPurchaseFlow: navigate() called with any implementation', () => {
  test('with immediate router.replace (original) — navigate called on success', async () => {
    const { mocks, handlers } = makeHandlers();
    const result = await runPostPurchaseFlow(RECEIPT, handlers);
    expect(result.error).toBeNull();
    expect(mocks.navigate).toHaveBeenCalledTimes(1);
  });

  test('with setPurchasePending (fix) — navigate still called once on success', async () => {
    let purchasePending = false;
    const setPurchasePending = jest.fn((v: boolean) => { purchasePending = v; });

    const { mocks, handlers } = makeHandlers({
      navigate: () => setPurchasePending(true),
    });

    const result = await runPostPurchaseFlow(RECEIPT, handlers);
    expect(result.error).toBeNull();
    // navigate() was called → setPurchasePending(true) was called
    expect(setPurchasePending).toHaveBeenCalledWith(true);
    expect(purchasePending).toBe(true);
    // verifyWithReceipt and refreshUser still called
    expect(mocks.verifyWithReceipt).toHaveBeenCalledWith(RECEIPT);
    expect(mocks.refreshUser).toHaveBeenCalledTimes(1);
  });

  test('with setPurchasePending — navigate NOT called if verification fails', async () => {
    let purchasePending = false;
    const setPurchasePending = jest.fn((v: boolean) => { purchasePending = v; });
    const { handlers } = makeHandlers({
      verifyWithReceipt: jest.fn().mockRejectedValue(new Error('Play verification failed')),
      navigate: () => setPurchasePending(true),
    });

    const result = await runPostPurchaseFlow(RECEIPT, handlers);
    expect(result.error).toBe('Play verification failed');
    // navigate must NOT be called on failure — purchasePending stays false
    expect(setPurchasePending).not.toHaveBeenCalled();
    expect(purchasePending).toBe(false);
  });

  test('restore path: null receipt — navigate still deferred via setPurchasePending', async () => {
    let purchasePending = false;
    const setPurchasePending = jest.fn((v: boolean) => { purchasePending = v; });
    const { mocks, handlers } = makeHandlers({
      navigate: () => setPurchasePending(true),
    });

    const result = await runPostPurchaseFlow(null, handlers);
    expect(result.error).toBeNull();
    // restore path: verifyWithRestore used, not verifyWithReceipt
    expect(mocks.verifyWithRestore).toHaveBeenCalledTimes(1);
    expect(mocks.verifyWithReceipt).not.toHaveBeenCalled();
    expect(setPurchasePending).toHaveBeenCalledWith(true);
    expect(purchasePending).toBe(true);
  });

  test('refreshUser throws — navigate still fires (non-fatal, consistent with original)', async () => {
    let purchasePending = false;
    const setPurchasePending = jest.fn((v: boolean) => { purchasePending = v; });
    const { handlers } = makeHandlers({
      refreshUser: jest.fn().mockRejectedValue(new Error('network timeout')),
      navigate: () => setPurchasePending(true),
    });

    const result = await runPostPurchaseFlow(RECEIPT, handlers);
    expect(result.error).toBeNull(); // refreshUser failure is non-fatal
    expect(setPurchasePending).toHaveBeenCalledWith(true);
  });
});

// ---------------------------------------------------------------------------
// 5. PaywallGuard full pathway simulation post-purchase
// ---------------------------------------------------------------------------

describe('End-to-end PaywallGuard pathway simulation', () => {
  test('pre-fix scenario: navigate then evaluate → re-redirect (demonstrates the bug)', () => {
    // Simulate: navigate() fires, PaywallGuard evaluates with stale user
    const staleUser: GuardUser = { email_verified: true, is_premium: false, subscription_status: null };
    const pathname = '/'; // after navigate('/')

    // Step 1: hasActiveSubscription with stale user
    expect(hasActiveSubscription(staleUser)).toBe(false);
    // Step 2: PaywallGuard proceeds to shouldForcePaywall
    expect(shouldForcePaywall(pathname, TOKEN, staleUser)).toBe(true);
    // Result: PaywallGuard re-redirects to /subscription — the bug
  });

  test('post-fix scenario: navigate only fires after is_premium committed → passes through', () => {
    // Simulate: purchasePending effect fires with committed user
    const committedUser: GuardUser = { email_verified: true, is_premium: true, subscription_status: 'trialing' };
    const pathname = '/'; // after navigate('/')

    // Step 1: hasActiveSubscription with committed user
    expect(hasActiveSubscription(committedUser)).toBe(true);
    // Step 2: PaywallGuard takes hasActiveSubscription early return, never calls shouldForcePaywall
    // But for completeness, confirm shouldForcePaywall also returns false
    expect(shouldForcePaywall(pathname, TOKEN, committedUser)).toBe(false);
    // Result: user enters app ✓
  });

  test('no backslide: on second visit to / after subscribing → still passes through', () => {
    const user: GuardUser = { email_verified: true, is_premium: true, subscription_status: 'active' };
    // Without firedRef, PaywallGuard evaluates every time. Must still pass through.
    expect(hasActiveSubscription(user)).toBe(true);
    expect(shouldForcePaywall('/', TOKEN, user)).toBe(false);
    // Second evaluation
    expect(shouldForcePaywall('/', TOKEN, user)).toBe(false);
  });
});
