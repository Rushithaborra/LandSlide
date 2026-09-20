"""Tests for the scheduled rainfall refresh (app/services/rainfall_refresh.py).
No database and no network: the database session is a mock, and Open-Meteo,
zone selection and the alert engine are replaced with fakes, so these check
the orchestration -- who gets refreshed, that one bad zone can't sink a run,
and that alerts fire only when they should."""
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from app.config import RainfallThresholdConfig
from app.services import open_meteo, rainfall_refresh as rr
from app.services.open_meteo import DailyRainfall

# threshold(D) = 40 / D mm/day (moderate tier): 1 day -> 40 mm.
CONFIG = RainfallThresholdConfig(region="test", coefficient=40.0, exponent=-1.0, source="synthetic, for unit tests only")
TODAY = datetime.now(timezone.utc).date()


def _series(mm_today: float, mm_before: float = 0.0, days: int = 20) -> list[DailyRainfall]:
    """`days` of history ending today, plus two forecast days (as Open-Meteo returns)."""
    past = [DailyRainfall(day=TODAY - timedelta(days=i), intensity_mm=mm_before) for i in range(days, 0, -1)]
    today = [DailyRainfall(day=TODAY, intensity_mm=mm_today)]
    forecast = [DailyRainfall(day=TODAY + timedelta(days=i), intensity_mm=0.0) for i in (1, 2)]
    return past + today + forecast


def _zone(state="Sikkim", tier="moderate") -> rr.ZoneTarget:
    return rr.ZoneTarget(id=uuid.uuid4(), state=state, risk_tier=tier, lat=27.3, lng=88.6)


@pytest.fixture
def wired(monkeypatch):
    """Fakes for every outside dependency; returns a handle to inspect what happened."""
    h = MagicMock()
    h.zones = []
    h.fetch = {}  # zone id -> list[DailyRainfall] | Exception
    h.triggered = []  # zone ids passed to check_and_trigger
    h.alert_result = object()  # what check_and_trigger returns (None = already alerted)
    h.stored = {}

    monkeypatch.setattr(rr, "select_zones", lambda db, per_state: h.zones)
    monkeypatch.setattr(rr, "get_rainfall_threshold", lambda state: CONFIG)
    monkeypatch.setattr(rr, "can_alert", lambda state: state != "Assam")  # Assam: refreshed, not trusted to alert
    monkeypatch.setattr(rr, "_fetch_all", lambda zones: [h.fetch[z.id] for z in zones])
    monkeypatch.setattr(rr, "store_readings", lambda db, by_zone: h.stored.update(by_zone) or [])

    def fake_check(db, zone_id):
        h.triggered.append(zone_id)
        return h.alert_result

    monkeypatch.setattr(rr, "check_and_trigger", fake_check)
    return h


def test_a_zone_whose_rain_crosses_the_threshold_triggers_the_alert_engine(wired):
    z = _zone()
    wired.zones = [z]
    wired.fetch = {z.id: _series(mm_today=90.0)}  # far above the 40 mm/day 1-day threshold
    out = rr.refresh_rainfall(MagicMock(), per_state=25)
    assert wired.triggered == [z.id]
    assert out["alerts_created"] == 1 and out["zones_refreshed"] == 1 and out["zones_failed"] == 0


def test_a_dry_zone_is_stored_but_never_reaches_the_alert_engine(wired):
    z = _zone()
    wired.zones = [z]
    wired.fetch = {z.id: _series(mm_today=2.0)}
    out = rr.refresh_rainfall(MagicMock(), per_state=25)
    assert z.id in wired.stored  # readings are still refreshed
    assert wired.triggered == []
    assert out["alerts_created"] == 0


def test_forecast_rain_alone_never_triggers_an_alert(wired):
    z = _zone()
    wired.zones = [z]
    series = _series(mm_today=0.0)
    series[-1] = DailyRainfall(day=TODAY + timedelta(days=2), intensity_mm=500.0)  # a huge forecast day
    wired.fetch = {z.id: series}
    rr.refresh_rainfall(MagicMock(), per_state=25)
    assert wired.triggered == []


