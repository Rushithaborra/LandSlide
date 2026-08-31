from datetime import date

import httpx
from pydantic import BaseModel

from app.config import settings


class DailyRainfall(BaseModel):
    day: date
    intensity_mm: float


def fetch_daily_rainfall(lat: float, lng: float, past_days: int = 20, forecast_days: int = 1) -> list[DailyRainfall]:
    """Live call to Open-Meteo (free, no API key). Primary rainfall source for
    the prototype — the pitch deck names IMD as the real target source, too
    slow to get API access for in a 4-day build. Flag this as simulated data
    when demoing.

    Daily granularity (not hourly) to match the I-D threshold model in
    alert_engine.py, which is fit to daily rainfall data."""
    response = httpx.get(
        settings.open_meteo_base_url,
        params={
            "latitude": lat,
            "longitude": lng,
            "daily": "precipitation_sum",
            "past_days": past_days,
            "forecast_days": forecast_days,
            "timezone": "UTC",
        },
        timeout=10.0,
    )
    response.raise_for_status()
    data = response.json()["daily"]
    return [
        DailyRainfall(day=d, intensity_mm=mm)
        for d, mm in zip(data["time"], data["precipitation_sum"])
    ]
