import pytest

from backend.server import _stable_place_key, _dedupe_places


def test_stable_place_key_prefers_ids_over_name_coord():
    # place_id wins
    k1 = _stable_place_key("Name", 10.123456, -20.98765, place_id="pid-1", source_id="sid-2")
    assert k1 == "pid-1"
    # source_id next
    k2 = _stable_place_key("Name", 10.123456, -20.98765, source_id="sid-2")
    assert k2 == "sid-2"
    # fallback name+coord rounded 4
    k3 = _stable_place_key("Name Here", 10.123456, -20.98765)
    assert k3 == "name here:10.1235,-20.9876"


def test_dedupe_places_collapses_by_normalized_name_and_coords():
    class Item:
        def __init__(self, name, lat, lon, dist):
            self.name = name
            self.lat = lat
            self.lon = lon
            self.dist = dist

    items = [
        Item("Test Place", 10.12341, -20.98764, 5.0),
        Item("test   place!!", 10.12344, -20.98761, 4.0),  # same rounded coord/name at 4 decimals
        Item("Other", 10.2000, -20.9000, 3.0),
    ]

    def key_fn(it: Item):
        return _stable_place_key(it.name, it.lat, it.lon)

    def prefer(candidate: Item, current: Item):
        return candidate.dist < current.dist

    deduped = _dedupe_places(items, key_fn, prefer)
    assert len(deduped) == 2
    # Best distance kept for first key
    kept = next(x for x in deduped if _stable_place_key(x.name, x.lat, x.lon) == "test place:10.1234,-20.9876")
    assert kept.dist == 4.0


@pytest.mark.asyncio
async def test_cracker_barrel_overpass_failure_returns_empty_and_error(monkeypatch):
    from backend import server

    async def fake_fetch(*args, **kwargs):
        raise TimeoutError("overpass down")

    monkeypatch.setattr(server, "_fetch_overpass_first_success", fake_fetch)
    req = server.OvernightSearchRequest(latitude=0, longitude=0, radius_miles=10)
    resp = await server.search_cracker_barrel(req)

    assert resp.ok is True
    assert resp.spots == []
    assert resp.error == "overpass_unavailable"
