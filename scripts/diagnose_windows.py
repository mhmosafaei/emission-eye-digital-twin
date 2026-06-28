from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.repositories import get_performance_windows


def diagnose_windows(vessel_id: str | None = None, sea_passage_only: bool = False) -> dict:
    windows = get_performance_windows(vessel_id=vessel_id, limit=100000)
    if sea_passage_only:
        windows = [window for window in windows if str(window.dominant_state_bucket or "").startswith("sea_passage|")]

    invalid_reason_counter: Counter[str] = Counter()
    sample_count_distribution: Counter[str] = Counter()
    training_valid_rate_distribution: Counter[str] = Counter()
    operation_mode_counts: Counter[str] = Counter()
    dominant_state_bucket_counter: Counter[str] = Counter()

    total_windows = len(windows)
    valid_windows = 0
    sea_passage_windows = 0
    sea_passage_valid_windows = 0

    for window in windows:
        valid_windows += int(window.is_valid_window)
        if str(window.dominant_state_bucket or "").startswith("sea_passage|"):
            sea_passage_windows += 1
            sea_passage_valid_windows += int(window.is_valid_window)
        operation_mode_counts[str(window.operation_mode or "unknown")] += 1
        if window.dominant_state_bucket:
            dominant_state_bucket_counter[str(window.dominant_state_bucket)] += 1
        sample_count_distribution[_sample_bucket(window.sample_count)] += 1
        training_valid_rate_distribution[_rate_bucket(window.training_valid_rate)] += 1
        for reason in _invalid_reasons(window.invalid_reasons_json):
            invalid_reason_counter[reason] += 1

    return {
        "total_windows": total_windows,
        "valid_windows": valid_windows,
        "invalid_windows": total_windows - valid_windows,
        "sea_passage_windows": sea_passage_windows,
        "sea_passage_valid_windows": sea_passage_valid_windows,
        "sea_passage_invalid_windows": sea_passage_windows - sea_passage_valid_windows,
        "invalid_reasons_count": dict(invalid_reason_counter),
        "sample_count_distribution": dict(sample_count_distribution),
        "training_valid_rate_distribution": dict(training_valid_rate_distribution),
        "operation_mode_counts": dict(operation_mode_counts),
        "dominant_state_bucket_top_20": dominant_state_bucket_counter.most_common(20),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnose performance window validity and distributions.")
    parser.add_argument("--vessel-id", help="Optional vessel filter.")
    parser.add_argument("--sea-passage-only", action="store_true", help="Only inspect sea-passage windows.")
    args = parser.parse_args()
    print(json.dumps(diagnose_windows(vessel_id=args.vessel_id, sea_passage_only=args.sea_passage_only), indent=2))


def _invalid_reasons(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return [str(item) for item in parsed]


def _sample_bucket(sample_count: int) -> str:
    if sample_count <= 1:
        return "1"
    if sample_count == 2:
        return "2"
    if sample_count <= 4:
        return "3_4"
    return "5_plus"


def _rate_bucket(rate: float) -> str:
    if rate < 0.25:
        return "0_0.25"
    if rate < 0.5:
        return "0.25_0.5"
    if rate < 0.75:
        return "0.5_0.75"
    return "0.75_1.0"


if __name__ == "__main__":
    main()
