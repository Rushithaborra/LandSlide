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


class Coords(BaseModel):
    lat: float
    lng: float
    accuracy: float | None = None


class CitizenReportIn(BaseModel):
    """Matches the reporting frontend's payload shape exactly (field names
    and casing) via aliases -- no rename needed on their end. Sent as the
    `data` form field (a JSON string) alongside an optional `photo` file in
    a multipart/form-data POST; see app/routers/reports.py."""

    model_config = ConfigDict(populate_by_name=True)

    report_type: Literal["crack", "movement", "road", "other"] = Field(alias="reportType")
    severity: Literal["low", "moderate", "high", "critical"]
    coords: Coords
    place_name: str | None = Field(default=None, alias="placeName")
    description: str = Field(min_length=5)
    reporter_name: str | None = Field(default=None, alias="reporterName")
    reporter_phone: str | None = Field(default=None, alias="reporterPhone")
    captured_at: datetime = Field(alias="capturedAt")
    # Not part of the documented frontend payload today -- optional, for
    # offline-queue-safe retries (see reports.py: dedupes on this if sent).
    client_report_id: uuid.UUID | None = None
    zone_id: uuid.UUID | None = None


class CitizenReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    client_report_id: uuid.UUID | None
    zone_id: uuid.UUID | None
    report_type: str
    severity: str
    geo_lat: float
    geo_lng: float
    geo_accuracy_m: float | None
    place_name: str | None
    description: str
    reporter_name: str | None
    reporter_phone: str | None
    photo_url: str | None
    captured_at: datetime
    submitted_at: datetime
    verified_status: str
