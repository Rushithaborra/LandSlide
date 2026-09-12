import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Alert, AlertBroadcast
from app.schemas import AlertOut, BroadcastIn, BroadcastOut

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertOut])
def list_alerts(status: str | None = None, db: Session = Depends(get_db)):
    # joinedload avoids an N+1 query -- AlertOut reads zone_name/risk_tier
    # through the zone relationship for every row.
    query = db.query(Alert).options(joinedload(Alert.zone))
    if status:
        query = query.filter(Alert.status == status)
    return query.order_by(Alert.triggered_at.desc()).all()


@router.post("/{alert_id}/resolve", response_model=AlertOut)
def resolve_alert(alert_id: uuid.UUID, db: Session = Depends(get_db)):
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.status = "resolved"
    db.commit()
    db.refresh(alert)
    return alert


@router.post("/{alert_id}/broadcast", response_model=BroadcastOut)
def broadcast_alert(alert_id: uuid.UUID, payload: BroadcastIn, db: Session = Depends(get_db)):
    """An officer's decision to push an alert out, recorded for real -- but
    status stays 'simulated': no SMS/CAP/siren gateway is wired up yet, same
    honesty as alerts.delivery_method='log_only'. One alert can have several
    broadcast rows (a correction, a re-send), so this never overwrites the
    alert itself."""
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    broadcast = AlertBroadcast(
        alert_id=alert_id,
        headline=payload.headline,
        severity=payload.severity,
        message=payload.message,
        channels=payload.channels,
        status="simulated",
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
