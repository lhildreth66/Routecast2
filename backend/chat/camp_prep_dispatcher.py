"""
Camp Prep Chat Dispatcher

Routes slash commands to appropriate domain functions with premium gating.

Commands:
  /prep-checklist - Free feature showing camping prep tasks
  /power-forecast - Premium: Solar power estimation
  /propane-usage - Premium: Propane consumption forecast
  /water-plan - Premium: Water budget planning
  /terrain-shade - Premium: Terrain shade analysis
  /wind-shelter - Premium: Wind shelter assessment
  /road-sim - Premium: Road passability simulation
  /cell-starlink - Premium: Connectivity prediction
  /camp-index - Premium: Campsite scoring
  /claim-log - Premium: Insurance claim log generation

All premium commands require active subscription.
"""

from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional
from datetime import datetime

# Import domain services
from solar_forecast_service import SolarForecastService
from propane_usage_service import PropaneUsageService
from water_budget_service import WaterBudgetService
from terrain_shade_service import TerrainShadeService
from wind_shelter_service import WindShelterService
from road_passability_service import RoadPassabilityService
from connectivity_prediction_service import cell_bars_probability, obstruction_risk
from campsite_index_service import SiteFactors, Weights, score as campsite_score
from claim_log_service import build_claim_log


@dataclass(frozen=True)
class PremiumInfo:
    """Premium gating information."""
    required: bool
    locked: bool
    feature: Optional[str] = None


@dataclass(frozen=True)
class DispatchResponse:
    """Standard response from camp prep dispatcher."""
    mode: str
    command: str
    human: str
    payload: Optional[Dict[str, Any]]
    premium: PremiumInfo
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mode": self.mode,
            "command": self.command,
            "human": self.human,
            "payload": self.payload,
            "premium": asdict(self.premium),
            "error": self.error,
        }


def _parse_args(message: str) -> Dict[str, Any]:
    """Parse key=value arguments from command string."""
    parts = message.split()
    args: Dict[str, Any] = {}
    for part in parts[1:]:  # Skip command itself
        if "=" in part:
            key, value = part.split("=", 1)
            # Attempt type conversion
            if value.lower() in ("true", "false"):
                args[key] = value.lower() == "true"
            elif value.replace(".", "", 1).replace("-", "", 1).isdigit():
                args[key] = float(value) if "." in value else int(value)
            else:
                args[key] = value
    return args


def _check_premium(subscription_id: Optional[str], feature: str) -> PremiumInfo:
    """Check if user has premium access for feature."""
    # For now, simple check - in production would query database
    has_access = subscription_id is not None and len(subscription_id) > 0
    return PremiumInfo(
        required=True,
        locked=not has_access,
        feature=feature,
    )


def _handle_prep_checklist(args: Dict[str, Any], subscription_id: Optional[str]) -> DispatchResponse:
    """Handle /prep-checklist command (free tier)."""
    has_premium = subscription_id is not None and len(subscription_id) > 0
    
    checklist = [
        "☑️ Check weather forecast",
        "☑️ Plan water supply (5-7 gal/person/day)",
        "☑️ Test propane levels",
        "☑️ Verify cell signal at site",
    ]
    
    premium_items = [
        "🔒 Run power forecast",
        "🔒 Calculate propane usage",
        "🔒 Plan water budget",
        "🔒 Check terrain shade",
        "🔒 Assess wind shelter",
    ]
    
    human = "Camp prep checklist generated."
    checklist.extend(premium_items)
    
    return DispatchResponse(
        mode="camp_prep",
        command="/prep-checklist",
        human=human,
        payload={"checklist": checklist, "premium_locked": not has_premium},
        premium=PremiumInfo(required=False, locked=False),
    )


