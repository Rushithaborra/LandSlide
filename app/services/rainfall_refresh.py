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
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.config import get_rainfall_threshold
from app.models import Alert, RainfallReading, Zone
from app.services import open_meteo
from app.services.alert_engine import can_alert, check_and_trigger, drop_forecast_days, evaluate_daily_rainfall, has_cleared

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
    states = [s for (s,) in db.execute(select(Zone.state).distinct()).all() if get_rainfall_threshold(s) is not None]
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
        if r.id not in have and can_alert(r.state) and get_rainfall_threshold(r.state) is not None
    )
    return targets


def _active_alert_zone_ids(db: Session, zone_ids: list[uuid.UUID]) -> set[uuid.UUID]:
    if not zone_ids:
        return set()
    rows = db.execute(select(Alert.zone_id).where(Alert.status == "active", Alert.zone_id.in_(zone_ids)).distinct()).all()
    return {zone_id for (zone_id,) in rows}


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


def refresh_rainfall(db: Session, per_state: int, run_alerts: bool = True) -> dict:
    """Refresh the selected zones and (unless run_alerts is False) fire alerts
    for the ones whose fresh rainfall crosses their threshold. Returns a
    summary for the caller (and the scheduler's log)."""
    started = time.monotonic()
    zones = select_zones(db, per_state)
    fetched = _fetch_all(zones)

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
    if run_alerts:
        alerting = [z for z in zones if z.id in daily_by_zone and can_alert(z.state)]
        has_active_alert = _active_alert_zone_ids(db, [z.id for z in alerting])
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
        "alerting_states": sorted({z.state for z in zones if can_alert(z.state)}),
        "states": per_state_refreshed,
        "errors": errors[:5],
        "duration_seconds": round(time.monotonic() - started, 1),
    }
