import asyncio
import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload
from starlette.concurrency import run_in_threadpool

from app.database import SessionLocal, get_db
from app.models import Alert, AlertBroadcast, RainfallReading, Zone
from app.security import require_officer_key
from app.schemas import AlertOut, BroadcastIn, BroadcastOut, GenerateBulletinIn, GenerateBulletinOut
from app.services.bulletin import generate_bulletin
from app.services.sms_alerts import escalate_critical_alert, twilio_configured

router = APIRouter(prefix="/alerts", tags=["alerts"])

# How often the stream re-checks for new alerts. A live "does the dashboard
# actually update when an alert fires" demo moment doesn't need millisecond
# precision -- polling the DB every few seconds inside an SSE response is far
# simpler and more robust than a real pub/sub broker, and correct at this
# scale (a handful of alerts, a single Render worker). See
# `run_in_threadpool` below -- the DB session is plain sync SQLAlchemy (same
# as every other endpoint in this app), so each poll runs off the event loop
# instead of blocking every other request for the query's duration.
STREAM_POLL_SECONDS = 3


def _fetch_alerts_since(last_seen: datetime | None) -> list[Alert]:
    db = SessionLocal()
    try:
        query = db.query(Alert).options(joinedload(Alert.zone)).order_by(Alert.triggered_at.asc())
        if last_seen is not None:
            query = query.filter(Alert.triggered_at > last_seen)
        return query.all()
    finally:
        db.close()


@router.get("/stream")
async def stream_alerts():
    """Server-Sent Events: pushes each newly-triggered alert to connected
    dashboards the moment it's created, instead of the officer needing to
    manually refresh (or wait out a polling interval) to see it. One-way
    server -> browser, so SSE over the browser's native EventSource -- no
    new frontend dependency, automatic reconnection built in -- rather than
    WebSockets, which this doesn't need (the dashboard never sends anything
    back over this channel)."""

    async def event_stream():
        last_seen = datetime.now(timezone.utc)
        while True:
            await asyncio.sleep(STREAM_POLL_SECONDS)
            new_alerts = await run_in_threadpool(_fetch_alerts_since, last_seen)
            if new_alerts:
                last_seen = new_alerts[-1].triggered_at
                for alert in new_alerts:
                    payload = {
                        "id": str(alert.id),
                        "zone_id": str(alert.zone_id),
                        "zone_name": alert.zone.name if alert.zone else None,
                        "threshold_crossed": alert.threshold_crossed,
                        "triggered_at": alert.triggered_at.isoformat(),
                    }
                    yield f"data: {json.dumps(payload)}\n\n"
            else:
                yield ": keep-alive\n\n"  # SSE comment line -- keeps proxies from timing out an idle connection

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("", response_model=list[AlertOut])
def list_alerts(status: str | None = None, state: str | None = None, db: Session = Depends(get_db)):
    # joinedload avoids an N+1 query -- AlertOut reads zone_name/risk_tier
    # through the zone relationship for every row.
    query = db.query(Alert).options(joinedload(Alert.zone))
    if status:
        query = query.filter(Alert.status == status)
    if state:
        # An alert belongs to a state through its zone. Filtering here (an
        # EXISTS on the zone) replaces the dashboard downloading every zone
        # of the state just to work out which alerts are its own.
        query = query.filter(Alert.zone.has(Zone.state == state))
    alerts = query.order_by(Alert.triggered_at.desc()).all()
    _attach_latest_rainfall(db, alerts)
    return alerts


