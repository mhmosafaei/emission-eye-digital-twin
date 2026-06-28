from __future__ import annotations

import json
import uuid
from contextlib import contextmanager
from typing import Any, Iterator

from sqlalchemy import Select, case, desc, func, select
from sqlalchemy.orm import Session

from simulator_core.enrichment import enrich_simulator_batch

from .database import get_session, init_db
from .models import EnrichedRecord, FeatureRow


@contextmanager
def session_scope(session: Session | None = None) -> Iterator[Session]:
    if session is not None:
        yield session
        return

    owned_session = get_session()
    try:
        yield owned_session
        owned_session.commit()
    except Exception:
        owned_session.rollback()
        raise
    finally:
        owned_session.close()


def create_enriched_record(item: dict, batch_metadata: dict | None = None, session: Session | None = None) -> dict:
    init_db()
    batch_metadata = batch_metadata or {}

    with session_scope(session) as db:
        ee_enrichment = item.get("ee_enrichment")
        if not isinstance(ee_enrichment, dict):
            raise ValueError("ee_enrichment is required for enriched record storage")

        timestamp_utc = item.get("timestamp_utc")
        vessel_id = _first_non_empty(
            ((ee_enrichment.get("feature_row") or {}).get("vessel_id")),
            item.get("node_id"),
            item.get("imo_number"),
            item.get("vessel_name"),
        )
        if not timestamp_utc or not vessel_id:
            raise ValueError("timestamp_utc and vessel identity are required")

        feature_row = ee_enrichment.get("feature_row") if isinstance(ee_enrichment.get("feature_row"), dict) else None
        record_model = EnrichedRecord(
            record_uuid=str(item.get("record_uuid") or item.get("packet_uuid") or uuid.uuid4()),
            batch_id=str(batch_metadata.get("batch_id") or item.get("batch_id") or "") or None,
            gateway_uid=str(batch_metadata.get("gateway_uid") or item.get("gateway_uid") or "") or None,
            vessel_id=str(vessel_id),
            vessel_name=_string_or_none(item.get("vessel_name")),
            imo_number=_string_or_none(item.get("imo_number")),
            mmsi=_string_or_none(item.get("mmsi")),
            vessel_type=_string_or_none(item.get("vessel_type")),
            timestamp_utc=str(timestamp_utc),
            operation_mode=_string_or_none(
                (feature_row or {}).get("operation_mode") or item.get("vessel_mode") or item.get("operation_mode")
            ),
            state_bucket=_string_or_none(ee_enrichment.get("state_bucket") or (feature_row or {}).get("state_bucket")),
            co2_kg_h=_float_or_none((feature_row or {}).get("co2_kg_h") or item.get("co2_value")),
            co2_kg_nm=_float_or_none((feature_row or {}).get("co2_kg_nm") or item.get("co2_kg_per_nm")),
            co2_g_kwh=_float_or_none((feature_row or {}).get("co2_g_kwh")),
            fuel_flow_kg_h=_float_or_none((feature_row or {}).get("fuel_flow_kg_h") or item.get("fuel_burn_rate")),
            fuel_kg_nm=_derive_fuel_kg_nm(item, feature_row),
            shaft_power_kw=_float_or_none((feature_row or {}).get("shaft_power_kw")),
            engine_load_pct=_float_or_none((feature_row or {}).get("engine_load_pct")),
            rpm=_float_or_none((feature_row or {}).get("rpm") or item.get("rpm")),
            sog_kn=_float_or_none((feature_row or {}).get("sog_kn") or item.get("speed_over_ground")),
            stw_kn=_float_or_none((feature_row or {}).get("stw_kn")),
            latitude=_float_or_none(item.get("lat")),
            longitude=_float_or_none(item.get("lon")),
            heading_deg=_float_or_none(item.get("course_over_ground")),
            wind_speed_kn=_float_or_none((feature_row or {}).get("wind_speed_kn") or item.get("weather_wind_speed")),
            relative_wind_angle_deg=_float_or_none(
                (feature_row or {}).get("relative_wind_angle_deg") or item.get("relative_wind_angle")
            ),
            wave_height_m=_float_or_none((feature_row or {}).get("wave_height_m") or item.get("weather_wave_height")),
            draft_m=_float_or_none((feature_row or {}).get("draft_m") or item.get("draft")),
            trim_m=_float_or_none((feature_row or {}).get("trim_m") or (ee_enrichment.get("geometry") or {}).get("trim_m")),
            depth_m=_float_or_none((feature_row or {}).get("depth_m") or item.get("depth")),
            ukc_m=_float_or_none((feature_row or {}).get("ukc_m") or item.get("ukc")),
            fuel_type=_string_or_none((feature_row or {}).get("fuel_type") or item.get("fuel_type")),
            is_valid_for_training=_bool_or_none(
                ee_enrichment.get("is_valid_for_training")
                if ee_enrichment.get("is_valid_for_training") is not None
                else (feature_row or {}).get("is_valid_for_training")
            ),
            data_quality_score=_calculate_data_quality_score(item, ee_enrichment),
            confidence_score=_float_or_none(item.get("confidence_score")),
            uncertainty_pct=_float_or_none(item.get("uncertainty_pct")),
            raw_item_json=json.dumps(item, sort_keys=True),
            ee_enrichment_json=json.dumps(ee_enrichment, sort_keys=True),
        )
        db.add(record_model)
        db.flush()

        feature_row_model: FeatureRow | None = None
        if feature_row:
            feature_row_model = FeatureRow(
                record_id=record_model.id,
                vessel_id=str(feature_row.get("vessel_id") or vessel_id),
                timestamp_utc=str(feature_row.get("timestamp_utc") or timestamp_utc),
                operation_mode=_string_or_none(feature_row.get("operation_mode")),
                state_bucket=_string_or_none(feature_row.get("state_bucket")),
                sog_kn=_float_or_none(feature_row.get("sog_kn")),
                stw_kn=_float_or_none(feature_row.get("stw_kn")),
                rpm=_float_or_none(feature_row.get("rpm")),
                engine_load_pct=_float_or_none(feature_row.get("engine_load_pct")),
                shaft_power_kw=_float_or_none(feature_row.get("shaft_power_kw")),
                fuel_flow_kg_h=_float_or_none(feature_row.get("fuel_flow_kg_h")),
                co2_kg_h=_float_or_none(feature_row.get("co2_kg_h")),
                co2_kg_nm=_float_or_none(feature_row.get("co2_kg_nm")),
                co2_g_kwh=_float_or_none(feature_row.get("co2_g_kwh")),
                fuel_kg_nm=_derive_fuel_kg_nm(item, feature_row),
                draft_m=_float_or_none(feature_row.get("draft_m")),
                trim_m=_float_or_none(feature_row.get("trim_m")),
                wind_speed_kn=_float_or_none(feature_row.get("wind_speed_kn")),
                relative_wind_angle_deg=_float_or_none(feature_row.get("relative_wind_angle_deg")),
                wave_height_m=_float_or_none(feature_row.get("wave_height_m")),
                depth_m=_float_or_none(feature_row.get("depth_m")),
                ukc_m=_float_or_none(feature_row.get("ukc_m")),
                fouling_multiplier=_float_or_none(feature_row.get("fouling_multiplier")),
                fuel_type=_string_or_none(feature_row.get("fuel_type")),
                is_valid_for_training=_bool_or_none(feature_row.get("is_valid_for_training")),
            )
            db.add(feature_row_model)

        if session is None:
            db.commit()
            db.refresh(record_model)

        return {
            "record": record_model,
            "feature_row": feature_row_model,
            "stored_feature_row": feature_row_model is not None,
        }


