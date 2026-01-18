# System Prompt: Routecast Development Principles

## Core Architecture

### Backend
- **Framework**: FastAPI (Python 3.x)
- **Database**: MongoDB (via motor async driver)
- **API Pattern**: RESTful with `/api/` prefix, `/api/pro/` for premium
- **Code Style**: 
  - Type hints on all functions
  - Pure functions for domain logic
  - Immutable data where possible
  - Comprehensive error handling

### Frontend
- **Framework**: React Native + Expo
- **Language**: TypeScript (100% typed)
- **Router**: Expo Router (file-based)
- **State**: React hooks
- **Styling**: React Native StyleSheet
- **HTTP**: Fetch API with typed responses

### Database Collections
- **subscriptions**: `{subscription_id, status, created_at, last_validated}`
- Other collections as needed per feature

## Feature Implementation Principles

### 1. Pure Functions
**Definition**: Functions that have no side effects and are deterministic.

**Good**:
```python
def calculate_score(input1, input2):
    result = input1 * input2
    return result  # No DB access, no mutations
```

**Bad**:
```python
def calculate_score(input1, input2):
    db.log_access()  # Side effect!
    return input1 * input2
```

### 2. Immutable Data
**Use frozen dataclasses** for all response/result objects:

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class Result:
    score: int
    message: str
```

### 3. Type Safety

**Python Backend**:
```python
from typing import List, Optional
from pydantic import BaseModel

class Request(BaseModel):
    param: int
    optional_param: Optional[str] = None

def handler(request: Request) -> ResponseModel:
    # Full type hints
    pass
```

**TypeScript Frontend**:
```typescript
interface Request {
  param: number;
  optional_param?: string;
}

async function handler(request: Request): Promise<ResponseModel> {
  // Full typing
}
```

### 4. Error Handling

**Never silently fail**. Always:
1. Validate inputs
2. Return informative errors
3. Log for debugging
4. Gracefully degrade

```python
try:
    result = validate_input(request)
    if not result.is_valid:
        raise ValueError(f"Invalid input: {result.reason}")
    
    output = process(result.data)
    return SuccessResponse(output)
except ValueError as e:
    logger.error(f"[FEATURE] Validation error: {e}")
    raise HTTPException(status_code=400, detail=str(e))
except Exception as e:
    logger.error(f"[FEATURE] Unexpected error: {e}")
    raise HTTPException(status_code=500, detail="Unable to process")
```

### 5. Premium Feature Gating

**All premium endpoints must**:

1. Accept optional `subscription_id`
2. Validate against `db.subscriptions` collection
3. Return `is_premium_locked: true` if not authorized
4. Log access with `[PREMIUM]` prefix
5. Show PaywallModal on frontend if locked

```python
@api_router.post("/pro/feature")
async def pro_feature(request: ProRequest):
    logger.info(f"[PREMIUM] Feature access requested")
    
    # Check subscription
    is_authorized = request.subscription_id and await db.subscriptions.find_one(
        {'subscription_id': request.subscription_id, 'status': 'active'}
    )
    
    if not is_authorized:
        logger.info(f"[PREMIUM] Access denied - premium required")
        return ProResponse(
            is_premium_locked=True,
            premium_message="Upgrade to Routecast Pro"
        )
    
    logger.info(f"[PREMIUM] Access granted for {request.subscription_id}")
    # Process request
    return ProResponse(is_premium_locked=False, data=result)
```

### 6. Testing Requirements

**Python (pytest)**:
- Unit tests for all major functions
- Table-driven parametrized tests for multiple scenarios
- Edge case coverage (invalid inputs, boundaries)
- Determinism verification (same input → same output)
- Purity verification (no side effects)

```python
CASES = [
    ("name", input1, input2, expected),
    ("another_case", input1, input2, expected),
]

@pytest.mark.parametrize("name,input1,input2,expected", CASES)
def test_function(name, input1, input2, expected):
    result = function(input1, input2)
    assert result == expected
