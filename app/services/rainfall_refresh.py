"""Scheduled rainfall refresh: keep stored rainfall current and let the alert
engine run on its own, without anyone opening the dashboard.

Until now rainfall was fetched (and alerts evaluated) only when something hit
POST /rainfall/{zone_id}/fetch -- i.e. when someone loaded the dashboard. This
refreshes the highest-risk zones of every state that HAS a rainfall threshold
(a zone in a state without one can't alert, so fetching it is wasted budget on
the free Open-Meteo tier), then runs the alert check only for zones whose fresh
data actually crosses their threshold.

Cheap on purpose (a request to a sleepy free-tier host must finish quickly):
zones are fetched a chunk per Open-Meteo request (50 single calls took ~33 s,
2 chunked requests ~2 s), all zones' readings are written in one batch, and
the threshold test is done in memory from the fetched data (the 20-day fetch
covers the longest alert window), so the database is touched a handful of
times, not once per zone.

It also closes alerts whose rain has cleared (alert_engine.has_cleared) -- without
that, an alert stayed active forever, since the dashboard has no resolve button
and a zone with an active alert is never alerted again.
"""
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.config import get_rainfall_threshold
from app.config import settings
from app.models import Alert, JobRun, RainfallReading, Zone
from app.services import open_meteo
from app.services.alert_engine import (
    can_alert,
    check_and_trigger,
    drop_forecast_days,
    escalate_if_worsened,
    evaluate_daily_rainfall,
    has_cleared,
)

FETCH_CHUNK_SIZE = 25  # locations per Open-Meteo request
MAX_FETCH_WORKERS = 3  # chunks fetched in parallel; well under Open-Meteo's per-minute limit


@dataclass
class ZoneTarget:
    id: uuid.UUID
    state: str
    risk_tier: str | None
    lat: float
    lng: float


def store_readings(db: Session, daily_by_zone: dict[uuid.UUID, list[open_meteo.DailyRainfall]]) -> list[RainfallReading]:
    """Writes fetched daily rainfall, replacing what those zones already have
    for the same days.

    Idempotent by (zone_id, day): Open-Meteo's `past_days` window covers the
    same recent days on every call, so a naive insert would add duplicate rows
    every time this runs. Deleting the zones' rows inside the fetched window
    first makes a call mean "refresh what's there", not "append forever". One
    commit for all zones."""
    all_days = {d.day for daily in daily_by_zone.values() for d in daily}
    if not all_days:
        return []
    day_start = datetime.combine(min(all_days), datetime.min.time(), tzinfo=timezone.utc)
    day_end = datetime.combine(max(all_days), datetime.min.time(), tzinfo=timezone.utc)
    db.query(RainfallReading).filter(
        RainfallReading.zone_id.in_(list(daily_by_zone)),
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
        for zone_id, daily in daily_by_zone.items()
        for d in daily
    ]
    db.add_all(readings)
    db.commit()
    return readings


def select_zones(db: Session, per_state: int) -> list[ZoneTarget]:
    """The `per_state` highest-susceptibility zones of each state that has a
    configured rainfall threshold -- the same "watch the most dangerous
    corridors first" priority the dashboard's rainfall card already uses --
    plus every zone in an alerting state that currently has an active alert,
    wherever it ranks: otherwise an alert on a zone outside the top few would
    never be re-checked, and could never clear."""
    states = [s for (s,) in db.execute(select(Zone.state).distinct()).all()]
    targets: list[ZoneTarget] = []
    for state in sorted(states):
        rows = db.execute(
            select(Zone.id, Zone.state, Zone.risk_tier, Zone.centroid_lat, Zone.centroid_lng)
            .where(Zone.state == state)
            .order_by(Zone.susceptibility_score.desc().nulls_last(), Zone.id)
            .limit(per_state)
        ).all()
        targets.extend(ZoneTarget(*r) for r in rows)

    have = {t.id for t in targets}
    with_alerts = db.execute(
        select(Zone.id, Zone.state, Zone.risk_tier, Zone.centroid_lat, Zone.centroid_lng)
        .join(Alert, Alert.zone_id == Zone.id)
        .where(Alert.status == "active")
        .distinct()
    ).all()
    targets.extend(
        ZoneTarget(*r)
        for r in with_alerts
        if r.id not in have and can_alert(r.state)
    )
    return targets


def _active_alerts_by_zone(db: Session, zone_ids: list[uuid.UUID]) -> dict[uuid.UUID, Alert]:
    """The active alert of each given zone (a zone has at most one), one query."""
    if not zone_ids:
        return {}
    alerts = db.execute(select(Alert).where(Alert.status == "active", Alert.zone_id.in_(zone_ids))).scalars().all()
    return {a.zone_id: a for a in alerts}


