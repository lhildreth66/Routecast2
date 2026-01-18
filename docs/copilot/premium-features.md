# Premium Features Implementation Guide

## Overview

Premium features in Routecast are gated behind the **Boondocking Pro** subscription. This guide explains how to properly implement premium-only features.

## Core Pattern

All premium features follow this three-layer architecture:

```
Frontend          Backend          Database
─────────────────────────────────────────────────
PaywallModal  ←→  Premium Gating  ←→  subscriptions
Component         Endpoint            Collection
```

## Step 1: Backend Domain Logic (Pure)

Create a pure domain service with **zero side effects**:

```python
# backend/feature_service.py
from dataclasses import dataclass

@dataclass(frozen=True)
class FeatureResult:
    score: float
    flags: Dict[str, bool]
    message: str

class FeatureService:
    @staticmethod
    def calculate(param1: float, param2: str) -> FeatureResult:
        """Pure function - no DB access, no mutations."""
        score = param1 * 100
        flags = {"flag1": param2 == "value"}
        return FeatureResult(score=score, flags=flags, message="OK")
```

### Key Rules
- ✅ Pure functions only
- ✅ Immutable data (frozen dataclasses)
- ✅ Full type hints
- ✅ Input validation before logic
- ✅ Deterministic (same input → same output)
- ❌ No database access
- ❌ No file I/O
- ❌ No random() or time-based logic

## Step 2: Unit Tests (Comprehensive)

Test every major function with parametrized table-driven tests:

```python
# backend/test_feature_service.py
import pytest
from feature_service import FeatureService

class TestFeatureCalculation:
    CASES = [
        ("case1", 10.0, "value", 1000.0),
        ("case2", 5.0, "value", 500.0),
        ("case3", 0.0, "other", 0.0),
    ]
    
    @pytest.mark.parametrize("name,param1,param2,expected_score", CASES)
    def test_calculate(self, name, param1, param2, expected_score):
        result = FeatureService.calculate(param1, param2)
        assert result.score == expected_score, f"Failed on {name}"
    
    def test_invalid_param1_negative(self):
        """Test that negative param1 is rejected."""
        with pytest.raises(ValueError):
            FeatureService.calculate(-5.0, "value")
    
    def test_determinism_100_iterations(self):
        """Verify deterministic behavior."""
        results = [
            FeatureService.calculate(10.0, "value").score
            for _ in range(100)
        ]
        assert len(set(results)) == 1, "Results should be identical"

# Run tests
# pytest test_feature_service.py -v
```

### Test Requirements
- ✅ Minimum 3 test cases per function
- ✅ Invalid input cases (expect ValueError)
- ✅ Edge cases (0, negative, max values)
- ✅ Determinism test (100 iterations identical)
- ✅ Expected test naming: `test_action_expected_result`

## Step 3: API Endpoint (With Gating)

Create FastAPI endpoint that validates subscription:

```python
# In backend/server.py

from pydantic import BaseModel
from feature_service import FeatureService

# Models
class FeatureRequest(BaseModel):
    param1: float
    param2: str
    subscription_id: Optional[str] = None

class FeatureResponse(BaseModel):
    score: Optional[float] = None
    flags: Optional[Dict[str, bool]] = None
    message: Optional[str] = None
    
    # Premium gating fields
    is_premium_locked: bool = False
    premium_message: Optional[str] = None

# Endpoint
@api_router.post("/pro/feature-name", response_model=FeatureResponse)
async def pro_feature_endpoint(request: FeatureRequest):
    """
    Premium feature endpoint.
    
    Requires active Routecast Pro subscription.
    Returns premium-locked response if not authorized.
    """
    logger.info(f"[PREMIUM] Feature endpoint accessed")
    
    # Validate subscription
    is_authorized = False
    if request.subscription_id:
        subscription = await db.subscriptions.find_one({
            'subscription_id': request.subscription_id,
            'status': 'active'
        })
        is_authorized = subscription is not None
    
    # If not authorized, return premium-locked response
    if not is_authorized:
        logger.info(f"[PREMIUM] Access denied - subscription required")
        return FeatureResponse(
            is_premium_locked=True,
            premium_message="Upgrade to Routecast Pro to unlock this feature"
        )
    
    # Authorized - call domain service
    try:
        logger.info(f"[PREMIUM] Computing feature for: {request.subscription_id}")
        
        result = FeatureService.calculate(
            request.param1,
            request.param2
        )
        
        logger.info(f"[PREMIUM] Feature completed successfully")
        
        return FeatureResponse(
            score=result.score,
            flags=result.flags,
            message=result.message,
            is_premium_locked=False
        )
    
    except ValueError as e:
        logger.error(f"[FEATURE] Invalid input: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[PREMIUM] Unexpected error: {e}")
        raise HTTPException(status_code=500, detail="Unable to compute feature")
```

