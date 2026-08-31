"""Dynamic-layer alert trigger: rainfall intensity-duration (I-D) threshold,
combined with the static ML susceptibility tier. Deliberately rule-based, not
ML — the "two layers, named separately" pitch point (docs/landslide_ews_pitch.pptx,
slide 4). The I-D threshold itself is loaded from config (app.config.settings
.rainfall_threshold) — see .env.example for its source/citation. Nothing here
invents a threshold number.

Split into a pure decision core (no DB, directly unit-testable) and a thin
DB-touching wrapper, so the rule logic can be verified without Postgres.
"""
import math
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.config import RainfallThresholdConfig, settings
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
    risk_tier: str = "moderate",
    config: RainfallThresholdConfig | None = None,
) -> float:
    """Threshold mean rainfall intensity (mm/day) for a duration window,
    scaled by susceptibility tier."""
    if duration_days <= 0:
        raise ValueError(f"duration_days must be positive, got {duration_days}")
    if risk_tier not in SUSCEPTIBILITY_MULTIPLIERS:
        raise ValueError(f"risk_tier must be one of {list(SUSCEPTIBILITY_MULTIPLIERS)}, got {risk_tier!r}")

    config = config or settings.rainfall_threshold
    base = config.coefficient * (duration_days**config.exponent)
    return base * SUSCEPTIBILITY_MULTIPLIERS[risk_tier]


@dataclass
class ThresholdCrossing:
    duration_days: int
    observed_mean_intensity_mm_per_day: float
    threshold_mm_per_day: float
    risk_tier: str


def evaluate_daily_rainfall(
    daily_totals: dict[date, float],
    risk_tier: str = "moderate",
    durations_days: list[int] | None = None,
    config: RainfallThresholdConfig | None = None,
) -> ThresholdCrossing | None:
    """Pure function: given {date: rainfall_mm}, check each duration window
    ending on the latest date for an I-D threshold crossing, scaled by
    susceptibility tier. Returns the shortest-duration crossing found (the
    most urgent signal), or None.

    Raises ValueError on invalid rainfall input (negative, NaN, non-finite)
    rather than silently treating bad data as "no rain"."""
    for day, mm in daily_totals.items():
        if mm is None or not isinstance(mm, (int, float)) or math.isnan(mm) or math.isinf(mm):
            raise ValueError(f"invalid rainfall value for {day}: {mm!r}")
        if mm < 0:
            raise ValueError(f"rainfall cannot be negative ({day}: {mm}mm)")

    if not daily_totals:
        return None

    config = config or settings.rainfall_threshold
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


def check_and_trigger(db: Session, zone_id) -> Alert | None:
    """DB-touching wrapper: pulls this zone's stored daily rainfall and its
    susceptibility tier, runs it through the pure threshold check, and writes
    an Alert row if crossed."""
    from app.models import Zone  # local import avoids a circular import with models.py

    zone = db.get(Zone, zone_id)
    if zone is None:
        raise ValueError(f"zone {zone_id} not found")
    risk_tier = zone.risk_tier or "moderate"  # no ML score yet -> assume moderate, don't silently skip alerting

    readings = (
        db.query(RainfallReading)
        .filter(RainfallReading.zone_id == zone_id)
        .order_by(RainfallReading.timestamp.desc())
        .limit(31)
        .all()
    )
    daily_totals = {r.timestamp.date(): r.intensity_mm for r in readings}

    crossing = evaluate_daily_rainfall(daily_totals, risk_tier=risk_tier)
    if crossing is None:
        return None

    existing = db.query(Alert).filter(Alert.zone_id == zone_id, Alert.status == "active").first()
    if existing:
        return None

    alert = Alert(
        zone_id=zone_id,
        threshold_crossed=(
            f"{crossing.duration_days}d mean {crossing.observed_mean_intensity_mm_per_day:.1f}mm/day"
            f" >= {crossing.risk_tier} threshold {crossing.threshold_mm_per_day:.1f}mm/day"
        ),
        status="active",
        delivery_method="log_only",
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    print(f"[ALERT] zone={zone_id} {alert.threshold_crossed} — logged (SMS not wired up)")
    return alert
