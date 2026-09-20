"""GET /zones/{id}/surroundings -- villages and nearest services around a road
stretch, from the OpenStreetMap snapshot. The SQL distance filter is exercised
against the real database when the app runs; these pin the behaviour around it:
named places only, the nearest few, per-kind service picks, honest emptiness,
input validation. No database."""
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app

ZONE_ID = uuid.uuid4()
SNAPSHOT = datetime(2026, 9, 20, 16, 0, tzinfo=timezone.utc)


def place(kind, name, phone=None):
    return SimpleNamespace(kind=kind, name=name, phone=phone)


@pytest.fixture
def client():
    db = MagicMock()
    db.get.return_value = SimpleNamespace(id=ZONE_ID, centroid_lat=27.3, centroid_lng=88.24)
    db.scalar.return_value = SNAPSHOT
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app), db
    app.dependency_overrides.pop(get_db, None)


def results(db, villages, hospital=(), clinic=(), police=(), fire=(), covered=True):
    # one db.execute(...).all() per call: the coverage check, then villages, hospital, clinic, police, fire_station
    calls = [[(place("village", "anything"), 1.0)] if covered else [], villages, list(hospital), list(clinic), list(police), list(fire)]
    db.execute.side_effect = [MagicMock(all=MagicMock(return_value=rows)) for rows in calls]


def test_lists_the_nearest_villages_with_the_total_and_the_nearest_services(client):
    c, db = client
    results(
        db,
        villages=[(place("village", "Pelling"), 0.34), (place("town", "Gyalshing"), 2.2)],
        hospital=[(place("hospital", "Geyzing District Hospital", "+91 3595 250000"), 2.14)],
        police=[(place("police", "Police picket post"), 7.0)],
    )
    body = c.get(f"/zones/{ZONE_ID}/surroundings").json()
    assert body["villages_total"] == 2
    assert [v["name"] for v in body["villages"]] == ["Pelling", "Gyalshing"]
    assert [(s["kind"], s["name"]) for s in body["services"]] == [("hospital", "Geyzing District Hospital"), ("police", "Police picket post")]
    assert body["services"][0]["phone"] == "+91 3595 250000" and body["services"][1]["phone"] is None
    assert body["services"][0]["distance_km"] == 2.1  # rounded, straight-line
    assert body["snapshot_at"].startswith("2026-09-20")


def test_unnamed_places_are_left_out_and_not_counted(client):
    c, db = client
    results(db, villages=[(place("village", None), 0.5), (place("village", "Yuksom"), 1.0)], hospital=[(place("hospital", ""), 3.0)])
    body = c.get(f"/zones/{ZONE_ID}/surroundings").json()
    assert body["villages_total"] == 1 and [v["name"] for v in body["villages"]] == ["Yuksom"]
    assert body["services"] == []  # an unnamed hospital is not something to send anyone to


def test_only_the_nearest_few_villages_are_listed_but_all_are_counted(client):
    c, db = client
    results(db, villages=[(place("village", f"V{i}"), i / 10) for i in range(1, 21)])
    body = c.get(f"/zones/{ZONE_ID}/surroundings").json()
    assert body["villages_total"] == 20 and len(body["villages"]) == 12


def test_at_most_two_of_each_kind_and_sorted_nearest_first(client):
    c, db = client
    results(db, villages=[], hospital=[(place("hospital", f"H{i}"), 10 + i) for i in range(5)], clinic=[(place("clinic", "C1"), 4.0)])
    body = c.get(f"/zones/{ZONE_ID}/surroundings").json()
    assert [s["name"] for s in body["services"]] == ["C1", "H0", "H1"]  # 2 hospitals max, clinic nearest so first


def test_nothing_mapped_is_reported_as_nothing_not_guessed(client):
    c, db = client
    results(db, villages=[])
    body = c.get(f"/zones/{ZONE_ID}/surroundings").json()
    assert body["villages_total"] == 0 and body["villages"] == [] and body["services"] == []


def test_an_area_with_nothing_loaded_is_flagged_not_reported_as_empty(client):
    c, db = client
    results(db, villages=[], covered=False)
    body = c.get(f"/zones/{ZONE_ID}/surroundings").json()
    assert body["area_covered"] is False and body["villages_total"] == 0  # "unknown", and the UI says so


def test_a_covered_area_is_flagged_covered(client):
    c, db = client
    results(db, villages=[])
    assert c.get(f"/zones/{ZONE_ID}/surroundings").json()["area_covered"] is True


def test_unknown_zone_is_404(client):
    c, db = client
    db.get.return_value = None
    assert c.get(f"/zones/{uuid.uuid4()}/surroundings").status_code == 404


@pytest.mark.parametrize("params", [{"village_km": 50}, {"village_km": 0}, {"service_km": 500}])
def test_rejects_oversized_or_empty_radii(client, params):
    c, _ = client
    assert c.get(f"/zones/{ZONE_ID}/surroundings", params=params).status_code == 422
