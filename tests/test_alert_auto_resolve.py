"""Auto-resolve: when may an alert close itself?

has_cleared() is deliberately conservative: it must answer False (keep the
alert) unless it can positively show the rainfall stayed below the threshold in
every window on each of the last few days. These tests pin that down, and the
ways it could wrongly say "all clear" (stale data, gaps, forecast rain, a brief
lull)."""
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from app.config import RainfallThresholdConfig
from app.services import rainfall_refresh as rr
from app.services.alert_engine import has_cleared
from app.services.open_meteo import DailyRainfall

# threshold(D) = 40 / D mm/day: 40 mm cumulative over ANY window (1..20 days) is a crossing.
CONFIG = RainfallThresholdConfig(region="test", coefficient=40.0, exponent=-1.0, source="synthetic, for unit tests only")
TODAY = datetime.now(timezone.utc).date()


def series(by_days_ago: dict[int, float] | None = None, history: int = 20, end_offset: int = 0) -> dict:
    """{date: mm}: `history` days ending `end_offset` days before today (0 = up to
    today), all dry except the given {days_ago: mm}."""
    by_days_ago = by_days_ago or {}
    return {
        TODAY - timedelta(days=d): float(by_days_ago.get(d, 0.0))
        for d in range(end_offset, end_offset + history + 1)
    }


def test_a_dry_spell_counts_as_cleared():
    assert has_cleared(series(), CONFIG, clear_days=2) is True


def test_rain_over_the_threshold_today_is_not_cleared():
    assert has_cleared(series({0: 90.0}), CONFIG, clear_days=2) is False


def test_a_heavy_day_still_inside_the_windows_is_not_cleared():
    # 3 days ago: still inside the 3/5/7/... day windows, so the alert stands.
    assert has_cleared(series({3: 90.0}), CONFIG, clear_days=2) is False


def test_it_must_stay_clear_for_the_whole_clear_period_not_just_today():
    # Heavy rain exactly 20 days ago: today's 20-day window (today-19..today)
    # already excludes it, but yesterday's window still includes it.
    data = series({20: 100.0})
    assert has_cleared(data, CONFIG, clear_days=1) is True  # clear as of today
    assert has_cleared(data, CONFIG, clear_days=2) is False  # ...but not yet as of yesterday


def test_forecast_rain_alone_never_blocks_an_all_clear_and_never_causes_one():
    data = series()
    data[TODAY + timedelta(days=2)] = 500.0  # a huge forecast day is ignored
    assert has_cleared(data, CONFIG, clear_days=2) is True


def test_stale_data_can_never_say_all_clear():
    # Newest reading is yesterday: we can't claim anything about today.
    assert has_cleared(series(end_offset=1), CONFIG, clear_days=2) is False


def test_a_gap_in_the_history_is_not_read_as_all_clear():
    # Only 10 days of data: evaluate_daily_rainfall would skip the longer
    # windows as "not enough data" and report no crossing -- that must not
    # count as cleared.
    assert has_cleared(series(history=10), CONFIG, clear_days=2) is False


def test_missing_days_inside_the_window_block_the_all_clear():
    data = series()
    for d in (5, 6, 7, 8):  # Open-Meteo returned no value for these days
        del data[TODAY - timedelta(days=d)]
    assert has_cleared(data, CONFIG, clear_days=2) is False


def test_no_data_at_all_is_not_cleared():
    assert has_cleared({}, CONFIG, clear_days=2) is False


def test_a_zero_clear_period_never_clears_anything():
    assert has_cleared(series(), CONFIG, clear_days=0) is False


def test_the_default_clear_period_comes_from_settings(monkeypatch):
    from app.services import alert_engine

    data = series({20: 100.0})
    monkeypatch.setattr(alert_engine.settings, "rainfall_alert_clear_days", 1)
    assert has_cleared(data, CONFIG) is True
    monkeypatch.setattr(alert_engine.settings, "rainfall_alert_clear_days", 2)
    assert has_cleared(data, CONFIG) is False


# --- the refresh closes alerts (and only the right ones) ------------------


def _zone(state="Sikkim"):
    return rr.ZoneTarget(id=uuid.uuid4(), state=state, risk_tier="moderate", lat=27.3, lng=88.6)


