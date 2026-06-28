from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.models import PerformanceWindow
from app.repositories import get_performance_windows

NUMERIC_FEATURE_FIELDS = (
    "sample_count",
    "valid_sample_count",
    "training_valid_rate",
    "state_bucket_confidence",
    "avg_fuel_flow_kg_h",
    "avg_fuel_kg_nm",
    "avg_sog_kn",
    "avg_stw_kn",
    "avg_rpm",
    "avg_engine_load_pct",
    "avg_shaft_power_kw",
    "avg_draft_m",
    "avg_trim_m",
    "avg_wind_speed_kn",
    "avg_relative_wind_angle_deg",
    "avg_wave_height_m",
    "avg_depth_m",
    "avg_ukc_m",
    "avg_fouling_multiplier",
    "window_quality_score",
)


def build_ml_training_dataset(
    *,
    vessel_id: str | None = None,
    limit: int = 100000,
) -> dict[str, Any]:
    windows = get_performance_windows(vessel_id=vessel_id, valid_only=True, limit=limit)
    rows = [window for window in windows if _is_ml_trainable_window(window)]
    feature_rows = [build_feature_row(window) for window in rows]
    target_values = [float(window.avg_co2_kg_nm) for window in rows if window.avg_co2_kg_nm is not None]
    return {
        "rows": rows,
        "features": feature_rows,
        "targets": target_values,
        "target_column": "avg_co2_kg_nm",
        "feature_columns": _collect_feature_columns(feature_rows),
    }


def build_prediction_dataset(
    *,
    vessel_id: str | None = None,
    limit: int = 100000,
) -> dict[str, Any]:
    windows = get_performance_windows(vessel_id=vessel_id, valid_only=True, limit=limit)
    rows = [window for window in windows if _is_ml_trainable_window(window)]
    return {
        "rows": rows,
        "features": [build_feature_row(window) for window in rows],
    }


def build_feature_row(window: PerformanceWindow) -> dict[str, Any]:
    state_parts = _parse_state_bucket(window.dominant_state_bucket)
    timestamp = _parse_timestamp(window.window_start_utc)
    duration_minutes = _duration_minutes(window.window_start_utc, window.window_end_utc)

    feature_row: dict[str, Any] = {}
    for field_name in NUMERIC_FEATURE_FIELDS:
        value = getattr(window, field_name, None)
        if value is not None:
            feature_row[field_name] = float(value)

    feature_row["duration_minutes"] = float(duration_minutes) if duration_minutes is not None else 15.0
    feature_row["window_hour_utc"] = float(timestamp.hour) if timestamp is not None else 0.0
    feature_row["window_day_of_week"] = float(timestamp.weekday()) if timestamp is not None else 0.0

    feature_row["vessel_id"] = window.vessel_id
    feature_row["operation_mode"] = window.operation_mode or "unknown"
    feature_row["dominant_state_bucket"] = window.dominant_state_bucket or "unknown"
    feature_row["fuel_type"] = window.fuel_type or "unknown"
    feature_row["loading_condition"] = state_parts.get("loading_condition", "unknown")
    feature_row["speed_bucket"] = state_parts.get("speed_bucket", "unknown")
    feature_row["load_bucket"] = state_parts.get("load_bucket", "unknown")
    feature_row["wind_bucket"] = state_parts.get("wind_bucket", "unknown")
    feature_row["wave_bucket"] = state_parts.get("wave_bucket", "unknown")
    feature_row["water_depth_bucket"] = state_parts.get("water_depth_bucket", "unknown")
    feature_row["fouling_bucket"] = state_parts.get("fouling_bucket", "unknown")
    return feature_row


def _is_ml_trainable_window(window: PerformanceWindow) -> bool:
    return (
        bool(window.is_valid_window)
        and window.avg_co2_kg_nm is not None
        and window.avg_fuel_kg_nm is not None
        and window.avg_sog_kn is not None
    )


def _parse_state_bucket(state_bucket: str | None) -> dict[str, str]:
    if not state_bucket:
        return {}
    parts = state_bucket.split("|")
    return {
        "operation_class": parts[0] if len(parts) > 0 else "unknown",
        "loading_condition": parts[1] if len(parts) > 1 else "unknown",
        "speed_bucket": parts[2] if len(parts) > 2 else "unknown",
        "load_bucket": parts[3] if len(parts) > 3 else "unknown",
        "wind_bucket": parts[4] if len(parts) > 4 else "unknown",
        "wave_bucket": parts[5] if len(parts) > 5 else "unknown",
        "water_depth_bucket": parts[6] if len(parts) > 6 else "unknown",
        "fouling_bucket": parts[7] if len(parts) > 7 else "unknown",
    }


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _duration_minutes(start_value: str | None, end_value: str | None) -> float | None:
    start = _parse_timestamp(start_value)
    end = _parse_timestamp(end_value)
    if start is None or end is None:
        return None
    return max((end - start).total_seconds() / 60.0, 0.0)


def _collect_feature_columns(feature_rows: list[dict[str, Any]]) -> list[str]:
    columns: set[str] = set()
    for row in feature_rows:
        columns.update(row.keys())
    return sorted(columns)
