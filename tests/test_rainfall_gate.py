"""The dashboard-driven refresh gate (app/services/rainfall_refresh.refresh_if_stale).

Anyone opening the dashboard can trigger a rainfall refresh, so the properties that
matter are all about NOT doing work: nothing happens while data is fresh, only one
refresh runs at a time, a crashed run can't wedge the system, and a run that fetched
nothing must never make stale data look fresh. No database, no network."""
import uuid
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app import security
from app.database import get_db
from app.main import app
from app.routers import alerts as alerts_router
from app.routers import rainfall as rainfall_router
from app.services import rainfall_refresh as rr

NOW = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)


# --- is_stale --------------------------------------------------------------


def test_never_refreshed_is_stale():
    assert rr.is_stale(None, 60, NOW) is True


def test_a_recent_refresh_is_fresh():
    assert rr.is_stale(NOW - timedelta(minutes=5), 60, NOW) is False


def test_it_becomes_stale_exactly_at_the_max_age():
    assert rr.is_stale(NOW - timedelta(minutes=59), 60, NOW) is False
    assert rr.is_stale(NOW - timedelta(minutes=60), 60, NOW) is True


def test_an_old_refresh_is_stale():
    assert rr.is_stale(NOW - timedelta(days=6), 60, NOW) is True


# --- refresh_if_stale ------------------------------------------------------


@pytest.fixture
def gate(monkeypatch):
    h = MagicMock()
    h.status = {"stale": True, "age_minutes": 300}
    h.claim = True
    h.summary = {"zones_refreshed": 50, "zones_failed": 0, "alerts_created": 0, "alerts_resolved": 0, "states": {"Sikkim": 25}, "duration_seconds": 4.2}
    h.calls = []
    monkeypatch.setattr(rr, "refresh_status", lambda db, max_age: h.status)
    monkeypatch.setattr(rr, "_claim_lease", lambda db: h.claim)
    monkeypatch.setattr(rr, "_release_lease", lambda db: h.calls.append("release"))
    monkeypatch.setattr(rr, "record_refresh", lambda db, summary: h.calls.append(("record", summary)))

    def fake_refresh(db, per_state, run_alerts=True):
        h.calls.append(("refresh", per_state, run_alerts))
        if isinstance(h.summary, Exception):
            raise h.summary
        return h.summary

    monkeypatch.setattr(rr, "refresh_rainfall", fake_refresh)
    return h


def test_fresh_data_does_nothing_at_all(gate):
    gate.status = {"stale": False, "age_minutes": 12}
    out = rr.refresh_if_stale(MagicMock(), 60, 25)
    assert out == {"status": "fresh", "age_minutes": 12}
    assert gate.calls == []  # not even a lease claim's release, and no fetch


def test_stale_data_is_refreshed_recorded_and_the_lease_released(gate):
    out = rr.refresh_if_stale(MagicMock(), 60, 25)
    assert out["status"] == "refreshed" and out["zones_refreshed"] == 50
    kinds = [c if isinstance(c, str) else c[0] for c in gate.calls]
    assert kinds == ["refresh", "record", "release"]
    assert gate.calls[0] == ("refresh", 25, True)  # alerts are evaluated too


def test_a_second_visitor_while_a_refresh_is_running_gets_in_progress(gate):
    gate.claim = False
    out = rr.refresh_if_stale(MagicMock(), 60, 25)
    assert out == {"status": "in_progress"}
    assert gate.calls == []  # nothing fetched, and it does NOT release someone else's lease


def test_a_crash_releases_the_lease_and_does_not_mark_the_data_fresh(gate):
    gate.summary = RuntimeError("Open-Meteo down")
    with pytest.raises(RuntimeError):
        rr.refresh_if_stale(MagicMock(), 60, 25)
    kinds = [c if isinstance(c, str) else c[0] for c in gate.calls]
    assert kinds == ["refresh", "release"]  # released, never recorded


def test_a_run_that_fetched_nothing_must_not_make_stale_data_look_fresh(gate):
    gate.summary = {**gate.summary, "zones_refreshed": 0, "zones_failed": 50}
    out = rr.refresh_if_stale(MagicMock(), 60, 25)
    assert out["status"] == "refreshed"
    assert not any(isinstance(c, tuple) and c[0] == "record" for c in gate.calls)
    assert "release" not in gate.calls  # cooldown: the lease stays until it expires


# --- the public endpoints --------------------------------------------------


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(security.settings, "api_key", "some-officer-key-value-1234567")  # auth ON
    app.dependency_overrides[get_db] = lambda: MagicMock()
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)


def test_refresh_if_stale_needs_no_key_even_when_auth_is_on(client, monkeypatch):
    monkeypatch.setattr(rainfall_router, "refresh_if_stale", lambda db, max_age, per_state: {"status": "fresh", "age_minutes": 3})
    r = client.post("/rainfall/refresh-if-stale")
    assert r.status_code == 200 and r.json()["status"] == "fresh"


def test_status_needs_no_key_and_reports_freshness(client, monkeypatch):
    monkeypatch.setattr(rainfall_router, "refresh_status", lambda db, max_age: {"last_refresh_at": NOW, "age_minutes": 7, "max_age_minutes": max_age, "stale": False})
    body = client.get("/rainfall/status").json()
    assert body["age_minutes"] == 7 and body["stale"] is False and body["max_age_minutes"] == rainfall_router.settings.rainfall_refresh_max_age_minutes


def test_the_authenticated_refresh_still_needs_the_key(client):
    assert client.post("/rainfall/refresh").status_code == 401


@pytest.mark.parametrize(
    "params,should_record",
    [({}, True), ({"per_state": 3}, False), ({"alerts": "false"}, False)],
)
def test_only_a_full_alerting_run_counts_as_fresh(client, monkeypatch, params, should_record):
    recorded = []
    out = {"zones_selected": 50, "zones_refreshed": 50, "zones_failed": 0, "alerts_enabled": True, "alerts_created": 0,
           "alerts_resolved": 0, "alerting_states": ["Sikkim"], "states": {"Sikkim": 50}, "errors": [], "duration_seconds": 3.0}
    monkeypatch.setattr(rainfall_router, "refresh_rainfall", lambda db, per_state, run_alerts=True: out)
    monkeypatch.setattr(rainfall_router, "record_refresh", lambda db, summary: recorded.append(summary))
    r = client.post("/rainfall/refresh", params=params, headers={"X-API-Key": "some-officer-key-value-1234567"})
    assert r.status_code == 200
    assert bool(recorded) is should_record


# --- alerts show current rainfall next to their frozen text ---------------


def test_each_alert_gets_its_zones_latest_observed_rainfall():
    z1, z2, z3 = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    db = MagicMock()
    db.execute.return_value.all.return_value = [
        (z1, datetime(2026, 9, 20, tzinfo=timezone.utc), 4.4),
        (z2, datetime(2026, 9, 18, tzinfo=timezone.utc), 0.0),
    ]
    alerts = [SimpleNamespace(zone_id=z) for z in (z1, z2, z3)]
    alerts_router._attach_latest_rainfall(db, alerts)
    assert (alerts[0].latest_rainfall_date, alerts[0].latest_rainfall_mm) == (date(2026, 9, 20), 4.4)
    assert (alerts[1].latest_rainfall_date, alerts[1].latest_rainfall_mm) == (date(2026, 9, 18), 0.0)
    assert (alerts[2].latest_rainfall_date, alerts[2].latest_rainfall_mm) == (None, None)  # no data for that zone


def test_no_alerts_means_no_query():
    db = MagicMock()
    alerts_router._attach_latest_rainfall(db, [])
    db.execute.assert_not_called()