def _handle_power_forecast(args: Dict[str, Any], subscription_id: Optional[str]) -> DispatchResponse:
    """Handle /power-forecast command (premium)."""
    premium = _check_premium(subscription_id, "solar_forecast")
    if premium.locked:
        return DispatchResponse(
            mode="camp_prep",
            command="/power-forecast",
            human="This feature requires a premium subscription. Upgrade to unlock solar power forecasting.",
            payload=None,
            premium=premium,
            error="premium_locked",
        )
    
    # Parse arguments with defaults
    lat = args.get("lat", 34.05)
    lon = args.get("lon", -111.03)
    panel_watts = args.get("panelWatts", 400)
    shade_pct = args.get("shadePct", 20)
    dates = args.get("dates", [
        datetime.now().strftime("%Y-%m-%d"),
    ])
    cloud_cover = args.get("cloudCover", [0] * len(dates))  # Match date range length
    
    if isinstance(cloud_cover, (int, float)):
        cloud_cover = [cloud_cover] * len(dates)
    
    try:
        result = SolarForecastService.forecast_daily_wh(
            lat=lat,
            lon=lon,
            date_range=dates,
            panel_watts=panel_watts,
            shade_pct=shade_pct,
            cloud_cover=cloud_cover,
        )
        
        avg_wh = sum(result.daily_wh) / len(result.daily_wh)
        human = f"Solar forecast: Avg {int(avg_wh)} Wh/day with {panel_watts}W panels. {result.advisory}"
        
        return DispatchResponse(
            mode="camp_prep",
            command="/power-forecast",
            human=human,
            payload={
                "daily_wh": result.daily_wh,
                "dates": result.dates,
                "avg_wh": int(avg_wh),
                "panel_watts": panel_watts,
                "shade_pct": shade_pct,
            },
            premium=premium,
        )
    except Exception as e:
        return DispatchResponse(
            mode="camp_prep",
            command="/power-forecast",
            human=f"Error calculating solar forecast: {str(e)}",
            payload=None,
            premium=premium,
            error="calculation_error",
        )


def _handle_propane_usage(args: Dict[str, Any], subscription_id: Optional[str]) -> DispatchResponse:
    """Handle /propane-usage command (premium)."""
    premium = _check_premium(subscription_id, "propane_usage")
    if premium.locked:
        return DispatchResponse(
            mode="camp_prep",
            command="/propane-usage",
            human="This feature requires a premium subscription. Upgrade to unlock propane usage forecasting.",
            payload=None,
            premium=premium,
            error="premium_locked",
        )
    
    furnace_btu = args.get("furnaceBtu", 20000)
    duty_cycle = args.get("dutyCycle", 50)
    temps = args.get("temps", [35, 25, 15, 45])
    people = args.get("people", 2)
    
    if isinstance(temps, int):
        temps = [temps]
    
    try:
        result = PropaneUsageService.estimate_lbs_per_day(
            furnace_btu=furnace_btu,
            duty_cycle_pct=duty_cycle,
            nights_temp_f=temps,
            people=people,
        )
        
        avg_lbs = sum(result.daily_lbs) / len(result.daily_lbs)
        human = f"Propane forecast: Avg {avg_lbs:.1f} lbs/day ({avg_lbs * 7:.1f} lbs/week). {result.advisory}"
        
        return DispatchResponse(
            mode="camp_prep",
            command="/propane-usage",
            human=human,
            payload={
                "daily_lbs": result.daily_lbs,
                "avg_lbs": round(avg_lbs, 1),
                "weekly_lbs": round(avg_lbs * 7, 1),
                "nights_temp_f": temps,
            },
            premium=premium,
        )
    except Exception as e:
        return DispatchResponse(
            mode="camp_prep",
            command="/propane-usage",
            human=f"Error calculating propane usage: {str(e)}",
            payload=None,
            premium=premium,
            error="calculation_error",
        )


def _handle_water_plan(args: Dict[str, Any], subscription_id: Optional[str]) -> DispatchResponse:
    """Handle /water-plan command (premium)."""
    premium = _check_premium(subscription_id, "water_budget")
    if premium.locked:
        return DispatchResponse(
            mode="camp_prep",
            command="/water-plan",
            human="This feature requires a premium subscription. Upgrade to unlock water budget planning.",
            payload=None,
            premium=premium,
            error="premium_locked",
        )
    
    people = args.get("people", 2)
    days = args.get("days", 7)
    shower_frequency = args.get("showerFreq", 1)
    
    try:
        result = WaterBudgetService.estimate_daily_gallons(
            people=people,
            days=days,
            shower_frequency_per_person_per_day=shower_frequency,
        )
        
        total = result.total_gallons
        daily = result.daily_avg_gallons
        human = f"Water plan: {total:.1f} gal total ({daily:.1f} gal/day) for {people} people × {days} days. {result.advisory}"
        
        return DispatchResponse(
            mode="camp_prep",
            command="/water-plan",
            human=human,
            payload={
                "total_gallons": round(total, 1),
                "daily_avg_gallons": round(daily, 1),
                "people": people,
                "days": days,
            },
            premium=premium,
        )
    except Exception as e:
        return DispatchResponse(
            mode="camp_prep",
            command="/water-plan",
            human=f"Error calculating water budget: {str(e)}",
            payload=None,
            premium=premium,
            error="calculation_error",
        )