### Endpoint Checklist
- ✅ Path: `/api/pro/feature-name`
- ✅ Method: POST
- ✅ Request model includes `subscription_id: Optional[str]`
- ✅ Response model includes `is_premium_locked: bool`
- ✅ Subscription validation against `db.subscriptions`
- ✅ Check for both `subscription_id` and `status: 'active'`
- ✅ Return premium-locked if not authorized
- ✅ Log with `[PREMIUM]` prefix
- ✅ Input validation with 400 error
- ✅ Error handling with 500 fallback

## Step 4: Frontend Hook (Type-Safe)

Create React hook that calls the endpoint:

```typescript
// frontend/app/hooks/useFeatureName.ts

import { useState } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { API_BASE } from '../apiConfig';

export interface FeatureRequest {
  param1: number;
  param2: string;
  subscription_id?: string;
}

export interface FeatureResponse {
  score?: number;
  flags?: Record<string, boolean>;
  message?: string;
  is_premium_locked: boolean;
  premium_message?: string;
}

export interface UseFeatureReturn {
  assess: (request: FeatureRequest) => Promise<FeatureResponse>;
  loading: boolean;
  error: string | null;
  result: FeatureResponse | null;
  clearResult: () => void;
}

export const useFeatureName = (): UseFeatureReturn => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<FeatureResponse | null>(null);

  const assess = async (request: FeatureRequest): Promise<FeatureResponse> => {
    setLoading(true);
    setError(null);

    try {
      // Get subscription ID from storage if not provided
      let subscriptionId = request.subscription_id;
      if (!subscriptionId) {
        subscriptionId = await AsyncStorage.getItem(
          'routecast_subscription_id'
        );
      }

      const response = await fetch(`${API_BASE}/api/pro/feature-name`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          param1: request.param1,
          param2: request.param2,
          subscription_id: subscriptionId,
        }),
      });

      if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
      }

      const data: FeatureResponse = await response.json();

      // Handle premium lock
      if (data.is_premium_locked) {
        setError(
          data.premium_message ||
          'This feature requires Routecast Pro. Upgrade to unlock.'
        );
      }

      setResult(data);
      return data;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unknown error';
      setError(message);
      console.error('[Feature] Error:', message);
      throw err;
    } finally {
      setLoading(false);
    }
  };

  const clearResult = () => {
    setResult(null);
    setError(null);
  };

  return { assess, loading, error, result, clearResult };
};
```

### Hook Checklist
- ✅ Exports typed interfaces
- ✅ Exports hook function
- ✅ State: loading, error, result
- ✅ Function: assess(request)
- ✅ Automatic subscription ID retrieval from AsyncStorage
- ✅ Handles `is_premium_locked` response
- ✅ Error handling with setError()
- ✅ Try/catch/finally structure
- ✅ JSDoc comments

## Step 5: Frontend Component (With Paywall)

Create UI component that integrates everything:

