from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.repositories import get_feature_rows


def diagnose_training_validity(
    *,
    input_path: str | Path | None = None,
    from_db: bool = False,
) -> dict:
    if from_db:
        feature_rows = [_feature_row_to_dict(row) for row in get_feature_rows(limit=100000)]
    elif input_path is not None:
        feature_rows = _load_feature_rows_from_jsonl(input_path)
    else:
        raise ValueError("Either input_path or from_db must be provided")

    operation_mode_counts = Counter(str(row.get("operation_mode") or "unknown") for row in feature_rows)
    total_rows = len(feature_rows)
    valid_rows = [row for row in feature_rows if bool(row.get("is_valid_for_training"))]
    sea_rows = [row for row in feature_rows if str(row.get("state_bucket") or "").startswith("sea_passage|")]

    summary = {
        "total_rows": total_rows,
        "valid_for_training_count": len(valid_rows),
        "invalid_for_training_count": total_rows - len(valid_rows),
        "sea_passage_rows": len(sea_rows),
        "sea_passage_valid_count": sum(int(bool(row.get("is_valid_for_training"))) for row in sea_rows),
        "operation_mode_counts": dict(operation_mode_counts),
        "missing_co2_kg_nm_count": _count_missing(feature_rows, "co2_kg_nm"),
        "missing_co2_g_kwh_count": _count_missing(feature_rows, "co2_g_kwh"),
        "missing_shaft_power_count": _count_missing(feature_rows, "shaft_power_kw"),
        "missing_fuel_flow_count": _count_missing(feature_rows, "fuel_flow_kg_h"),
        "low_speed_count": sum(1 for row in feature_rows if float(row.get("sog_kn") or 0.0) < 6.0),
        "non_sea_passage_count": sum(1 for row in feature_rows if str(row.get("operation_mode") or "") != "sea_passage"),
    }
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnose training-validity reasons from enriched JSONL or SQLite.")
    parser.add_argument("--input", help="Enriched simulator JSONL path.")
    parser.add_argument("--from-db", action="store_true", help="Read feature rows from the SQLite database.")
    args = parser.parse_args()

    summary = diagnose_training_validity(input_path=args.input, from_db=args.from_db)
    print(json.dumps(summary, indent=2))


def _load_feature_rows_from_jsonl(input_path: str | Path) -> list[dict]:
    input_file = Path(input_path)
    feature_rows: list[dict] = []
    with input_file.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            batch = json.loads(line)
            for item in batch.get("items", []):
                feature_row = ((item.get("ee_enrichment") or {}).get("feature_row"))
                if isinstance(feature_row, dict):
                    feature_rows.append(feature_row)
    return feature_rows


def _count_missing(feature_rows: list[dict], field_name: str) -> int:
    return sum(1 for row in feature_rows if row.get(field_name) in {None, ""})


def _feature_row_to_dict(row: object) -> dict:
    return {key: value for key, value in row.__dict__.items() if not key.startswith("_")}


if __name__ == "__main__":
    main()
