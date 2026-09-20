"""Rainfall fetched by the GitHub Actions runner and posted to the backend
(POST /rainfall/ingest). The point of the tests: the caller supplies numbers
only -- it can't choose which zones get written or alerted. No DB, no network."""
import importlib.util
import uuid
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app import security
from app.database import get_db
from app.main import app
from app.routers import rainfall as rainfall_router
from app.services import open_meteo
from app.services import rainfall_refresh as rr

KEY = "some-officer-key-value-1234567"
Z1, Z2, OTHER = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()


def _zone(zid, state="Sikkim"):
    return rr.ZoneTarget(id=zid, state=state, risk_tier="high", lat=27.3, lng=88.6)


def _day(mm):
    return [open_meteo.DailyRainfall(day=date(2026, 9, 20), intensity_mm=mm)]


@pytest.fixture
def stored(monkeypatch):
    calls = []
    monkeypatch.setattr(rr, "select_zones", lambda db, n: [_zone(Z1), _zone(Z2)])
    monkeypatch.setattr(rr, "store_readings", lambda db, by_zone: calls.append(by_zone))
    return calls


def test_only_eligible_zones_are_stored_and_unknown_ids_are_ignored(stored):
    out = rr.ingest_rainfall(MagicMock(), 25, {Z1: _day(5.0), OTHER: _day(999.0)}, run_alerts=False)
    assert set(stored[0]) == {Z1}  # OTHER was never a target, so it is dropped
    assert out["zones_refreshed"] == 1 and out["zones_failed"] == 1  # Z2 sent nothing


def test_a_zone_with_no_supplied_data_counts_as_failed_not_fresh(stored):
    out = rr.ingest_rainfall(MagicMock(), 25, {}, run_alerts=False)
    assert out["zones_refreshed"] == 0 and out["zones_failed"] == 2
    assert stored == []  # nothing written


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(security.settings, "api_key", KEY)
    app.dependency_overrides[get_db] = lambda: MagicMock()
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)


BODY = {"readings": [{"zone_id": str(Z1), "days": [{"day": "2026-09-20", "mm": 3.5}]}]}


def test_targets_and_ingest_need_the_officer_key(client):
    assert client.get("/rainfall/targets").status_code == 401
    assert client.post("/rainfall/ingest", json=BODY).status_code == 401


def test_targets_lists_the_zones_to_fetch(client, monkeypatch):
    monkeypatch.setattr(rainfall_router, "select_zones", lambda db, n: [_zone(Z1)])
    r = client.get("/rainfall/targets", headers={"X-API-Key": KEY})
    assert r.json() == [{"id": str(Z1), "lat": 27.3, "lng": 88.6}]


@pytest.mark.parametrize(
    "body",
    [
        {"readings": [{"zone_id": str(Z1), "days": [{"day": "2026-09-20", "mm": -1}]}]},  # negative rain
        {"readings": [{"zone_id": str(Z1), "days": [{"day": "2026-09-20", "mm": 99999}]}]},  # absurd
        {"readings": [{"zone_id": str(Z1), "days": [{"day": "2026-08-01", "mm": 1}] * 41}]},  # too many days
        {"readings": [{"zone_id": "not-a-uuid", "days": []}]},
    ],
)
def test_ingest_rejects_malformed_or_implausible_data(client, body):
    assert client.post("/rainfall/ingest", json=body, headers={"X-API-Key": KEY}).status_code == 422


def test_a_full_ingest_marks_rainfall_fresh_but_a_data_only_one_does_not(client, monkeypatch):
    recorded = []
    out = {"zones_selected": 1, "zones_refreshed": 1, "zones_failed": 0, "alerts_enabled": True, "alerts_created": 0,
           "alerts_resolved": 0, "alerting_states": ["Sikkim"], "states": {"Sikkim": 1}, "errors": [], "duration_seconds": 1.0}
    monkeypatch.setattr(rainfall_router, "ingest_rainfall", lambda db, n, supplied, run_alerts=True: out)
    monkeypatch.setattr(rainfall_router, "record_refresh", lambda db, s: recorded.append(s))
    h = {"X-API-Key": KEY}
    assert client.post("/rainfall/ingest", json=BODY, headers=h).status_code == 200
    assert len(recorded) == 1
    assert client.post("/rainfall/ingest?alerts=false", json=BODY, headers=h).status_code == 200
    assert len(recorded) == 1  # unchanged


# --- the runner script -----------------------------------------------------


@pytest.fixture
def runner():
    spec = importlib.util.spec_from_file_location("runner", Path(__file__).parent.parent / "scripts" / "refresh_rainfall_from_runner.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_chunk_maps_open_meteo_locations_to_zones_and_skips_null_days(runner, monkeypatch):
    payload = [
        {"daily": {"time": ["2026-09-19", "2026-09-20"], "precipitation_sum": [1.0, None]}},
        {"daily": {"time": ["2026-09-19"], "precipitation_sum": [0.0]}},
    ]
    monkeypatch.setattr(runner, "call", lambda url, **kw: payload)
    out = runner.fetch_chunk([{"id": "a", "lat": 1, "lng": 2}, {"id": "b", "lat": 3, "lng": 4}])
    assert out == [
        {"zone_id": "a", "days": [{"day": "2026-09-19", "mm": 1.0}]},
        {"zone_id": "b", "days": [{"day": "2026-09-19", "mm": 0.0}]},
    ]


def test_a_single_zone_chunk_is_handled(runner, monkeypatch):  # Open-Meteo returns an object, not a list, for one point
    monkeypatch.setattr(runner, "call", lambda url, **kw: {"daily": {"time": ["2026-09-20"], "precipitation_sum": [2.0]}})
    assert runner.fetch_chunk([{"id": "a", "lat": 1, "lng": 2}])[0]["days"] == [{"day": "2026-09-20", "mm": 2.0}]


def test_a_count_mismatch_from_open_meteo_is_an_error(runner, monkeypatch):
    monkeypatch.setattr(runner, "call", lambda url, **kw: [{"daily": {"time": [], "precipitation_sum": []}}])
    with pytest.raises(RuntimeError):
        runner.fetch_chunk([{"id": "a", "lat": 1, "lng": 2}, {"id": "b", "lat": 3, "lng": 4}])


def test_nothing_fetched_means_the_backend_is_not_called_and_the_run_fails(runner, monkeypatch):
    monkeypatch.setenv("BACKEND_URL", "http://backend")
    monkeypatch.setenv("OFFICER_KEY", "k")
    monkeypatch.setattr(runner.sys, "argv", ["x"])
    monkeypatch.setattr(runner.time, "sleep", lambda s: None)
    calls = []

    def fake_call(url, **kw):
        calls.append(url)
        if url.endswith("/rainfall/targets"):
            return [{"id": "a", "lat": 1, "lng": 2}]
        raise RuntimeError("HTTP 429")

    monkeypatch.setattr(runner, "call", fake_call)
    assert runner.main() == 1
    assert not any("/ingest" in c for c in calls)


def test_missing_credentials_fail_fast(runner, monkeypatch):
    monkeypatch.delenv("OFFICER_KEY", raising=False)
    monkeypatch.setattr(runner.sys, "argv", ["x"])
    assert runner.main() == 2
