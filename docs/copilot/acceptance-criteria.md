# Acceptance Criteria: Feature Implementation Checklist

## Definition of Done

A feature is complete when all items in the appropriate section are checked.

## For All Features

### Code Quality
- [ ] All functions have complete type hints (Python `-> Type`, TypeScript `Type`)
- [ ] All inputs are validated with informative error messages
- [ ] All code paths have error handling
- [ ] No hardcoded values (use environment variables or config)
- [ ] No global state mutations
- [ ] Code follows Black/Prettier formatting
- [ ] Code review approved

### Testing
- [ ] Unit tests written for all major functions
- [ ] Tests use table-driven parametrized approach
- [ ] Edge cases covered (invalid inputs, boundaries, empty values)
- [ ] Tests pass locally: `pytest test_*.py -v`
- [ ] Code coverage > 80%

### Documentation
- [ ] README or feature guide created
- [ ] API endpoint documented (request/response examples)
- [ ] Function/method docstrings complete
- [ ] Complex logic explained with comments
- [ ] Real-world usage examples provided
- [ ] Troubleshooting guide included

### Git & Commits
- [ ] Code committed with clear messages
- [ ] Commits are logical and atomic
- [ ] No debugging/WIP commits
- [ ] Git history is clean

---

## For Backend Features

### Domain Logic (`*_service.py`)

- [ ] Service file created: `backend/feature_service.py`
- [ ] All functions are pure (no side effects)
- [ ] All data structures are immutable (`frozen=True` dataclasses)
- [ ] Input validation happens before core logic
- [ ] Clear error messages for invalid inputs
- [ ] Determinism verified (same input → same output)
- [ ] No database access from pure functions
- [ ] Comments explain complex algorithms
- [ ] Function signatures are clear and documented

### Tests (`test_*_service.py`)

- [ ] Test file created: `backend/test_feature_service.py`
- [ ] Test classes organized by function
- [ ] Table-driven parametrized test cases
- [ ] Minimum 3 test cases per function
- [ ] Invalid input cases tested (expect ValueError)
- [ ] Boundary conditions tested
- [ ] All tests pass: `pytest test_feature_service.py -v`
- [ ] Determinism test (100 iterations)
- [ ] Purity test (no side effects)

Example test structure:
```python
class TestFeatureFunction:
    CASES = [
        ("name", input1, input2, expected),
        ("another", input1, input2, expected),
    ]
    
    @pytest.mark.parametrize("name,in1,in2,exp", CASES)
    def test_function(self, name, in1, in2, exp):
        result = function(in1, in2)
        assert result == exp
    
    def test_invalid_input(self):
        with pytest.raises(ValueError):
            function(invalid_input)
```

### API Endpoint (`server.py`)

#### For Free Features
- [ ] Endpoint created in `/api/` path
- [ ] Request model defined with validation
- [ ] Response model defined with consistent structure
- [ ] Function validates all inputs
- [ ] Function has error handling with HTTPException
- [ ] Endpoint is documented with docstring
- [ ] Logging includes `[FEATURE]` prefix

#### For Premium Features
- [ ] Endpoint created in `/api/pro/` path
- [ ] `subscription_id` accepted in request
- [ ] Subscription validated against `db.subscriptions`
- [ ] If not authorized: Return response with `is_premium_locked: true`
- [ ] If authorized: Call domain service and return result with `is_premium_locked: false`
- [ ] Response includes `premium_message` field (for locked responses)
- [ ] All access logged with `[PREMIUM]` prefix
- [ ] Graceful error handling (400 for validation, 500 for server errors)

Example premium endpoint:
```python
@api_router.post("/pro/feature", response_model=FeatureResponse)
async def pro_feature(request: FeatureRequest):
    logger.info(f"[PREMIUM] Feature requested")
    
    # Check subscription
    is_authorized = request.subscription_id and await db.subscriptions.find_one({
        'subscription_id': request.subscription_id,
        'status': 'active'
    })
    
    if not is_authorized:
        logger.info(f"[PREMIUM] Denied - premium required")
        return FeatureResponse(
            is_premium_locked=True,
            premium_message="Upgrade to unlock..."
        )
    
    # Call domain service
    result = DomainService.calculate(...)
    logger.info(f"[PREMIUM] Feature executed successfully")
    
    return FeatureResponse(
        is_premium_locked=False,
        data=result
    )
```

### Type Hints
- [ ] All function parameters have types: `param: Type`
- [ ] All function returns have types: `-> Type`
- [ ] Pydantic models used for request/response
- [ ] Optional types marked: `Optional[Type]`
- [ ] Type imports are correct: `from typing import ...`

---

## For Frontend Features

### Hook (`hooks/useFeatureName.ts`)

- [ ] Hook file created: `frontend/app/hooks/useFeatureName.ts`
- [ ] Exports interface: `interface FeatureRequest { ... }`
- [ ] Exports interface: `interface FeatureResponse { ... }`
- [ ] Exports return interface: `interface UseFeatureReturn { ... }`
- [ ] Hook function: `export const useFeatureName = () => { ... }`
- [ ] State: `loading`, `error`, `result`
- [ ] Function: `assess(request)` or similar
- [ ] Handles `is_premium_locked` from response
- [ ] Automatic subscription ID retrieval from AsyncStorage
- [ ] Clear error messages
- [ ] JSDoc comments for public API
- [ ] No unused dependencies

