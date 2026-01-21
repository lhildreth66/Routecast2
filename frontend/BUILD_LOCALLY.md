# Build AAB Locally (Without EAS)

## Prerequisites
1. Android Studio installed on your desktop
2. Java JDK 17 or higher
3. Android SDK (install via Android Studio)

## Steps

### 1. Generate Android Project
```bash
cd frontend
npx expo prebuild --platform android --clean
```

### 2. Configure Signing (one-time setup)
Create `frontend/android/gradle.properties` and add:
```
MYAPP_UPLOAD_STORE_FILE=../keystores/upload-keystore.jks
MYAPP_UPLOAD_KEY_ALIAS=upload
MYAPP_UPLOAD_STORE_PASSWORD=your_keystore_password
MYAPP_UPLOAD_KEY_PASSWORD=your_key_password
```

### 3. Build the AAB
```bash
cd frontend/android
./gradlew bundleRelease
```

### 4. Find Your AAB
The file will be at:
```
frontend/android/app/build/outputs/bundle/release/app-release.aab
```

## Copy Files to Your Desktop

### Option A: Download entire project
Download this whole repository as a ZIP from GitHub

### Option B: Use these commands (from desktop terminal)
```bash
# If you have git access to the codespace
git clone <your-repo-url>
cd Routecast2/frontend
npm install
npx expo prebuild --platform android --clean
cd android
./gradlew bundleRelease
```

## Notes
- Make sure your keystore file is in `frontend/keystores/`
- Version numbers are in `frontend/app.json`
- Each build must have a higher versionCode than the last
