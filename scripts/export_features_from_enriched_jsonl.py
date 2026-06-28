from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def export_features(input_path: str | Path, output_path: str | Path) -> dict:
    input_file = Path(input_path)
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []
    valid_for_training_count = 0

    with input_file.open("r", encoding="utf-8") as src:
        for raw_line in src:
            line = raw_line.strip()
            if not line:
                continue
            batch = json.loads(line)
            for item in batch.get("items", []):
                feature_row = ((item.get("ee_enrichment") or {}).get("feature_row"))
                if isinstance(feature_row, dict):
                    rows.append(feature_row)
                    valid_for_training_count += int(bool(feature_row.get("is_valid_for_training")))

    if rows:
        fieldnames = list(rows[0].keys())
        with output_file.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
    else:
        output_file.write_text("", encoding="utf-8")

    return {
        "rows_written": len(rows),
        "valid_for_training_count": valid_for_training_count,
        "invalid_for_training_count": len(rows) - valid_for_training_count,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Export feature rows from enriched simulator JSONL.")
    parser.add_argument("--input", required=True, help="Input enriched simulator JSONL file.")
    parser.add_argument("--output", required=True, help="Output CSV path.")
    args = parser.parse_args()

    summary = export_features(args.input, args.output)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