Example hook structure:
```typescript
export interface FeatureRequest {
  param1: number;
  param2: string;
  subscription_id?: string;
}

export interface FeatureResponse {
  data: FeatureResult;
  is_premium_locked: boolean;
  premium_message?: string;
}

export const useFeatureName = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<FeatureResponse | null>(null);
  
  const assess = async (request: FeatureRequest) => {
    // Implementation
  };
  
  return { assess, loading, error, result };
};
```

### Component (`components/FeatureScreen.tsx`)

- [ ] Component file created: `frontend/app/components/FeatureScreen.tsx`
- [ ] Uses `useFeatureName` hook
- [ ] Uses `usePremium` hook for subscription info
- [ ] Input controls for all parameters
- [ ] Results display when available
- [ ] Loading indicator during assessment
- [ ] Error display with clear messages
- [ ] PaywallModal shown when `is_premium_locked: true`
- [ ] Color-coded severity/status indicators
- [ ] Responsive design (works on mobile)
- [ ] Touch targets > 44x44 points (accessibility)
- [ ] All text is readable
- [ ] Navigation/back button works

Example component structure:
```typescript
const FeatureScreen: React.FC = () => {
  const { assess, loading, error, result } = useFeatureName();
  const { subscriptionId } = usePremium();
  const [showPaywall, setShowPaywall] = useState(false);
  
  const handleAssess = async () => {
    try {
      const res = await assess({
        param1: value1,
        param2: value2,
        subscription_id: subscriptionId,
      });
      
      if (res.is_premium_locked) {
        setShowPaywall(true);
        return;
      }
      
      // Display results
    } catch (err) {
      // Handle error
    }
  };
  
  return (
    <ScrollView style={styles.container}>
      {/* Input controls */}
      <TouchableOpacity onPress={handleAssess} disabled={loading}>
        <Text>{loading ? 'Loading...' : 'Assess'}</Text>
      </TouchableOpacity>
      
      {error && <View style={styles.error}>{error}</View>}
      
      {result && !result.is_premium_locked && (
        <View>{/* Results display */}</View>
      )}
      
      <PaywallModal visible={showPaywall} onClose={...} />
    </ScrollView>
  );
};
```

### Type Safety
- [ ] All props have types
- [ ] All state has types
- [ ] Return type specified: `: React.FC`
- [ ] No `any` types (except justified with comment)
- [ ] Interface/type for every object
- [ ] TypeScript compiler has no errors: `tsc --noEmit`

### Testing
- [ ] Component renders without error
- [ ] Hook returns expected interface
- [ ] API call happens with correct parameters
- [ ] Premium lock response shows paywall
- [ ] Errors display correctly
- [ ] Loading state works

---

## Specific: Road Passability Feature

This is the reference implementation. Use as template for other features.

### Backend Checklist
- [ ] `backend/road_passability_service.py` (400+ lines)
  - `calculate_passability_score()` function
  - `assess_road_passability()` function
  - `PassabilityRisks` frozen dataclass
  - `RoadPassabilityResult` frozen dataclass
  - Pure functions, no DB access

- [ ] `backend/test_road_passability_service.py` (650+ lines)
  - 63+ test cases
  - Tests for score calculation
  - Tests for risk flags
  - Tests for all soil types
  - Edge case tests
  - Determinism verification

- [ ] `backend/server.py` additions
  - `RoadPassabilityRequest` model
  - `RoadPassabilityResponse` model
  - `POST /api/pro/road-passability` endpoint
  - Subscription validation
  - Premium gating logic
  - Error handling

### Frontend Checklist
- [ ] `frontend/app/hooks/useRoadPassability.ts`
  - `assess()` function
  - Loading/error/result states
  - Subscription ID handling

- [ ] `frontend/app/components/RoadPassabilityScreen.tsx`
  - Input controls
  - Results display
  - Premium paywall
  - Risk indicators

### Documentation Checklist
- [ ] `ROAD_PASSABILITY_FEATURE.md`
  - Algorithm explanation
  - API endpoint specification
  - Real-world examples
  - Integration guide
  - Troubleshooting

---

## Review Checklist

**For Code Reviewers**: Before approving, verify:

- [ ] Code quality standards met
- [ ] Tests cover all major paths
- [ ] Documentation is clear and complete
- [ ] Premium gating implemented correctly
- [ ] Error messages are helpful
- [ ] Performance is acceptable
- [ ] No security issues
- [ ] Follows project patterns
- [ ] Git history is clean

**For QA**: Before launching, test:

- [ ] Feature works as designed
- [ ] Premium gating works correctly
- [ ] Paywall triggers appropriately
- [ ] Errors display helpfully
- [ ] Loads quickly
- [ ] Works offline (if applicable)
- [ ] Works on different devices/OS versions
- [ ] Accessibility features work

---

## Success Metrics

A feature is production-ready when:

1. ✅ Code quality: No linting errors, full type hints
2. ✅ Testing: 80%+ coverage, all tests passing
3. ✅ Documentation: Complete and accurate
4. ✅ Premium features: Gating works, paywall triggers
5. ✅ Performance: API < 100ms, renders smooth
6. ✅ Errors: All paths handled gracefully
7. ✅ Logging: Analytics-ready with proper prefixes
8. ✅ Reviews: Code and design approved
9. ✅ QA: Tested on multiple devices
10. ✅ Docs: Feature guide, API reference, examples

---

## Quick Links

- [System Prompt](./system-prompt.md) - Development principles
- [Project Map](./project-map.md) - Repository structure
- [Road Passability](../ROAD_PASSABILITY_FEATURE.md) - Reference implementation
