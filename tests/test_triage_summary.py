"""Unit tests for app/services/triage_summary.py -- the Gemini API client is
mocked out entirely, no real API key or network call needed, matching this
project's existing split between pure-logic tests and integration testing."""
from types import SimpleNamespace
from unittest.mock import patch

from app.services import ai_client, triage_summary


def _fake_response(text: str):
    return SimpleNamespace(text=text)


def test_generate_triage_summary_returns_model_text():
    with patch.object(triage_summary, "get_client") as mock_get_client:
        mock_get_client.return_value.models.generate_content.return_value = _fake_response(
            "Progressive shear failure precursor -- evacuate school and 12 households immediately."
        )
        result = triage_summary.generate_triage_summary("crack", "high", "Long rambling description of cracks near the school.")
    assert result == "Progressive shear failure precursor -- evacuate school and 12 households immediately."


def test_generate_triage_summary_returns_none_on_api_error():
    with patch.object(triage_summary, "get_client", side_effect=RuntimeError("Google API key not configured")):
        result = triage_summary.generate_triage_summary("crack", "high", "Some description.")
    assert result is None


def test_generate_triage_summary_returns_none_on_empty_response():
    with patch.object(triage_summary, "get_client") as mock_get_client:
        mock_get_client.return_value.models.generate_content.return_value = _fake_response("   ")
        result = triage_summary.generate_triage_summary("crack", "high", "Some description.")
    assert result is None


def test_gemini_configured_false_without_key():
    with patch.object(ai_client.settings, "google_api_key", None):
        assert ai_client.gemini_configured() is False


def test_gemini_configured_true_with_key():
    with patch.object(ai_client.settings, "google_api_key", "test-key"):
        assert ai_client.gemini_configured() is True
