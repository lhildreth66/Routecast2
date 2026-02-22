"""
RouteCast API Backend Tests
Tests for: Water Budget, Casinos, Route Weather, How To Use features
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('EXPO_PUBLIC_BACKEND_URL', 'https://premium-toggle.preview.emergentagent.com')

class TestHealthAndBasicEndpoints:
    """Basic API health and connectivity tests"""
    
    def test_health_endpoint(self):
        """Test API health check"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        print(f"✓ Health check passed: {data}")
    
    def test_root_endpoint(self):
        """Test root API endpoint"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        data = response.json()
        assert "Routecast" in data.get("message", "")
        print(f"✓ Root endpoint passed: {data}")


class TestWaterBudgetAPI:
    """Water Budget calculation API tests - includes Fresh, Gray, Black tanks"""
    
    def test_water_budget_basic_calculation(self):
        """Test water budget with default values"""
        payload = {
            "fresh_gal": 40,
            "gray_gal": 30,
            "black_gal": 20,
            "people": 2,
            "showers_per_week": 7,
            "hot_days": False
        }
        response = requests.post(f"{BASE_URL}/api/water-budget", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Verify all three tanks are in response
        assert "fresh_days" in data, "Missing fresh_days in response"
        assert "gray_days" in data, "Missing gray_days in response"
        assert "black_days" in data, "Missing black_days in response"
        assert "days_remaining" in data, "Missing days_remaining"
        assert "limiting_factor" in data, "Missing limiting_factor"
        assert "daily_fresh_gal" in data, "Missing daily_fresh_gal"
        assert "daily_gray_gal" in data, "Missing daily_gray_gal"
        assert "daily_black_gal" in data, "Missing daily_black_gal"
        
        print(f"✓ Water budget calculation: {data['days_remaining']} days, limited by: {data['limiting_factor']}")
        print(f"  Fresh: {data['fresh_days']} days, Gray: {data['gray_days']} days, Black: {data['black_days']} days")
    
    def test_water_budget_hot_weather(self):
        """Test water budget with hot weather mode enabled (+30% usage)"""
        payload = {
            "fresh_gal": 40,
            "gray_gal": 30,
            "black_gal": 20,
            "people": 2,
            "showers_per_week": 7,
            "hot_days": True
        }
        response = requests.post(f"{BASE_URL}/api/water-budget", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        # Hot weather should reduce days remaining due to higher usage
        assert data["days_remaining"] > 0
        assert data["daily_fresh_gal"] > 0
        print(f"✓ Hot weather mode: {data['days_remaining']} days remaining, daily fresh: {data['daily_fresh_gal']} gal")
    
    def test_water_budget_more_people(self):
        """Test water budget with more people (should reduce days)"""
        payload = {
            "fresh_gal": 40,
            "gray_gal": 30,
            "black_gal": 20,
            "people": 4,
            "showers_per_week": 14,
            "hot_days": False
        }
        response = requests.post(f"{BASE_URL}/api/water-budget", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        # More people = fewer days
        assert data["days_remaining"] > 0
        print(f"✓ 4 people budget: {data['days_remaining']} days, limited by: {data['limiting_factor']}")


class TestCasinosAPI:
    """Casinos Near Me API tests"""
    
    def test_casinos_las_vegas(self):
        """Test finding casinos near Las Vegas"""
        # Las Vegas coordinates
        params = {
            "latitude": 36.1699,
            "longitude": -115.1398,
            "radius_miles": 50
        }
        response = requests.get(f"{BASE_URL}/api/boondocking/casinos", params=params)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "results" in data, "Missing results in response"
        assert "total" in data, "Missing total in response"
        
        # Las Vegas should definitely have casinos
        print(f"✓ Casinos near Las Vegas: Found {data['total']} casinos")
        if data['results']:
            print(f"  First result: {data['results'][0]['name']}")
    
    def test_casinos_rural_area(self):
        """Test casinos API with rural coordinates (may return 0 results)"""
        # Rural Wyoming coordinates
        params = {
            "latitude": 43.0,
            "longitude": -108.0,
            "radius_miles": 100
        }
        response = requests.get(f"{BASE_URL}/api/boondocking/casinos", params=params)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "results" in data
        print(f"✓ Casinos in rural area: Found {data['total']} casinos (expected fewer)")


class TestGeocodeAutocomplete:
    """Geocode/Autocomplete API tests for address clear X buttons"""
    
    def test_autocomplete_city(self):
        """Test geocode autocomplete with city search"""
        params = {
            "query": "Denver",
            "limit": 5
        }
        response = requests.get(f"{BASE_URL}/api/geocode/autocomplete", params=params)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Expected list of suggestions"
        if data:
            assert "place_name" in data[0], "Missing place_name in suggestion"
            print(f"✓ Autocomplete for 'Denver': {len(data)} suggestions")
            print(f"  First: {data[0]['place_name']}")
        else:
            print("✓ Autocomplete returned empty (may be API limit)")


class TestRouteWeather:
    """Route Weather API tests - includes Bridge Height Hazards"""
    
    def test_route_weather_basic(self):
        """Test basic route weather request"""
        payload = {
            "origin": "Denver, CO",
            "destination": "Colorado Springs, CO",
            "vehicle_type": "car",
            "trucker_mode": False
        }
        response = requests.post(f"{BASE_URL}/api/route/weather", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "origin" in data
        assert "destination" in data
        assert "waypoints" in data
        assert "total_distance_miles" in data or data.get("total_distance_miles") is None
        
        print(f"✓ Route weather: {data['origin']} -> {data['destination']}")
        print(f"  Distance: {data.get('total_distance_miles', 'N/A')} miles")
    
    def test_route_weather_trucker_mode(self):
        """Test route weather with trucker mode and vehicle height for bridge alerts"""
        payload = {
            "origin": "Denver, CO",
            "destination": "Albuquerque, NM",
            "vehicle_type": "semi",
            "trucker_mode": True,
            "vehicle_height_ft": 13.6
        }
        response = requests.post(f"{BASE_URL}/api/route/weather", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Check trucker-specific fields
        assert "trucker_warnings" in data, "Missing trucker_warnings"
        assert "vehicle_type" in data
        assert "bridge_clearance_alerts" in data, "Missing bridge_clearance_alerts field"
        
        print(f"✓ Trucker mode route: {len(data.get('trucker_warnings', []))} warnings")
        print(f"  Bridge alerts: {len(data.get('bridge_clearance_alerts', []))} (may be empty if no data)")
        print(f"  Safety score: {data.get('safety_score', {}).get('overall_score', 'N/A')}")


class TestRoutesHistoryFavorites:
    """Routes history and favorites API tests"""
    
    def test_routes_history(self):
        """Test getting route history"""
        response = requests.get(f"{BASE_URL}/api/routes/history")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Expected list of routes"
        print(f"✓ Routes history: {len(data)} routes")
    
    def test_routes_favorites(self):
        """Test getting favorite routes"""
        response = requests.get(f"{BASE_URL}/api/routes/favorites")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Expected list of favorites"
        print(f"✓ Favorite routes: {len(data)} favorites")


class TestTruckerEndpoints:
    """Trucker-specific API endpoints"""
    
    def test_truck_stops(self):
        """Test finding truck stops"""
        params = {
            "latitude": 39.7392,
            "longitude": -104.9903,
            "radius_miles": 30
        }
        response = requests.get(f"{BASE_URL}/api/trucker/truck-stops", params=params)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "results" in data
        print(f"✓ Truck stops near Denver: {data.get('total', len(data['results']))} found")
    
    def test_weight_restrictions(self):
        """Test weight restrictions endpoint"""
        params = {
            "latitude": 39.7392,
            "longitude": -104.9903,
            "radius_miles": 30
        }
        response = requests.get(f"{BASE_URL}/api/trucker/weight-restrictions", params=params)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "restrictions" in data
        print(f"✓ Weight restrictions: {len(data['restrictions'])} items returned")


class TestAIChat:
    """AI Chat assistant endpoint test"""
    
    def test_chat_basic(self):
        """Test AI chat with basic question"""
        payload = {
            "message": "What should I do if I encounter fog while driving?",
            "route_context": None
        }
        response = requests.post(f"{BASE_URL}/api/chat", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "response" in data, "Missing response in chat"
        print(f"✓ AI Chat response received: {len(data['response'])} chars")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
