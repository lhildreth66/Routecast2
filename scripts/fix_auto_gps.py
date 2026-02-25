#!/usr/bin/env python3
"""
Remove auto-GPS on mount from every affected screen.

For each screen we:
  1. Remove the auto-GPS useEffect block on mount.
  2. Replace hardcoded default lat/lon state with '' (empty).
  3. Replace the body of useCurrentLocation / useMyLocation with a call
     to the injected `triggerGps` from the shared hook.
  4. Add imports for the shared hook + component.
  5. Add the hook call inside the component function.
  6. Replace the old location UI box with <LocationSearchBox ...>.

We use simple string replacement since the patterns are nearly identical.
"""

import re
import sys
from pathlib import Path

APP = Path(__file__).parent.parent / "frontend" / "app"

# ── screens and their per-screen session keys ────────────────────────────────
SCREENS = {
    "truck-parking.tsx":      ("truckParkingLoc",   "#f59e0b"),
    "truck-stops.tsx":        ("truckStopsLoc",      "#f59e0b"),
    "truck-services.tsx":     ("truckServicesLoc",   "#f59e0b"),
    "weigh-stations.tsx":     ("weighStationsLoc",   "#f59e0b"),
    "truck-restrictions.tsx": ("truckRestrictLoc",   "#f59e0b"),
    "campsite-index.tsx":     ("campsiteIndexLoc",   "#22c55e"),
    "casinos.tsx":            ("casinosLoc",          "#8b5cf6"),
    "dump-station.tsx":       ("dumpStationLoc",      "#06b6d4"),
    "cracker-barrel.tsx":     ("crackerBarrelLoc",    "#ef4444"),
    "last-chance.tsx":        ("lastChanceLoc",       "#f59e0b"),
    "rv-dealership.tsx":      ("rvDealershipLoc",     "#3b82f6"),
    "walmart-parking.tsx":    ("walmartParkingLoc",   "#0ea5e9"),
    "wind-shelter.tsx":       ("windShelterLoc",      "#06b6d4"),
    "connectivity.tsx":       ("connectivityLoc",     "#06b6d4"),
    "solar-forecast.tsx":     ("solarForecastLoc",    "#eab308"),
    "terrain-shade.tsx":      ("terrainShadeLoc",     "#22c55e"),
}

HOOK_IMPORT = (
    "import { useLocationSearch } from '../lib/useLocationSearch';\n"
    "import LocationSearchBox from '../lib/components/LocationSearchBox';\n"
)


def remove_auto_gps_useeffect(src: str) -> str:
    """
    Remove the first useEffect block that contains requestForegroundPermissionsAsync
    (the auto-GPS on mount block).  We find the opening `useEffect(() => {`
    that wraps the GPS call and remove it entirely.
    """
    # Find `useEffect(() => {` that contains requestForegroundPermissionsAsync
    # within roughly 20 lines
    pattern = re.compile(
        r"(\s*// [^\n]*\n)?"            # optional comment line before
        r"  useEffect\(\(\) => \{\n"
        r"(?:    \(\s*async \(\) => \{[\s\S]*?requestForegroundPermissionsAsync[\s\S]*?\}\)\(\);\n"
        r"  \},\s*\[\]\);\n)"
        , re.MULTILINE
    )
    # Broader fallback pattern
    fallback = re.compile(
        r"  useEffect\(\(\) => \{\n"
        r"    \(\s*async \(\) => \{[\s\S]*?requestForegroundPermissionsAsync[\s\S]*?\}\)\(\);\s*\n"
        r"  \},\s*\[\]\);\n",
        re.MULTILINE
    )
    new_src = fallback.sub('', src)
    if new_src == src:
        print("  WARNING: could not remove auto-GPS useEffect — check manually")
    return new_src


def replace_default_coords(src: str) -> str:
    """Replace hardcoded default lat/lon useState values with empty strings."""
    # e.g. useState('34.05') -> useState('')
    src = re.sub(r"useState\('[0-9.-]+'\)", "useState('')", src)
    return src


def replace_use_current_location_body(src: str) -> str:
    """
    Replace entire useCurrentLocation / useMyLocation function body with
    a one-liner that calls triggerGps().
    The function is kept so existing JSX onPress handlers still compile.
    """
    # Match: const useCurrentLocation = async () => { ... };
    pattern = re.compile(
        r"(  const use[Cc]urrent[Ll]ocation = async \(\) => \{)"
        r"[\s\S]*?"
        r"(  \};)",
        re.MULTILINE
    )
    replacement = (
        r"\1\n"
        r"    await triggerGps();\n"
        r"  \2"
    )
    new_src = pattern.sub(replacement, src)

    # Also handle useMyLocation pattern
    pattern2 = re.compile(
        r"(  const useMyLocation = async \(\) => \{)"
        r"[\s\S]*?"
        r"(  \};)",
        re.MULTILINE
    )
    new_src = pattern2.sub(replacement, new_src)

    if new_src == src:
        print("  WARNING: could not replace useCurrentLocation body — check manually")
    return new_src


