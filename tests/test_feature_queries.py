from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path

from app.repositories import create_enriched_batch, get_feature_rows
from scripts.enrich_simulator_jsonl import enrich_jsonl
from scripts.export_db_features_csv import export_db_features_csv
from scripts.ingest_enriched_jsonl import ingest_enriched_jsonl


def make_workspace_temp_dir() -> Path:
    base_dir = Path("C:\\Users\\nedan\\Downloads\\Projects\\New Digital Twin Project\\test_artifacts")
    base_dir.mkdir(parents=True, exist_ok=True)
    index = 0
    while True:
        candidate = base_dir / f"api_case_{index}"
        if not candidate.exists():
            candidate.mkdir(parents=True, exist_ok=False)
            return candidate
        index += 1


def test_features_query(client, enriched_batch: dict) -> None:
    client.post("/ingest/enriched-batch", json=enriched_batch)
    response = client.get("/features", params={"valid_for_training": True})
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 2
    assert rows[0]["state_bucket"]


def test_state_buckets_endpoint(client, enriched_batch: dict) -> None:
    client.post("/ingest/enriched-batch", json=enriched_batch)
    response = client.get("/state-buckets")
    assert response.status_code == 200
    rows = response.json()
    assert rows
    assert rows[0]["record_count"] >= 1


def test_ingest_enriched_jsonl_script(temp_db_url: str, raw_batch: dict) -> None:
    tmp_path = make_workspace_temp_dir()
    try:
        raw_path = tmp_path / "raw.jsonl"
        enriched_path = tmp_path / "enriched.jsonl"
        raw_path.write_text(json.dumps(raw_batch) + "\n", encoding="utf-8")
        enrich_jsonl(raw_path, enriched_path)
        summary = ingest_enriched_jsonl(enriched_path)
        assert summary["batches_read"] == 1
        assert summary["records_stored"] == 2
        assert summary["feature_rows_stored"] == 2
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_export_db_features_csv_script(temp_db_url: str, enriched_batch: dict) -> None:
    create_enriched_batch(enriched_batch)
    tmp_path = make_workspace_temp_dir()
    try:
        output_path = tmp_path / "db_features.csv"
        summary = export_db_features_csv(output_path=output_path, valid_for_training_only=True, limit=10)
        assert summary["rows_written"] == 2
        with output_path.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        assert rows[0]["vessel_id"].startswith("NODE-BALTIC")
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)