def _handle_terrain_shade(args: Dict[str, Any], subscription_id: Optional[str]) -> DispatchResponse:
    """Handle /terrain-shade command (premium)."""
    premium = _check_premium(subscription_id, "terrain_shade")
    if premium.locked:
        return DispatchResponse(
            mode="camp_prep",
            command="/terrain-shade",
            human="This feature requires a premium subscription. Upgrade to unlock terrain shade analysis.",
            payload=None,
            premium=premium,
            error="premium_locked",
        )
    
    lat = args.get("lat", 34.05)
    lon = args.get("lon", -111.03)
    date = args.get("date", datetime.now().strftime("%Y-%m-%d"))
    ridges_str = args.get("ridges", "90,15,0;180,20,500;270,10,200")
    
    # Parse ridges
    ridges = []
    for ridge_str in ridges_str.split(";"):
        parts = ridge_str.split(",")
        if len(parts) >= 3:
            ridges.append({
                "azimuth_deg": int(parts[0]),
                "elevation_deg": int(parts[1]),
                "distance_m": int(parts[2]),
            })
    
    try:
        result = TerrainShadeService.compute_sun_path_with_shade(
            lat=lat,
            lon=lon,
            date=date,
            ridges=ridges,
        )
        
        shaded = sum(1 for slot in result.slots if slot.is_shaded)
        total = len(result.slots)
        pct = (shaded / total * 100) if total > 0 else 0
        
        human = f"Terrain shade: {shaded}/{total} hours shaded ({pct:.0f}%). {result.advisory}"
        
        return DispatchResponse(
            mode="camp_prep",
            command="/terrain-shade",
            human=human,
            payload={
                "shaded_hours": shaded,
                "total_hours": total,
                "shade_pct": round(pct, 1),
            },
            premium=premium,
        )
    except Exception as e:
        return DispatchResponse(
            mode="camp_prep",
            command="/terrain-shade",
            human=f"Error calculating terrain shade: {str(e)}",
            payload=None,
            premium=premium,
            error="calculation_error",
        )


def _handle_wind_shelter(args: Dict[str, Any], subscription_id: Optional[str]) -> DispatchResponse:
    """Handle /wind-shelter command (premium)."""
    premium = _check_premium(subscription_id, "wind_shelter")
    if premium.locked:
        return DispatchResponse(
            mode="camp_prep",
            command="/wind-shelter",
            human="This feature requires a premium subscription. Upgrade to unlock wind shelter assessment.",
            payload=None,
            premium=premium,
            error="premium_locked",
        )
    
    wind_dir = args.get("windDir", 270)
    wind_speed = args.get("windSpeed", 25)
    ridges_str = args.get("ridges", "90,15,0;180,20,500;270,10,200")
    
    ridges = []
    for ridge_str in ridges_str.split(";"):
        parts = ridge_str.split(",")
        if len(parts) >= 3:
            ridges.append({
                "azimuth_deg": int(parts[0]),
                "elevation_deg": int(parts[1]),
                "distance_m": int(parts[2]),
            })
    
    try:
        result = WindShelterService.assess_shelter(
            wind_azimuth_deg=wind_dir,
            wind_speed_mph=wind_speed,
            ridges=ridges,
        )
        
        human = f"Wind shelter: {result.shelter_quality} ({result.reduction_pct:.0f}% reduction). {result.advisory}"
        
        return DispatchResponse(
            mode="camp_prep",
            command="/wind-shelter",
            human=human,
            payload={
                "shelter_quality": result.shelter_quality,
                "reduction_pct": round(result.reduction_pct, 1),
                "effective_wind_mph": round(result.effective_wind_mph, 1),
            },
            premium=premium,
        )
    except Exception as e:
        return DispatchResponse(
            mode="camp_prep",
            command="/wind-shelter",
            human=f"Error calculating wind shelter: {str(e)}",
            payload=None,
            premium=premium,
            error="calculation_error",
        )


