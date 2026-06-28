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
