import uuid
from datetime import date, datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator


class ZoneOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    state: str
    susceptibility_score: float | None
    risk_tier: str | None
    model_version: str | None
    last_updated: datetime
    # Centroid of the stored polygon -- for map pins, not the full geometry.
    centroid_lat: float
    centroid_lng: float


class NearestSaferOut(ZoneOut):
    """GET /zones/{id}/nearest-safer -- the closest zone in the same state
    with a lower risk tier. Great-circle distance from centroid to centroid,
    not a road route (the dashboard hands real routing off to Google Maps)."""

    distance_km: float


class AreaRiskOut(BaseModel):
    """GET /zones/near -- what we can honestly say about a place. The model
    scores ROAD-CORRIDOR segments, not arbitrary points, so this reports the
    nearest assessed segment and how far away it is; `zone` is null when there
    is none within the radius (the place is outside what was assessed)."""

    lat: float
    lng: float
    radius_km: float
    zone: ZoneOut | None
    distance_km: float | None
    # Assessed segments within the radius, by risk tier -- the nearest one alone
    # can mislead when a high-risk stretch is just past it.
    counts: dict[str, int]
    active_alerts: int  # active rainfall alerts on segments within the radius


class MapZoneOut(BaseModel):
    """One zone as a map pin -- only what a marker + tooltip need."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    state: str
    susceptibility_score: float | None
    risk_tier: str | None
    centroid_lat: float
    centroid_lng: float


class MapClusterOut(BaseModel):
    """A grid cell of zones for a zoomed-out map. `bounds` (min_lat, min_lng,
    max_lat, max_lng of the member zones) lets the dashboard zoom straight
    into the cell when it's clicked."""

    lat: float
    lng: float
    count: int
    high: int
    moderate: int
    low: int
    unscored: int
    bounds: list[float]


class MapViewOut(BaseModel):
    """GET /zones/map: individual zones when few enough are in view, grid
    clusters otherwise -- so the payload stays small no matter how many
    zones the database holds."""

    mode: Literal["zones", "clusters"]
    total: int
    zones: list[MapZoneOut] = []
    clusters: list[MapClusterOut] = []


class ZoneStatsOut(BaseModel):
    """GET /zones/stats -- real counts over every zone (not a capped page)
    plus the extent of the zones, for the Overview cards and initial map fit."""

    total: int
    high: int
    moderate: int
    low: int
    unscored: int
    bounds: list[float] | None  # min_lat, min_lng, max_lat, max_lng; None if no zones


class CorridorOut(BaseModel):
    """Zones grouped by their real highway/road code (GET /corridors) --
    not a stored table, computed from existing zones + alerts."""

    code: str
    zone_count: int
    active_alert_count: int
    worst_risk_tier: str | None
    worst_zone_name: str
    worst_susceptibility_score: float | None


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

    @computed_field
    @property
    def is_forecast(self) -> bool:
        """True for a reading dated after today -- open_meteo.fetch_daily_rainfall
        pulls forecast_days alongside past_days, and the two are otherwise
        indistinguishable once stored. Computed from the date itself (not a
        stored flag) so a reading correctly stops being "forecast" the moment
        its day actually arrives, with no backfill needed."""
        return self.timestamp.astimezone(timezone.utc).date() > datetime.now(timezone.utc).date()


class RainfallRefreshOut(BaseModel):
    """Summary of one scheduled/manual POST /rainfall/refresh run."""

    zones_selected: int
    zones_refreshed: int
    zones_failed: int
    alerts_enabled: bool
    alerts_created: int
    alerts_resolved: int  # active alerts closed because the rainfall cleared
    alerts_worsened: int = 0  # active alerts updated because the rain got clearly worse
    alerting_states: list[str]  # refreshed states whose thresholds are trusted to alert
    states: dict[str, int]  # zones refreshed per state
    errors: list[str]  # first few failures, for the scheduler's log
    duration_seconds: float


class RainfallStatusOut(BaseModel):
    """GET /rainfall/status -- how fresh the stored rainfall is."""

    last_refresh_at: datetime | None
    age_minutes: int | None
    max_age_minutes: int
    stale: bool
    # States whose rainfall alerts are switched on. A state outside this list is
    # refreshed for display but never alerts, so the dashboard must not present
    # its "0 alerts" as if it meant "no danger".
    alerting_states: list[str] = []


class RainfallRefreshIfStaleOut(BaseModel):
    """POST /rainfall/refresh-if-stale: 'fresh' (nothing to do), 'in_progress'
    (someone else is refreshing right now) or 'refreshed' (with the summary)."""

    status: Literal["fresh", "in_progress", "refreshed"]
    age_minutes: int | None = None
    zones_refreshed: int | None = None
    zones_failed: int | None = None
    alerts_created: int | None = None
    alerts_resolved: int | None = None
    alerts_worsened: int | None = None
    duration_seconds: float | None = None
    first_error: str | None = None  # why zones failed, if any did


