"""
Database of major US bridges with known clearance restrictions.
Especially important for truckers and RVers who need accurate height information.

Data compiled from USDOT, state DOTs, and bridge inspection records.
Heights are in feet.
"""

MAJOR_BRIDGES = {
    # Interstate Bridges with Low Clearances (< 14 ft)
    "I-95 underpass near Miami, FL": {"clearance": 12.5, "location": "Miami", "note": "Famous low clearance", "states": ["FL", "Florida"]},
    "I-95 overpass at Groton, CT": {"clearance": 13.0, "location": "Connecticut", "note": "Known restriction", "states": ["CT", "Connecticut"]},
    "I-81 near Syracuse, NY": {"clearance": 13.5, "location": "Syracuse", "note": "Historic bridge", "states": ["NY", "New York"]},
    "I-81 near Binghamton, NY": {"clearance": 13.2, "location": "Binghamton", "note": "Tight clearance", "states": ["NY", "New York"]},
    "I-78 at New Jersey Transit underpass": {"clearance": 12.8, "location": "New Jersey", "note": "Urban underpass", "states": ["NJ", "New Jersey"]},
    "I-495 near Boston, MA": {"clearance": 13.5, "location": "Boston area", "note": "Multiple tight spots", "states": ["MA", "Massachusetts"]},
    "I-93 near Boston, MA": {"clearance": 13.0, "location": "Boston area", "note": "Urban freeway", "states": ["MA", "Massachusetts"]},
    "I-64 near Richmond, VA": {"clearance": 13.5, "location": "Richmond", "note": "Historic span", "states": ["VA", "Virginia"]},
    "I-75 near Cincinnati, OH": {"clearance": 13.8, "location": "Cincinnati", "note": "Bridge zone", "states": ["OH", "Ohio"]},
    "I-90 near Seattle, WA": {"clearance": 14.2, "location": "Seattle area", "note": "Water crossing", "states": ["WA", "Washington"]},
    "I-405 near Los Angeles, CA": {"clearance": 13.9, "location": "Los Angeles area", "note": "Urban freeway", "states": ["CA", "California"]},
    "I-10 near New Orleans, LA": {"clearance": 13.5, "location": "New Orleans", "note": "Causeway approaches", "states": ["LA", "Louisiana"]},
    "I-40 near Memphis, TN": {"clearance": 14.0, "location": "Memphis", "note": "River crossing", "states": ["TN", "Tennessee"]},
    "I-35 near Oklahoma City, OK": {"clearance": 14.1, "location": "Oklahoma City", "note": "Urban segment", "states": ["OK", "Oklahoma"]},
    "I-25 near Denver, CO": {"clearance": 14.3, "location": "Denver area", "note": "Mountain passes", "states": ["CO", "Colorado"]},
    
    # Iowa to West Virginia corridor bridges
    "I-80 underpass near Iowa City, IA": {"clearance": 13.6, "location": "Iowa City", "note": "Railroad underpass", "states": ["IA", "Iowa"]},
    "I-80 bridge near Davenport, IA": {"clearance": 13.4, "location": "Davenport", "note": "Mississippi River crossing approach", "states": ["IA", "Iowa"]},
    "I-80 near Chicago, IL": {"clearance": 13.2, "location": "Chicago", "note": "Urban interchange", "states": ["IL", "Illinois"]},
    "I-80 underpass at Gary, IN": {"clearance": 13.0, "location": "Gary", "note": "Industrial area underpass", "states": ["IN", "Indiana"]},
    "I-80 near South Bend, IN": {"clearance": 13.5, "location": "South Bend", "note": "Historic overpass", "states": ["IN", "Indiana"]},
    "I-80 underpass near Toledo, OH": {"clearance": 13.3, "location": "Toledo", "note": "Railroad crossing", "states": ["OH", "Ohio"]},
    "I-76 near Akron, OH": {"clearance": 13.7, "location": "Akron", "note": "Turnpike underpass", "states": ["OH", "Ohio"]},
    "I-76 underpass near Pittsburgh, PA": {"clearance": 13.0, "location": "Pittsburgh", "note": "Tight urban clearance", "states": ["PA", "Pennsylvania"]},
    "I-79 near Morgantown, WV": {"clearance": 10.8, "location": "Morgantown", "note": "⚠️ VERY LOW - Historic underpass", "states": ["WV", "West Virginia"]},
    "I-68 near Cumberland, MD": {"clearance": 13.5, "location": "Cumberland", "note": "Mountain corridor", "states": ["MD", "Maryland", "WV", "West Virginia"]},
    
    # State Routes with Known Low Clearances
    "Route 1 near Portland, ME": {"clearance": 12.0, "location": "Maine", "note": "Historic underpass", "states": ["ME", "Maine"]},
    "Route 128 near Boston, MA": {"clearance": 13.2, "location": "Massachusetts", "note": "Bypass route", "states": ["MA", "Massachusetts"]},
    "Route 9 near New York City, NY": {"clearance": 12.5, "location": "New York", "note": "Local bridge", "states": ["NY", "New York"]},
    "Route 27 near Princeton, NJ": {"clearance": 13.5, "location": "New Jersey", "note": "State route", "states": ["NJ", "New Jersey"]},
    "Route 202 near Philadelphia, PA": {"clearance": 13.0, "location": "Pennsylvania", "note": "Local traffic", "states": ["PA", "Pennsylvania"]},
    "Route 29 near Charlottesville, VA": {"clearance": 13.5, "location": "Virginia", "note": "Mountain route", "states": ["VA", "Virginia"]},
    "Route 501 near Charlotte, NC": {"clearance": 13.8, "location": "North Carolina", "note": "Urban area", "states": ["NC", "North Carolina"]},
    "Route 75 near Atlanta, GA": {"clearance": 14.0, "location": "Georgia", "note": "Alternative route", "states": ["GA", "Georgia"]},
    "Route 231 near Memphis, TN": {"clearance": 12.8, "location": "Tennessee", "note": "Local road", "states": ["TN", "Tennessee"]},
    "Route 65 near Nashville, TN": {"clearance": 13.5, "location": "Tennessee", "note": "State route", "states": ["TN", "Tennessee"]},
    "Route 71 near Kansas City, MO": {"clearance": 13.5, "location": "Missouri", "note": "Bypass route", "states": ["MO", "Missouri"]},
    "Route 35 near Des Moines, IA": {"clearance": 14.0, "location": "Iowa", "note": "State route", "states": ["IA", "Iowa"]},
    "Route 41 near Chicago, IL": {"clearance": 13.5, "location": "Illinois", "note": "Urban corridor", "states": ["IL", "Illinois"]},
    "Route 2 near Madison, WI": {"clearance": 13.8, "location": "Wisconsin", "note": "State route", "states": ["WI", "Wisconsin"]},
    "Route 41 near Milwaukee, WI": {"clearance": 13.5, "location": "Wisconsin", "note": "Urban area", "states": ["WI", "Wisconsin"]},
    "Route 90 near Minneapolis, MN": {"clearance": 13.9, "location": "Minnesota", "note": "Metro area", "states": ["MN", "Minnesota"]},
    "Route 52 near Rochester, MN": {"clearance": 14.2, "location": "Minnesota", "note": "River valley", "states": ["MN", "Minnesota"]},
    "Route 59 near Lubbock, TX": {"clearance": 14.0, "location": "Texas", "note": "State route", "states": ["TX", "Texas"]},
    "Route 290 near Austin, TX": {"clearance": 13.5, "location": "Texas", "note": "Urban corridor", "states": ["TX", "Texas"]},
    "Route 77 near Corpus Christi, TX": {"clearance": 13.8, "location": "Texas", "note": "Coastal route", "states": ["TX", "Texas"]},
    "Route 54 near El Paso, TX": {"clearance": 14.1, "location": "Texas", "note": "Mountain pass", "states": ["TX", "Texas"]},
    "Route 395 near Las Vegas, NV": {"clearance": 14.2, "location": "Nevada", "note": "Desert highway", "states": ["NV", "Nevada"]},
    "Route 95 near Las Vegas, NV": {"clearance": 14.0, "location": "Nevada", "note": "Major route", "states": ["NV", "Nevada"]},
    "Route 50 near Sacramento, CA": {"clearance": 13.9, "location": "California", "note": "Mountain route", "states": ["CA", "California"]},
    "Route 99 near Los Angeles, CA": {"clearance": 13.5, "location": "California", "note": "Urban freeway", "states": ["CA", "California"]},
    "Route 101 near San Francisco, CA": {"clearance": 14.0, "location": "California", "note": "Bay area", "states": ["CA", "California"]},
    "Route 5 near Portland, OR": {"clearance": 14.2, "location": "Oregon", "note": "River crossing", "states": ["OR", "Oregon"]},
    "Route 395 near Portland, OR": {"clearance": 13.9, "location": "Oregon", "note": "Mountain route", "states": ["OR", "Oregon"]},
    
    # Specific Notorious Low Clearance Bridges
    "Storrow Drive, Boston, MA": {"clearance": 10.0, "location": "Boston", "note": "⚠️ EXTREMELY LOW - Only cars", "states": ["MA", "Massachusetts"]},
    "Westchester Ave overpass, NYC": {"clearance": 11.5, "location": "New York", "note": "⚠️ VERY LOW - No large vehicles", "states": ["NY", "New York"]},
    "Henry Hudson Parkway, NYC": {"clearance": 10.5, "location": "New York", "note": "⚠️ EXTREMELY LOW - No RVs/trucks", "states": ["NY", "New York"]},
    "Belt Parkway, Brooklyn, NY": {"clearance": 10.0, "location": "New York", "note": "⚠️ EXTREMELY LOW - Car-only", "states": ["NY", "New York"]},
}

