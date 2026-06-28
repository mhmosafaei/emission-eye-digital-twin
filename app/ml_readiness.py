from __future__ import annotations

from collections import defaultdict

from app.analytics import get_baseline_trend
from app.repositories import (
    count_completed_baseline_comparisons,
    count_distinct_vessels_with_windows,
    count_feature_rows,
    count_records,
    count_valid_feature_rows,
    count_valid_performance_windows,
    count_performance_windows,
    get_average_baseline_confidence,
    get_state_bucket_window_counts,
    get_vessel_completed_comparison_counts,
    get_vessel_window_coverage,
)


def summarize_window_coverage() -> dict:
    return {
        "enriched_records": count_records(),
        "feature_rows": count_feature_rows(),
        "valid_feature_rows": count_valid_feature_rows(),
        "performance_windows": count_performance_windows(),
        "valid_performance_windows": count_valid_performance_windows(),
        "completed_baseline_comparisons": count_completed_baseline_comparisons(),
        "distinct_vessels": count_distinct_vessels_with_windows(valid_only=True),
        "average_baseline_confidence": get_average_baseline_confidence(),
    }


def summarize_state_bucket_repetition() -> dict:
    bucket_rows = get_state_bucket_window_counts(valid_only=True)
    repeated_rows = [row for row in bucket_rows if row["window_count"] >= 2]
    repeated_window_counts = [row["window_count"] for row in repeated_rows]
    return {
        "distinct_state_buckets": len(bucket_rows),
        "repeated_state_buckets": len(repeated_rows),
        "average_windows_per_repeated_bucket": round(sum(repeated_window_counts) / len(repeated_window_counts), 6) if repeated_window_counts else 0.0,
        "top_state_buckets": bucket_rows[:10],
    }


def summarize_vessel_training_coverage() -> list[dict]:
    window_rows = get_vessel_window_coverage()
    comparison_rows = {row["vessel_id"]: row for row in get_vessel_completed_comparison_counts()}
    repeated_bucket_map = _vessel_repeated_bucket_counts()

    coverage: list[dict] = []
    for window_row in window_rows:
        vessel_id = window_row["vessel_id"]
        completed_row = comparison_rows.get(vessel_id, {})
        trend_direction = get_baseline_trend(vessel_id=vessel_id, limit=100).get("trend_direction", "insufficient_data")
        completed_comparisons = int(completed_row.get("completed_comparisons") or 0)
        coverage.append(
            {
                "vessel_id": vessel_id,
                "total_windows": window_row["total_windows"],
                "valid_windows": window_row["valid_windows"],
                "distinct_state_buckets": window_row["distinct_state_buckets"],
                "repeated_state_buckets": repeated_bucket_map.get(vessel_id, 0),
                "average_training_valid_rate": window_row["average_training_valid_rate"],
                "completed_comparisons": completed_comparisons,
                "average_baseline_confidence": completed_row.get("average_baseline_confidence"),
                "trend_direction": trend_direction,
                "trend_ready": trend_direction != "insufficient_data",
                "ml_training_candidate": window_row["valid_windows"] >= 20 and completed_comparisons >= 3,
            }
        )
    return coverage


