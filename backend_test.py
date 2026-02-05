#!/usr/bin/env python3

import requests
import sys
import json
from datetime import datetime

class RouteCastAPITester:
    def __init__(self, base_url="http://localhost:8001"):
        self.base_url = base_url
        self.tests_run = 0
        self.tests_passed = 0

    def run_test(self, name, method, endpoint, expected_status, data=None, timeout=30):
        """Run a single API test"""
        url = f"{self.base_url}/{endpoint}"
        headers = {'Content-Type': 'application/json'}

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=timeout)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=timeout)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    response_data = response.json()
                    if isinstance(response_data, dict) and len(response_data) > 0:
                        print(f"   Response keys: {list(response_data.keys())}")
                except:
                    print(f"   Response: {response.text[:100]}...")
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                print(f"   Response: {response.text[:200]}...")

            return success, response.json() if success else {}

        except requests.exceptions.Timeout:
            print(f"❌ Failed - Request timed out after {timeout}s")
            return False, {}
        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {}

    def test_health_check(self):
        """Test health check endpoint"""
        return self.run_test("Health Check", "GET", "api/health", 200)

    def test_root_endpoint(self):
        """Test root API endpoint"""
        return self.run_test("Root API", "GET", "api/", 200)

    def test_route_weather(self):
        """Test route weather endpoint"""
        data = {
            "origin": "Denver, CO",
            "destination": "Boulder, CO",
            "vehicle_type": "RV"
        }
        return self.run_test("Route Weather", "POST", "api/route/weather", 200, data, timeout=60)

    def test_free_camping_search(self):
        """Test free camping search endpoint"""
        data = {
            "latitude": 39.7392,
            "longitude": -104.9903,
            "radius_miles": 25
        }
        return self.run_test("Free Camping Search", "POST", "api/free-camping/search", 200, data, timeout=45)

    def test_dump_stations_search(self):
        """Test dump stations search endpoint"""
        data = {
            "latitude": 39.7392,
            "longitude": -104.9903,
            "radius_miles": 50
        }
        return self.run_test("Dump Stations Search", "POST", "api/dump-stations/search", 200, data, timeout=45)

    def test_truck_stops_search(self):
        """Test truck stops search endpoint"""
        data = {
            "latitude": 39.7392,
            "longitude": -104.9903,
            "radius_miles": 15
        }
        return self.run_test("Truck Stops Search", "POST", "api/truck-stops/search", 200, data, timeout=60)

def main():
    print("🚀 Starting RouteCast Backend API Tests")
    print("=" * 50)
    
    tester = RouteCastAPITester()

    # Test basic endpoints first
    print("\n📋 Testing Basic Endpoints...")
    tester.test_health_check()
    tester.test_root_endpoint()

    # Test core functionality
    print("\n🌤️ Testing Weather & Route Endpoints...")
    tester.test_route_weather()

    # Test location-based services
    print("\n📍 Testing Location-Based Services...")
    tester.test_free_camping_search()
    tester.test_dump_stations_search()
    tester.test_truck_stops_search()

    # Print results
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {tester.tests_passed}/{tester.tests_run} passed")
    
    if tester.tests_passed == tester.tests_run:
        print("🎉 All tests passed!")
        return 0
    else:
        print(f"⚠️  {tester.tests_run - tester.tests_passed} tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())