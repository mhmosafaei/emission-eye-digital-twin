from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel

try:
    from pydantic import ConfigDict
except ImportError:  # pragma: no cover
    ConfigDict = None  # type: ignore


class ModelBase(BaseModel):
    if ConfigDict is not None:
        model_config = ConfigDict(extra="allow", from_attributes=True)
    else:  # pragma: no cover
        class Config:
            extra = "allow"
            orm_mode = True


class EnrichedRecordIn(ModelBase):
    timestamp_utc: str
    vessel_name: str | None = None
    imo_number: str | None = None
    mmsi: str | None = None
    vessel_type: str | None = None
    ee_enrichment: dict[str, Any] | None = None


class EnrichedBatchIn(ModelBase):
    batch_id: str | None = None
    gateway_uid: str | None = None
    items: list[EnrichedRecordIn]


class IngestSummary(BaseModel):
    source: str
    batch_id: str | None = None
    received: int
    stored_records: int
    stored_feature_rows: int
    rejected: int
    enriched: int | None = None


class RecordOut(ModelBase):
    id: int
    record_uuid: str
    batch_id: str | None = None
    gateway_uid: str | None = None
    vessel_id: str
    vessel_name: str | None = None
    imo_number: str | None = None
    mmsi: str | None = None
    vessel_type: str | None = None
    timestamp_utc: str
    operation_mode: str | None = None
    state_bucket: str | None = None
    co2_kg_h: float | None = None
    co2_kg_nm: float | None = None
    co2_g_kwh: float | None = None
    fuel_flow_kg_h: float | None = None
    fuel_kg_nm: float | None = None
    shaft_power_kw: float | None = None
    engine_load_pct: float | None = None
    rpm: float | None = None
    sog_kn: float | None = None
    stw_kn: float | None = None
    latitude: float | None = None
    longitude: float | None = None
    heading_deg: float | None = None
    wind_speed_kn: float | None = None
    relative_wind_angle_deg: float | None = None
    wave_height_m: float | None = None
    draft_m: float | None = None
    trim_m: float | None = None
    depth_m: float | None = None
    ukc_m: float | None = None
    fuel_type: str | None = None
    is_valid_for_training: bool | None = None
    data_quality_score: float | None = None
    confidence_score: float | None = None
    uncertainty_pct: float | None = None
    raw_item_json: str
    ee_enrichment_json: str
    created_at: datetime


class FeatureRowOut(ModelBase):
    id: int
    record_id: int
    vessel_id: str
    timestamp_utc: str
    operation_mode: str | None = None
    state_bucket: str | None = None
    sog_kn: float | None = None
    stw_kn: float | None = None
    rpm: float | None = None
    engine_load_pct: float | None = None
    shaft_power_kw: float | None = None
    fuel_flow_kg_h: float | None = None
    co2_kg_h: float | None = None
    co2_kg_nm: float | None = None
    co2_g_kwh: float | None = None
    fuel_kg_nm: float | None = None
    draft_m: float | None = None
    trim_m: float | None = None
    wind_speed_kn: float | None = None
    relative_wind_angle_deg: float | None = None
    wave_height_m: float | None = None
    depth_m: float | None = None
    ukc_m: float | None = None
    fouling_multiplier: float | None = None
    fuel_type: str | None = None
    is_valid_for_training: bool | None = None
    created_at: datetime


class WindowBuildRequest(BaseModel):
    vessel_id: str | None = None
    window_minutes: int = 15


class WindowBuildSummary(BaseModel):
    windows_created: int
    valid_windows: int
    invalid_windows: int