```

**TypeScript (Jest)**:
- Component rendering tests
- Hook behavior tests
- Error handling tests
- Type safety (compiler enforces)

### 7. Code Organization

**Backend**:
```
backend/
  feature_service.py       # Pure domain logic
  test_feature_service.py  # Comprehensive tests
  server.py                # API endpoints (add to this)
```

**Frontend**:
```
frontend/app/
  hooks/
    useFeature.ts          # Hook for API calls
  components/
    FeatureScreen.tsx      # UI component
```

### 8. Logging Standards

Use consistent logging with feature prefixes:

```python
logger.info(f"[FEATURE] Starting operation")
logger.warning(f"[FEATURE] Unusual condition: {detail}")
logger.error(f"[FEATURE] Error: {detail}")

# Premium features
logger.info(f"[PREMIUM] Subscription validated")
logger.info(f"[PREMIUM] Access denied - premium required")
```

### 9. API Response Pattern

All responses should be consistent:

```python
@dataclass(frozen=True)
class FeatureResponse:
    # Common fields
    success: bool
    message: str
    
    # For premium features
    is_premium_locked: bool = False
    premium_message: Optional[str] = None
    
    # Feature-specific data
    data: Optional[FeatureResult] = None
```

Frontend handles:
```typescript
if (response.is_premium_locked) {
    setShowPaywall(true);
    setError(response.premium_message);
} else if (!response.success) {
    setError(response.message);
} else {
    setResult(response.data);
}
```

### 10. Documentation Standards

Every feature needs:
1. **Feature Guide** - What it does, scoring algorithm, examples
2. **API Reference** - Endpoint, request/response models
3. **Integration Guide** - How to use the hook/component
4. **Real-world Examples** - Actual usage scenarios
5. **Troubleshooting** - Common issues and solutions

## Code Quality Checklist

- [ ] All functions have type hints
- [ ] All inputs are validated
- [ ] All errors are handled with informative messages
- [ ] All domain logic is pure (no side effects)
- [ ] All data is immutable (frozen dataclasses)
- [ ] All features have comprehensive tests
- [ ] All premium features check subscription status
- [ ] All endpoints return consistent response format
- [ ] All logging uses appropriate prefixes
- [ ] All code has clear comments for complex logic
- [ ] All documentation is complete and current

## Anti-Patterns

❌ **Never do this**:
1. Direct DB access from pure functions
2. Modifying input parameters
3. Using global variables
4. Hardcoding config values
5. Skipping error handling
6. Silent failures
7. Mixing business logic with transport logic
8. Untested code paths
9. Inconsistent error messages
10. Hardcoding premium features without gating

## Performance Guidelines

- Pure functions: < 1ms
- API endpoints: < 100ms (including DB queries)
- Frontend renders: < 16ms (60 FPS)
- Database queries: Use indexes, pagination

## Security Guidelines

- ✅ Always validate subscription IDs
- ✅ Always sanitize user input
- ✅ Always use type hints
- ✅ Always handle errors gracefully
- ✅ Always log access to premium features
- ❌ Never expose internal errors to users
- ❌ Never skip authentication checks
- ❌ Never trust client-provided data blindly

## Monitoring & Analytics

Premium features should log:
- Who accessed the feature (subscription_id)
- When they accessed it (timestamp)
- What they were doing (action)
- Whether access was granted (success/denied)

This data helps with:
- Usage analytics
- Feature adoption tracking
- Identifying usage patterns
- Detecting anomalies

## Communication

- Use `[FEATURE]` prefix for feature-specific logs
- Use `[PREMIUM]` prefix for premium-only logs
- Use `[ERROR]` prefix for errors
- Use `[WARNING]` prefix for warnings

Example:
```
[PREMIUM] Subscription validated: routecast_pro_monthly
[FEATURE] Road assessment: score 45, mud_risk true
[WARNING] High-clearance vehicle recommended: 45cm needed
[ERROR] Invalid soil type: garbage
```
