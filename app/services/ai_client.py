"""Shared Gemini client singleton, used by both app/services/triage_summary.py
and app/services/bulletin.py -- one client, one place that knows how to
build it, instead of two copies of the same lazy-singleton logic.

Gemini (not Claude/OpenAI) specifically because it has a genuinely free tier
(Google AI Studio, no card required) -- this is a student/hackathon project
with no budget for paid API credits.
"""
from app.config import settings

# Google's own "fastest, most cost-effective" flash-lite tier -- free-tier
# friendly, appropriate for the short generation tasks this project uses it
# for (a one-line summary, a short public bulletin), not the flagship
# gemini-3.8-flash, which would be unnecessary here.
MODEL = "gemini-3.5-flash-lite"

_client = None


def get_client():
    """Lazy singleton, same pattern as sms_alerts.get_twilio_client()."""
    global _client
    if _client is None:
        if not settings.google_api_key:
            raise RuntimeError(
                "Google API key not configured -- set GOOGLE_API_KEY before "
                "generating AI text."
            )
        from google import genai  # local import: optional dependency, only needed here

        _client = genai.Client(api_key=settings.google_api_key)
    return _client


def gemini_configured() -> bool:
    return bool(settings.google_api_key)
