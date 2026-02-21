# RouteCast - Product Requirements Document

## Overview
RouteCast is a React Native/Expo mobile app providing weather-smart route planning for road trips, RVers, and truck drivers. The app integrates real-time weather data (NOAA), location search (Mapbox), and point-of-interest data (Google Places API).

## Tech Stack
- **Frontend**: React Native, Expo SDK 51, TypeScript, Expo Router
- **Backend**: Python FastAPI
- **Database**: MongoDB
- **APIs**: NOAA Weather Service, Mapbox Geocoding, Google Places API
- **Payments**: Stripe (web), Apple IAP (iOS), Google Play Billing (Android)
- **Email**: SendGrid
- **Auth**: JWT (access + refresh tokens)

## Domain Structure (Production)
- `routecastweather.com` → Marketing/landing page (existing)
- `app.routecastweather.com` → Web app (login + dashboard)
- `api.routecastweather.com` → FastAPI backend

## Subscription Tiers

### Free Tier
- Basic route weather
- Limited alerts (1 route monitor)

### Premium ($9.99/month or $59.99/year)
- 7-day free trial
- Unlimited route monitoring
- Push weather alerts
- AI-powered recommendations
- Advanced trucker features
- Boondocking tools
- Priority support (yearly)

## Core Features

### Route Weather
- Enter origin and destination addresses with autocomplete
- Clear X buttons to quickly clear address inputs
- View weather conditions along entire route
- Safety score calculation based on conditions
- Weather alerts from NWS
- Turn-by-turn directions
- Voice "Listen" button for road conditions (hands-free)

### Boondockers Section
- Camp Prep Checklist (persistent)
- Free Camping Finder
- Casinos Near Me (with address search + location detect)
- Walmart Overnight Parking
- Cracker Barrel locations
- Dump Station Finder
- Last Chance Supplies (groceries)
- RV Dealerships
- Solar Forecast calculator
- Propane Usage calculator
- Water Budget Planner (Fresh/Gray/Black tanks)
- Wind Shelter recommendations
- Connectivity Check
- Campsite Suitability Index

### Truck Drivers Section
- Truck Stops and Fuel (with location detect)
- Weigh Stations
- Truck Parking (with location detect)
- Truck Repair Services (with location detect)
- Low Bridge Clearance Alerts (via Trucker Mode)
- Weight Restricted Routes info
- Bridge Height Hazards tab on route page

### Authentication System
- Email + password signup
- Email verification (SendGrid)
- Password reset
- JWT access + refresh tokens
- `/api/me` endpoint with subscription status

### Subscription System
- Stripe Subscriptions (web)
- Apple In-App Purchase (iOS) - scaffold ready
- Google Play Billing (Android) - scaffold ready
- Unified entitlements system
- 7-day free trial
- Admin controls (grant/revoke)

### User Experience
- Clear X buttons on address inputs
- Location detect button on all POI screens
- Comprehensive How To Use guide
- Push Weather Alerts (via external worker)
- Favorites and Recent routes

## API Structure

### Authentication (/api/auth/*)
- POST /signup - Register
- POST /login - Login
- POST /refresh - Refresh token
- POST /verify-email - Verify email
- POST /forgot-password - Request reset
- POST /reset-password - Reset password
- GET /me - User profile + subscription

### Subscription (/api/subscription/*)
- GET /status - Current status
- GET /plans - Available plans
- POST /start-trial - Start 7-day trial
- POST /checkout - Create Stripe checkout
- POST /verify/apple - Verify Apple receipt
- POST /verify/google - Verify Google receipt

### Admin (/api/admin/*)
- GET /users - List users
- GET /users/{id} - User details
- POST /users/{id}/grant-subscription
- POST /users/{id}/revoke-subscription
- GET /stats - Platform stats

### Webhooks (/api/webhook/*)
- POST /stripe - Stripe events
- POST /apple - Apple notifications
- POST /google - Google notifications

## Database Schema (MongoDB)

