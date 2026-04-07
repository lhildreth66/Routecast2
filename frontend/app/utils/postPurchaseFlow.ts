/**
 * postPurchaseFlow.ts
 *
 * Pure post-purchase orchestration — extracted for testability.
 *
 * Problem this solves:
 *   After a Google Play subscription completes, `billing.purchase()` polls
 *   `IAP.getAvailablePurchases()` for the receipt token.  On Android, the
 *   `purchaseUpdatedListener` fires first and calls `finishTransaction()`
 *   (acknowledging the purchase).  Some expo-iap versions then exclude the
 *   acknowledged purchase from `getAvailablePurchases()`, so the poll returns
 *   nothing and `billing.purchase()` returns null — even though Google Play
 *   shows "Subscribed".
 *
 * Fix:
 *   1. If a receipt is available → verify it directly.
 *   2. If no receipt (acknowledged before poll) → fall through to the restore
 *      path, which scans all active purchases via `getAvailablePurchases` at
 *      a higher level and finds the token from the completed transaction.
 *   3. After successful backend verification, refresh the user profile (best-
 *      effort — non-fatal if it fails) and navigate into the app.
 */

export interface PurchaseVerificationPayload {
  purchaseToken: string;
  productId: string;
  packageName: string;
}

export interface PostPurchaseHandlers {
  /** Call backend /subscription/verify/google with the receipt token. */
  verifyWithReceipt: (receipt: PurchaseVerificationPayload) => Promise<void>;
  /** Scan all active Google Play purchases and verify whichever matches. */
  verifyWithRestore: () => Promise<void>;
  /** Re-fetch /auth/me so is_premium reflects the new entitlement. */
  refreshUser: () => Promise<void>;
  /** Navigate the user into the app after successful entitlement. */
  navigate: () => void;
}

export interface PostPurchaseResult {
  /** Non-null when verification failed and should be shown to the user. */
  error: string | null;
}

function extractErrorMessage(err: unknown): string {
  if (err instanceof Error) return err.message;
  if (err && typeof (err as any).message === 'string') return (err as any).message;
  return 'Unable to verify purchase. Tap "Restore Purchases" to try again.';
}

/**
 * Runs the full post-purchase sequence.
 *
 * - Verification errors are fatal: returned as { error } so the caller can
 *   surface them to the user.
 * - refreshUser failure is non-fatal: NativeAuthGuard will retry on the next
 *   render cycle, so we still navigate on success.
 */
export async function runPostPurchaseFlow(
  receipt: PurchaseVerificationPayload | null,
  handlers: PostPurchaseHandlers,
): Promise<PostPurchaseResult> {
  try {
    if (receipt) {
      await handlers.verifyWithReceipt(receipt);
    } else {
      // No receipt token: purchase was acknowledged by the listener before the
      // billing hook's poll could retrieve it.  Restore path finds it instead.
      await handlers.verifyWithRestore();
    }
  } catch (err: unknown) {
    return { error: extractErrorMessage(err) };
  }

  // Backend confirmed entitlement.  Profile refresh is best-effort.
  try {
    await handlers.refreshUser();
  } catch {
    // Non-fatal — NativeAuthGuard retries refreshUser on mount.
  }

  handlers.navigate();
  return { error: null };
}
