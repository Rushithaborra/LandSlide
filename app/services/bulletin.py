"""AI-drafted public warning bulletin for the Broadcast composer, via the
Gemini API. The officer still picks severity and channels and can edit
every word before sending -- this only saves them from writing a headline
and message from scratch, using the alert's own real data (zone name, risk
tier, the rainfall trigger that actually fired it).

This is the other half of the "AI-generated text" idea from the reference-
video comparison (SITREP bulletins + per-report triage summaries) --
app/services/triage_summary.py already covers the report-triage half.
"""
from pydantic import BaseModel

from app.services.ai_client import MODEL, get_client

SYSTEM_PROMPT = (
    "You draft short public warning bulletins for a landslide early-warning system, "
    "for a district officer to review and send. Given a zone name, its risk tier, the "
    "rainfall trigger that fired the alert, and the severity the officer has chosen, "
    "write a headline (under 12 words, no punctuation at the end) and a message "
    "(2-3 sentences, plain public safety language: what's happening, what to do). "
    "Do not invent numbers or details beyond what's given. Do not use alarmist or "
    "exaggerated language beyond what the severity level warrants."
)


class BulletinDraft(BaseModel):
    headline: str
    message: str


def generate_bulletin(zone_name: str, risk_tier: str | None, threshold_crossed: str,
                       severity: str) -> BulletinDraft | None:
    """Returns a draft headline+message, or None if the API call fails for
    any reason -- callers must fall back to an empty/manual-entry form,
    never surface this as an error to the officer."""
    try:
        from google.genai import types

        client = get_client()
        response = client.models.generate_content(
            model=MODEL,
            contents=(
                f"Zone: {zone_name}\nRisk tier: {risk_tier or 'not yet scored'}\n"
                f"Rainfall trigger: {threshold_crossed}\nBroadcast severity: {severity}"
            ),
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                max_output_tokens=300,
                temperature=0.4,
                response_mime_type="application/json",
                response_schema=BulletinDraft,
            ),
        )
        draft = response.parsed
        if draft is None or not draft.headline.strip() or not draft.message.strip():
            return None
        return draft
    except Exception as e:
        print(f"[BULLETIN] draft generation failed: {e}")
        return None
