# Test Data & Fixtures

**Project**: Routecast2  
**Version**: 1.0.8  
**Last Updated**: January 18, 2026

This document defines the test fixtures used throughout the codebase for reliable, deterministic testing. All fixtures are **synthetic and reproducible** - no live data, no randomness, no network dependencies.

---

## Table of Contents

1. [Weather Fixtures](#weather-fixtures)
2. [Terrain Fixtures](#terrain-fixtures)
3. [Soil Fixtures](#soil-fixtures)
4. [Connectivity Fixtures](#connectivity-fixtures)
5. [Trip Fixtures](#trip-fixtures)
6. [Usage Guidelines](#usage-guidelines)
7. [Fixture File Locations](#fixture-file-locations)

---

## Weather Fixtures

### Overview

Weather fixtures provide 3-day (72-hour) hourly forecasts for various conditions. Each fixture contains 72 entries with consistent timestamps starting from `2026-01-20T00:00:00Z`.

### Format

Each weather entry contains:
```json
{
  "timestamp": "ISO 8601 datetime",
  "temperature": "number (°F)",
  "precipitation": "number (inches/hour)",
  "wind_speed": "number (mph)",
  "cloud_cover": "number (0-100%)",
  "visibility": "number (miles)",
  "conditions": "string (clear|cloudy|rain|snow)"
}
```

### Scenarios

#### Scenario 1: Clear
**File**: `fixtures/weather_clear.json`

**Characteristics**:
- Temperature: 65-75°F (mild variation)
- Precipitation: 0.0 inches/hour
- Wind speed: 5-15 mph (light breeze)
- Cloud cover: 0-20% (mostly clear)
- Visibility: 10 miles
- Conditions: "clear" or "partly_cloudy"

**Use Cases**:
- Baseline good weather tests
- Road passability (dry conditions)
- Solar forecast (high sun exposure)
- Safe departure timing

**Sample Entry**:
```json
{
  "timestamp": "2026-01-20T00:00:00Z",
  "temperature": 68,
  "precipitation": 0.0,
  "wind_speed": 8,
  "cloud_cover": 10,
  "visibility": 10,
  "conditions": "clear"
}
```

---

#### Scenario 2: Partly Cloudy
**File**: `fixtures/weather_partly_cloudy.json`

**Characteristics**:
- Temperature: 55-70°F (moderate variation)
- Precipitation: 0.0-0.1 inches/hour (occasional light drizzle)
- Wind speed: 10-20 mph (moderate breeze)
- Cloud cover: 30-60% (variable)
- Visibility: 5-8 miles
- Conditions: "partly_cloudy" or "cloudy"

**Use Cases**:
- Moderate solar forecast (partial sun exposure)
- Mild road conditions
- Battery planning with intermittent charging
- Borderline departure decisions

**Sample Entry**:
```json
{
  "timestamp": "2026-01-20T12:00:00Z",
  "temperature": 62,
  "precipitation": 0.05,
  "wind_speed": 15,
  "cloud_cover": 45,
  "visibility": 6,
  "conditions": "partly_cloudy"
}
```

---

#### Scenario 3: Storm
**File**: `fixtures/weather_storm.json`

**Characteristics**:
- Temperature: 32-45°F (cold)
- Precipitation: 0.2-0.8 inches/hour (heavy rain/snow)
- Wind speed: 25-45 mph (strong winds)
- Cloud cover: 80-100% (overcast)
- Visibility: 0.5-2 miles (low)
- Conditions: "rain" or "snow"

**Use Cases**:
- Smart delay notifications (dangerous conditions)
- Road passability (wet/icy surfaces)
- Battery planning (no solar charging)
- Risk assessment edge cases

**Sample Entry**:
```json
{
  "timestamp": "2026-01-20T18:00:00Z",
  "temperature": 35,
  "precipitation": 0.6,
  "wind_speed": 38,
  "cloud_cover": 95,
  "visibility": 1.2,
  "conditions": "snow"
}
```

---

## Terrain Fixtures

### Overview

Terrain fixtures provide Digital Elevation Model (DEM) data for different topographies. Each fixture is a 100x100 grid of elevation values.

### Format

```json
{
  "metadata": {
    "resolution": "number (meters per pixel)",
    "bounds": {
      "north": "latitude",
      "south": "latitude",
      "east": "longitude",
      "west": "longitude"
    },
    "width": 100,
    "height": 100,
    "units": "meters"
  },
  "elevations": [
    [/* row 0: 100 elevation values */],
    [/* row 1: 100 elevation values */],
    // ... 100 rows total
  ]
}
```

### Scenarios

#### Scenario 1: Flat Terrain
**File**: `fixtures/terrain_flat.json`

**Characteristics**:
- Elevation range: 100-105 meters (5m variation)
- Gradient: <2% (nearly flat)
- Suitable for: Paved roads, RV camping, solar installations

**Use Cases**:
- Baseline terrain tests
- Road passability (minimal slope impact)
- Starlink obstruction (open sky)
- Campsite quality (flat, stable)

**Elevation Pattern**:
```
100, 101, 100, 102, 101, 100, 103, 102, ... (minor variations)
```

**Bounds**:
```json
{
  "north": 40.0,
  "south": 39.9,
  "east": -105.0,
  "west": -105.1
}
```

---

#### Scenario 2: Hilly Terrain
**File**: `fixtures/terrain_hilly.json`

**Characteristics**:
- Elevation range: 100-300 meters (200m variation)
- Gradient: 5-15% (moderate slopes)
- Features: Rolling hills, valleys
- Suitable for: Unpaved roads, mountain routes

**Use Cases**:
- Road passability (steep slope penalties)
- Starlink obstruction (terrain blocking)
- Battery consumption (uphill travel)
- Campsite quality (slope assessment)

**Elevation Pattern**:
```
100, 110, 130, 160, 200, 240, 270, 290, 300, 280, 250, ... (hills and valleys)
```

**Bounds**:
```json
{
  "north": 39.8,
  "south": 39.7,
  "east": -106.0,
  "west": -106.1
}
```

---

## Soil Fixtures

### Overview

Soil fixtures define drainage, compaction, and passability characteristics for different soil types.

### Format

```json
{
  "soil_type": "string (sand|loam|clay)",
  "drainage_coefficient": "number (0-1, higher = better drainage)",
  "compaction_coefficient": "number (0-1, higher = more compacted)",
  "base_passability": "number (0-100, score when dry)",
  "wet_penalty_multiplier": "number (multiplier when wet)",
  "recovery_hours": "number (hours to dry after rain)",
  "texture": "string (coarse|medium|fine)",
  "organic_content": "number (0-100%)"
}
```

### Scenarios

#### Scenario 1: Sand
**File**: `fixtures/soil_sand.json`

**Characteristics**:
- Drainage coefficient: 0.9 (excellent drainage)
- Compaction coefficient: 0.3 (loose, soft)
- Base passability: 60 (can get stuck when dry)
- Wet penalty multiplier: 0.8 (slightly worse when wet)
- Recovery hours: 2 (dries quickly)
- Texture: coarse
- Organic content: 5%

**Use Cases**:
- Desert/beach road passability
- Quick recovery after rain
- Low compaction (soft surface)

**Full Fixture**:
```json
{
  "soil_type": "sand",
  "drainage_coefficient": 0.9,
  "compaction_coefficient": 0.3,
  "base_passability": 60,
  "wet_penalty_multiplier": 0.8,
  "recovery_hours": 2,
  "texture": "coarse",
  "organic_content": 5,
  "description": "Sandy soil with excellent drainage but low compaction"
}
```

---

#### Scenario 2: Loam
**File**: `fixtures/soil_loam.json`

**Characteristics**:
- Drainage coefficient: 0.6 (good drainage)
- Compaction coefficient: 0.7 (moderately compacted)
- Base passability: 85 (good traction)
- Wet penalty multiplier: 0.5 (moderate impact when wet)
- Recovery hours: 8 (moderate recovery)
- Texture: medium
- Organic content: 15%

**Use Cases**:
- Agricultural/rural road passability
- Balanced drainage and compaction
- Typical forest roads

**Full Fixture**:
```json
{
  "soil_type": "loam",
  "drainage_coefficient": 0.6,
  "compaction_coefficient": 0.7,
  "base_passability": 85,
  "wet_penalty_multiplier": 0.5,
  "recovery_hours": 8,
  "texture": "medium",
  "organic_content": 15,
  "description": "Balanced loam with good passability when dry"
}
```

---

#### Scenario 3: Clay
**File**: `fixtures/soil_clay.json`

**Characteristics**:
- Drainage coefficient: 0.2 (poor drainage)
- Compaction coefficient: 0.9 (highly compacted when dry)
- Base passability: 90 (excellent when dry)
- Wet penalty multiplier: 0.1 (severe impact when wet, becomes mud)
- Recovery hours: 24 (very slow to dry)
- Texture: fine
- Organic content: 10%

**Use Cases**:
- Worst-case wet road conditions
- Mud risk assessment
- Long recovery time scenarios

**Full Fixture**:
```json
{
  "soil_type": "clay",
  "drainage_coefficient": 0.2,
  "compaction_coefficient": 0.9,
  "base_passability": 90,
  "wet_penalty_multiplier": 0.1,
  "recovery_hours": 24,
  "texture": "fine",
  "organic_content": 10,
  "description": "Clay soil with poor drainage, excellent when dry, impassable when wet"
}
```

---

## Connectivity Fixtures

### Overview

Connectivity fixtures model cellular tower distances and canopy cover impacts on signal quality.

### Format

```json
{
  "scenario_name": "string",
  "tower_distance_km": "number (kilometers to nearest tower)",
  "canopy_cover_percent": "number (0-100%)",
  "expected_signal_strength": "number (-120 to -50 dBm)",
  "expected_quality": "string (excellent|good|fair|poor|none)",
  "starlink_obstruction_percent": "number (0-100%)",
  "expected_download_mbps": "number (estimated speed)"
}
```

### Scenarios

#### Tower Distance: 1 km (Close)

**Scenario**: `tower_1km_canopy_0`  
**File**: `fixtures/connectivity_1km_open.json`

```json
{
  "scenario_name": "tower_1km_canopy_0",
  "tower_distance_km": 1.0,
  "canopy_cover_percent": 0,
  "expected_signal_strength": -65,
  "expected_quality": "excellent",
  "starlink_obstruction_percent": 0,
  "expected_download_mbps": 50
}
```

**Scenario**: `tower_1km_canopy_40`  
**File**: `fixtures/connectivity_1km_partial.json`

```json
{
  "scenario_name": "tower_1km_canopy_40",
  "tower_distance_km": 1.0,
  "canopy_cover_percent": 40,
  "expected_signal_strength": -72,
  "expected_quality": "good",
  "starlink_obstruction_percent": 15,
  "expected_download_mbps": 35
}
```

**Scenario**: `tower_1km_canopy_80`  
**File**: `fixtures/connectivity_1km_dense.json`

```json
{
  "scenario_name": "tower_1km_canopy_80",
  "tower_distance_km": 1.0,
  "canopy_cover_percent": 80,
  "expected_signal_strength": -85,
  "expected_quality": "fair",
  "starlink_obstruction_percent": 40,
  "expected_download_mbps": 15
}
```

---

#### Tower Distance: 5 km (Moderate)

**Scenario**: `tower_5km_canopy_0`  
**File**: `fixtures/connectivity_5km_open.json`

```json
{
  "scenario_name": "tower_5km_canopy_0",
  "tower_distance_km": 5.0,
  "canopy_cover_percent": 0,
  "expected_signal_strength": -85,
  "expected_quality": "good",
  "starlink_obstruction_percent": 0,
  "expected_download_mbps": 25
}
```

**Scenario**: `tower_5km_canopy_40`  
**File**: `fixtures/connectivity_5km_partial.json`

```json
{
  "scenario_name": "tower_5km_canopy_40",
  "tower_distance_km": 5.0,
  "canopy_cover_percent": 40,
  "expected_signal_strength": -95,
  "expected_quality": "fair",
  "starlink_obstruction_percent": 15,
  "expected_download_mbps": 12
}
```

**Scenario**: `tower_5km_canopy_80`  
**File**: `fixtures/connectivity_5km_dense.json`

```json
{
  "scenario_name": "tower_5km_canopy_80",
  "tower_distance_km": 5.0,
  "canopy_cover_percent": 80,
  "expected_signal_strength": -105,
  "expected_quality": "poor",
  "starlink_obstruction_percent": 40,
  "expected_download_mbps": 3
}
```

---

#### Tower Distance: 15 km (Far)

**Scenario**: `tower_15km_canopy_0`  
**File**: `fixtures/connectivity_15km_open.json`

```json
{
  "scenario_name": "tower_15km_canopy_0",
  "tower_distance_km": 15.0,
  "canopy_cover_percent": 0,
  "expected_signal_strength": -105,
  "expected_quality": "fair",
  "starlink_obstruction_percent": 0,
  "expected_download_mbps": 8
}
```

**Scenario**: `tower_15km_canopy_40`  
**File**: `fixtures/connectivity_15km_partial.json`

```json
{
  "scenario_name": "tower_15km_canopy_40",
  "tower_distance_km": 15.0,
  "canopy_cover_percent": 40,
  "expected_signal_strength": -112,
  "expected_quality": "poor",
  "starlink_obstruction_percent": 15,
  "expected_download_mbps": 2
}
```

**Scenario**: `tower_15km_canopy_80`  
**File**: `fixtures/connectivity_15km_dense.json`

```json
{
  "scenario_name": "tower_15km_canopy_80",
  "tower_distance_km": 15.0,
  "canopy_cover_percent": 80,
  "expected_signal_strength": -118,
  "expected_quality": "none",
  "starlink_obstruction_percent": 40,
  "expected_download_mbps": 0
}
```

---

## Trip Fixtures

### Overview

Trip fixtures define complete route geometries with surface types, lengths, and waypoints.

### Format

```json
{
  "route_name": "string",
  "surface_type": "string (paved|gravel|dirt|sand)",
  "total_length_km": "number",
  "estimated_duration_minutes": "number",
  "waypoints": [
    {
      "latitude": "number",
      "longitude": "number",
      "elevation": "number (meters)",
      "distance_from_start_km": "number"
    }
  ],
  "surface_quality": "string (excellent|good|fair|poor)",
  "terrain_difficulty": "string (easy|moderate|difficult)"
}
```

### Scenarios

#### Scenario 1: Paved Highway Route
**File**: `fixtures/trip_paved_highway.json`

**Characteristics**:
- Surface: Paved (asphalt)
- Length: 150 km
- Duration: 90 minutes (100 km/h avg)
- Terrain: Flat to rolling hills
- Quality: Excellent
- Difficulty: Easy

**Use Cases**:
- Baseline route planning
- Best-case battery consumption
- High-speed travel scenarios
- Minimal road passability concerns

**Full Fixture**:
```json
{
  "route_name": "paved_highway",
  "surface_type": "paved",
  "total_length_km": 150,
  "estimated_duration_minutes": 90,
  "waypoints": [
    {
      "latitude": 39.7392,
      "longitude": -104.9903,
      "elevation": 1609,
      "distance_from_start_km": 0,
      "name": "Denver, CO"
    },
    {
      "latitude": 39.5501,
      "longitude": -105.7821,
      "elevation": 2134,
      "distance_from_start_km": 75,
      "name": "I-70 Mountain Pass"
    },
    {
      "latitude": 39.6433,
      "longitude": -106.3781,
      "elevation": 2438,
      "distance_from_start_km": 150,
      "name": "Vail, CO"
    }
  ],
  "surface_quality": "excellent",
  "terrain_difficulty": "easy",
  "average_speed_kmh": 100,
  "road_conditions": "well_maintained"
}
```

---

#### Scenario 2: Sandy Forest Road Route
**File**: `fixtures/trip_sandy_forest.json`

**Characteristics**:
- Surface: Dirt/sand
- Length: 25 km
- Duration: 90 minutes (16.7 km/h avg)
- Terrain: Hilly, uneven
- Quality: Poor
- Difficulty: Difficult

**Use Cases**:
- Worst-case road passability
- High battery consumption (low speed, rough terrain)
- Risk assessment (getting stuck)
- 4WD/AWD requirements

**Full Fixture**:
```json
{
  "route_name": "sandy_forest_road",
  "surface_type": "sand",
  "total_length_km": 25,
  "estimated_duration_minutes": 90,
  "waypoints": [
    {
      "latitude": 34.5199,
      "longitude": -117.3000,
      "elevation": 900,
      "distance_from_start_km": 0,
      "name": "Mojave Preserve Entrance"
    },
    {
      "latitude": 34.5350,
      "longitude": -117.2200,
      "elevation": 1100,
      "distance_from_start_km": 12.5,
      "name": "Sandy Wash Crossing"
    },
    {
      "latitude": 34.5500,
      "longitude": -117.1500,
      "elevation": 950,
      "distance_from_start_km": 25,
      "name": "Remote Campsite"
    }
  ],
  "surface_quality": "poor",
  "terrain_difficulty": "difficult",
  "average_speed_kmh": 16.7,
  "road_conditions": "unmaintained",
  "soil_type": "sand",
  "requires_4wd": true
}
```

---

## Usage Guidelines

### Loading Fixtures in Tests

**Python (Backend)**:
```python
import json
from pathlib import Path

def load_fixture(filename: str):
    """Load a fixture file from the fixtures directory."""
    fixture_path = Path(__file__).parent / "fixtures" / filename
    with open(fixture_path, 'r') as f:
        return json.load(f)

# Usage
weather = load_fixture("weather_storm.json")
soil = load_fixture("soil_clay.json")
```

**TypeScript (Frontend)**:
```typescript
import weatherStorm from '../fixtures/weather_storm.json';
import soilClay from '../fixtures/soil_clay.json';

// Or dynamic loading
async function loadFixture(filename: string) {
  const response = await fetch(`/fixtures/${filename}`);
  return response.json();
}
```

---

### Combining Fixtures

Many tests require multiple fixtures:

```python
def test_road_passability_worst_case():
    # Worst-case scenario: storm + clay soil + sandy forest road
    weather = load_fixture("weather_storm.json")
    soil = load_fixture("soil_clay.json")
    route = load_fixture("trip_sandy_forest.json")
    
    result = assess_road_passability(
        weather_forecast=weather,
        soil_type=soil,
        route_geometry=route
    )
    
    # Expect very low passability score
    assert result.passability_score < 30
    assert "high_risk" in result.warnings
```

---

### Fixture Versioning

All fixtures include a `version` field:

```json
{
  "version": "1.0",
  "scenario_name": "weather_storm",
  "data": { ... }
}
```

When updating fixtures:
1. Increment version number
2. Update this documentation
3. Re-run all tests using the fixture
4. Document breaking changes in commit message

---

## Fixture File Locations

### Directory Structure

```
app/src/test/resources/fixtures/
├── weather/
│   ├── weather_clear.json
│   ├── weather_partly_cloudy.json
│   └── weather_storm.json
├── terrain/
│   ├── terrain_flat.json
│   └── terrain_hilly.json
├── soil/
│   ├── soil_sand.json
│   ├── soil_loam.json
│   └── soil_clay.json
├── connectivity/
│   ├── connectivity_1km_open.json
│   ├── connectivity_1km_partial.json
│   ├── connectivity_1km_dense.json
│   ├── connectivity_5km_open.json
│   ├── connectivity_5km_partial.json
│   ├── connectivity_5km_dense.json
│   ├── connectivity_15km_open.json
│   ├── connectivity_15km_partial.json
│   └── connectivity_15km_dense.json
└── trips/
    ├── trip_paved_highway.json
    └── trip_sandy_forest.json
```

---

## Test Coverage Matrix

| Feature | Fixtures Used | Test Files |
|---------|---------------|------------|
| Road Passability | weather_*, soil_*, trip_* | `test_road_passability_service.py` |
| Smart Delay | weather_storm.json, trip_* | `test_notifications_smart_delay.py` |
| Solar Forecast | weather_clear.json, weather_partly_cloudy.json | `test_solar_forecast.py` (TBD) |
| Connectivity | connectivity_*.json, terrain_* | `test_connectivity_prediction.py` (TBD) |
| Battery Planning | weather_*, trip_*, terrain_hilly.json | `test_battery_planning.py` (TBD) |
| Campsite Quality | terrain_*, soil_*, connectivity_* | `test_campsite_quality.py` (TBD) |

---

## Maintenance

### Adding New Fixtures

1. Create fixture file in appropriate subdirectory
2. Document in this file (add new section or scenario)
3. Add to test coverage matrix
4. Write at least one test using the fixture
5. Commit both fixture and documentation together

### Deprecating Fixtures

1. Mark as `[DEPRECATED]` in this document
2. Update tests to use replacement fixture
3. Remove file after 1 release cycle
4. Document in version history

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-01-18 | Initial fixture documentation |

---

## References

- Test Implementation: `/backend/test_notifications_smart_delay.py`
- Fixture Generation Scripts: `/scripts/generate_fixtures.py` (TBD)
- Data Sources: All fixtures are synthetic (not derived from real data)

---

**Maintained by**: Engineering Team  
**Reviewed by**: QA, Test Engineering  
**Next Review**: February 2026
