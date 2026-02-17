import asyncio
import httpx
import pytest

import server
from server import OvernightSearchRequest, _search_boondockers_google_places, _fetch_overpass_data


@pytest.mark.asyncio
async def test_google_places_dedupes_by_place_id():
    req = OvernightSearchRequest(lat=0.0, lon=0.0, radius_miles=10)

    payloads = {
        None: (
            200,
            {
                "places": [
                    {
                        "id": "p1",
                        "displayName": {"text": "Alpha"},
                        "location": {"latitude": 0.0, "longitude": 0.0},
                    },
                    {
                        "id": "p2",
                        "displayName": {"text": "Beta"},
                        "location": {"latitude": 0.1, "longitude": 0.0},
                    },
                ],
                "nextPageToken": "token-1",
            },
        ),
        "token-1": (
            200,
            {
                "places": [
                    {
                        "id": "p2",
                        "displayName": {"text": "Beta Duplicate"},
                        "location": {"latitude": 0.1, "longitude": 0.0},
                    },
                    {
                        "id": "p3",
                        "displayName": {"text": "Gamma"},
                        "location": {"latitude": 0.2, "longitude": 0.0},
                    },
                ]
            },
        ),
    }

    async def fake_fetch(page_token):
        return payloads[page_token]

    async def no_sleep(_):
        return None

    spots, debug = await _search_boondockers_google_places(
        req, fetch_page_fn=fake_fetch, sleep_fn=no_sleep
    )

    assert len(spots) == 3
    assert len({s.osm_id for s in spots}) == 3
    assert debug["status"] == "OK"
    assert debug.get("unique_place_ids") == 3


@pytest.mark.asyncio
async def test_next_page_token_retry():
    req = OvernightSearchRequest(lat=0.0, lon=0.0, radius_miles=5)

    calls = {"token-1": 0}

    async def fake_fetch(page_token):
        if page_token is None:
            return (
                200,
                {
                    "places": [
                        {
                            "id": "p1",
                            "displayName": {"text": "Alpha"},
                            "location": {"latitude": 0.0, "longitude": 0.0},
                        }
                    ],
                    "nextPageToken": "token-1",
                },
            )
        calls["token-1"] += 1
        if calls["token-1"] == 1:
            return (
                400,
                {
                    "error": {
                        "status": "INVALID_ARGUMENT",
                        "message": "next page token not yet ready",
                    }
                },
            )
        return (
            200,
            {
                "places": [
                    {
                        "id": "p2",
                        "displayName": {"text": "Beta"},
                        "location": {"latitude": 0.05, "longitude": 0.0},
                    }
                ]
            },
        )

    async def no_sleep(_):
        return None

    spots, debug = await _search_boondockers_google_places(
        req, fetch_page_fn=fake_fetch, sleep_fn=no_sleep
    )

    assert len(spots) == 2
    assert debug["status"] == "OK"
    assert calls["token-1"] == 2  # retried once before succeeding


@pytest.mark.asyncio
async def test_zero_results_reports_debug():
    req = OvernightSearchRequest(lat=1.0, lon=1.0, radius_miles=5)

    async def fake_fetch(page_token):
        return 200, {"places": []}

    async def no_sleep(_):
        return None

    spots, debug = await _search_boondockers_google_places(
        req, fetch_page_fn=fake_fetch, sleep_fn=no_sleep
    )

    assert spots == []
    assert debug["status"] == "ZERO_RESULTS"
    assert debug["reason"]
    assert debug.get("unique_place_ids") == 0


@pytest.mark.asyncio
async def test_overpass_retries_on_429_then_succeeds(monkeypatch):
    calls = []

    # Speed up backoff during test
    async def no_sleep(_):
        return None

    monkeypatch.setattr(server.asyncio, "sleep", no_sleep)

    # Use a small deterministic pool so order is predictable
    monkeypatch.setattr(server, "OVERPASS_URLS", ["https://overpass-one.test", "https://overpass-two.test"])

    async def fake_post(url: str, _: str):
        req = httpx.Request("POST", url)
        if not calls:
            calls.append((url, 429))
            return httpx.Response(status_code=429, request=req, json={"error": "rate limited"})
        calls.append((url, 200))
        return httpx.Response(
            status_code=200,
            request=req,
            json={"elements": [{"type": "node", "lat": 0.0, "lon": 0.0, "tags": {}}]},
        )

    result = await _fetch_overpass_data("fake-query", "Boondockers", post_fn=fake_post)

    assert result.get("elements")
    # First endpoint 429, second succeeds
    assert calls[0] == ("https://overpass-one.test", 429)
    assert calls[1] == ("https://overpass-two.test", 200)
