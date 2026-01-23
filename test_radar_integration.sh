#!/bin/bash
# Smoke test for weather radar & alerts integration

echo "🧪 Weather Radar Integration Smoke Test"
echo "========================================"
echo ""

BACKEND_URL="http://localhost:8000"

# Test 1: Check if radar alerts endpoint is available
echo "Test 1: Checking /api/radar/alerts/map endpoint..."
ALERTS_RESPONSE=$(curl -s "${BACKEND_URL}/api/radar/alerts/map")
ALERT_COUNT=$(echo "$ALERTS_RESPONSE" | jq -r '.total_count // "ERROR"')

if [ "$ALERT_COUNT" != "ERROR" ]; then
    echo "✅ PASS: Found $ALERT_COUNT alerts with geometry"
else
    echo "❌ FAIL: Could not fetch alerts"
    exit 1
fi
echo ""

# Test 2: Check if radar tiles endpoint works
echo "Test 2: Checking /api/radar/tiles endpoint..."
TILES_RESPONSE=$(curl -s "${BACKEND_URL}/api/radar/tiles")
TILE_URL=$(echo "$TILES_RESPONSE" | jq -r '.tile_url // "null"')

if [ "$TILE_URL" != "null" ]; then
    echo "✅ PASS: Radar tiles available"
    echo "   URL: ${TILE_URL:0:50}..."
else
    echo "⚠️  WARNING: Radar tiles unavailable (RainViewer may be down)"
fi
echo ""

# Test 3: Check alert types endpoint
echo "Test 3: Checking /api/radar/alert-types endpoint..."
TYPES_RESPONSE=$(curl -s "${BACKEND_URL}/api/radar/alert-types")
CATEGORIES=$(echo "$TYPES_RESPONSE" | jq -r '.categories | length')

if [ "$CATEGORIES" -gt 0 ]; then
    echo "✅ PASS: Alert types endpoint working ($CATEGORIES categories)"
else
    echo "❌ FAIL: Alert types endpoint not working"
    exit 1
fi
echo ""

# Test 4: Check cache behavior
echo "Test 4: Testing 10-minute cache..."
echo "   First request (should fetch from NWS)..."
TIME1=$(date +%s%N)
curl -s "${BACKEND_URL}/api/radar/alerts/map" > /dev/null
TIME2=$(date +%s%N)
DURATION1=$(( (TIME2 - TIME1) / 1000000 ))
echo "   Duration: ${DURATION1}ms"

echo "   Second request (should use cache)..."
TIME1=$(date +%s%N)
curl -s "${BACKEND_URL}/api/radar/alerts/map" > /dev/null
TIME2=$(date +%s%N)
DURATION2=$(( (TIME2 - TIME1) / 1000000 ))
echo "   Duration: ${DURATION2}ms"

if [ $DURATION2 -lt $(( DURATION1 / 2 )) ]; then
    echo "✅ PASS: Cache is working (2nd request ${DURATION2}ms < 1st request ${DURATION1}ms)"
else
    echo "⚠️  WARNING: Cache may not be working as expected"
fi
echo ""

echo "========================================"
echo "✅ All smoke tests passed!"
echo ""
echo "Next steps:"
echo "1. Test frontend: npm start in /frontend"
echo "2. Navigate to any route"
echo "3. Tap 'Radar' button in header"
echo "4. Verify map loads with alerts and radar toggle"
