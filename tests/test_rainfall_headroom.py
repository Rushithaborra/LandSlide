"""GET /rainfall/headroom -- how close each state's real rainfall is to its own
threshold, using the same strongest_ratio the alert engine itself uses. Answers
"is this state's rule really watching" honestly for a state with 0 active alerts."""
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.config import RainfallThresholdConfig
from app.database import get_db
from app.main import app
from app.routers import rainfall as rainfall_router

TODAY = datetime(2026, 9, 26, tzinfo=timezone.utc)
HIGH_ZONE, LOW_ZONE = uuid.uuid4(), uuid.uuid4()

CONFIG = RainfallThresholdConfig(region="test", coefficient=50.0, exponent=0.0, durations_days=[1], source="a real study")


def target(zid, state, tier):
    return SimpleNamespace(id=zid, state=state, risk_tier=tier, lat=27.0, lng=88.0)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(rainfall_router, "select_zones", lambda db, n: [target(HIGH_ZONE, "Assam", "high"), target(LOW_ZONE, "Meghalaya", "moderate")])
    monkeypatch.setattr(rainfall_router, "get_rainfall_threshold", lambda state: CONFIG)
    monkeypatch.setattr(rainfall_router, "can_alert", lambda state: state == "Assam")
    db = MagicMock()
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app), db
    app.dependency_overrides.pop(get_db, None)


def readings_row(zid, mm, day=TODAY):
    return (zid, day, mm)


def test_reports_the_real_ratio_and_the_real_alerting_flag_per_state(client):
    c, db = client
    # Assam (high tier, so its 50mm/day threshold is scaled to 40 via the 0.8x multiplier): 40mm
    # -> ratio 1.0, exactly at the line. Meghalaya (moderate, unscaled 50mm/day): 60mm -> ratio 1.2, over it.
    db.execute.side_effect = [
        SimpleNamespace(all=lambda: [readings_row(HIGH_ZONE, 40.0), readings_row(LOW_ZONE, 60.0)]),
        SimpleNamespace(all=lambda: [(HIGH_ZONE, "NH27 (1_00_001)"), (LOW_ZONE, "SH-5 (2_00_002)")]),
    ]
    body = c.get("/rainfall/headroom").json()
    by_state = {s["state"]: s for s in body["states"]}
    assert by_state["Assam"] == {
        "state": "Assam", "alerting_enabled": True, "zone_name": "NH27 (1_00_001)", "risk_tier": "high", "ratio": 1.0, "threshold_source": "a real study",
        "top_zones": [{"zone_name": "NH27 (1_00_001)", "risk_tier": "high", "ratio": 1.0}],
    }
    # Meghalaya has REALLY crossed its own line (ratio 1.2) but alerting_enabled is honestly False --
    # the two facts are independent, and this must never blend them into one misleading number.
    assert by_state["Meghalaya"]["ratio"] == 1.2 and by_state["Meghalaya"]["alerting_enabled"] is False


def test_the_watch_list_is_every_monitored_zones_own_real_ratio_closest_first(monkeypatch):
    z1, z2, z3 = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    monkeypatch.setattr(rainfall_router, "select_zones", lambda db, n: [target(z1, "Manipur", "high"), target(z2, "Manipur", "moderate"), target(z3, "Manipur", "low")])
    monkeypatch.setattr(rainfall_router, "get_rainfall_threshold", lambda state: CONFIG)
    monkeypatch.setattr(rainfall_router, "can_alert", lambda state: True)
    db = MagicMock()
    app.dependency_overrides[get_db] = lambda: db
    try:
        db.execute.side_effect = [
            SimpleNamespace(all=lambda: [readings_row(z1, 10.0), readings_row(z2, 45.0), readings_row(z3, 30.0)]),  # ratios: 0.25, 0.9, 0.6
            SimpleNamespace(all=lambda: [(z1, "road A"), (z2, "road B"), (z3, "road C")]),
        ]
        top = TestClient(app).get("/rainfall/headroom").json()["states"][0]["top_zones"]
        assert [z["zone_name"] for z in top] == ["road B", "road C", "road A"]  # 0.9, 0.6, 0.25 -- closest first
        assert all(z["ratio"] < 1 for z in top)  # none of these are an actual crossing
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_a_state_with_no_stored_rainfall_yet_reports_nulls_not_a_guess(client):
    c, db = client
    db.execute.side_effect = [SimpleNamespace(all=lambda: []), SimpleNamespace(all=lambda: [])]
    body = c.get("/rainfall/headroom").json()
    for s in body["states"]:
        assert s["ratio"] is None and s["zone_name"] is None and s["risk_tier"] is None and s["threshold_source"] is None and s["top_zones"] == []


def test_no_monitored_zones_at_all_returns_an_empty_list_not_an_error(monkeypatch):
    monkeypatch.setattr(rainfall_router, "select_zones", lambda db, n: [])
    db = MagicMock()
    app.dependency_overrides[get_db] = lambda: db
    try:
        assert TestClient(app).get("/rainfall/headroom").json() == {"states": []}
        db.execute.assert_not_called()
    finally:
        app.dependency_overrides.pop(get_db, None)
