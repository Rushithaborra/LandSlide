from datetime import datetime

import httpx
from pydantic import BaseModel

from app.config import settings


class HourlyRainfall(BaseModel):
    timestamp: datetime
    intensity_mm: float


def fetch_hourly_rainfall(lat: float, lng: float, forecast_days: int = 1) -> list[HourlyRainfall]:
    """Live call to Open-Meteo (free, no API key). Primary rainfall source for the
    prototype — the pitch deck names IMD as the real target source, too slow to
    get API access for in a 4-day build. Flag this as simulated data when demoing."""
    response = httpx.get(
        settings.open_meteo_base_url,
        params={
            "latitude": lat,
            "longitude": lng,
            "hourly": "precipitation",
            "forecast_days": forecast_days,
            "timezone": "UTC",
        },
        timeout=10.0,
    )
    response.raise_for_status()
    data = response.json()["hourly"]
    return [
        HourlyRainfall(timestamp=ts, intensity_mm=mm)
        for ts, mm in zip(data["time"], data["precipitation"])
    ]
