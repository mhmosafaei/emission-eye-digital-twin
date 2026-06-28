from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.repositories import get_baseline_comparisons


def export_baseline_comparisons_csv(output_path: str | Path, vessel_id: str | None = None, limit: int = 1000) -> dict:
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    comparisons = get_baseline_comparisons(vessel_id=vessel_id, limit=limit)
    rows = [{key: value for key, value in comparison.__dict__.items() if not key.startswith("_")} for comparison in comparisons]

    if rows:
        with output_file.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
    else:
        output_file.write_text("", encoding="utf-8")

    return {"rows_written": len(rows), "vessel_id": vessel_id, "limit": limit}


def main() -> None:
    parser = argparse.ArgumentParser(description="Export stored baseline comparisons to CSV.")
    parser.add_argument("--output", required=True, help="Output CSV path.")
    parser.add_argument("--vessel-id", help="Optional vessel filter.")
    parser.add_argument("--limit", type=int, default=1000, help="Maximum rows to export.")
    args = parser.parse_args()

    print(json.dumps(export_baseline_comparisons_csv(output_path=args.output, vessel_id=args.vessel_id, limit=args.limit), indent=2))


if __name__ == "__main__":
    main()
