"""Opt-in browser notifications for Warning-level alerts: who may subscribe, who gets told, and
that nothing here can undo an alert or reach an address it should not. No database, no network."""
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from pywebpush import WebPushException

from app.config import settings
from app.database import get_db
from app.main import app
from app.models import AlertSubscription
from app.routers import subscriptions as subs_router
from app.services import alert_engine as ae
from app.services import push_alerts as pa

NOW = datetime(2026, 10, 24, 12, 0, tzinfo=timezone.utc)
GOOD = "https://fcm.googleapis.com/fcm/send/abcdefghijklmnopqrstuvwxyz"


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    monkeypatch.setattr(settings, "vapid_public_key", "PUBLIC")
    monkeypatch.setattr(settings, "vapid_private_key", "PRIVATE")
    monkeypatch.setattr(settings, "warning_max_window_days", 3)
    monkeypatch.setattr(settings, "push_cooldown_hours", 6)


def sub(lat=27.30, lng=88.60, radius=3.0, last=None, language="en", label="Pelling", endpoint=None):
    return AlertSubscription(
        id=uuid.uuid4(), channel="webpush", endpoint=endpoint or f"{GOOD}{uuid.uuid4().hex}", p256dh="p" * 30, auth="a" * 16,
        lat=lat, lng=lng, radius_km=radius, place_label=label, language=language, unsubscribe_token="t" * 40, last_notified_at=last,
    )


ZONE = SimpleNamespace(id=uuid.uuid4(), name="NH10 (1_00_001)", centroid_lat=27.30, centroid_lng=88.60)


def db_with(*subscriptions):
    db = MagicMock()
    db.execute.return_value.scalars.return_value.all.return_value = list(subscriptions)
    return db


# ---- the endpoint allow-list (SSRF) -----------------------------------------------------------


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://fcm.googleapis.com/fcm/send/abc",
        "https://updates.push.services.mozilla.com/wpush/v2/abc",
        "https://wns2-par02p.notify.windows.com/w/?token=abc",
        "https://web.push.apple.com/abc",
    ],
)
def test_the_browsers_own_push_services_are_accepted(endpoint):
    assert pa.is_allowed_push_endpoint(endpoint)


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://fcm.googleapis.com/fcm/send/abc",  # not https
        "https://localhost/hook",
        "https://127.0.0.1/hook",
        "https://169.254.169.254/latest/meta-data/",  # cloud metadata address
        "https://10.0.0.5/internal",
        "https://evil.example.com/fcm.googleapis.com",  # the allowed name only in the path
        "https://fcm.googleapis.com@evil.example.com/x",  # user-info trick: the real host is evil.example.com
        "https://fcm.googleapis.com.evil.example.com/x",  # allowed name as a prefix of another domain
        "https://notfcm.googleapis.com/x",  # shares the suffix text but is not a subdomain
        "https://fcm.googleapis.com:8443/x",  # a port other than 443
        "ftp://fcm.googleapis.com/x",
        "not a url",
    ],
)
def test_anything_else_is_refused_so_the_server_cannot_be_aimed_at_arbitrary_addresses(endpoint):
    assert not pa.is_allowed_push_endpoint(endpoint)


# ---- warning vs watch -----------------------------------------------------------------------------


def test_only_a_short_window_crossing_is_a_warning(monkeypatch):
    assert pa.is_warning(1) and pa.is_warning(3)
    assert not pa.is_warning(5) and not pa.is_warning(20) and not pa.is_warning(None)
    monkeypatch.setattr(settings, "warning_max_window_days", 1)  # a setting the team can change
    assert pa.is_warning(1) and not pa.is_warning(3)


# ---- who gets told ----------------------------------------------------------------------------------


def test_a_subscriber_is_told_only_if_the_zone_is_inside_their_own_radius():
    inside = sub(lat=27.31, lng=88.60, radius=3.0)  # ~1.1 km away
    outside = sub(lat=27.40, lng=88.60, radius=3.0)  # ~11 km away
    wide = sub(lat=27.35, lng=88.60, radius=8.0)  # ~5.6 km away, but asked for 8 km
    got = pa.subscribers_near(db_with(inside, outside, wide), ZONE.centroid_lat, ZONE.centroid_lng, NOW)
    assert inside in got and wide in got and outside not in got


def test_a_subscriber_in_cooldown_is_skipped_until_it_ends():
    recent = sub(last=NOW - timedelta(hours=2))
    old = sub(last=NOW - timedelta(hours=7))
    never = sub(last=None)
    got = pa.subscribers_near(db_with(recent, old, never), ZONE.centroid_lat, ZONE.centroid_lng, NOW)
    assert recent not in got and old in got and never in got


