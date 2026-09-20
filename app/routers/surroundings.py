import math
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Place, Zone
from app.schemas import NearbyPlaceOut, SurroundingsOut

router = APIRouter(prefix="/zones", tags=["zones"])

KM_PER_DEGREE = 111.32
VILLAGE_KINDS = ("village", "town", "city")
SERVICE_KINDS = ("hospital", "clinic", "police", "fire_station")
VILLAGES_SHOWN = 12  # the nearest few; the total is reported separately
SERVICES_PER_KIND = 2
COVERAGE_KM = 15  # if nothing at all is loaded within this distance, the area is not covered


def _nearby(db: Session, kinds: tuple[str, ...], lat: float, lng: float, radius_km: float, limit: int | None):
    """Places of these kinds within radius_km of a point, nearest first, as
    (Place, km) rows. A bounding box first (uses the (kind, lat, lng) index), then
    the equirectangular distance -- accurate enough over tens of km."""
    dlat = radius_km / KM_PER_DEGREE
    dlng = radius_km / (KM_PER_DEGREE * max(math.cos(math.radians(lat)), 0.01))
    dist_km = func.sqrt(
        func.power((Place.lat - lat) * KM_PER_DEGREE, 2) + func.power((Place.lng - lng) * KM_PER_DEGREE * math.cos(math.radians(lat)), 2)
    )
    query = (
        select(Place, dist_km.label("dist"))
        .where(Place.kind.in_(kinds), Place.lat.between(lat - dlat, lat + dlat), Place.lng.between(lng - dlng, lng + dlng), dist_km <= radius_km)
        .order_by("dist")
    )
    if limit is not None:
        query = query.limit(limit)
    return db.execute(query).all()


def _out(place: Place, km: float) -> NearbyPlaceOut:
    return NearbyPlaceOut(name=place.name or "", kind=place.kind, distance_km=round(km, 1), phone=place.phone)


@router.get("/{zone_id}/surroundings", response_model=SurroundingsOut)
def zone_surroundings(
    zone_id: uuid.UUID,
    village_km: float = Query(3.0, gt=0, le=10),
    service_km: float = Query(50.0, gt=0, le=100),
    db: Session = Depends(get_db),
):
    """Villages within a few km of a road stretch and the nearest hospital,
    clinic, police and fire station, from a downloaded OpenStreetMap snapshot.
    Public (residents need it). It does NOT say which villages are cut off, and
    gives no rescue time: OpenStreetMap has neither, and inventing them would be
    worse than saying so."""
    zone = db.get(Zone, zone_id)
    if zone is None:
        raise HTTPException(status_code=404, detail="Zone not found")

    covered = bool(_nearby(db, VILLAGE_KINDS + SERVICE_KINDS, zone.centroid_lat, zone.centroid_lng, COVERAGE_KM, 1))

    # Named places only: an unnamed dot is not something a person can act on.
    all_villages = [(p, km) for p, km in _nearby(db, VILLAGE_KINDS, zone.centroid_lat, zone.centroid_lng, village_km, None) if p.name]
    services: list[NearbyPlaceOut] = []
    for kind in SERVICE_KINDS:
        rows = [(p, km) for p, km in _nearby(db, (kind,), zone.centroid_lat, zone.centroid_lng, service_km, SERVICES_PER_KIND * 3) if p.name]
        services.extend(_out(p, km) for p, km in rows[:SERVICES_PER_KIND])
    services.sort(key=lambda s: s.distance_km)

    return SurroundingsOut(
        village_radius_km=village_km,
        service_radius_km=service_km,
        villages_total=len(all_villages),
        villages=[_out(p, km) for p, km in all_villages[:VILLAGES_SHOWN]],
        services=services,
        snapshot_at=db.scalar(select(func.max(Place.fetched_at))),
        area_covered=covered,
    )