def test_alerts_off_stores_the_data_but_triggers_nothing(wired):
    z = _zone()
    wired.zones = [z]
    wired.fetch = {z.id: _series(mm_today=90.0)}
    out = rr.refresh_rainfall(MagicMock(), per_state=25, run_alerts=False)
    assert z.id in wired.stored
    assert wired.triggered == [] and out["alerts_enabled"] is False and out["alerts_created"] == 0


def test_a_zone_that_already_has_an_active_alert_is_not_counted_as_new(wired):
    z = _zone()
    wired.zones = [z]
    wired.fetch = {z.id: _series(mm_today=90.0)}
    wired.alert_result = None  # the engine skips it: an active alert already exists
    out = rr.refresh_rainfall(MagicMock(), per_state=25)
    assert wired.triggered == [z.id] and out["alerts_created"] == 0


def test_one_failing_fetch_does_not_sink_the_run(wired):
    ok, bad, empty = _zone(), _zone(), _zone()
    wired.zones = [ok, bad, empty]
    wired.fetch = {ok.id: _series(mm_today=90.0), bad.id: RuntimeError("Open-Meteo 503"), empty.id: []}
    out = rr.refresh_rainfall(MagicMock(), per_state=25)
    assert out["zones_selected"] == 3 and out["zones_refreshed"] == 1 and out["zones_failed"] == 2
    assert set(wired.stored) == {ok.id}
    assert wired.triggered == [ok.id] and out["alerts_created"] == 1
    assert any("503" in e for e in out["errors"])


def test_an_alert_engine_error_for_one_zone_is_reported_not_raised(wired, monkeypatch):
    a, b = _zone(), _zone()
    wired.zones = [a, b]
    wired.fetch = {a.id: _series(mm_today=90.0), b.id: _series(mm_today=90.0)}

    def flaky(db, zone_id):
        if zone_id == a.id:
            raise RuntimeError("Twilio down")
        return object()

    monkeypatch.setattr(rr, "check_and_trigger", flaky)
    out = rr.refresh_rainfall(MagicMock(), per_state=25)
    assert out["alerts_created"] == 1
    assert any("Twilio down" in e for e in out["errors"])


def test_the_summary_counts_refreshed_zones_per_state(wired):
    s1, s2, a1 = _zone("Sikkim"), _zone("Sikkim"), _zone("Assam")
    wired.zones = [s1, s2, a1]
    wired.fetch = {z.id: _series(mm_today=1.0) for z in (s1, s2, a1)}
    out = rr.refresh_rainfall(MagicMock(), per_state=25)
    assert out["states"] == {"Sikkim": 2, "Assam": 1}


def test_an_empty_selection_is_a_clean_no_op(wired):
    out = rr.refresh_rainfall(MagicMock(), per_state=25)
    assert out["zones_selected"] == 0 and out["zones_refreshed"] == 0 and wired.stored == {}


# --- store_readings ------------------------------------------------------


def test_store_readings_replaces_the_window_and_commits_once():
    db = MagicMock()
    z1, z2 = uuid.uuid4(), uuid.uuid4()
    rows = rr.store_readings(db, {z1: _series(5.0), z2: _series(7.0)})
    assert len(rows) == 2 * 23  # 20 past days + today + 2 forecast, for two zones
    db.query.return_value.filter.return_value.delete.assert_called_once()
    db.add_all.assert_called_once()
    db.commit.assert_called_once()
    assert {r.zone_id for r in rows} == {z1, z2}
    assert all(r.source == "open-meteo" and r.timestamp.tzinfo is not None for r in rows)


def test_store_readings_with_nothing_fetched_writes_nothing():
    db = MagicMock()
    assert rr.store_readings(db, {}) == []
    db.commit.assert_not_called()


