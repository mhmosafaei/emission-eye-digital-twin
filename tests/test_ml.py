from __future__ import annotations

import csv
import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.ml_features import build_ml_training_dataset
from app.ml_prediction import classify_ml_gap, predict_expected_co2_for_windows, summarize_ml_predictions
from app.ml_training import load_model_metadata, train_expected_co2_model
from app.repositories import create_performance_window, get_latest_ml_prediction, get_ml_predictions
from scripts.export_ml_predictions_csv import export_ml_predictions_csv


def make_workspace_temp_dir(prefix: str = "ml_case_") -> Path:
    base_dir = Path("C:\\Users\\nedan\\Downloads\\Projects\\New Digital Twin Project\\test_artifacts")
    base_dir.mkdir(parents=True, exist_ok=True)
    index = 0
    while True:
        candidate = base_dir / f"{prefix}{index}"
        if not candidate.exists():
            candidate.mkdir(parents=True, exist_ok=False)
            return candidate
        index += 1


@pytest.fixture
def temp_model_dir(monkeypatch):
    tmp_dir = make_workspace_temp_dir("ml_models_")
    monkeypatch.setenv("EMISSION_EYE_MODEL_DIR", str(tmp_dir / "models"))
    yield Path(tmp_dir / "models")
    monkeypatch.delenv("EMISSION_EYE_MODEL_DIR", raising=False)
    shutil.rmtree(tmp_dir, ignore_errors=True)


def create_ml_window(
    *,
    vessel_id: str,
    window_uuid: str,
    window_start_utc: str,
    avg_co2_kg_nm: float,
    avg_fuel_kg_nm: float,
    avg_sog_kn: float,
    avg_engine_load_pct: float,
    avg_shaft_power_kw: float,
    avg_wind_speed_kn: float,
    avg_wave_height_m: float,
    state_bucket: str,
) -> None:
    create_performance_window(
        {
            "window_uuid": window_uuid,
            "vessel_id": vessel_id,
            "window_start_utc": window_start_utc,
            "window_end_utc": (
                datetime.fromisoformat(window_start_utc.replace("Z", "+00:00")) + timedelta(minutes=15)
            ).isoformat().replace("+00:00", "Z"),
            "sample_count": 3,
            "valid_sample_count": 3,
            "training_valid_rate": 1.0,
            "operation_mode": "sea_passage",
            "dominant_state_bucket": state_bucket,
            "state_bucket_confidence": 1.0,
            "avg_co2_kg_h": round(avg_co2_kg_nm * avg_sog_kn, 6),
            "avg_co2_kg_nm": avg_co2_kg_nm,
            "avg_co2_g_kwh": 620.0,
            "avg_fuel_flow_kg_h": round(avg_fuel_kg_nm * avg_sog_kn, 6),
            "avg_fuel_kg_nm": avg_fuel_kg_nm,
            "avg_sog_kn": avg_sog_kn,
            "avg_stw_kn": max(avg_sog_kn - 0.3, 0.0),
            "avg_rpm": 72.0 + ((avg_engine_load_pct - 55.0) * 0.2),
            "avg_engine_load_pct": avg_engine_load_pct,
            "avg_shaft_power_kw": avg_shaft_power_kw,
            "avg_draft_m": 9.4,
            "avg_trim_m": 0.3,
            "avg_wind_speed_kn": avg_wind_speed_kn,
            "avg_relative_wind_angle_deg": 18.0,
            "avg_wave_height_m": avg_wave_height_m,
            "avg_depth_m": 34.0,
            "avg_ukc_m": 24.6,
            "avg_fouling_multiplier": 1.02 + ((avg_engine_load_pct - 55.0) / 500.0),
            "fuel_type": "MGO_PROXY",
            "is_valid_window": True,
            "window_quality_score": 95.0,
            "invalid_reasons_json": "[]",
        }
    )


def seed_training_windows() -> None:
    start = datetime(2026, 6, 28, 0, 0, tzinfo=timezone.utc)
    vessel_ids = ["NODE-ML-0001", "NODE-ML-0002", "NODE-ML-0003"]
    for vessel_index, vessel_id in enumerate(vessel_ids):
        for index in range(12):
            speed = 11.2 + ((index + vessel_index) % 4) * 0.8
            engine_load = 55.0 + (index % 5) * 6.0
            shaft_power = 7600.0 + (index * 220.0) + (vessel_index * 150.0)
            wind_speed = 12.0 + ((index + vessel_index) % 4) * 2.0
            wave_height = 0.8 + (index % 3) * 0.5
            fuel_kg_nm = 20.0 + (speed * 0.7) + (engine_load * 0.08) + (wave_height * 1.5)
            co2_kg_nm = round((fuel_kg_nm * 3.114) + (wind_speed * 0.2), 6)
            timestamp = start + timedelta(minutes=((vessel_index * 100) + index) * 15)
            loading_condition = "laden" if vessel_index % 2 == 0 else "ballast"
            state_bucket = f"sea_passage|{loading_condition}|speed_{int(speed)}_{int(speed)+2}|load_50_70|cross_wind_5_15|wave_1_2m|deep_water|moderate_fouling"
            create_ml_window(
                vessel_id=vessel_id,
                window_uuid=f"{vessel_id}-{index}",
                window_start_utc=timestamp.isoformat().replace("+00:00", "Z"),
                avg_co2_kg_nm=co2_kg_nm,
                avg_fuel_kg_nm=round(fuel_kg_nm, 6),
                avg_sog_kn=round(speed, 6),
                avg_engine_load_pct=round(engine_load, 6),
                avg_shaft_power_kw=round(shaft_power, 6),
                avg_wind_speed_kn=round(wind_speed, 6),
                avg_wave_height_m=round(wave_height, 6),
                state_bucket=state_bucket,
            )


