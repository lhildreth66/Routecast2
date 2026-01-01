# EAS Secrets Configuration for Routecast

## Overview

This document lists all secrets that need to be configured in EAS for production builds.

## API Keys Used

### Backend Secrets (Server-side only)

These are used by your **backend server**, NOT the mobile app:

| Secret | Description | Where Used |
|--------|-------------|------------|
| `MAPBOX_ACCESS_TOKEN` | Mapbox API key for routing and geocoding | Backend only |
| `EMERGENT_LLM_KEY` | AI summary generation (optional) | Backend only |
| `MONGO_URL` | MongoDB connection string | Backend only |
| `DB_NAME` | Database name | Backend only |

**Note:** The mobile app does NOT contain any API keys. All API calls go through your backend server.

### Frontend Environment Variables

| Variable | Description | Set In |
|----------|-------------|--------|
| `EXPO_PUBLIC_BACKEND_URL` | Your production backend URL | eas.json or EAS Secrets |

## Setting EAS Secrets

Run these commands after `eas login`:

```bash
# Set your production backend URL
eas secret:create EXPO_PUBLIC_BACKEND_URL --value "https://your-production-api.com" --scope project
```

## Google Maps vs Mapbox

**This app uses Mapbox ONLY** - No Google Maps API key is required.

- Routing: Mapbox Directions API
- Geocoding: Mapbox Geocoding API  
- Reverse Geocoding: Mapbox Geocoding API
- Map Display: Leaflet with CartoDB tiles (free, no key needed)

## NOAA Weather API

The NOAA/NWS Weather API is **free and requires no API key**.

Requests include the header:
```
User-Agent: HawkeyeDevWeather/1.0 (lisaannehildreth@gmail.com)
```

## Production Checklist

- [ ] Deploy backend to production server
- [ ] Set `EXPO_PUBLIC_BACKEND_URL` to production backend URL
- [ ] Configure Google Play App Signing in Play Console
- [ ] Run `eas build --platform android --profile production`
- [ ] Download .aab from EAS dashboard
- [ ] Upload to Google Play Console

## Build Commands

```bash
# Login to EAS
eas login

# Configure EAS (first time only)
eas build:configure

# Build Android App Bundle for Google Play
eas build --platform android --profile production

# Build APK for testing
eas build --platform android --profile preview
```
