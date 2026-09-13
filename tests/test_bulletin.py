"""Unit tests for app/services/bulletin.py -- the Gemini client is mocked
out entirely, no real API key or network call needed, matching this
project's existing split between pure-logic tests and integration testing."""
from types import SimpleNamespace
from unittest.mock import patch

from app.services import bulletin


def _fake_response(draft):
    return SimpleNamespace(parsed=draft)


def test_generate_bulletin_returns_parsed_draft():
    draft = bulletin.BulletinDraft(headline="High risk near Mangan", message="Avoid the area until conditions improve.")
    with patch.object(bulletin, "get_client") as mock_get_client:
        mock_get_client.return_value.models.generate_content.return_value = _fake_response(draft)
        result = bulletin.generate_bulletin("NH310A (zone)", "high", "5d rainfall averaged 14.0mm/day, exceeding threshold", "high")
    assert result.headline == "High risk near Mangan"
    assert "Avoid the area" in result.message


def test_generate_bulletin_returns_none_on_api_error():
    with patch.object(bulletin, "get_client", side_effect=RuntimeError("Google API key not configured")):
        result = bulletin.generate_bulletin("Zone", "high", "trigger text", "high")
    assert result is None


def test_generate_bulletin_returns_none_on_empty_fields():
    draft = bulletin.BulletinDraft(headline="  ", message="  ")
    with patch.object(bulletin, "get_client") as mock_get_client:
        mock_get_client.return_value.models.generate_content.return_value = _fake_response(draft)
        result = bulletin.generate_bulletin("Zone", "high", "trigger text", "high")
    assert result is None


def test_generate_bulletin_returns_none_when_unparsed():
    with patch.object(bulletin, "get_client") as mock_get_client:
        mock_get_client.return_value.models.generate_content.return_value = _fake_response(None)
        result = bulletin.generate_bulletin("Zone", "high", "trigger text", "high")
    assert result is None
