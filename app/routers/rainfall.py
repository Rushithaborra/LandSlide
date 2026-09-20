import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import get_rainfall_threshold
from app.database import get_db
from app.models import RainfallReading, Zone
from app.schemas import RainfallReadingOut, RainfallThresholdOut
from app.services import open_meteo
from app.services.alert_engine import intensity_duration_threshold, check_and_trigger
from app.security import require_officer_key

router = APIRouter(prefix="/rainfall", tags=["rainfall"])


@router.post("/{zone_id}/fetch", response_model=list[RainfallReadingOut], dependencies=[Depends(require_officer_key)])
def fetch_and_store(zone_id: uuid.UUID, db: Session = Depends(get_db)):
    """Pulls live rainfall from Open-Meteo for the zone's centroid, stores it,
    and runs the alert-trigger check on the latest reading.

    Idempotent by (zone_id, day): Open-Meteo's `past_days` window always
    covers the same recent days on every call, so a naive insert would add a
    duplicate row per day every time this endpoint is hit -- which matters
    once something calls this on every dashboard view to keep data current
    (see the frontend's getRainfallTrend) rather than as a one-off batch
    script. Replacing this zone's existing rows in the fetched window keeps
    a call "refresh what's already there", not "append forever"."""
    zone = db.get(Zone, zone_id)
    if zone is None:
        raise HTTPException(status_code=404, detail="Zone not found")

    daily = open_meteo.fetch_daily_rainfall(lat=zone.centroid_lat, lng=zone.centroid_lng)
    if not daily:
        return []

    fetched_days = {d.day for d in daily}
    day_start = datetime.combine(min(fetched_days), datetime.min.time(), tzinfo=timezone.utc)
    day_end = datetime.combine(max(fetched_days), datetime.min.time(), tzinfo=timezone.utc)
    db.query(RainfallReading).filter(
        RainfallReading.zone_id == zone_id,
        RainfallReading.timestamp >= day_start,
        RainfallReading.timestamp <= day_end,
    ).delete(synchronize_session=False)

    readings = [
        RainfallReading(
            zone_id=zone_id,
            timestamp=datetime.combine(d.day, datetime.min.time(), tzinfo=timezone.utc),
            intensity_mm=d.intensity_mm,
            source="open-meteo",
        )
        for d in daily
    ]
    db.add_all(readings)
    db.commit()
    for r in readings:
        db.refresh(r)

    check_and_trigger(db, zone_id)

    return readings


@router.get("/{zone_id}", response_model=list[RainfallReadingOut])
def list_readings(zone_id: uuid.UUID, db: Session = Depends(get_db)):
    return (
        db.query(RainfallReading)
        .filter(RainfallReading.zone_id == zone_id)
        .order_by(RainfallReading.timestamp.desc())
        .all()
    )


@router.get("/{zone_id}/threshold", response_model=RainfallThresholdOut | None)
def get_zone_threshold(zone_id: uuid.UUID, db: Session = Depends(get_db)):
    """The real threshold the dashboard's rainfall chart should draw its
    reference line against -- previously the chart used a hardcoded, fake
    100mm constant (dashboard-app/src/data/mockData.js) that had no
    relationship to what actually fires an alert (app.services.alert_engine,
    scaled by this zone's own risk_tier). Returns null, not an invented
    number, when this zone's state has no configured threshold (e.g.
    Mizoram today) -- same "don't guess" rule the alert engine itself
    already follows in check_and_trigger."""
    zone = db.get(Zone, zone_id)
    if zone is None:
        raise HTTPException(status_code=404, detail="Zone not found")

    config = get_rainfall_threshold(zone.state)
    if config is None:
        return None

    risk_tier = zone.risk_tier or "moderate"
    return RainfallThresholdOut(
        threshold_mm_per_day=intensity_duration_threshold(1, config, risk_tier),
        risk_tier=risk_tier,
        source=config.source,
        verified_against_primary_text=config.verified_against_primary_text,
    )
