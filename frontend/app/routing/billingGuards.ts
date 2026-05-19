export type GuardUser = {
  email_verified?: boolean;
  is_premium?: boolean;
  subscription_status?: string | null;
  subscription_provider?: string | null;
  subscription_expiration?: string | null;
} | null;

export const ACTIVE_SUBSCRIPTION_STATUSES = new Set(['trialing', 'active', 'canceling']);

export const PAYWALL_OPEN_ROUTES = new Set([
  '/login', '/signup', '/verify-email', '/subscription',
  '/landing', '/terms', '/privacy', '/contact',
  '/forgot-password', '/reset-password',
  '/welcome',
  '/account',
]);

const MOBILE_APP_SCHEME = 'routecast2';

function topSegment(pathname: string): string {
  return '/' + (pathname.split('/').filter(Boolean)[0] ?? '');
}

// Admin-only entitlement bypass.
// ALL four conditions must be true. Any other provider value — including null,
// undefined, "google_play", "stripe", "apple" — fails at the first check.
function isAdminEntitled(user: NonNullable<GuardUser>): boolean {
  if (user.subscription_provider !== 'admin') return false;   // strict equality
  if (!user.is_premium) return false;
  if ((user.subscription_status ?? '').toLowerCase() !== 'active') return false;
  if (!user.subscription_expiration) return false;            // must exist
  return new Date(user.subscription_expiration) > new Date(); // must be future
}

export function hasActiveSubscription(user: GuardUser): boolean {
  if (!user) return false;
  if (isAdminEntitled(user)) return true;
  return Boolean(
    user.email_verified &&
    user.is_premium &&
    ACTIVE_SUBSCRIPTION_STATUSES.has((user.subscription_status || '').toLowerCase())
  );
}

export function shouldForcePaywall(pathname: string, accessToken: string | null, user: GuardUser): boolean {
  const seg = topSegment(pathname);

  if (!accessToken) return false;

  if (!user) {
    return pathname !== '/subscription' && seg !== '/subscription';
  }

  if (hasActiveSubscription(user)) return false;
  if (!user.email_verified) return false;

  if (PAYWALL_OPEN_ROUTES.has(pathname) || PAYWALL_OPEN_ROUTES.has(seg)) {
    return false;
  }

  return true;
}

/**
 * Routes that are allowed on the web build.
 * routecastweather.com is informational/verification only — no login, no app access.
 * Everything else redirects to /landing on web.
 */
export const WEB_ALLOWED_ROUTES = new Set([
  '/landing', '/faq', '/verify-email', '/terms', '/privacy', '/contact', '/welcome',
]);

export function isWebAllowed(pathname: string): boolean {
  const seg = topSegment(pathname);
  return WEB_ALLOWED_ROUTES.has(pathname) || WEB_ALLOWED_ROUTES.has(seg);
}

export function verifySuccessHandoffUrl(email?: string): string {
  const encoded = email ? encodeURIComponent(email) : '';
  return `${MOBILE_APP_SCHEME}://login?verified=1${encoded ? `&email=${encoded}` : ''}`;
}

export function verifySuccessRoute({
  isWeb,
  email,
}: {
  isWeb: boolean;
  email?: string;
}): string {
  if (isWeb) {
    return verifySuccessHandoffUrl(email);
  }
  // Native: take the user directly to the subscription screen so they can
  // start a Google Play trial/subscription immediately after verification.
  // They are not yet logged in at this point — the subscription screen handles
  // the unauthenticated case (saves the pending purchase and routes to /login).
  return '/subscription';
}
