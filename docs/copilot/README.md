# Copilot Development Guide

This directory contains guidance for GitHub Copilot and developers implementing features in Routecast2.

## Quick Links

1. [System Prompt](./system-prompt.md) - Core principles and architecture
2. [Project Map](./project-map.md) - Repository structure and key files
3. [Acceptance Criteria](./acceptance-criteria.md) - Definition of done for features
4. [Premium Features](./premium-features.md) - How to gate and implement premium-only features

## Key Principles

### Backend Stack
- **Language**: Python 3.x
- **Framework**: FastAPI
- **Database**: MongoDB
- **Testing**: pytest
- **Code Style**: Type hints, pure functions, immutable data

### Frontend Stack
- **Framework**: React Native + Expo
- **Language**: TypeScript
- **Testing**: Jest
- **State**: React hooks
- **Styling**: React Native StyleSheet

### Premium Features

All premium features must:

1. **Gate Behind Paywall**
   - Validate subscription via `db.subscriptions` collection
   - Return 403-like response if not authorized
   - Frontend shows `PaywallModal` on `is_premium_locked: true`

2. **Pure Domain Logic**
   - Core business logic in pure functions
   - No side effects, fully testable
   - Immutable data structures

3. **Comprehensive Testing**
   - Unit tests for all major functions
   - Edge case coverage
   - Table-driven parametrized tests
   - Verify determinism and purity

4. **Clear Error Handling**
   - Validate all inputs
   - Graceful degradation
   - Informative error messages
   - No hard blocks on premium features

## Feature Implementation Flow

1. **Design Phase**
   - Read acceptance criteria
   - Check project map for related code
   - Define API contract
   - Plan data models

2. **Backend Implementation**
   - Create pure domain service
   - Implement FastAPI endpoint with gating
   - Add comprehensive tests
   - Verify determinism

3. **Frontend Integration**
   - Create React hook for API calls
   - Build UI component
   - Integrate paywall modal
   - Add error handling

4. **Documentation**
   - Write feature guide
   - Document API endpoint
   - Provide integration examples
   - Include real-world scenarios

5. **Testing & Verification**
   - Run full test suite
   - Verify premium gating works
   - Test paywall flow
   - Validate type safety

## Code Quality Standards

✅ **Required**
- Full type hints (Python/TypeScript)
- Comprehensive unit tests
- Error handling
- Input validation
- Pure functions where applicable
- Immutable data
- Clear documentation

❌ **Forbidden**
- Hardcoded API keys
- Side effects in pure functions
- Incomplete error handling
- Untested code paths
- Silent failures
- Global state mutations

## Premium Feature Architecture

```
Backend:
  └─ domain/
     └─ service.py (pure functions, immutable data)
  └─ api/
     └─ endpoint (subscription validation, gating)
  └─ tests/
     └─ test_service.py (comprehensive tests)

Frontend:
  └─ hooks/
     └─ useFeatureName.ts (API calls, state)
  └─ components/
     └─ FeatureScreen.tsx (UI, paywall handling)
```

## Gating Pattern

### Backend (FastAPI)
```python
@api_router.post("/pro/feature-name")
async def feature_endpoint(request: FeatureRequest):
    # Validate subscription
    is_authorized = await validate_subscription(request.subscription_id)
    
    if not is_authorized:
        return FeatureResponse(
            is_premium_locked=True,
            premium_message="Upgrade to unlock..."
        )
    
    # Call pure domain service
    result = DomainService.calculate(...)
    return FeatureResponse(
        is_premium_locked=False,
        result=result
    )
```

### Frontend (React)
```typescript
const { result, error } = await assess(params);

if (result.is_premium_locked) {
    showPaywall();  // PaywallModal
} else {
    displayResults(result);
}
```

## Next Steps

- Review [system-prompt.md](./system-prompt.md) for detailed principles
- Check [project-map.md](./project-map.md) to understand structure
- Read [acceptance-criteria.md](./acceptance-criteria.md) for feature requirements
- See [premium-features.md](./premium-features.md) for gating specifics
