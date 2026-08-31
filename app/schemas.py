import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ZoneOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    susceptibility_score: float | None
    risk_tier: str | None
    last_updated: datetime


class SusceptibilityUpdate(BaseModel):
    """Written by the ML lead's pipeline. Backend only stores/serves this value."""

    susceptibility_score: float
    risk_tier: str


class RainfallReadingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    zone_id: uuid.UUID
    timestamp: datetime
    intensity_mm: float
    source: str


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    zone_id: uuid.UUID
    triggered_at: datetime
    threshold_crossed: str
    status: str
    delivery_method: str


class CitizenReportIn(BaseModel):
    zone_id: uuid.UUID | None = None
    photo_url: str | None = None
    geo_lat: float
    geo_lng: float
    description: str | None = None


class CitizenReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    zone_id: uuid.UUID | None
    submitted_at: datetime
    photo_url: str | None
    geo_lat: float
    geo_lng: float
    description: str | None
    verified_status: str
