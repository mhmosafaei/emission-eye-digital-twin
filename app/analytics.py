from __future__ import annotations

import json
import statistics
from collections import Counter

from app.models import BaselineComparison
from app.repositories import (
    get_completed_baseline_comparisons,
    get_distinct_vessel_ids_with_comparisons,
    get_worst_completed_comparisons,
)

VALID_CLASSIFICATIONS = {"better", "normal", "worse"}


def summarize_vessel_baseline_performance(vessel_id: str | None = None) -> dict:
    comparisons = get_completed_baseline_comparisons(vessel_id=vessel_id, limit=5000)
    classification_counts = Counter(comparison.classification for comparison in comparisons if comparison.classification in VALID_CLASSIFICATIONS)
    gaps = [float(comparison.performance_gap_pct) for comparison in comparisons if comparison.performance_gap_pct is not None]
    fuel_gaps = [float(comparison.fuel_gap_pct) for comparison in comparisons if comparison.fuel_gap_pct is not None]
    confidences = [float(comparison.baseline_confidence) for comparison in comparisons if comparison.baseline_confidence is not None]
    cause_counts = _cause_counter(comparisons)

    dominant_classification = None
    if classification_counts:
        dominant_classification = sorted(classification_counts.items(), key=lambda item: (-item[1], item[0]))[0][0]

    return {
        "vessel_id": vessel_id,
        "completed_comparisons": len(comparisons),
        "better": classification_counts.get("better", 0),
        "normal": classification_counts.get("normal", 0),
        "worse": classification_counts.get("worse", 0),
        "average_gap_pct": _round_or_none(_safe_mean(gaps)),
        "median_gap_pct": _round_or_none(statistics.median(gaps) if gaps else None),
        "worst_gap_pct": _round_or_none(max(gaps) if gaps else None),
        "best_gap_pct": _round_or_none(min(gaps) if gaps else None),
        "average_fuel_gap_pct": _round_or_none(_safe_mean(fuel_gaps)),
        "dominant_classification": dominant_classification,
        "baseline_confidence_mean": _round_or_none(_safe_mean(confidences)),
        "top_possible_causes": [{"cause": cause, "count": count} for cause, count in cause_counts.most_common(5)],
        "interpretation": _interpret_summary(dominant_classification, len(comparisons), gaps),
    }


def get_worst_baseline_windows(vessel_id: str | None = None, limit: int = 10) -> list[dict]:
    comparisons = get_worst_completed_comparisons(vessel_id=vessel_id, limit=limit)
    return [
        {
            "comparison_uuid": comparison.comparison_uuid,
            "window_id": comparison.window_id,
            "vessel_id": comparison.vessel_id,
            "state_bucket": comparison.state_bucket,
            "current_co2_kg_nm": _round_or_none(comparison.current_co2_kg_nm),
            "baseline_co2_kg_nm": _round_or_none(comparison.baseline_co2_kg_nm),
            "performance_gap_pct": _round_or_none(comparison.performance_gap_pct),
            "current_fuel_kg_nm": _round_or_none(comparison.current_fuel_kg_nm),
            "baseline_fuel_kg_nm": _round_or_none(comparison.baseline_fuel_kg_nm),
            "fuel_gap_pct": _round_or_none(comparison.fuel_gap_pct),
            "classification": comparison.classification,
            "baseline_confidence": _round_or_none(comparison.baseline_confidence),
            "crew_message": comparison.crew_message,
            "possible_causes": _parse_string_list(comparison.possible_causes_json),
        }
        for comparison in comparisons
    ]


def get_baseline_trend(
    vessel_id: str | None = None,
    bucket: str | None = None,
    limit: int = 100,
) -> dict:
    comparisons = get_completed_baseline_comparisons(vessel_id=vessel_id, state_bucket=bucket, limit=limit)
    points = [
        {
            "timestamp": _comparison_timestamp(comparison),
            "performance_gap_pct": _round_or_none(comparison.performance_gap_pct),
            "fuel_gap_pct": _round_or_none(comparison.fuel_gap_pct),
            "classification": comparison.classification,
            "state_bucket": comparison.state_bucket,
        }
        for comparison in comparisons
    ]
    gap_values = [float(comparison.performance_gap_pct) for comparison in comparisons if comparison.performance_gap_pct is not None]
    return {
        "vessel_id": vessel_id,
        "state_bucket": bucket,
        "points": points,
        "rolling_average_gap_pct": _round_or_none(_safe_mean(gap_values)),
        "latest_gap_pct": _round_or_none(gap_values[-1] if gap_values else None),
        "trend_direction": _trend_direction(gap_values),
    }


