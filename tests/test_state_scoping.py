"""State scoping: authority contacts and citizen reports belong to a state, and a
critical broadcast rings only the alert's own state's officials (plus all-states
ones). No database; queries are inspected as SQL."""
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app import security
from app.database import get_db
from app.main import app
from app.routers import reports as reports_router
from app.services import sms_alerts

KEY = "some-officer-key-value-1234567"
H = {"X-API-Key": KEY}


def sql(statement) -> str:
    return str(statement.compile(compile_kwargs={"literal_binds": True}))


# --- which officials get called ---------------------------------------------


def test_a_states_alert_calls_that_states_contacts_and_the_all_states_ones():
    db = MagicMock()
    sms_alerts.get_authority_contacts(db, "Sikkim")
    query = sql(db.execute.call_args.args[0])
    assert "authority_contacts.state = 'Sikkim' OR authority_contacts.state IS NULL" in query


def test_a_zone_of_unknown_state_calls_only_the_all_states_contacts():
    db = MagicMock()
    sms_alerts.get_authority_contacts(db, None)
    query = sql(db.execute.call_args.args[0])
    assert "authority_contacts.state IS NULL" in query and "OR" not in query.split("WHERE")[1]


@pytest.fixture
def escalation(monkeypatch):
    rec = SimpleNamespace(states=[], calls=[])
    monkeypatch.setattr(sms_alerts, "trigger_zone_alert", lambda *a, **k: {"skipped": True})
    monkeypatch.setattr(sms_alerts, "get_last_alert_time_by_channel", lambda *a, **k: None)
    monkeypatch.setattr(sms_alerts, "log_alert_sent", lambda *a, **k: None)
    monkeypatch.setattr(sms_alerts, "make_alert_call", lambda phone, text: rec.calls.append(phone) or {"success": True})

    def contacts(db, state=None):
        rec.states.append(state)
        return [{"name": "Officer", "phone": "+911111111111"}]

    monkeypatch.setattr(sms_alerts, "get_authority_contacts", contacts)
    return rec


def test_a_critical_broadcast_for_an_assam_zone_asks_for_assams_officials(escalation):
    db = MagicMock()
    db.get.return_value = SimpleNamespace(state="Assam")
    out = sms_alerts.escalate_critical_alert(db, uuid.uuid4(), "NH27 (1_00_001)", "critical", message="x")
    assert escalation.states == ["Assam"] and out["calls"]["called"] == 1


def test_a_non_critical_broadcast_calls_nobody(escalation):
    db = MagicMock()
    out = sms_alerts.escalate_critical_alert(db, uuid.uuid4(), "z", "high", message="x")
    assert escalation.states == [] and escalation.calls == [] and out["calls"]["skipped"] is True


# --- the authority contacts API ---------------------------------------------


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(security.settings, "api_key", KEY)
    db = MagicMock()
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app), db
    app.dependency_overrides.pop(get_db, None)


def test_listing_for_a_state_filters_and_listing_all_does_not(client):
    c, db = client
    c.get("/authority-contacts", params={"state": "Assam"}, headers=H)
    filtered = sql(db.query.return_value.filter.call_args.args[0])
    assert "state = 'Assam'" in filtered and "IS NULL" in filtered
    db.query.return_value.filter.reset_mock()
    c.get("/authority-contacts", headers=H)
    db.query.return_value.filter.assert_not_called()


def test_a_contact_can_be_added_for_a_state_or_for_all_states(client):
    c, db = client
    added = []
    db.add.side_effect = added.append

    def fill_in(obj):  # what the database would set on insert
        obj.id, obj.added_at = uuid.uuid4(), datetime(2026, 9, 21, tzinfo=timezone.utc)

    db.refresh.side_effect = fill_in
    body = {"name": "A. Officer", "phone_number": "+911234567890"}
    c.post("/authority-contacts", json={**body, "state": "Manipur"}, headers=H)
    c.post("/authority-contacts", json=body, headers=H)
    assert [a.state for a in added] == ["Manipur", None]  # None = an all-states (national) contact