def resolve_cleared_alerts(db: Session, zone_ids: list[uuid.UUID]) -> int:
    """Marks these zones' active alerts resolved by the system. Returns how many."""
    if not zone_ids:
        return 0
    result = db.execute(
        update(Alert)
        .where(Alert.zone_id.in_(zone_ids), Alert.status == "active")
        .values(status="resolved", resolved_at=datetime.now(timezone.utc), resolved_by="system")
    )
    db.commit()
    return result.rowcount


def _fetch_all(zones: list[ZoneTarget]) -> list[list[open_meteo.DailyRainfall] | Exception]:
    """Rainfall for every zone, in order, one request per chunk of zones (a
    few chunks in parallel). A failed chunk marks just its own zones as failed
    -- one bad response must not sink the whole run."""
    chunks = [zones[i:i + FETCH_CHUNK_SIZE] for i in range(0, len(zones), FETCH_CHUNK_SIZE)]

    def fetch_chunk(chunk: list[ZoneTarget]) -> list[list[open_meteo.DailyRainfall] | Exception]:
        try:
            return open_meteo.fetch_daily_rainfall_batch([(z.lat, z.lng) for z in chunk])
        except Exception as e:
            return [e] * len(chunk)

    with ThreadPoolExecutor(max_workers=MAX_FETCH_WORKERS) as pool:
        return [result for chunk_results in pool.map(fetch_chunk, chunks) for result in chunk_results]


REFRESH_JOB = "rainfall_refresh"  # job_runs row: when a refresh last completed
LEASE_JOB = "rainfall_refresh_lease"  # job_runs row: a refresh is running (or crashed) since...
LEASE_MINUTES = 3  # a run takes ~10 s; a crashed run stops blocking others after this


def is_stale(last_run_at: datetime | None, max_age_minutes: int, now: datetime | None = None) -> bool:
    """True when there has never been a refresh, or the last one is at least
    `max_age_minutes` old."""
    if last_run_at is None:
        return True
    return (now or datetime.now(timezone.utc)) - last_run_at >= timedelta(minutes=max_age_minutes)


