import uuid
from datetime import date, datetime, timezone

from geoalchemy2 import Geometry
from sqlalchemy import CheckConstraint, Date, DateTime, Float, ForeignKey, Integer, SmallInteger, String
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Zone(Base):
    __tablename__ = "zones"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False)
    geometry = mapped_column(Geometry(geometry_type="POLYGON", srid=4326), nullable=False)
    susceptibility_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_tier: Mapped[str | None] = mapped_column(String, nullable=True)
    model_version: Mapped[str | None] = mapped_column(String, nullable=True)
    # onupdate: PUT /zones/{id}/susceptibility re-scores an existing row, and
    # without this last_updated kept its original insert time forever, so
    # /zones reported a stale date for a zone whose score had just changed.
    last_updated: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)
    # NER expansion, phase 1 (migrations/004_zone_state.sql), widened to all
    # 8 real NER states in migrations/008_ner_all_states.sql so a future
    # state's real zones don't need another schema migration to land. Sikkim
    # is the only state with real populated zones so far -- every other
    # value is real and valid but has zero rows until that state's own data
    # pipeline runs (see scripts/ml/ml_config.py's STATE_CONFIGS).
    state: Mapped[str] = mapped_column(String, default="Sikkim")

    __table_args__ = (
        CheckConstraint("risk_tier IN ('low','moderate','high')"),
        CheckConstraint("susceptibility_score IS NULL OR (susceptibility_score >= 0 AND susceptibility_score <= 1)"),
        CheckConstraint(
            "state IN ('Sikkim','Assam','Arunachal Pradesh','Manipur','Meghalaya','Mizoram','Nagaland','Tripura')"
        ),
    )

    rainfall_readings: Mapped[list["RainfallReading"]] = relationship(back_populates="zone")
    alerts: Mapped[list["Alert"]] = relationship(back_populates="zone")

    # Stored, not computed (migrations/009_zone_centroid_columns.sql): this
    # used to be a per-request Shapely centroid() call on every zone in every
    # GET /zones response -- fine at Sikkim's 3,921 zones, but a real,
    # demonstrated cause of GET /zones timing out completely once Assam's
    # 66,677 zones landed. Computed once at zone-creation time instead (see
    # scripts/integrate_zone_predictions.py, scripts/seed_zone.py). NOT NULL
    # (migrations/010_zone_centroid_not_null.sql) because ZoneOut requires
    # both as plain floats -- a zone inserted without one would otherwise
    # 500 every GET /zones response containing it, not just fail loudly at
    # insert time.
    centroid_lat: Mapped[float] = mapped_column(Float, nullable=False)
    centroid_lng: Mapped[float] = mapped_column(Float, nullable=False)


class RainfallReading(Base):
    __tablename__ = "rainfall_readings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    zone_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("zones.id", ondelete="CASCADE"))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    intensity_mm: Mapped[float] = mapped_column(Float, nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    __table_args__ = (CheckConstraint("source IN ('open-meteo','imd')"),)

    zone: Mapped[Zone] = relationship(back_populates="rainfall_readings")


class JobRun(Base):
    """When a background job last completed (migrations/013_job_runs.sql) -- the
    rainfall refresh uses it to decide whether the data is stale."""

    __tablename__ = "job_runs"

    name: Mapped[str] = mapped_column(String, primary_key=True)
    last_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    zone_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("zones.id", ondelete="CASCADE"))
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    threshold_crossed: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, default="active")
    delivery_method: Mapped[str] = mapped_column(String, nullable=False)
    # Set when status becomes 'resolved' (migrations/012_alert_resolution.sql):
    # 'officer' via the resolve endpoint, 'system' when the rainfall cleared.
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by: Mapped[str | None] = mapped_column(String, nullable=True)
    # "Rain worsened" tracking (migrations/014_alert_worsening.sql): mean rainfall /
    # danger level (1.0 = exactly at the level) when the alert was last raised or
    # updated, and when/how often it was updated because the rain got clearly worse.
    peak_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    worsened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    worsened_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)

    __table_args__ = (
        CheckConstraint("status IN ('active','resolved')"),
        CheckConstraint("resolved_by IS NULL OR resolved_by IN ('officer','system')", name="alerts_resolved_by_check"),
        CheckConstraint("delivery_method IN ('sms_mock','sms_twilio','log_only')"),
    )

    zone: Mapped[Zone] = relationship(back_populates="alerts")

    # Convenience read-through so AlertOut can expose these without the API
    # consumer having to separately fetch /zones and join by zone_id -- an
    # alert should say which zone and how landslide-susceptible it is on its
    # own, not just the rainfall number that triggered it.
    @property
    def zone_name(self) -> str:
        return self.zone.name

    @property
    def risk_tier(self) -> str | None:
        return self.zone.risk_tier


