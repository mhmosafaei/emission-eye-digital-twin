from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from simulator_core.validation_suite import summarize_telemetry


def validate_enriched_run(input_path: str | Path, output_path: str | Path) -> dict:
    input_file = Path(input_path)
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    items: list[dict] = []
    with input_file.open("r", encoding="utf-8") as src:
        for raw_line in src:
            line = raw_line.strip()
            if not line:
                continue
            batch = json.loads(line)
            items.extend(batch.get("items", []))

    summary = summarize_telemetry(items).as_dict()
    output_file.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a validation summary from enriched simulator JSONL.")
    parser.add_argument("--input", required=True, help="Input enriched simulator JSONL file.")
    parser.add_argument("--output", required=True, help="Output JSON summary path.")
    args = parser.parse_args()

    summary = validate_enriched_run(args.input, args.output)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
