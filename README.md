# Emission-Eye Digital CO2 Twin

This repository builds the simulator-side foundation and backend plumbing for the Emission-Eye Digital CO2 Twin MVP.

## Current flow

`simulator.py -> enrichment layer -> enriched JSONL -> FastAPI ingestion -> SQLite storage -> feature rows -> performance windows -> baseline comparisons`

The simulator remains the source of raw telemetry. The enrichment layer adds:

- `ee_enrichment.state_bucket`
- `ee_enrichment.feature_row`
- `ee_enrichment.sensor_fields`
- `ee_enrichment.machinery_breakdown`
- `ee_enrichment.geometry`
- `ee_enrichment.validation_flags`

## Commands

```bash
python scripts/run_simulator_limited.py --output data/simulator_output.jsonl --batches 10

python scripts/run_simulator_limited.py \
  --output data/simulator_output.jsonl \
  --batches 200 \
  --profile sea-passage \
  --reset-output \
  --seed 42

python scripts/enrich_simulator_jsonl.py \
  --input data/simulator_output.jsonl \
  --output data/enriched_simulator_output.jsonl

python scripts/ingest_enriched_jsonl.py \
  --input data/enriched_simulator_output.jsonl

python scripts/build_windows.py --window-minutes 15

python scripts/diagnose_windows.py --sea-passage-only

python scripts/run_baseline_comparison.py

python scripts/run_baseline_comparison.py --include-invalid-windows

python scripts/export_windows_csv.py --output data/performance_windows.csv --sea-passage-only

python scripts/export_baseline_comparisons_csv.py \
  --output data/baseline_comparisons.csv

python scripts/export_features_from_enriched_jsonl.py \
  --input data/enriched_simulator_output.jsonl \
  --output data/features.csv

python scripts/export_db_features_csv.py \
  --output data/db_features.csv \
  --valid-for-training-only

python scripts/reset_local_db.py --yes

uvicorn app.main:app --reload
```

Sprint 4 does not train an ML model yet. Sprint 4 creates the adaptive historical baseline layer over stored feature rows and 15-minute performance windows.

## API examples

```bash
curl http://localhost:8000/health

curl -X POST http://localhost:8000/ingest/enriched-batch \
  -H "Content-Type: application/json" \
  --data @data/sample_enriched_batch.json

curl http://localhost:8000/records/count

curl http://localhost:8000/features?valid_for_training=true

curl http://localhost:8000/state-buckets

curl http://localhost:8000/windows/count

curl http://localhost:8000/baseline/summary

curl http://localhost:8000/baseline/latest

curl http://localhost:8000/baseline/latest-completed

curl "http://localhost:8000/baseline/comparisons?valid_only=true&limit=20"

curl "http://localhost:8000/baseline/comparisons?status=completed&limit=20"
```
