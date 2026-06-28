from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.analytics import get_worst_baseline_windows


def export_worst_windows_csv(output_path: str | Path, vessel_id: str | None = None, limit: int = 20) -> dict:
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    rows = get_worst_baseline_windows(vessel_id=vessel_id, limit=limit)
    serialized_rows = [{**row, "possible_causes": json.dumps(row["possible_causes"])} for row in rows]
    if serialized_rows:
        with output_file.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(serialized_rows[0].keys()))
            writer.writeheader()
            writer.writerows(serialized_rows)
    else:
        output_file.write_text("", encoding="utf-8")
    return {"rows_written": len(serialized_rows), "vessel_id": vessel_id, "limit": limit}


def main() -> None:
    parser = argparse.ArgumentParser(description="Export worst completed baseline windows to CSV.")
    parser.add_argument("--output", required=True, help="Output CSV path.")
    parser.add_argument("--vessel-id", help="Optional vessel filter.")
    parser.add_argument("--limit", type=int, default=20, help="Maximum rows to export.")
    args = parser.parse_args()
    print(
        json.dumps(
            export_worst_windows_csv(output_path=args.output, vessel_id=args.vessel_id, limit=args.limit),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
