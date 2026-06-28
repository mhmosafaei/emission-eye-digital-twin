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

## What remains intentionally simple

- Machinery formulas are configurable heuristics, not a final marine physics model.
- Sensor synthesis is a proxy layer derived from existing mass-emissions outputs.
- YAML parsing supports simple key-value scenario files and does not attempt to cover the full YAML spec without an optional parser dependency.
- The enrichment path is file-based and sidecar-oriented; it does not deeply refactor the simulator loop.
- `run_simulator_limited.py` imports the simulator and calls `make_batch()` directly rather than trying to interrupt the infinite runtime loop.
- No changes were made to `simulator.py` in this sprint.
