"""Officer access key (app/security.py). None of these tests touch the database:
every request is either rejected by the key check before any query runs, or
sent with an invalid body so validation fails (422) without a query."""
import uuid

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app import security
from app.main import app

KEY = "correct-horse-battery-staple-2026"
ZONE = uuid.uuid4()
ALERT = uuid.uuid4()

# (method, path, kwargs) for every route the key must protect. Bodies are
# deliberately invalid so a request that gets past the key fails validation
# (422) instead of reaching the database.
PROTECTED = [
    ("put", f"/zones/{ZONE}/susceptibility", {"json": {}}),
    ("post", f"/rainfall/{ZONE}/fetch", {}),
    ("post", "/rainfall/refresh", {}),
    ("post", f"/alerts/{ALERT}/resolve", {}),
    ("post", f"/alerts/{ALERT}/generate-bulletin", {"json": {}}),
    ("post", f"/alerts/{ALERT}/broadcast", {"json": {}}),
    ("get", "/authority-contacts", {}),
    ("post", "/authority-contacts", {"json": {}}),
    ("delete", f"/authority-contacts/{uuid.uuid4()}", {}),
    ("get", "/reports", {}),
    ("post", f"/reports/{uuid.uuid4()}/verify", {}),
]


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    security._reset_throttle()
    yield
    security._reset_throttle()


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(security.settings, "api_key", KEY)
    return TestClient(app)


def _call(client, method, path, kwargs, key=None):
    headers = {"X-API-Key": key} if key is not None else {}
    return getattr(client, method)(path, headers=headers, **kwargs)


@pytest.mark.parametrize("method,path,kwargs", PROTECTED)
def test_protected_routes_reject_a_missing_key(client, method, path, kwargs):
    assert _call(client, method, path, kwargs).status_code == 401


@pytest.mark.parametrize("method,path,kwargs", PROTECTED)
def test_protected_routes_reject_a_wrong_key(client, method, path, kwargs):
    assert _call(client, method, path, kwargs, key="not-the-key").status_code == 401


@pytest.mark.parametrize("method,path,kwargs", [p for p in PROTECTED if p[2].get("json") is not None])
def test_the_right_key_gets_past_the_check(client, method, path, kwargs):
    # Reaches request validation (422 for the empty body), which only happens
    # after the key check passed and before any database access.
    assert _call(client, method, path, kwargs, key=KEY).status_code == 422


def test_public_endpoints_need_no_key(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "officer_auth": "enabled"}


def test_citizen_report_submission_stays_public(client):
    # No key sent: must not be a 401. (Empty form -> validation error, not auth.)
    assert client.post("/reports").status_code != 401
    assert client.post("/reports/polish-description", json={}).status_code != 401


def test_when_no_key_is_configured_nothing_is_locked(monkeypatch):
    monkeypatch.setattr(security.settings, "api_key", None)
    c = TestClient(app)
    assert c.put(f"/zones/{ZONE}/susceptibility", json={}).status_code == 422  # past auth, fails validation
    assert c.get("/health").json()["officer_auth"] == "disabled"


def test_the_key_itself_is_never_exposed_by_health(client):
    assert KEY not in client.get("/health").text


def test_repeated_wrong_guesses_are_throttled_but_the_right_key_still_works(client):
    for _ in range(security.MAX_FAILURES):
        assert client.get("/authority-contacts", headers={"X-API-Key": "guess"}).status_code == 401
    assert client.get("/authority-contacts", headers={"X-API-Key": "guess"}).status_code == 429
    # A correct key is never throttled (checked via the dependency directly so no DB is needed).
    assert security.require_officer_key(KEY) is None


def test_require_officer_key_raises_401_with_no_header(monkeypatch):
    monkeypatch.setattr(security.settings, "api_key", KEY)
    with pytest.raises(HTTPException) as exc:
        security.require_officer_key(None)
    assert exc.value.status_code == 401


def test_auth_headers_for_scripts(monkeypatch):
    monkeypatch.setattr(security.settings, "api_key", KEY)
    assert security.auth_headers() == {"X-API-Key": KEY}
    monkeypatch.setattr(security.settings, "api_key", None)
    assert security.auth_headers() == {}
