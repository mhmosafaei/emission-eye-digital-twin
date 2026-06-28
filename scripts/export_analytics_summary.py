from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.analytics import rank_vessels_by_baseline_performance, summarize_possible_causes, summarize_vessel_baseline_performance


def export_analytics_summary(output_path: str | Path, vessel_id: str | None = None) -> dict:
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "vessel_summary": summarize_vessel_baseline_performance(vessel_id=vessel_id),
        "possible_causes": summarize_possible_causes(vessel_id=vessel_id),
        "fleet_ranking": [] if vessel_id else rank_vessels_by_baseline_performance(),
    }
    output_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return {
        "output_path": str(output_file),
        "vessel_id": vessel_id,
        "sections_written": len(payload),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Export baseline analytics summary to JSON.")
    parser.add_argument("--output", required=True, help="Output JSON path.")
    parser.add_argument("--vessel-id", help="Optional vessel filter.")
    args = parser.parse_args()
    print(json.dumps(export_analytics_summary(output_path=args.output, vessel_id=args.vessel_id), indent=2))


if __name__ == "__main__":
    main()
