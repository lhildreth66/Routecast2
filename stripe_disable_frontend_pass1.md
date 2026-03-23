Stripe Disable Pass 1 — Frontend (Google Play submission)
==========================================================

What changed (commented, not deleted)
------------------------------------
- frontend/app/landing.tsx — noted CTA stripe disable comment; pricing disclaimer, FAQ, and footer Stripe mentions commented with headers.
- frontend/app/login.tsx — Stripe trial-start banner commented.
- frontend/app/account.tsx — Stripe billing-portal handler and Manage Subscription button commented.
- frontend/app/welcome.tsx — Stripe activation (session_id POST) effect commented.
- frontend/app/verify-email.tsx — Stripe checkout redirect effect commented.
- frontend/app/_layout.tsx — paywall guard effect (subscription redirect) commented.
- frontend/app/subscribe/success.tsx — checkout-session verification effect commented.
- frontend/app/subscription/success.tsx — post-Stripe refresh/redirect effect commented.
- frontend/contexts/AuthContext.tsx — loginWithTokens (Stripe checkout login) commented; stubbed no-op replacement.

Verification snippets (first 3 lines of each commented block)
------------------------------------------------------------
- frontend/app/landing.tsx (CTA note)
  // STRIPE DISABLED - Google Play submission - do not delete
  // All pricing CTAs route to /signup - Stripe checkout handled post-signup

- frontend/app/landing.tsx (pricing disclaimer)
  {/* // STRIPE DISABLED - Google Play submission - do not delete */}
  {/*
  <Text style={styles.pricingDisclaimer}>

- frontend/app/landing.tsx (FAQ section)
  {/* // STRIPE DISABLED - Google Play submission - do not delete */}
  {/* FAQ Section */}
  {/*

- frontend/app/landing.tsx (footer Stripe)
  {/* // STRIPE DISABLED - Google Play submission - do not delete */}
  {/*
  <View style={styles.footerStripe}>

- frontend/app/login.tsx (trial-start banner)
  {/* // STRIPE DISABLED - Google Play submission - do not delete */}
  {/* Trial-started banner (Stripe success redirect) */}
  {/*

- frontend/app/account.tsx (Stripe portal handler)
  // STRIPE DISABLED - Google Play submission - do not delete
  /*
  const handleManageSubscription = async () => {

- frontend/app/account.tsx (Manage Subscription button)
  {/* // STRIPE DISABLED - Google Play submission - do not delete */}
  {/* Manage Subscription - only for premium Stripe users */}
  {**

- frontend/app/welcome.tsx (Stripe activation effect)
  // STRIPE DISABLED - Google Play submission - do not delete
  /*
  useEffect(() => {

- frontend/app/verify-email.tsx (checkout redirect)
  // STRIPE DISABLED - Google Play submission - do not delete
  // ── MODE 1: Token present → redirect to backend for Stripe checkout ────
  /*

- frontend/app/_layout.tsx (paywall guard effect)
  // STRIPE DISABLED - Google Play submission - do not delete
  /*
  useEffect(() => {

- frontend/app/subscribe/success.tsx (checkout verification)
  // STRIPE DISABLED - Google Play submission - do not delete
  /*
  useEffect(() => {

- frontend/app/subscription/success.tsx (post-Stripe refresh)
  // STRIPE DISABLED - Google Play submission - do not delete
  /*
  useEffect(() => {

- frontend/contexts/AuthContext.tsx (checkout login flow)
  // STRIPE DISABLED - Google Play submission - do not delete
  // ── loginWithTokens — used by /welcome after Stripe checkout ──────────────
  /*

Notes
-----
- All changes are comments only; original code preserved inside comment blocks; AuthContext re-exports a no-op loginWithTokens stub to satisfy callers.
- No commits made.
