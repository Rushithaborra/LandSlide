from fastapi import APIRouter

from app.config import settings
from app.schemas import IntegrationsOut

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/integrations", response_model=IntegrationsOut)
def integrations():
    """Which optional services this server has credentials for, as yes/no flags only --
    never a value. Feeds the Data & Observations page so it reports the running system,
    not a hard-coded list. 'Configured' means credentials are present, not that the
    provider is reachable right now."""
    return IntegrationsOut(
        sms_voice=all((settings.twilio_account_sid, settings.twilio_auth_token, settings.twilio_from_number)),
        ai_summaries=bool(settings.google_api_key),
        photo_storage=all((settings.supabase_url, settings.supabase_service_role_key)),
    )
