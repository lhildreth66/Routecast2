# Project Map: Routecast2 Repository Structure

## Directory Layout

```
/workspaces/Routecast2/
├── backend/                          # FastAPI backend
│   ├── server.py                     # Main API server & routes
│   ├── requirements.txt               # Python dependencies
│   ├── *_service.py                  # Domain services (pure logic)
│   ├── test_*_service.py             # Unit tests (pytest)
│   └── bridge_database.py            # Bridge height warnings
│
├── frontend/                         # React Native + Expo app
│   ├── package.json                  # Dependencies
│   ├── tsconfig.json                 # TypeScript config
│   ├── app/
│   │   ├── index.tsx                 # Home screen
│   │   ├── route.tsx                 # Route display screen
│   │   ├── _layout.tsx               # Navigation layout
│   │   ├── hooks/
│   │   │   ├── usePremium.ts         # Premium status hook
│   │   │   └── useFeature.ts         # Feature hooks (add here)
│   │   ├── components/
│   │   │   ├── PaywallModal.tsx      # Premium paywall UI
│   │   │   └── FeatureScreen.tsx     # Feature components
│   │   ├── services/
│   │   │   ├── BillingService.ts     # Billing integration
│   │   │   └── apiConfig.ts          # API configuration
│   │   └── assets/
│   ├── android/                      # Android build config
│   └── ios/                          # iOS build config
│
├── docs/
│   └── copilot/                      # Copilot guidance
│       ├── README.md                 # This guide
│       ├── system-prompt.md          # Development principles
│       ├── project-map.md            # Repository structure
│       └── acceptance-criteria.md    # Feature definition checklist
│
├── tests/                            # Integration tests
│   └── __init__.py
│
└── [other files]
   ├── README.md
   ├── *.md                           # Feature documentation
   └── [config files]
```

## Key Files

### Backend Core

| File | Purpose | Key Content |
|------|---------|------------|
| `backend/server.py` | FastAPI app & routes | Endpoints, models, routers |
| `backend/requirements.txt` | Dependencies | pip packages (fastapi, motor, etc) |
| `backend/*_service.py` | Domain logic | Pure functions, algorithms |
| `backend/test_*_service.py` | Unit tests | pytest test cases |

### Frontend Core

| File | Purpose | Key Content |
|------|---------|------------|
| `frontend/app/index.tsx` | Home screen | Route input, vehicle selection |
| `frontend/app/route.tsx` | Route display | Weather, alerts, navigation |
| `frontend/app/hooks/usePremium.ts` | Premium state | Subscription status, feature gating |
| `frontend/app/hooks/useFeature.ts` | Feature hooks | API calls, loading, results |
| `frontend/app/components/PaywallModal.tsx` | Paywall UI | Premium gating modal |
| `frontend/app/services/apiConfig.ts` | API config | Backend URL, headers |

### Copilot Documentation

| File | Purpose |
|------|---------|
| `docs/copilot/README.md` | Quick start guide |
| `docs/copilot/system-prompt.md` | Core principles & patterns |
| `docs/copilot/project-map.md` | This file |
| `docs/copilot/acceptance-criteria.md` | Feature checklist |

## Backend Architecture

### API Structure
```
/api
  ├── /health                    # Health check
  ├── /route/weather            # Route analysis (FREE)
  ├── /routes/history           # Saved routes (FREE)
  ├── /routes/favorites         # Favorite routes (FREE)
  ├── /chat                      # AI chat (FREE)
  ├── /notifications            # Push notifications (FREE)
  ├── /billing/validate-subscription  # Subscription validation
  ├── /billing/features          # Feature gating info
  └── /pro/                      # Premium features (GATED)
      ├── /road-passability     # Road conditions assessment
      └── [other premium features]
```

### Database Schema

**subscriptions collection**:
```json
{
  "subscription_id": "routecast_pro_monthly",
  "status": "active",           // or "inactive", "cancelled"
  "created_at": "2024-01-15T10:00:00Z",
  "last_validated": "2024-01-18T14:30:00Z"
}
```

### Models & Types

**Request Models** (in `server.py`):
```python
class FeatureRequest(BaseModel):
    param1: float
    param2: str
    subscription_id: Optional[str] = None
```

**Response Models** (in `server.py`):
```python
class FeatureResponse(BaseModel):
    success: bool
    is_premium_locked: bool = False
    premium_message: Optional[str] = None
    data: Optional[FeatureResult] = None
```

**Domain Models** (in `*_service.py`):
```python
@dataclass(frozen=True)
class Result:
    score: float
    flags: Dict[str, bool]
    advisory: str
```

### Logging

All logs use prefixes:
- `[FEATURE]` - Feature-specific logic
- `[PREMIUM]` - Premium entitlement checks
- `[ROUTING]` - Route analysis
- `[BILLING]` - Subscription/billing
- `[ERROR]` - Error conditions

Example from `server.py`:
```python
logger.info(f"[PREMIUM] Road passability assessed: {score}")
logger.error(f"[FEATURE] Invalid input: {error}")
```

## Frontend Architecture

### Hook Pattern

All feature hooks follow this pattern:

