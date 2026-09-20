"""Dynamic-layer alert trigger: rainfall intensity-duration (I-D) threshold,
combined with the static ML susceptibility tier. Deliberately rule-based, not
ML — the "two layers, named separately" pitch point (docs/landslide_ews_pitch.pptx,
slide 4). The I-D threshold is loaded per-state from config
(app.config.get_rainfall_threshold) — see .env.example for its source/citation.
Nothing here invents a threshold number.

NER expansion, phase 1: each state gets its own literature-sourced threshold
(they're geologically different regions) instead of one global config, so
the pure functions below now take `config` as a required argument rather
than silently defaulting to a single global -- there's no longer one
sensible default across states.

Split into a pure decision core (no DB, directly unit-testable) and a thin
DB-touching wrapper, so the rule logic can be verified without Postgres.
"""
import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.config import RainfallThresholdConfig, get_rainfall_threshold, settings
from app.models import Alert, RainfallReading

# How susceptibility tier scales the rainfall threshold: a high-susceptibility
# zone should alert at a *lower* rainfall bar than a low-susceptibility one.
# This is our own explainable rule for combining the two layers per the
# deck's "Risk Engine" step — it is NOT a literature-sourced number, unlike
# the I-D threshold itself. Keep it that way in any explanation to judges.
SUSCEPTIBILITY_MULTIPLIERS = {
    "high": 0.8,
    "moderate": 1.0,
    "low": 1.25,
}


def intensity_duration_threshold(
    duration_days: int,
    config: RainfallThresholdConfig,
    risk_tier: str = "moderate",
) -> float:
    """Threshold mean rainfall intensity (mm/day) for a duration window,
    scaled by susceptibility tier."""
    if duration_days <= 0:
        raise ValueError(f"duration_days must be positive, got {duration_days}")
    if risk_tier not in SUSCEPTIBILITY_MULTIPLIERS:
        raise ValueError(f"risk_tier must be one of {list(SUSCEPTIBILITY_MULTIPLIERS)}, got {risk_tier!r}")

    base = config.coefficient * (duration_days**config.exponent)
    return base * SUSCEPTIBILITY_MULTIPLIERS[risk_tier]


@dataclass
class ThresholdCrossing:
    duration_days: int
    observed_mean_intensity_mm_per_day: float
    threshold_mm_per_day: float
    risk_tier: str


def _validate_rainfall(daily_totals: dict[date, float]) -> None:
    for day, mm in daily_totals.items():
        if mm is None or not isinstance(mm, (int, float)) or math.isnan(mm) or math.isinf(mm):
            raise ValueError(f"invalid rainfall value for {day}: {mm!r}")
        if mm < 0:
            raise ValueError(f"rainfall cannot be negative ({day}: {mm}mm)")


def evaluate_daily_rainfall(
    daily_totals: dict[date, float],
    config: RainfallThresholdConfig,
    risk_tier: str = "moderate",
    durations_days: list[int] | None = None,
) -> ThresholdCrossing | None:
    """Pure function: given {date: rainfall_mm}, check each duration window
    ending on the latest date for an I-D threshold crossing, scaled by
    susceptibility tier. Returns the shortest-duration crossing found (the
    most urgent signal), or None.

    Raises ValueError on invalid rainfall input (negative, NaN, non-finite)
    rather than silently treating bad data as "no rain"."""
    _validate_rainfall(daily_totals)

    if not daily_totals:
        return None

    durations_days = durations_days or config.durations_days
    latest = max(daily_totals)

    for duration in sorted(durations_days):
        window_start = latest - timedelta(days=duration - 1)
        window_dates = [d for d in daily_totals if window_start <= d <= latest]
        if len(window_dates) < duration:
            continue  # incomplete window — not enough data to evaluate this duration yet

        cumulative = sum(daily_totals[d] for d in window_dates)
        mean_intensity = cumulative / duration
        threshold = intensity_duration_threshold(duration, risk_tier=risk_tier, config=config)

        if mean_intensity >= threshold:
            return ThresholdCrossing(duration, mean_intensity, threshold, risk_tier)

    return None


