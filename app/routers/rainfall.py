import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from geoalchemy2.shape import to_shape
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import RainfallReading, Zone
from app.schemas import RainfallReadingOut
from app.services import open_meteo
from app.services.alert_engine import check_and_trigger

router = APIRouter(prefix="/rainfall", tags=["rainfall"])


@router.post("/{zone_id}/fetch", response_model=list[RainfallReadingOut])
def fetch_and_store(zone_id: uuid.UUID, db: Session = Depends(get_db)):
    """Pulls live rainfall from Open-Meteo for the zone's centroid, stores it,
    and runs the alert-trigger check on the latest reading."""
    zone = db.get(Zone, zone_id)
    if zone is None:
        raise HTTPException(status_code=404, detail="Zone not found")

    centroid = to_shape(zone.geometry).centroid
    daily = open_meteo.fetch_daily_rainfall(lat=centroid.y, lng=centroid.x)

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

    if readings:
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
