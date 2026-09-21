"""GET /system/integrations reports only whether credentials are set -- never their values."""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers import system as system_router

client = TestClient(app)


def set_all(monkeypatch, **values):
    for name in ("twilio_account_sid", "twilio_auth_token", "twilio_from_number", "google_api_key", "supabase_url", "supabase_service_role_key"):
        monkeypatch.setattr(system_router.settings, name, values.get(name))


def test_nothing_configured_reports_all_false(monkeypatch):
    set_all(monkeypatch)
    assert client.get("/system/integrations").json() == {"sms_voice": False, "ai_summaries": False, "photo_storage": False}


def test_each_service_needs_all_of_its_credentials(monkeypatch):
    set_all(monkeypatch, twilio_account_sid="AC-secret", twilio_auth_token="tok-secret")  # no from-number
    assert client.get("/system/integrations").json()["sms_voice"] is False
    set_all(monkeypatch, twilio_account_sid="AC-secret", twilio_auth_token="tok-secret", twilio_from_number="+10000000000",
            google_api_key="g-secret", supabase_url="https://x.supabase.co", supabase_service_role_key="sb-secret")
    assert client.get("/system/integrations").json() == {"sms_voice": True, "ai_summaries": True, "photo_storage": True}


@pytest.mark.parametrize("secret", ["AC-secret", "tok-secret", "g-secret", "sb-secret", "+10000000000"])
def test_no_credential_value_is_ever_returned(monkeypatch, secret):
    set_all(monkeypatch, twilio_account_sid="AC-secret", twilio_auth_token="tok-secret", twilio_from_number="+10000000000",
            google_api_key="g-secret", supabase_url="https://x.supabase.co", supabase_service_role_key="sb-secret")
    assert secret not in client.get("/system/integrations").text
