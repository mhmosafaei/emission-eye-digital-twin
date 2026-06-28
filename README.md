# Emission-Eye Digital CO2 Twin

This repository builds the simulator-side foundation and backend plumbing for the Emission-Eye Digital CO2 Twin MVP.

## Current flow

`simulator.py -> enrichment layer -> enriched JSONL -> FastAPI ingestion -> SQLite storage -> feature row queries`

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

python scripts/export_features_from_enriched_jsonl.py \
  --input data/enriched_simulator_output.jsonl \
  --output data/features.csv

python scripts/export_db_features_csv.py \
  --output data/db_features.csv \
  --valid-for-training-only

python scripts/reset_local_db.py --yes

uvicorn app.main:app --reload
```

## API examples

```bash
curl http://localhost:8000/health

curl -X POST http://localhost:8000/ingest/enriched-batch \
  -H "Content-Type: application/json" \
  --data @data/sample_enriched_batch.json

curl http://localhost:8000/records/count

curl http://localhost:8000/features?valid_for_training=true

curl http://localhost:8000/state-buckets
```
