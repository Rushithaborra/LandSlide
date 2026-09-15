"""Real SMS/voice alert delivery via Twilio -- ported from teammate D's
handover module (docs/sms_voice_alert_handover.md) onto this backend's actual
SQLAlchemy ORM stack (the original was written against a raw psycopg2
connection and a `reports` table that doesn't exist here -- see that doc's
"Integration notes" section for the full list of fixes).

Two separate entry points, matching the two places a severity actually comes
from in this app:
- `trigger_zone_alert()`: automatic SMS to citizen subscribers, called from
  app.services.alert_engine.check_and_trigger() with the zone's `risk_tier`
  (low/moderate/high -- there is no "critical" tier in the automated engine).
- `escalate_critical_alert()`: SMS + a real phone call to every registered
  authority, called from the Broadcast composer
  (app/routers/alerts.py:broadcast_alert) with the operator's own chosen
  severity, which is the only place "critical" is ever actually selected.
"""
import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import AuthorityContact, CitizenReport, SmsAlertLog

# Minimum time between automatic SMS alerts for the SAME zone, so one ongoing
# rain event doesn't spam the same people every time check_and_trigger() reruns.
# Does not apply to the Broadcast composer path -- that's an operator's
# deliberate, on-demand action and should never be silently dropped.
COOLDOWN_MINUTES = 30

_client = None


def get_twilio_client():
    """Lazy singleton -- avoids importing/creating a Twilio client unless
    something actually tries to send. Raises a clear error if credentials
    aren't configured, same pattern as the missing-Supabase-config error in
    app/routers/reports.py, rather than silently no-op'ing."""
    global _client
    if _client is None:
        if not (settings.twilio_account_sid and settings.twilio_auth_token and settings.twilio_from_number):
            raise RuntimeError(
                "Twilio not configured -- set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, "
                "TWILIO_FROM_NUMBER before sending real SMS/voice alerts."
            )
        from twilio.rest import Client  # local import: optional dependency, only needed here

        _client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
    return _client


def twilio_configured() -> bool:
    return bool(settings.twilio_account_sid and settings.twilio_auth_token and settings.twilio_from_number)


def format_alert_message(zone_name: str, severity: str) -> str:
    return (
        f"RESQ ALERT: {severity.upper()} landslide risk near {zone_name}. "
        f"Rainfall has crossed the danger threshold for this area. "
        f"Avoid unstable slopes and roads. Follow local authority guidance."
    )


def send_sms(to_number: str, message: str) -> dict:
    """Sends one text via Twilio. Wrapped so one bad number doesn't crash a
    whole batch -- returns a success/failure result instead of raising."""
    try:
        client = get_twilio_client()
        result = client.messages.create(body=message, from_=settings.twilio_from_number, to=to_number)
        return {"to": to_number, "success": True, "sid": result.sid}
    except Exception as e:
        return {"to": to_number, "success": False, "error": str(e)}


def make_alert_call(to_number: str, message: str) -> dict:
    """Places an automated voice call reading the message aloud twice via
    Twilio's <Say> (phone audio is easier to miss/mishear than a re-readable
    text)."""
    twiml = (
        f'<Response>'
        f'<Say voice="alice">{message}</Say>'
        f'<Pause length="1"/>'
        f'<Say voice="alice">Repeating. {message}</Say>'
        f'</Response>'
    )
    try:
        client = get_twilio_client()
        call = client.calls.create(twiml=twiml, to=to_number, from_=settings.twilio_from_number)
        return {"to": to_number, "success": True, "sid": call.sid}
    except Exception as e:
        return {"to": to_number, "success": False, "error": str(e)}


def get_subscribers_for_zone(db: Session, zone_id) -> list[str]:
    """Distinct, non-empty reporter phone numbers from citizen reports in
    this zone -- a pragmatic v1 recipient list with no new opt-in UI needed."""
    rows = db.execute(
        select(CitizenReport.reporter_phone)
        .where(CitizenReport.zone_id == zone_id, CitizenReport.reporter_phone.isnot(None), CitizenReport.reporter_phone != "")
        .distinct()
    ).all()
    return [r[0] for r in rows]


def get_authority_contacts(db: Session) -> list[dict]:
    contacts = db.execute(
        select(AuthorityContact).where(AuthorityContact.phone_number.isnot(None), AuthorityContact.phone_number != "")
    ).scalars().all()
    return [{"name": c.name, "phone": c.phone_number} for c in contacts]