class Place(Base):
    """A village/town or an emergency service from OpenStreetMap (migrations/
    015_places.sql). A dated snapshot, incomplete by nature -- see the migration."""

    __tablename__ = "places"

    osm_id: Mapped[str] = mapped_column(String, primary_key=True)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lng: Mapped[float] = mapped_column(Float, nullable=False)
    phone: Mapped[str | None] = mapped_column(String, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class LandslideRecord(Base):
    """A real historical landslide from a Geological Survey of India inventory
    (migrations/017_landslide_records.sql). Place, coordinates and activity status only:
    the inventories almost never carry a date or severity, so none is stored."""

    __tablename__ = "landslide_records"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slide_no: Mapped[str | None] = mapped_column(String, nullable=True)
    state: Mapped[str] = mapped_column(String, nullable=False)
    district: Mapped[str | None] = mapped_column(String, nullable=True)
    slide_name: Mapped[str | None] = mapped_column(String, nullable=True)
    location: Mapped[str | None] = mapped_column(String, nullable=True)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lng: Mapped[float] = mapped_column(Float, nullable=False)
    activity: Mapped[str] = mapped_column(String, nullable=False, default="Unknown")
    material: Mapped[str | None] = mapped_column(String, nullable=True)
    movement: Mapped[str | None] = mapped_column(String, nullable=True)
    history_note: Mapped[str | None] = mapped_column(String, nullable=True)
    source: Mapped[str] = mapped_column(String, nullable=False, default="Geological Survey of India landslide inventory")


class ImdWarning(Base):
    """One district's IMD warning for one of the next five days, from a pushed snapshot
    (migrations/018_imd_warnings.sql). Replaced wholesale on every push."""

    __tablename__ = "imd_warnings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    state: Mapped[str] = mapped_column(String, nullable=False)
    district: Mapped[str] = mapped_column(String, nullable=False)
    obj_id: Mapped[str] = mapped_column(String, nullable=False)
    day: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    valid_date: Mapped[date] = mapped_column(Date, nullable=False)
    codes: Mapped[str] = mapped_column(String, nullable=False)
    color: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class AlertBroadcast(Base):
    __tablename__ = "alert_broadcasts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    alert_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("alerts.id", ondelete="CASCADE"))
    headline: Mapped[str] = mapped_column(String, nullable=False)
    severity: Mapped[str] = mapped_column(String, nullable=False)
    message: Mapped[str] = mapped_column(String, nullable=False)
    channels: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False)
    status: Mapped[str] = mapped_column(String, default="simulated")
    dispatched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    __table_args__ = (
        CheckConstraint("severity IN ('moderate','high','critical')"),
        CheckConstraint("status IN ('simulated','sent')"),
    )


class SmsAlertLog(Base):
    """Tracks every real SMS/call alert send, so app.services.sms_alerts can
    enforce a per-zone cooldown and avoid spamming the same people every time
    the rainfall check reruns. 'sms' (citizens) and 'call' (authorities) are
    tracked as separate channels with independent cooldowns."""

    __tablename__ = "sms_alert_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    zone_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("zones.id", ondelete="CASCADE"))
    severity: Mapped[str] = mapped_column(String, nullable=False)
    recipient_count: Mapped[int] = mapped_column(nullable=False)
    channel: Mapped[str] = mapped_column(String, default="sms")
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    __table_args__ = (CheckConstraint("channel IN ('sms', 'call')"),)


class AuthorityContact(Base):
    """Hand-registered officials who get a real phone call on critical
    broadcasts. Deliberately separate from citizen_reports.reporter_phone --
    officials need to be properly added, not scraped from reports."""

    __tablename__ = "authority_contacts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str | None] = mapped_column(String, nullable=True)
    phone_number: Mapped[str] = mapped_column(String, nullable=False)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    # migrations/016: the state this official covers; NULL = all states (national /
    # NER-wide). A critical broadcast rings the alert's own state's contacts plus these.
    state: Mapped[str | None] = mapped_column(String, nullable=True)


class CitizenReport(Base):
    __tablename__ = "citizen_reports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_report_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), unique=True, nullable=True)
    zone_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("zones.id", ondelete="SET NULL"), nullable=True
    )
    report_type: Mapped[str] = mapped_column(String, nullable=False)
    severity: Mapped[str] = mapped_column(String, nullable=False)
    geo_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    geo_lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    geo_accuracy_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    place_name: Mapped[str | None] = mapped_column(String, nullable=True)
    # migrations/016: worked out at submission (zone, else the nearest assessed zone to the
    # coordinates); NULL = could not be worked out -- shown under "All States" only.
    state: Mapped[str | None] = mapped_column(String, nullable=True)
    description: Mapped[str] = mapped_column(String, nullable=False)
    reporter_name: Mapped[str | None] = mapped_column(String, nullable=True)
    reporter_phone: Mapped[str | None] = mapped_column(String, nullable=True)
    photo_url: Mapped[str | None] = mapped_column(String, nullable=True)
    # AI-generated, one-line triage priority (see app/services/triage_summary.py)
    # -- condenses the free-text `description` above for a fast dashboard scan.
    # Null until generated (best-effort at submission time; never blocks it).
    triage_summary: Mapped[str | None] = mapped_column(String, nullable=True)
    # AI-translated English rendering of `description` above (see
    # app/services/translation.py) -- the citizen's original text is never
    # altered; this is shown alongside it for an officer who doesn't read
    # the language it was written in. Null until generated (best-effort at
    # submission time; never blocks it).
    description_translated: Mapped[str | None] = mapped_column(String, nullable=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    verified_status: Mapped[str] = mapped_column(String, default="unverified")

    __table_args__ = (
        CheckConstraint("report_type IN ('crack','movement','road','other')"),
        CheckConstraint("severity IN ('low','moderate','high','critical')"),
        CheckConstraint("verified_status IN ('unverified','verified','rejected')"),
    )
