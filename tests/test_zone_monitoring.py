"""Whether a zone is actually checked for live rainfall is a fact most zones
lack: only the handful select_zones() picks per state ever get a rainfall
reading, so the other tens of thousands must never look "checked and safe" in
/zones, /zones/map or /zones/stats -- they were simply never asked. These tests
pin that _monitored_ids() (reusing select_zones(), not a re-derived rule)
propagates the same true/false and the same count everywhere a zone or a
cluster is shown."""
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.routers import zones as zones_router

MONITORED, UNMONITORED = uuid.uuid4(), uuid.uuid4()


def _zone(zid, tier="high", name="NH10 (1_00_001)", state="Sikkim"):
    return SimpleNamespace(
        id=zid, name=name, state=state, susceptibility_score=0.5, risk_tier=tier,
        model_version="m", last_updated=datetime(2026, 9, 1, tzinfo=timezone.utc), centroid_lat=27.3, centroid_lng=88.6,
    )


@pytest.fixture
def client(monkeypatch):
    # select_zones is replaced with a fixed, real-shaped result -- exactly
    # what it would return, without needing to sequence its own several
    # db.execute calls (a per-state loop plus an active-alerts join) through
    # the same mock these tests use for the endpoint's own query.
    monkeypatch.setattr(zones_router, "select_zones", lambda db, per_state: [SimpleNamespace(id=MONITORED)])
    db = MagicMock()
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app), db
    app.dependency_overrides.pop(get_db, None)


def test_zone_list_flags_the_monitored_zone_and_not_the_other(client):
    c, db = client
    db.query.return_value.options.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [
        _zone(MONITORED), _zone(UNMONITORED),
    ]
    body = c.get("/zones").json()
    by_id = {z["id"]: z for z in body}
    assert by_id[str(MONITORED)]["rainfall_monitored"] is True
    assert by_id[str(UNMONITORED)]["rainfall_monitored"] is False


def test_single_zone_lookup_reports_its_own_monitoring_status(client):
    c, db = client
    db.get.return_value = _zone(UNMONITORED)
    assert c.get(f"/zones/{UNMONITORED}").json()["rainfall_monitored"] is False
    db.get.return_value = _zone(MONITORED)
    assert c.get(f"/zones/{MONITORED}").json()["rainfall_monitored"] is True


def test_zone_stats_reports_how_many_of_the_total_are_monitored(client):
    c, db = client
    # total, high, moderate, low, unscored, monitored, min_lat, min_lng, max_lat, max_lng
    db.execute.return_value.one.return_value = (100, 40, 30, 20, 10, 1, 27.0, 88.0, 28.0, 89.0)
    body = c.get("/zones/stats").json()
    assert body["total"] == 100 and body["monitored"] == 1


def test_map_zones_mode_flags_each_pin(client):
    c, db = client
    db.query.return_value.select_from.return_value.filter.return_value.scalar.return_value = 2
    db.query.return_value.options.return_value.filter.return_value.order_by.return_value.all.return_value = [
        _zone(MONITORED), _zone(UNMONITORED),
    ]
    body = c.get("/zones/map", params={"min_lat": 27, "min_lng": 88, "max_lat": 28, "max_lng": 89}).json()
    assert body["mode"] == "zones"
    by_id = {z["id"]: z for z in body["zones"]}
    assert by_id[str(MONITORED)]["rainfall_monitored"] is True
    assert by_id[str(UNMONITORED)]["rainfall_monitored"] is False


def test_map_cluster_mode_reports_how_many_in_the_cell_are_monitored(client):
    c, db = client
    # Above MAP_MAX_INDIVIDUAL_ZONES so the backend switches to grid clusters.
    db.query.return_value.select_from.return_value.filter.return_value.scalar.return_value = 5000
    # lat, lng, count, high, moderate, low, unscored, monitored, min_lat, min_lng, max_lat, max_lng
    db.execute.return_value.all.return_value = [(27.5, 88.5, 3000, 1000, 1000, 900, 100, 1, 27.0, 88.0, 28.0, 89.0)]
    body = c.get("/zones/map", params={"min_lat": 27, "min_lng": 88, "max_lat": 28, "max_lng": 89}).json()
    assert body["mode"] == "clusters"
    assert body["clusters"][0]["count"] == 3000 and body["clusters"][0]["monitored"] == 1


def test_area_around_a_monitored_zone_flags_it_too(client):
    c, db = client
    zone = _zone(MONITORED, tier="high")
    db.execute.return_value.all.return_value = [(zone, 0.3)]
    db.scalar.return_value = 0
    body = c.get("/zones/near", params={"lat": 27.3, "lng": 88.6}).json()
    assert body["zone"]["rainfall_monitored"] is True
