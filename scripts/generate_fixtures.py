#!/usr/bin/env python3
"""
Generate test fixtures for Routecast2

This script creates all test fixture files documented in docs/copilot/test-data.md.
All fixtures are deterministic and reproducible.

Usage:
    python generate_fixtures.py
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any
import math


def generate_weather_fixtures():
    """Generate 3-day hourly weather fixtures (72 entries each)."""
    
    base_time = datetime(2026, 1, 20, 0, 0, 0)
    fixtures_dir = Path("app/src/test/resources/fixtures/weather")
    
    # Scenario 1: Clear weather
    clear_data = []
    for hour in range(72):
        timestamp = base_time + timedelta(hours=hour)
        # Temperature varies sinusoidally (65-75°F, peak at 2pm each day)
        temp = 70 + 5 * math.sin((hour % 24 - 14) * math.pi / 12)
        # Cloud cover varies slightly (0-20%)
        cloud = 10 + 10 * math.sin(hour * math.pi / 36)
        
        clear_data.append({
            "timestamp": timestamp.isoformat() + "Z",
            "temperature": round(temp, 1),
            "precipitation": 0.0,
            "wind_speed": 8 + 4 * math.sin(hour * math.pi / 24),
            "cloud_cover": max(0, min(20, round(cloud, 1))),
            "visibility": 10.0,
            "conditions": "clear" if cloud < 15 else "partly_cloudy"
        })
    
    with open(fixtures_dir / "weather_clear.json", 'w') as f:
        json.dump({
            "version": "1.0",
            "scenario": "clear",
            "description": "Clear weather with minimal precipitation",
            "entries": clear_data
        }, f, indent=2)
    
    # Scenario 2: Partly cloudy
    partly_cloudy_data = []
    for hour in range(72):
        timestamp = base_time + timedelta(hours=hour)
        # More temperature variation (55-70°F)
        temp = 62.5 + 7.5 * math.sin((hour % 24 - 14) * math.pi / 12)
        # Variable cloud cover (30-60%)
        cloud = 45 + 15 * math.sin(hour * math.pi / 18)
        # Occasional light drizzle
        precip = 0.05 if hour % 17 == 0 else 0.0
        
        partly_cloudy_data.append({
            "timestamp": timestamp.isoformat() + "Z",
            "temperature": round(temp, 1),
            "precipitation": precip,
            "wind_speed": 15 + 5 * math.sin(hour * math.pi / 20),
            "cloud_cover": round(cloud, 1),
            "visibility": 6.5 if precip > 0 else 7.5,
            "conditions": "partly_cloudy" if cloud < 50 else "cloudy"
        })
    
    with open(fixtures_dir / "weather_partly_cloudy.json", 'w') as f:
        json.dump({
            "version": "1.0",
            "scenario": "partly_cloudy",
            "description": "Variable cloud cover with occasional light precipitation",
            "entries": partly_cloudy_data
        }, f, indent=2)
    
    # Scenario 3: Storm
    storm_data = []
    for hour in range(72):
        timestamp = base_time + timedelta(hours=hour)
        # Cold temperatures (32-45°F)
        temp = 38 + 6 * math.sin((hour % 24 - 14) * math.pi / 12)
        # Heavy precipitation (0.2-0.8 inches/hour)
        precip = 0.5 + 0.3 * math.sin(hour * math.pi / 12)
        # Strong winds (25-45 mph)
        wind = 35 + 10 * math.sin(hour * math.pi / 16)
        # Low visibility (0.5-2 miles)
        visibility = 1.25 + 0.75 * math.sin(hour * math.pi / 24)
        
        storm_data.append({
            "timestamp": timestamp.isoformat() + "Z",
            "temperature": round(temp, 1),
            "precipitation": round(precip, 2),
            "wind_speed": round(wind, 1),
            "cloud_cover": 90 + 10 * math.sin(hour * math.pi / 36),
            "visibility": round(visibility, 1),
            "conditions": "snow" if temp < 35 else "rain"
        })
    
    with open(fixtures_dir / "weather_storm.json", 'w') as f:
        json.dump({
            "version": "1.0",
            "scenario": "storm",
            "description": "Severe weather with heavy precipitation and strong winds",
            "entries": storm_data
        }, f, indent=2)
    
    print(f"✓ Generated 3 weather fixtures ({len(clear_data)} entries each)")


def generate_terrain_fixtures():
    """Generate DEM terrain fixtures (100x100 grids)."""
    
    fixtures_dir = Path("app/src/test/resources/fixtures/terrain")
    
    # Scenario 1: Flat terrain (100-105m variation)
    flat_elevations = []
    for row in range(100):
        row_data = []
        for col in range(100):
            # Minor variations using sinusoidal pattern
            base = 100
            variation = 2.5 * math.sin(row * math.pi / 50) + 2.5 * math.sin(col * math.pi / 50)
            elevation = base + variation
            row_data.append(round(elevation, 1))
        flat_elevations.append(row_data)
    
    flat_terrain = {
        "version": "1.0",
        "scenario": "flat",
        "metadata": {
            "resolution": 30,  # meters per pixel
            "bounds": {
                "north": 40.0,
                "south": 39.9,
                "east": -105.0,
                "west": -105.1
            },
            "width": 100,
            "height": 100,
            "units": "meters",
            "min_elevation": 100.0,
            "max_elevation": 105.0,
            "mean_gradient_percent": 1.5
        },
        "elevations": flat_elevations
    }
    
    with open(fixtures_dir / "terrain_flat.json", 'w') as f:
        json.dump(flat_terrain, f, indent=2)
    
    # Scenario 2: Hilly terrain (100-300m variation)
    hilly_elevations = []
    for row in range(100):
        row_data = []
        for col in range(100):
            # Create hills and valleys using multiple sinusoidal frequencies
            base = 200
            hill1 = 80 * math.sin(row * math.pi / 25)
            hill2 = 60 * math.sin(col * math.pi / 30)
            hill3 = 40 * math.sin((row + col) * math.pi / 20)
            elevation = base + hill1 + hill2 + hill3
            row_data.append(round(elevation, 1))
        hilly_elevations.append(row_data)
    
    hilly_terrain = {
        "version": "1.0",
        "scenario": "hilly",
        "metadata": {
            "resolution": 30,
            "bounds": {
                "north": 39.8,
                "south": 39.7,
                "east": -106.0,
                "west": -106.1
            },
            "width": 100,
            "height": 100,
            "units": "meters",
            "min_elevation": 100.0,
            "max_elevation": 300.0,
            "mean_gradient_percent": 8.5
        },
        "elevations": hilly_elevations
    }
    
    with open(fixtures_dir / "terrain_hilly.json", 'w') as f:
        json.dump(hilly_terrain, f, indent=2)
    
    print(f"✓ Generated 2 terrain fixtures (100x100 grids)")


def generate_soil_fixtures():
    """Generate soil type fixtures."""
    
    fixtures_dir = Path("app/src/test/resources/fixtures/soil")
    
    soils = [
        {
            "version": "1.0",
            "soil_type": "sand",
            "drainage_coefficient": 0.9,
            "compaction_coefficient": 0.3,
            "base_passability": 60,
            "wet_penalty_multiplier": 0.8,
            "recovery_hours": 2,
            "texture": "coarse",
            "organic_content": 5,
            "description": "Sandy soil with excellent drainage but low compaction"
        },
        {
            "version": "1.0",
            "soil_type": "loam",
            "drainage_coefficient": 0.6,
            "compaction_coefficient": 0.7,
            "base_passability": 85,
            "wet_penalty_multiplier": 0.5,
            "recovery_hours": 8,
            "texture": "medium",
            "organic_content": 15,
            "description": "Balanced loam with good passability when dry"
        },
        {
            "version": "1.0",
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
    ]
    
    for soil in soils:
        filename = f"soil_{soil['soil_type']}.json"
        with open(fixtures_dir / filename, 'w') as f:
            json.dump(soil, f, indent=2)
    
    print(f"✓ Generated 3 soil fixtures")


def generate_connectivity_fixtures():
    """Generate connectivity fixtures (tower distances × canopy cover)."""
    
    fixtures_dir = Path("app/src/test/resources/fixtures/connectivity")
    
    scenarios = [
        # 1 km tower distance
        {"distance": 1.0, "canopy": 0, "signal": -65, "quality": "excellent", "obstruction": 0, "mbps": 50, "name": "open"},
        {"distance": 1.0, "canopy": 40, "signal": -72, "quality": "good", "obstruction": 15, "mbps": 35, "name": "partial"},
        {"distance": 1.0, "canopy": 80, "signal": -85, "quality": "fair", "obstruction": 40, "mbps": 15, "name": "dense"},
        # 5 km tower distance
        {"distance": 5.0, "canopy": 0, "signal": -85, "quality": "good", "obstruction": 0, "mbps": 25, "name": "open"},
        {"distance": 5.0, "canopy": 40, "signal": -95, "quality": "fair", "obstruction": 15, "mbps": 12, "name": "partial"},
        {"distance": 5.0, "canopy": 80, "signal": -105, "quality": "poor", "obstruction": 40, "mbps": 3, "name": "dense"},
        # 15 km tower distance
        {"distance": 15.0, "canopy": 0, "signal": -105, "quality": "fair", "obstruction": 0, "mbps": 8, "name": "open"},
        {"distance": 15.0, "canopy": 40, "signal": -112, "quality": "poor", "obstruction": 15, "mbps": 2, "name": "partial"},
        {"distance": 15.0, "canopy": 80, "signal": -118, "quality": "none", "obstruction": 40, "mbps": 0, "name": "dense"},
    ]
    
    for scenario in scenarios:
        fixture = {
            "version": "1.0",
            "scenario_name": f"tower_{int(scenario['distance'])}km_canopy_{scenario['canopy']}",
            "tower_distance_km": scenario['distance'],
            "canopy_cover_percent": scenario['canopy'],
            "expected_signal_strength_dbm": scenario['signal'],
            "expected_quality": scenario['quality'],
            "starlink_obstruction_percent": scenario['obstruction'],
            "expected_download_mbps": scenario['mbps']
        }
        
        filename = f"connectivity_{int(scenario['distance'])}km_{scenario['name']}.json"
        with open(fixtures_dir / filename, 'w') as f:
            json.dump(fixture, f, indent=2)
    
    print(f"✓ Generated 9 connectivity fixtures")


def generate_trip_fixtures():
    """Generate trip/route fixtures."""
    
    fixtures_dir = Path("app/src/test/resources/fixtures/trips")
    
    # Paved highway route
    paved_highway = {
        "version": "1.0",
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
    
    with open(fixtures_dir / "trip_paved_highway.json", 'w') as f:
        json.dump(paved_highway, f, indent=2)
    
    # Sandy forest road route
    sandy_forest = {
        "version": "1.0",
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
        "requires_4wd": True
    }
    
    with open(fixtures_dir / "trip_sandy_forest.json", 'w') as f:
        json.dump(sandy_forest, f, indent=2)
    
    print(f"✓ Generated 2 trip fixtures")


def main():
    """Generate all test fixtures."""
    print("Generating test fixtures...")
    print()
    
    generate_weather_fixtures()
    generate_terrain_fixtures()
    generate_soil_fixtures()
    generate_connectivity_fixtures()
    generate_trip_fixtures()
    
    print()
    print("✅ All fixtures generated successfully!")
    print()
    print("Fixture locations:")
    print("  app/src/test/resources/fixtures/weather/")
    print("  app/src/test/resources/fixtures/terrain/")
    print("  app/src/test/resources/fixtures/soil/")
    print("  app/src/test/resources/fixtures/connectivity/")
    print("  app/src/test/resources/fixtures/trips/")


if __name__ == "__main__":
    main()
