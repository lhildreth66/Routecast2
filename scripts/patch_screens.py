#!/usr/bin/env python3
"""
Patch all 16 screens to:
  1. Remove auto-GPS useEffect on mount
  2. Remove the GPS-only function (getCurrentLocation)
  3. Replace refreshLocation/useCurrentLocation body with await triggerGps()
  4. Add useLocationSearch hook import + call
  5. Remove old latitude/longitude/locationLoading useState lines
  6. Replace location box JSX with <LocationSearchBox />

Run with: python3 scripts/patch_screens.py [--dry-run] [screen_name ...]
"""

import sys
import re
from pathlib import Path

APP = Path(__file__).parent.parent / "frontend" / "app"

HOOK_IMPORTS = (
    "import { useLocationSearch } from '../lib/useLocationSearch';\n"
    "import LocationSearchBox from '../lib/components/LocationSearchBox';\n"
)

# Hook call — aliases lat/lon so existing code that uses `latitude`/`longitude` keeps working
def hook_call(session_key: str) -> str:
    return (
        f"\n"
        f"  // ── Location (manual search + explicit GPS only) ────────────────────\n"
        f"  const {{\n"
        f"    lat: latitude, lon: longitude,\n"
        f"    locationLabel, locationLoading,\n"
        f"    locationQuery, suggestions, showSuggestions,\n"
        f"    handleLocationQueryChange, selectSuggestion,\n"
        f"    clearManualLocation, triggerGps, setShowSuggestions,\n"
        f"  }} = useLocationSearch('{session_key}');\n"
    )


# ── helpers ──────────────────────────────────────────────────────────────────

def find_block_end(src: str, open_pos: int) -> int:
    """
    Given `open_pos` pointing to the opening `{`, find the matching `}`.
    Returns index of matching `}`.
    """
    depth = 0
    i = open_pos
    while i < len(src):
        if src[i] == '{':
            depth += 1
        elif src[i] == '}':
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def collect_useeffect_block(lines: list, start_idx: int) -> tuple[list, int]:
    """
    Collect all lines of the useEffect block starting at start_idx.
    Returns (block_lines, next_idx).
    """
    block_lines = [lines[start_idx]]
    j = start_idx + 1
    brace_depth = lines[start_idx].count('{') - lines[start_idx].count('}')
    while j < len(lines):
        block_lines.append(lines[j])
        brace_depth += lines[j].count('{') - lines[j].count('}')
        j += 1
        if brace_depth == 0:
            break
    return block_lines, j


def remove_useeffect_with_gps(src: str) -> str:
    """
    Remove the useEffect block that triggers GPS on mount.
    Handles two patterns:
      1. useEffect(() => { getCurrentLocation(); }, []);  (indirect call)
      2. useEffect(() => { (async () => { ...requestForegroundPermissionsAsync... })(); }, []);
    """
    lines = src.split('\n')
    out_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        # Check for optional preceding comment line like '// Automatically get...'
        if re.match(r'\s*// .*(?:Automat|location.*mount|get.*current)', line, re.I):
            if i + 1 < len(lines) and re.match(r'\s*useEffect\(', lines[i + 1]):
                i += 1  # skip comment, let next iteration handle the useEffect
                continue

        if re.match(r'\s*useEffect\(\(\) => \{', line):
            block_lines, next_i = collect_useeffect_block(lines, i)
            block_text = '\n'.join(block_lines)
            # Skip if it's a GPS block (either direct call or async IIFE)
            if ('requestForegroundPermissionsAsync' in block_text or
                    'getCurrentLocation()' in block_text):
                i = next_i
                continue

        out_lines.append(line)
        i += 1

    return '\n'.join(out_lines)


