#!/bin/bash

# Usage: ./scripts/bump-version.sh 1.0.106 106

if [ -z "$1" ] || [ -z "$2" ]; then
    echo "Usage: $0 <version> <versionCode>"
    echo "Example: $0 1.0.106 106"
    exit 1
fi

VERSION=$1
VERSION_CODE=$2

echo "Bumping version to $VERSION ($VERSION_CODE)..."

# Update app.json
sed -i "s/\"version\": \"[0-9.]*\"/\"version\": \"$VERSION\"/" frontend/app.json
sed -i "s/\"versionCode\": [0-9]*/\"versionCode\": $VERSION_CODE/" frontend/app.json

# Update build.gradle
sed -i "s/versionCode [0-9]*/versionCode $VERSION_CODE/" frontend/android/app/build.gradle
sed -i "s/versionName \"[0-9.]*\"/versionName \"$VERSION\"/" frontend/android/app/build.gradle

echo "✅ Updated app.json: version=$VERSION, versionCode=$VERSION_CODE"
echo "✅ Updated build.gradle: versionCode=$VERSION_CODE, versionName=$VERSION"
echo ""
echo "Verify changes:"
grep -A1 '"version"' frontend/app.json | head -2
grep 'versionCode' frontend/android/app/build.gradle
grep 'versionName' frontend/android/app/build.gradle
