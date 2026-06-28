from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.ml_readiness import summarize_ml_readiness


def export_ml_readiness_report(output_path: str | Path, pretty: bool = False) -> dict:
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    payload = summarize_ml_readiness()
    output_file.write_text(
        json.dumps(payload, indent=2 if pretty else None),
        encoding="utf-8",
    )
    return {
        "output_path": str(output_file),
        "pretty": pretty,
        "readiness_level": payload["readiness_level"],
        "readiness_score": payload["readiness_score"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Export ML readiness diagnostics to JSON.")
    parser.add_argument("--output", required=True, help="Output JSON path.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print the JSON output.")
    args = parser.parse_args()
    print(json.dumps(export_ml_readiness_report(output_path=args.output, pretty=args.pretty), indent=2))


if __name__ == "__main__":
    main()
