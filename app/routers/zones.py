import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, load_only

from app.database import get_db
from app.models import Zone
from app.schemas import SusceptibilityUpdate, ZoneOut

# ZoneOut never includes the full polygon `geometry` column (only its
# precomputed centroid), but a plain `db.query(Zone)` hydrates it anyway --
# for a wide corridor polygon that's real, non-trivial WKB per row, on top of
# every column ZoneOut actually needs. load_only() tells SQLAlchemy to
# SELECT just those columns, skipping geometry entirely at both the DB I/O
# and Python-deserialization layers -- confirmed via EXPLAIN ANALYZE that
# the raw query itself was fast (~5s for 66,677 Assam rows); the gap to a
# noticeably slower full HTTP response was this exact overhead. Shared with
# app/routers/corridors.py, which fetches the same Zone rows the same way.
ZONE_LIST_COLUMNS = load_only(
    Zone.id, Zone.name, Zone.state, Zone.susceptibility_score, Zone.risk_tier,
    Zone.model_version, Zone.last_updated, Zone.centroid_lat, Zone.centroid_lng,
)

router = APIRouter(prefix="/zones", tags=["zones"])

# A real, demonstrated production bug: GET /zones had no limit at all, and
# returning every matching row (already a ~45-60s load at Sikkim's 3,921
# zones) timed out completely once Assam's 66,677 real zones landed.
# Defaulting -- not just capping on request -- means every existing caller
# (nothing in this codebase passed limit/offset before this fix) is
# automatically protected without needing to change first.
#
# Sorted by susceptibility_score, not risk_tier directly: risk_tier is
# itself derived from susceptibility_score via cutoff thresholds
# (scripts/generate_zone_predictions.py's score_to_tier), so the two sort
# identically in practice -- but susceptibility_score is a plain numeric
# column a btree index can actually satisfy (migrations/
# 009_zone_centroid_columns.sql), where a CASE-based priority on the string
# risk_tier could not.
DEFAULT_ZONE_LIMIT = 2000
MAX_ZONE_LIMIT = 5000


@router.get("", response_model=list[ZoneOut])
def list_zones(
    state: str | None = None,
    limit: int = Query(DEFAULT_ZONE_LIMIT, gt=0, le=MAX_ZONE_LIMIT),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(Zone).options(ZONE_LIST_COLUMNS)
    if state:
        query = query.filter(Zone.state == state)
    # Zone.id as a tiebreaker: offset paging over a non-unique sort key can
    # repeat one row on two pages and skip another when scores tie (782
    # zones share a score with another today), since Postgres doesn't
    # promise a stable order among equal keys between separate requests.
    query = query.order_by(Zone.susceptibility_score.desc().nulls_last(), Zone.id)
    return query.offset(offset).limit(limit).all()


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
    zone.model_version = payload.model_version
    db.commit()
    db.refresh(zone)
    return zone