```typescript
// hooks/useFeatureName.ts
export const useFeatureName = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<Result | null>(null);
  
  const assess = async (request: Request) => {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/api/pro/feature`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
      });
      
      if (!response.ok) throw new Error(...);
      
      const data = await response.json();
      if (data.is_premium_locked) {
        setError(data.premium_message);
      }
      setResult(data);
      return data;
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  };
  
  return { assess, loading, error, result };
};
```

### Component Pattern

Features typically have a dedicated screen:

```typescript
// components/FeatureScreen.tsx
export default function FeatureScreen() {
  const { assess, loading, result, error } = useFeatureName();
  const { isPremium } = usePremium();
  const [showPaywall, setShowPaywall] = useState(false);
  
  const handleAssess = async () => {
    try {
      const res = await assess({...});
      if (res.is_premium_locked) {
        setShowPaywall(true);
      }
    } catch (err) {
      Alert.alert('Error', error);
    }
  };
  
  return (
    <ScrollView style={styles.container}>
      {/* Input controls */}
      <TouchableOpacity onPress={handleAssess} disabled={loading}>
        <Text>Assess</Text>
      </TouchableOpacity>
      
      {result && !result.is_premium_locked && (
        <View>{/* Display results */}</View>
      )}
      
      <PaywallModal visible={showPaywall} onClose={...} />
    </ScrollView>
  );
}
```

### State Management

**Premium Status** (global):
```typescript
const { isPremium, subscriptionId } = usePremium();
```

**Feature State** (local):
```typescript
const { assess, loading, error, result } = useFeatureName();
```

**UI State** (component):
```typescript
const [showPaywall, setShowPaywall] = useState(false);
const [selectedOption, setSelectedOption] = useState('');
```

## Testing Strategy

### Backend (pytest)

Structure:
```python
# backend/test_*_service.py

class TestFunction1:
    CASES = [("name", input, expected), ...]
    
    @pytest.mark.parametrize("name,input,expected", CASES)
    def test_function(self, name, input, expected):
        result = function(input)
        assert result == expected

class TestFunction2:
    # Similar structure
    pass

class TestDeterminism:
    def test_100_iterations(self):
        results = [function() for _ in range(100)]
        assert len(set(results)) == 1  # All identical
```

Run with:
```bash
cd backend
python -m pytest test_*_service.py -v
```

### Frontend (Jest)

Structure:
```typescript
describe('Feature', () => {
  test('should render correctly', () => {
    const { getByText } = render(<FeatureScreen />);
    expect(getByText('Title')).toBeTruthy();
  });
  
  test('should handle error', async () => {
    // Mock fetch, test error handling
  });
});
```

Run with:
```bash
cd frontend
npm test
```

## Adding a New Feature

1. **Create Domain Service**
   - File: `backend/feature_service.py`
   - Pure functions, immutable data
   - No DB access from pure functions

2. **Create Tests**
   - File: `backend/test_feature_service.py`
   - Parametrized test cases
   - Edge case coverage
   - Determinism verification

3. **Create API Endpoint**
   - Update: `backend/server.py`
   - Add models to server.py
   - Add endpoint with gating (if premium)
   - Validate all inputs

4. **Create React Hook**
   - File: `frontend/app/hooks/useFeatureName.ts`
   - Call API endpoint
   - Handle loading/error/result states
   - Return typed interface

5. **Create UI Component**
   - File: `frontend/app/components/FeatureScreen.tsx`
   - Use hook for data
   - Display results
   - Handle paywall (if premium)

6. **Document**
   - Create `FEATURE_NAME.md`
   - Explain algorithm
   - Show API spec
   - Provide examples

7. **Test**
   - Run backend tests: `pytest test_feature_service.py -v`
   - Verify premium gating works
   - Test paywall UI
   - Validate types

## Common Patterns

### Input Validation
```python
def validate_input(request: Request) -> ValidationResult:
    if request.param < 0:
        raise ValueError("param must be positive")
    if not request.name:
        raise ValueError("name is required")
    return ValidationResult(is_valid=True, data=request)
```

### Premium Check
```python
is_authorized = request.subscription_id and await db.subscriptions.find_one({
    'subscription_id': request.subscription_id,
    'status': 'active'
})

if not is_authorized:
    return FeatureResponse(is_premium_locked=True, ...)
```

### Response Handling
```typescript
if (response.is_premium_locked) {
    setShowPaywall(true);
    return;
}

if (response.error) {
    setError(response.error);
    return;
}

setResult(response.data);
```

## Environment Variables

Backend (`.env`):
```
MONGO_URL=mongodb+srv://...
DB_NAME=routecast
MAPBOX_ACCESS_TOKEN=...
GOOGLE_API_KEY=...
NOAA_USER_AGENT=...
```

Frontend (`.env.local`):
```
EXPO_PUBLIC_BACKEND_URL=http://localhost:8000
EXPO_PUBLIC_GOOGLE_API_KEY=...
```

## Deployment

**Backend**:
- Deployed on cloud platform (AWS/GCP/Azure)
- FastAPI runs on port 8000
- MongoDB Atlas for database
- Environment variables set in cloud

**Frontend**:
- Built via Expo
- APK for Android
- AAB for Play Store
- IPA for iOS
- Testflight for beta testing

## Useful Commands

```bash
# Backend
cd backend
pip install -r requirements.txt
python -m pytest test_*.py -v
python server.py

# Frontend
cd frontend
npm install
npm start  # Expo dev server
npm test   # Jest

# Git
git log --oneline -10
git add .
git commit -m "feat: description"
git push
```

## Common Issues & Solutions

| Issue | Solution |
|-------|----------|
| "Module not found" | `cd backend && pip install -r requirements.txt` |
| "Port already in use" | `lsof -i :8000` then kill process |
| "DB connection failed" | Check MONGO_URL in .env |
| "API returns 404" | Check endpoint path, restart server |
| "Frontend fetch fails" | Check EXPO_PUBLIC_BACKEND_URL |
| "Test fails locally but passes in CI" | Check environment variables |
| "Premium gating not working" | Verify subscription_id is in DB |

## Next Steps

1. Read [system-prompt.md](./system-prompt.md) for principles
2. Review [acceptance-criteria.md](./acceptance-criteria.md) for requirements
3. Check existing features (e.g., Road Passability) as examples
4. Create feature following the patterns here
5. Test thoroughly before submitting
6. Document clearly for future maintenance
