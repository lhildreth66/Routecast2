# Welcome to your Expo app 👋

This is an [Expo](https://expo.dev) project created with [`create-expo-app`](https://www.npmjs.com/package/create-expo-app).

## Required environment

- `EXPO_PUBLIC_BACKEND_URL=https://routecast-backend.onrender.com`
- `EXPO_PUBLIC_MAPBOX_ACCESS_TOKEN=<your pk... token>` (do not check in; inject via EAS secrets or env)

## Dev client workflow

```bash
cd frontend
npm install
npx expo start --dev-client

To restart with cache cleared:

npx expo start -c
eas build -p android --profile development   # rebuild after updating Mapbox token
```

Watch device logs for `[health-check]` and `[mapbox] tokenPresent=true len=...` on startup. Trigger autocomplete once to surface Mapbox/backend response codes.
