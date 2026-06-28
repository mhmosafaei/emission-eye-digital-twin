# Simulator Upgrade Plan

## Sprint scope

This sprint adds a clean extension foundation around the existing simulator instead of refactoring the simulator itself. The goal is to prepare the Emission-Eye Digital CO2 Twin for scenario control, machinery decomposition, explainable state labels, ML-ready exports, and validation summaries.

## How the new modules connect to the current simulator

- `simulator_core.scenarios`
  Loads repeatable scenario inputs from JSON or YAML so future runs can be parameterized without editing simulator code.
- `simulator_core.vessel_geometry`
  Holds vessel geometry fields and helper calculations that can later replace scattered draft/depth heuristics with shared geometry logic.
- `simulator_core.machinery`
  Produces a simple main-engine, auxiliary, and boiler breakdown that can be attached to simulator telemetry or used to create subsystem audit views.
- `simulator_core.sensor_model`
  Synthesizes direct-measurement-style exhaust fields from existing simulator mass-emission outputs for future CEMS-style workflows.
- `simulator_core.state_buckets`
  Converts telemetry into explainable crew-facing operating states that can later power adaptive baselines and segmented analytics.
- `simulator_core.feature_store`
  Converts simulator telemetry items into ML-ready rows with stable field names for model training and offline analysis.
- `simulator_core.validation_suite`
  Summarizes run quality, training readiness, confidence, and uncertainty across telemetry batches.

## Integration path for the next sprint

1. Load a scenario file before simulator startup and map its fields to vessel choice, route presets, fouling profile, and sensor-quality mode.
2. Attach `state_bucket`, feature rows, and synthesized sensor readings directly to outgoing telemetry or to a sidecar export pipeline.
3. Feed machinery snapshots from simulator power outputs so subsystem-level emissions become first-class telemetry.
4. Add scenario-driven sample generation and validation reports to repeatable demo or backtest runs.
5. Introduce AIS replay and packet builders only after the current payload contract is stable.

## Sprint 2 - Enrichment Layer Integration

Sprint 2 adds a safe sidecar pipeline around the existing simulator output:

`simulator.py -> enrichment.py -> enriched JSONL -> features.csv -> validation summary`

The core simulator remains the source of raw telemetry. The new enrichment layer preserves the original item fields and attaches extra outputs under `ee_enrichment`, including:

- explainable state buckets,
- ML-ready feature rows,
- raw exhaust-style sensor fields,
- machinery breakdowns,
- vessel geometry summaries,
- validation flags.

### Example commands

```bash
python scripts/run_simulator_limited.py --output data/simulator_output.jsonl --batches 10
python scripts/enrich_simulator_jsonl.py --input data/simulator_output.jsonl --output data/enriched_simulator_output.jsonl
python scripts/export_features_from_enriched_jsonl.py --input data/enriched_simulator_output.jsonl --output data/features.csv
python scripts/validate_enriched_simulator_run.py --input data/enriched_simulator_output.jsonl --output data/validation_summary.json
```

## Sprint 3 - FastAPI and SQLite Backend

Sprint 3 adds persistent storage and API access for enriched telemetry:

`simulator.py -> enrichment layer -> enriched JSONL -> FastAPI ingestion -> SQLite storage -> feature rows`

### Backend flow

- `scripts/ingest_enriched_jsonl.py` stores enriched batches into SQLite.
- `app.main` exposes FastAPI endpoints for ingest, record queries, feature queries, and state-bucket summaries.
- `feature_rows` are normalized from `ee_enrichment.feature_row` for downstream model and analytics workflows.

### Example commands

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

uvicorn app.main:app --reload

python scripts/reset_local_db.py --yes
```

### API examples

```bash
curl http://localhost:8000/health

curl -X POST http://localhost:8000/ingest/enriched-batch \
  -H "Content-Type: application/json" \
  --data @data/sample_enriched_batch.json