```typescript
// frontend/app/components/FeatureScreen.tsx

import React, { useState } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  ScrollView,
  ActivityIndicator,
  Alert,
  StyleSheet,
} from 'react-native';
import { useFeatureName } from '../hooks/useFeatureName';
import { usePremium } from '../hooks/usePremium';
import { PaywallModal } from './PaywallModal';

const FeatureScreen: React.FC = () => {
  const { assess, loading, error, result, clearResult } = useFeatureName();
  const { subscriptionId } = usePremium();
  
  const [showPaywall, setShowPaywall] = useState(false);
  const [param1, setParam1] = useState(10);
  const [param2, setParam2] = useState('value');

  const handleAssess = async () => {
    try {
      const response = await assess({
        param1,
        param2,
        subscription_id: subscriptionId || undefined,
      });

      // Handle premium lock
      if (response.is_premium_locked) {
        setShowPaywall(true);
        return;
      }

      // Display results
      if (response.score !== undefined) {
        Alert.alert(
          'Feature Result',
          `Score: ${response.score}\n${response.message}`
        );
      }
    } catch (err) {
      Alert.alert('Error', error || 'Failed to assess');
    }
  };

  return (
    <ScrollView style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <Text style={styles.title}>Feature Assessment</Text>
      </View>

      {/* Input Controls */}
      <View style={styles.section}>
        <Text style={styles.label}>Parameter 1: {param1}</Text>
        <View style={styles.buttonRow}>
          <TouchableOpacity onPress={() => setParam1(Math.max(0, param1 - 1))}>
            <Text style={styles.button}>−</Text>
          </TouchableOpacity>
          <TouchableOpacity onPress={() => setParam1(param1 + 1)}>
            <Text style={styles.button}>+</Text>
          </TouchableOpacity>
        </View>
      </View>

      {/* Assess Button */}
      <TouchableOpacity
        style={[styles.assessButton, loading && styles.disabled]}
        onPress={handleAssess}
        disabled={loading}
      >
        {loading ? (
          <ActivityIndicator size="small" color="#fff" />
        ) : (
          <Text style={styles.assessText}>Assess</Text>
        )}
      </TouchableOpacity>

      {/* Error Display */}
      {error && (
        <View style={styles.errorBox}>
          <Text style={styles.errorText}>{error}</Text>
          {error.includes('premium') && (
            <TouchableOpacity onPress={() => setShowPaywall(true)}>
              <Text style={styles.upgradeText}>Upgrade Now</Text>
            </TouchableOpacity>
          )}
        </View>
      )}

      {/* Results Display */}
      {result && !result.is_premium_locked && (
        <View style={styles.resultsBox}>
          <Text style={styles.resultText}>
            Score: {result.score}
          </Text>
          <Text style={styles.resultText}>
            {result.message}
          </Text>
        </View>
      )}

      {/* Paywall Modal */}
      <PaywallModal visible={showPaywall} onClose={() => setShowPaywall(false)} />
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#fff', padding: 20 },
  header: { marginBottom: 30 },
  title: { fontSize: 24, fontWeight: '700' },
  section: { marginBottom: 20 },
  label: { fontSize: 14, fontWeight: '500', marginBottom: 10 },
  buttonRow: { flexDirection: 'row', gap: 8 },
  button: { padding: 8, backgroundColor: '#f0f0f0', borderRadius: 4 },
  assessButton: { backgroundColor: '#3b82f6', padding: 12, borderRadius: 8, alignItems: 'center', marginBottom: 20 },
  assessText: { color: '#fff', fontWeight: '600' },
  disabled: { opacity: 0.5 },
  errorBox: { backgroundColor: '#fee', padding: 12, borderRadius: 6, marginBottom: 20 },
  errorText: { color: '#c00', marginBottom: 8 },
  upgradeText: { color: '#fff', backgroundColor: '#c00', padding: 8, borderRadius: 4, textAlign: 'center' },
  resultsBox: { backgroundColor: '#f0f9ff', padding: 12, borderRadius: 6 },
  resultText: { color: '#0c4a6e', marginBottom: 4 },
});

export default FeatureScreen;
```

