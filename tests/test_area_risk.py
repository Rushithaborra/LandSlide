"""GET /zones/near -- the risk picture around a typed place or GPS point.
The SQL distance filter is exercised against the real database when running
the app; these pin the behaviour around it (shape, counting, honesty when
nothing is assessed, input validation). No DB."""
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app


def _zone(tier, name="NH10 (1_00_001)"):
    return SimpleNamespace(
        id=uuid.uuid4(), name=name, state="Sikkim", susceptibility_score=0.5, risk_tier=tier,
        model_version="m", last_updated=datetime(2026, 9, 1, tzinfo=timezone.utc), centroid_lat=27.3, centroid_lng=88.6,
    )


@pytest.fixture
def client():
    db = MagicMock()
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app), db
    app.dependency_overrides.pop(get_db, None)


def test_reports_the_nearest_zone_and_counts_tiers_in_the_radius(client):
    c, db = client
    rows = [(_zone("low"), 0.1234), (_zone("high"), 0.8), (_zone("high"), 1.4), (_zone("moderate"), 2.0), (_zone(None), 2.5)]
    db.execute.return_value.all.return_value = rows
    db.scalar.return_value = 2
    body = c.get("/zones/near", params={"lat": 27.3, "lng": 88.6}).json()
    assert body["zone"]["risk_tier"] == "low" and body["distance_km"] == 0.12
    assert body["counts"] == {"high": 2, "moderate": 1, "low": 1, "unscored": 1}  # the nearest alone would hide the two high ones
    assert body["active_alerts"] == 2 and body["radius_km"] == 3.0


def test_nothing_assessed_nearby_or_further_out_says_so_instead_of_guessing(client):
    c, db = client
    db.execute.return_value.all.return_value = []
    db.execute.return_value.first.return_value = None  # the wider fallback search also finds nothing
    body = c.get("/zones/near", params={"lat": 28.6, "lng": 77.2}).json()  # Delhi -- nowhere near any NER zone
    assert body["zone"] is None and body["distance_km"] is None and body["active_alerts"] == 0
    assert body["counts"] == {"high": 0, "moderate": 0, "low": 0, "unscored": 0}
    assert body["nearest_beyond_radius"] is None and body["nearest_beyond_radius_km"] is None
    db.scalar.assert_not_called()  # no alert lookup without zones


def test_a_point_just_outside_the_radius_reports_the_true_nearest_zone_honestly(client):
    """The exact real-world case this guards: geocoding a whole state's own broad
    centroid (e.g. searching "Assam") lands nowhere near a specific road, even though
    the state has thousands of real zones -- the answer must say so, not "not assessed"."""
    c, db = client
    db.execute.side_effect = [
        SimpleNamespace(all=lambda: []),  # nothing within the requested (e.g. 3km) radius
        SimpleNamespace(first=lambda: (_zone("high", name="NH27 (99_00_004)"), 8.45)),  # but real data 8.45km away
    ]
    body = c.get("/zones/near", params={"lat": 26.4073841, "lng": 93.2551303}).json()
    assert body["zone"] is None  # still honestly nothing THIS close
    assert body["nearest_beyond_radius"]["risk_tier"] == "high" and body["nearest_beyond_radius_km"] == 8.4


@pytest.mark.parametrize("params", [{"lat": 95, "lng": 88}, {"lat": 27, "lng": 200}, {"lat": 27, "lng": 88, "radius_km": 50}, {"lat": 27, "lng": 88, "radius_km": 0}, {"lng": 88}])
def test_rejects_impossible_or_oversized_queries(client, params):
    c, _ = client
    assert c.get("/zones/near", params=params).status_code == 422
