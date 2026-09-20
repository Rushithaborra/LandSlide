import math
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, load_only

from app.database import get_db
from app.models import Alert, Zone
from app.security import require_officer_key
from app.schemas import (
    AreaRiskOut,
    MapClusterOut,
    MapViewOut,
    MapZoneOut,
    NearestSaferOut,
    SusceptibilityUpdate,
    ZoneOut,
    ZoneStatsOut,
)

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
MAP_COLUMNS = load_only(
    Zone.id, Zone.name, Zone.state, Zone.susceptibility_score, Zone.risk_tier,
    Zone.centroid_lat, Zone.centroid_lng,
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

# The map never needs every zone at once. Below this many zones in view it
# gets each one as a pin; above it, a coarse grid of counts. That keeps the
# payload small (and the browser fast) whether the database holds 4,000
# zones or 100,000 -- listing them all, even paged, stops working long
# before then.
MAP_MAX_INDIVIDUAL_ZONES = 1500
MAP_GRID_TARGET_CELLS = 10


def grid_cell_degrees(span_deg: float, target_cells: int = MAP_GRID_TARGET_CELLS) -> float:
    """Grid cell size for a map view `span_deg` wide: a power of two, so the
    cell edges stay in the same place while the user pans at one zoom level
    (a viewport-relative grid would reshuffle every cluster on each drag)."""
    return 2.0 ** math.floor(math.log2(max(span_deg, 1e-6) / target_cells))


@router.get("", response_model=list[ZoneOut])
def list_zones(
    state: str | None = None,
    q: str | None = Query(None, min_length=2, description="case-insensitive name search"),
    limit: int = Query(DEFAULT_ZONE_LIMIT, gt=0, le=MAX_ZONE_LIMIT),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(Zone).options(ZONE_LIST_COLUMNS)
    if state:
        query = query.filter(Zone.state == state)
    if q:
        query = query.filter(Zone.name.icontains(q, autoescape=True))
    # Zone.id as a tiebreaker: offset paging over a non-unique sort key can
    # repeat one row on two pages and skip another when scores tie (782
    # zones share a score with another today), since Postgres doesn't
    # promise a stable order among equal keys between separate requests.
    query = query.order_by(Zone.susceptibility_score.desc().nulls_last(), Zone.id)
    return query.offset(offset).limit(limit).all()


KM_PER_DEGREE = 111.32


@router.get("/near", response_model=AreaRiskOut)
def area_risk(
    lat: float = Query(ge=-90, le=90),
    lng: float = Query(ge=-180, le=180),
    radius_km: float = Query(3.0, gt=0, le=10),
    db: Session = Depends(get_db),
):
    """The risk picture around a point (a village, a searched place, or the
    visitor's own GPS position). Public on purpose -- it is what a resident
    needs. One indexed-box query: a bounding box first (cheap), then the exact
    distance, so it stays fast with 100k zones."""
    dlat = radius_km / KM_PER_DEGREE
    dlng = radius_km / (KM_PER_DEGREE * max(math.cos(math.radians(lat)), 0.01))
    # Equirectangular distance in km -- plenty accurate over a few km.
    dist_km = func.sqrt(
        func.power((Zone.centroid_lat - lat) * KM_PER_DEGREE, 2)
        + func.power((Zone.centroid_lng - lng) * KM_PER_DEGREE * math.cos(math.radians(lat)), 2)
    )
    rows = db.execute(
        select(Zone, dist_km.label("dist"))
        .options(ZONE_LIST_COLUMNS)
        .where(
            Zone.centroid_lat.between(lat - dlat, lat + dlat),
            Zone.centroid_lng.between(lng - dlng, lng + dlng),
            dist_km <= radius_km,
        )
        .order_by("dist")
        .limit(1000)
    ).all()

    counts = {"high": 0, "moderate": 0, "low": 0, "unscored": 0}
    for zone, _ in rows:
        counts[zone.risk_tier if zone.risk_tier in counts else "unscored"] += 1
    active = 0
    if rows:
        active = db.scalar(
            select(func.count(func.distinct(Alert.zone_id))).where(
                Alert.status == "active", Alert.zone_id.in_([z.id for z, _ in rows])
            )
        )
    nearest = rows[0] if rows else None
    return AreaRiskOut(
        lat=lat,
        lng=lng,
        radius_km=radius_km,
        zone=ZoneOut.model_validate(nearest[0]) if nearest else None,
        distance_km=round(nearest[1], 2) if nearest else None,
        counts=counts,
        active_alerts=active or 0,
    )


@router.get("/map", response_model=MapViewOut)
def map_view(
    min_lat: float,
    min_lng: float,
    max_lat: float,
    max_lng: float,
    state: str | None = None,
    db: Session = Depends(get_db),
):
    """What the map should draw for the current viewport: every zone as a pin
    if few are in view, otherwise grid clusters (count + per-tier counts)."""
    in_view = [
        Zone.centroid_lat.between(min_lat, max_lat),
        Zone.centroid_lng.between(min_lng, max_lng),
    ]
    if state:
        in_view.append(Zone.state == state)

    # count(*), not count(id): `id` isn't in idx_zones_map, so count(id) forces a
    # trip to the table (with its large polygons) for every zone in view --
    # 6.4 s vs 0.17 s for the whole region. count(*) is answered from the index.
    total = db.query(func.count()).select_from(Zone).filter(*in_view).scalar()
    if total <= MAP_MAX_INDIVIDUAL_ZONES:
        zones = (
            db.query(Zone).options(MAP_COLUMNS).filter(*in_view)
            .order_by(Zone.susceptibility_score.desc().nulls_last(), Zone.id).all()
        )
        return MapViewOut(mode="zones", total=total, zones=[MapZoneOut.model_validate(z) for z in zones])

    cell = grid_cell_degrees(max(max_lat - min_lat, max_lng - min_lng))
    cell_y = func.floor(Zone.centroid_lat / cell)
    cell_x = func.floor(Zone.centroid_lng / cell)
    rows = db.execute(
        select(
            func.avg(Zone.centroid_lat), func.avg(Zone.centroid_lng), func.count(),
            func.count().filter(Zone.risk_tier == "high"),
            func.count().filter(Zone.risk_tier == "moderate"),
            func.count().filter(Zone.risk_tier == "low"),
            func.count().filter(Zone.risk_tier.is_(None)),
            func.min(Zone.centroid_lat), func.min(Zone.centroid_lng),
            func.max(Zone.centroid_lat), func.max(Zone.centroid_lng),
        )
        .where(*in_view)
        .group_by(cell_y, cell_x)
    ).all()
    clusters = [
        MapClusterOut(lat=r[0], lng=r[1], count=r[2], high=r[3], moderate=r[4], low=r[5], unscored=r[6],
                      bounds=[r[7], r[8], r[9], r[10]])
        for r in rows
    ]
    return MapViewOut(mode="clusters", total=total, clusters=clusters)


@router.get("/stats", response_model=ZoneStatsOut)
def zone_stats(state: str | None = None, db: Session = Depends(get_db)):
    """Counts over EVERY zone (a capped /zones page can't answer "how many
    high-risk zones are there") and the extent to fit the map to."""
    query = select(
        func.count(),
        func.count().filter(Zone.risk_tier == "high"),
        func.count().filter(Zone.risk_tier == "moderate"),
        func.count().filter(Zone.risk_tier == "low"),
        func.count().filter(Zone.risk_tier.is_(None)),
        func.min(Zone.centroid_lat), func.min(Zone.centroid_lng),
        func.max(Zone.centroid_lat), func.max(Zone.centroid_lng),
    )
    if state:
        query = query.where(Zone.state == state)
    total, high, moderate, low, unscored, min_lat, min_lng, max_lat, max_lng = db.execute(query).one()
    # Rounded outward to 4 decimals (~11 m): the database driver returns
    # coordinates rounded to 15 digits, so the exact min/max can land a hair
    # inside the zone that defines it and a bounding-box query with them
    # would drop that zone (3 of 33,303 did).
    pad = 1e4
    bounds = (
        [math.floor(min_lat * pad) / pad, math.floor(min_lng * pad) / pad,
         math.ceil(max_lat * pad) / pad, math.ceil(max_lng * pad) / pad]
        if total else None
    )
    return ZoneStatsOut(total=total, high=high, moderate=moderate, low=low, unscored=unscored, bounds=bounds)


# Which tiers count as "safer" than a zone of a given tier. An unscored zone
# is treated like the highest tier (only a real "low" counts as safer), so
# this never recommends fleeing toward an unassessed area.
SAFER_TIERS = {"high": ("moderate", "low"), "moderate": ("low",), "low": ()}


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    dlat, dlng = math.radians(lat2 - lat1), math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(a))


@router.get("/{zone_id}/nearest-safer", response_model=NearestSaferOut | None)
def nearest_safer_zone(zone_id: uuid.UUID, db: Session = Depends(get_db)):
    """The closest zone in the same state with a lower risk tier, found in
    SQL -- the dashboard used to download every zone of the state and scan
    them in the browser, which stops working at tens of thousands of zones.
    Null when there's nothing safer (the zone is already low risk, or no
    lower-tier zone exists in its state)."""
    zone = db.get(Zone, zone_id)
    if zone is None:
        raise HTTPException(status_code=404, detail="Zone not found")
    safer = SAFER_TIERS.get(zone.risk_tier, ("low",))
    if not safer:
        return None
    # Equirectangular distance is plenty to rank neighbours a few km apart;
    # the reported figure below is the real great-circle distance.
    dlat = Zone.centroid_lat - zone.centroid_lat
    dlng = (Zone.centroid_lng - zone.centroid_lng) * math.cos(math.radians(zone.centroid_lat))
    nearest = (
        db.query(Zone).options(ZONE_LIST_COLUMNS)
        .filter(Zone.state == zone.state, Zone.risk_tier.in_(safer), Zone.id != zone.id)
        .order_by(dlat * dlat + dlng * dlng)
        .first()
    )
    if nearest is None:
        return None
    return NearestSaferOut(
        **ZoneOut.model_validate(nearest).model_dump(),
        distance_km=_haversine_km(zone.centroid_lat, zone.centroid_lng, nearest.centroid_lat, nearest.centroid_lng),
    )


@router.get("/{zone_id}", response_model=ZoneOut)
def get_zone(zone_id: uuid.UUID, db: Session = Depends(get_db)):
    zone = db.get(Zone, zone_id)
    if zone is None:
        raise HTTPException(status_code=404, detail="Zone not found")
    return zone


@router.put("/{zone_id}/susceptibility", response_model=ZoneOut, dependencies=[Depends(require_officer_key)])
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
