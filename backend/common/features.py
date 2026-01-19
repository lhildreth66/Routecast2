"""
Premium Feature Definitions

Shared constants for premium features across backend.
These must match the frontend definitions exactly.
"""

# Premium feature identifiers
SOLAR_FORECAST = "solar_forecast"
BATTERY_SOC = "battery_soc"
PROPANE_USAGE = "propane_usage"
ROAD_SIM = "road_sim"
CELL_STARLINK = "cell_starlink"
EVAC_OPTIMIZER = "evac_optimizer"
CLAIM_LOG = "claim_log"
SMART_DELAY_ALERTS = "smart_delay_alerts"

# All premium features
PREMIUM_FEATURES = {
    SOLAR_FORECAST,
    BATTERY_SOC,
    PROPANE_USAGE,
    ROAD_SIM,
    CELL_STARLINK,
    EVAC_OPTIMIZER,
    CLAIM_LOG,
    SMART_DELAY_ALERTS,
}


def is_premium_feature(feature: str) -> bool:
    """Check if a feature ID is a valid premium feature."""
    return feature in PREMIUM_FEATURES
