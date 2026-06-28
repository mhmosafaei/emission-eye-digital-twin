from __future__ import annotations

import json
import shutil
from pathlib import Path

from scripts.enrich_simulator_jsonl import enrich_jsonl
from scripts.run_simulator_limited import run_simulator_limited


def make_workspace_temp_dir() -> Path:
    base_dir = Path("C:\\Users\\nedan\\Downloads\\Projects\\New Digital Twin Project\\test_artifacts")
    base_dir.mkdir(parents=True, exist_ok=True)
    index = 0
    while True:
        candidate = base_dir / f"runner_case_{index}"
        if not candidate.exists():
            candidate.mkdir(parents=True, exist_ok=False)
            return candidate
        index += 1


def read_batches(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def test_run_simulator_limited_default_profile_still_works() -> None:
    tmp_path = make_workspace_temp_dir()
    try:
        output_path = tmp_path / "default.jsonl"
        summary = run_simulator_limited(output_path, 3, profile="default", reset_output=True, seed=1)
        assert summary["batches_written"] == 3
        assert output_path.exists()
        assert len(read_batches(output_path)) == 3
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_run_simulator_limited_sea_passage_profile_produces_output() -> None:
    tmp_path = make_workspace_temp_dir()
    try:
        output_path = tmp_path / "sea_passage.jsonl"
        summary = run_simulator_limited(output_path, 6, profile="sea-passage", reset_output=True, seed=7)
        assert summary["batches_written"] == 6
        assert output_path.exists()
        batches = read_batches(output_path)
        assert len(batches) == 6
        assert summary["profile"] == "sea-passage"
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_sea_passage_profile_has_steaming_or_sea_passage_records() -> None:
    tmp_path = make_workspace_temp_dir()
    try:
        raw_path = tmp_path / "simulator_output.jsonl"
        enriched_path = tmp_path / "enriched_simulator_output.jsonl"
        run_simulator_limited(raw_path, 12, profile="sea-passage", reset_output=True, seed=11)
        enrich_jsonl(raw_path, enriched_path)

        batches = read_batches(enriched_path)
        state_buckets = [
            item["ee_enrichment"]["state_bucket"]
            for batch in batches
            for item in batch.get("items", [])
            if isinstance(item.get("ee_enrichment"), dict) and item["ee_enrichment"].get("state_bucket")
        ]
        vessel_modes = [
            item.get("vessel_mode")
            for batch in batches
            for item in batch.get("items", [])
        ]

        assert any(bucket.startswith("sea_passage|") for bucket in state_buckets)
        assert any(mode == "Steaming" for mode in vessel_modes)
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_run_simulator_limited_supports_multi_vessel_generation() -> None:
    tmp_path = make_workspace_temp_dir()
    try:
        output_path = tmp_path / "multi_vessel.jsonl"
        summary = run_simulator_limited(
            output_path,
            10,
            profile="sea-passage",
            reset_output=True,
            seed=21,
            vessels=5,
            repeat_state_buckets=True,
        )
        batches = read_batches(output_path)
        vessel_ids = {
            item.get("node_id")
            for batch in batches
            for item in batch.get("items", [])
        }
        assert summary["vessels_requested"] == 5
        assert len(vessel_ids) >= 5
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_run_simulator_limited_records_per_vessel_expands_batch_count() -> None:
    tmp_path = make_workspace_temp_dir()
    try:
        output_path = tmp_path / "records_per_vessel.jsonl"
        summary = run_simulator_limited(
            output_path,
            3,
            profile="sea-passage",
            reset_output=True,
            seed=22,
            vessels=4,
            records_per_vessel=3,
        )
        assert summary["batches_written"] == 12
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)