def remove_getcurrentlocation_function(src: str) -> str:
    """Remove `const getCurrentLocation = async () => { ... };` function."""
    # Pattern: const getCurrentLocation = async () => {
    pattern = re.compile(r'  const getCurrentLocation = async \(\) => \{')
    match = pattern.search(src)
    if not match:
        return src
    
    # Find closing brace
    open_brace = src.index('{', match.start())
    close_brace = find_block_end(src, open_brace)
    if close_brace == -1:
        return src
    
    # Include the `;\n` after `}`
    end = close_brace + 1
    if end < len(src) and src[end] == ';':
        end += 1
    if end < len(src) and src[end] == '\n':
        end += 1
    
    return src[:match.start()] + src[end:]


def replace_gps_function_body(src: str) -> str:
    """
    Replace the body of refreshLocation / useCurrentLocation / useMyLocation
    with a single `await triggerGps();` call.
    """
    for func_name in ['refreshLocation', 'useCurrentLocation', 'useMyLocation']:
        pattern = re.compile(
            r'(  const ' + re.escape(func_name) + r' = async \(\) => \{)'
        )
        match = pattern.search(src)
        if not match:
            continue
        
        open_brace = src.index('{', match.start())
        close_brace = find_block_end(src, open_brace)
        if close_brace == -1:
            continue
        
        # Replace the body (between { and }) with `await triggerGps();`
        new_body = '{\n    await triggerGps();\n  }'
        src = src[:open_brace] + new_body + src[close_brace + 1:]
    
    return src


def add_hook_imports(src: str) -> str:
    """Add hook imports after the last existing import line."""
    if 'useLocationSearch' in src:
        return src
    
    # Find last `import ` line
    last_import_end = 0
    for m in re.finditer(r'^import [^\n]+\n', src, re.MULTILINE):
        last_import_end = m.end()
    
    if last_import_end == 0:
        return HOOK_IMPORTS + src
    
    return src[:last_import_end] + HOOK_IMPORTS + src[last_import_end:]


def add_hook_call(src: str, session_key: str) -> str:
    """Insert useLocationSearch call before the old state declarations."""
    if '= useLocationSearch(' in src:
        return src
    
    call = hook_call(session_key)
    
    # Insert before first `const [latitude` state line
    match = re.search(r'^  const \[latitude, setLatitude\]', src, re.MULTILINE)
    if match:
        return src[:match.start()] + call + '\n' + src[match.start():]
    
    # Fallback: insert after router = useRouter()
    match2 = re.search(r'  const router = useRouter\(\);\n', src)
    if match2:
        return src[:match2.end()] + call + src[match2.end():]
    
    return src


def remove_old_state_lines(src: str) -> str:
    """Remove useState declarations that the hook now provides."""
    patterns = [
        r"  const \[latitude, setLatitude\] = useState\('[^']*'\);\n",
        r"  const \[latitude, setLatitude\] = useState\(''\);\n",
        r"  const \[longitude, setLongitude\] = useState\('[^']*'\);\n",
        r"  const \[longitude, setLongitude\] = useState\(''\);\n",
        r"  const \[locationLoading, setLocationLoading\] = useState\((?:true|false)\);\n",
    ]
    for p in patterns:
        src = re.sub(p, '', src)
    return src


def remove_location_import_if_unused(src: str) -> str:
    """
    Remove `import * as Location from 'expo-location';` if no longer used directly.
    The hook handles the Location import internally.
    """
    # Keep the import if there are direct uses beyond the hook (rare)
    # Check for Location.xxx usages other than in the import line
    import_line = "import * as Location from 'expo-location';\n"
    if import_line not in src:
        return src
    
    # Count non-import references to Location.
    src_without_import = src.replace(import_line, '')
    if 'Location.' not in src_without_import:
        return src_without_import
    return src


def remove_unused_useeffect_import(src: str) -> str:
    """Remove `useEffect` from React import if it's no longer used in the file."""
    # Count actual uses (not in import line)
    non_import = re.sub(r"^import React.*\n", '', src, flags=re.MULTILINE)
    if 'useEffect' in non_import:
        return src  # still used
    # Remove from import
    src = re.sub(r',\s*useEffect', '', src)
    src = re.sub(r'useEffect,\s*', '', src)
    return src


