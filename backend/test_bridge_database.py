"""Test bridge database matching logic"""
from bridge_database import get_bridge_warnings

def test_bridge_warnings():
    """Test that bridge warnings are generated correctly for a sample route."""
    
    # Test locations along the route from North Liberty, IA to Kingwood, WV
    test_locations = [
        "Start - North Liberty, Iowa",
        "Point 1 - Iowa City, Iowa",
        "Point 2 - Davenport, Iowa",
        "Point 3 - Chicago, Illinois",
        "Point 4 - Gary, Indiana",
        "Point 5 - South Bend, Indiana",
        "Point 6 - Toledo, Ohio",
        "Point 7 - Cleveland, Ohio",
        "Point 8 - Akron, Ohio",
        "Point 9 - Pittsburgh, Pennsylvania",
        "Point 10 - Morgantown, West Virginia",
        "End - Kingwood, West Virginia"
    ]
    
    vehicle_height = 11.0  # 11 feet tall vehicle
    
    print(f"\n{'='*80}")
    print(f"Testing Bridge Height Alerts for 11 ft vehicle")
    print(f"Route: North Liberty, IA to Kingwood, WV")
    print(f"{'='*80}\n")
    
    total_warnings = 0
    critical_warnings = 0
    
    for location in test_locations:
        warnings = get_bridge_warnings(location, vehicle_height)
        if warnings:
            print(f"\n📍 {location}:")
            for warning in warnings:
                print(f"  {warning}")
                total_warnings += 1
                if "CRITICAL" in warning or "DANGER" in warning:
                    critical_warnings += 1
    
    print(f"\n{'='*80}")
    print(f"Summary: {total_warnings} total warnings, {critical_warnings} critical/danger warnings")
    print(f"{'='*80}\n")
    
    if total_warnings == 0:
        print("⚠️ WARNING: No bridge warnings generated! Check matching logic.")
        return False
    else:
        print(f"✓ Bridge matching is working! Found {total_warnings} warnings.")
        return True

if __name__ == "__main__":
    success = test_bridge_warnings()
    exit(0 if success else 1)
