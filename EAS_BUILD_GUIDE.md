# EAS Build Guide for Google Play

This guide walks you through building an Android App Bundle (AAB) for Google Play Store submission.

---

## Prerequisites

1. **Expo Account**: Create one at https://expo.dev/
2. **EAS CLI**: Install globally
   ```bash
   npm install -g eas-cli
   ```
3. **Login to EAS**:
   ```bash
   eas login
   ```

---

## One-Time Setup

### 1. Initialize EAS Project

```bash
cd frontend
eas init
```

This will:
- Create/update `eas.json`
- Link your project to Expo's build service
- Generate a project ID

### 2. Update app.json

Ensure these values are set in `app.json`:

```json
{
  "expo": {
    "name": "Routecast",
    "slug": "routecast",
    "version": "1.0.0",
    "android": {
      "package": "com.routecast.app",
      "versionCode": 1,
      "adaptiveIcon": {
        "foregroundImage": "./assets/images/adaptive-icon.png",
        "backgroundColor": "#18181b"
      }
    },
    "extra": {
      "eas": {
        "projectId": "your-project-id-from-eas-init"
      }
    }
  }
}
```

**Important for Google Play:**
- `android.package` must be unique and never change
- `android.versionCode` must increment with each release
- `version` is the user-facing version string

### 3. Configure eas.json

Your `eas.json` should look like this:

```json
{
  "cli": {
    "version": ">= 5.0.0"
  },
  "build": {
    "development": {
      "developmentClient": true,
      "distribution": "internal"
    },
    "preview": {
      "distribution": "internal",
      "android": {
        "buildType": "apk"
      }
    },
    "production": {
      "android": {
        "buildType": "app-bundle"
      },
      "env": {
        "EXPO_PUBLIC_BACKEND_URL": "https://routecast-backend.onrender.com"
      }
    }
  },
  "submit": {
    "production": {
      "android": {
        "serviceAccountKeyPath": "./google-service-account.json",
        "track": "internal"
      }
    }
  }
}
```

---

## Building the AAB

### Production Build (for Google Play)

```bash
cd frontend
eas build -p android --profile production
```

This will:
1. Upload your code to Expo's build servers
2. Build an Android App Bundle (`.aab`)
3. Provide a download link when complete

**Build time**: Usually 10-20 minutes

### Preview Build (for testing)

```bash
eas build -p android --profile preview
```

This creates an APK you can install directly on devices for testing.

---

## Downloading the AAB

After the build completes:

1. EAS CLI will print a download URL
2. Or visit https://expo.dev/ → Your Project → Builds
3. Download the `.aab` file

---

## Uploading to Google Play Console

### Manual Upload

1. Go to https://play.google.com/console/
2. Select your app (or create new)
3. Go to **Release** → **Production** (or Testing track)
4. Click **Create new release**
5. Upload the `.aab` file
6. Fill in release notes
7. Review and roll out

### Automated Upload (Optional)

Set up EAS Submit for automated uploads:

1. Create a Google Play Service Account:
   - Go to Google Play Console → Setup → API access
   - Create a service account with "Release manager" permissions
   - Download the JSON key file

2. Add the key to your project:
   ```bash
   # Save as ./google-service-account.json (gitignored)
   ```

3. Submit to Google Play:
   ```bash
   eas submit -p android --profile production
   ```

---

## Version Management

Before each new release:

1. Update `version` in `app.json` (e.g., "1.0.0" → "1.0.1")
2. Increment `android.versionCode` (e.g., 1 → 2)
3. Commit changes
4. Run `eas build -p android --profile production`

---

## Troubleshooting

### "Invalid package name"
- Ensure `android.package` follows format: `com.yourcompany.appname`
- Package name cannot start with a number
- Use only lowercase letters, numbers, and dots

### Build fails with missing assets
- Ensure all referenced images exist in `./assets/`
- Check paths in `app.json` are correct

### "Version code already used"
- Increment `android.versionCode` in `app.json`
- Each upload to Google Play needs a higher version code

### EAS build hangs
- Check Expo status: https://status.expo.dev/
- Try `eas build --clear-cache -p android --profile production`

---

## Quick Reference

| Command | Purpose |
|---------|--------|
| `eas login` | Login to Expo account |
| `eas init` | Initialize EAS project |
| `eas build -p android --profile production` | Build AAB for Play Store |
| `eas build -p android --profile preview` | Build APK for testing |
| `eas submit -p android` | Upload to Google Play |
| `eas build:list` | List recent builds |

---

## Checklist Before Submission

- [ ] Backend deployed to Render and healthy
- [ ] `EXPO_PUBLIC_BACKEND_URL` set correctly in `eas.json`
- [ ] `android.package` is final (can't change after first upload)
- [ ] `android.versionCode` incremented from last release
- [ ] App icons present in `./assets/images/`
- [ ] Tested preview build on real device
- [ ] Privacy policy URL ready (required by Google)