curl http://localhost:8000/records/count
curl http://localhost:8000/features?valid_for_training=true
curl http://localhost:8000/state-buckets
```

## Sprint 4 - 15-Minute Windows and Adaptive Baseline

Sprint 4 adds the first Digital CO2 Twin intelligence layer:

`simulator.py -> enrichment -> SQLite feature_rows -> 15-minute performance_windows -> baseline_comparisons -> API queries`

This sprint does not train an ML model yet. It builds an adaptive historical baseline by vessel and state bucket so the MVP can ask whether a vessel has performed better before in similar operating conditions.

### Example commands

```bash
python scripts/build_windows.py --window-minutes 15
python scripts/run_baseline_comparison.py
python scripts/export_baseline_comparisons_csv.py --output data/baseline_comparisons.csv
python -m uvicorn app.main:app --reload
```

### API examples

```bash
curl.exe http://localhost:8000/windows/count
curl.exe http://localhost:8000/baseline/summary
curl.exe http://localhost:8000/baseline/latest
curl.exe http://localhost:8000/baseline/latest-completed
curl.exe "http://localhost:8000/baseline/comparisons?valid_only=true&limit=20"
curl.exe "http://localhost:8000/baseline/comparisons?status=completed&limit=20"
```

## Sprint 4.1 - Baseline Cleanup and Window Diagnostics

Sprint 4.1 keeps the baseline layer focused on valid sea-passage intelligence by:

- storing explicit invalid-window reasons,
- diagnosing why windows are invalid,
- defaulting baseline comparison runs to valid windows only,
- exposing a latest-completed baseline endpoint and cleaner comparison filters,
- exporting performance windows for inspection.

### Example commands

```bash
python scripts/diagnose_windows.py --sea-passage-only
python scripts/run_baseline_comparison.py
python scripts/run_baseline_comparison.py --include-invalid-windows
python scripts/export_windows_csv.py --output data/performance_windows.csv --sea-passage-only
```

## Sprint 5 - Baseline Analytics and Operational Advisor Refinement

Sprint 5 extends the completed baseline layer into demo-ready operational analytics:

`simulator.py -> enrichment -> feature_rows -> performance_windows -> baseline_comparisons -> baseline analytics/advisor -> API/demo outputs`

This sprint does not train an ML model, does not build a dashboard UI, and does not add real-time alert delivery. It turns completed baseline comparisons into explainable vessel summaries, worst-window analysis, trend analytics, cause aggregation, and fleet ranking outputs.

### Example commands

```bash
python scripts/export_analytics_summary.py --output data/analytics_summary.json
python scripts/export_analytics_summary.py --vessel-id NODE-ARCTIC-0003 --output data/analytics_summary_NODE-ARCTIC-0003.json
python scripts/export_worst_windows_csv.py --output data/worst_windows.csv --limit 20
```

### API examples

```bash
curl.exe http://localhost:8000/analytics/vessel-summary
curl.exe http://localhost:8000/analytics/worst-windows
curl.exe http://localhost:8000/analytics/trend
curl.exe http://localhost:8000/analytics/causes
curl.exe http://localhost:8000/analytics/fleet-ranking
```

## Sprint 5.5 - Demo Dataset Expansion + ML Readiness Diagnostics

Sprint 5.5 strengthens the demo dataset and adds a transparent readiness gate before Sprint 6:

`simulator.py -> sea-passage demo generation -> enrichment -> feature_rows -> performance_windows -> baseline_comparisons -> baseline analytics/advisor -> ML-readiness diagnostics -> Sprint 6 decision gate`

This sprint does not train an ML model, does not build a dashboard, and does not add alert delivery. It expands sea-passage demo generation, improves repeated bucket coverage, and reports whether Sprint 6 ML is justified.

### Example commands

```bash
python scripts/build_demo_dataset.py --batches 3000 --vessels 5 --seed 42 --reset-db
python scripts/export_ml_readiness_report.py --output data/ml_readiness_report.json --pretty
```

### API examples

```bash
curl.exe http://localhost:8000/ml-readiness/summary
curl.exe http://localhost:8000/ml-readiness/window-coverage
curl.exe http://localhost:8000/ml-readiness/state-buckets
curl.exe http://localhost:8000/ml-readiness/vessels
```

## Sprint 6 - ML Expected CO2 Twin

Sprint 6 adds the first trained expected-CO2 model on top of the validated demo dataset:

`simulator.py -> enrichment -> feature_rows -> performance_windows -> baseline_comparisons -> baseline analytics/advisor -> ML-readiness diagnostics -> ML expected CO2 model -> actual vs ML-expected CO2 predictions -> API/demo outputs`

Sprint 6 trains the first expected CO2 model, keeps ML predictions separate from historical baseline comparisons, does not build a dashboard, does not add alert delivery, and does not modify `simulator.py`.

### Example commands

```bash
python scripts/train_expected_co2_model.py
python scripts/predict_expected_co2.py --limit 500
python scripts/export_ml_predictions_csv.py --output data/ml_predictions.csv
```

### API examples

```bash
curl.exe -X POST http://localhost:8000/ml/train
curl.exe http://localhost:8000/ml/model-metadata
curl.exe -X POST "http://localhost:8000/ml/predict?limit=500"
curl.exe http://localhost:8000/ml/predictions/latest
curl.exe http://localhost:8000/ml/summary
```

## What remains intentionally simple

- Machinery formulas are configurable heuristics, not a final marine physics model.
- Sensor synthesis is a proxy layer derived from existing mass-emissions outputs.
- YAML parsing supports simple key-value scenario files and does not attempt to cover the full YAML spec without an optional parser dependency.
- The enrichment path is file-based and sidecar-oriented; it does not deeply refactor the simulator loop.
- `run_simulator_limited.py` imports the simulator and calls `make_batch()` directly rather than trying to interrupt the infinite runtime loop.
- No changes were made to `simulator.py` in this sprint.
