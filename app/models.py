from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class EnrichedRecord(Base):
    __tablename__ = "enriched_records"
    __table_args__ = (
        Index("ix_enriched_records_vessel_id", "vessel_id"),
        Index("ix_enriched_records_timestamp_utc", "timestamp_utc"),
        Index("ix_enriched_records_state_bucket", "state_bucket"),
        Index("ix_enriched_records_is_valid_for_training", "is_valid_for_training"),
        Index("ix_enriched_records_vessel_id_timestamp_utc", "vessel_id", "timestamp_utc"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    record_uuid: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    batch_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    gateway_uid: Mapped[str | None] = mapped_column(String(128), nullable=True)
    vessel_id: Mapped[str] = mapped_column(String(128), nullable=False)
    vessel_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    imo_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    mmsi: Mapped[str | None] = mapped_column(String(64), nullable=True)
    vessel_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    timestamp_utc: Mapped[str] = mapped_column(String(64), nullable=False)
    operation_mode: Mapped[str | None] = mapped_column(String(128), nullable=True)
    state_bucket: Mapped[str | None] = mapped_column(String(255), nullable=True)
    co2_kg_h: Mapped[float | None] = mapped_column(Float, nullable=True)
    co2_kg_nm: Mapped[float | None] = mapped_column(Float, nullable=True)
    co2_g_kwh: Mapped[float | None] = mapped_column(Float, nullable=True)
    fuel_flow_kg_h: Mapped[float | None] = mapped_column(Float, nullable=True)
    fuel_kg_nm: Mapped[float | None] = mapped_column(Float, nullable=True)
    shaft_power_kw: Mapped[float | None] = mapped_column(Float, nullable=True)
    engine_load_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    rpm: Mapped[float | None] = mapped_column(Float, nullable=True)
    sog_kn: Mapped[float | None] = mapped_column(Float, nullable=True)
    stw_kn: Mapped[float | None] = mapped_column(Float, nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    heading_deg: Mapped[float | None] = mapped_column(Float, nullable=True)
    wind_speed_kn: Mapped[float | None] = mapped_column(Float, nullable=True)
    relative_wind_angle_deg: Mapped[float | None] = mapped_column(Float, nullable=True)
    wave_height_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    draft_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    trim_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    depth_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    ukc_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    fuel_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_valid_for_training: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    data_quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    uncertainty_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    raw_item_json: Mapped[str] = mapped_column(Text, nullable=False)
    ee_enrichment_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    feature_row: Mapped["FeatureRow | None"] = relationship(
        "FeatureRow",
        back_populates="record",
        cascade="all, delete-orphan",
        uselist=False,
    )


class FeatureRow(Base):
    __tablename__ = "feature_rows"
    __table_args__ = (
        Index("ix_feature_rows_vessel_id", "vessel_id"),
        Index("ix_feature_rows_timestamp_utc", "timestamp_utc"),
        Index("ix_feature_rows_state_bucket", "state_bucket"),
        Index("ix_feature_rows_is_valid_for_training", "is_valid_for_training"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    record_id: Mapped[int] = mapped_column(ForeignKey("enriched_records.id"), nullable=False, unique=True)
    vessel_id: Mapped[str] = mapped_column(String(128), nullable=False)
    timestamp_utc: Mapped[str] = mapped_column(String(64), nullable=False)
    operation_mode: Mapped[str | None] = mapped_column(String(128), nullable=True)
    state_bucket: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sog_kn: Mapped[float | None] = mapped_column(Float, nullable=True)
    stw_kn: Mapped[float | None] = mapped_column(Float, nullable=True)
    rpm: Mapped[float | None] = mapped_column(Float, nullable=True)
    engine_load_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    shaft_power_kw: Mapped[float | None] = mapped_column(Float, nullable=True)
    fuel_flow_kg_h: Mapped[float | None] = mapped_column(Float, nullable=True)
    co2_kg_h: Mapped[float | None] = mapped_column(Float, nullable=True)
    co2_kg_nm: Mapped[float | None] = mapped_column(Float, nullable=True)
    co2_g_kwh: Mapped[float | None] = mapped_column(Float, nullable=True)
    fuel_kg_nm: Mapped[float | None] = mapped_column(Float, nullable=True)
    draft_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    trim_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    wind_speed_kn: Mapped[float | None] = mapped_column(Float, nullable=True)
    relative_wind_angle_deg: Mapped[float | None] = mapped_column(Float, nullable=True)
    wave_height_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    depth_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    ukc_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    fouling_multiplier: Mapped[float | None] = mapped_column(Float, nullable=True)
    fuel_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_valid_for_training: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    record: Mapped[EnrichedRecord] = relationship("EnrichedRecord", back_populates="feature_row")