# --- batch fetching ------------------------------------------------------


def _loc(days_mm: dict[str, float | None]) -> dict:
    return {"daily": {"time": list(days_mm), "precipitation_sum": list(days_mm.values())}}


def _mock_http(monkeypatch, payload):
    calls = []

    def fake_get(url, params=None, timeout=None):
        calls.append(params)
        resp = MagicMock()
        resp.json.return_value = payload
        return resp

    monkeypatch.setattr(open_meteo.httpx, "get", fake_get)
    return calls


def test_batch_fetch_sends_one_request_and_returns_series_in_point_order(monkeypatch):
    calls = _mock_http(monkeypatch, [_loc({"2026-09-01": 1.0}), _loc({"2026-09-01": 9.0})])
    out = open_meteo.fetch_daily_rainfall_batch([(27.1, 88.1), (26.2, 91.7)])
    assert len(calls) == 1
    assert calls[0]["latitude"] == "27.1,26.2" and calls[0]["longitude"] == "88.1,91.7"
    assert [s[0].intensity_mm for s in out] == [1.0, 9.0]


def test_a_single_point_comes_back_as_one_object_not_a_list(monkeypatch):
    _mock_http(monkeypatch, _loc({"2026-09-01": 4.0, "2026-09-02": 6.0}))
    out = open_meteo.fetch_daily_rainfall_batch([(27.1, 88.1)])
    assert [d.intensity_mm for d in out[0]] == [4.0, 6.0]


def test_a_day_with_no_value_is_skipped_not_fatal(monkeypatch):
    _mock_http(monkeypatch, _loc({"2026-09-01": 3.0, "2026-09-02": None, "2026-09-03": 5.0}))
    out = open_meteo.fetch_daily_rainfall_batch([(27.1, 88.1)])
    assert [d.intensity_mm for d in out[0]] == [3.0, 5.0]


def test_a_mismatched_number_of_locations_is_an_error(monkeypatch):
    _mock_http(monkeypatch, [_loc({"2026-09-01": 1.0})])
    with pytest.raises(ValueError):
        open_meteo.fetch_daily_rainfall_batch([(27.1, 88.1), (26.2, 91.7)])


def test_no_points_makes_no_request(monkeypatch):
    calls = _mock_http(monkeypatch, [])
    assert open_meteo.fetch_daily_rainfall_batch([]) == []
    assert calls == []


def test_the_single_zone_fetch_matches_the_batch_path(monkeypatch):
    _mock_http(monkeypatch, _loc({"2026-09-01": 2.5}))
    assert [d.intensity_mm for d in open_meteo.fetch_daily_rainfall(27.1, 88.1)] == [2.5]


def test_zones_are_fetched_in_chunks_and_results_stay_in_order(monkeypatch):
    zones = [_zone() for _ in range(rr.FETCH_CHUNK_SIZE + 5)]  # forces two requests

    def fake_batch(points):
        return [[DailyRainfall(day=TODAY, intensity_mm=float(lat))] for lat, _ in points]

    for i, z in enumerate(zones):
        z.lat = float(i)  # each zone's series is tagged with its own position
    monkeypatch.setattr(rr.open_meteo, "fetch_daily_rainfall_batch", fake_batch)
    out = rr._fetch_all(zones)
    assert [r[0].intensity_mm for r in out] == [float(i) for i in range(len(zones))]


def test_a_failed_chunk_only_fails_its_own_zones(monkeypatch):
    zones = [_zone() for _ in range(rr.FETCH_CHUNK_SIZE + 5)]
    calls = {"n": 0}

    def flaky_batch(points):
        calls["n"] += 1
        if len(points) == rr.FETCH_CHUNK_SIZE:
            raise RuntimeError("Open-Meteo 503")
        return [[DailyRainfall(day=TODAY, intensity_mm=1.0)] for _ in points]

    monkeypatch.setattr(rr.open_meteo, "fetch_daily_rainfall_batch", flaky_batch)
    out = rr._fetch_all(zones)
    assert calls["n"] == 2
    assert all(isinstance(r, Exception) for r in out[: rr.FETCH_CHUNK_SIZE])
    assert all(not isinstance(r, Exception) for r in out[rr.FETCH_CHUNK_SIZE :])


