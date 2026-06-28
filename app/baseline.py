from __future__ import annotations

import math
import uuid

from app.advisor import generate_baseline_message
from app.models import BaselineComparison, PerformanceWindow
from app.repositories import create_baseline_comparisons, find_historical_performance_windows, get_uncompared_performance_windows


def compare_window_to_baseline(window: PerformanceWindow) -> BaselineComparison:
    if not window.is_valid_window:
        comparison = BaselineComparison(
            comparison_uuid=str(uuid.uuid4()),
            window_id=window.id,
            vessel_id=window.vessel_id,
            state_bucket=window.dominant_state_bucket,
            comparison_status="invalid_window",
            current_co2_kg_nm=window.avg_co2_kg_nm,
            baseline_co2_kg_nm=None,
            performance_gap_pct=None,
            current_fuel_kg_nm=window.avg_fuel_kg_nm,
            baseline_fuel_kg_nm=None,
            fuel_gap_pct=None,
            similar_windows_count=0,
            baseline_confidence=None,
            baseline_window_start_utc=None,
            baseline_window_id=None,
            classification="invalid_window",
            crew_message=None,
            possible_causes_json=None,
            advisor_json=None,
        )
        message = generate_baseline_message(comparison, window)
        comparison.crew_message = message["crew_message"]
        comparison.possible_causes_json = message["possible_causes_json"]
        comparison.advisor_json = message["advisor_json"]
        return comparison

    historical_windows = find_similar_historical_windows(
        vessel_id=window.vessel_id,
        state_bucket=window.dominant_state_bucket or "",
        before_time=window.window_start_utc,
        limit=100,
    )
    if len(historical_windows) < 2:
        comparison = BaselineComparison(
            comparison_uuid=str(uuid.uuid4()),
            window_id=window.id,
            vessel_id=window.vessel_id,
            state_bucket=window.dominant_state_bucket,
            comparison_status="insufficient_history",
            current_co2_kg_nm=window.avg_co2_kg_nm,
            baseline_co2_kg_nm=None,
            performance_gap_pct=None,
            current_fuel_kg_nm=window.avg_fuel_kg_nm,
            baseline_fuel_kg_nm=None,
            fuel_gap_pct=None,
            similar_windows_count=len(historical_windows),
            baseline_confidence=None,
            baseline_window_start_utc=None,
            baseline_window_id=None,
            classification="insufficient_history",
            crew_message=None,
            possible_causes_json=None,
            advisor_json=None,
        )
        message = generate_baseline_message(comparison, window)
        comparison.crew_message = message["crew_message"]
        comparison.possible_causes_json = message["possible_causes_json"]
        comparison.advisor_json = message["advisor_json"]
        return comparison

    baseline = calculate_best_baseline(historical_windows)
    current = float(window.avg_co2_kg_nm or 0.0)
    baseline_value = float(baseline["baseline_co2_kg_nm"])
    performance_gap_pct = round(((current - baseline_value) / baseline_value) * 100.0, 6) if baseline_value > 0 else None
    current_fuel = window.avg_fuel_kg_nm
    baseline_fuel = baseline["baseline_fuel_kg_nm"]
    fuel_gap_pct = None
    if current_fuel is not None and baseline_fuel not in {None, 0}:
        fuel_gap_pct = round(((current_fuel - baseline_fuel) / baseline_fuel) * 100.0, 6)

    if performance_gap_pct is None:
        classification = "invalid_window"
    elif performance_gap_pct <= -2.0:
        classification = "better"
    elif performance_gap_pct > 5.0:
        classification = "worse"
    else:
        classification = "normal"

    comparison = BaselineComparison(
        comparison_uuid=str(uuid.uuid4()),
        window_id=window.id,
        vessel_id=window.vessel_id,
        state_bucket=window.dominant_state_bucket,
        comparison_status="completed",
        current_co2_kg_nm=current,
        baseline_co2_kg_nm=baseline_value,
        performance_gap_pct=performance_gap_pct,
        current_fuel_kg_nm=current_fuel,
        baseline_fuel_kg_nm=baseline_fuel,
        fuel_gap_pct=fuel_gap_pct,
        similar_windows_count=baseline["similar_windows_count"],
        baseline_confidence=baseline["baseline_confidence"],
        baseline_window_start_utc=baseline["baseline_window_start_utc"],
        baseline_window_id=baseline["baseline_window_id"],
        classification=classification,
        crew_message=None,
        possible_causes_json=None,
        advisor_json=None,
    )
    message = generate_baseline_message(comparison, window)
    comparison.crew_message = message["crew_message"]
    comparison.possible_causes_json = message["possible_causes_json"]
    comparison.advisor_json = message["advisor_json"]
    return comparison