def strongest_ratio(
    daily_totals: dict[date, float],
    config: RainfallThresholdConfig,
    risk_tier: str = "moderate",
    max_duration_days: int | None = None,
) -> float | None:
    """Pure: how far above its danger level the rain is, as the highest
    (mean rainfall / threshold) over every complete duration window ending on the
    latest day -- 1.0 is exactly at the level, 2.0 is twice it. Unlike
    evaluate_daily_rainfall (which returns the SHORTEST window that crosses) this
    takes the maximum, so the same measure can be compared over time: a storm
    that moves from a 5-day to a 3-day crossing must not look like an improvement.
    `max_duration_days` (default RAINFALL_ESCALATION_MAX_WINDOW_DAYS) leaves out
    the long windows, which barely react to a new burst.
    None when no window is complete (not enough data to say)."""
    _validate_rainfall(daily_totals)
    if not daily_totals:
        return None
    if max_duration_days is None:
        max_duration_days = settings.rainfall_escalation_max_window_days
    latest = max(daily_totals)
    best = None
    for duration in sorted(d for d in config.durations_days if d <= max_duration_days):
        window_start = latest - timedelta(days=duration - 1)
        window = [d for d in daily_totals if window_start <= d <= latest]
        if len(window) < duration:
            continue
        mean_intensity = sum(daily_totals[d] for d in window) / duration
        ratio = mean_intensity / intensity_duration_threshold(duration, risk_tier=risk_tier, config=config)
        best = ratio if best is None else max(best, ratio)
    return best


def has_worsened(baseline_ratio: float, current_ratio: float, step: float | None = None) -> bool:
    """Pure: is the rain at least `step` (default RAINFALL_ESCALATION_STEP) danger
    levels further above the level than it was when the alert was last raised or
    updated?"""
    step = settings.rainfall_escalation_step if step is None else step
    return current_ratio >= baseline_ratio + step


def drop_forecast_days(daily_totals: dict[date, float]) -> dict[date, float]:
    """Real-alert evaluation must never anchor on a day that hasn't happened
    yet: `open_meteo.fetch_daily_rainfall` pulls forecast_days alongside
    past_days (see app/routers/rainfall.py), and both get stored as plain
    RainfallReading rows with no distinction -- so `evaluate_daily_rainfall`'s
    `latest = max(daily_totals)` would otherwise anchor its backward-looking
    windows on tomorrow's *predicted* rainfall. With Twilio now live, that
    would mean a real SMS/call could fire off an unconfirmed forecast. Pure
    and separately testable from the DB-touching check_and_trigger below."""
    today = datetime.now(timezone.utc).date()
    return {d: mm for d, mm in daily_totals.items() if d <= today}


def has_cleared(
    daily_totals: dict[date, float],
    config: RainfallThresholdConfig,
    risk_tier: str = "moderate",
    clear_days: int | None = None,
) -> bool:
    """Pure: has this zone's rainfall stayed BELOW its threshold, in every
    duration window, on each of the last `clear_days` days? Only then may an
    active alert close itself.

    Deliberately conservative -- it answers False (keep the alert) unless it
    can positively show the rain has cleared:
    - the data must reach today (stale data can't say "all clear");
    - each day checked needs a full longest window of history behind it, so a
      day Open-Meteo returned no value for makes an incomplete window, and
      evaluate_daily_rainfall would otherwise read "not enough data" as "no
      crossing" and wrongly close a live alert;
    - several days in a row (default 2), so a lull mid-storm doesn't close it.
    Forecast days are ignored, as everywhere in alert evaluation."""
    clear_days = settings.rainfall_alert_clear_days if clear_days is None else clear_days
    totals = drop_forecast_days(daily_totals)
    if not totals or clear_days < 1:
        return False
    latest = max(totals)
    if latest < datetime.now(timezone.utc).date():
        return False
    needed_history = max(config.durations_days)
    for days_back in range(clear_days):
        as_of = latest - timedelta(days=days_back)
        window = {d: mm for d, mm in totals.items() if d <= as_of}
        if len(window) < needed_history:
            return False
        if evaluate_daily_rainfall(window, config=config, risk_tier=risk_tier) is not None:
            return False
    return True


def can_alert(state: str) -> bool:
    """Whether this state's rainfall threshold is trusted to fire alerts (see
    Settings.rainfall_alert_states). A state can have a threshold for display
    and data refresh without being on this list."""
    return state.lower() in {s.lower() for s in settings.rainfall_alert_states}