def test_the_message_is_in_the_subscribers_language_and_names_their_place():
    en = pa.build_payload(sub(language="en", label="Pelling"), ZONE.name, ZONE.id)
    hi = pa.build_payload(sub(language="hi", label="पेलिंग"), ZONE.name, ZONE.id)
    import json

    e, h = json.loads(en), json.loads(hi)
    assert "Pelling" in e["title"] and "112" in e["body"] and e["url"].endswith(f"/zones/{ZONE.id}")
    assert "पेलिंग" in h["title"] and "112" in h["body"]
    assert e["tag"] == f"warning-{ZONE.id}"
    assert "Pelling" not in pa.build_payload(sub(label=None), ZONE.name, ZONE.id)  # falls back to the zone name
    assert ZONE.name in pa.build_payload(sub(label=None), ZONE.name, ZONE.id)


# ---- delivery ---------------------------------------------------------------------------------------


def _gone(status):
    return WebPushException("gone", response=SimpleNamespace(status_code=status))


def test_delivery_counts_sends_removes_dead_subscriptions_and_survives_failures(monkeypatch):
    ok, dead, flaky = sub(), sub(), sub()
    db = db_with(ok, dead, flaky)
    db.get.return_value = ZONE
    sent_to = []

    def fake_send(s, payload):
        if s is dead:
            raise _gone(410)
        if s is flaky:
            raise _gone(500)
        sent_to.append(s)

    monkeypatch.setattr(pa, "_send", fake_send)
    result = pa.notify_zone_warning(db, ZONE.id)  # by id, as the engine calls it; the zone is loaded inside
    assert result == {"sent": 1, "failed": 1, "removed": 1}
    assert sent_to == [ok] and ok.last_notified_at is not None and flaky.last_notified_at is None
    db.delete.assert_called_once_with(dead)  # the push service said it is gone: do not keep it
    db.commit.assert_called()


def test_nothing_is_sent_when_push_is_not_configured(monkeypatch):
    monkeypatch.setattr(settings, "vapid_private_key", None)
    monkeypatch.setattr(pa, "_send", lambda *a: pytest.fail("must not send"))
    assert pa.notify_zone_warning(db_with(sub()), ZONE.id) == {"skipped": True, "reason": "web push is not configured"}


def test_an_unknown_zone_id_is_skipped_not_an_error():
    db = db_with(sub())
    db.get.return_value = None
    assert pa.notify_zone_warning(db, uuid.uuid4()) == {"skipped": True, "reason": "zone not found"}


# ---- the alert engine's hooks -----------------------------------------------------------------------


class FakeAlert:
    warning_notified_at = None


def test_an_alert_notifies_once_when_it_reaches_warning_and_never_for_a_long_window_only(monkeypatch):
    calls = []
    monkeypatch.setattr(pa, "notify_zone_warning", lambda db, zone_id: calls.append(zone_id) or {"sent": 1})
    db = MagicMock()
    watch = FakeAlert()
    assert ae.notify_if_newly_warning(db, watch, ZONE.id, 20) is False and watch.warning_notified_at is None and calls == []
    warn = FakeAlert()
    assert ae.notify_if_newly_warning(db, warn, ZONE.id, 2) is True and warn.warning_notified_at is not None and calls == [ZONE.id]
    assert ae.notify_if_newly_warning(db, warn, ZONE.id, 2) is False and calls == [ZONE.id]  # already told: not again


def test_a_watch_that_later_becomes_a_warning_notifies_at_that_moment(monkeypatch):
    calls = []
    monkeypatch.setattr(pa, "notify_zone_warning", lambda db, zone_id: calls.append(zone_id) or {})
    alert = FakeAlert()
    assert not ae.notify_if_newly_warning(MagicMock(), alert, ZONE.id, 15) and calls == []
    assert ae.notify_if_newly_warning(MagicMock(), alert, ZONE.id, 1) and calls == [ZONE.id]


def test_a_push_failure_never_undoes_the_alert_and_the_flag_still_stops_a_retry_storm(monkeypatch):
    def boom(db, zone_id):
        raise RuntimeError("push service down")

    monkeypatch.setattr(pa, "notify_zone_warning", boom)
    alert = FakeAlert()
    assert ae.notify_if_newly_warning(MagicMock(), alert, ZONE.id, 1) is True  # did not raise
    assert alert.warning_notified_at is not None  # at most once: no hourly retry blast


def test_a_worsened_update_uses_the_real_zone_name_even_for_the_refreshs_nameless_zone_object(monkeypatch):
    """Regression: the scheduled refresh passes a ZoneTarget (no .name) to escalate_if_worsened;
    the text used zone.name, raised AttributeError, and the error was swallowed -- so the
    "rain worsened" message never went out. The tests only ever passed a zone with a name."""
    from datetime import date

    from app.config import RainfallThresholdConfig

    texted = []
    monkeypatch.setattr(
        "app.services.sms_alerts.trigger_zone_alert",
        lambda db, zone_id, zone_name, severity, message=None, bypass_cooldown=False: texted.append(zone_name) or {"skipped": False, "sent": 1},
    )
    monkeypatch.setattr(pa, "notify_zone_warning", lambda db, zone_id: {})
    config = RainfallThresholdConfig(region="t", coefficient=40.0, exponent=-1.0, durations_days=[1], source="synthetic")
    today = datetime.now(timezone.utc).date()
    alert = SimpleNamespace(peak_ratio=1.2, worsened_at=None, worsened_count=0, delivery_method="log_only")
    nameless = SimpleNamespace(id=uuid.uuid4())  # what ZoneTarget looks like to the engine: no `name`
    db = MagicMock()
    db.get.return_value = SimpleNamespace(name="NH10 (1_00_001)")
    assert ae.escalate_if_worsened(db, alert, nameless, {today: 100.0}, config, "moderate") is True
    assert texted == ["NH10 (1_00_001)"]


