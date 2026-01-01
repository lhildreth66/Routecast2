# Routecast - Production Build Guide

## App Information

| Field | Value |
|-------|-------|
| App Name | Routecast |
| Package Name | com.routecast.app |
| Version | 1.0.0 |
| Version Code | 1 |
| Min Android SDK | 21 (Android 5.0) |

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Mobile App    │────▶│  Backend API    │────▶│  External APIs  │
│  (Expo/React    │     │   (FastAPI)     │     │                 │
│   Native)       │     │                 │     │  - Mapbox       │
└─────────────────┘     └─────────────────┘     │  - NOAA Weather │
                                                └─────────────────┘
```

## APIs Used

| API | Purpose | Key Required | Key Location |
|-----|---------|--------------|---------------|
| Mapbox Directions | Route calculation | Yes | Backend .env |
| Mapbox Geocoding | Address lookup | Yes | Backend .env |
| NOAA/NWS | Weather data | No (free) | N/A |
| Emergent LLM | AI summaries | Yes (optional) | Backend .env |

**Important:** The mobile app contains NO API keys. All sensitive operations go through your backend.

## Permissions

### Android Permissions

| Permission | Reason |
|------------|--------|
| ACCESS_FINE_LOCATION | GPS for route planning |
| ACCESS_COARSE_LOCATION | Approximate location |
| ACCESS_BACKGROUND_LOCATION | Weather updates during trip |
| POST_NOTIFICATIONS | Weather alerts |
| INTERNET | API communication |
| ACCESS_NETWORK_STATE | Check connectivity |
| VIBRATE | Notification feedback |
| WAKE_LOCK | Background processing |
| SCHEDULE_EXACT_ALARM | Scheduled alerts |
| RECEIVE_BOOT_COMPLETED | Restart services after reboot |

## Build Steps

### Prerequisites

1. Node.js 18+ installed
2. EAS CLI installed: `npm install -g eas-cli`
3. Expo account created at expo.dev
4. Google Play Console account

### Step 1: Clone and Setup

```bash
git clone <your-repo-url>
cd routecast/frontend
npm install
```

### Step 2: Configure EAS

```bash
# Login to Expo
eas login

# Initialize EAS (creates project on expo.dev)
eas build:configure
```

### Step 3: Update app.json

Replace `your-project-id-here` with your actual EAS project ID from expo.dev.

### Step 4: Set Production Backend URL

Edit `eas.json` and set your production backend URL:

```json
"production": {
  "env": {
    "EXPO_PUBLIC_BACKEND_URL": "https://your-production-backend.com"
  }
}
```

### Step 5: Build for Google Play

```bash
# Build Android App Bundle (.aab)
eas build --platform android --profile production
```

### Step 6: Download and Upload

1. Download .aab from expo.dev dashboard
2. Go to Google Play Console
3. Create new app or select existing
4. Upload .aab to Production track
5. Complete store listing
6. Submit for review

## Google Play App Signing

EAS automatically handles app signing when you use `credentialsSource: "remote"`.

For Google Play App Signing:
1. Build with EAS (creates upload key)
2. In Play Console, enable Google Play App Signing
3. Upload your first .aab
4. Google generates and manages the release signing key

## Environment Variables

### For Mobile App (set in eas.json or EAS Secrets)

```
EXPO_PUBLIC_BACKEND_URL=https://your-production-backend.com
```

### For Backend Server (set on your server)

```
MONGO_URL=mongodb://your-production-mongodb:27017
DB_NAME=routecast_production
MAPBOX_ACCESS_TOKEN=pk.eyJ1...
EMERGENT_LLM_KEY=sk-emergent-... (optional)
```

## NOAA API Configuration

The backend includes the required User-Agent header:

```python
NOAA_HEADERS = {
    'User-Agent': 'HawkeyeDevWeather/1.0 (lisaannehildreth@gmail.com)',
    'Accept': 'application/geo+json'
}
```

## Features Included

- ✅ Route weather forecasts
- ✅ Multi-stop routes
- ✅ Departure time selection
- ✅ Save favorite routes
- ✅ Share weather reports
- ✅ Voice weather summary
- ✅ Packing suggestions
- ✅ Weather timeline
- ✅ Push notifications for alerts
- ✅ Offline route caching
- ✅ Location names with reverse geocoding

## Support

For issues with:
- EAS Build: https://docs.expo.dev/build/introduction/
- Google Play: https://support.google.com/googleplay/android-developer/
- Expo: https://forums.expo.dev/
