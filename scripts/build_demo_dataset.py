from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_windows import build_windows
from scripts.enrich_simulator_jsonl import enrich_jsonl
from scripts.export_analytics_summary import export_analytics_summary
from scripts.export_ml_readiness_report import export_ml_readiness_report
from scripts.export_worst_windows_csv import export_worst_windows_csv
from scripts.ingest_enriched_jsonl import ingest_enriched_jsonl
from scripts.reset_local_db import reset_local_db
from scripts.run_baseline_comparison import run_baseline
from scripts.run_simulator_limited import run_simulator_limited


def build_demo_dataset(
    *,
    batches: int,
    vessels: int,
    seed: int | None = None,
    reset_db: bool = False,
    output_dir: str | Path = "data",
    window_minutes: int = 15,
) -> dict:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    raw_output = output_root / "simulator_output.jsonl"
    enriched_output = output_root / "enriched_simulator_output.jsonl"
    analytics_output = output_root / "analytics_summary.json"
    worst_windows_output = output_root / "worst_windows.csv"
    readiness_output = output_root / "ml_readiness_report.json"

    summary: dict[str, dict] = {}
    if reset_db:
        summary["reset_db"] = reset_local_db(yes=True)

    summary["generate"] = run_simulator_limited(
        raw_output,
        batches,
        profile="sea-passage",
        reset_output=True,
        seed=seed,
        vessels=vessels,
        repeat_state_buckets=True,
        records_per_vessel=max(batches // max(vessels, 1), 1),
    )
    summary["enrich"] = enrich_jsonl(raw_output, enriched_output)
    summary["ingest"] = ingest_enriched_jsonl(enriched_output)
    summary["windows"] = build_windows(window_minutes=window_minutes)
    summary["baseline"] = run_baseline(limit=max(batches, 5000))
    summary["analytics_export"] = export_analytics_summary(analytics_output)
    summary["worst_windows_export"] = export_worst_windows_csv(worst_windows_output, limit=20)
    summary["ml_readiness_export"] = export_ml_readiness_report(readiness_output, pretty=True)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a larger demo dataset and export readiness diagnostics.")
    parser.add_argument("--batches", type=int, default=3000, help="Total batches to generate.")
    parser.add_argument("--vessels", type=int, default=5, help="Number of vessels to cycle through.")
    parser.add_argument("--seed", type=int, help="Optional seed for repeatable demo generation.")
    parser.add_argument("--reset-db", action="store_true", help="Delete the local SQLite database before rebuilding.")
    parser.add_argument("--output-dir", default="data", help="Output directory for generated artifacts.")
    args = parser.parse_args()

    summary = build_demo_dataset(
        batches=args.batches,
        vessels=args.vessels,
        seed=args.seed,
        reset_db=args.reset_db,
        output_dir=args.output_dir,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
