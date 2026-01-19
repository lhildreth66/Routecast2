from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from .contracts import (
    AlertsProvider,
    CellCoverageProvider,
    DirectionsProvider,
    ElevationProvider,
    GeocodeProvider,
    PublicLandsProvider,
    RadarProvider,
    SoilProvider,
    WeatherProvider,
    WildfireProvider,
)
from .fake_providers import (
    FakeAlertsProvider,
    FakeCellCoverageProvider,
    FakeDirectionsProvider,
    FakeElevationProvider,
    FakeGeocodeProvider,
    FakePublicLandsProvider,
    FakeRadarProvider,
    FakeSoilProvider,
    FakeWeatherProvider,
    FakeWildfireProvider,
)
from .real_providers import (
    DefaultCellCoverageProvider,
    DefaultElevationProvider,
    DefaultPublicLandsProvider,
    DefaultRadarProvider,
    DefaultSoilProvider,
    DefaultWildfireProvider,
    MapboxDirectionsProvider,
    MapboxGeocodeProvider,
    NOAAAlertsProvider,
    NOAAWeatherProvider,
)


@dataclass
class ProviderSet:
    geocode: GeocodeProvider
    directions: DirectionsProvider
    weather: WeatherProvider
    alerts: AlertsProvider
    elevation: ElevationProvider
    soil: SoilProvider
    cell: CellCoverageProvider
    wildfire: WildfireProvider
    public_lands: PublicLandsProvider
    radar: RadarProvider


def _build_prod() -> ProviderSet:
    return ProviderSet(
        geocode=MapboxGeocodeProvider(),
        directions=MapboxDirectionsProvider(),
        weather=NOAAWeatherProvider(),
        alerts=NOAAAlertsProvider(),
        elevation=DefaultElevationProvider(),
        soil=DefaultSoilProvider(),
        cell=DefaultCellCoverageProvider(),
        wildfire=DefaultWildfireProvider(),
        public_lands=DefaultPublicLandsProvider(),
        radar=DefaultRadarProvider(),
    )


def _build_fake() -> ProviderSet:
    return ProviderSet(
        geocode=FakeGeocodeProvider(),
        directions=FakeDirectionsProvider(),
        weather=FakeWeatherProvider(),
        alerts=FakeAlertsProvider(),
        elevation=FakeElevationProvider(),
        soil=FakeSoilProvider(),
        cell=FakeCellCoverageProvider(),
        wildfire=FakeWildfireProvider(),
        public_lands=FakePublicLandsProvider(),
        radar=FakeRadarProvider(),
    )


_provider_cache: Optional[ProviderSet] = None


def load_providers(mode: Optional[str] = None) -> ProviderSet:
    global _provider_cache
    active_mode = (mode or os.environ.get("ROUTECAST_MODE", "prod")).lower()
    if _provider_cache and mode is None:
        return _provider_cache
    if active_mode in {"demo", "test"}:
        _provider_cache = _build_fake()
    else:
        _provider_cache = _build_prod()
    return _provider_cache


def get_providers() -> ProviderSet:
    return load_providers()


def reload_providers(mode: Optional[str] = None) -> ProviderSet:
    global _provider_cache
    _provider_cache = None
    return load_providers(mode)
