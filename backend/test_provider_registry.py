import os
import pytest

from providers.fake_providers import (
    FakeAlertsProvider,
    FakeDirectionsProvider,
    FakeGeocodeProvider,
    FakeWeatherProvider,
)
from providers.registry import get_providers, reload_providers
from providers.real_providers import MapboxDirectionsProvider, MapboxGeocodeProvider


@pytest.fixture(autouse=True)
def _demo_mode(monkeypatch):
    monkeypatch.setenv("ROUTECAST_MODE", "demo")
    reload_providers()
    yield
    reload_providers("prod")


def test_demo_mode_uses_fakes():
    providers = get_providers()
    assert isinstance(providers.geocode, FakeGeocodeProvider)
    assert isinstance(providers.directions, FakeDirectionsProvider)
    assert isinstance(providers.weather, FakeWeatherProvider)
    assert isinstance(providers.alerts, FakeAlertsProvider)


@pytest.mark.asyncio
async def test_geocode_deterministic():
    providers = get_providers()
    first = await providers.geocode.geocode("Seattle, WA")
    second = await providers.geocode.geocode("Seattle, WA")
    assert first == second == {"lat": 47.6062, "lon": -122.3321}


@pytest.mark.asyncio
async def test_directions_fixture_reused():
    providers = get_providers()
    origin = {"lat": 47.6062, "lon": -122.3321}
    dest = {"lat": 45.5152, "lon": -122.6784}
    first = await providers.directions.route(origin, dest, None)
    second = await providers.directions.route(origin, dest, None)
    assert first == second
    assert first["geometry"]
    assert first["duration"] == 180


def test_prod_mode_switch(monkeypatch):
    monkeypatch.setenv("ROUTECAST_MODE", "prod")
    reload_providers()
    providers = get_providers()
    assert isinstance(providers.geocode, MapboxGeocodeProvider)
    assert isinstance(providers.directions, MapboxDirectionsProvider)
