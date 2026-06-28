from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.repositories import create_enriched_batch


def ingest_enriched_jsonl(input_path: str | Path) -> dict:
    input_file = Path(input_path)
    batches_read = 0
    items_received = 0
    records_stored = 0
    feature_rows_stored = 0
    rejected = 0

    with input_file.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            batch = json.loads(line)
            summary = create_enriched_batch(batch)
            batches_read += 1
            items_received += int(summary["received"])
            records_stored += int(summary["stored_records"])
            feature_rows_stored += int(summary["stored_feature_rows"])
            rejected += int(summary["rejected"])

    return {
        "batches_read": batches_read,
        "items_received": items_received,
        "records_stored": records_stored,
        "feature_rows_stored": feature_rows_stored,
        "rejected": rejected,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest enriched simulator JSONL into SQLite.")
    parser.add_argument("--input", required=True, help="Path to enriched simulator JSONL.")
    args = parser.parse_args()

    print(json.dumps(ingest_enriched_jsonl(args.input), indent=2))


if __name__ == "__main__":
    main()