def _attach_latest_rainfall(db: Session, alerts: list[Alert]) -> None:
    """Each alert's text is frozen at the moment it was raised. Attach the
    zone's most recent OBSERVED daily rainfall (today at the latest, never a
    forecast day) so the dashboard can show what the rain is doing now."""
    zone_ids = {a.zone_id for a in alerts}
    if not zone_ids:
        return
    rows = db.execute(
        select(RainfallReading.zone_id, RainfallReading.timestamp, RainfallReading.intensity_mm)
        .where(RainfallReading.zone_id.in_(zone_ids), RainfallReading.timestamp <= func.now())
        .distinct(RainfallReading.zone_id)
        .order_by(RainfallReading.zone_id, RainfallReading.timestamp.desc())
    ).all()
    latest = {zone_id: (ts.date(), mm) for zone_id, ts, mm in rows}
    for a in alerts:
        a.latest_rainfall_date, a.latest_rainfall_mm = latest.get(a.zone_id, (None, None))


@router.post("/{alert_id}/resolve", response_model=AlertOut, dependencies=[Depends(require_officer_key)])
def resolve_alert(alert_id: uuid.UUID, db: Session = Depends(get_db)):
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    if alert.status != "resolved":  # idempotent: don't overwrite who/when it was first resolved
        alert.status = "resolved"
        alert.resolved_at = datetime.now(timezone.utc)
        alert.resolved_by = "officer"
    db.commit()
    db.refresh(alert)
    return alert


@router.post("/{alert_id}/generate-bulletin", response_model=GenerateBulletinOut, dependencies=[Depends(require_officer_key)])
def generate_bulletin_draft(alert_id: uuid.UUID, payload: GenerateBulletinIn, db: Session = Depends(get_db)):
    """AI-drafted headline+message for the Broadcast composer (Gemini, see
    app.services.bulletin) -- the officer reviews and can edit every word
    before actually sending. Uses the alert's own real data, not invented
    numbers. 502 if the draft can't be generated (missing key, API error) --
    the composer falls back to a blank form, not a fake draft."""
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    draft = generate_bulletin(alert.zone.name, alert.zone.risk_tier, alert.threshold_crossed, payload.severity)
    if draft is None:
        raise HTTPException(status_code=502, detail="Could not generate a bulletin draft right now")
    return GenerateBulletinOut(headline=draft.headline, message=draft.message)


@router.post("/{alert_id}/broadcast", response_model=BroadcastOut, dependencies=[Depends(require_officer_key)])
def broadcast_alert(alert_id: uuid.UUID, payload: BroadcastIn, db: Session = Depends(get_db)):
    """An officer's decision to push an alert out. Real SMS (and, for
    severity='critical', a real phone call to every registered authority) go
    out via app.services.sms_alerts when Twilio is configured and "sms" is
    one of the chosen channels -- status becomes 'sent' only then. Push/
    siren/CAP-gateway remain simulated (no such gateway is wired up) --
    'sent' never overclaims delivery on channels that aren't actually real.
    One alert can have several broadcast rows (a correction, a re-send), so
    this never overwrites the alert itself."""
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")

    status = "simulated"
    if twilio_configured() and ("sms" in payload.channels or payload.severity == "critical"):
        try:
            result = escalate_critical_alert(
                db, alert.zone_id, alert.zone.name, payload.severity,
                message=payload.message, send_sms="sms" in payload.channels,
            )
            sms_sent = not result["sms"].get("skipped") and result["sms"].get("sent", 0) > 0
            calls_made = not result["calls"].get("skipped") and result["calls"].get("called", 0) > 0
            if sms_sent or calls_made:
                status = "sent"
        except Exception as e:
            print(f"[BROADCAST] alert={alert_id} real send failed, staying simulated: {e}")

    broadcast = AlertBroadcast(
        alert_id=alert_id,
        headline=payload.headline,
        severity=payload.severity,
        message=payload.message,
        channels=payload.channels,
        status=status,
    )
    db.add(broadcast)
    db.commit()
    db.refresh(broadcast)
    return broadcast


@router.get("/{alert_id}/broadcasts", response_model=list[BroadcastOut])
def list_broadcasts(alert_id: uuid.UUID, db: Session = Depends(get_db)):
    return (
        db.query(AlertBroadcast)
        .filter(AlertBroadcast.alert_id == alert_id)
        .order_by(AlertBroadcast.dispatched_at.desc())
        .all()
    )
