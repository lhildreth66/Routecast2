# Premium Feature Tasks

This document tracks premium feature implementations for Routecast Pro (Boondocking Pro).

## Task A1: Solar Forecast

**Status**: In Progress

**Description**: Implement solar energy forecasting for boondocking users to estimate daily solar generation at their current or planned location.

**Category**: Boondocking Pro / Premium Feature

### Requirements

**Inputs**:
- `lat` (float): Latitude (-90 to 90)
- `lon` (float): Longitude (-180 to 180)
- `date_range` (list[str]): ISO format dates (e.g., ["2026-01-20", "2026-01-21"])
- `panel_watts` (float): Solar panel capacity in watts (>0)
- `shade_pct` (float): Average shade percentage (0-100)
- `cloud_cover` (list[float]): Cloud cover percentages per day (0-100)

**Logic**:
1. Calculate clear-sky baseline Wh/day based on latitude and date (using solar irradiance model)
2. Apply cloud cover multiplier: 0.2-1.0 range (full overcast = 0.2, clear = 1.0)
3. Apply shade loss: `(100 - shade_pct) / 100`
4. Result: `clear_sky_baseline × cloud_multiplier × shade_loss × panel_watts / 1000`

**Output**:
- `Wh/day` list (one per date in date_range)
- Each value clamped to realistic range

**Premium Gating**:
- Only available to users with active Boondocking Pro subscription
- Return premium-locked response if user is not authorized
- Trigger PaywallModal on frontend

### Implementation Checklist

**Backend**:
- [ ] `backend/solar_forecast_service.py` (pure domain logic)
  - [ ] `calculate_clear_sky_baseline(lat: float, doy: int) -> float`
  - [ ] `calculate_cloud_multiplier(cloud_cover: float) -> float`
  - [ ] `calculate_shade_loss(shade_pct: float) -> float`
  - [ ] `forecast_daily_wh(lat, lon, date_range, panel_watts, shade_pct, cloud_cover) -> list[float]`
  - [ ] All functions pure and deterministic
  - [ ] Full type hints
  - [ ] Input validation with clear error messages

- [ ] `backend/test_solar_forecast_service.py` (comprehensive tests)
  - [ ] Minimum 3 test cases per function
  - [ ] Table-driven parametrized tests
  - [ ] Edge cases: full overcast, no shade, maximum shade, zero panels
  - [ ] Invalid inputs: negative shade, negative panel_watts, empty dates, wrong cloud array length
  - [ ] Boundary conditions: lat=90, lat=-90, lon=0, lon=180
  - [ ] Determinism test: 100 iterations identical

- [ ] API endpoint: `POST /api/pro/solar-forecast`
  - [ ] `SolarForecastRequest` model with subscription_id
  - [ ] `SolarForecastResponse` model with is_premium_locked
  - [ ] Subscription validation
  - [ ] Premium-locked response if unauthorized
  - [ ] Logging with `[PREMIUM]` prefix
  - [ ] Error handling (400 for validation, 500 for errors)

**Frontend**:
- [ ] `frontend/app/hooks/useSolarForecast.ts`
  - [ ] `SolarForecastRequest` interface
  - [ ] `SolarForecastResponse` interface
  - [ ] `UseSolarForecastReturn` interface
  - [ ] `useSolarForecast()` hook
  - [ ] State: loading, error, result
  - [ ] Subscription ID retrieval from AsyncStorage

- [ ] `frontend/app/components/SolarForecastScreen.tsx`
  - [ ] Input controls: lat/lon, date range, panel watts, shade %, cloud cover
  - [ ] Call hook and display results
  - [ ] Show loading indicator
  - [ ] Show errors clearly
  - [ ] Trigger PaywallModal when premium-locked
  - [ ] Responsive design

**Documentation**:
- [ ] Feature guide: `SOLAR_FORECAST_FEATURE.md`
- [ ] API reference
- [ ] Integration guide
- [ ] Real-world examples (RV solar setup, minimal panels, etc.)
- [ ] Troubleshooting guide

**Testing**:
- [ ] Backend: all pytest tests passing
- [ ] Frontend: hook renders, calls API, handles premium-locked
- [ ] Manual: gating works, paywall triggers

**Git & Commits**:
- [ ] Clean atomic commits
- [ ] Clear commit messages
- [ ] Feature branch or PR-sized work

---

## Implementation Notes

### Solar Model Details

The clear-sky baseline uses a simplified solar irradiance model:

```
Peak irradiance (W/m²): 1000 W/m²
Elevation angle at solar noon (degrees): arcsin(sin(lat) × sin(declination) + cos(lat) × cos(declination))
Day length hours: varies by latitude and date
Simplified baseline: ~5.5 peak sun hours / day at equator on equinox
Latitude adjustment: multiply by cos(latitude difference from equator)
Seasonal adjustment: declination varies ~23.5° throughout year
```

For implementation, use a reasonable approximation based on:
- Latitude (higher = less summer sun, more winter variation)
- Day of year (seasonal variation)
- Standard 5.5 peak sun hours baseline at 0° latitude, 0° day-of-year

### Cloud Cover Multiplier

- 0% cloud = 1.0 (clear day, full sun)
- 30% cloud = 0.8 (mostly clear)
- 60% cloud = 0.5 (partly cloudy)
- 90% cloud = 0.2 (mostly overcast)
- 100% cloud = 0.2 (full overcast, use minimum)

Clamp to [0.2, 1.0] range.

### Example Scenario

RV in Arizona (lat=34.05, lon=-111.03) on Jan 20 with:
- 400W solar panels
- 20% average shade from awning/trees
- Forecast: Clear (cloud=0%), Partly cloudy (cloud=40%), Overcast (cloud=90%)

Expected output (Wh/day):
- Clear day: ~1800 Wh
- Partly cloudy: ~1400 Wh
- Overcast: ~700 Wh

### Follow Copilot Standards

All code must follow:
- `system-prompt.md`: Pure functions, immutable data, type safety
- `premium-features.md`: Seven-step implementation pattern
- `acceptance-criteria.md`: Code quality, testing, documentation
- `project-map.md`: Repository structure and conventions

---

## Other Premium Features (Planned)

- **Task A2**: Wind Speed Forecast
- **Task A3**: Weather-Based Route Recommendations
- **Task B1**: Offline Map Downloads
- **Task C1**: Trip Planning & Optimization

---

