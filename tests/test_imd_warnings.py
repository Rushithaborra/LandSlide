"""POST/GET /imd/warnings: a replaceable IMD snapshot, rain warnings only on the way out."""
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.models import ImdWarning

ISSUED = datetime(2026, 9, 21, 9, 22, tzinfo=timezone.utc)
FETCHED = datetime(2026, 9, 21, 17, 0, tzinfo=timezone.utc)


@pytest.fixture
def client():
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
    assert body == {"issued_at": None, "fetched_at": None, "districts_covered": 0, "districts": []}


def test_the_model_matches_the_migration_columns():
    assert {c.name for c in ImdWarning.__table__.columns} == {"id", "state", "district", "obj_id", "day", "valid_date", "codes", "color", "issued_at", "fetched_at"}
