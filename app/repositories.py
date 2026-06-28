from __future__ import annotations

import json
import uuid
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Iterator

from sqlalchemy import Select, case, desc, func, select
from sqlalchemy.orm import Session, joinedload

from simulator_core.enrichment import enrich_simulator_batch

from .database import get_session, init_db
from .models import BaselineComparison, EnrichedRecord, FeatureRow, PerformanceWindow


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


def count_valid_feature_rows(vessel_id: str | None = None, session: Session | None = None) -> int:
    statement = select(func.count(FeatureRow.id)).where(FeatureRow.is_valid_for_training.is_(True))
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


def create_performance_window(window: PerformanceWindow | dict, session: Session | None = None) -> PerformanceWindow:
    init_db()
    payload = _window_payload(window)
    with session_scope(session) as db:
        existing = db.execute(
            select(PerformanceWindow).where(
                PerformanceWindow.vessel_id == payload["vessel_id"],
                PerformanceWindow.window_start_utc == payload["window_start_utc"],
                PerformanceWindow.window_end_utc == payload["window_end_utc"],
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing

        model = PerformanceWindow(**payload)
        db.add(model)
        db.flush()
        if session is None:
            db.commit()
            db.refresh(model)
        return model


def create_performance_windows(windows: list[PerformanceWindow | dict], session: Session | None = None) -> list[PerformanceWindow]:
    created: list[PerformanceWindow] = []
    with session_scope(session) as db:
        for window in windows:
            created.append(create_performance_window(window, session=db))
        if session is None:
            db.commit()
    return created


def get_performance_windows(
    vessel_id: str | None = None,
    state_bucket: str | None = None,
    valid_only: bool | None = None,
    limit: int = 100,
    session: Session | None = None,
) -> list[PerformanceWindow]:
    statement: Select[tuple[PerformanceWindow]] = select(PerformanceWindow)
    if vessel_id:
        statement = statement.where(PerformanceWindow.vessel_id == vessel_id)
    if state_bucket:
        statement = statement.where(PerformanceWindow.dominant_state_bucket == state_bucket)
    if valid_only is True:
        statement = statement.where(PerformanceWindow.is_valid_window.is_(True))
    elif valid_only is False:
        statement = statement.where(PerformanceWindow.is_valid_window.is_(False))
    statement = statement.order_by(desc(PerformanceWindow.window_start_utc), desc(PerformanceWindow.id)).limit(limit)
    with session_scope(session) as db:
        return list(db.execute(statement).scalars().all())


def count_performance_windows(vessel_id: str | None = None, session: Session | None = None) -> int:
    statement = select(func.count(PerformanceWindow.id))
    if vessel_id:
        statement = statement.where(PerformanceWindow.vessel_id == vessel_id)
    with session_scope(session) as db:
        return int(db.execute(statement).scalar_one())


def count_valid_performance_windows(vessel_id: str | None = None, session: Session | None = None) -> int:
    statement = select(func.count(PerformanceWindow.id)).where(PerformanceWindow.is_valid_window.is_(True))
    if vessel_id:
        statement = statement.where(PerformanceWindow.vessel_id == vessel_id)
    with session_scope(session) as db:
        return int(db.execute(statement).scalar_one())


def get_uncompared_performance_windows(
    vessel_id: str | None = None,
    limit: int = 100,
    valid_windows_only: bool = True,
    session: Session | None = None,
) -> list[PerformanceWindow]:
    statement: Select[tuple[PerformanceWindow]] = (
        select(PerformanceWindow)
        .outerjoin(BaselineComparison, BaselineComparison.window_id == PerformanceWindow.id)
        .where(BaselineComparison.id.is_(None))
        .order_by(PerformanceWindow.window_start_utc.asc(), PerformanceWindow.id.asc())
        .limit(limit)
    )
    if vessel_id:
        statement = statement.where(PerformanceWindow.vessel_id == vessel_id)
    if valid_windows_only:
        statement = statement.where(PerformanceWindow.is_valid_window.is_(True))
    with session_scope(session) as db:
        return list(db.execute(statement).scalars().all())


def create_baseline_comparison(comparison: BaselineComparison | dict, session: Session | None = None) -> BaselineComparison:
    init_db()
    payload = _comparison_payload(comparison)
    with session_scope(session) as db:
        existing = db.execute(
            select(BaselineComparison).where(BaselineComparison.window_id == payload["window_id"])
        ).scalar_one_or_none()
        if existing is not None:
            return existing

        model = BaselineComparison(**payload)
        db.add(model)
        db.flush()
        if session is None:
            db.commit()
            db.refresh(model)
        return model


def create_baseline_comparisons(comparisons: list[BaselineComparison | dict], session: Session | None = None) -> list[BaselineComparison]:
    created: list[BaselineComparison] = []
    with session_scope(session) as db:
        for comparison in comparisons:
            created.append(create_baseline_comparison(comparison, session=db))
        if session is None:
            db.commit()
    return created


def get_baseline_comparisons(
    vessel_id: str | None = None,
    classification: str | None = None,
    state_bucket: str | None = None,
    status: str | None = None,
    valid_only: bool = False,
    limit: int = 100,
    session: Session | None = None,
) -> list[BaselineComparison]:
    statement: Select[tuple[BaselineComparison]] = select(BaselineComparison)
    if vessel_id:
        statement = statement.where(BaselineComparison.vessel_id == vessel_id)
    if classification:
        statement = statement.where(BaselineComparison.classification == classification)
    if state_bucket:
        statement = statement.where(BaselineComparison.state_bucket == state_bucket)
    if status:
        statement = statement.where(BaselineComparison.comparison_status == status)
    if valid_only:
        statement = statement.where(
            BaselineComparison.comparison_status == "completed",
            BaselineComparison.classification.in_(("better", "normal", "worse")),
        )
    statement = statement.order_by(desc(BaselineComparison.created_at), desc(BaselineComparison.id)).limit(limit)
    with session_scope(session) as db:
        return list(db.execute(statement).scalars().all())


def get_completed_baseline_comparisons(
    vessel_id: str | None = None,
    state_bucket: str | None = None,
    limit: int = 1000,
    session: Session | None = None,
) -> list[BaselineComparison]:
    statement: Select[tuple[BaselineComparison]] = (
        select(BaselineComparison)
        .options(joinedload(BaselineComparison.window))
        .where(
            BaselineComparison.comparison_status == "completed",
            BaselineComparison.classification.in_(("better", "normal", "worse")),
        )
    )
    if vessel_id:
        statement = statement.where(BaselineComparison.vessel_id == vessel_id)
    if state_bucket:
        statement = statement.where(BaselineComparison.state_bucket == state_bucket)
    statement = statement.order_by(BaselineComparison.created_at.asc(), BaselineComparison.id.asc()).limit(limit)
    with session_scope(session) as db:
        return list(db.execute(statement).scalars().all())


def get_worst_completed_comparisons(
    vessel_id: str | None = None,
    limit: int = 10,
    session: Session | None = None,
) -> list[BaselineComparison]:
    statement: Select[tuple[BaselineComparison]] = select(BaselineComparison).options(joinedload(BaselineComparison.window)).where(
        BaselineComparison.comparison_status == "completed",
        BaselineComparison.classification.in_(("better", "normal", "worse")),
    )
    if vessel_id:
        statement = statement.where(BaselineComparison.vessel_id == vessel_id)
    statement = statement.order_by(desc(BaselineComparison.performance_gap_pct), desc(BaselineComparison.id)).limit(limit)
    with session_scope(session) as db:
        return list(db.execute(statement).scalars().all())


def get_completed_comparisons_by_vessel(
    vessel_id: str,
    limit: int = 1000,
    session: Session | None = None,
) -> list[BaselineComparison]:
    return get_completed_baseline_comparisons(vessel_id=vessel_id, limit=limit, session=session)


def get_distinct_vessel_ids_with_comparisons(session: Session | None = None) -> list[str]:
    statement = (
        select(BaselineComparison.vessel_id)
        .where(
            BaselineComparison.comparison_status == "completed",
            BaselineComparison.classification.in_(("better", "normal", "worse")),
        )
        .distinct()
        .order_by(BaselineComparison.vessel_id.asc())
    )
    with session_scope(session) as db:
        return [str(value) for value in db.execute(statement).scalars().all()]


def count_completed_baseline_comparisons(session: Session | None = None) -> int:
    statement = select(func.count(BaselineComparison.id)).where(
        BaselineComparison.comparison_status == "completed",
        BaselineComparison.classification.in_(("better", "normal", "worse")),
    )
    with session_scope(session) as db:
        return int(db.execute(statement).scalar_one())


def count_distinct_vessels_with_windows(valid_only: bool = True, session: Session | None = None) -> int:
    statement = select(func.count(func.distinct(PerformanceWindow.vessel_id)))
    if valid_only:
        statement = statement.where(PerformanceWindow.is_valid_window.is_(True))
    with session_scope(session) as db:
        return int(db.execute(statement).scalar_one())


def get_state_bucket_window_counts(valid_only: bool = True, session: Session | None = None) -> list[dict[str, Any]]:
    statement = (
        select(
            PerformanceWindow.dominant_state_bucket,
            func.count(PerformanceWindow.id).label("window_count"),
            func.count(func.distinct(PerformanceWindow.vessel_id)).label("vessel_count"),
        )
        .where(PerformanceWindow.dominant_state_bucket.is_not(None))
        .group_by(PerformanceWindow.dominant_state_bucket)
        .order_by(desc("window_count"), PerformanceWindow.dominant_state_bucket.asc())
    )
    if valid_only:
        statement = statement.where(PerformanceWindow.is_valid_window.is_(True))
    with session_scope(session) as db:
        rows = db.execute(statement).all()
        return [
            {
                "state_bucket": row.dominant_state_bucket,
                "window_count": int(row.window_count or 0),
                "vessel_count": int(row.vessel_count or 0),
            }
            for row in rows
        ]


def get_vessel_window_coverage(session: Session | None = None) -> list[dict[str, Any]]:
    statement = (
        select(
            PerformanceWindow.vessel_id,
            func.count(PerformanceWindow.id).label("total_windows"),
            func.sum(case((PerformanceWindow.is_valid_window.is_(True), 1), else_=0)).label("valid_windows"),
            func.count(func.distinct(PerformanceWindow.dominant_state_bucket)).label("distinct_state_buckets"),
            func.avg(PerformanceWindow.training_valid_rate).label("average_training_valid_rate"),
        )
        .group_by(PerformanceWindow.vessel_id)
        .order_by(PerformanceWindow.vessel_id.asc())
    )
    with session_scope(session) as db:
        rows = db.execute(statement).all()
        return [
            {
                "vessel_id": str(row.vessel_id),
                "total_windows": int(row.total_windows or 0),
                "valid_windows": int(row.valid_windows or 0),
                "distinct_state_buckets": int(row.distinct_state_buckets or 0),
                "average_training_valid_rate": round(float(row.average_training_valid_rate), 6) if row.average_training_valid_rate is not None else None,
            }
            for row in rows
        ]


def get_vessel_completed_comparison_counts(session: Session | None = None) -> list[dict[str, Any]]:
    statement = (
        select(
            BaselineComparison.vessel_id,
            func.count(BaselineComparison.id).label("completed_comparisons"),
            func.avg(BaselineComparison.baseline_confidence).label("average_baseline_confidence"),
        )
        .where(
            BaselineComparison.comparison_status == "completed",
            BaselineComparison.classification.in_(("better", "normal", "worse")),
        )
        .group_by(BaselineComparison.vessel_id)
        .order_by(BaselineComparison.vessel_id.asc())
    )
    with session_scope(session) as db:
        rows = db.execute(statement).all()
        return [
            {
                "vessel_id": str(row.vessel_id),
                "completed_comparisons": int(row.completed_comparisons or 0),
                "average_baseline_confidence": round(float(row.average_baseline_confidence), 6) if row.average_baseline_confidence is not None else None,
            }
            for row in rows
        ]


def get_average_baseline_confidence(session: Session | None = None) -> float | None:
    statement = select(func.avg(BaselineComparison.baseline_confidence)).where(
        BaselineComparison.comparison_status == "completed",
        BaselineComparison.classification.in_(("better", "normal", "worse")),
        BaselineComparison.baseline_confidence.is_not(None),
    )
    with session_scope(session) as db:
        value = db.execute(statement).scalar_one()
        return round(float(value), 6) if value is not None else None


def get_latest_baseline_comparison(vessel_id: str | None = None, session: Session | None = None) -> BaselineComparison | None:
    statement = select(BaselineComparison).order_by(desc(BaselineComparison.created_at), desc(BaselineComparison.id)).limit(1)
    if vessel_id:
        statement = statement.where(BaselineComparison.vessel_id == vessel_id)
    with session_scope(session) as db:
        return db.execute(statement).scalar_one_or_none()


def get_latest_completed_baseline_comparison(vessel_id: str | None = None, session: Session | None = None) -> BaselineComparison | None:
    statement = (
        select(BaselineComparison)
        .where(
            BaselineComparison.comparison_status == "completed",
            BaselineComparison.classification.in_(("better", "normal", "worse")),
        )
        .order_by(desc(BaselineComparison.created_at), desc(BaselineComparison.id))
        .limit(1)
    )
    if vessel_id:
        statement = statement.where(BaselineComparison.vessel_id == vessel_id)
    with session_scope(session) as db:
        return db.execute(statement).scalar_one_or_none()


def get_baseline_summary(vessel_id: str | None = None, session: Session | None = None) -> dict[str, Any]:
    statement = select(BaselineComparison)
    if vessel_id:
        statement = statement.where(BaselineComparison.vessel_id == vessel_id)
    with session_scope(session) as db:
        comparisons = list(db.execute(statement).scalars().all())

    total = len(comparisons)
    by_classification = {
        "better": 0,
        "normal": 0,
        "worse": 0,
        "insufficient_history": 0,
        "invalid_window": 0,
    }
    gaps = []
    for comparison in comparisons:
        by_classification[comparison.classification] = by_classification.get(comparison.classification, 0) + 1
        if comparison.performance_gap_pct is not None:
            gaps.append(float(comparison.performance_gap_pct))
    return {
        "total_comparisons": total,
        **by_classification,
        "average_gap_pct": round(sum(gaps) / len(gaps), 6) if gaps else None,
    }


def get_feature_rows_for_windowing(vessel_id: str | None = None, session: Session | None = None) -> list[FeatureRow]:
    statement: Select[tuple[FeatureRow]] = select(FeatureRow).order_by(FeatureRow.vessel_id.asc(), FeatureRow.timestamp_utc.asc(), FeatureRow.id.asc())
    if vessel_id:
        statement = statement.where(FeatureRow.vessel_id == vessel_id)
    with session_scope(session) as db:
        return list(db.execute(statement).scalars().all())


def find_historical_performance_windows(
    vessel_id: str,
    state_bucket: str,
    before_time: str,
    limit: int = 100,
    session: Session | None = None,
) -> list[PerformanceWindow]:
    statement: Select[tuple[PerformanceWindow]] = (
        select(PerformanceWindow)
        .where(
            PerformanceWindow.vessel_id == vessel_id,
            PerformanceWindow.dominant_state_bucket == state_bucket,
            PerformanceWindow.is_valid_window.is_(True),
            PerformanceWindow.window_start_utc < before_time,
        )
        .order_by(desc(PerformanceWindow.window_start_utc), desc(PerformanceWindow.id))
        .limit(limit)
    )
    with session_scope(session) as db:
        return list(db.execute(statement).scalars().all())


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


def _window_payload(window: PerformanceWindow | dict) -> dict[str, Any]:
    if isinstance(window, PerformanceWindow):
        return {column.name: getattr(window, column.name) for column in PerformanceWindow.__table__.columns if column.name != "id"}
    payload = dict(window)
    payload.setdefault("window_uuid", str(uuid.uuid4()))
    return payload


def _comparison_payload(comparison: BaselineComparison | dict) -> dict[str, Any]:
    if isinstance(comparison, BaselineComparison):
        return {column.name: getattr(comparison, column.name) for column in BaselineComparison.__table__.columns if column.name != "id"}
    payload = dict(comparison)
    payload.setdefault("comparison_uuid", str(uuid.uuid4()))
    if isinstance(payload.get("possible_causes_json"), list):
        payload["possible_causes_json"] = json.dumps(payload["possible_causes_json"])
    if isinstance(payload.get("advisor_json"), dict):
        payload["advisor_json"] = json.dumps(payload["advisor_json"])
    return payload