def _handle_road_sim(args: Dict[str, Any], subscription_id: Optional[str]) -> DispatchResponse:
    """Handle /road-sim command (premium)."""
    premium = _check_premium(subscription_id, "road_passability")
    if premium.locked:
        return DispatchResponse(
            mode="camp_prep",
            command="/road-sim",
            human="This feature requires a premium subscription. Upgrade to unlock road passability simulation.",
            payload=None,
            premium=premium,
            error="premium_locked",
        )
    
    precip_72h = args.get("precip72h", 30)
    slope_pct = args.get("slopePct", 8)
    min_temp_f = args.get("minTempF", 35)
    soil_type = args.get("soilType", "clay")
    
    try:
        result = RoadPassabilityService.assess_road_passability(
            precip_72h=precip_72h,
            slope_pct=slope_pct,
            min_temp_f=min_temp_f,
            soil_type=soil_type,
        )
        
        human = f"Road conditions: {result.condition_assessment} (score {result.passability_score:.0f}/100). {result.advisory}"
        
        return DispatchResponse(
            mode="camp_prep",
            command="/road-sim",
            human=human,
            payload={
                "score": round(result.passability_score, 0),
                "condition": result.condition_assessment,
                "mud_risk": result.risks.mud_risk if hasattr(result.risks, 'mud_risk') else False,
                "ice_risk": result.risks.ice_risk if hasattr(result.risks, 'ice_risk') else False,
                "needs_4x4": result.risks.four_x_four_recommended,
            },
            premium=premium,
        )
    except Exception as e:
        return DispatchResponse(
            mode="camp_prep",
            command="/road-sim",
            human=f"Error simulating road conditions: {str(e)}",
            payload=None,
            premium=premium,
            error="calculation_error",
        )


def _handle_cell_starlink(args: Dict[str, Any], subscription_id: Optional[str]) -> DispatchResponse:
    """Handle /cell-starlink command (premium)."""
    premium = _check_premium(subscription_id, "connectivity_prediction")
    if premium.locked:
        return DispatchResponse(
            mode="camp_prep",
            command="/cell-starlink",
            human="This feature requires a premium subscription. Upgrade to unlock connectivity predictions.",
            payload=None,
            premium=premium,
            error="premium_locked",
        )
    
    carrier = args.get("carrier", "verizon")
    tower_distance_km = args.get("towerDistanceKm", 8)
    terrain_obstruction = args.get("terrainObstruction", 45)
    horizon_south_deg = args.get("horizonSouthDeg", 30)
    canopy_pct = args.get("canopyPct", 60)
    
    try:
        cell_result = cell_bars_probability(carrier, tower_distance_km, terrain_obstruction)
        starlink_result = obstruction_risk(horizon_south_deg, canopy_pct)
        
        human = f"Connectivity: {cell_result.bar_estimate} cell signal, {starlink_result.risk_level} Starlink risk."
        
        return DispatchResponse(
            mode="camp_prep",
            command="/cell-starlink",
            human=human,
            payload={
                "cell_bars": cell_result.bar_estimate,
                "cell_probability": round(cell_result.probability, 2),
                "starlink_risk": starlink_result.risk_level,
            },
            premium=premium,
        )
    except Exception as e:
        return DispatchResponse(
            mode="camp_prep",
            command="/cell-starlink",
            human=f"Error predicting connectivity: {str(e)}",
            payload=None,
            premium=premium,
            error="calculation_error",
        )


