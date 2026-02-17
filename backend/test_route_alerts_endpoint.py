import asyncio
import os
from datetime import datetime, timedelta

from httpx import ASGITransport, AsyncClient

from providers import reload_providers
from server import app, cache_route_context


def test_route_alerts_endpoint_returns_shape():
    """Ensure the alerts endpoint returns a stable JSON contract and does not raise."""

    os.environ["ROUTECAST_MODE"] = "test"
    reload_providers("test")

    route_id = "test-route-alerts-endpoint"
    now = datetime.utcnow()
    cache_route_context(
        route_id,
        {
            "hazard_waypoints": [
                {
                    "lat": 47.6062,
                    "lon": -122.3321,
                    "name": "Seattle",
                    "distance_from_start": 0.0,
                    "eta_minutes": 0,
                    "arrival_time": now.isoformat(),
                },
                {
                    "lat": 45.5152,
                    "lon": -122.6784,
                    "name": "Portland",
                    "distance_from_start": 175.0,
                    "eta_minutes": 180,
                    "arrival_time": (now + timedelta(hours=3)).isoformat(),
                },
            ],
            "departure_time": now.isoformat(),
            "total_distance_miles": 175.0,
            "total_duration_minutes": 180,
            "route_geometry": "",
            "origin": "Seattle, WA",
            "destination": "Portland, OR",
        },
    )

    async def _run():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/api/route/weather/alerts/{route_id}")
        assert response.status_code == 200
        payload = response.json()

        assert payload["route_id"] == route_id
        assert payload.get("status") in {"pending", "ready", "error"}
        assert isinstance(payload.get("alerts"), list)
        assert isinstance(payload.get("hazard_alerts"), list)
        assert isinstance(payload.get("weather_alert_cards"), list)
        assert len(payload.get("weather_alert_cards", [])) <= 10

        # No duplicate IDs in returned cards
        ids = [card.get("id") or card.get("alert_id") for card in payload.get("weather_alert_cards", [])]
        ids = [i for i in ids if i]
        assert len(ids) == len(set(ids))
        assert "road_conditions" in payload
        assert "weather_conditions" in payload
        # Should always return a contract, even when no alerts are present
        assert "error" in payload

    asyncio.run(_run())