### Component Checklist
- ✅ Uses hook for API calls
- ✅ Uses usePremium for subscription ID
- ✅ Input controls for parameters
- ✅ Loading state management
- ✅ Error display
- ✅ Premium paywall modal integration
- ✅ Results display
- ✅ Responsive design
- ✅ Touch targets > 44x44pt
- ✅ Accessible text

## Step 6: Testing

### Backend
```bash
cd backend
python -m pytest test_feature_service.py -v
# Expected: 30+ tests passing
```

### Frontend
```bash
cd frontend
npm test -- useFeatureName
# Expected: Component renders, hook works
```

### Manual Testing
1. Launch app without subscription → Should show paywall
2. Activate pro subscription → Should call endpoint
3. Endpoint should validate subscription → Should allow access
4. Results should display → Should show data
5. Toggle premium → Should gate/ungated correctly

## Step 7: Documentation

Create `FEATURE_NAME.md` documenting:

```markdown
# Feature Name

## Overview
[What it does, how it helps users]

## Algorithm
[How scoring works]

## API Endpoint
POST /api/pro/feature-name
Request: {...}
Response: {...}

## Frontend Integration
[How to use the hook]

## Examples
[Real-world scenarios]

## Troubleshooting
[Common issues]
```

## Verification Checklist

Before submitting, verify:

- [ ] Pure domain service with no side effects
- [ ] 30+ unit tests with full coverage
- [ ] All tests passing
- [ ] API endpoint with subscription gating
- [ ] Premium-locked response if unauthorized
- [ ] Frontend hook with proper types
- [ ] Component with paywall integration
- [ ] Error handling on all paths
- [ ] Logging with `[PREMIUM]` prefix
- [ ] Documentation complete
- [ ] Manual testing confirms gating works
- [ ] Code review approved

## Monitoring Premium Access

After deployment, monitor:

```
Logs to watch:
- [PREMIUM] Feature accessed: count, who, when
- [PREMIUM] Access denied: how many blocked
- [PREMIUM] Features executed: performance metrics
```

Use for:
- Adoption tracking
- Feature usage analytics
- Performance monitoring
- Issue detection

## Common Mistakes (Don't Do These!)

❌ **Accessing DB from pure functions**
```python
# BAD - Don't do this!
def calculate(param):
    db.log_access()  # Side effect!
    return result
```

❌ **Forgetting premium check**
```python
# BAD - Anyone can access!
@api_router.post("/pro/feature")
async def endpoint(request: Request):
    result = calculate(request.param)  # No gating!
    return result
```

❌ **Not handling premium lock on frontend**
```typescript
// BAD - Crashes if premium_locked
const { score } = result;  // May be undefined!
```

❌ **No error handling**
```python
# BAD - Silent failure
def calculate(param):
    return param / param  # Divides by zero silently!
```

✅ **Do this instead**:
```python
# GOOD - Pure, tested, gated
def calculate(param: float) -> Result:
    if param == 0:
        raise ValueError("param cannot be zero")
    return Result(score=100.0 / param)

@api_router.post("/pro/feature")
async def endpoint(request: Request):
    # Check subscription first
    if not is_authorized:
        return Response(is_premium_locked=True)
    
    # Call domain service
    result = calculate(request.param)
    return Response(is_premium_locked=False, data=result)
```

## Next Steps

1. Create domain service with pure functions
2. Write comprehensive unit tests
3. Create API endpoint with gating
4. Create React hook with proper types
5. Build UI component with paywall
6. Document thoroughly
7. Test manually
8. Submit for review

---

**Remember**: Premium features are valuable. Implement them properly with clear gating, comprehensive testing, and excellent documentation. Users will thank you for the polish and reliability!