def find_similar_historical_windows(
    vessel_id: str,
    state_bucket: str,
    before_time,
    limit: int = 100,
) -> list[PerformanceWindow]:
    return find_historical_performance_windows(vessel_id=vessel_id, state_bucket=state_bucket, before_time=before_time, limit=limit)


def calculate_best_baseline(windows: list[PerformanceWindow]) -> dict:
    valid_windows = [window for window in windows if window.avg_co2_kg_nm is not None]
    if not valid_windows:
        return {
            "baseline_co2_kg_nm": None,
            "baseline_fuel_kg_nm": None,
            "similar_windows_count": 0,
            "baseline_confidence": None,
            "baseline_window_start_utc": None,
            "baseline_window_id": None,
        }

    valid_windows.sort(key=lambda window: float(window.avg_co2_kg_nm or math.inf))
    values = [float(window.avg_co2_kg_nm or 0.0) for window in valid_windows]
    if len(valid_windows) >= 5:
        baseline_co2 = _percentile(values, 10.0)
        baseline_window = min(valid_windows, key=lambda window: abs(float(window.avg_co2_kg_nm or 0.0) - baseline_co2))
    else:
        baseline_window = valid_windows[0]
        baseline_co2 = float(baseline_window.avg_co2_kg_nm or 0.0)

    baseline_fuel_values = [float(window.avg_fuel_kg_nm) for window in valid_windows if window.avg_fuel_kg_nm is not None]
    baseline_fuel = _percentile(baseline_fuel_values, 10.0) if len(baseline_fuel_values) >= 5 else (min(baseline_fuel_values) if baseline_fuel_values else None)

    count = len(valid_windows)
    if count >= 20:
        confidence = 0.90
    elif count >= 10:
        confidence = 0.75
    elif count >= 5:
        confidence = 0.60
    elif count >= 2:
        confidence = 0.40
    else:
        confidence = None

    return {
        "baseline_co2_kg_nm": round(baseline_co2, 6),
        "baseline_fuel_kg_nm": round(baseline_fuel, 6) if baseline_fuel is not None else None,
        "similar_windows_count": count,
        "baseline_confidence": confidence,
        "baseline_window_start_utc": baseline_window.window_start_utc,
        "baseline_window_id": baseline_window.id,
    }


def run_baseline_comparisons(vessel_id: str | None = None, limit: int = 100) -> list[BaselineComparison]:
    windows = get_uncompared_performance_windows(vessel_id=vessel_id, limit=limit, valid_windows_only=True)
    comparisons = [compare_window_to_baseline(window) for window in windows]
    return create_baseline_comparisons(comparisons)


def run_baseline_comparisons_with_options(
    *,
    vessel_id: str | None = None,
    limit: int = 100,
    valid_windows_only: bool = True,
) -> list[BaselineComparison]:
    windows = get_uncompared_performance_windows(
        vessel_id=vessel_id,
        limit=limit,
        valid_windows_only=valid_windows_only,
    )
    comparisons = [compare_window_to_baseline(window) for window in windows]
    return create_baseline_comparisons(comparisons)


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        raise ValueError("values must not be empty")
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = ((len(ordered) - 1) * percentile) / 100.0
    lower_index = int(math.floor(position))
    upper_index = int(math.ceil(position))
    if lower_index == upper_index:
        return ordered[lower_index]
    fraction = position - lower_index
    return ordered[lower_index] + ((ordered[upper_index] - ordered[lower_index]) * fraction)
