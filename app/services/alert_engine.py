"""Dynamic-layer alert trigger: rule-based rainfall intensity threshold.

Deliberately NOT ML — this is the "two layers, named separately" pitch point.
The threshold in app.config is a placeholder; swap it for the team's cited
intensity-duration threshold before the demo, and say so if asked.
"""
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Alert, RainfallReading


def check_and_trigger(db: Session, zone_id, intensity_mm: float) -> Alert | None:
    if intensity_mm < settings.rainfall_alert_threshold_mm_per_hour:
        return None

    existing = (
        db.query(Alert)
        .filter(Alert.zone_id == zone_id, Alert.status == "active")
        .first()
    )
    if existing:
        return None

    alert = Alert(
        zone_id=zone_id,
        threshold_crossed=f"rainfall_intensity>{settings.rainfall_alert_threshold_mm_per_hour}mm/hr",
        status="active",
        delivery_method="log_only",
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    print(f"[ALERT] zone={zone_id} intensity={intensity_mm}mm/hr threshold crossed — logged (SMS not wired up)")
    return alert
