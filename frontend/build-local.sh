#!/bin/bash
# Build Android APK/AAB locally without EAS charges
# This uses expo prebuild + gradle directly - NO EAS FEES!

set -e

echo "🏗️  Building Routecast locally without EAS..."

# Check if keystore exists
if [ ! -f "android/keystores/release.keystore" ]; then
    echo "❌ Error: Keystore not found!"
    echo "Please read android/keystores/README.md for setup instructions"
    exit 1
fi

# Set environment variables
export EXPO_PUBLIC_BACKEND_URL="https://routecast-backend.onrender.com"

# Generate native Android project
echo "📦 Running expo prebuild..."
npx expo prebuild --platform android --clean

# Build the app bundle with Gradle (signed and ready for Play Store)
echo "🔨 Building signed AAB with Gradle..."
cd android
./gradlew bundleRelease

echo ""
echo "✅ Build complete!"
echo "📱 Signed AAB file: android/app/build/outputs/bundle/release/app-release.aab"
echo ""
echo "You can now upload this AAB directly to Google Play Console!"
echo "No EAS charges - this was built 100% locally! 🎉"

