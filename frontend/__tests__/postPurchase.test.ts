/**
 * Tests for runPostPurchaseFlow — the post-Google-Play-purchase orchestrator.
 *
 * Covers:
 *  - Receipt present → verifyWithReceipt, not verifyWithRestore
 *  - Receipt absent (null) → verifyWithRestore, not verifyWithReceipt
 *  - Successful flow: refreshUser called, navigate called, error null
 *  - verifyWithReceipt throws → error returned, refreshUser/navigate NOT called
 *  - verifyWithRestore throws → error returned, refreshUser/navigate NOT called
 *  - refreshUser throws → navigate is still called (non-fatal), error null
 *  - Error message extraction: Error instance, plain object, unknown
 */

import {
  runPostPurchaseFlow,
  PurchaseVerificationPayload,
  PostPurchaseHandlers,
} from '../app/utils/postPurchaseFlow';

const DUMMY_RECEIPT: PurchaseVerificationPayload = {
  purchaseToken: 'gp_token_abc123xyz',
  productId: 'routecast_vs1',
  packageName: 'com.routecast.app',
};

function makeHandlers(overrides: Partial<PostPurchaseHandlers> = {}): {
  mocks: {
    verifyWithReceipt: jest.Mock;
    verifyWithRestore: jest.Mock;
    refreshUser: jest.Mock;
    navigate: jest.Mock;
  };
  handlers: PostPurchaseHandlers;
} {
  const verifyWithReceipt = jest.fn().mockResolvedValue(undefined);
  const verifyWithRestore = jest.fn().mockResolvedValue(undefined);
  const refreshUser = jest.fn().mockResolvedValue(undefined);
  const navigate = jest.fn();

  const handlers: PostPurchaseHandlers = {
    verifyWithReceipt,
    verifyWithRestore,
    refreshUser,
    navigate,
    ...overrides,
  };

  return { mocks: { verifyWithReceipt, verifyWithRestore, refreshUser, navigate }, handlers };
}

// ─── Receipt present ──────────────────────────────────────────────────────────

describe('runPostPurchaseFlow — receipt present', () => {
  it('calls verifyWithReceipt with the receipt payload', async () => {
    const { mocks, handlers } = makeHandlers();
    await runPostPurchaseFlow(DUMMY_RECEIPT, handlers);
    expect(mocks.verifyWithReceipt).toHaveBeenCalledWith(DUMMY_RECEIPT);
  });

  it('does NOT call verifyWithRestore when receipt is provided', async () => {
    const { mocks, handlers } = makeHandlers();
    await runPostPurchaseFlow(DUMMY_RECEIPT, handlers);
    expect(mocks.verifyWithRestore).not.toHaveBeenCalled();
  });

  it('calls refreshUser after successful verification', async () => {
    const { mocks, handlers } = makeHandlers();
    await runPostPurchaseFlow(DUMMY_RECEIPT, handlers);
    expect(mocks.refreshUser).toHaveBeenCalledTimes(1);
  });

  it('calls navigate after successful verification', async () => {
    const { mocks, handlers } = makeHandlers();
    await runPostPurchaseFlow(DUMMY_RECEIPT, handlers);
    expect(mocks.navigate).toHaveBeenCalledTimes(1);
  });

  it('returns { error: null } on success', async () => {
    const { handlers } = makeHandlers();
    const result = await runPostPurchaseFlow(DUMMY_RECEIPT, handlers);
    expect(result.error).toBeNull();
  });
});

// ─── Receipt absent (null) ───────────────────────────────────────────────────

describe('runPostPurchaseFlow — receipt absent (null)', () => {
  it('calls verifyWithRestore when receipt is null', async () => {
    const { mocks, handlers } = makeHandlers();
    await runPostPurchaseFlow(null, handlers);
    expect(mocks.verifyWithRestore).toHaveBeenCalledTimes(1);
  });

  it('does NOT call verifyWithReceipt when receipt is null', async () => {
    const { mocks, handlers } = makeHandlers();
    await runPostPurchaseFlow(null, handlers);
    expect(mocks.verifyWithReceipt).not.toHaveBeenCalled();
  });

  it('calls refreshUser after successful restore-verification', async () => {
    const { mocks, handlers } = makeHandlers();
    await runPostPurchaseFlow(null, handlers);
    expect(mocks.refreshUser).toHaveBeenCalledTimes(1);
  });

  it('calls navigate after successful restore-verification', async () => {
    const { mocks, handlers } = makeHandlers();
    await runPostPurchaseFlow(null, handlers);
    expect(mocks.navigate).toHaveBeenCalledTimes(1);
  });

  it('returns { error: null } on success', async () => {
    const { handlers } = makeHandlers();
    const result = await runPostPurchaseFlow(null, handlers);
    expect(result.error).toBeNull();
  });
});

