import uuid
from datetime import datetime, timezone

from geoalchemy2 import Geometry
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
    last_updated: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    __table_args__ = (CheckConstraint("risk_tier IN ('low','moderate','high')"),)

    rainfall_readings: Mapped[list["RainfallReading"]] = relationship(back_populates="zone")
    alerts: Mapped[list["Alert"]] = relationship(back_populates="zone")


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
    zone_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("zones.id", ondelete="SET NULL"), nullable=True
    )
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    photo_url: Mapped[str | None] = mapped_column(String, nullable=True)
    geo_lat: Mapped[float] = mapped_column(Float, nullable=False)
    geo_lng: Mapped[float] = mapped_column(Float, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    verified_status: Mapped[str] = mapped_column(String, default="unverified")

    __table_args__ = (CheckConstraint("verified_status IN ('unverified','verified','rejected')"),)
