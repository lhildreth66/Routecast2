# Road Passability - Quick Reference

## 🎯 What It Does

Assesses whether roads are passable based on:
- **Weather**: 72-hour precipitation (mm)
- **Terrain**: Road grade/slope (%)
- **Temperature**: Minimum temp (°F)
- **Soil Type**: clay, sand, rocky, or loam

Returns:
- **Score**: 0-100 (Impassable → Excellent)
- **Risks**: Mud, ice, ruts, clearance, 4WD needs
- **Recommendations**: Vehicle type & ground clearance

## 🔐 Premium Feature

Requires active `routecast_pro_monthly` or `routecast_pro_annual` subscription.

## 📍 Endpoints

### Backend Service
```python
from road_passability_service import RoadPassabilityService

result = RoadPassabilityService.assess_road_passability(
    precip_72h=50,    # mm
    slope_pct=8,      # %
    min_temp_f=28,    # °F
    soil_type="clay"  # str
)
```

### API Endpoint
```
POST /api/pro/road-passability

Request:
{
  "precip_72h": 50,
  "slope_pct": 8,
  "min_temp_f": 28,
  "soil_type": "clay",
  "subscription_id": "routecast_pro_monthly"
}

Response (if authorized):
{
  "passability_score": 20.0,
  "condition_assessment": "Impassable",
  "advisory": "🚫 Road impassable. Extreme conditions. Do not attempt.",
  "min_clearance_cm": 45,
  "recommended_vehicle_type": "4x4",
  "needs_four_x_four": true,
  "risks": {...},
  "is_premium_locked": false
}

Response (if premium locked):
{
  "is_premium_locked": true,
  "premium_message": "Requires Routecast Pro..."
}
```

### Frontend Hook
```typescript
import { useRoadPassability } from './hooks/useRoadPassability';

const { assess, loading, error, result } = useRoadPassability();

const response = await assess({
  precip_72h: 50,
  slope_pct: 8,
  min_temp_f: 28,
  soil_type: 'clay'
});

if (response.is_premium_locked) {
  // Show paywall modal
}
```

## 📊 Scoring Examples

| Conditions | Score | Assessment | Advisory |
|-----------|-------|------------|----------|
| Clay + 50mm rain + gentle slope | 20 | Impassable | 🚫 Don't attempt |
| Loam + freeze-thaw + moderate slope | 45 | Poor | ❌ Challenging |
| Sand + dry + flat | 92 | Excellent | ✅ Well-maintained |
| Rocky + wet + flat | 85 | Excellent | ✅ Drains well |

## ⚠️ Risk Flags

- `mud_risk`: true if soil saturated/wet + slope ≤ 10%
- `ice_risk`: true if temp ≤ 32°F + precipitation > 0mm
- `deep_rut_risk`: true if wet soil + slope ≥ 12%
- `high_clearance_recommended`: true if need > 20cm
- `four_x_four_recommended`: true if score < 60 OR slope > 15%

## 🚗 Vehicle Recommendations

- **Sedan**: Score ≥ 80 (dry, flat, excellent)
- **SUV**: Score 60-79 (good, some challenges)
- **4x4**: Score < 60 (poor conditions, 4WD recommended)

## 📈 Ground Clearance

Calculated from moisture level + slope:

```
Base: 15cm
Moisture adjustment:  dry +0cm, moist +5cm, wet +10cm, saturated +25cm
Slope adjustment:     flat +0cm, moderate +3cm, steep +8cm
```

Range: 15-60cm

## 🧪 Testing

```bash
# Run all tests
cd backend
python -m pytest test_road_passability_service.py -v

# Run specific test class
pytest test_road_passability_service.py::TestPassabilityScore -v

# Run with coverage
pytest test_road_passability_service.py --cov=road_passability_service
```

**Result**: 63 tests, all passing ✅

## 🔧 Implementation Checklist

To add road passability to a screen:

- [ ] Import `useRoadPassability` hook
- [ ] Create state for input parameters
- [ ] Call `assess()` with parameters
- [ ] Handle `loading` state with spinner
- [ ] Check `result.is_premium_locked` for paywall
- [ ] Display results with color-coding
- [ ] Handle errors with retry option

## 📚 Documentation

- **Full Guide**: [ROAD_PASSABILITY_FEATURE.md](ROAD_PASSABILITY_FEATURE.md)
- **Implementation Summary**: [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)
- **Backend Code**: [backend/road_passability_service.py](backend/road_passability_service.py)
- **Tests**: [backend/test_road_passability_service.py](backend/test_road_passability_service.py)
- **Frontend Hook**: [frontend/app/hooks/useRoadPassability.ts](frontend/app/hooks/useRoadPassability.ts)
- **Example Component**: [frontend/app/components/RoadPassabilityScreen.tsx](frontend/app/components/RoadPassabilityScreen.tsx)

## ⚡ Key Features

✅ **Pure Functions**: No side effects, fully deterministic
✅ **63 Tests**: All passing, comprehensive coverage
✅ **Premium Gated**: Subscription validation included
✅ **Type Safe**: Full TypeScript + Python typing
✅ **Production Ready**: Error handling, logging, validation
✅ **Scalable**: Parametrized tests for easy expansion
✅ **Documented**: Reference-quality documentation

## 🐛 Troubleshooting

**Q: Getting premium-locked response?**
A: Ensure subscription_id is passed and exists in db.subscriptions with status='active'

**Q: Score doesn't match expected value?**
A: Review scoring algorithm in ROAD_PASSABILITY_FEATURE.md - check specific deductions for your conditions

**Q: Tests failing?**
A: Run `pytest test_road_passability_service.py -v --tb=short` to see detailed errors

**Q: Need to modify scoring?**
A: Update coefficients in RoadPassabilityService.calculate_passability_score() and adjust test expectations

## 📞 Questions?

Refer to:
1. [ROAD_PASSABILITY_FEATURE.md](ROAD_PASSABILITY_FEATURE.md) - Comprehensive reference
2. [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) - Architecture & design
3. Test cases in `test_road_passability_service.py` - Real examples
4. Example component - Usage patterns

---

**Status**: ✅ Production Ready
**Tests**: 63 passing
**Version**: 1.0
