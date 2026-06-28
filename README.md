# Emission-Eye Digital CO2 Twin

This repository builds the simulator-side foundation and backend plumbing for the Emission-Eye Digital CO2 Twin MVP.

## Current flow

`simulator.py -> sea-passage demo generation -> enrichment layer -> enriched JSONL -> FastAPI ingestion -> SQLite storage -> feature rows -> performance windows -> baseline comparisons -> baseline analytics/advisor -> ML-readiness diagnostics -> ML expected CO2 model -> actual vs ML-expected CO2 predictions -> API/demo outputs`

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
  --vessels 5 \
  --repeat-state-buckets \
  --reset-output \
  --seed 42

python scripts/build_demo_dataset.py --batches 3000 --vessels 5 --seed 42 --reset-db

python scripts/enrich_simulator_jsonl.py \
  --input data/simulator_output.jsonl \
  --output data/enriched_simulator_output.jsonl

python scripts/ingest_enriched_jsonl.py \
  --input data/enriched_simulator_output.jsonl

python scripts/build_windows.py --window-minutes 15

python scripts/diagnose_windows.py --sea-passage-only

python scripts/run_baseline_comparison.py

python scripts/run_baseline_comparison.py --include-invalid-windows

python scripts/export_analytics_summary.py --output data/analytics_summary.json

python scripts/export_worst_windows_csv.py --output data/worst_windows.csv --limit 20

python scripts/export_ml_readiness_report.py --output data/ml_readiness_report.json --pretty

python scripts/train_expected_co2_model.py

python scripts/predict_expected_co2.py --limit 500

python scripts/export_ml_predictions_csv.py --output data/ml_predictions.csv

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

Sprint 6 trains the first expected CO2 model, keeps ML predictions separate from historical baseline comparisons, does not build a dashboard, does not add alert delivery, and does not modify `simulator.py`.

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

curl http://localhost:8000/analytics/vessel-summary

curl http://localhost:8000/analytics/worst-windows

curl http://localhost:8000/analytics/trend

curl http://localhost:8000/analytics/causes

curl http://localhost:8000/analytics/fleet-ranking

curl http://localhost:8000/ml-readiness/summary

curl http://localhost:8000/ml-readiness/window-coverage

curl http://localhost:8000/ml-readiness/state-buckets

curl http://localhost:8000/ml-readiness/vessels

curl -X POST http://localhost:8000/ml/train

curl http://localhost:8000/ml/model-metadata

curl -X POST "http://localhost:8000/ml/predict?limit=500"

curl http://localhost:8000/ml/predictions/latest

curl http://localhost:8000/ml/summary
```
