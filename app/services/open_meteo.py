from datetime import date

import httpx
from pydantic import BaseModel

from app.config import settings


class DailyRainfall(BaseModel):
    day: date
    intensity_mm: float


def fetch_daily_rainfall_batch(
    points: list[tuple[float, float]], past_days: int = 20, forecast_days: int = 3
) -> list[list[DailyRainfall]]:
    """One Open-Meteo request for many (lat, lng) points -- the API takes
    comma-separated coordinates -- returning one daily series per point, in
    order. Fetching ~50 zones this way took ~a few seconds; 50 separate calls
    took ~33 s (each ~2 s, and parallel calls didn't help much), too slow for
    a request to a free-tier host.

    A day Open-Meteo has no value for (null) is skipped rather than failing
    the whole series: the alert engine already treats an incomplete window as
    "not enough data yet". An empty `points` makes no request."""
    if not points:
        return []
    response = httpx.get(
        settings.open_meteo_base_url,
        params={
            "latitude": ",".join(str(lat) for lat, _ in points),
            "longitude": ",".join(str(lng) for _, lng in points),
            "daily": "precipitation_sum",
            "past_days": past_days,
            "forecast_days": forecast_days,
            "timezone": "UTC",
        },
        timeout=25.0,
    )
    response.raise_for_status()
    payload = response.json()
    # A single point comes back as one object, several as a list of them.
    locations = [payload] if isinstance(payload, dict) else payload
    if len(locations) != len(points):
        raise ValueError(f"Open-Meteo returned {len(locations)} locations for {len(points)} points")
    return [
        [
            DailyRainfall(day=d, intensity_mm=mm)
            for d, mm in zip(loc["daily"]["time"], loc["daily"]["precipitation_sum"])
            if mm is not None
        ]
        for loc in locations
    ]


def fetch_daily_rainfall(lat: float, lng: float, past_days: int = 20, forecast_days: int = 3) -> list[DailyRainfall]:
    """Live call to Open-Meteo (free, no API key). Primary rainfall source for
    the prototype — the pitch deck names IMD as the real target source, too
    slow to get API access for in a 4-day build. Flag this as simulated data
    when demoing.

    Daily granularity (not hourly) to match the I-D threshold model in
    alert_engine.py, which is fit to daily rainfall data.

    forecast_days=3 per Open-Meteo's own semantics means "today + the next 2
    days" (forecast_days=1 would be today only, not tomorrow — verified
    directly against the API). PS26001 explicitly asks for a dashboard
    "weather forecast", not just history; the 2 genuinely-future days this
    now returns are what RainfallReadingOut.is_forecast (app/schemas.py) and
    alert_engine.drop_forecast_days() are for — shown distinctly on the
    chart, and always excluded from real alert evaluation."""
    return fetch_daily_rainfall_batch([(lat, lng)], past_days, forecast_days)[0]
