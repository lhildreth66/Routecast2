# Definition of Done

**Project**: Routecast2  
**Version**: 1.0.8  
**Last Updated**: January 18, 2026

This document defines the acceptance criteria that must be met before any feature is considered complete and ready for release. All criteria are mandatory unless explicitly marked as optional.

---

## Table of Contents

1. [Domain & Core Logic](#domain--core-logic)
2. [Premium Gating](#premium-gating)
3. [Paywall & Purchases](#paywall--purchases)
4. [Chat & AI Intents](#chat--ai-intents)
5. [Claim Log Export](#claim-log-export)
6. [Analytics](#analytics)
7. [Background Notifications](#background-notifications)
8. [General Requirements](#general-requirements)

---

## Domain & Core Logic

### AC-DOMAIN-1: Pure Domain Functions
**Requirement**: All domain functions must be pure (no side effects, no Android framework dependencies, no I/O operations).

**Validation**:
- ✅ Domain functions accept inputs and return outputs without modifying external state
- ✅ No direct Android framework imports (e.g., `android.*`, `androidx.*`)
- ✅ No I/O operations (file system, network, database) in domain layer
- ✅ Functions are deterministic (same input → same output)
- ✅ No access to system time, random generators, or other non-deterministic sources

**Examples**:
```python
# ✅ GOOD: Pure domain function
def compute_departure_risk(
    weather: WeatherConditions,
    route: Route,
    departure_time: datetime
) -> RiskScore:
    # Pure calculation, no side effects
    return RiskScore(...)

# ❌ BAD: Impure domain function
def compute_departure_risk(route: Route) -> RiskScore:
    weather = requests.get("https://api.weather.com")  # I/O!
    current_time = datetime.now()  # Non-deterministic!
    return RiskScore(...)
```

**Testing**:
- Domain functions can be tested without mocks (table-driven tests)
- Tests should use fixture data, not live APIs
- Tests must be fast (<100ms per test)

---

### AC-DOMAIN-2: Test Coverage
**Requirement**: Domain layer must have ≥85% unit test line coverage.

**Validation**:
- ✅ Run coverage analysis: `pytest --cov=backend/notifications --cov-report=term-missing`
- ✅ Coverage report shows ≥85% for domain modules
- ✅ All critical paths have test coverage
- ✅ Edge cases are tested (null inputs, boundary values, error conditions)

**Exemptions**:
- Trivial getters/setters (if any)
- Debug logging statements
- Type checking code (if any)

**Example Coverage Report**:
```
backend/notifications/smart_delay.py    92%
backend/notifications/models.py         88%
backend/notifications/expo_push.py      85%
```

**Enforcement**:
- CI/CD pipeline fails if coverage drops below 85%
- Coverage must be measured per-module, not just aggregate

---

## Premium Gating

### AC-GATE-1: Centralized Gating
**Requirement**: Premium feature gating must be centralized using a single gate function/mechanism. No ad-hoc entitlement checks scattered throughout codebase.

**Validation**:
- ✅ All premium checks use `premiumGate()` function (frontend) or `require_premium()` decorator (backend)
- ✅ No direct `isPremium` or `hasEntitlement` checks outside gate layer
- ✅ Search for `isPremium` returns only centralized gate implementations

**Implementation**:
```typescript
// ✅ GOOD: Centralized gating
const result = await premiumGate({
  feature: 'solar_forecast',
  action: () => fetchSolarForecast(),
  onLocked: () => showPaywall('solar_forecast')
});

// ❌ BAD: Ad-hoc check
if (!user.isPremium) {
  showPaywall();
  return;
}
fetchSolarForecast();
```

**Audit Command**:
```bash
# Should return only premiumGate.ts and test files
grep -r "isPremium" frontend/app --exclude-dir=__tests__
```

---

### AC-GATE-2: PremiumLockedException
**Requirement**: Premium features must throw `PremiumLockedException` (or equivalent) when accessed without valid entitlements.

**Validation**:
- ✅ Backend endpoints return 402 Payment Required for locked features
- ✅ Frontend gates either redirect to paywall or show soft gate
- ✅ Exception/error contains feature name for tracking
- ✅ No silent failures (user must know why access was denied)

**Backend Example**:
```python
@require_premium()
async def smart_delay_endpoint(request):
    # Will raise PremiumLockedException if not premium
    pass
```

**Frontend Example**:
```typescript
try {
  await api.getSolarForecast();
} catch (error) {
  if (error.status === 402) {
    showPaywall('solar_forecast');
  }
}
```

---

## Paywall & Purchases

### AC-PAYWALL-1: Trigger on Locked Action
**Requirement**: Paywall must appear immediately when user attempts to access a locked feature.

**Validation**:
- ✅ Manual test: Tap locked feature as free user → paywall appears
- ✅ Paywall displays within 200ms of tap
- ✅ Paywall shows which feature triggered it
- ✅ User can dismiss paywall and return to previous screen

**Test Case**:
```
1. Log out or use free account
2. Tap "Solar Forecast" button
3. EXPECT: Paywall modal appears
4. EXPECT: Modal shows "Solar Forecast" as locked feature
5. Tap "Not Now"
6. EXPECT: Return to previous screen
```

---

### AC-PAYWALL-2: Immediate Unlock
**Requirement**: Successful purchase must immediately unlock features (no app restart required).

**Validation**:
- ✅ Purchase → entitlements refresh within 1 second
- ✅ Previously locked features become accessible immediately
- ✅ Paywall does not reappear after purchase
- ✅ UI updates to reflect premium status (badges, icons, etc.)

**Test Case**:
```
1. Trigger paywall from locked feature
2. Complete test purchase (sandbox)
3. EXPECT: Paywall dismisses automatically
4. EXPECT: Feature is now accessible
5. EXPECT: Premium badge appears in UI
6. EXPECT: No app restart needed
```

**Implementation Check**:
- Entitlements are refreshed after successful purchase
- Subscription state is stored in memory and persisted
- UI observes subscription state changes

---

### AC-PAYWALL-3: Persistence
**Requirement**: Entitlements must persist across app relaunch.

**Validation**:
- ✅ Purchase → force quit app → relaunch → features still unlocked
- ✅ Subscription status loaded from persistent storage on app start
- ✅ Receipt validation on launch (if applicable)
- ✅ No regression to free tier after restart

**Test Case**:
```
1. Complete purchase (or restore previous purchase)
2. Verify premium features are unlocked
3. Force quit app (swipe away from task switcher)
4. Relaunch app
5. EXPECT: Still logged in as premium user
6. EXPECT: Premium features still accessible
7. EXPECT: No paywall re-appears
```

**Storage Check**:
- AsyncStorage (frontend) or database (backend) contains subscription record
- Subscription includes expiry date and product ID
- App validates subscription on cold start

---

## Chat & AI Intents

### AC-CHAT-1: Dual Response Format
**Requirement**: Each chat intent must return both human-readable text AND structured JSON payload.

**Validation**:
- ✅ API response contains `text` field (string, human-readable)
- ✅ API response contains `data` field (object, structured JSON)
- ✅ Text is suitable for display in chat UI
- ✅ JSON payload follows documented schema

**Example Response**:
```json
{
  "text": "Based on current conditions, I recommend delaying your departure by 2 hours to avoid severe weather.",
  "data": {
    "intent": "smart_delay_recommendation",
    "recommendedDelay": {
      "hours": 2,
      "reason": "severe_weather",
      "confidence": 0.87
    },
    "weatherConditions": {
      "current": "rain",
      "severity": "high"
    }
  }
}
```

---

### AC-CHAT-2: Schema Compliance
**Requirement**: JSON responses must follow documented schemas (versioned, with examples).

**Validation**:
- ✅ Schema files exist in `/backend/schemas/` or `/docs/schemas/`
- ✅ Schemas include version number (e.g., `v1`)
- ✅ Each schema has at least one example payload
- ✅ Responses validate against schema (automated test)

**Schema Example** (`/backend/schemas/smart_delay_v1.json`):
```json
{
  "version": "1.0",
  "type": "object",
  "required": ["intent", "recommendedDelay"],
  "properties": {
    "intent": {
      "type": "string",
      "enum": ["smart_delay_recommendation"]
    },
    "recommendedDelay": {
      "type": "object",
      "required": ["hours", "reason"],
      "properties": {
        "hours": { "type": "number", "minimum": 0, "maximum": 48 },
        "reason": { "type": "string" }
      }
    }
  }
}
```

**Test Requirement**:
- JSON schema validation in unit tests
- Example payloads in tests match production responses

---

## Claim Log Export

### AC-CLAIM-1: Valid JSON Export
**Requirement**: Claim Log must export valid JSON matching the documented schema.

**Validation**:
- ✅ Export → JSON file is created
- ✅ JSON is valid (parseable by `JSON.parse()`)
- ✅ JSON validates against schema in `/docs/schemas/claim_log_v1.json`
- ✅ All required fields are present
- ✅ Data types match schema

**Schema Location**: `/docs/schemas/claim_log_v1.json` (must exist)

**Test Case**:
```
1. Create incident with photos, notes, weather data
2. Tap "Export Claim Log" → Select JSON
3. EXPECT: File downloads/saves
4. Open file in text editor
5. EXPECT: Valid JSON (no syntax errors)
6. Validate against schema
7. EXPECT: Passes validation
```

**Example Export**:
```json
{
  "version": "1.0",
  "exportDate": "2026-01-18T19:30:00Z",
  "incident": {
    "id": "incident_123",
    "timestamp": "2026-01-15T14:00:00Z",
    "location": {
      "latitude": 40.7128,
      "longitude": -74.0060
    },
    "description": "Vehicle stuck in mud",
    "photos": [
      { "url": "file://...", "timestamp": "..." }
    ]
  }
}
```

---

### AC-CLAIM-2: PDF Export and Open
**Requirement**: Claim Log must export as PDF that opens on-device without errors.

**Validation**:
- ✅ Export → PDF file is created
- ✅ PDF is valid (opens in system PDF viewer)
- ✅ PDF contains all incident data (text, photos, metadata)
- ✅ Photos are embedded (not linked)
- ✅ PDF is formatted for printing (header, footer, page numbers)

**Test Case**:
```
1. Create incident with ≥2 photos and notes
2. Tap "Export Claim Log" → Select PDF
3. EXPECT: PDF file downloads/saves
4. Tap file to open
5. EXPECT: Opens in default PDF viewer (no errors)
6. EXPECT: Contains incident details, photos, timestamp
7. EXPECT: Formatted professionally (readable, printable)
```

**Quality Checks**:
- Photos are not blurry or oversized
- Text is selectable (not image-based)
- Metadata includes app version, export date
- File size is reasonable (<10MB for typical incident)

---

## Analytics

### AC-ANALYTICS-1: Required Events
**Requirement**: All required analytics events must be logged at the correct trigger points.

**Events**:
1. **paywall_viewed**: When paywall screen/modal is displayed
2. **trial_started**: When user successfully starts free trial
3. **purchase_success**: After confirmed subscription purchase
4. **feature_intent_used**: When user attempts to use any feature (free or premium)
5. **feature_locked_shown**: When paywall is shown due to premium gate

**Validation**:
- ✅ Search codebase for `trackEvent('paywall_viewed')` → found in PaywallScreen
- ✅ Search for `trackEvent('trial_started')` → found in purchase handler
- ✅ Search for `trackEvent('purchase_success')` → found in purchase handler
- ✅ Search for `trackEvent('feature_intent_used')` → found in premiumGate
- ✅ Search for `trackEvent('feature_locked_shown')` → found in premiumGate
- ✅ Manual test: Trigger each event → verify console log (dev mode)

**Audit Command**:
```bash
# Check all events are tracked
grep -r "trackEvent" frontend/app/billing
grep -r "trackEvent" frontend/app/utils
```

**Test Case**:
```
1. Open app with __DEV__ = true
2. Trigger paywall → check console for "paywall_viewed"
3. Complete purchase → check console for "purchase_success" + "trial_started"
4. Attempt locked feature → check console for "feature_intent_used" + "feature_locked_shown"
5. EXPECT: All 5 events appear in console
```

---

### AC-ANALYTICS-2: Non-Blocking & No PII
**Requirement**: Analytics events must be non-blocking (never throw errors, never delay UI) and must not contain Personally Identifiable Information (PII).

**Validation**:
- ✅ Events are logged asynchronously (no `await` in UI code)
- ✅ Event tracking wrapped in try/catch (errors logged, not thrown)
- ✅ No PII fields: email, userId, name, phone, address, creditCard, etc.
- ✅ Automated test: Pass PII → verify it's stripped before storage

**Non-Blocking Check**:
```typescript
// ✅ GOOD: Fire and forget
trackEvent('paywall_viewed', { feature: 'solar_forecast' });

// ❌ BAD: Blocking UI
await trackEvent('paywall_viewed', { feature: 'solar_forecast' });
```

**PII Sanitization Test**:
```typescript
// Test that PII is removed
trackEvent('purchase_success', {
  productId: 'pro_yearly',
  email: 'user@example.com',  // Should be stripped
  userId: '12345'              // Should be stripped
});

const events = await getStoredEvents();
expect(events[0].params.email).toBeUndefined();
expect(events[0].params.userId).toBeUndefined();
```

**Allowed Data**:
- Feature names (e.g., 'solar_forecast')
- Product IDs (e.g., 'pro_yearly')
- Plan types (e.g., 'monthly', 'yearly')
- Platform (e.g., 'ios', 'android')
- Timestamps
- Session IDs (ephemeral, non-identifying)

**Blocked Data**:
- Email addresses
- User IDs
- Names
- Phone numbers
- Addresses
- Credit card info
- IP addresses
- Device IDs (IMEI, UDID)

---

## Background Notifications

### AC-NOTIF-1: Reproducible Fixture Conditions
**Requirement**: Weather-based background notifications must fire under reproducible fixture conditions (no reliance on live weather APIs).

**Validation**:
- ✅ Tests use fixture data (mocked weather responses)
- ✅ System time is controllable (mocked or injected)
- ✅ Tests are deterministic (same fixture → same result)
- ✅ No network calls in test suite (all APIs mocked)

**Example Test**:
```python
def test_smart_delay_notification_fires():
    # Fixture data (no live API)
    fixture_weather = WeatherConditions(
        temperature=32,
        conditions="snow",
        visibility_miles=0.5
    )
    
    fixture_trip = PlannedTrip(
        departure_time=datetime(2026, 1, 20, 8, 0),
        destination="Denver, CO"
    )
    
    # Pure domain logic (no I/O)
    recommendation = compute_departure_risk(
        weather=fixture_weather,
        route=fixture_trip.route,
        departure_time=fixture_trip.departure_time
    )
    
    assert recommendation.should_notify == True
    assert recommendation.recommended_delay_hours == 4
```

---

### AC-NOTIF-2: No Live Dependencies
**Requirement**: Background notification tests must not rely on live network or real system time.

**Validation**:
- ✅ Network requests are mocked (`httpx.Mock`, `responses`, etc.)
- ✅ System time is injected (pass `datetime` as parameter, not `datetime.now()`)
- ✅ Tests run offline (disable network → tests still pass)
- ✅ Tests complete in <5 seconds (no waiting for real timers)

**Bad Example**:
```python
# ❌ BAD: Uses live API
def test_notification():
    weather = requests.get("https://api.weather.com")  # FAILS offline
    assert weather.status_code == 200
```

**Good Example**:
```python
# ✅ GOOD: Uses fixture
def test_notification(httpx_mock):
    httpx_mock.add_response(
        url="https://api.weather.com",
        json={"temp": 32, "conditions": "snow"}
    )
    
    weather = fetch_weather()  # Uses mock
    assert weather.temp == 32
```

**Time Injection**:
```python
# ✅ GOOD: Time is injected
def should_send_notification(
    trip: PlannedTrip,
    current_time: datetime  # Injected, not datetime.now()
) -> bool:
    time_until_departure = trip.departure_time - current_time
    return time_until_departure.hours <= 4
```

---

## General Requirements

### AC-GENERAL-1: Code Quality
**Requirement**: All code must pass linting and type checking.

**Validation**:
- ✅ Frontend: `npm run lint` passes (0 errors)
- ✅ Backend: `flake8` and `mypy` pass
- ✅ No unused imports or variables
- ✅ Consistent code style (auto-formatted)

**Enforcement**:
- CI/CD pipeline fails if linting fails
- Pre-commit hooks run linters locally

---

### AC-GENERAL-2: Documentation
**Requirement**: All public APIs and complex logic must be documented.

**Validation**:
- ✅ All exported functions have JSDoc/docstrings
- ✅ Complex algorithms include inline comments
- ✅ README files exist for major modules
- ✅ API endpoints documented in OpenAPI/Swagger (if applicable)

**Example**:
```typescript
/**
 * Tracks an analytics event with automatic deduplication and PII sanitization.
 * 
 * @param name - Event name (e.g., 'paywall_viewed')
 * @param params - Event parameters (feature, source, etc.)
 * 
 * @example
 * trackEvent('paywall_viewed', { feature: 'solar_forecast' });
 */
export async function trackEvent(
  name: AnalyticsEvent,
  params: EventParams = {}
): Promise<void> {
  // Implementation...
}
```

---

### AC-GENERAL-3: No Regressions
**Requirement**: Existing tests must continue to pass after new changes.

**Validation**:
- ✅ Full test suite runs: `npm test` (frontend) + `pytest` (backend)
- ✅ All existing tests pass (0 failures)
- ✅ No skipped tests (unless documented with reason)
- ✅ Test coverage does not decrease

**Pre-Release Checklist**:
```bash
# Frontend
cd frontend
npm test                    # All tests pass
npm run lint                # 0 errors

# Backend
cd backend
pytest                      # All tests pass
pytest --cov --cov-report=term-missing  # Coverage ≥85%
flake8                      # 0 errors
mypy .                      # 0 errors
```

---

## Release Checklist

Before any release, verify:

- [ ] **Domain Logic**: Pure functions, ≥85% coverage
- [ ] **Premium Gating**: Centralized, throws exceptions, no ad-hoc checks
- [ ] **Paywall**: Triggers on locked actions, immediate unlock, persists
- [ ] **Chat Intents**: Dual response format, schema compliance
- [ ] **Claim Export**: Valid JSON + PDF opens on-device
- [ ] **Analytics**: All 5 events tracked, non-blocking, no PII
- [ ] **Notifications**: Fixture-based tests, no live dependencies
- [ ] **Code Quality**: Linting passes, types validated
- [ ] **Documentation**: APIs documented, examples provided
- [ ] **Tests**: All passing, no regressions

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-01-18 | Initial Definition of Done |

---

## References

- Analytics Implementation: `/frontend/ANALYTICS.md`
- Test Coverage: `/backend/test_notifications_smart_delay.py`
- Premium Gating: `/frontend/app/billing/premiumGate.ts`
- Schemas: `/docs/schemas/` (to be created)

---

**Maintained by**: Engineering Team  
**Reviewed by**: Product, QA, Release Management  
**Effective Date**: January 18, 2026

