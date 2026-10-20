"""POST/GET /imd/warnings: a replaceable IMD snapshot, rain warnings only on the way out."""
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.database import get_db
from app.main import app
from app.models import ImdWarning
from app.routers import imd as imd_router

ISSUED = datetime(2026, 9, 21, 9, 22, tzinfo=timezone.utc)
FETCHED = datetime(2026, 9, 21, 17, 0, tzinfo=timezone.utc)


@pytest.fixture
def client(monkeypatch):
    # These tests are about the endpoint's own logic, not auth (that's test_security.py's job) --
    # pin api_key to disabled so a real key sitting in the local .env (for push_imd_warnings.py)
    # can never make POST /imd/warnings 401 here instead of validating/writing as expected.
    monkeypatch.setattr(settings, "api_key", None)
    # "Today" is pinned: the sample warnings are for 22 Sep 2026, and whether they are still a
    # forecast depends on the real date -- these tests must not start failing as time passes.
    monkeypatch.setattr(imd_router, "_today_ist", lambda: date(2026, 9, 21))
    db = MagicMock()
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app), db
    app.dependency_overrides.pop(get_db, None)


def row(**over):
    base = dict(state="Assam", district="CACHAR", obj_id="10", day=2, valid_date="2026-09-22", codes=[2, 4], color=3)
    base.update(over)
    return base


def stored(**over):
    base = dict(state="Assam", district="CACHAR", obj_id="10", day=2, valid_date=date(2026, 9, 22), codes="2,4", color=3, issued_at=ISSUED, fetched_at=FETCHED)
    base.update(over)
    return SimpleNamespace(**base)


def test_a_push_replaces_the_whole_snapshot_in_one_commit(client):
    c, db = client
    res = c.post("/imd/warnings", json={"issued_at": ISSUED.isoformat(), "rows": [row(), row(day=3, codes=[1], color=4)]})
    assert res.json() == {"stored": 2}
    added = db.add_all.call_args.args[0]
    assert [(r.day, r.codes) for r in added] == [(2, "2,4"), (3, "1")]
    assert "DELETE FROM imd_warnings" in str(db.execute.call_args.args[0])
    db.commit.assert_called_once()


@pytest.mark.parametrize("bad", [row(state="Bihar"), row(day=6), row(codes=[18]), row(codes=[]), row(color=5), row(district="")])
def test_a_bad_row_is_refused_and_nothing_is_written(client, bad):
    c, db = client
    assert c.post("/imd/warnings", json={"issued_at": ISSUED.isoformat(), "rows": [bad]}).status_code == 422
    db.commit.assert_not_called()


def test_only_rain_warnings_come_back_and_they_are_ranked_by_severity(client):
    c, db = client
    db.execute.return_value.scalars.return_value.all.return_value = [
        stored(day=1, codes="1", color=4),                          # no warning: kept only for the count
        stored(day=2, codes="4,2", color=3),                        # thunderstorm + heavy rain -> heavy
        stored(day=3, codes="17,2", color=1),                       # both rain kinds listed, mildest first
        stored(district="KAMRUP", obj_id="11", day=2, codes="4", color=3),  # thunderstorm only: not a rain warning
    ]
    body = c.get("/imd/warnings", params={"state": "Assam"}).json()
    assert body["districts_covered"] == 2 and [d["district"] for d in body["districts"]] == ["CACHAR"]
    days = {d["day"]: d for d in body["districts"][0]["days"]}
    assert set(days) == {2, 3}
    assert days[2]["kinds"] == ["heavy"] and days[3]["kinds"] == ["heavy", "extremely_heavy"] and days[3]["color"] == 1
    assert body["issued_at"].startswith("2026-09-21T09:22")


def test_a_state_imd_does_not_list_reports_zero_districts_covered_not_an_empty_success(client):
    c, db = client
    db.execute.return_value.scalars.return_value.all.return_value = []
    db.scalar.return_value = 560  # a snapshot exists, but not for this state
    db.execute.return_value.one.return_value = (ISSUED, FETCHED)
    body = c.get("/imd/warnings", params={"state": "Mizoram"}).json()
    assert body["districts_covered"] == 0 and body["districts"] == [] and body["issued_at"] is not None


def test_before_any_snapshot_the_dates_are_null(client):
    c, db = client
    db.execute.return_value.scalars.return_value.all.return_value = []
    db.scalar.return_value = 0
    body = c.get("/imd/warnings").json()
    assert body == {"issued_at": None, "fetched_at": None, "districts_covered": 0, "districts": [], "valid_until": None, "expired": False}


def test_the_model_matches_the_migration_columns():
    assert {c.name for c in ImdWarning.__table__.columns} == {"id", "state", "district", "obj_id", "day", "valid_date", "codes", "color", "issued_at", "fetched_at"}


def test_a_snapshot_whose_every_warning_is_past_is_expired_not_a_calm_forecast(client, monkeypatch):
    """The real case that showed on the live dashboard: a hand-pushed snapshot kept listing "day 4
    (29/09)" three weeks later. Its districts must not come back as if they were a forecast."""
    c, db = client
    monkeypatch.setattr(imd_router, "_today_ist", lambda: date(2026, 10, 20))
    db.execute.return_value.scalars.return_value.all.return_value = [
        stored(day=2, valid_date=date(2026, 9, 22)),
        stored(day=5, valid_date=date(2026, 9, 25), district="KAMRUP", obj_id="11"),
    ]
    body = c.get("/imd/warnings").json()
    assert body["expired"] is True and body["valid_until"] == "2026-09-25"
    assert body["districts"] == []  # past warnings are history, not shown as a forecast
    assert body["districts_covered"] == 2  # IMD did list these districts: expired is not "not listed"


def test_past_days_are_dropped_but_today_and_later_are_kept(client, monkeypatch):
    c, db = client
    monkeypatch.setattr(imd_router, "_today_ist", lambda: date(2026, 9, 22))
    db.execute.return_value.scalars.return_value.all.return_value = [
        stored(day=1, valid_date=date(2026, 9, 21)),  # yesterday
        stored(day=2, valid_date=date(2026, 9, 22)),  # today: still in force
        stored(day=3, valid_date=date(2026, 9, 23)),
    ]
    body = c.get("/imd/warnings").json()
    assert body["expired"] is False and body["valid_until"] == "2026-09-23"
    assert [d["day"] for d in body["districts"][0]["days"]] == [2, 3]


def test_expiry_uses_the_india_date_not_the_servers_utc_date():
    from datetime import datetime, timezone

    # 20:00 UTC on 21 Sep is already 01:30 IST on 22 Sep: a warning for 21 Sep is past in India.
    class FakeNow(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 9, 21, 20, 0, tzinfo=timezone.utc).astimezone(tz)

    original = imd_router.datetime
    imd_router.datetime = FakeNow
    try:
        assert imd_router._today_ist() == date(2026, 9, 22)
    finally:
        imd_router.datetime = original
