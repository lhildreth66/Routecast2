# Field Test Playbook: Florida Free Camping Sites

**Project**: Routecast2  
**Version**: 1.0.8  
**Last Updated**: January 18, 2026

This playbook guides real-world validation testing of Routecast2 features at free, legal camping sites in Florida. Designed for testers, QA engineers, and product team members conducting field validation.

---

## Table of Contents

1. [Purpose](#purpose)
2. [Test Locations](#test-locations)
3. [Authoritative Rule References](#authoritative-rule-references)
4. [Pre-Trip Checklist](#pre-trip-checklist)
5. [Field Testing Procedures](#field-testing-procedures)
6. [Data Collection](#data-collection)
7. [Safety & Legal Compliance](#safety--legal-compliance)

---

## Purpose

This playbook validates **real-world behavior** of Routecast2 features under actual camping conditions. Unlike unit tests (which use synthetic fixtures), field tests verify the app performs correctly with:

- Real weather data
- Actual terrain and road conditions
- Live cellular/GPS connectivity
- True solar exposure and canopy cover
- Real-time background notifications

### Features Under Test

✅ **Road Passability**
- Sandy/clay road surface assessment
- Wet vs dry condition scoring
- Slope and terrain impact
- 4WD/AWD recommendations

✅ **Wind Shelter Logic**
- Terrain-based wind blocking
- Canopy cover impact
- Campsite exposure rating

✅ **Shade/Solar Impact**
- Solar forecast accuracy (battery charging)
- Canopy cover percentage estimation
- Time-of-day sun exposure

✅ **Energy & Water Planning**
- Battery state-of-charge modeling
- Solar charging predictions
- Water consumption tracking
- Propane usage estimates

✅ **Background Notifications**
- Smart departure timing (weather alerts)
- Severe weather warnings
- Trip hazard notifications

✅ **Premium Entitlement Gating**
- Paywall triggers for locked features
- Subscription validation
- Feature unlock after purchase
- Restore purchases workflow

---

## Test Locations

### Location 1: Ocala National Forest — Dispersed Camping

**Address/Coordinates**: Forest Road 46 (FR 46) and surrounding areas  
**Coordinates**: Approximately 29.1°N, 81.6°W (multiple dispersed sites)  
**Access**: Off SR 19, various forest roads

#### Legal Status & Rules

✅ **Dispersed camping allowed** under USFS regulations  
⏱️ **14-day stay limit** (must move 5+ miles after 14 days)  
📏 **Distance requirements**:
- 150 feet from water sources
- 150 feet from developed sites/trails
- Stay on existing roads and clearings (no cross-country travel)

🚫 **Prohibited**:
- Cutting live vegetation
- Campfires during burn bans
- Dumping waste/gray water
- Blocking roads or trails

#### Recommended Test Areas

**Forest Road 46 (FR 46)**: Sandy forest road with multiple pullouts
- **Surface**: Deep sand, loose
- **Difficulty**: 4WD recommended, impassable when wet
- **Use Cases**: Road passability (worst-case sand), wind shelter, shade analysis

**Forest Road 88 (FR 88)**: Clay/sand mix
- **Surface**: Firmer than FR 46, but slippery when wet
- **Difficulty**: 2WD possible when dry, 4WD when wet
- **Use Cases**: Road passability (clay), wet condition testing

**Alexander Springs Area**: Shaded forest camping
- **Surface**: Firm, established sites
- **Canopy**: 60-80% tree cover
- **Use Cases**: Shade/solar impact, energy planning, connectivity

#### Features to Test

| Feature | Test Scenario | Expected Result |
|---------|---------------|-----------------|
| **Road Passability** | Navigate FR 46 in dry conditions | Score: 40-60 (sand, loose) |
| **Road Passability** | Navigate FR 46 after rain | Score: <30 (high risk, impassable) |
| **Wind Shelter** | Assess campsite in dense forest | High shelter rating (trees block wind) |
| **Solar Forecast** | Camp under 70% canopy | Reduced charging (30-50% of max) |
| **Weather Alerts** | Monitor overnight with rain forecast | Background notification fires 4hr before |
| **Premium Gating** | Attempt solar forecast as free user | Paywall appears, feature locked |

#### Seasonal Considerations

- **Best Season**: October - April (dry, cool)
- **Avoid**: June - September (wet season, heavy afternoon storms, mosquitoes)
- **Road Conditions**: FR 46 often impassable May - October due to rain

---

### Location 2: Apalachicola National Forest — Porter Lake

**Address/Coordinates**: Porter Lake Campground (primitive)  
**Coordinates**: 30.1°N, 84.6°W  
**Access**: Off SR 267, well-marked entrance

#### Legal Status & Rules

✅ **Primitive, free camping** (no reservations required)  
✅ **Vault toilet available** (non-flush)  
⚠️ **No potable water** (bring your own or treat)  
⏱️ **14-day stay limit**

**Facilities**:
- Vault toilet (no running water)
- Fire rings at established sites
- Trash disposal (pack out)

#### Recommended Test Areas

**Porter Lake Shoreline Sites**: Lakeside primitive camping
- **Surface**: Firm dirt, some grass
- **Canopy**: 30-50% (partial sun)
- **Amenities**: Vault toilet, no water/electric
- **Use Cases**: Energy/water planning, off-grid scenarios

**Interior Forest Sites**: Deeper into forest
- **Surface**: Firm, shaded
- **Canopy**: 70-90% (dense trees)
- **Use Cases**: Solar impact (low sun), battery planning

#### Features to Test

| Feature | Test Scenario | Expected Result |
|---------|---------------|-----------------|
| **Energy Planning** | 3-day dry camp, no hookups | Battery SOC predictions accurate ±10% |
| **Water Planning** | Track usage (cooking, cleaning, drinking) | Consumption model matches actual usage |
| **Solar Forecast** | Test under 30-50% canopy | Charging predictions accurate ±15% |
| **Background Notifications** | Monitor weather overnight | Alerts fire for approaching storms |
| **Premium Features** | Test water/energy features as premium user | All features accessible, no paywall |

#### Seasonal Considerations

- **Best Season**: November - March (cool, dry)
- **Avoid**: July - August (extreme heat, high humidity)
- **Water Notes**: Lake water not potable (treat or bring 5+ gallons)

---

### Location 3: SWFWMD & SJRWMD Managed Lands

**Multiple Sites**: Various Water Management District properties

#### SWFWMD Sites (Southwest Florida Water Management District)

**Example Sites**:
- **Green Swamp East Wilderness Preserve** (Polk County)
- **Halpata Tastanaki Preserve** (Citrus County)
- **Cypress Creek Wellfield** (Pasco County)

**Coordinates**: Varies by site (see SWFWMD website for maps)

#### Legal Status & Rules

✅ **Free camping with reservation/permit required**  
🚫 **No dispersed camping** (designated sites only)  
⏱️ **Varies by site** (typically 3-7 day limits)

**Reservation Process**:
1. Visit [swfwmd.state.fl.us](https://www.swfwmd.state.fl.us/recreation/camping)
2. Check site availability
3. Submit free reservation request (24-48hr advance)
4. Receive permit via email
5. Print permit and display at campsite

**Site Rules**:
- Camp only in designated areas (marked)
- Fires in established rings only (if allowed)
- Pack out all trash
- No cutting vegetation
- Quiet hours: 10 PM - 6 AM

#### SJRWMD Sites (St. Johns River Water Management District)

**Example Sites**:
- **Lake George Conservation Area** (Volusia/Putnam)
- **Tiger Bay State Forest** (Volusia)
- **Tosohatchee Wildlife Management Area** (Orange)

**Coordinates**: Varies by site (see SJRWMD website)

#### Legal Status & Rules

✅ **Primitive camping with free reservation**  
⏱️ **7-day limit** (consecutive)  
🚫 **Designated sites only**

**Reservation Process**:
1. Visit [sjrwmd.com/recreation](https://www.sjrwmd.com/recreation/)
2. Select property and check availability
3. Reserve online (free, instant confirmation)
4. Print permit
5. Display at campsite

**Site Rules**:
- Pets allowed (leashed)
- Campfires in designated areas only
- Water: bring your own or treat
- Hunting seasons: check calendar (may restrict access)

#### Features to Test

| Feature | Test Scenario | Expected Result |
|---------|---------------|-----------------|
| **Shade vs Solar** | Compare open vs shaded sites | Solar forecast varies 50-100% based on canopy |
| **Premium Gating** | Test reservation-driven trip planning | Premium features locked for free users |
| **Entitlement Flow** | Complete purchase → unlock features | Immediate unlock, no app restart |
| **Trip Planning** | Enter reserved dates/site | App validates dates, shows site rules |
| **Connectivity** | Test in remote WMD sites | Signal quality matches predicted (fair/poor) |

#### Seasonal Considerations

- **Best Season**: October - April (dry, mild)
- **Hunting Season**: October - February (check WMD calendars, wear orange)
- **Avoid**: May - September (wet, hot, mosquitoes)

---

## Authoritative Rule References

### National Forests (USFS)

**Ocala & Apalachicola National Forests**  
📖 **Official Site**: [https://www.fs.usda.gov/florida](https://www.fs.usda.gov/florida)

**Dispersed Camping Guidance**:
- [USFS Florida Dispersed Camping Rules](https://www.fs.usda.gov/detail/florida/recreation/?cid=fsbdev3_063843)
- 14-day stay limit
- 150-foot setback requirements
- Prohibited activities (cutting trees, dumping waste)

**Contact**: Ocala National Forest Visitor Center  
📞 Phone: (352) 236-0288  
📧 Email: R8_Florida_NF@usda.gov

---

### Southwest Florida Water Management District (SWFWMD)

**Official Site**: [https://www.swfwmd.state.fl.us](https://www.swfwmd.state.fl.us)

**Camping & Reservations**:
- [SWFWMD Recreation & Camping](https://www.swfwmd.state.fl.us/recreation/camping)
- Free reservations required
- Designated sites only
- Property-specific rules

**Reservation System**:
- Online: [SWFWMD Recreation Portal](https://www.swfwmd.state.fl.us/recreation/)
- Phone: (352) 796-7211 (Recreation Dept)
- Email: recreation@watermatters.org

**Key Rules**:
- Advance reservation (24-48 hours)
- 3-7 day limits (varies by site)
- Pack in/pack out
- Fire restrictions (seasonal)

---

### St. Johns River Water Management District (SJRWMD)

**Official Site**: [https://www.sjrwmd.com](https://www.sjrwmd.com)

**Primitive Camping Rules**:
- [SJRWMD Recreation & Camping](https://www.sjrwmd.com/recreation/)
- 7-day consecutive limit
- Free online reservations
- Designated sites only

**Reservation System**:
- Online: [SJRWMD Recreation Reservations](https://www.sjrwmd.com/recreation/camping-reservations/)
- Phone: (386) 329-4500
- Email: recreation@sjrwmd.com

**Key Rules**:
- Hunting seasons affect access (check calendar)
- Pets allowed (leashed)
- Motorized vehicles on designated roads only
- Fires in established rings only

---

### Florida State Regulations

**Florida Fish & Wildlife Conservation Commission (FWC)**  
📖 [https://myfwc.com](https://myfwc.com)

**Relevant Regulations**:
- Hunting seasons (affects WMD access)
- Fishing licenses (if testing near water)
- Wildlife safety (bears, alligators)

---

## Pre-Trip Checklist

### 1. Legal & Permits

- [ ] **Verify site is open** (check USFS/WMD websites for closures)
- [ ] **Obtain reservation/permit** (if required)
- [ ] **Print permit/confirmation** (display at campsite)
- [ ] **Check hunting season calendar** (WMD sites - wear orange if hunting active)
- [ ] **Verify road access** (some forest roads close seasonally)

### 2. Equipment & Supplies

#### Vehicle & Navigation
- [ ] **4WD/AWD vehicle** (recommended for Ocala NF)
- [ ] **Offline maps downloaded** (Gaia GPS, OnX Offroad, or similar)
- [ ] **Tire pressure gauge & compressor** (air down for sand)
- [ ] **Recovery gear** (tow strap, shovel, traction boards)
- [ ] **Spare tire & jack** (verified functional)

#### Camping Gear
- [ ] **Tent or RV** (depending on test scenario)
- [ ] **Water** (5+ gallons minimum - no potable sources)
- [ ] **Food** (no stores nearby)
- [ ] **First aid kit**
- [ ] **Fire extinguisher**
- [ ] **Weather radio or app** (NOAA alerts)

#### Test Equipment
- [ ] **Routecast2 app installed** (latest version)
- [ ] **Test accounts** (free + premium)
- [ ] **Power bank or portable battery** (keep phone charged)
- [ ] **Notebook or tablet** (for manual observations)
- [ ] **Measuring tape** (shade/canopy measurements)
- [ ] **Compass or GPS** (verify wind direction)
- [ ] **Camera** (document road conditions, campsites)

### 3. Safety & Communication

- [ ] **Share itinerary** (someone knows where you are)
- [ ] **Check weather forecast** (avoid severe weather)
- [ ] **Verify cell coverage** (or bring satellite communicator)
- [ ] **Full tank of gas** (limited gas stations near test sites)
- [ ] **Emergency contact list** (local ranger station, tow services)

### 4. Test Plan

- [ ] **Define test scenarios** (which features to validate)
- [ ] **Prepare test cases** (expected vs actual results)
- [ ] **Review acceptance criteria** (docs/copilot/acceptance-criteria.md)
- [ ] **Load test fixtures** (for comparison with real data)

---

## Field Testing Procedures

### Day 1: Road Passability Testing

#### Morning: Dry Conditions
1. **Route Planning**
   - Open Routecast2
   - Enter route to campsite (e.g., FR 46)
   - Note predicted passability score

2. **Real-World Validation**
   - Drive route, observe surface conditions
   - Record: sandy/clay/firm, dry/wet, slope
   - Rate difficulty: easy/moderate/difficult/impassable

3. **App Comparison**
   - Does predicted score match reality?
   - Are warnings accurate? (e.g., "4WD recommended")
   - Document discrepancies

#### Afternoon: Campsite Setup
4. **Wind Shelter Assessment**
   - Use compass to identify wind direction
   - Estimate canopy cover (0%, 25%, 50%, 75%, 100%)
   - Check app's wind shelter rating
   - Validate: Does canopy/terrain block wind?

5. **Solar Exposure**
   - Note sun position at arrival
   - Estimate shade percentage at campsite
   - Record app's solar forecast
   - Set up solar panels (if available)

#### Evening: Background Notifications
6. **Weather Alert Setup**
   - Check weather forecast in app
   - Enable background notifications
   - If storm predicted, note expected alert time
   - Verify notification fires 4 hours before departure

---

### Day 2: Energy & Water Planning

#### Morning: Solar Charging
1. **Solar Forecast Validation**
   - Record actual solar panel output (if available)
   - Compare to app's predicted charging rate
   - Note discrepancies (e.g., cloud cover, canopy blocking)

2. **Battery State-of-Charge**
   - Input starting battery level in app
   - Track usage throughout day (lights, fridge, devices)
   - Compare predicted SOC to actual readings
   - Document accuracy (±10% acceptable)

#### Afternoon: Water Usage
3. **Water Planning**
   - Log water consumption in app
   - Track actual usage: cooking, cleaning, drinking
   - Compare predicted vs actual consumption
   - Note if app warnings are helpful (e.g., "Low water - 1 day remaining")

#### Evening: Connectivity Testing
4. **Cellular Signal**
   - Check app's connectivity prediction
   - Test actual signal strength (dBm)
   - Compare to predicted (excellent/good/fair/poor/none)
   - Try data-intensive tasks (weather refresh, map load)

---

### Day 3: Premium Feature Testing

#### Morning: Free User Workflow
1. **Feature Gating**
   - Sign out or use test free account
   - Attempt to use premium features:
     - Solar forecast
     - Road passability (premium)
     - Water planning (premium)
   - Verify paywall appears
   - Document which features are locked

2. **Paywall Behavior**
   - Does paywall explain feature value?
   - Is dismissal easy (not intrusive)?
   - Are free features still accessible?

#### Afternoon: Premium User Workflow
3. **Purchase/Restore**
   - Complete test purchase (sandbox mode)
   - OR restore existing purchase
   - Verify immediate unlock (no app restart)
   - Test all premium features work

4. **Persistence Check**
   - Force quit app
   - Relaunch app
   - Verify still premium (no regression)
   - Test premium features still accessible

#### Evening: Trip Planning
5. **Departure Planning**
   - Input planned departure time (e.g., next morning)
   - Check app's recommendations (delay/go/optimal time)
   - Validate weather integration
   - Test background notification fires correctly

---

## Data Collection

### Field Observation Form

Use this template for each test scenario:

```
Test Date: _____________
Location: _____________
Tester: _____________

ROAD CONDITIONS
Road Name: _____________
Surface Type: [  ] Paved  [  ] Gravel  [  ] Dirt  [  ] Sand  [  ] Clay
Condition: [  ] Dry  [  ] Wet  [  ] Muddy
Difficulty: [  ] Easy  [  ] Moderate  [  ] Difficult  [  ] Impassable
Predicted Score: _____
Actual Score (subjective): _____
Match: [  ] Yes  [  ] No
Notes: _______________________________

CAMPSITE CONDITIONS
Canopy Cover: _____%
Wind Exposure: [  ] Sheltered  [  ] Moderate  [  ] Exposed
Predicted Shelter Rating: _____
Actual (subjective): _____
Match: [  ] Yes  [  ] No
Notes: _______________________________

SOLAR/SHADE
Predicted Solar Output: _____ Wh/day
Actual Solar Output: _____ Wh/day
Difference: _____%
Acceptable (<15%): [  ] Yes  [  ] No
Notes: _______________________________

CONNECTIVITY
Predicted Quality: _____________
Actual Signal: _____ dBm
Actual Quality: _____________
Match: [  ] Yes  [  ] No
Notes: _______________________________

NOTIFICATIONS
Expected Alert Time: _____________
Actual Alert Time: _____________
Fired Correctly: [  ] Yes  [  ] No
Notes: _______________________________

PREMIUM GATING
Free User Tested: [  ] Yes  [  ] No
Paywall Appeared: [  ] Yes  [  ] No
Premium Features Locked: [  ] Yes  [  ] No
Purchase Flow Worked: [  ] Yes  [  ] No
Immediate Unlock: [  ] Yes  [  ] No
Notes: _______________________________
```

### Photo Documentation

**Required Photos**:
1. Road surface (close-up showing texture)
2. Road overview (showing width, vegetation)
3. Campsite from multiple angles
4. Overhead canopy (looking up at trees)
5. Solar panel setup (if applicable)
6. App screenshots (passability, solar, notifications)

**Naming Convention**:
```
[DATE]_[LOCATION]_[FEATURE]_[NUMBER].jpg

Examples:
2026-01-20_OcalaNF_RoadPassability_01.jpg
2026-01-20_OcalaNF_Campsite_Canopy_03.jpg
2026-01-21_PorterLake_SolarPanels_01.jpg
```

---

## Safety & Legal Compliance

### Legal Requirements

✅ **Always Follow Posted Rules**
- Obey all USFS/WMD signage
- Stay on designated roads
- Camp only in allowed areas
- Display permits where required

✅ **Respect Stay Limits**
- USFS: 14 days max
- SJRWMD: 7 days max
- SWFWMD: Varies (check permit)

✅ **Leave No Trace**
- Pack out all trash
- Don't cut vegetation
- Use existing fire rings
- Dispose of waste properly

### Safety Considerations

⚠️ **Wildlife**
- Bears active in all test areas (secure food)
- Alligators near water (maintain distance)
- Snakes (watch where you step)
- Mosquitoes (bring repellent)

⚠️ **Weather**
- Florida storms can be severe (monitor weather)
- Lightning common in summer (seek shelter)
- Heat exhaustion risk (stay hydrated)
- Flash floods possible (avoid low areas)

⚠️ **Road Hazards**
- Sandy roads can trap 2WD vehicles
- Clay roads impassable when wet
- No cell service in many areas
- Limited tow truck access

### Emergency Contacts

**Ocala National Forest**
- Ranger Station: (352) 236-0288
- Emergency: 911 (limited cell coverage)
- Nearest Hospital: Ocala Regional Medical Center (30+ miles)

**Apalachicola National Forest**
- Ranger Station: (850) 643-2282
- Emergency: 911
- Nearest Hospital: Tallahassee Memorial (40+ miles)

**SWFWMD/SJRWMD Sites**
- District Office: (varies by site)
- Emergency: 911
- Check WMD website for site-specific contacts

---

## Post-Field Reporting

### Debrief Checklist

After returning from field test:

- [ ] **Upload photos** (to project shared drive)
- [ ] **Submit field observation forms** (digital or scan)
- [ ] **Log bugs** (GitHub issues with "field-test" label)
- [ ] **Document discrepancies** (predicted vs actual)
- [ ] **Update fixtures** (if real-world data differs significantly)
- [ ] **Share findings** (team meeting or Slack)

### Bug Reporting Template

```
Title: [Field Test] [Feature] - [Issue Summary]

Location: [Site Name]
Date: [Test Date]
Tester: [Your Name]

Expected Behavior:
[What the app should have done]

Actual Behavior:
[What the app actually did]

Steps to Reproduce:
1. [Step 1]
2. [Step 2]
3. [Step 3]

Screenshots/Photos:
[Attach evidence]

Real-World Conditions:
- Surface: [sand/clay/etc]
- Weather: [clear/rain/etc]
- Canopy: [X%]
- Connectivity: [excellent/poor/etc]

Severity: [Low/Medium/High/Critical]
```

---

## Appendix: Quick Reference

### Site Comparison Matrix

| Site | Type | Permit | Stay Limit | Road Access | Water | Tests Best For |
|------|------|--------|------------|-------------|-------|----------------|
| Ocala NF (FR 46) | Dispersed | None | 14 days | 4WD (sand) | None | Road passability, wind, solar |
| Ocala NF (FR 88) | Dispersed | None | 14 days | 2WD (dry) | None | Road passability (clay) |
| Porter Lake | Primitive | None | 14 days | 2WD | None | Energy, water, off-grid |
| SWFWMD Sites | Designated | Required | 3-7 days | 2WD | None | Solar, premium, connectivity |
| SJRWMD Sites | Designated | Required | 7 days | 2WD | None | Trip planning, reservations |

### Test Scenario Priority

**High Priority** (must validate):
1. Road passability (sand, dry vs wet)
2. Solar forecast accuracy
3. Premium feature gating
4. Background weather notifications
5. Battery SOC predictions

**Medium Priority** (validate if time):
1. Wind shelter logic
2. Water consumption tracking
3. Connectivity predictions
4. Trip planning with reservations

**Low Priority** (nice to have):
1. Campsite quality scoring
2. Propane usage estimates
3. Claim log export (PDF/JSON)

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-01-18 | Initial field test playbook |

---

**Maintained by**: QA & Product Team  
**Questions?** Contact: product@routecast.com  
**Next Review**: March 2026 (post-season testing)

---

## Additional Resources

- **Test Fixtures**: `/app/src/test/resources/fixtures/`
- **Acceptance Criteria**: `/docs/copilot/acceptance-criteria.md`
- **Test Data Documentation**: `/docs/copilot/test-data.md`
- **Feature Specs**: `/docs/ROAD_PASSABILITY_FEATURE.md`, `/frontend/ANALYTICS.md`

**Stay safe, test thoroughly, and document everything!** 🏕️📱
