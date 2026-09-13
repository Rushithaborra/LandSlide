"""AI-generated one-line triage summary for a citizen report, via the
Gemini API (Google). Condenses a free-text field description into something
an officer can scan in one line on a crowded reports list -- e.g.
"Progressive shear failure precursor -- evacuate school and 12 households
immediately" instead of a full paragraph.

Uses Gemini (not Claude) specifically because it has a genuinely free tier
(Google AI Studio, no card required) -- this is a student/hackathon project
with no budget for Anthropic's prepaid API credits.

Best-effort, same pattern as app/services/sms_alerts.py: called from
POST /reports after the report is already committed, wrapped in a try/except
by the caller so a missing API key or a transient API error never blocks a
citizen's report from being accepted. triage_summary simply stays null.
"""
from app.config import settings

# Google's own "fastest, most cost-effective" flash-lite tier -- free-tier
# friendly, appropriate for a short, simple one-line summarization task
# (not the flagship gemini-3.8-flash, which is unnecessary for this).
MODEL = "gemini-3.5-flash-lite"

SYSTEM_PROMPT = (
    "You write one-line triage summaries for landslide-risk field reports, for a "
    "district officer scanning a long list of citizen reports. Given a report's "
    "type, severity, and free-text description, write exactly ONE short sentence "
    "(under 20 words) capturing the most actionable fact -- what's happening and "
    "what's at risk or needed. Do not add hedging, greetings, or explanation. "
    "Do not invent details not in the report. Output only the sentence, nothing else."
)

_client = None


def get_client():
    """Lazy singleton, same pattern as sms_alerts.get_twilio_client()."""
    global _client
    if _client is None:
        if not settings.google_api_key:
            raise RuntimeError(
                "Google API key not configured -- set GOOGLE_API_KEY "
                "before generating triage summaries."
            )
        from google import genai  # local import: optional dependency, only needed here

        _client = genai.Client(api_key=settings.google_api_key)
    return _client


def gemini_configured() -> bool:
    return bool(settings.google_api_key)


def generate_triage_summary(report_type: str, severity: str, description: str,
                             place_name: str | None = None) -> str | None:
    """Returns a one-line summary, or None if the API call fails for any
    reason (missing key, rate limit, network error) -- callers must treat
    None as "not generated yet", never as an error to surface to the citizen."""
    try:
        from google.genai import types

        client = get_client()
        location_line = f"Location: {place_name}\n" if place_name else ""
        response = client.models.generate_content(
            model=MODEL,
            contents=(
                f"Report type: {report_type}\nSeverity: {severity}\n{location_line}"
                f"Description: {description}"
            ),
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                max_output_tokens=100,
                temperature=0.2,
            ),
        )
        text = (response.text or "").strip()
        return text or None
    except Exception as e:
        print(f"[TRIAGE] summary generation failed: {e}")
        return None