def test_build_ml_training_dataset(temp_db_url: str) -> None:
    seed_training_windows()
    dataset = build_ml_training_dataset()
    assert len(dataset["rows"]) == 36
    assert len(dataset["features"]) == 36
    assert dataset["target_column"] == "avg_co2_kg_nm"
    assert "vessel_id" in dataset["feature_columns"]


def test_train_expected_co2_model(temp_db_url: str, temp_model_dir: Path) -> None:
    seed_training_windows()
    summary = train_expected_co2_model()
    assert summary["model_type"] == "RandomForestRegressor"
    assert summary["train_rows"] > 0
    assert summary["test_rows"] > 0
    assert Path(summary["model_path"]).exists()


def test_model_metadata_saved(temp_db_url: str, temp_model_dir: Path) -> None:
    seed_training_windows()
    train_expected_co2_model()
    metadata = load_model_metadata()
    assert metadata is not None
    assert metadata["model_version"]
    assert Path(metadata["metadata_path"]).exists()


def test_predict_expected_co2_for_windows(temp_db_url: str, temp_model_dir: Path) -> None:
    seed_training_windows()
    train_expected_co2_model()
    summary = predict_expected_co2_for_windows(limit=100)
    assert summary["predictions_created"] == 36
    predictions = get_ml_predictions(limit=100)
    assert len(predictions) == 36


def test_ml_gap_classification() -> None:
    assert classify_ml_gap(-4.0) == "ml_better"
    assert classify_ml_gap(0.0) == "ml_normal"
    assert classify_ml_gap(6.0) == "ml_worse"


def test_ml_train_api(client, temp_model_dir: Path) -> None:
    seed_training_windows()
    response = client.post("/ml/train")
    assert response.status_code == 200
    assert response.json()["model_type"] == "RandomForestRegressor"


def test_ml_model_metadata_api(client, temp_model_dir: Path) -> None:
    seed_training_windows()
    client.post("/ml/train")
    response = client.get("/ml/model-metadata")
    assert response.status_code == 200
    assert response.json()["model_version"]


def test_ml_predict_api(client, temp_model_dir: Path) -> None:
    seed_training_windows()
    client.post("/ml/train")
    response = client.post("/ml/predict", params={"limit": 100})
    assert response.status_code == 200
    assert response.json()["predictions_created"] == 36


def test_ml_predictions_latest_api(client, temp_model_dir: Path) -> None:
    seed_training_windows()
    client.post("/ml/train")
    client.post("/ml/predict", params={"limit": 100})
    response = client.get("/ml/predictions/latest")
    assert response.status_code == 200
    assert response.json()["prediction_status"] == "completed"


def test_ml_predictions_summary_api(client, temp_model_dir: Path) -> None:
    seed_training_windows()
    client.post("/ml/train")
    client.post("/ml/predict", params={"limit": 100})
    response = client.get("/ml/summary")
    assert response.status_code == 200
    assert response.json()["total_predictions"] == 36


def test_train_expected_co2_model_script(temp_db_url: str, temp_model_dir: Path) -> None:
    seed_training_windows()
    from scripts.train_expected_co2_model import main

    # Script smoke is covered by running the main entrypoint with argparse defaults patched via sys.argv.
    import sys
    original_argv = sys.argv[:]
    try:
        sys.argv = ["train_expected_co2_model.py"]
        main()
    finally:
        sys.argv = original_argv
    assert load_model_metadata() is not None


def test_predict_expected_co2_script(temp_db_url: str, temp_model_dir: Path) -> None:
    seed_training_windows()
    train_expected_co2_model()
    from scripts.predict_expected_co2 import main

    import sys
    original_argv = sys.argv[:]
    try:
        sys.argv = ["predict_expected_co2.py", "--limit", "100"]
        main()
    finally:
        sys.argv = original_argv
    assert get_latest_ml_prediction() is not None


def test_export_ml_predictions_csv_script(temp_db_url: str, temp_model_dir: Path) -> None:
    seed_training_windows()
    train_expected_co2_model()
    predict_expected_co2_for_windows(limit=100)
    tmp_dir = make_workspace_temp_dir("ml_export_")
    try:
        output_path = tmp_dir / "ml_predictions.csv"
        summary = export_ml_predictions_csv(output_path=output_path, limit=100)
        assert summary["rows_written"] == 36
        with output_path.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        assert rows[0]["classification"]
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
