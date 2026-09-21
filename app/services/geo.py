import math

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Zone

KM_PER_DEGREE = 111.32


def state_at(db: Session, lat: float, lng: float, radius_km: float = 25.0) -> str | None:
    """The state of the nearest assessed zone within `radius_km` of a point, or None.

    Zones are road corridors across the region, so a report from anywhere the
    system covers has one nearby. None (no zone that close) means "cannot tell",
    which is honest: a point in another country or a state we have not loaded is
    not guessed into one of ours."""
    dlat = radius_km / KM_PER_DEGREE
    dlng = radius_km / (KM_PER_DEGREE * max(math.cos(math.radians(lat)), 0.01))
    dist_km = func.sqrt(
        func.power((Zone.centroid_lat - lat) * KM_PER_DEGREE, 2)
        + func.power((Zone.centroid_lng - lng) * KM_PER_DEGREE * math.cos(math.radians(lat)), 2)
    )
    return db.execute(
        select(Zone.state)
        .where(Zone.centroid_lat.between(lat - dlat, lat + dlat), Zone.centroid_lng.between(lng - dlng, lng + dlng), dist_km <= radius_km)
        .order_by(dist_km)
        .limit(1)
    ).scalar()


# OpenStreetMap's Nominatim, restricted to the north-east (left, top, right, bottom). One
# short request per report that gave only a place name -- well within its usage policy.
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
NER_VIEWBOX = "88.0,29.6,97.5,21.9"
NOMINATIM_HEADERS = {"User-Agent": "landslide-ews-research/1.0 (SIH prototype; github.com/Rushithaborra/LandSlide)"}


def state_from_place_name(db: Session, place_name: str, timeout: float = 4.0) -> str | None:
    """A state for a report that gave only a place name (no coordinates): geocode the
    name inside the north-east, work out each match's state, and accept it only if ALL
    matches agree. An ambiguous name (matches in two states), an unknown one, or any
    failure gives None -- a report is never put under a state on a guess, and a slow
    or failed lookup must never delay or fail the report itself."""
    name = (place_name or "").strip()
    if len(name) < 2:
        return None
    try:
        resp = httpx.get(
            NOMINATIM_URL,
            params={"q": name, "format": "jsonv2", "countrycodes": "in", "viewbox": NER_VIEWBOX, "bounded": "1", "limit": "3"},
            headers=NOMINATIM_HEADERS,
            timeout=timeout,
        )
        resp.raise_for_status()
        matches = resp.json()
    except (httpx.HTTPError, ValueError):
        return None
    states = {state_at(db, float(m["lat"]), float(m["lon"])) for m in matches}
    return states.pop() if len(states) == 1 and None not in states else None
