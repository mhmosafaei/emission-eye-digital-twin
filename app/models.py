from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
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


class PerformanceWindow(Base):
    __tablename__ = "performance_windows"
    __table_args__ = (
        UniqueConstraint("vessel_id", "window_start_utc", "window_end_utc", name="uq_performance_window_vessel_interval"),
        Index("ix_performance_windows_vessel_id", "vessel_id"),
        Index("ix_performance_windows_window_start_utc", "window_start_utc"),
        Index("ix_performance_windows_dominant_state_bucket", "dominant_state_bucket"),
        Index("ix_performance_windows_is_valid_window", "is_valid_window"),
        Index("ix_performance_windows_vessel_id_window_start_utc", "vessel_id", "window_start_utc"),
        Index("ix_performance_windows_vessel_id_dominant_state_bucket", "vessel_id", "dominant_state_bucket"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    window_uuid: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    vessel_id: Mapped[str] = mapped_column(String(128), nullable=False)
    window_start_utc: Mapped[str] = mapped_column(String(64), nullable=False)
    window_end_utc: Mapped[str] = mapped_column(String(64), nullable=False)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False)
    valid_sample_count: Mapped[int] = mapped_column(Integer, nullable=False)
    training_valid_rate: Mapped[float] = mapped_column(Float, nullable=False)
    operation_mode: Mapped[str | None] = mapped_column(String(128), nullable=True)
    dominant_state_bucket: Mapped[str | None] = mapped_column(String(255), nullable=True)
    state_bucket_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_co2_kg_h: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_co2_kg_nm: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_co2_g_kwh: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_fuel_flow_kg_h: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_fuel_kg_nm: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_sog_kn: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_stw_kn: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_rpm: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_engine_load_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_shaft_power_kw: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_draft_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_trim_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_wind_speed_kn: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_relative_wind_angle_deg: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_wave_height_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_depth_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_ukc_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_fouling_multiplier: Mapped[float | None] = mapped_column(Float, nullable=True)
    fuel_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_valid_window: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    window_quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    invalid_reasons_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    baseline_comparison: Mapped["BaselineComparison | None"] = relationship(
        "BaselineComparison",
        back_populates="window",
        cascade="all, delete-orphan",
        uselist=False,
    )
    ml_predictions: Mapped[list["MLPrediction"]] = relationship(
        "MLPrediction",
        back_populates="window",
        cascade="all, delete-orphan",
    )


class BaselineComparison(Base):
    __tablename__ = "baseline_comparisons"
    __table_args__ = (
        UniqueConstraint("window_id", name="uq_baseline_comparisons_window_id"),
        Index("ix_baseline_comparisons_vessel_id", "vessel_id"),
        Index("ix_baseline_comparisons_state_bucket", "state_bucket"),
        Index("ix_baseline_comparisons_classification", "classification"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    comparison_uuid: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    window_id: Mapped[int] = mapped_column(ForeignKey("performance_windows.id"), nullable=False)
    vessel_id: Mapped[str] = mapped_column(String(128), nullable=False)
    state_bucket: Mapped[str | None] = mapped_column(String(255), nullable=True)
    comparison_status: Mapped[str | None] = mapped_column(String(128), nullable=True)
    current_co2_kg_nm: Mapped[float | None] = mapped_column(Float, nullable=True)
    baseline_co2_kg_nm: Mapped[float | None] = mapped_column(Float, nullable=True)
    performance_gap_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    current_fuel_kg_nm: Mapped[float | None] = mapped_column(Float, nullable=True)
    baseline_fuel_kg_nm: Mapped[float | None] = mapped_column(Float, nullable=True)
    fuel_gap_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    similar_windows_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    baseline_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    baseline_window_start_utc: Mapped[str | None] = mapped_column(String(64), nullable=True)
    baseline_window_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    classification: Mapped[str] = mapped_column(String(64), nullable=False)
    crew_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    possible_causes_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    advisor_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    window: Mapped[PerformanceWindow] = relationship("PerformanceWindow", back_populates="baseline_comparison")


class MLPrediction(Base):
    __tablename__ = "ml_predictions"
    __table_args__ = (
        UniqueConstraint("window_id", "model_version", name="uq_ml_predictions_window_model_version"),
        Index("ix_ml_predictions_vessel_id", "vessel_id"),
        Index("ix_ml_predictions_classification", "classification"),
        Index("ix_ml_predictions_model_version", "model_version"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    prediction_uuid: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    window_id: Mapped[int] = mapped_column(ForeignKey("performance_windows.id"), nullable=False)
    vessel_id: Mapped[str] = mapped_column(String(128), nullable=False)
    window_start_utc: Mapped[str | None] = mapped_column(String(64), nullable=True)
    actual_co2_kg_nm: Mapped[float | None] = mapped_column(Float, nullable=True)
    expected_co2_kg_nm: Mapped[float | None] = mapped_column(Float, nullable=True)
    ml_gap_kg_nm: Mapped[float | None] = mapped_column(Float, nullable=True)
    ml_gap_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    classification: Mapped[str] = mapped_column(String(64), nullable=False)
    prediction_status: Mapped[str] = mapped_column(String(64), nullable=False)
    model_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    model_metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    window: Mapped[PerformanceWindow] = relationship("PerformanceWindow", back_populates="ml_predictions")