def calculate_ml_readiness_score() -> dict:
    window_coverage = summarize_window_coverage()
    state_bucket_coverage = summarize_state_bucket_repetition()
    vessel_coverage = summarize_vessel_training_coverage()

    score = 0
    blocking_reasons: list[str] = []
    warnings: list[str] = []

    valid_windows = int(window_coverage["valid_performance_windows"])
    completed = int(window_coverage["completed_baseline_comparisons"])
    distinct_vessels = int(window_coverage["distinct_vessels"])
    repeated_state_buckets = int(state_bucket_coverage["repeated_state_buckets"])
    average_confidence = float(window_coverage["average_baseline_confidence"] or 0.0)
    vessels_with_3plus_completed = sum(1 for row in vessel_coverage if int(row["completed_comparisons"]) >= 3)
    trend_ready_vessels = sum(1 for row in vessel_coverage if bool(row["trend_ready"]))

    if valid_windows >= 300:
        score += 20
    else:
        blocking_reasons.append("Need at least 300 valid performance windows.")

    if completed >= 100:
        score += 20
    else:
        blocking_reasons.append("Need at least 100 completed baseline comparisons.")

    if distinct_vessels >= 3:
        score += 15
    else:
        blocking_reasons.append("Need at least 3 distinct vessels.")

    if repeated_state_buckets >= 10:
        score += 15
    else:
        blocking_reasons.append("Need more repeated state buckets.")

    if average_confidence >= 0.5:
        score += 10
    else:
        warnings.append("Average baseline confidence is still below the ideal 0.5 threshold.")

    if vessels_with_3plus_completed >= 3:
        score += 10
    else:
        warnings.append("Fewer than 3 vessels currently have 3 or more completed comparisons.")

    if trend_ready_vessels >= 3:
        score += 10
    else:
        warnings.append("Trend analytics are ready for fewer than 3 vessels.")

    if repeated_state_buckets < max(10, distinct_vessels * 2):
        warnings.append("Some vessels still have low repeated state-bucket coverage.")

    readiness_level = "ready" if score >= 75 else ("borderline" if score >= 50 else "not_ready")
    ml_ready = readiness_level == "ready"

    if ml_ready:
        recommended_next_action = "Proceed to Sprint 6 ML Expected CO2 Twin."
    elif readiness_level == "borderline":
        recommended_next_action = "Expand the sea-passage demo dataset and rebuild windows before starting Sprint 6."
    else:
        recommended_next_action = "Increase valid windows, repeated state-bucket coverage, and completed baseline history before Sprint 6."

    return {
        "readiness_score": score,
        "readiness_level": readiness_level,
        "ml_ready": ml_ready,
        "blocking_reasons": blocking_reasons,
        "warnings": warnings,
        "recommended_next_action": recommended_next_action,
        "trend_ready_vessels": trend_ready_vessels,
        "vessels_with_3plus_completed_comparisons": vessels_with_3plus_completed,
    }


def summarize_ml_readiness() -> dict:
    window_coverage = summarize_window_coverage()
    state_bucket_coverage = summarize_state_bucket_repetition()
    vessel_coverage = summarize_vessel_training_coverage()
    score = calculate_ml_readiness_score()
    return {
        **window_coverage,
        **state_bucket_coverage,
        "trend_ready_vessels": score["trend_ready_vessels"],
        "vessel_training_coverage": vessel_coverage,
        "ml_ready": score["ml_ready"],
        "readiness_level": score["readiness_level"],
        "readiness_score": score["readiness_score"],
        "blocking_reasons": score["blocking_reasons"],
        "warnings": score["warnings"],
        "recommended_next_action": score["recommended_next_action"],
    }


def _vessel_repeated_bucket_counts() -> dict[str, int]:
    repeated_by_vessel: dict[str, int] = defaultdict(int)
    for row in get_state_bucket_window_counts(valid_only=True):
        state_bucket = row["state_bucket"]
        if state_bucket in {None, ""} or row["window_count"] < 2:
            continue
    # Per-vessel repeated bucket counts are calculated from the vessel coverage rows below.
    vessel_bucket_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for vessel_row in get_vessel_window_coverage():
        repeated_by_vessel.setdefault(vessel_row["vessel_id"], 0)
    from app.repositories import get_performance_windows  # local import to avoid circular import overhead

    for window in get_performance_windows(limit=100000, valid_only=True):
        if not window.dominant_state_bucket:
            continue
        vessel_bucket_counts[window.vessel_id][window.dominant_state_bucket] += 1
    for vessel_id, bucket_counts in vessel_bucket_counts.items():
        repeated_by_vessel[vessel_id] = sum(1 for count in bucket_counts.values() if count >= 2)
    return dict(repeated_by_vessel)
