"""AI wording assist for a citizen filling out the report form -- fixes
grammar, spelling, and clarity in the citizen's OWN description before they
submit. Deliberately does NOT rewrite, expand, or embellish: a citizen
report is a first-hand ground-truth account an officer verifies against, so
this must never add a detail, number, or claim the citizen didn't actually
write. The citizen sees the suggestion and chooses to accept it or keep
their own wording -- this never runs silently or auto-replaces their text.

This is a deliberately narrower, safer scope than the AI features on the
officer side (triage_summary.py, bulletin.py): those condense or draft text
a trained officer reviews before it goes anywhere; this touches the
citizen's own testimony, so authorship integrity matters more than fluency.
"""
from app.services.ai_client import MODEL, get_client

SYSTEM_PROMPT = (
    "You fix grammar, spelling, and clarity in a citizen's landslide hazard report "
    "description. Rules, strictly enforced:\n"
    "1. Do NOT add any fact, number, measurement, location detail, or claim that "
    "is not already in the original text.\n"
    "2. Do NOT change what the citizen is saying, its meaning, or its severity.\n"
    "3. Do NOT make it longer or more dramatic than the original -- fix wording only.\n"
    "4. If the original is already clear, return it with minimal or no changes.\n"
    "5. Keep the same language the citizen wrote in.\n"
    "Output only the corrected text, nothing else -- no preamble, no quotes."
)


def polish_description(text: str) -> str | None:
    """Returns a grammar/clarity-corrected version of `text`, or None if the
    API call fails for any reason -- callers must fall back to the
    citizen's original text unchanged, never block or replace it silently."""
    try:
        from google.genai import types

        client = get_client()
        response = client.models.generate_content(
            model=MODEL,
            contents=text,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                max_output_tokens=300,
                temperature=0.1,
            ),
        )
        polished = (response.text or "").strip()
        return polished or None
    except Exception as e:
        print(f"[POLISH] description polish failed: {e}")
        return None
