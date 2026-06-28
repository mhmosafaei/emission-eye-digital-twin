from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.baseline import run_baseline_comparisons_with_options


def run_baseline(vessel_id: str | None = None, limit: int = 100, valid_windows_only: bool = True) -> dict:
    comparisons = run_baseline_comparisons_with_options(
        vessel_id=vessel_id,
        limit=limit,
        valid_windows_only=valid_windows_only,
    )
    summary = {
        "comparisons_created": len(comparisons),
        "better": 0,
        "normal": 0,
        "worse": 0,
        "insufficient_history": 0,
        "invalid_window": 0,
    }
    for comparison in comparisons:
        summary[comparison.classification] = summary.get(comparison.classification, 0) + 1
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run baseline comparison for stored performance windows.")
    parser.add_argument("--vessel-id", help="Optional vessel filter.")
    parser.add_argument("--limit", type=int, default=100, help="Maximum windows to compare.")
    parser.add_argument("--include-invalid-windows", action="store_true", help="Also compare invalid windows.")
    args = parser.parse_args()

    print(
        json.dumps(
            run_baseline(
                vessel_id=args.vessel_id,
                limit=args.limit,
                valid_windows_only=not args.include_invalid_windows,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