def refresh_status(db: Session, max_age_minutes: int) -> dict:
    """When rainfall was last refreshed, for the dashboard's 'updated 12 min ago'
    and for the staleness gate."""
    row = db.get(JobRun, REFRESH_JOB)
    last = row.last_run_at if row else None
    now = datetime.now(timezone.utc)
    return {
        "last_refresh_at": last,
        "age_minutes": None if last is None else int((now - last).total_seconds() // 60),
        "max_age_minutes": max_age_minutes,
        "stale": is_stale(last, max_age_minutes, now),
    }


def _claim_lease(db: Session) -> bool:
    """Atomically take the right to run a refresh. Two visitors opening the
    dashboard at the same moment must not both fetch and write: exactly one
    claim succeeds, the other is told a refresh is already running. It is one
    INSERT ... ON CONFLICT DO UPDATE ... WHERE (the row is expired), so it works
    through any connection pooler -- a Postgres advisory lock does not -- and a
    run that crashed cannot block the next one for longer than LEASE_MINUTES."""
    now = func.now()
    stmt = (
        pg_insert(JobRun)
        .values(name=LEASE_JOB, last_run_at=now)
        .on_conflict_do_update(
            index_elements=[JobRun.name],
            set_={"last_run_at": now},
            where=JobRun.last_run_at < now - timedelta(minutes=LEASE_MINUTES),
        )
        .returning(JobRun.name)
    )
    claimed = db.execute(stmt).first() is not None
    db.commit()
    return claimed


def _release_lease(db: Session) -> None:
    db.execute(update(JobRun).where(JobRun.name == LEASE_JOB).values(last_run_at=datetime(2000, 1, 1, tzinfo=timezone.utc)))
    db.commit()


def record_refresh(db: Session, summary: dict) -> None:
    now = datetime.now(timezone.utc)
    stmt = pg_insert(JobRun).values(name=REFRESH_JOB, last_run_at=now, summary=summary)
    db.execute(stmt.on_conflict_do_update(index_elements=[JobRun.name], set_={"last_run_at": now, "summary": summary}))
    db.commit()


def refresh_if_stale(db: Session, max_age_minutes: int, per_state: int, run_alerts: bool = True) -> dict:
    """The dashboard-driven refresh: does nothing if rainfall is fresh, otherwise
    refreshes it (and alerts). Safe to call from anywhere, any number of times:
    the freshness check makes repeats free, the lease keeps concurrent callers
    from doubling up, and nothing here takes input that could change WHAT is
    fetched or alerted -- a caller can only make it run at the earliest moment
    it was going to be due anyway."""
    status = refresh_status(db, max_age_minutes)
    if not status["stale"]:
        return {"status": "fresh", "age_minutes": status["age_minutes"]}
    if not _claim_lease(db):
        return {"status": "in_progress"}
    try:
        summary = refresh_rainfall(db, per_state, run_alerts)
    except Exception:
        _release_lease(db)
        raise
    # First failure reason (zone id stripped) so a run that fetched nothing says why.
    errors = summary.get("errors")
    first_error = errors[0].split(": ", 1)[-1][:200] if errors else None
    if summary["zones_refreshed"] > 0:
        record_refresh(db, {k: summary[k] for k in ("zones_refreshed", "zones_failed", "alerts_created", "alerts_resolved", "states")})
        _release_lease(db)
    # else: a run that fetched nothing must not look fresh, and its lease is
    # deliberately kept until it expires (LEASE_MINUTES), so a provider outage or
    # rate limit means one retry every few minutes -- not one per dashboard visitor.
    return {"status": "refreshed", "first_error": first_error, **summary}


def refresh_rainfall(db: Session, per_state: int, run_alerts: bool = True) -> dict:
    """Refresh the selected zones and (unless run_alerts is False) fire alerts
    for the ones whose fresh rainfall crosses their threshold. Returns a
    summary for the caller (and the scheduler's log)."""
    started = time.monotonic()
    zones = select_zones(db, per_state)
    return _store_and_evaluate(db, zones, _fetch_all(zones), run_alerts, started)


def ingest_rainfall(
    db: Session, per_state: int, supplied: dict[uuid.UUID, list[open_meteo.DailyRainfall]], run_alerts: bool = True
) -> dict:
    """Same as refresh_rainfall, but the rainfall was fetched by the CALLER (the
    GitHub Actions runner -- Open-Meteo rate-limits the shared IPs of free hosts
    like Render, so the fetch happens elsewhere). The caller only supplies the
    numbers: which zones are eligible is decided here, exactly as for a normal
    refresh, and data for any other zone id is ignored -- so a caller can't
    write rainfall for arbitrary zones or make the engine alert on them."""
    started = time.monotonic()
    zones = select_zones(db, per_state)
    fetched = [supplied.get(z.id, []) for z in zones]
    return _store_and_evaluate(db, zones, fetched, run_alerts, started)


def _store_and_evaluate(
    db: Session,
    zones: list[ZoneTarget],
    fetched: list[list[open_meteo.DailyRainfall] | Exception],
    run_alerts: bool,
    started: float,
) -> dict:
    daily_by_zone: dict[uuid.UUID, list[open_meteo.DailyRainfall]] = {}
    errors: list[str] = []
    per_state_refreshed: dict[str, int] = {}
    for zone, result in zip(zones, fetched):
        if isinstance(result, Exception) or not result:
            errors.append(f"{zone.id}: {result if isinstance(result, Exception) else 'no data returned'}")
            continue
        daily_by_zone[zone.id] = result
        per_state_refreshed[zone.state] = per_state_refreshed.get(zone.state, 0) + 1

    if daily_by_zone:
        store_readings(db, daily_by_zone)

    alerts_created = 0
    alerts_resolved = 0
    alerts_worsened = 0
    if run_alerts:
        alerting = [z for z in zones if z.id in daily_by_zone and can_alert(z.state)]
        active_alerts = _active_alerts_by_zone(db, [z.id for z in alerting])
        has_active_alert = set(active_alerts)
        to_resolve: list[uuid.UUID] = []
        for zone in alerting:
            totals = {d.day: d.intensity_mm for d in daily_by_zone[zone.id]}
            config = get_rainfall_threshold(zone.state)
            tier = zone.risk_tier or "moderate"
            try:
                crossing = evaluate_daily_rainfall(drop_forecast_days(totals), config=config, risk_tier=tier)
                if crossing is not None:
                    # Only zones that really cross reach the alert engine, which
                    # re-checks from the stored data and skips a zone that already
                    # has an active alert (so no duplicate alerts or SMS).
                    if check_and_trigger(db, zone.id) is not None:
                        alerts_created += 1
                    elif zone.id in active_alerts and escalate_if_worsened(
                        db, active_alerts[zone.id], zone, totals, config, tier
                    ):
                        alerts_worsened += 1  # already alerting, and the rain is now clearly worse
                elif zone.id in has_active_alert and has_cleared(totals, config, tier):
                    to_resolve.append(zone.id)
            except Exception as e:
                errors.append(f"{zone.id}: alert check failed: {e}")
        alerts_resolved = resolve_cleared_alerts(db, to_resolve)

    return {
        "zones_selected": len(zones),
        "zones_refreshed": len(daily_by_zone),
        "zones_failed": len(zones) - len(daily_by_zone),
        "alerts_enabled": run_alerts,
        "alerts_created": alerts_created,
        "alerts_resolved": alerts_resolved,
        "alerts_worsened": alerts_worsened,
        "alerting_states": sorted({z.state for z in zones if can_alert(z.state)}),
        "states": per_state_refreshed,
        "errors": errors[:5],
        "duration_seconds": round(time.monotonic() - started, 1),
    }