def test_an_unknown_state_is_rejected(client):
    c, _ = client
    assert c.post("/authority-contacts", json={"name": "x", "phone_number": "1", "state": "Atlantis"}, headers=H).status_code == 422


# --- a citizen report's state -------------------------------------------------


def payload(zone_id=None, coords=None, place_name=None):
    return SimpleNamespace(zone_id=zone_id, coords=coords, place_name=place_name)


def test_a_report_takes_its_zones_state(monkeypatch):
    db = MagicMock()
    db.get.return_value = SimpleNamespace(state="Mizoram")
    assert reports_router._report_state(db, payload(zone_id=uuid.uuid4())) == "Mizoram"


def test_a_report_without_a_zone_uses_the_nearest_assessed_zone_to_its_coordinates(monkeypatch):
    monkeypatch.setattr(reports_router, "state_at", lambda db, lat, lng: "Assam" if (lat, lng) == (26.14, 91.74) else None)
    db = MagicMock()
    assert reports_router._report_state(db, payload(coords=SimpleNamespace(lat=26.14, lng=91.74))) == "Assam"
    assert reports_router._report_state(db, payload(coords=SimpleNamespace(lat=17.7, lng=83.3))) is None  # nowhere we cover


def test_a_report_with_neither_coordinates_nor_a_place_name_has_no_state():
    assert reports_router._report_state(MagicMock(), payload()) is None


def test_a_report_with_only_a_place_name_uses_its_geocoded_state(monkeypatch):
    monkeypatch.setattr(reports_router, "state_from_place_name", lambda db, name: "Sikkim" if name == "gangtok" else None)
    assert reports_router._report_state(MagicMock(), payload(place_name="gangtok")) == "Sikkim"
    assert reports_router._report_state(MagicMock(), payload(place_name="nowhere")) is None


# --- geocoding a place name to a state --------------------------------------


class FakeResponse:
    def __init__(self, matches):
        self._m = matches

    def raise_for_status(self):
        pass

    def json(self):
        return self._m


def geocode(monkeypatch, matches, states):
    """states: what state_at answers for each match, in order."""
    from app.services import geo

    monkeypatch.setattr(geo.httpx, "get", lambda *a, **k: FakeResponse(matches))
    answers = iter(states)
    monkeypatch.setattr(geo, "state_at", lambda db, lat, lng: next(answers))
    return geo.state_from_place_name(MagicMock(), "somewhere")


M = {"lat": "27.3", "lon": "88.6"}


def test_a_name_whose_matches_all_agree_gets_that_state(monkeypatch):
    assert geocode(monkeypatch, [M, M], ["Sikkim", "Sikkim"]) == "Sikkim"


def test_an_ambiguous_name_matching_two_states_gets_none(monkeypatch):
    assert geocode(monkeypatch, [M, M], ["Sikkim", "Assam"]) is None


def test_a_match_outside_our_coverage_makes_it_none_not_a_guess(monkeypatch):
    assert geocode(monkeypatch, [M, M], ["Sikkim", None]) is None


def test_no_matches_or_a_failed_lookup_gives_none_and_never_raises(monkeypatch):
    from app.services import geo

    assert geocode(monkeypatch, [], []) is None

    def boom(*a, **k):
        raise geo.httpx.ConnectError("down")

    monkeypatch.setattr(geo.httpx, "get", boom)
    assert geo.state_from_place_name(MagicMock(), "gangtok") is None
    assert geo.state_from_place_name(MagicMock(), " ") is None  # nothing to look up


def test_the_reports_list_filters_by_state_only_when_asked(client):
    c, db = client
    c.get("/reports", params={"state": "Nagaland"}, headers=H)
    assert "citizen_reports.state = 'Nagaland'" in sql(db.query.return_value.filter.call_args.args[0])
    db.query.return_value.filter.reset_mock()
    c.get("/reports", headers=H)
    db.query.return_value.filter.assert_not_called()