def build_location_search_box(accent: str, indent: str = '          ') -> str:
    """Return the <LocationSearchBox ...> JSX string."""
    return (
        f"{indent}<LocationSearchBox\n"
        f"{indent}  lat={{latitude}}\n"
        f"{indent}  lon={{longitude}}\n"
        f"{indent}  locationLabel={{locationLabel}}\n"
        f"{indent}  locationLoading={{locationLoading}}\n"
        f"{indent}  locationQuery={{locationQuery}}\n"
        f"{indent}  suggestions={{suggestions}}\n"
        f"{indent}  showSuggestions={{showSuggestions}}\n"
        f"{indent}  handleLocationQueryChange={{handleLocationQueryChange}}\n"
        f"{indent}  selectSuggestion={{selectSuggestion}}\n"
        f"{indent}  clearManualLocation={{clearManualLocation}}\n"
        f"{indent}  triggerGps={{triggerGps}}\n"
        f"{indent}  setShowSuggestions={{setShowSuggestions}}\n"
        f"{indent}  accentColor=\"{accent}\"\n"
        f"{indent}/>"
    )


def replace_location_box_jsx(src: str, accent: str) -> str:
    """
    Replace the old location display box with <LocationSearchBox />.
    Handles both variants:
      - styles.locationBoxHeader / styles.locationBoxCoords
      - styles.locationHeader / styles.locationCoords
    """
    if '<LocationSearchBox' in src:
        return src
    
    # Find the `<View style={styles.locationBox}>` line — capture only spaces, not newline
    box_match = re.search(r'\n([ \t]+)<View style=\{styles\.locationBox\}>', src)
    if not box_match:
        return src
    
    indent = box_match.group(1)  # spaces only (e.g. '          ')
    open_start = box_match.start() + 1  # skip the leading \n
    # Find the opening {  of this View — it's the > in the matched line
    # Now find the matching closing </View>
    # We parse the JSX by counting <View and </View>
    
    # Find start of the <View ...> tag
    view_tag_start = open_start + len(indent)  # position of '<'
    
    # Walk forward to find balanced </View>
    pos = view_tag_start + len('<View style={styles.locationBox}>')
    depth = 1
    while pos < len(src) - 6 and depth > 0:
        if src[pos:pos+5] == '<View':
            depth += 1
            pos += 5
        elif src[pos:pos+7] == '</View>':
            depth -= 1
            if depth == 0:
                close_end = pos + 7
                break
            pos += 7
        else:
            pos += 1
    else:
        return src  # Couldn't find matching close
    
    # The text we want to replace runs from start of indent on that line to after </View>
    # But we also want to remove the comment before it
    # Check if there's a comment line right before
    block_start = open_start
    # Look for preceding comment line
    pre = src[:open_start].rstrip('\n')
    last_newline = pre.rfind('\n')
    comment_line = pre[last_newline + 1:]
    if re.match(r'\s*\{/\*.*\*/\}', comment_line) or re.match(r'\s*\{/\* Location', comment_line):
        block_start = last_newline + 1  # include from start of comment line
    
    # The replacement
    jsx = build_location_search_box(accent, indent)
    # Include trailing newline to replace the </View>\n
    replaced = src[block_start:close_end]
    return src[:block_start] + jsx + src[close_end:]


# ── per-screen configuration ─────────────────────────────────────────────────

