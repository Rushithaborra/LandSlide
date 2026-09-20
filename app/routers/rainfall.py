import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.config import get_rainfall_threshold, settings
from app.database import get_db
from app.models import RainfallReading, Zone
from app.schemas import (
    RainfallIngestIn,
    RainfallReadingOut,
    RainfallRefreshIfStaleOut,
    RainfallRefreshOut,
    RainfallStatusOut,
    RainfallTargetOut,
    RainfallThresholdOut,
)
from app.security import require_officer_key
from app.services import open_meteo
from app.services.alert_engine import can_alert, check_and_trigger, intensity_duration_threshold
from app.services.rainfall_refresh import (
    ingest_rainfall,
    record_refresh,
    refresh_if_stale,
    refresh_rainfall,
    refresh_status,
    select_zones,
    store_readings,
)

router = APIRouter(prefix="/rainfall", tags=["rainfall"])


@router.post("/refresh", response_model=RainfallRefreshOut, dependencies=[Depends(require_officer_key)])
def refresh_all(
    per_state: int | None = Query(None, ge=1, le=100, description="zones per state (default: RAINFALL_REFRESH_ZONES_PER_STATE)"),
    alerts: bool = Query(True, description="false = store rainfall only, don't trigger alerts/SMS"),
    db: Session = Depends(get_db),
):
    """What the scheduler calls (see .github/workflows/rainfall-refresh.yml):
    refreshes the highest-risk zones of every state that has a rainfall
    threshold, then fires alerts (and SMS, if Twilio is set up) for any whose
    fresh rainfall crosses it. `alerts=false` is a dry run for the data only."""
    out = refresh_rainfall(db, per_state or settings.rainfall_refresh_zones_per_state, run_alerts=alerts)
    _record_if_full_run(db, out, per_state, alerts)
    return out


def _record_if_full_run(db: Session, out: dict, per_state: int | None, alerts: bool) -> None:
    # Only a full-size run that also checked alerts counts as "refreshed" for the
    # staleness gate; a data-only or tiny test run must not make the system look fresh.
    if per_state is None and alerts and out["zones_refreshed"] > 0:
        record_refresh(db, {k: out[k] for k in ("zones_refreshed", "zones_failed", "alerts_created", "alerts_resolved", "states")})


@router.get("/targets", response_model=list[RainfallTargetOut], dependencies=[Depends(require_officer_key)])
def refresh_targets(db: Session = Depends(get_db)):
    """The zones a rainfall fetcher should get data for -- the same selection a
    normal refresh uses. Step 1 of the GitHub Actions flow (see /ingest)."""
    return [
        RainfallTargetOut(id=z.id, lat=z.lat, lng=z.lng)
        for z in select_zones(db, settings.rainfall_refresh_zones_per_state)
    ]


@router.post("/ingest", response_model=RainfallRefreshOut, dependencies=[Depends(require_officer_key)])
def ingest(
    payload: RainfallIngestIn,
    alerts: bool = Query(True, description="false = store rainfall only, don't trigger alerts/SMS"),
    db: Session = Depends(get_db),
):
    """Step 2 of the GitHub Actions flow: the runner fetched daily rainfall from
    Open-Meteo (the backend's own fetch gets 429-throttled on Render's shared
    IPs) and posts it here. Stored and alert-checked exactly like /refresh; data
    for zones outside the /targets selection is ignored."""
    supplied = {
        r.zone_id: [open_meteo.DailyRainfall(day=d.day, intensity_mm=d.mm) for d in r.days] for r in payload.readings
    }
    out = ingest_rainfall(db, settings.rainfall_refresh_zones_per_state, supplied, run_alerts=alerts)
    _record_if_full_run(db, out, None, alerts)
    return out


@router.get("/status", response_model=RainfallStatusOut)
def rainfall_status(db: Session = Depends(get_db)):
    """When rainfall was last refreshed (the dashboard shows 'updated 12 min ago')."""
    return {**refresh_status(db, settings.rainfall_refresh_max_age_minutes), "alerting_states": settings.rainfall_alert_states}


@router.post("/refresh-if-stale", response_model=RainfallRefreshIfStaleOut)
def refresh_if_stale_endpoint(db: Session = Depends(get_db)):
    """Public on purpose: the dashboard calls this when it opens, so rainfall
    stays current for anyone looking at it (a judge, an officer) without
    depending on a scheduler. Safe to expose: it takes no input, does nothing
    while the data is fresh (RAINFALL_REFRESH_MAX_AGE_MINUTES, default 60), only
    one refresh runs at a time, and what it fetches and alerts on is fixed by
    configuration -- a caller can only make it run when it was due anyway."""
    return refresh_if_stale(db, settings.rainfall_refresh_max_age_minutes, settings.rainfall_refresh_zones_per_state)


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

    readings = store_readings(db, {zone_id: daily})
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
    # Also null for a state that has a threshold configured but isn't trusted to
    # alert (see Settings.rainfall_alert_states): the chart's "danger" line must
    # not show a number the system doesn't stand behind.
    if config is None or not can_alert(zone.state):
        return None

    risk_tier = zone.risk_tier or "moderate"
    return RainfallThresholdOut(
        threshold_mm_per_day=intensity_duration_threshold(1, config, risk_tier),
        risk_tier=risk_tier,
        source=config.source,
        verified_against_primary_text=config.verified_against_primary_text,
    )