def _handle_camp_index(args: Dict[str, Any], subscription_id: Optional[str]) -> DispatchResponse:
    """Handle /camp-index command (premium)."""
    premium = _check_premium(subscription_id, "campsite_index")
    if premium.locked:
        return DispatchResponse(
            mode="camp_prep",
            command="/camp-index",
            human="This feature requires a premium subscription. Upgrade to unlock campsite scoring.",
            payload=None,
            premium=premium,
            error="premium_locked",
        )
    
    wind_gust = args.get("windGust", 15)
    shade = args.get("shade", 0.6)
    slope = args.get("slope", 5)
    access = args.get("access", 0.8)
    signal = args.get("signal", 0.7)
    road_score = args.get("roadScore", 75)
    
    try:
        site = SiteFactors(
            wind_gust_mph=wind_gust,
            shade_score=shade,
            slope_pct=slope,
            access_score=access,
            signal_score=signal,
            road_passability_score=road_score,
        )
        result = campsite_score(site)
        
        human = f"Campsite index: {result.score}/100. Site is rated as {'excellent' if result.score >= 80 else 'good' if result.score >= 60 else 'fair' if result.score >= 40 else 'poor'}."
        
        return DispatchResponse(
            mode="camp_prep",
            command="/camp-index",
            human=human,
            payload={
                "score": result.score,
                "breakdown": result.breakdown,
            },
            premium=premium,
        )
    except Exception as e:
        return DispatchResponse(
            mode="camp_prep",
            command="/camp-index",
            human=f"Error calculating campsite index: {str(e)}",
            payload=None,
            premium=premium,
            error="calculation_error",
        )


def _handle_claim_log(args: Dict[str, Any], subscription_id: Optional[str]) -> DispatchResponse:
    """Handle /claim-log command (premium)."""
    premium = _check_premium(subscription_id, "claim_log")
    if premium.locked:
        return DispatchResponse(
            mode="camp_prep",
            command="/claim-log",
            human="This feature requires a premium subscription. Upgrade to unlock insurance claim log generation.",
            payload=None,
            premium=premium,
            error="premium_locked",
        )
    
    # Simplified - would parse complex hazard/weather data in production
    human = "Claim log generation: Use the dedicated /pro/claim-log/build endpoint for full functionality."
    
    return DispatchResponse(
        mode="camp_prep",
        command="/claim-log",
        human=human,
        payload={"note": "Use /pro/claim-log/build API for detailed claim generation"},
        premium=premium,
    )


def _handle_unknown_command(command: str) -> DispatchResponse:
    """Handle unknown command."""
    supported = [
        "/prep-checklist",
        "/power-forecast",
        "/propane-usage",
        "/water-plan",
        "/terrain-shade",
        "/wind-shelter",
        "/road-sim",
        "/cell-starlink",
        "/camp-index",
        "/claim-log",
    ]
    
    return DispatchResponse(
        mode="camp_prep",
        command=command,
        human=f"Unknown command: {command}. Supported commands: {', '.join(supported)}",
        payload={"supported_commands": supported},
        premium=PremiumInfo(required=False, locked=False),
        error="unknown_command",
    )


def dispatch(message: str, subscription_id: Optional[str] = None) -> DispatchResponse:
    """
    Dispatch a camp prep command to the appropriate handler.
    
    Args:
        message: Command string starting with /
        subscription_id: Optional subscription ID for premium gating
        
    Returns:
        DispatchResponse with human summary, payload, and premium info
    """
    message = message.strip()
    
    if not message.startswith("/"):
        return DispatchResponse(
            mode="camp_prep",
            command="",
            human="Commands must start with /. Try /prep-checklist to see available commands.",
            payload=None,
            premium=PremiumInfo(required=False, locked=False),
            error="invalid_format",
        )
    
    parts = message.split()
    command = parts[0].lower()
    args = _parse_args(message)
    
    handlers = {
        "/prep-checklist": _handle_prep_checklist,
        "/power-forecast": _handle_power_forecast,
        "/propane-usage": _handle_propane_usage,
        "/water-plan": _handle_water_plan,
        "/terrain-shade": _handle_terrain_shade,
        "/wind-shelter": _handle_wind_shelter,
        "/road-sim": _handle_road_sim,
        "/cell-starlink": _handle_cell_starlink,
        "/camp-index": _handle_camp_index,
        "/claim-log": _handle_claim_log,
    }
    
    handler = handlers.get(command)
    if handler:
        return handler(args, subscription_id)
    else:
        return _handle_unknown_command(command)