def check_and_trigger(db: Session, zone_id) -> Alert | None:
    """DB-touching wrapper: pulls this zone's stored daily rainfall and its
    susceptibility tier, runs it through the pure threshold check, and writes
    an Alert row if crossed."""
    from app.models import Zone  # local import avoids a circular import with models.py

    zone = db.get(Zone, zone_id)
    if zone is None:
        raise ValueError(f"zone {zone_id} not found")
    risk_tier = zone.risk_tier or "moderate"  # no ML score yet -> assume moderate, don't silently skip alerting

    if not can_alert(zone.state):
        print(f"[ALERT] zone={zone_id} state={zone.state!r} is not on the alerting list -- skipping")
        return None

    config = get_rainfall_threshold(zone.state)
    if config is None:
        # Honest gap, not a bug: this zone's state has no literature-sourced
        # threshold configured yet (e.g. Mizoram, pending a citable I-D
        # equation) -- skip alerting rather than borrow another state's
        # geologically-unrelated number.
        print(f"[ALERT] zone={zone_id} state={zone.state!r} has no configured rainfall threshold -- skipping")
        return None

    readings = (
        db.query(RainfallReading)
        .filter(RainfallReading.zone_id == zone_id)
        .order_by(RainfallReading.timestamp.desc())
        .limit(31)
        .all()
    )
    daily_totals = drop_forecast_days({r.timestamp.date(): r.intensity_mm for r in readings})

    crossing = evaluate_daily_rainfall(daily_totals, config=config, risk_tier=risk_tier)
    if crossing is None:
        return None

    existing = db.query(Alert).filter(Alert.zone_id == zone_id, Alert.status == "active").first()
    if existing:
        return None

    alert = Alert(
        zone_id=zone_id,
        threshold_crossed=(
            f"{crossing.risk_tier.capitalize()} landslide-risk zone — {crossing.duration_days}d rainfall averaged"
            f" {crossing.observed_mean_intensity_mm_per_day:.1f}mm/day, exceeding the"
            f" {crossing.threshold_mm_per_day:.1f}mm/day danger threshold for this susceptibility level"
        ),
        status="active",
        delivery_method="log_only",
        peak_ratio=strongest_ratio(daily_totals, config, risk_tier),  # baseline for "rain worsened" updates
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)

    # Real SMS to citizen subscribers (app/services/sms_alerts.py), using this
    # zone's risk_tier as severity -- the automated engine never produces
    # "critical" (that only exists in the operator-driven Broadcast composer,
    # see app/routers/alerts.py:broadcast_alert). Wrapped so a Twilio failure
    # or missing credentials can never roll back the alert already committed
    # above -- SMS delivery is best-effort on top of a real alert, not a
    # precondition for one.
    try:
        from app.services.sms_alerts import trigger_zone_alert

        sms_result = trigger_zone_alert(db, zone_id, zone.name, risk_tier)
        if not sms_result.get("skipped") and sms_result.get("sent", 0) > 0:
            alert.delivery_method = "sms_twilio"
            db.commit()
            db.refresh(alert)
        print(f"[ALERT] zone={zone_id} {alert.threshold_crossed} — {sms_result}")
    except Exception as e:
        print(f"[ALERT] zone={zone_id} {alert.threshold_crossed} — logged (SMS send failed: {e})")

    return alert


def worsened_message(zone_name: str, severity: str) -> str:
    return (
        f"RESQ ALERT UPDATE: rain has got worse near {zone_name}. "
        f"{severity.upper()} landslide risk continues. "
        f"Stay away from unstable slopes and roads. Follow local authority guidance."
    )


def escalate_if_worsened(
    db: Session,
    alert: Alert,
    zone,
    daily_totals: dict[date, float],
    config: RainfallThresholdConfig,
    risk_tier: str,
    now: datetime | None = None,
) -> bool:
    """An alert stays active while the rain keeps crossing its threshold, so a
    later, much heavier burst used to be invisible on it (and no one was told).
    If the rain is now at least RAINFALL_ESCALATION_STEP danger levels above where
    it was when the alert was last raised/updated, record that on the alert
    (worsened_at, worsened_count, a new baseline) and re-text the zone's
    subscribers. Returns True if it did.

    Guards, all deliberate: forecast days never count; an alert with no baseline
    (raised before this feature) is just measured from now on, silently, so a
    deploy can't blast everyone at once; at most one update per
    RAINFALL_ESCALATION_MIN_HOURS per alert (the baseline is NOT moved while
    waiting, so a real worsening is caught on the next refresh after the gap); an
    SMS failure can never undo the recorded update."""
    ratio = strongest_ratio(drop_forecast_days(daily_totals), config, risk_tier)
    if ratio is None:
        return False
    if alert.peak_ratio is None:
        alert.peak_ratio = ratio
        db.commit()
        return False
    if not has_worsened(alert.peak_ratio, ratio):
        return False
    now = now or datetime.now(timezone.utc)
    if alert.worsened_at is not None and now - alert.worsened_at < timedelta(hours=settings.rainfall_escalation_min_hours):
        return False

    alert.peak_ratio = ratio
    alert.worsened_at = now
    alert.worsened_count = (alert.worsened_count or 0) + 1
    db.commit()

    try:
        from app.services.sms_alerts import trigger_zone_alert

        result = trigger_zone_alert(db, zone.id, zone.name, risk_tier, message=worsened_message(zone.name, risk_tier))
        if not result.get("skipped") and result.get("sent", 0) > 0 and alert.delivery_method != "sms_twilio":
            alert.delivery_method = "sms_twilio"
            db.commit()
        print(f"[ALERT] zone={zone.id} rain worsened to {ratio:.2f}x the danger level -- {result}")
    except Exception as e:
        print(f"[ALERT] zone={zone.id} rain worsened to {ratio:.2f}x the danger level -- recorded (SMS failed: {e})")
    return True
