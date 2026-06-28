from __future__ import annotations

import json
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from app.models import FeatureRow, PerformanceWindow
from app.repositories import create_performance_windows, get_feature_rows_for_windowing


def create_performance_windows_from_feature_rows(
    vessel_id: str | None = None,
    window_minutes: int = 15,
) -> list[PerformanceWindow]:
    rows = get_feature_rows_for_windowing(vessel_id=vessel_id)
    grouped: dict[tuple[str, str], list[FeatureRow]] = defaultdict(list)
    window_meta: dict[tuple[str, str], tuple[str, str]] = {}

    for row in rows:
        timestamp = _parse_timestamp(row.timestamp_utc)
        if timestamp is None:
            continue
        window_start = _floor_timestamp(timestamp, window_minutes)
        window_end = window_start + timedelta(minutes=window_minutes)
        key = (row.vessel_id, _isoformat_z(window_start))
        grouped[key].append(row)
        window_meta[key] = (_isoformat_z(window_start), _isoformat_z(window_end))

    windows: list[PerformanceWindow] = []
    for key, group_rows in grouped.items():
        window = aggregate_feature_rows_to_window(group_rows)
        window.window_start_utc, window.window_end_utc = window_meta[key]
        windows.append(window)

    return create_performance_windows(windows)


def aggregate_feature_rows_to_window(rows: list[FeatureRow]) -> PerformanceWindow:
    if not rows:
        raise ValueError("rows must not be empty")

    vessel_id = rows[0].vessel_id
    sample_count = len(rows)
    valid_sample_count = sum(int(bool(row.is_valid_for_training)) for row in rows)
    training_valid_rate = round(valid_sample_count / sample_count, 6) if sample_count else 0.0

    state_bucket_counter = Counter(row.state_bucket for row in rows if row.state_bucket)
    dominant_state_bucket, dominant_count = (state_bucket_counter.most_common(1)[0] if state_bucket_counter else (None, 0))
    state_bucket_confidence = round(dominant_count / sample_count, 6) if sample_count else None

    operation_counter = Counter(row.operation_mode for row in rows if row.operation_mode)
    operation_mode = operation_counter.most_common(1)[0][0] if operation_counter else None

    window = PerformanceWindow(
        window_uuid=str(uuid.uuid4()),
        vessel_id=vessel_id,
        window_start_utc=rows[0].timestamp_utc,
        window_end_utc=rows[-1].timestamp_utc,
        sample_count=sample_count,
        valid_sample_count=valid_sample_count,
        training_valid_rate=training_valid_rate,
        operation_mode=operation_mode,
        dominant_state_bucket=dominant_state_bucket,
        state_bucket_confidence=state_bucket_confidence,
        avg_co2_kg_h=_average([row.co2_kg_h for row in rows]),
        avg_co2_kg_nm=_average([row.co2_kg_nm for row in rows]),
        avg_co2_g_kwh=_average([row.co2_g_kwh for row in rows]),
        avg_fuel_flow_kg_h=_average([row.fuel_flow_kg_h for row in rows]),
        avg_fuel_kg_nm=_average([row.fuel_kg_nm for row in rows]),
        avg_sog_kn=_average([row.sog_kn for row in rows]),
        avg_stw_kn=_average([row.stw_kn for row in rows]),
        avg_rpm=_average([row.rpm for row in rows]),
        avg_engine_load_pct=_average([row.engine_load_pct for row in rows]),
        avg_shaft_power_kw=_average([row.shaft_power_kw for row in rows]),
        avg_draft_m=_average([row.draft_m for row in rows]),
        avg_trim_m=_average([row.trim_m for row in rows]),
        avg_wind_speed_kn=_average([row.wind_speed_kn for row in rows]),
        avg_relative_wind_angle_deg=_average([row.relative_wind_angle_deg for row in rows]),
        avg_wave_height_m=_average([row.wave_height_m for row in rows]),
        avg_depth_m=_average([row.depth_m for row in rows]),
        avg_ukc_m=_average([row.ukc_m for row in rows]),
        avg_fouling_multiplier=_average([row.fouling_multiplier for row in rows]),
        fuel_type=_dominant_value([row.fuel_type for row in rows]),
        is_valid_window=False,
        window_quality_score=0.0,
        invalid_reasons_json=None,
    )
    invalid_reasons = _collect_invalid_reasons(window)
    window.is_valid_window = not invalid_reasons
    window.window_quality_score = _calculate_window_quality_score(window)
    window.invalid_reasons_json = json.dumps(invalid_reasons) if invalid_reasons else None
    return window


def _collect_invalid_reasons(window: PerformanceWindow) -> list[str]:
    reasons: list[str] = []
    if window.sample_count < 2:
        reasons.append("sample_count_below_minimum")
    if window.training_valid_rate < 0.5:
        reasons.append("training_valid_rate_below_threshold")
    if window.avg_co2_kg_nm is None:
        reasons.append("avg_co2_kg_nm_missing")
    if not window.dominant_state_bucket:
        reasons.append("dominant_state_bucket_missing")
    if (window.operation_mode or "") != "sea_passage":
        reasons.append("operation_mode_not_sea_passage")
    if (window.state_bucket_confidence or 0.0) < 0.5:
        reasons.append("low_state_bucket_confidence")
    return reasons


def _calculate_window_quality_score(window: PerformanceWindow) -> float:
    score = 0.0
    score += min(window.training_valid_rate, 1.0) * 40.0
    score += min(window.state_bucket_confidence or 0.0, 1.0) * 20.0
    score += min(window.sample_count / 4.0, 1.0) * 20.0
    completeness = sum(
        value is not None
        for value in (
            window.avg_co2_kg_nm,
            window.avg_fuel_kg_nm,
            window.avg_shaft_power_kw,
            window.avg_sog_kn,
            window.avg_wind_speed_kn,
        )
    )
    score += (completeness / 5.0) * 20.0
    return round(max(0.0, min(score, 100.0)), 6)


def _average(values: list[float | None]) -> float | None:
    valid = [float(value) for value in values if value is not None]
    if not valid:
        return None
    return round(sum(valid) / len(valid), 6)


def _dominant_value(values: list[str | None]) -> str | None:
    valid = [value for value in values if value not in {None, ""}]
    if not valid:
        return None
    return Counter(valid).most_common(1)[0][0]


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _floor_timestamp(value: datetime, window_minutes: int) -> datetime:
    minute = (value.minute // window_minutes) * window_minutes
    return value.replace(minute=minute, second=0, microsecond=0)


def _isoformat_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