def get_last_alert_time_by_channel(db: Session, zone_id, channel: str):
    row = db.execute(
        select(SmsAlertLog.sent_at)
        .where(SmsAlertLog.zone_id == zone_id, SmsAlertLog.channel == channel)
        .order_by(SmsAlertLog.sent_at.desc())
        .limit(1)
    ).first()
    return row[0] if row else None


def log_alert_sent(db: Session, zone_id, severity: str, recipient_count: int, channel: str = "sms") -> None:
    db.add(SmsAlertLog(zone_id=zone_id, severity=severity, recipient_count=recipient_count, channel=channel))
    db.commit()


def trigger_zone_alert(
    db: Session, zone_id, zone_name: str, severity: str, message: str | None = None, bypass_cooldown: bool = False,
) -> dict:
    """Automatic SMS to citizen subscribers, gated by a per-zone cooldown so
    the same rain event doesn't re-text people every few minutes. `message`
    lets a caller (the Broadcast composer) pass the operator's own written
    text instead of the auto-generated one. `bypass_cooldown` exists because
    this same function is also the composer's SMS path (via
    escalate_critical_alert) -- without it, a recent *automatic* SMS for a
    zone could silently swallow an operator's later, deliberate composer
    send, directly contradicting this module's own documented guarantee
    (see COOLDOWN_MINUTES's comment) that the composer path is never
    silently dropped. Caught live: verified the two paths shared this gate
    with no way to tell them apart."""
    if not bypass_cooldown:
        last_sent = get_last_alert_time_by_channel(db, zone_id, "sms")
        if last_sent is not None:
            elapsed = datetime.datetime.now(datetime.timezone.utc) - last_sent
            if elapsed < datetime.timedelta(minutes=COOLDOWN_MINUTES):
                return {"skipped": True, "reason": f"Cooldown active -- last SMS {elapsed.seconds // 60} min ago"}

    subscribers = get_subscribers_for_zone(db, zone_id)
    if not subscribers:
        return {"skipped": True, "reason": "No subscribers with phone numbers for this zone yet"}

    text = message or format_alert_message(zone_name, severity)
    results = [send_sms(number, text) for number in subscribers]
    sent_count = sum(1 for r in results if r["success"])
    log_alert_sent(db, zone_id, severity, sent_count, channel="sms")

    return {
        "skipped": False,
        "attempted": len(subscribers),
        "sent": sent_count,
        "failed": len(subscribers) - sent_count,
        "results": results,
    }


def escalate_critical_alert(
    db: Session, zone_id, zone_name: str, severity: str, message: str | None = None, send_sms: bool = True,
) -> dict:
    """A real phone call to every registered authority, only when severity ==
    'critical'; optionally also SMS to citizens (send_sms=False lets the
    Broadcast composer skip texting when the operator didn't choose the
    "sms" channel, while still escalating a critical broadcast to a call).
    `message` lets a caller pass the operator's own written text instead of
    the auto-generated one."""
    text = message or format_alert_message(zone_name, severity)
    sms_result = (
        trigger_zone_alert(db, zone_id, zone_name, severity, message=text, bypass_cooldown=True)
        if send_sms
        else {"skipped": True, "reason": "sms channel not selected"}
    )

    if severity != "critical":
        return {"sms": sms_result, "calls": {"skipped": True, "reason": "Not critical severity"}}

    last_call = get_last_alert_time_by_channel(db, zone_id, "call")
    if last_call is not None:
        elapsed = datetime.datetime.now(datetime.timezone.utc) - last_call
        if elapsed < datetime.timedelta(minutes=COOLDOWN_MINUTES):
            return {"sms": sms_result, "calls": {"skipped": True, "reason": "Call cooldown active"}}

    authorities = get_authority_contacts(db)
    if not authorities:
        return {"sms": sms_result, "calls": {"skipped": True, "reason": "No authority contacts registered"}}

    call_results = [make_alert_call(a["phone"], text) for a in authorities]
    called_count = sum(1 for r in call_results if r["success"])
    log_alert_sent(db, zone_id, severity, called_count, channel="call")

    return {
        "sms": sms_result,
        "calls": {
            "skipped": False,
            "attempted": len(authorities),
            "called": called_count,
            "results": call_results,
        },
    }
