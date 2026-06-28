import csv
import json
import os
import shutil
from pathlib import Path

from scripts.enrich_simulator_jsonl import enrich_jsonl
from scripts.export_features_from_enriched_jsonl import export_features
from scripts.validate_enriched_simulator_run import validate_enriched_run
from simulator_core.enrichment import enrich_simulator_batch, enrich_simulator_item
from simulator_core.feature_store import telemetry_to_feature_row
from simulator_core.machinery import AuxiliaryEngineSystem, BoilerSystem, MachinerySnapshot, MainEngine
from simulator_core.scenarios import load_scenario
from simulator_core.sensor_model import synthesize_sensor_readings
from simulator_core.state_buckets import build_state_bucket
from simulator_core.validation_suite import summarize_telemetry
from simulator_core.vessel_geometry import (
    VesselGeometry,
    calculate_depth_draft_ratio,
    calculate_mean_draft,
    calculate_trim,
    classify_depth_condition,
    estimate_displacement_proxy,
)


def sample_telemetry() -> dict:
    return {
        "timestamp_utc": "2026-06-28T10:00:00Z",
        "node_id": "NODE-BALTIC-0001",
        "vessel_mode": "Steaming",
        "speed_over_ground": 13.2,
        "rpm": 74,
        "engine_load_ratio": 0.63,
        "required_power_kw": 11200.0,
        "fuel_burn_rate": 1820.0,
        "co2_value": 5667.48,
        "ch4_value": 0.62,
        "n2o_value": 0.18,
        "draft": 9.4,
        "depth": 34.0,
        "ukc": 24.6,
        "relative_wind_angle": 18.0,
        "weather_wind_speed": 19.0,
        "weather_wave_height": 1.6,
        "weather_air_temp": 6.0,
        "distance_from_previous_nm": 2.64,
        "co2_mass_step_kg": 1133.496,
        "fuel_burn_step_kg": 364.0,
        "fouling_multiplier": 1.09,
        "fuel_type": "MGO_PROXY",
        "cargo_quantity": 24000.0,
        "deadweight_tonnes": 32000.0,
        "confidence_score": 82,
        "uncertainty_pct": 11.5,
        "validation_status": "validation_ready",
        "quality_flags": {
            "shaft_power_kw": 10950.0,
            "current_along_track_kn": 0.4,
        },
    }


def make_workspace_temp_dir() -> Path:
    base_dir = Path("C:\\Users\\nedan\\Downloads\\Projects\\New Digital Twin Project\\test_artifacts")
    base_dir.mkdir(parents=True, exist_ok=True)
    index = 0
    while True:
        candidate = base_dir / f"case_{index}"
        if not candidate.exists():
            candidate.mkdir(parents=True, exist_ok=False)
            return candidate
        index += 1


def test_scenario_config_parses_json_and_yaml() -> None:
    json_config = load_scenario("scenarios/demo_balanced.json")
    yaml_config = load_scenario("scenarios/demo_heavy_weather.yaml")

    assert json_config.scenario_name == "demo_balanced"
    assert json_config.duration_minutes == 360
    assert yaml_config.scenario_name == "demo_heavy_weather"
    assert yaml_config.random_seed == 202


def test_vessel_geometry_helpers() -> None:
    assert calculate_mean_draft(8.8, 10.0) == 9.4
    assert calculate_trim(8.8, 10.0) == 1.2
    assert round(estimate_displacement_proxy(200.0, 32.0, 9.4), 3) == 43164.8
    assert round(calculate_depth_draft_ratio(34.0, 9.4), 6) == 3.617021
    assert classify_depth_condition(3.6) == "deep_water"

    geometry = VesselGeometry.from_drafts(
        length_pp_m=200.0,
        beam_m=32.0,
        design_draft_m=11.0,
        forward_draft_m=8.8,
        aft_draft_m=10.0,
        depth_m=34.0,
        deadweight_tonnes=32000.0,
        gross_tonnage=22000.0,
        wetted_surface_m2=9800.0,
        air_drag_area_m2=1200.0,
    )
    assert geometry.mean_draft_m == 9.4
    assert geometry.trim_m == 1.2
    assert round(geometry.depth_draft_ratio, 6) == 3.617021


def test_machinery_snapshot_output() -> None:
    snapshot = MachinerySnapshot.build(
        main_engine=MainEngine(rated_power_kw=15000.0, sfoc_g_per_kwh=172.0),
        auxiliary_system=AuxiliaryEngineSystem(rated_power_kw=2400.0, sfoc_g_per_kwh=205.0),
        boiler_system=BoilerSystem(rated_power_kw=800.0, sfoc_g_per_kwh=230.0),
        main_engine_power_kw=10000.0,
        auxiliary_power_kw=900.0,
        boiler_power_kw=300.0,
    )

    assert snapshot.main_engine.power_kw == 10000.0
    assert snapshot.total.power_kw == 11200.0
    assert snapshot.total.fuel_kg_h > snapshot.main_engine.fuel_kg_h
    assert snapshot.total.co2_kg_h > 0


