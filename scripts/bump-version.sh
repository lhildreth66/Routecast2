#!/usr/bin/env bash
# bump-version.sh — Keep app.json and android/app/build.gradle in sync.
#
# Usage:
#   scripts/bump-version.sh <versionName> <versionCode>
#
# Example:
#   scripts/bump-version.sh 1.0.164 235
#
# What it does:
#   1. Validates arguments
#   2. Updates frontend/app.json  (version + android.versionCode)
#   3. Updates frontend/android/app/build.gradle  (versionName + versionCode)
#   4. Reads both files back and verifies the values were written correctly
#   5. Prints a summary — does NOT commit or push (caller decides that)

set -euo pipefail

# ── Colours ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
RESET='\033[0m'

ok()   { echo -e "${GREEN}✔${RESET} $*"; }
fail() { echo -e "${RED}✖ ERROR:${RESET} $*" >&2; exit 1; }
info() { echo -e "${YELLOW}→${RESET} $*"; }

# ── Args ─────────────────────────────────────────────────────────────────────
if [[ $# -ne 2 ]]; then
    echo -e "${BOLD}Usage:${RESET} $0 <versionName> <versionCode>"
    echo "  Example: $0 1.0.164 235"
    exit 1
fi

VERSION_NAME="$1"
VERSION_CODE="$2"

# Validate versionName looks like x.y.z
if ! [[ "$VERSION_NAME" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    fail "versionName must be in x.y.z format (got: '$VERSION_NAME')"
fi

# Validate versionCode is a positive integer
if ! [[ "$VERSION_CODE" =~ ^[1-9][0-9]*$ ]]; then
    fail "versionCode must be a positive integer (got: '$VERSION_CODE')"
fi

# ── Locate files ─────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

APP_JSON="$REPO_ROOT/frontend/app.json"
BUILD_GRADLE="$REPO_ROOT/frontend/android/app/build.gradle"

[[ -f "$APP_JSON" ]]     || fail "app.json not found at $APP_JSON"
[[ -f "$BUILD_GRADLE" ]] || fail "build.gradle not found at $BUILD_GRADLE"

# ── Read current values ───────────────────────────────────────────────────────
OLD_VERSION=$(grep -m1 '"version"' "$APP_JSON" | sed 's/.*"version": *"\([^"]*\)".*/\1/')
OLD_VC_JSON=$(grep -m1 '"versionCode"' "$APP_JSON" | sed 's/[^0-9]//g')
OLD_VN_GRADLE=$(grep -m1 'versionName' "$BUILD_GRADLE" | sed 's/.*versionName *"\([^"]*\)".*/\1/')
OLD_VC_GRADLE=$(grep -m1 'versionCode' "$BUILD_GRADLE" | sed 's/[^0-9]//g')

echo ""
echo -e "${BOLD}Current values:${RESET}"
echo "  app.json          version      = $OLD_VERSION"
echo "  app.json          versionCode  = $OLD_VC_JSON"
echo "  build.gradle      versionName  = $OLD_VN_GRADLE"
echo "  build.gradle      versionCode  = $OLD_VC_GRADLE"
echo ""
echo -e "${BOLD}Applying:${RESET}"
echo "  versionName → $VERSION_NAME"
echo "  versionCode → $VERSION_CODE"
echo ""

# ── Update app.json ───────────────────────────────────────────────────────────
info "Updating app.json ..."

# "version": "x.y.z"  (top-level, first occurrence)
sed -i "s/\"version\": *\"[^\"]*\"/\"version\": \"$VERSION_NAME\"/" "$APP_JSON"

# "versionCode": N  (inside android block)
sed -i "s/\"versionCode\": *[0-9]*/\"versionCode\": $VERSION_CODE/" "$APP_JSON"

# ── Update build.gradle ───────────────────────────────────────────────────────
info "Updating android/app/build.gradle ..."

sed -i "s/versionCode *[0-9]*/versionCode $VERSION_CODE/" "$BUILD_GRADLE"
sed -i "s/versionName *\"[^\"]*\"/versionName \"$VERSION_NAME\"/" "$BUILD_GRADLE"

# ── Verify ────────────────────────────────────────────────────────────────────
NEW_VERSION=$(grep -m1 '"version"' "$APP_JSON" | sed 's/.*"version": *"\([^"]*\)".*/\1/')
NEW_VC_JSON=$(grep -m1 '"versionCode"' "$APP_JSON" | sed 's/[^0-9]//g')
NEW_VN_GRADLE=$(grep -m1 'versionName' "$BUILD_GRADLE" | sed 's/.*versionName *"\([^"]*\)".*/\1/')
NEW_VC_GRADLE=$(grep -m1 'versionCode' "$BUILD_GRADLE" | sed 's/[^0-9]//g')

ERRORS=0

check() {
    local label="$1" expected="$2" actual="$3"
    if [[ "$actual" == "$expected" ]]; then
        ok "$label = $actual"
    else
        echo -e "${RED}✖${RESET} $label expected '$expected', got '$actual'" >&2
        ERRORS=$((ERRORS + 1))
    fi
}

echo -e "${BOLD}Verification:${RESET}"
check "app.json          version     " "$VERSION_NAME" "$NEW_VERSION"
check "app.json          versionCode " "$VERSION_CODE" "$NEW_VC_JSON"
check "build.gradle      versionName " "$VERSION_NAME" "$NEW_VN_GRADLE"
check "build.gradle      versionCode " "$VERSION_CODE" "$NEW_VC_GRADLE"

echo ""
if [[ $ERRORS -ne 0 ]]; then
    fail "$ERRORS value(s) did not update correctly — check the files manually."
fi

# ── Summary ───────────────────────────────────────────────────────────────────
echo -e "${BOLD}${GREEN}Done.${RESET} Both files updated successfully."
echo ""
echo "  Files changed:"
echo "    frontend/app.json"
echo "    frontend/android/app/build.gradle"
echo ""
echo "  New values:"
echo "    versionName  $OLD_VERSION  →  $VERSION_NAME"
echo "    versionCode  $OLD_VC_GRADLE  →  $VERSION_CODE"
echo ""
echo "  Suggested commit:"
echo "    git add frontend/app.json frontend/android/app/build.gradle"
echo "    git commit -m \"Bump version to $VERSION_NAME ($VERSION_CODE)\""
echo "    git push origin main"
echo ""
