import pytest

from server import CampingSpot, _dedupe_camping_spots


def test_free_camping_dedupes_by_bucket_and_prefers_rating_cell_then_distance():
    base = {
        "type": "Campground",
        "description": "Test",
        "amenities": ["Water"],
        "stay_limit": "14 days",
        "access_difficulty": "easy",
        "elevation_ft": 1000,
        "free": True,
    }

    # Same ~0.1 mile cluster -> should keep the higher-rated with known cell, even if slightly farther.
    spot_a = CampingSpot(
        name="Lower Rated Unknown",
        distance_miles=2.0,
        latitude=41.7612,
        longitude=-91.5663,
        cell_coverage="unknown",
        rating=3.6,
        **base,
    )
    spot_b = CampingSpot(
        name="Higher Rated Known",
        distance_miles=2.5,
        latitude=41.7614,
        longitude=-91.5662,
        cell_coverage="good",
        rating=4.4,
        **base,
    )
    # Same rating as spot_b but unknown coverage and closer distance -> spot_b should still win due to coverage.
    spot_c = CampingSpot(
        name="Equal Rating Unknown",
        distance_miles=1.5,
        latitude=41.7615,
        longitude=-91.5661,
        cell_coverage="unknown",
        rating=4.4,
        **base,
    )

    # Different bucket
    spot_d = CampingSpot(
        name="Different Bucket",
        distance_miles=3.0,
        latitude=41.7721,
        longitude=-91.5701,
        cell_coverage="fair",
        rating=4.0,
        **base,
    )

    deduped = _dedupe_camping_spots([spot_a, spot_b, spot_c, spot_d], precision=3)

    assert len(deduped) == 2

    # Verify the cluster kept the higher-rated + known coverage entry
    cluster_key = (round(41.7612, 3), round(-91.5663, 3))
    kept = next(s for s in deduped if (round(s.latitude, 3), round(s.longitude, 3)) == cluster_key)
    assert kept.name == "Higher Rated Known"
    assert kept.cell_coverage == "good"

    # Ensure the other bucket remains
    other = next(s for s in deduped if s.name == "Different Bucket")
    assert other.latitude == pytest.approx(41.7721)
    assert other.longitude == pytest.approx(-91.5701)
