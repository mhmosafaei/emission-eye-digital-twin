from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from simulator_core.enrichment import enrich_simulator_batch
from simulator_core.scenarios import load_scenario


def enrich_jsonl(input_path: str | Path, output_path: str | Path, scenario_path: str | Path | None = None) -> dict:
    scenario = load_scenario(scenario_path) if scenario_path else None
    input_file = Path(input_path)
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    batches_read = 0
    items_read = 0
    items_enriched = 0
    items_failed = 0

    with input_file.open("r", encoding="utf-8") as src, output_file.open("w", encoding="utf-8", newline="\n") as dst:
        for raw_line in src:
            line = raw_line.strip()
            if not line:
                continue
            batch = json.loads(line)
            enriched_batch = enrich_simulator_batch(batch, scenario)
            dst.write(json.dumps(enriched_batch) + "\n")

            batches_read += 1
            batch_items = batch.get("items", [])
            batch_meta = enriched_batch.get("ee_batch_enrichment") or {}
            items_read += len(batch_items)
            items_enriched += int(batch_meta.get("items_enriched") or 0)
            items_failed += int(batch_meta.get("items_failed") or 0)

    summary = {
        "batches_read": batches_read,
        "items_read": items_read,
        "items_enriched": items_enriched,
        "items_failed": items_failed,
    }
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Enrich simulator batch JSONL with Emission-Eye fields.")
    parser.add_argument("--input", required=True, help="Input JSONL file containing simulator batches.")
    parser.add_argument("--output", required=True, help="Output JSONL file for enriched batches.")
    parser.add_argument("--scenario", help="Optional JSON or YAML scenario file.")
    args = parser.parse_args()

    summary = enrich_jsonl(args.input, args.output, args.scenario)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
