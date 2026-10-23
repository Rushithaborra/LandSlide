import secrets

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import AlertSubscription
from app.schemas import SubscribeIn, SubscribeOut, SubscriptionConfigOut, UnsubscribeIn
from app.services.push_alerts import MAX_RADIUS_KM, is_allowed_push_endpoint, push_configured

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])

# Public endpoint, so the table cannot be allowed to grow without limit. A real deployment would
# raise this; it is far above anything this prototype will see.
MAX_SUBSCRIPTIONS = 5000
DEFAULT_RADIUS_KM = 3.0


@router.get("/config", response_model=SubscriptionConfigOut)
def subscription_config():
    """Public: whether browser notifications are switched on, and the key the browser needs."""
    enabled = push_configured()
    return SubscriptionConfigOut(
        enabled=enabled,
        public_key=settings.vapid_public_key if enabled else None,
        warning_window_days=settings.warning_max_window_days,
        default_radius_km=DEFAULT_RADIUS_KM,
        max_radius_km=MAX_RADIUS_KM,
    )


@router.post("", response_model=SubscribeOut)
def subscribe(payload: SubscribeIn, db: Session = Depends(get_db)):
    """Opt a browser in to Warning-level alerts near a point. Public by design -- a resident
    subscribes their own device -- so what it accepts is tightly bounded: only the browsers' own
    push services as the endpoint (this server will POST to it), a box around the north-east, a
    radius cap, and a ceiling on the table's size. Subscribing the same endpoint again updates it."""
    if not push_configured():
        raise HTTPException(status_code=503, detail="Notifications are not switched on yet")
    if not is_allowed_push_endpoint(payload.endpoint):
        raise HTTPException(status_code=422, detail="Not a browser push endpoint")

    sub = db.scalar(select(AlertSubscription).where(AlertSubscription.endpoint == payload.endpoint))
    if sub is None:
        if db.scalar(select(func.count()).select_from(AlertSubscription)) >= MAX_SUBSCRIPTIONS:
            raise HTTPException(status_code=503, detail="Subscriptions are full right now")
        sub = AlertSubscription(channel="webpush", endpoint=payload.endpoint, unsubscribe_token=secrets.token_urlsafe(32))
        db.add(sub)
    sub.p256dh, sub.auth = payload.keys.p256dh, payload.keys.auth
    sub.lat, sub.lng, sub.radius_km = payload.lat, payload.lng, payload.radius_km
    sub.place_label, sub.language = payload.place_label, payload.language
    db.commit()
    db.refresh(sub)
    return SubscribeOut(id=sub.id, unsubscribe_token=sub.unsubscribe_token, radius_km=sub.radius_km)


@router.post("/unsubscribe", status_code=204)
def unsubscribe(payload: UnsubscribeIn, db: Session = Depends(get_db)):
    """Delete the subscription this token belongs to. Always 204, whether or not it existed: the
    answer must not reveal which tokens are real. POST with a body, not DELETE with the token in
    the URL, so the credential never lands in an access log."""
    sub = db.scalar(select(AlertSubscription).where(AlertSubscription.unsubscribe_token == payload.unsubscribe_token))
    if sub is not None:
        db.delete(sub)
        db.commit()
    return Response(status_code=204)