def add_hook_import(src: str) -> str:
    """Add hook+component imports after the last existing import line."""
    if "useLocationSearch" in src:
        return src  # already added
    # Insert after the last import
    last_import = src.rfind("\nimport ")
    if last_import == -1:
        return HOOK_IMPORT + src
    # find end of that line
    end_of_line = src.find("\n", last_import + 1)
    return src[:end_of_line + 1] + HOOK_IMPORT + src[end_of_line + 1:]


def add_hook_call(src: str, session_key: str, accent: str) -> str:
    """
    Insert the useLocationSearch call right after the component function opens
    and after the existing router/navigation hooks, before the first useState.
    """
    if "useLocationSearch" in src and "= useLocationSearch(" in src:
        return src  # already added

    hook_call = (
        f"\n"
        f"  // ── Manual location search (no auto-GPS on mount) ─────────────────────\n"
        f"  const {{\n"
        f"    lat: latitude, lon: longitude, locationLabel, locationLoading,\n"
        f"    locationQuery, suggestions, showSuggestions,\n"
        f"    handleLocationQueryChange, selectSuggestion,\n"
        f"    clearManualLocation, triggerGps, setShowSuggestions,\n"
        f"  }} = useLocationSearch('{session_key}');\n"
    )

    # Find first `const [latitude` or `const [lat` useState
    match = re.search(r"^  const \[(?:latitude|lat),", src, re.MULTILINE)
    if match:
        return src[:match.start()] + hook_call + "\n" + src[match.start():]

    # Fallback: insert after the function declaration line
    match2 = re.search(r"export default function \w+\([^)]*\) \{", src)
    if match2:
        end = src.find("\n", match2.end())
        return src[:end + 1] + hook_call + src[end + 1:]

    return src


def remove_old_lat_lon_state(src: str) -> str:
    """Remove the useState lines for latitude/longitude since the hook provides them."""
    src = re.sub(r"  const \[latitude, setLatitude\] = useState\('?'?\);\n", '', src)
    src = re.sub(r"  const \[longitude, setLongitude\] = useState\('?'?\);\n", '', src)
    # Also remove the locationLoading state (hook provides it)
    src = re.sub(r"  const \[locationLoading, setLocationLoading\] = useState\((?:true|false)\);\n", '', src)
    return src


def replace_location_box_jsx(src: str, accent: str) -> str:
    """
    Replace the old location display box JSX with <LocationSearchBox ...>.
    We look for the common `{/* Location` comment block and replace the
    whole View+children up to and including its closing </View>.
    This is the hardest part; we use a heuristic approach.
    """
    if "LocationSearchBox" in src:
        return src  # already replaced

    location_box_snippet = (
        f"          <LocationSearchBox\n"
        f"            lat={{latitude}}\n"
        f"            lon={{longitude}}\n"
        f"            locationLabel={{locationLabel}}\n"
        f"            locationLoading={{locationLoading}}\n"
        f"            locationQuery={{locationQuery}}\n"
        f"            suggestions={{suggestions}}\n"
        f"            showSuggestions={{showSuggestions}}\n"
        f"            handleLocationQueryChange={{handleLocationQueryChange}}\n"
        f"            selectSuggestion={{selectSuggestion}}\n"
        f"            clearManualLocation={{clearManualLocation}}\n"
        f"            triggerGps={{triggerGps}}\n"
        f"            setShowSuggestions={{setShowSuggestions}}\n"
        f"            accentColor=\"{accent}\"\n"
        f"          />"
    )

    # Pattern: {/* Location ... */} block followed by <View ...>...</View>
    # We look for the comment, then capture until we find the matching closing
    # of the first View at that indentation level.  This is approximate.
    pattern = re.compile(
        r"          \{/\* Location[^*]*\*/\}\n"
        r"          <View[^>]*>\n"
        r"(?:            [\s\S]*?\n)*?"  # non-greedy inner lines
        r"          </View>\n",
        re.MULTILINE
    )
    new_src = pattern.sub(location_box_snippet + "\n", src)
    if new_src == src:
        print("  WARNING: could not replace location box JSX — check manually")
    return new_src


def fix_file(path: Path, session_key: str, accent: str) -> bool:
    print(f"Processing {path.name}...")
    src = path.read_text()

    src = remove_auto_gps_useeffect(src)
    src = replace_default_coords(src)
    src = add_hook_import(src)
    src = add_hook_call(src, session_key, accent)
    src = remove_old_lat_lon_state(src)
    src = replace_use_current_location_body(src)
    src = replace_location_box_jsx(src, accent)

    path.write_text(src)
    print(f"  ✓  {path.name}")
    return True


if __name__ == "__main__":
    errors = []
    for filename, (session_key, accent) in SCREENS.items():
        p = APP / filename
        if not p.exists():
            print(f"  SKIP (not found): {filename}")
            continue
        try:
            fix_file(p, session_key, accent)
        except Exception as e:
            print(f"  ERROR {filename}: {e}")
            errors.append(filename)
    if errors:
        print(f"\nFailed: {errors}")
        sys.exit(1)
    else:
        print("\nAll screens patched.")