class RainfallTargetOut(BaseModel):
    """One zone a rainfall fetcher should get data for (GET /rainfall/targets)."""

    id: uuid.UUID
    lat: float
    lng: float


class RainfallDayIn(BaseModel):
    day: date
    mm: float = Field(ge=0, le=2000, description="daily precipitation total, mm")


class RainfallZoneIn(BaseModel):
    zone_id: uuid.UUID
    days: list[RainfallDayIn] = Field(max_length=40)


class RainfallIngestIn(BaseModel):
    """POST /rainfall/ingest body: daily rainfall the caller fetched from Open-Meteo."""

    readings: list[RainfallZoneIn] = Field(max_length=500)


class RainfallThresholdOut(BaseModel):
    """The real, config-driven 1-day I-D threshold for one zone -- what the
    dashboard's rainfall chart should draw its reference line against,
    instead of an invented flat number. 1-day specifically because the
    chart plots daily mm bars; the real engine also checks longer duration
    windows (3/5/7/10/15/20 days), which a single flat line can't represent
    -- this is the closest single, honest number to that per-day view, not
    a claim that it's the only threshold that matters."""

    threshold_mm_per_day: float
    risk_tier: str
    source: str
    verified_against_primary_text: bool


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    zone_id: uuid.UUID
    zone_name: str
    risk_tier: str | None
    triggered_at: datetime
    threshold_crossed: str
    status: str
    delivery_method: str
    resolved_at: datetime | None = None
    resolved_by: str | None = None  # 'officer' | 'system' (rainfall cleared)
    # An alert's text is a snapshot from the moment it was raised and never
    # changes; these are the zone's most recent OBSERVED daily rainfall, so the
    # dashboard can show what the rain is doing now next to it.
    latest_rainfall_mm: float | None = None
    latest_rainfall_date: date | None = None
    # "Rain worsened" updates: when the rain last got clearly worse while this alert
    # stayed active, how often, and how far above the danger level it peaked at
    # that point (1.0 = exactly at the level).
    worsened_at: datetime | None = None
    worsened_count: int = 0
    peak_ratio: float | None = None


class GenerateBulletinIn(BaseModel):
    severity: Literal["moderate", "high", "critical"]


class GenerateBulletinOut(BaseModel):
    headline: str
    message: str


class BroadcastIn(BaseModel):
    headline: str = Field(min_length=1)
    severity: Literal["moderate", "high", "critical"]
    message: str = Field(min_length=1)
    channels: list[Literal["sms", "push", "siren", "cap_gateway"]] = Field(min_length=1)


class BroadcastOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    alert_id: uuid.UUID
    headline: str
    severity: str
    message: str
    channels: list[str]
    status: str
    dispatched_at: datetime


class AuthorityContactIn(BaseModel):
    name: str = Field(min_length=1)
    role: str | None = None
    phone_number: str = Field(min_length=1)


class AuthorityContactOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    role: str | None
    phone_number: str
    added_at: datetime


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
    # Optional: GPS is unreliable in the mountainous, poor-signal terrain this
    # app targets, so the frontend lets a reporter submit a place name alone
    # when GPS fails. See the model_validator below -- at least one of the
    # two is still required.
    coords: Coords | None = None
    place_name: str | None = Field(default=None, alias="placeName")
    description: str = Field(min_length=5)
    reporter_name: str | None = Field(default=None, alias="reporterName")
    reporter_phone: str | None = Field(default=None, alias="reporterPhone")
    captured_at: datetime = Field(alias="capturedAt")
    # Not part of the documented frontend payload today -- optional, for
    # offline-queue-safe retries (see reports.py: dedupes on this if sent).
    client_report_id: uuid.UUID | None = None
    zone_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def require_coords_or_place_name(self) -> "CitizenReportIn":
        if self.coords is None and not (self.place_name and self.place_name.strip()):
            raise ValueError("either coords or placeName is required")
        return self


class PolishDescriptionIn(BaseModel):
    description: str = Field(min_length=5)


class PolishDescriptionOut(BaseModel):
    polished: str


class CitizenReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    client_report_id: uuid.UUID | None
    zone_id: uuid.UUID | None
    report_type: str
    severity: str
    geo_lat: float | None
    geo_lng: float | None
    geo_accuracy_m: float | None
    place_name: str | None
    description: str
    reporter_name: str | None
    reporter_phone: str | None
    photo_url: str | None
    triage_summary: str | None
    description_translated: str | None
    captured_at: datetime
    submitted_at: datetime
    verified_status: str