def _as_daily(by_date: dict) -> list[DailyRainfall]:
    return [DailyRainfall(day=d, intensity_mm=mm) for d, mm in sorted(by_date.items())]


@pytest.fixture
def wired(monkeypatch):
    h = MagicMock()
    h.zones, h.fetch, h.active, h.resolved, h.triggered, h.escalated = [], {}, set(), [], [], []
    h.escalate_result = False
    monkeypatch.setattr(rr, "select_zones", lambda db, per_state: h.zones)
    monkeypatch.setattr(rr, "get_rainfall_threshold", lambda state: CONFIG)
    monkeypatch.setattr(rr, "can_alert", lambda state: state != "Assam")
    monkeypatch.setattr(rr, "_fetch_all", lambda zones: [h.fetch[z.id] for z in zones])
    monkeypatch.setattr(rr, "store_readings", lambda db, by_zone: [])
    monkeypatch.setattr(rr, "_active_alerts_by_zone", lambda db, ids: {i: MagicMock(zone_id=i) for i in ids if i in h.active})
    monkeypatch.setattr(rr, "escalate_if_worsened", lambda db, alert, zone, totals, config, tier: h.escalated.append(zone.id) or h.escalate_result)
    monkeypatch.setattr(rr, "resolve_cleared_alerts", lambda db, ids: h.resolved.extend(ids) or len(ids))
    monkeypatch.setattr(rr, "check_and_trigger", lambda db, zid: h.triggered.append(zid) or None)
    monkeypatch.setattr("app.services.alert_engine.settings.rainfall_alert_clear_days", 2)
    return h


def test_an_active_alert_on_a_zone_whose_rain_cleared_is_resolved(wired):
    z = _zone()
    wired.zones, wired.active = [z], {z.id}
    wired.fetch = {z.id: _as_daily(series())}
    out = rr.refresh_rainfall(MagicMock(), per_state=25)
    assert wired.resolved == [z.id] and out["alerts_resolved"] == 1


def test_an_alert_is_kept_while_the_rain_still_crosses_the_threshold(wired):
    z = _zone()
    wired.zones, wired.active = [z], {z.id}
    wired.fetch = {z.id: _as_daily(series({0: 90.0}))}
    out = rr.refresh_rainfall(MagicMock(), per_state=25)
    assert wired.resolved == [] and out["alerts_resolved"] == 0


def test_a_zone_without_an_active_alert_has_nothing_to_resolve(wired):
    z = _zone()
    wired.zones = [z]
    wired.fetch = {z.id: _as_daily(series())}
    out = rr.refresh_rainfall(MagicMock(), per_state=25)
    assert wired.resolved == [] and out["alerts_resolved"] == 0


def test_incomplete_data_keeps_the_alert_open(wired):
    z = _zone()
    wired.zones, wired.active = [z], {z.id}
    wired.fetch = {z.id: _as_daily(series(history=8))}
    out = rr.refresh_rainfall(MagicMock(), per_state=25)
    assert wired.resolved == [] and out["alerts_resolved"] == 0


def test_a_failed_fetch_never_resolves_an_alert(wired):
    z = _zone()
    wired.zones, wired.active = [z], {z.id}
    wired.fetch = {z.id: RuntimeError("Open-Meteo 503")}
    out = rr.refresh_rainfall(MagicMock(), per_state=25)
    assert wired.resolved == [] and out["zones_failed"] == 1


def test_alerts_off_changes_no_alerts_at_all(wired):
    z = _zone()
    wired.zones, wired.active = [z], {z.id}
    wired.fetch = {z.id: _as_daily(series())}
    out = rr.refresh_rainfall(MagicMock(), per_state=25, run_alerts=False)
    assert wired.resolved == [] and out["alerts_resolved"] == 0


def test_a_state_not_on_the_alerting_list_is_left_alone(wired):
    z = _zone("Assam")
    wired.zones, wired.active = [z], {z.id}
    wired.fetch = {z.id: _as_daily(series())}
    out = rr.refresh_rainfall(MagicMock(), per_state=25)
    assert wired.resolved == [] and out["alerts_resolved"] == 0


