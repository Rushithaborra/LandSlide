"""Unit tests for app/services/description_polish.py -- the Gemini client
is mocked out entirely, no real API key or network call needed."""
from types import SimpleNamespace
from unittest.mock import patch

from app.services import description_polish


def _fake_response(text):
    return SimpleNamespace(text=text)


def test_polish_description_returns_corrected_text():
    with patch.object(description_polish, "get_client") as mock_get_client:
        mock_get_client.return_value.models.generate_content.return_value = _fake_response(
            "A large crack has appeared across the road near my house."
        )
        result = description_polish.polish_description("big crack acros road near my hous")
    assert result == "A large crack has appeared across the road near my house."


def test_polish_description_returns_none_on_api_error():
    with patch.object(description_polish, "get_client", side_effect=RuntimeError("Google API key not configured")):
        result = description_polish.polish_description("some text")
    assert result is None


def test_polish_description_returns_none_on_empty_response():
    with patch.object(description_polish, "get_client") as mock_get_client:
        mock_get_client.return_value.models.generate_content.return_value = _fake_response("   ")
        result = description_polish.polish_description("some text")
    assert result is None