class PerformanceWindowOut(ModelBase):
    id: int
    window_uuid: str
    vessel_id: str
    window_start_utc: str
    window_end_utc: str
    sample_count: int
    valid_sample_count: int
    training_valid_rate: float
    operation_mode: str | None = None
    dominant_state_bucket: str | None = None
    state_bucket_confidence: float | None = None
    avg_co2_kg_h: float | None = None
    avg_co2_kg_nm: float | None = None
    avg_co2_g_kwh: float | None = None
    avg_fuel_flow_kg_h: float | None = None
    avg_fuel_kg_nm: float | None = None
    avg_sog_kn: float | None = None
    avg_stw_kn: float | None = None
    avg_rpm: float | None = None
    avg_engine_load_pct: float | None = None
    avg_shaft_power_kw: float | None = None
    avg_draft_m: float | None = None
    avg_trim_m: float | None = None
    avg_wind_speed_kn: float | None = None
    avg_relative_wind_angle_deg: float | None = None
    avg_wave_height_m: float | None = None
    avg_depth_m: float | None = None
    avg_ukc_m: float | None = None
    avg_fouling_multiplier: float | None = None
    fuel_type: str | None = None
    is_valid_window: bool
    window_quality_score: float | None = None
    invalid_reasons_json: str | None = None
    created_at: datetime


class BaselineCompareRequest(BaseModel):
    vessel_id: str | None = None
    limit: int = 100
    valid_windows_only: bool = True


class BaselineCompareSummary(BaseModel):
    comparisons_created: int
    better: int
    normal: int
    worse: int
    insufficient_history: int
    invalid_window: int


class BaselineComparisonOut(ModelBase):
    id: int
    comparison_uuid: str
    window_id: int
    vessel_id: str
    state_bucket: str | None = None
    comparison_status: str | None = None
    current_co2_kg_nm: float | None = None
    baseline_co2_kg_nm: float | None = None
    performance_gap_pct: float | None = None
    current_fuel_kg_nm: float | None = None
    baseline_fuel_kg_nm: float | None = None
    fuel_gap_pct: float | None = None
    similar_windows_count: int
    baseline_confidence: float | None = None
    baseline_window_start_utc: str | None = None
    baseline_window_id: int | None = None
    classification: str
    crew_message: str | None = None
    possible_causes_json: str | None = None
    advisor_json: str | None = None
    created_at: datetime


class BaselineSummaryOut(BaseModel):
    total_comparisons: int
    better: int
    normal: int
    worse: int
    insufficient_history: int
    invalid_window: int
    average_gap_pct: float | None = None


class AnalyticsCauseOut(BaseModel):
    cause: str
    count: int


class VesselBaselineSummaryOut(BaseModel):
    vessel_id: str | None = None
    completed_comparisons: int
    better: int
    normal: int
    worse: int
    average_gap_pct: float | None = None
    median_gap_pct: float | None = None
    worst_gap_pct: float | None = None
    best_gap_pct: float | None = None
    average_fuel_gap_pct: float | None = None
    dominant_classification: str | None = None
    baseline_confidence_mean: float | None = None
    top_possible_causes: list[AnalyticsCauseOut]
    interpretation: str


class WorstBaselineWindowOut(BaseModel):
    comparison_uuid: str
    window_id: int
    vessel_id: str
    state_bucket: str | None = None
    current_co2_kg_nm: float | None = None
    baseline_co2_kg_nm: float | None = None
    performance_gap_pct: float | None = None
    current_fuel_kg_nm: float | None = None
    baseline_fuel_kg_nm: float | None = None
    fuel_gap_pct: float | None = None
    classification: str
    baseline_confidence: float | None = None
    crew_message: str | None = None
    possible_causes: list[str]


class TrendPointOut(BaseModel):
    timestamp: str
    performance_gap_pct: float | None = None
    fuel_gap_pct: float | None = None
    classification: str
    state_bucket: str | None = None


class BaselineTrendOut(BaseModel):
    vessel_id: str | None = None
    state_bucket: str | None = None
    points: list[TrendPointOut]
    rolling_average_gap_pct: float | None = None
    latest_gap_pct: float | None = None
    trend_direction: str


class PossibleCauseSummaryOut(BaseModel):
    vessel_id: str | None = None
    completed_comparisons: int
    comparisons_with_causes: int
    top_possible_causes: list[AnalyticsCauseOut]