### users collection
```javascript
{
  user_id: string,
  email: string,
  name: string,
  hashed_password: string,
  email_verified: boolean,
  created_at: datetime,
  updated_at: datetime,
  subscription_status: "inactive" | "active" | "trialing" | "canceled" | "expired",
  subscription_provider: "stripe" | "apple" | "google" | "admin" | null,
  subscription_plan: "free" | "monthly" | "yearly",
  subscription_expiration: datetime | null,
  stripe_customer_id: string | null,
  stripe_subscription_id: string | null,
  apple_original_transaction_id: string | null,
  google_purchase_token: string | null,
  trial_used: boolean,
  trial_start: datetime | null,
  trial_end: datetime | null
}
```

## Environment Variables

### Backend (.env)
```
MONGO_URL=<mongodb-url>
DB_NAME=routecast
MAPBOX_ACCESS_TOKEN=<token>
GOOGLE_API_KEY=<key>
NOAA_USER_AGENT=Routecast/1.0
JWT_SECRET_KEY=<secret>
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
APP_URL=https://app.routecastweather.com
API_URL=https://api.routecastweather.com
SENDGRID_API_KEY=<key>
SENDER_EMAIL=noreply@routecastweather.com
STRIPE_API_KEY=<key>
STRIPE_WEBHOOK_SECRET=<secret>
ADMIN_API_KEY=<key>
```

## Completed Features

### Auth/Subscription Frontend UI (Feb 2025)
- Login page with email/password
- Signup page with 7-day trial promotion
- Email verification page with resend/skip options
- Forgot password page with success state
- Reset password page
- Subscription page showing plans ($9.99/mo, $59.99/yr)
- Account page with subscription status + manage link
- Account button in main app header
- AuthContext for state management

### Authentication & Subscription Backend (Dec 2025)
- Full auth system with JWT tokens
- Email verification flow
- Password reset flow
- Stripe checkout integration
- Unified entitlements system
- Admin controls for subscriptions
- Apple/Google receipt verification scaffolds

### Previous Implementation
- All Boondocker/Trucker API endpoints
- AI chat bubble removed
- Truck Services/Stops/Parking with location detect
- Water Budget with 3 tanks
- How To Use page
- Clear X buttons on inputs

## Pending Tasks

### P0 (Critical)
- ~~**Deploy backend to Render**~~ - DONE, backend live at api.routecastweather.com
- ~~**Deploy frontend to Render**~~ - DONE, frontend live at app.routecastweather.com
- ~~**Bridge Height Alerts (OSM/Overpass)**~~ - DONE, integrated into route + trucker endpoints
- ~~**Push Notification Worker**~~ - DONE, token registration + route monitors
- ~~**Weight-Restricted Roads**~~ - DONE, real OSM data integration
- ~~**Stripe Webhook for Generic Payment Links**~~ - DONE (Feb 2025), supports email-based user mapping

### P1 (High Priority)
- **Redeploy backend** - Push code to trigger Render redeploy with new Stripe webhook
- **End-to-end validation** - Signup → checkout → webhook → premium unlocked
- Fix white bar autofill bug on address fields
- Complete Apple IAP implementation
- Complete Google Play Billing implementation

### P2 (Medium Priority)
- Admin dashboard UI
- Talking button scope adjustment (road conditions only)

### P3 (Low Priority)
- Offline mode support
- Rate limiting
- Analytics integration

## Recent Changes (Feb 2025)

### Stripe Webhook Improvements
- Fixed `determine_plan()` to return `'yearly'` instead of `'annual'` to match SubscriptionPlan enum
- Fixed `handle_subscription_deleted()` to set both `plan` and `subscription_plan` to `'free'`
- Fixed `check_subscription_status()` to include `'canceling'` and `'past_due'` as premium statuses
- Email-based user lookup for generic `buy.stripe.com` payment links
- All webhook events tested: checkout.session.completed, customer.subscription.updated, customer.subscription.deleted