def test_only_the_cleared_zones_are_resolved_in_a_mixed_run(wired):
    cleared, still_wet, quiet = _zone(), _zone(), _zone()
    wired.zones = [cleared, still_wet, quiet]
    wired.active = {cleared.id, still_wet.id}
    wired.fetch = {
        cleared.id: _as_daily(series()),
        still_wet.id: _as_daily(series({1: 90.0})),
        quiet.id: _as_daily(series()),
    }
    out = rr.refresh_rainfall(MagicMock(), per_state=25)
    assert wired.resolved == [cleared.id] and out["alerts_resolved"] == 1


def test_resolve_cleared_alerts_marks_them_resolved_by_the_system():
    db = MagicMock()
    db.execute.return_value.rowcount = 3
    assert rr.resolve_cleared_alerts(db, [uuid.uuid4(), uuid.uuid4()]) == 3
    stmt = db.execute.call_args[0][0]
    compiled = stmt.compile(compile_kwargs={"literal_binds": False})
    values = list(compiled.params.values())
    assert "resolved" in values and "system" in values  # status and resolved_by
    db.commit.assert_called_once()


def test_resolving_nothing_touches_nothing():
    db = MagicMock()
    assert rr.resolve_cleared_alerts(db, []) == 0
    db.execute.assert_not_called()


# --- manual resolve records who did it -----------------------------------


@pytest.fixture
def resolve_client(monkeypatch):
    from types import SimpleNamespace

    from fastapi.testclient import TestClient

    from app import security
    from app.database import get_db
    from app.main import app

    monkeypatch.setattr(security.settings, "api_key", None)  # auth is tested elsewhere
    alert = SimpleNamespace(
        id=uuid.uuid4(), zone_id=uuid.uuid4(), zone_name="NH10 (1)", risk_tier="high",
        triggered_at=datetime.now(timezone.utc), threshold_crossed="x", status="active",
        delivery_method="log_only", resolved_at=None, resolved_by=None,
    )
    db = MagicMock()
    db.get.return_value = alert
    app.dependency_overrides[get_db] = lambda: db
    try:
        yield TestClient(app), alert
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_an_officer_resolving_an_alert_is_recorded_as_the_officer(resolve_client):
    client, alert = resolve_client
    body = client.post(f"/alerts/{alert.id}/resolve").json()
    assert body["status"] == "resolved" and body["resolved_by"] == "officer" and body["resolved_at"] is not None


def test_resolving_twice_keeps_the_original_resolver_and_time(resolve_client):
    client, alert = resolve_client
    first_time = datetime(2026, 9, 1, tzinfo=timezone.utc)
    alert.status, alert.resolved_by, alert.resolved_at = "resolved", "system", first_time
    body = client.post(f"/alerts/{alert.id}/resolve").json()
    assert body["resolved_by"] == "system"  # not overwritten by the later call
    assert body["resolved_at"].startswith("2026-09-01")


# --- the refresh also updates alerts whose rain got clearly worse ------------


def test_an_active_alert_still_crossing_is_checked_for_worsening_and_counted(wired):
    z = _zone()
    wired.zones, wired.active, wired.escalate_result = [z], {z.id}, True
    wired.fetch = {z.id: _as_daily(series({0: 90.0}))}
    out = rr.refresh_rainfall(MagicMock(), per_state=25)
    assert wired.escalated == [z.id] and out["alerts_worsened"] == 1
    assert out["alerts_created"] == 0 and out["alerts_resolved"] == 0


def test_no_worsening_check_without_an_active_alert(wired):
    z = _zone()
    wired.zones = [z]  # crossing, but no alert yet: check_and_trigger raises one instead
    wired.fetch = {z.id: _as_daily(series({0: 90.0}))}
    out = rr.refresh_rainfall(MagicMock(), per_state=25)
    assert wired.escalated == [] and out["alerts_worsened"] == 0 and wired.triggered == [z.id]


def test_no_worsening_check_when_the_rain_has_cleared(wired):
    z = _zone()
    wired.zones, wired.active = [z], {z.id}
    wired.fetch = {z.id: _as_daily(series())}
    rr.refresh_rainfall(MagicMock(), per_state=25)
    assert wired.escalated == [] and wired.resolved == [z.id]  # it closes, it does not "escalate"
