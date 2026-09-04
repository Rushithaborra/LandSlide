import uuid
from datetime import datetime, timezone

from geoalchemy2 import Geometry
from geoalchemy2.shape import to_shape
from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
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
    last_updated: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    __table_args__ = (
        CheckConstraint("risk_tier IN ('low','moderate','high')"),
        CheckConstraint("susceptibility_score IS NULL OR (susceptibility_score >= 0 AND susceptibility_score <= 1)"),
    )

    rainfall_readings: Mapped[list["RainfallReading"]] = relationship(back_populates="zone")
    alerts: Mapped[list["Alert"]] = relationship(back_populates="zone")

    # Computed, not stored: the dashboard's map needs a single point per zone
    # to place a pin, but the stored geometry is a full polygon. Centroid is
    # good enough for a pin location -- no new column needed.
    @property
    def centroid_lat(self) -> float:
        return to_shape(self.geometry).centroid.y

    @property
    def centroid_lng(self) -> float:
        return to_shape(self.geometry).centroid.x


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


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    zone_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("zones.id", ondelete="CASCADE"))
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    threshold_crossed: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, default="active")
    delivery_method: Mapped[str] = mapped_column(String, nullable=False)

    __table_args__ = (
        CheckConstraint("status IN ('active','resolved')"),
        CheckConstraint("delivery_method IN ('sms_mock','sms_twilio','log_only')"),
    )

    zone: Mapped[Zone] = relationship(back_populates="alerts")


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
    description: Mapped[str] = mapped_column(String, nullable=False)
    reporter_name: Mapped[str | None] = mapped_column(String, nullable=True)
    reporter_phone: Mapped[str | None] = mapped_column(String, nullable=True)
    photo_url: Mapped[str | None] = mapped_column(String, nullable=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    verified_status: Mapped[str] = mapped_column(String, default="unverified")

    __table_args__ = (
        CheckConstraint("report_type IN ('crack','movement','road','other')"),
        CheckConstraint("severity IN ('low','moderate','high','critical')"),
        CheckConstraint("verified_status IN ('unverified','verified','rejected')"),
    )