def test_sensor_model_output() -> None:
    readings = synthesize_sensor_readings(sample_telemetry(), sensor_quality_mode="standard")
    assert readings.exhaust_flow_kg_h > 0
    assert 0 < readings.co2_percent < 20
    assert readings.sensor_quality_flag in {"ok", "check"}


def test_state_bucket_generation() -> None:
    bucket = build_state_bucket(sample_telemetry())
    assert bucket == "sea_passage|laden|speed_12_14|load_50_70|head_wind_15_25|wave_1_2m|deep_water|moderate_fouling"


def test_feature_row_generation() -> None:
    row = telemetry_to_feature_row(sample_telemetry())
    assert row.vessel_id == "NODE-BALTIC-0001"
    assert row.stw_kn == 12.8
    assert row.co2_kg_nm == round(1133.496 / 2.64, 6)
    assert row.is_valid_for_training is True


def test_validation_summary() -> None:
    summary = summarize_telemetry([sample_telemetry(), sample_telemetry() | {"confidence_score": 60}])
    assert summary.sample_count == 2
    assert summary.mean_co2_kg_nm is not None
    assert summary.mean_fuel_kg_nm is not None
    assert summary.training_valid_rate == 1.0
    assert summary.confidence_mean == 71.0


def test_enrich_simulator_item_preserves_original_fields() -> None:
    item = sample_telemetry()
    enriched = enrich_simulator_item(item)
    for key, value in item.items():
        assert enriched[key] == value


def test_enrich_simulator_item_adds_ee_enrichment() -> None:
    enriched = enrich_simulator_item(sample_telemetry())
    assert "ee_enrichment" in enriched
    assert "validation_flags" in enriched["ee_enrichment"]


def test_enrich_simulator_item_generates_state_bucket() -> None:
    enriched = enrich_simulator_item(sample_telemetry())
    assert enriched["ee_enrichment"]["state_bucket"] == "sea_passage|laden|speed_12_14|load_50_70|head_wind_15_25|wave_1_2m|deep_water|moderate_fouling"


def test_enrich_simulator_item_generates_feature_row() -> None:
    enriched = enrich_simulator_item(sample_telemetry())
    feature_row = enriched["ee_enrichment"]["feature_row"]
    assert feature_row["vessel_id"] == "NODE-BALTIC-0001"
    assert feature_row["is_valid_for_training"] is True


def test_enrich_simulator_item_generates_sensor_fields() -> None:
    enriched = enrich_simulator_item(sample_telemetry())
    sensor_fields = enriched["ee_enrichment"]["sensor_fields"]
    assert sensor_fields["exhaust_flow_kg_h"] > 0
    assert sensor_fields["sensor_quality_flag"] in {"ok", "check"}


def test_enrich_simulator_item_generates_machinery_breakdown() -> None:
    enriched = enrich_simulator_item(sample_telemetry())
    machinery = enriched["ee_enrichment"]["machinery_breakdown"]
    assert set(machinery) == {"main_engine", "auxiliary_engines", "boiler", "total"}
    assert machinery["total"]["power_kw"] > 0


def test_enrich_simulator_batch() -> None:
    batch = {"batch_id": "batch-1", "items": [sample_telemetry(), sample_telemetry() | {"node_id": "NODE-2"}]}
    enriched_batch = enrich_simulator_batch(batch)
    assert enriched_batch["batch_id"] == "batch-1"
    assert len(enriched_batch["items"]) == 2
    assert enriched_batch["ee_batch_enrichment"]["items_enriched"] == 2


def test_export_features_from_enriched_jsonl() -> None:
    batch = {"batch_id": "batch-1", "items": [sample_telemetry()]}
    tmp_path = make_workspace_temp_dir()
    try:
        input_path = tmp_path / "input.jsonl"
        enriched_path = tmp_path / "enriched.jsonl"
        features_path = tmp_path / "features.csv"
        input_path.write_text(json.dumps(batch) + "\n", encoding="utf-8")

        enrich_summary = enrich_jsonl(input_path, enriched_path)
        export_summary = export_features(enriched_path, features_path)

        assert enrich_summary["items_enriched"] == 1
        assert export_summary["rows_written"] == 1
        with features_path.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        assert rows[0]["state_bucket"] == "sea_passage|laden|speed_12_14|load_50_70|head_wind_15_25|wave_1_2m|deep_water|moderate_fouling"
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_validate_enriched_simulator_run() -> None:
    batch = {"batch_id": "batch-1", "items": [sample_telemetry(), sample_telemetry() | {"confidence_score": 60}]}
    tmp_path = make_workspace_temp_dir()
    try:
        input_path = tmp_path / "input.jsonl"
        enriched_path = tmp_path / "enriched.jsonl"
        summary_path = tmp_path / "validation_summary.json"
        input_path.write_text(json.dumps(batch) + "\n", encoding="utf-8")

        enrich_jsonl(input_path, enriched_path)
        summary = validate_enriched_run(enriched_path, summary_path)

        assert summary["sample_count"] == 2
        assert summary["training_valid_rate"] == 1.0
        assert summary_path.exists()
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)
