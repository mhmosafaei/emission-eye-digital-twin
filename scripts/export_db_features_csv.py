from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.repositories import get_feature_rows


def export_db_features_csv(
    output_path: str | Path,
    vessel_id: str | None = None,
    valid_for_training_only: bool = False,
    limit: int = 1000,
) -> dict:
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    rows = get_feature_rows(
        vessel_id=vessel_id,
        valid_for_training=True if valid_for_training_only else None,
        limit=limit,
    )
    row_dicts = [_row_to_dict(row) for row in rows]

    if row_dicts:
        with output_file.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(row_dicts[0].keys()))
            writer.writeheader()
            writer.writerows(row_dicts)
    else:
        output_file.write_text("", encoding="utf-8")

    return {
        "rows_written": len(row_dicts),
        "vessel_id": vessel_id,
        "valid_for_training_only": valid_for_training_only,
        "limit": limit,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Export stored feature rows from SQLite to CSV.")
    parser.add_argument("--output", required=True, help="Output CSV file path.")
    parser.add_argument("--vessel-id", help="Optional vessel id filter.")
    parser.add_argument("--valid-for-training-only", action="store_true", help="Only export training-valid rows.")
    parser.add_argument("--limit", type=int, default=1000, help="Maximum rows to export.")
    args = parser.parse_args()

    print(
        json.dumps(
            export_db_features_csv(
                output_path=args.output,
                vessel_id=args.vessel_id,
                valid_for_training_only=args.valid_for_training_only,
                limit=args.limit,
            ),
            indent=2,
        )
    )


def _row_to_dict(row: object) -> dict:
    return {
        key: value
        for key, value in row.__dict__.items()
        if not key.startswith("_")
    }


if __name__ == "__main__":
    main()