# ---- the public API ---------------------------------------------------------------------------------


@pytest.fixture
def client():
    db = MagicMock()
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app), db
    app.dependency_overrides.pop(get_db, None)


BODY = {"endpoint": GOOD, "keys": {"p256dh": "p" * 30, "auth": "a" * 16}, "lat": 27.3, "lng": 88.6, "radius_km": 3, "place_label": "Pelling", "language": "en"}


def test_config_reports_off_and_hides_the_key_until_both_keys_are_set(client, monkeypatch):
    c, _ = client
    assert c.get("/subscriptions/config").json() == {"enabled": True, "public_key": "PUBLIC", "warning_window_days": 3, "default_radius_km": 3.0, "max_radius_km": 10.0}
    monkeypatch.setattr(settings, "vapid_private_key", None)
    off = c.get("/subscriptions/config").json()
    assert off["enabled"] is False and off["public_key"] is None


def test_subscribing_creates_a_subscription_and_returns_the_only_credential(client):
    c, db = client
    db.scalar.side_effect = [None, 0]  # no existing subscription for this endpoint; table is empty
    db.refresh.side_effect = lambda obj: setattr(obj, "id", uuid.uuid4())
    body = c.post("/subscriptions", json=BODY).json()
    added = db.add.call_args.args[0]
    assert added.endpoint == GOOD and added.channel == "webpush" and added.radius_km == 3 and added.place_label == "Pelling"
    assert body["unsubscribe_token"] == added.unsubscribe_token and len(added.unsubscribe_token) >= 32


def test_subscribing_the_same_browser_again_updates_it_and_keeps_its_token(client):
    c, db = client
    existing = sub(endpoint=GOOD, radius=3.0)
    db.scalar.side_effect = [existing]
    db.refresh.side_effect = lambda obj: None
    res = c.post("/subscriptions", json={**BODY, "radius_km": 6, "place_label": "Gangtok"})
    assert res.status_code == 200 and res.json()["unsubscribe_token"] == "t" * 40
    assert existing.radius_km == 6 and existing.place_label == "Gangtok"
    db.add.assert_not_called()


@pytest.mark.parametrize(
    "change,status",
    [
        ({"endpoint": "https://evil.example.com/x" + "a" * 20}, 422),  # not a push service
        ({"endpoint": "http://fcm.googleapis.com/fcm/send/" + "a" * 20}, 422),
        ({"lat": 51.5, "lng": -0.1}, 422),  # nowhere near the north-east
        ({"radius_km": 50}, 422),
        ({"radius_km": 0}, 422),
        ({"language": "fr"}, 422),
        ({"place_label": "p" * 121}, 422),
        ({"keys": {"p256dh": "x", "auth": "y"}}, 422),
    ],
)
def test_a_bad_subscription_is_refused_and_nothing_is_stored(client, change, status):
    c, db = client
    assert c.post("/subscriptions", json={**BODY, **change}).status_code == status
    db.add.assert_not_called()


def test_subscribing_is_refused_while_notifications_are_not_switched_on(client, monkeypatch):
    c, db = client
    monkeypatch.setattr(settings, "vapid_public_key", None)
    assert c.post("/subscriptions", json=BODY).status_code == 503
    db.add.assert_not_called()


def test_a_full_table_refuses_new_subscriptions(client, monkeypatch):
    c, db = client
    monkeypatch.setattr(subs_router, "MAX_SUBSCRIPTIONS", 2)
    db.scalar.side_effect = [None, 2]
    assert c.post("/subscriptions", json=BODY).status_code == 503
    db.add.assert_not_called()


def test_unsubscribing_deletes_the_row_and_an_unknown_token_gets_the_same_answer(client):
    c, db = client
    mine = sub()
    db.scalar.return_value = mine
    assert c.post("/subscriptions/unsubscribe", json={"unsubscribe_token": "t" * 40}).status_code == 204
    db.delete.assert_called_once_with(mine)
    db.reset_mock()
    db.scalar.return_value = None
    assert c.post("/subscriptions/unsubscribe", json={"unsubscribe_token": "z" * 40}).status_code == 204  # does not reveal which tokens exist
    db.delete.assert_not_called()