class FleetRankingOut(BaseModel):
    vessel_id: str
    completed_comparisons: int
    average_gap_pct: float | None = None
    worse: int
    better: int
    normal: int
    dominant_classification: str | None = None
    baseline_confidence_mean: float | None = None


class WindowCoverageSummaryOut(BaseModel):
    enriched_records: int
    feature_rows: int
    valid_feature_rows: int
    performance_windows: int
    valid_performance_windows: int
    completed_baseline_comparisons: int
    distinct_vessels: int
    average_baseline_confidence: float | None = None


class StateBucketCoverageRowOut(BaseModel):
    state_bucket: str | None = None
    window_count: int
    vessel_count: int


class StateBucketCoverageSummaryOut(BaseModel):
    distinct_state_buckets: int
    repeated_state_buckets: int
    average_windows_per_repeated_bucket: float
    top_state_buckets: list[StateBucketCoverageRowOut]


class VesselTrainingCoverageOut(BaseModel):
    vessel_id: str
    total_windows: int
    valid_windows: int
    distinct_state_buckets: int
    repeated_state_buckets: int
    average_training_valid_rate: float | None = None
    completed_comparisons: int
    average_baseline_confidence: float | None = None
    trend_direction: str
    trend_ready: bool
    ml_training_candidate: bool


class MLReadinessSummaryOut(BaseModel):
    enriched_records: int
    feature_rows: int
    valid_feature_rows: int
    performance_windows: int
    valid_performance_windows: int
    completed_baseline_comparisons: int
    distinct_vessels: int
    distinct_state_buckets: int
    repeated_state_buckets: int
    average_windows_per_repeated_bucket: float
    average_baseline_confidence: float | None = None
    trend_ready_vessels: int
    vessel_training_coverage: list[VesselTrainingCoverageOut]
    ml_ready: bool
    readiness_level: str
    readiness_score: int
    blocking_reasons: list[str]
    warnings: list[str]
    recommended_next_action: str


class MLTrainingSummaryOut(BaseModel):
    model_type: str
    target_column: str
    train_rows: int
    test_rows: int
    mae: float | None = None
    rmse: float | None = None
    r2: float | None = None
    mape_pct: float | None = None
    model_version: str
    model_path: str
    metadata_path: str
    feature_columns: list[str]
    created_at: str


class MLModelMetadataOut(BaseModel):
    model_type: str
    target_column: str
    train_rows: int
    test_rows: int
    mae: float | None = None
    rmse: float | None = None
    r2: float | None = None
    mape_pct: float | None = None
    dummy_mae: float | None = None
    dummy_rmse: float | None = None
    dummy_r2: float | None = None
    dummy_mape_pct: float | None = None
    feature_columns: list[str]
    raw_feature_columns: list[str]
    model_version: str
    created_at: str
    model_path: str
    metadata_path: str
    vessel_id: str | None = None


class MLPredictSummaryOut(BaseModel):
    predictions_created: int
    model_version: str | None = None
    model_type: str | None = None
    summary: dict[str, Any] | None = None


class MLPredictionResultOut(ModelBase):
    id: int
    prediction_uuid: str
    window_id: int
    vessel_id: str
    window_start_utc: str | None = None
    actual_co2_kg_nm: float | None = None
    expected_co2_kg_nm: float | None = None
    ml_gap_kg_nm: float | None = None
    ml_gap_pct: float | None = None
    classification: str
    prediction_status: str
    model_type: str | None = None
    model_version: str | None = None
    model_metadata_json: str | None = None
    interpretation: str | None = None
    created_at: datetime


class MLPredictionSummaryOut(BaseModel):
    total_predictions: int
    ml_better: int
    ml_normal: int
    ml_worse: int
    average_ml_gap_pct: float | None = None
    worst_ml_gap_pct: float | None = None
    best_ml_gap_pct: float | None = None
    model_type: str | None = None
    model_version: str | None = None
    interpretation: str