// ─── Verification failure ─────────────────────────────────────────────────────

describe('runPostPurchaseFlow — verification failure', () => {
  it('returns the error message when verifyWithReceipt throws an Error', async () => {
    const { handlers } = makeHandlers({
      verifyWithReceipt: jest.fn().mockRejectedValue(new Error('Purchase token expired')),
    });
    const result = await runPostPurchaseFlow(DUMMY_RECEIPT, handlers);
    expect(result.error).toBe('Purchase token expired');
  });

  it('returns the error message when verifyWithRestore throws an Error', async () => {
    const { handlers } = makeHandlers({
      verifyWithRestore: jest.fn().mockRejectedValue(new Error('No active purchases found')),
    });
    const result = await runPostPurchaseFlow(null, handlers);
    expect(result.error).toBe('No active purchases found');
  });

  it('does NOT call refreshUser when verification throws', async () => {
    const { mocks, handlers } = makeHandlers({
      verifyWithReceipt: jest.fn().mockRejectedValue(new Error('Backend 502')),
    });
    await runPostPurchaseFlow(DUMMY_RECEIPT, handlers);
    expect(mocks.refreshUser).not.toHaveBeenCalled();
  });

  it('does NOT call navigate when verification throws', async () => {
    const { mocks, handlers } = makeHandlers({
      verifyWithReceipt: jest.fn().mockRejectedValue(new Error('Backend 502')),
    });
    await runPostPurchaseFlow(DUMMY_RECEIPT, handlers);
    expect(mocks.navigate).not.toHaveBeenCalled();
  });

  it('extracts .message from a plain object error', async () => {
    const { handlers } = makeHandlers({
      verifyWithReceipt: jest.fn().mockRejectedValue({ message: 'Google Play verification unavailable' }),
    });
    const result = await runPostPurchaseFlow(DUMMY_RECEIPT, handlers);
    expect(result.error).toBe('Google Play verification unavailable');
  });

  it('uses fallback message for unknown thrown value', async () => {
    const { handlers } = makeHandlers({
      verifyWithReceipt: jest.fn().mockRejectedValue('string error'),
    });
    const result = await runPostPurchaseFlow(DUMMY_RECEIPT, handlers);
    expect(result.error).toBe('Unable to verify purchase. Tap "Restore Purchases" to try again.');
  });
});

// ─── refreshUser non-fatal ───────────────────────────────────────────────────

describe('runPostPurchaseFlow — refreshUser non-fatal', () => {
  it('still calls navigate when refreshUser throws', async () => {
    const { mocks, handlers } = makeHandlers({
      refreshUser: jest.fn().mockRejectedValue(new Error('network timeout')),
    });
    await runPostPurchaseFlow(DUMMY_RECEIPT, handlers);
    expect(mocks.navigate).toHaveBeenCalledTimes(1);
  });

  it('returns { error: null } when refreshUser throws (verification succeeded)', async () => {
    const { handlers } = makeHandlers({
      refreshUser: jest.fn().mockRejectedValue(new Error('network timeout')),
    });
    const result = await runPostPurchaseFlow(DUMMY_RECEIPT, handlers);
    expect(result.error).toBeNull();
  });
});

// ─── Call order ──────────────────────────────────────────────────────────────

describe('runPostPurchaseFlow — call order', () => {
  it('verifyWithReceipt completes before refreshUser is called', async () => {
    const callOrder: string[] = [];
    const { handlers } = makeHandlers({
      verifyWithReceipt: jest.fn().mockImplementation(async () => { callOrder.push('verify'); }),
      refreshUser: jest.fn().mockImplementation(async () => { callOrder.push('refresh'); }),
      navigate: jest.fn().mockImplementation(() => { callOrder.push('navigate'); }),
    });
    await runPostPurchaseFlow(DUMMY_RECEIPT, handlers);
    expect(callOrder).toEqual(['verify', 'refresh', 'navigate']);
  });

  it('verifyWithRestore completes before refreshUser is called', async () => {
    const callOrder: string[] = [];
    const { handlers } = makeHandlers({
      verifyWithRestore: jest.fn().mockImplementation(async () => { callOrder.push('restore'); }),
      refreshUser: jest.fn().mockImplementation(async () => { callOrder.push('refresh'); }),
      navigate: jest.fn().mockImplementation(() => { callOrder.push('navigate'); }),
    });
    await runPostPurchaseFlow(null, handlers);
    expect(callOrder).toEqual(['restore', 'refresh', 'navigate']);
  });
});
