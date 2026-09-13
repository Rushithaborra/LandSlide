"""AI translation of a citizen report's description to English, via Gemini
-- for the officer reading it, not the citizen. A citizen writes naturally
in whichever language they're comfortable in (Hindi, Nepali, Bhutia,
Lepcha, or English); the original is always preserved unchanged, and this
generates an English rendering alongside it, clearly labeled, so an officer
who doesn't read that language can still act on the report.

Best-effort, same pattern as app/services/triage_summary.py: called from
POST /reports after the report is already committed, wrapped in a
try/except by the caller so a missing API key or a transient API error
never blocks a citizen's report from being accepted. description_translated
simply stays null.
"""
from app.services.ai_client import MODEL, get_client

SYSTEM_PROMPT = (
    "Translate the following citizen landslide-hazard report to English. Translate "
    "only -- do not add, remove, embellish, or summarize anything. Preserve the exact "
    "meaning and level of detail. If the text is already in English, return it "
    "completely unchanged. Output only the translation, nothing else."
)


def translate_to_english(text: str) -> str | None:
    """Returns an English rendering of `text` (or `text` itself, if the
    model determines it's already English), or None if the API call fails
    for any reason -- callers must treat None as "not generated yet", never
    as an error to surface to the citizen."""
    try:
        from google.genai import types

        client = get_client()
        response = client.models.generate_content(
            model=MODEL,
            contents=text,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                max_output_tokens=400,
                temperature=0.1,
            ),
        )
        translated = (response.text or "").strip()
        return translated or None
    except Exception as e:
        print(f"[TRANSLATE] translation failed: {e}")
        return None