# --- which states may alert ----------------------------------------------


def test_a_state_not_on_the_alerting_list_is_refreshed_but_never_alerted(wired):
    assam = _zone("Assam")
    wired.zones = [assam]
    wired.fetch = {assam.id: _series(mm_today=90.0)}  # would cross any sane threshold
    out = rr.refresh_rainfall(MagicMock(), per_state=25)
    assert assam.id in wired.stored  # its rainfall is still refreshed for the dashboard
    assert wired.triggered == [] and out["alerts_created"] == 0
    assert out["alerting_states"] == []


def test_only_alerting_states_are_reported_as_alerting(wired):
    sikkim, assam = _zone("Sikkim"), _zone("Assam")
    wired.zones = [sikkim, assam]
    wired.fetch = {z.id: _series(mm_today=90.0) for z in (sikkim, assam)}
    out = rr.refresh_rainfall(MagicMock(), per_state=25)
    assert wired.triggered == [sikkim.id]
    assert out["alerting_states"] == ["Sikkim"] and out["alerts_created"] == 1


def test_can_alert_follows_the_configured_list_and_ignores_case(monkeypatch):
    from app.services import alert_engine

    monkeypatch.setattr(alert_engine.settings, "rainfall_alert_states", ["sikkim", "Meghalaya"])
    assert alert_engine.can_alert("Sikkim") and alert_engine.can_alert("SIKKIM") and alert_engine.can_alert("meghalaya")
    assert not alert_engine.can_alert("Assam")


def test_sikkim_alerts_by_default_and_assam_does_not():
    from app.config import Settings
    from app.services import alert_engine

    assert Settings(_env_file=None).rainfall_alert_states == ["sikkim"]  # unchanged production behaviour
    assert alert_engine.can_alert("Sikkim") is True
    assert alert_engine.can_alert("Assam") is False


def test_the_alert_engine_itself_refuses_a_state_not_on_the_list(monkeypatch):
    """check_and_trigger is also reached by the manual per-zone fetch, so the
    guard must live there, not only in the scheduler."""
    from types import SimpleNamespace

    from app.services import alert_engine

    db = MagicMock()
    db.get.return_value = SimpleNamespace(state="Assam", risk_tier="high", name="NH27 (1)")
    assert alert_engine.check_and_trigger(db, uuid.uuid4()) is None
    db.query.assert_not_called()  # never even read rainfall for it


# --- the threshold line on the chart -------------------------------------


def test_the_chart_threshold_is_hidden_for_a_state_that_does_not_alert(monkeypatch):
    from types import SimpleNamespace

    from fastapi.testclient import TestClient

    from app.database import get_db
    from app.main import app
    from app.routers import rainfall as rainfall_router

    zone = SimpleNamespace(state="Assam", risk_tier="high")
    fake_db = MagicMock()
    fake_db.get.return_value = zone
    app.dependency_overrides[get_db] = lambda: fake_db
    monkeypatch.setattr(rainfall_router, "get_rainfall_threshold", lambda state: CONFIG)
    try:
        c = TestClient(app)
        assert c.get(f"/rainfall/{uuid.uuid4()}/threshold").json() is None  # configured, but not trusted
        zone.state = "Sikkim"
        body = c.get(f"/rainfall/{uuid.uuid4()}/threshold").json()
        assert body["threshold_mm_per_day"] == pytest.approx(40.0 * 0.8)  # high tier scales the 1-day 40 mm
    finally:
        app.dependency_overrides.pop(get_db, None)
