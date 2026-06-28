from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.repositories import get_performance_windows


def export_windows_csv(
    output_path: str | Path,
    *,
    vessel_id: str | None = None,
    valid_only: bool = False,
    sea_passage_only: bool = False,
    limit: int = 100000,
) -> dict:
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    windows = get_performance_windows(vessel_id=vessel_id, valid_only=True if valid_only else None, limit=limit)
    if sea_passage_only:
        windows = [window for window in windows if str(window.dominant_state_bucket or "").startswith("sea_passage|")]

    rows = [{key: value for key, value in window.__dict__.items() if not key.startswith("_")} for window in windows]
    if rows:
        with output_file.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
    else:
        output_file.write_text("", encoding="utf-8")

    return {
        "rows_written": len(rows),
        "vessel_id": vessel_id,
        "valid_only": valid_only,
        "sea_passage_only": sea_passage_only,
        "limit": limit,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Export performance windows to CSV.")
    parser.add_argument("--output", required=True, help="Output CSV path.")
    parser.add_argument("--vessel-id", help="Optional vessel filter.")
    parser.add_argument("--valid-only", action="store_true", help="Only export valid windows.")
    parser.add_argument("--sea-passage-only", action="store_true", help="Only export sea-passage windows.")
    parser.add_argument("--limit", type=int, default=100000, help="Maximum rows to export.")
    args = parser.parse_args()
    print(
        json.dumps(
            export_windows_csv(
                output_path=args.output,
                vessel_id=args.vessel_id,
                valid_only=args.valid_only,
                sea_passage_only=args.sea_passage_only,
                limit=args.limit,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
