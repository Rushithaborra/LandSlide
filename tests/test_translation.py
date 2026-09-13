"""Unit tests for app/services/translation.py -- the Gemini client is
mocked out entirely, no real API key or network call needed."""
from types import SimpleNamespace
from unittest.mock import patch

from app.services import translation


def _fake_response(text):
    return SimpleNamespace(text=text)


def test_translate_to_english_returns_translation():
    with patch.object(translation, "get_client") as mock_get_client:
        mock_get_client.return_value.models.generate_content.return_value = _fake_response(
            "A large crack has appeared near my house."
        )
        result = translation.translate_to_english("mere ghar ke pass ek bada darar aaya hai")
    assert result == "A large crack has appeared near my house."


def test_translate_to_english_returns_none_on_api_error():
    with patch.object(translation, "get_client", side_effect=RuntimeError("Google API key not configured")):
        result = translation.translate_to_english("some text")
    assert result is None


def test_translate_to_english_returns_none_on_empty_response():
    with patch.object(translation, "get_client") as mock_get_client:
        mock_get_client.return_value.models.generate_content.return_value = _fake_response("   ")
        result = translation.translate_to_english("some text")
    assert result is None