# (session_key, accent_color, needs_lsbox)
# needs_lsbox=False means screen already has manual coord inputs (solar, terrain)
# so we only remove GPS and don't replace location box
SCREENS: dict[str, tuple[str, str, bool]] = {
    "truck-parking.tsx":      ("truckParkingLoc",    "#22c55e", True),
    "truck-stops.tsx":        ("truckStopsLoc",       "#3b82f6", True),
    "truck-services.tsx":     ("truckServicesLoc",    "#f59e0b", True),
    "weigh-stations.tsx":     ("weighStationsLoc",    "#8b5cf6", True),
    "truck-restrictions.tsx": ("truckRestrictLoc",    "#ec4899", True),
    "campsite-index.tsx":     ("campsiteIndexLoc",    "#22c55e", True),
    "casinos.tsx":            ("casinosLoc",           "#0ea5e9", True),
    "dump-station.tsx":       ("dumpStationLoc",       "#0ea5e9", True),
    "cracker-barrel.tsx":     ("crackerBarrelLoc",     "#ef4444", True),
    "last-chance.tsx":        ("lastChanceLoc",        "#f59e0b", True),
    "rv-dealership.tsx":      ("rvDealershipLoc",      "#3b82f6", True),
    "walmart-parking.tsx":    ("walmartParkingLoc",    "#0ea5e9", True),
    "wind-shelter.tsx":       ("windShelterLoc",       "#06b6d4", False),  # no locationBox wrapper
    "connectivity.tsx":       ("connectivityLoc",      "#06b6d4", True),
    "solar-forecast.tsx":     ("solarForecastLoc",     "#eab308", False),  # has manual coord inputs
    "terrain-shade.tsx":      ("terrainShadeLoc",      "#22c55e", False),  # has manual coord inputs
}


def patch_file(path: Path, session_key: str, accent: str, use_lsbox: bool, dry_run: bool) -> bool:
    print(f"  {'[DRY RUN] ' if dry_run else ''}Patching {path.name}...")
    src = path.read_text()
    original = src
    
    # Step 1: Remove auto-GPS useEffect
    src = remove_useeffect_with_gps(src)
    
    # Step 2: Remove getCurrentLocation only-GPS function
    src = remove_getcurrentlocation_function(src)
    
    # Clean up unused useEffect import (both branches)
    src = remove_unused_useeffect_import(src)
    
    if use_lsbox:
        # Step 3: Add hook imports
        src = add_hook_imports(src)
        
        # Step 4: Add hook call (before old state)
        src = add_hook_call(src, session_key)
        
        # Step 5: Remove old state lines
        src = remove_old_state_lines(src)
        
        # Step 6: Replace GPS function body with triggerGps
        src = replace_gps_function_body(src)
        
        # Step 7: Remove direct Location import if unused
        src = remove_location_import_if_unused(src)
        
        # Step 8: Replace location box JSX
        src = replace_location_box_jsx(src, accent)
    else:
        # For screens with manual coord inputs (solar-forecast, terrain-shade)
        # and wind-shelter: just removed auto-GPS useEffect above.
        # Keep existing refreshLocation function body as-is
        # (these screens keep their own GPS state management for the refresh btn)
        pass
    
    if src == original:
        print(f"  WARNING: No changes made to {path.name}")
        return True
    
    if not dry_run:
        path.write_text(src)
        print(f"  ✓ {path.name}")
    else:
        # Show diff summary
        orig_lines = original.split('\n')
        new_lines = src.split('\n')
        print(f"  Lines: {len(orig_lines)} → {len(new_lines)} (change: {len(new_lines) - len(orig_lines):+d})")
    
    return True


if __name__ == '__main__':
    dry_run = '--dry-run' in sys.argv
    filter_screens = [a for a in sys.argv[1:] if not a.startswith('--')]
    
    errors = []
    for filename, (session_key, accent, use_lsbox) in SCREENS.items():
        if filter_screens and filename not in filter_screens:
            continue
        p = APP / filename
        if not p.exists():
            print(f"  SKIP (not found): {filename}")
            continue
        try:
            patch_file(p, session_key, accent, use_lsbox, dry_run)
        except Exception as e:
            import traceback
            print(f"  ERROR {filename}: {e}")
            traceback.print_exc()
            errors.append(filename)
    
    if errors:
        print(f"\n❌ Failed: {errors}")
        sys.exit(1)
    else:
        print(f"\n{'[DRY RUN] ' if dry_run else ''}✅ All screens patched.")
