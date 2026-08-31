import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ZoneOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    susceptibility_score: float | None
    risk_tier: str | None
    model_version: str | None
    last_updated: datetime


class SusceptibilityUpdate(BaseModel):
    """ML -> backend contract for PUT /zones/{id}/susceptibility. Written by
    the ML lead's pipeline; backend only stores/serves these values, never
    computes them."""

    susceptibility_score: float = Field(ge=0, le=1, description="Model output, 0-1 probability-like score")
    risk_tier: Literal["low", "moderate", "high"]
    model_version: str = Field(min_length=1, description="e.g. 'rf-v1' or a git commit hash of the training run")


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
