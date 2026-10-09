"""GET /alerts/summary and the per-alert driving_window_days on GET /alerts: what the
active-alert count actually rests on. Display-only -- nothing here may change which
alerts open or close. Database mocked; the rainfall rows are real-shaped."""
import uuid
from datetime import datetime, time, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.config import RainfallThresholdConfig
from app.database import get_db
from app.main import app
from app.routers import alerts as alerts_router

# threshold(D) = 40/D mm/day (moderate): 1 day -> 40, 3 -> 13.3, 10 -> 4, 20 -> 2.
CONFIG = RainfallThresholdConfig(
    region="test", coefficient=40.0, exponent=-1.0, durations_days=[1, 3, 10, 20], source="synthetic, for unit tests only"
)
TODAY = datetime.now(timezone.utc).date()

STEADY_A, STEADY_B, STORM, NO_DATA, CALM, RESOLVED = (uuid.uuid4() for _ in range(6))


def _alert(zone_id, status="active"):
    return SimpleNamespace(
        id=uuid.uuid4(), zone_id=zone_id, zone_name=f"road ({zone_id.hex[:6]})", risk_tier="moderate",
        triggered_at=datetime(2026, 9, 1, tzinfo=timezone.utc), threshold_crossed="x", status=status,
        delivery_method="log_only", resolved_at=None, resolved_by=None, worsened_at=None, worsened_count=0, peak_ratio=None,
        zone=SimpleNamespace(state="Sikkim", risk_tier="moderate"),
    )


def _rows(zone_id, mm_by_age):
    return [(zone_id, datetime.combine(TODAY - timedelta(days=age), time.min, tzinfo=timezone.utc), mm) for age, mm in mm_by_age.items()]


STEADY = {age: 3.0 for age in range(20)}  # calm today, but the 20-day mean (3.0) is over 2.0
RAIN_ROWS = (
    _rows(STEADY_A, STEADY)
    + _rows(STEADY_B, STEADY)  # identical data: the same weather-model cell as STEADY_A
    + _rows(STORM, {0: 50.0, **{age: 0.0 for age in range(1, 20)}})  # over the 1-day line right now
    + _rows(CALM, {age: 1.0 for age in range(20)})  # nothing over its line
)  # NO_DATA has no stored rainfall at all


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(alerts_router, "get_rainfall_threshold", lambda state: CONFIG)
    db = MagicMock()
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app), db
    app.dependency_overrides.pop(get_db, None)


def test_summary_separates_alerts_from_the_rain_evidence_behind_them(client):
    c, db = client
    alerts = [_alert(z) for z in (STEADY_A, STEADY_B, STORM, NO_DATA, CALM)]
    db.query.return_value.options.return_value.filter.return_value.all.return_value = alerts
    db.execute.return_value.all.return_value = RAIN_ROWS
    body = c.get("/alerts/summary").json()
    assert body == {
        "active_alerts": 5,
        "distinct_rainfall_records": 3,  # steady (x2 identical), storm, calm -- five alerts, three observations
        "long_window_alerts": 2,  # both steady-rain zones: driven only by the 20-day window
        "long_window_days": 10,
        "not_currently_over": 1,  # CALM: still open, no window over its line today
        "no_rainfall_data": 1,  # NO_DATA: nothing stored, never guessed
    }


def test_summary_with_no_active_alerts_is_all_zero_and_asks_no_rain_question(client):
    c, db = client
    db.query.return_value.options.return_value.filter.return_value.all.return_value = []
    body = c.get("/alerts/summary").json()
    assert body["active_alerts"] == 0 and body["distinct_rainfall_records"] == 0 and body["long_window_alerts"] == 0
    db.execute.assert_not_called()


def test_each_active_alert_reports_its_own_driving_window(client):
    c, db = client
    alerts = [_alert(STEADY_A), _alert(STORM), _alert(NO_DATA), _alert(RESOLVED, status="resolved")]
    db.query.return_value.options.return_value.order_by.return_value.all.return_value = alerts
    db.execute.side_effect = [
        SimpleNamespace(all=lambda: []),  # _attach_latest_rainfall
        SimpleNamespace(all=lambda: RAIN_ROWS + _rows(RESOLVED, STEADY)),  # _rainfall_drivers
    ]
    by_zone = {a["zone_id"]: a for a in c.get("/alerts").json()}
    assert by_zone[str(STEADY_A)]["driving_window_days"] == 20 and by_zone[str(STEADY_A)]["long_window_alert"] is True
    assert by_zone[str(STORM)]["driving_window_days"] == 1 and by_zone[str(STORM)]["long_window_alert"] is False
    assert by_zone[str(NO_DATA)]["driving_window_days"] is None and by_zone[str(NO_DATA)]["long_window_alert"] is False
    # A resolved alert is history, not something to explain.
    assert by_zone[str(RESOLVED)]["driving_window_days"] is None and by_zone[str(RESOLVED)]["long_window_alert"] is False
