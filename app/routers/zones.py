import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Zone
from app.schemas import SusceptibilityUpdate, ZoneOut

router = APIRouter(prefix="/zones", tags=["zones"])


@router.get("", response_model=list[ZoneOut])
def list_zones(db: Session = Depends(get_db)):
    return db.query(Zone).all()


@router.get("/{zone_id}", response_model=ZoneOut)
def get_zone(zone_id: uuid.UUID, db: Session = Depends(get_db)):
    zone = db.get(Zone, zone_id)
    if zone is None:
        raise HTTPException(status_code=404, detail="Zone not found")
    return zone


@router.put("/{zone_id}/susceptibility", response_model=ZoneOut)
def update_susceptibility(zone_id: uuid.UUID, payload: SusceptibilityUpdate, db: Session = Depends(get_db)):
    """Write path for the ML lead's pipeline. Backend does not compute this score."""
    zone = db.get(Zone, zone_id)
    if zone is None:
        raise HTTPException(status_code=404, detail="Zone not found")
    zone.susceptibility_score = payload.susceptibility_score
    zone.risk_tier = payload.risk_tier
    db.commit()
    db.refresh(zone)
    return zone
