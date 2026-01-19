# Test Fixtures

This directory contains deterministic test fixtures for Routecast2 unit and integration tests.

## Quick Reference

### Generated Files

- **19 fixture files** across 5 categories
- **388 KB total** (compressed JSON)
- All fixtures are **versioned** (v1.0) and **deterministic**

### Categories

```
fixtures/
├── weather/           (3 files, 64KB)  - 3-day hourly forecasts
├── terrain/           (2 files, 256KB) - DEM elevation grids
├── soil/              (3 files, 16KB)  - Soil type characteristics
├── connectivity/      (9 files, 40KB)  - Tower distance × canopy cover
└── trips/             (2 files, 12KB)  - Route geometries
```

## Usage

### Python

```python
import json
from pathlib import Path

# Load a fixture
def load_fixture(category: str, filename: str):
    path = Path(__file__).parent / "fixtures" / category / filename
    with open(path) as f:
        return json.load(f)

# Example
weather = load_fixture("weather", "weather_storm.json")
soil = load_fixture("soil", "soil_clay.json")
```

### TypeScript/JavaScript

```typescript
import weatherStorm from './fixtures/weather/weather_storm.json';
import soilClay from './fixtures/soil/soil_clay.json';
```

## Fixture Index

### Weather (72-hour forecasts)

| File | Scenario | Temp (°F) | Precip | Wind | Visibility |
|------|----------|-----------|--------|------|------------|
| `weather_clear.json` | Clear skies | 65-75 | 0.0" | 5-15 mph | 10 mi |
| `weather_partly_cloudy.json` | Variable clouds | 55-70 | 0-0.1" | 10-20 mph | 5-8 mi |
| `weather_storm.json` | Severe weather | 32-45 | 0.2-0.8" | 25-45 mph | 0.5-2 mi |

**Use Cases**: Road passability, smart delay, solar forecast, battery planning

---

### Terrain (100×100 grids)

| File | Type | Elevation | Gradient | Use Case |
|------|------|-----------|----------|----------|
| `terrain_flat.json` | Flat | 100-105m | <2% | Baseline, paved roads, solar |
| `terrain_hilly.json` | Hilly | 100-300m | 5-15% | Mountain routes, obstructions |

**Use Cases**: Road passability, Starlink obstruction, battery consumption

---

### Soil (3 types)

| File | Type | Drainage | Compaction | Dry Score | Wet Penalty |
|------|------|----------|------------|-----------|-------------|
| `soil_sand.json` | Sand | 0.9 | 0.3 | 60 | 0.8× |
| `soil_loam.json` | Loam | 0.6 | 0.7 | 85 | 0.5× |
| `soil_clay.json` | Clay | 0.2 | 0.9 | 90 | 0.1× |

**Use Cases**: Road passability (wet conditions), recovery time estimation

---

### Connectivity (9 scenarios)

| Tower Distance | Canopy | Signal (dBm) | Quality | Starlink | Speed |
|----------------|--------|--------------|---------|----------|-------|
| 1 km | 0% | -65 | Excellent | 0% | 50 Mbps |
| 1 km | 40% | -72 | Good | 15% | 35 Mbps |
| 1 km | 80% | -85 | Fair | 40% | 15 Mbps |
| 5 km | 0% | -85 | Good | 0% | 25 Mbps |
| 5 km | 40% | -95 | Fair | 15% | 12 Mbps |
| 5 km | 80% | -105 | Poor | 40% | 3 Mbps |
| 15 km | 0% | -105 | Fair | 0% | 8 Mbps |
| 15 km | 40% | -112 | Poor | 15% | 2 Mbps |
| 15 km | 80% | -118 | None | 40% | 0 Mbps |

**Use Cases**: Connectivity prediction, signal quality assessment

---

### Trips (2 routes)

| File | Type | Length | Duration | Speed | Difficulty |
|------|------|--------|----------|-------|------------|
| `trip_paved_highway.json` | Paved | 150 km | 90 min | 100 km/h | Easy |
| `trip_sandy_forest.json` | Sand | 25 km | 90 min | 16.7 km/h | Difficult |

**Use Cases**: Route planning, battery consumption, travel time estimation

---

## Regenerating Fixtures

To regenerate all fixtures (after modifying the script):

```bash
cd /workspaces/Routecast2
python scripts/generate_fixtures.py
```

This will:
- ✅ Generate all 19 fixture files
- ✅ Ensure deterministic, reproducible data
- ✅ Version all fixtures (v1.0)
- ✅ Validate JSON structure

## Fixture Principles

1. **Deterministic**: Same script run → same output
2. **No Randomness**: All variations use mathematical functions (sin, cos)
3. **No Live Data**: All values are synthetic
4. **Versioned**: Each fixture includes `"version": "1.0"`
5. **Documented**: All fixtures documented in `docs/copilot/test-data.md`

## Test Coverage

| Feature | Fixtures Used | Test File |
|---------|---------------|-----------|
| Road Passability | weather_*, soil_*, trip_* | `test_road_passability_service.py` |
| Smart Delay | weather_storm, trip_* | `test_notifications_smart_delay.py` |
| Solar Forecast | weather_clear, weather_partly_cloudy | TBD |
| Connectivity | connectivity_*, terrain_* | TBD |
| Battery Planning | weather_*, trip_*, terrain_hilly | TBD |
| Campsite Quality | terrain_*, soil_*, connectivity_* | TBD |

## Documentation

- **Full Docs**: `docs/copilot/test-data.md`
- **Generator Script**: `scripts/generate_fixtures.py`
- **Acceptance Criteria**: `docs/copilot/acceptance-criteria.md`

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-01-18 | Initial fixture generation |

---

**Maintained by**: Engineering Team  
**Last Generated**: January 18, 2026
