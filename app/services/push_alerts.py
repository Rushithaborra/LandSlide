"""Opt-in browser notifications for Warning-level alerts.

A resident subscribes their own device (POST /subscriptions) to warnings near a point; when an
alert reaches WARNING -- its shortest crossing window is at most settings.warning_max_window_days
-- every active subscription whose radius covers the alert's zone is notified, at most once per
settings.push_cooldown_hours. A long-window-only alert (a dashboard "watch") never notifies:
those windows alert on nearly every monsoon day, which would teach people to ignore the app.

Best-effort by design, like SMS: a push failure can never undo an alert that is already committed.
"""
import json
import math
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

from pywebpush import WebPushException, webpush
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import AlertSubscription, Zone
from app.services.geo import KM_PER_DEGREE, distance_km

# The only hosts this server will ever POST a notification to. The endpoint comes from the
# public subscribe request, so accepting an arbitrary URL would let anyone aim this server at
# internal or third-party addresses (SSRF). These are the browsers' own push services.
PUSH_HOST_SUFFIXES = ("fcm.googleapis.com", "push.services.mozilla.com", "notify.windows.com", "push.apple.com")
MAX_RADIUS_KM = 10.0  # the largest radius a subscription may ask for (also bounds the area scan)

TEMPLATES = {
    "en": (
        "Landslide warning near {place}",
        "Rain near {place} is over the danger level for landslides. Stay away from unstable slopes and roads. "
        "Follow your local authority's guidance. In danger, call 112.",
    ),
    "hi": (
        "{place} के पास भूस्खलन चेतावनी",
        "{place} के पास बारिश भूस्खलन के ख़तरे के स्तर से ऊपर है। अस्थिर ढलानों और सड़कों से दूर रहें। "
        "अपने स्थानीय प्राधिकरण की सलाह मानें। ख़तरे में हों तो 112 पर कॉल करें।",
    ),
    "ne": (
        "{place} नजिक पहिरो चेतावनी",
        "{place} नजिक वर्षा पहिरोको खतरा स्तरभन्दा माथि छ। अस्थिर भिर र सडकबाट टाढा रहनुहोस्। "
        "आफ्नो स्थानीय निकायको सल्लाह मान्नुहोस्। खतरामा भए ११२ मा फोन गर्नुहोस्।",
    ),
}


def push_configured() -> bool:
    return bool(settings.vapid_public_key and settings.vapid_private_key)


def is_allowed_push_endpoint(endpoint: str) -> bool:
    parts = urlsplit(endpoint)
    host = (parts.hostname or "").lower()
    return (
        parts.scheme == "https"
        and parts.port in (None, 443)
        and parts.username is None
        and any(host == s or host.endswith("." + s) for s in PUSH_HOST_SUFFIXES)
    )


def is_warning(window_days: int | None) -> bool:
    """True for an alert whose shortest over-the-line window is short enough to warn people."""
    return window_days is not None and window_days <= settings.warning_max_window_days


def subscribers_near(db: Session, lat: float, lng: float, now: datetime | None = None) -> list[AlertSubscription]:
    """Active web-push subscriptions whose own radius covers (lat, lng) and that are not still in
    their cooldown. A box scan first (cheap, indexed), then the exact per-subscription radius."""
    now = now or datetime.now(timezone.utc)
    dlat = MAX_RADIUS_KM / KM_PER_DEGREE
    dlng = dlat / max(0.01, abs(math.cos(math.radians(lat))))
    cooldown = timedelta(hours=settings.push_cooldown_hours)
    rows = db.execute(
        select(AlertSubscription).where(
            AlertSubscription.channel == "webpush",
            AlertSubscription.lat.between(lat - dlat, lat + dlat),
            AlertSubscription.lng.between(lng - dlng, lng + dlng),
        )
    ).scalars().all()
    return [
        s for s in rows
        if distance_km(s.lat, s.lng, lat, lng) <= s.radius_km
        and (s.last_notified_at is None or now - s.last_notified_at >= cooldown)
    ]


def build_payload(subscription: AlertSubscription, zone_name: str, zone_id) -> str:
    title, body = TEMPLATES.get(subscription.language, TEMPLATES["en"])
    place = subscription.place_label or zone_name
    return json.dumps(
        {
            "title": title.format(place=place),
            "body": body.format(place=place),
            "url": f"{settings.dashboard_url.rstrip('/')}/zones/{zone_id}",
            "tag": f"warning-{zone_id}",  # a repeat for the same zone replaces, not stacks
        },
        ensure_ascii=False,
    )


def _send(subscription: AlertSubscription, payload: str) -> None:
    webpush(
        subscription_info={"endpoint": subscription.endpoint, "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth}},
        data=payload,
        vapid_private_key=settings.vapid_private_key,
        vapid_claims={"sub": settings.dashboard_url},
        ttl=6 * 3600,  # a landslide warning that is hours old is no longer news
        timeout=10,
    )


def notify_zone_warning(db: Session, zone_id) -> dict:
    """Notify every eligible subscriber near the zone with this id. A subscription the push
    service reports gone (404/410: the user revoked it or cleared the browser) is deleted.
    Takes the id, like every other engine hook, and loads the zone itself. Returns counts and
    never raises for a delivery problem."""
    if not push_configured():
        return {"skipped": True, "reason": "web push is not configured"}
    zone = db.get(Zone, zone_id)
    if zone is None:
        return {"skipped": True, "reason": "zone not found"}
    now = datetime.now(timezone.utc)
    sent = failed = removed = 0
    for sub in subscribers_near(db, zone.centroid_lat, zone.centroid_lng, now):
        try:
            _send(sub, build_payload(sub, zone.name, zone.id))
            sub.last_notified_at = now
            sent += 1
        except WebPushException as e:
            status = getattr(getattr(e, "response", None), "status_code", None)
            if status in (404, 410):
                db.delete(sub)
                removed += 1
            else:
                failed += 1
        except Exception:
            failed += 1
    db.commit()
    return {"sent": sent, "failed": failed, "removed": removed}