def create_enriched_batch(batch: dict, session: Session | None = None) -> dict:
    init_db()
    received = len(batch.get("items", []))
    stored_records = 0
    stored_feature_rows = 0
    rejected = 0

    with session_scope(session) as db:
        for item in batch.get("items", []):
            try:
                result = create_enriched_record(
                    item,
                    batch_metadata={"batch_id": batch.get("batch_id"), "gateway_uid": batch.get("gateway_uid")},
                    session=db,
                )
                stored_records += 1
                stored_feature_rows += int(result["stored_feature_row"])
            except Exception:
                rejected += 1
        if session is None:
            db.commit()

    return {
        "batch_id": batch.get("batch_id"),
        "received": received,
        "stored_records": stored_records,
        "stored_feature_rows": stored_feature_rows,
        "rejected": rejected,
    }


def create_raw_batch(batch: dict, session: Session | None = None) -> dict:
    enriched_batch = enrich_simulator_batch(batch)
    summary = create_enriched_batch(enriched_batch, session=session)
    summary["enriched"] = len(enriched_batch.get("items", []))
    return summary


def get_latest_record(vessel_id: str | None = None, session: Session | None = None) -> EnrichedRecord | None:
    statement = select(EnrichedRecord).order_by(desc(EnrichedRecord.timestamp_utc), desc(EnrichedRecord.id)).limit(1)
    if vessel_id:
        statement = statement.where(EnrichedRecord.vessel_id == vessel_id)
    with session_scope(session) as db:
        return db.execute(statement).scalar_one_or_none()


def get_records(
    vessel_id: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    state_bucket: str | None = None,
    valid_for_training: bool | None = None,
    limit: int = 100,
    session: Session | None = None,
) -> list[EnrichedRecord]:
    statement: Select[tuple[EnrichedRecord]] = select(EnrichedRecord)
    statement = _apply_record_filters(statement, vessel_id, start_time, end_time, state_bucket, valid_for_training)
    statement = statement.order_by(desc(EnrichedRecord.timestamp_utc), desc(EnrichedRecord.id)).limit(limit)
    with session_scope(session) as db:
        return list(db.execute(statement).scalars().all())