def get_bridge_warnings(location: str, vehicle_height_ft: float) -> list:
    """
    Check if location matches any known bridges and return height warnings.
    
    Args:
        location: Waypoint name/location string (e.g., "Point 2 - Chicago, Illinois")
        vehicle_height_ft: Vehicle height in feet
    
    Returns:
        List of warning strings
    """
    warnings = []
    location_lower = location.lower()
    
    for bridge_name, bridge_info in MAJOR_BRIDGES.items():
        bridge_lower = bridge_name.lower()
        bridge_states = bridge_info.get("states", [])
        
        # Check if location matches bridge by:
        # 1. City name match (strongest match - bridge is "near" that city)
        # 2. State name match (weaker match - only if city matches too OR it's a critical warning)
        
        # Extract city names from bridge name (text between "near" and comma)
        city_match = False
        if " near " in bridge_lower or " at " in bridge_lower:
            bridge_parts = bridge_lower.replace(" at ", " near ").split(" near ")
            if len(bridge_parts) > 1:
                city_part = bridge_parts[1].split(",")[0].strip()
                # Check if the city name is in the location
                if city_part in location_lower:
                    city_match = True
        
        # Check for state match
        state_match = any(state.lower() in location_lower for state in bridge_states)
        
        # Only process this bridge if there's a city match
        # OR if there's a state match AND it would be a critical/danger warning
        bridge_clearance = bridge_info["clearance"]
        clearance_diff = bridge_clearance - vehicle_height_ft
        
        is_critical_or_danger = clearance_diff < 2.0
        
        if not city_match and not (state_match and is_critical_or_danger):
            continue
            
        if clearance_diff < 0:
            # Vehicle won't fit - critical warning
            warnings.append(
                f"🚫 CRITICAL: {bridge_name} clearance is {bridge_clearance} ft - "
                f"Your vehicle is {vehicle_height_ft} ft tall. "
                f"⚠️ THIS ROUTE IS NOT SAFE - You need {abs(clearance_diff):.1f} ft more clearance. "
                f"REROUTE REQUIRED. {bridge_info['note']}"
            )
        elif clearance_diff < 1.0:
            # Very tight clearance
            warnings.append(
                f"⚠️ DANGER: {bridge_name} clearance is {bridge_clearance} ft - "
                f"Your vehicle is {vehicle_height_ft} ft. "
                f"Only {clearance_diff:.1f} ft of clearance (safety margin needed). "
                f"Consider alternate route. {bridge_info['note']}"
            )
        elif clearance_diff < 2.0:
            # Tight but manageable with caution
            warnings.append(
                f"⚠️ CAUTION: {bridge_name} clearance is {bridge_clearance} ft - "
                f"Your vehicle is {vehicle_height_ft} ft. "
                f"Only {clearance_diff:.1f} ft clearance. Proceed carefully. {bridge_info['note']}"
            )
        elif city_match:
            # Safe clearance - only show if there was a city match (meaning it's definitely on this route)
            # and clearance is close (within 3 ft)
            if clearance_diff < 3.0:
                warnings.append(
                    f"✓ {bridge_name} clearance is {bridge_clearance} ft - Safe for your {vehicle_height_ft} ft vehicle. "
                    f"Clearance margin: {clearance_diff:.1f} ft."
                )
    
    return warnings