def summarize_possible_causes(vessel_id: str | None = None) -> dict:
    comparisons = get_completed_baseline_comparisons(vessel_id=vessel_id, limit=5000)
    cause_counts = _cause_counter(comparisons)
    comparisons_with_causes = sum(1 for comparison in comparisons if _parse_string_list(comparison.possible_causes_json))
    return {
        "vessel_id": vessel_id,
        "completed_comparisons": len(comparisons),
        "comparisons_with_causes": comparisons_with_causes,
        "top_possible_causes": [{"cause": cause, "count": count} for cause, count in cause_counts.most_common(10)],
    }


def rank_vessels_by_baseline_performance() -> list[dict]:
    rankings: list[dict] = []
    for vessel_id in get_distinct_vessel_ids_with_comparisons():
        summary = summarize_vessel_baseline_performance(vessel_id=vessel_id)
        rankings.append(
            {
                "vessel_id": vessel_id,
                "completed_comparisons": summary["completed_comparisons"],
                "average_gap_pct": summary["average_gap_pct"],
                "worse": summary["worse"],
                "better": summary["better"],
                "normal": summary["normal"],
                "dominant_classification": summary["dominant_classification"],
                "baseline_confidence_mean": summary["baseline_confidence_mean"],
            }
        )
    rankings.sort(
        key=lambda item: (
            -(item["average_gap_pct"] if item["average_gap_pct"] is not None else float("-inf")),
            -item["worse"],
            item["vessel_id"],
        )
    )
    return rankings


def _trend_direction(gap_values: list[float]) -> str:
    if len(gap_values) < 3:
        return "insufficient_data"
    split_index = len(gap_values) // 2
    first_half = gap_values[:split_index]
    second_half = gap_values[split_index:]
    if not first_half or not second_half:
        return "insufficient_data"
    delta = statistics.mean(second_half) - statistics.mean(first_half)
    if delta <= -2.0:
        return "improving"
    if delta >= 2.0:
        return "worsening"
    return "stable"


def _interpret_summary(dominant_classification: str | None, comparison_count: int, gaps: list[float]) -> str:
    if comparison_count == 0:
        return "No completed baseline comparisons are available yet for this vessel."
    if dominant_classification == "worse":
        return "This vessel is frequently operating above its historical CO2 baseline in similar conditions."
    if dominant_classification == "better":
        return "This vessel is often outperforming its historical CO2 baseline in similar conditions."
    average_gap = statistics.mean(gaps) if gaps else 0.0
    if average_gap > 2.0:
        return "This vessel is mostly near baseline, with a mild tendency toward above-baseline CO2 intensity."
    if average_gap < -2.0:
        return "This vessel is mostly near baseline, with a mild tendency toward better-than-baseline CO2 intensity."
    return "This vessel is generally operating within its normal historical CO2 baseline range."


def _cause_counter(comparisons: list[BaselineComparison]) -> Counter[str]:
    counter: Counter[str] = Counter()
    for comparison in comparisons:
        counter.update(_parse_string_list(comparison.possible_causes_json))
    return counter


def _parse_string_list(raw_value: str | None) -> list[str]:
    if not raw_value:
        return []
    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed if item not in {None, ""}]


def _comparison_timestamp(comparison: BaselineComparison) -> str:
    if comparison.window is not None and comparison.window.window_start_utc:
        return comparison.window.window_start_utc
    if comparison.baseline_window_start_utc:
        return comparison.baseline_window_start_utc
    return comparison.created_at.isoformat()


def _safe_mean(values: list[float]) -> float | None:
    if not values:
        return None
    return statistics.mean(values)


def _round_or_none(value: float | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 6)
