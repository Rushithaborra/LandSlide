"""AI-generated one-line triage summary for a citizen report, via the Claude
API. Condenses a free-text field description into something an officer can
scan in one line on a crowded reports list -- e.g. "Progressive shear
failure precursor -- evacuate school and 12 households immediately" instead
of a full paragraph.

Best-effort, same pattern as app/services/sms_alerts.py: called from
POST /reports after the report is already committed, wrapped in a try/except
by the caller so a missing API key or a transient API error never blocks a
citizen's report from being accepted. triage_summary simply stays null.
"""
from app.config import settings

MODEL = "claude-opus-5"

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
        if not settings.anthropic_api_key:
            raise RuntimeError(
                "Anthropic API key not configured -- set ANTHROPIC_API_KEY "
                "before generating triage summaries."
            )
        import anthropic  # local import: optional dependency, only needed here

        _client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return _client


def anthropic_configured() -> bool:
    return bool(settings.anthropic_api_key)


def generate_triage_summary(report_type: str, severity: str, description: str,
                             place_name: str | None = None) -> str | None:
    """Returns a one-line summary, or None if the API call fails for any
    reason (missing key, rate limit, network error) -- callers must treat
    None as "not generated yet", never as an error to surface to the citizen."""
    try:
        client = get_client()
        location_line = f"Location: {place_name}\n" if place_name else ""
        response = client.messages.create(
            model=MODEL,
            max_tokens=100,
            system=SYSTEM_PROMPT,
            output_config={"effort": "low"},
            messages=[{
                "role": "user",
                "content": (
                    f"Report type: {report_type}\nSeverity: {severity}\n{location_line}"
                    f"Description: {description}"
                ),
            }],
        )
        text = "".join(block.text for block in response.content if block.type == "text").strip()
        return text or None
    except Exception as e:
        print(f"[TRIAGE] summary generation failed: {e}")
        return None