def count_records(vessel_id: str | None = None, session: Session | None = None) -> int:
    statement = select(func.count(EnrichedRecord.id))
    if vessel_id:
        statement = statement.where(EnrichedRecord.vessel_id == vessel_id)
    with session_scope(session) as db:
        return int(db.execute(statement).scalar_one())


def get_feature_rows(
    vessel_id: str | None = None,
    state_bucket: str | None = None,
    valid_for_training: bool | None = None,
    limit: int = 1000,
    session: Session | None = None,
) -> list[FeatureRow]:
    statement: Select[tuple[FeatureRow]] = select(FeatureRow)
    if vessel_id:
        statement = statement.where(FeatureRow.vessel_id == vessel_id)
    if state_bucket:
        statement = statement.where(FeatureRow.state_bucket == state_bucket)
    if valid_for_training is not None:
        statement = statement.where(FeatureRow.is_valid_for_training == valid_for_training)
    statement = statement.order_by(desc(FeatureRow.timestamp_utc), desc(FeatureRow.id)).limit(limit)
    with session_scope(session) as db:
        return list(db.execute(statement).scalars().all())


def count_feature_rows(vessel_id: str | None = None, session: Session | None = None) -> int:
    statement = select(func.count(FeatureRow.id))
    if vessel_id:
        statement = statement.where(FeatureRow.vessel_id == vessel_id)
    with session_scope(session) as db:
        return int(db.execute(statement).scalar_one())


def get_state_bucket_counts(session: Session | None = None) -> list[dict[str, Any]]:
    statement = (
        select(
            EnrichedRecord.state_bucket,
            func.count(EnrichedRecord.id).label("record_count"),
            func.sum(case((EnrichedRecord.is_valid_for_training.is_(True), 1), else_=0)).label("valid_training_count"),
        )
        .where(EnrichedRecord.state_bucket.is_not(None))
        .group_by(EnrichedRecord.state_bucket)
        .order_by(desc("record_count"))
    )
    with session_scope(session) as db:
        rows = db.execute(statement).all()
        return [
            {
                "state_bucket": row.state_bucket,
                "record_count": int(row.record_count or 0),
                "valid_training_count": int(row.valid_training_count or 0),
            }
            for row in rows
        ]


def _apply_record_filters(
    statement: Select[tuple[EnrichedRecord]],
    vessel_id: str | None,
    start_time: str | None,
    end_time: str | None,
    state_bucket: str | None,
    valid_for_training: bool | None,
) -> Select[tuple[EnrichedRecord]]:
    if vessel_id:
        statement = statement.where(EnrichedRecord.vessel_id == vessel_id)
    if start_time:
        statement = statement.where(EnrichedRecord.timestamp_utc >= start_time)
    if end_time:
        statement = statement.where(EnrichedRecord.timestamp_utc <= end_time)
    if state_bucket:
        statement = statement.where(EnrichedRecord.state_bucket == state_bucket)
    if valid_for_training is not None:
        statement = statement.where(EnrichedRecord.is_valid_for_training == valid_for_training)
    return statement


def _first_non_empty(*values: Any) -> Any:
    for value in values:
        if value not in {None, ""}:
            return value
    return None


def _string_or_none(value: Any) -> str | None:
    if value in {None, ""}:
        return None
    return str(value)


def _float_or_none(value: Any) -> float | None:
    if value in {None, ""}:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _bool_or_none(value: Any) -> bool | None:
    if value in {None, ""}:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes"}:
            return True
        if lowered in {"false", "0", "no"}:
            return False
    return bool(value)


def _derive_fuel_kg_nm(item: dict, feature_row: dict | None) -> float | None:
    if feature_row and feature_row.get("fuel_kg_nm") not in {None, ""}:
        return _float_or_none(feature_row.get("fuel_kg_nm"))
    distance_nm = _float_or_none(item.get("distance_from_previous_nm"))
    fuel_step_kg = _float_or_none(item.get("fuel_burn_step_kg"))
    if distance_nm in {None, 0} or fuel_step_kg is None:
        return None
    return round(fuel_step_kg / distance_nm, 6)


def _calculate_data_quality_score(item: dict, ee_enrichment: dict) -> float | None:
    confidence = _float_or_none(item.get("confidence_score"))
    uncertainty = _float_or_none(item.get("uncertainty_pct"))
    validation_flags = ee_enrichment.get("validation_flags") or {}

    if confidence is None and uncertainty is None:
        return 80.0 if validation_flags.get("training_valid") else 50.0

    score = confidence if confidence is not None else 100.0
    if uncertainty is not None:
        score -= uncertainty * 0.5
    return round(max(0.0, min(score, 100.0)), 3)
