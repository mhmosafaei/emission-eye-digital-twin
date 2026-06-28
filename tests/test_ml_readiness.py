from __future__ import annotations

import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.ml_readiness import (
    calculate_ml_readiness_score,
    summarize_ml_readiness,
    summarize_state_bucket_repetition,
    summarize_vessel_training_coverage,
)
from app.repositories import create_baseline_comparison, create_performance_window
from scripts.build_demo_dataset import build_demo_dataset
from scripts.export_ml_readiness_report import export_ml_readiness_report


def make_workspace_temp_dir() -> Path:
    base_dir = Path("C:\\Users\\nedan\\Downloads\\Projects\\New Digital Twin Project\\test_artifacts")
    base_dir.mkdir(parents=True, exist_ok=True)
    index = 0
    while True:
        candidate = base_dir / f"ml_readiness_case_{index}"
        if not candidate.exists():
            candidate.mkdir(parents=True, exist_ok=False)
            return candidate
        index += 1


def create_window_with_optional_comparison(
    *,
    vessel_id: str,
    window_uuid: str,
    window_start_utc: str,
    state_bucket: str,
    valid_window: bool = True,
    completed_comparison: bool = False,
    performance_gap_pct: float = 4.0,
    baseline_confidence: float = 0.6,
) -> None:
    window = create_performance_window(
        {
            "window_uuid": window_uuid,
            "vessel_id": vessel_id,
            "window_start_utc": window_start_utc,
            "window_end_utc": (
                datetime.fromisoformat(window_start_utc.replace("Z", "+00:00")) + timedelta(minutes=15)
            ).isoformat().replace("+00:00", "Z"),
            "sample_count": 3,
            "valid_sample_count": 3 if valid_window else 1,
            "training_valid_rate": 1.0 if valid_window else 0.33,
            "operation_mode": "sea_passage",
            "dominant_state_bucket": state_bucket,
            "state_bucket_confidence": 1.0,
            "avg_co2_kg_h": 960.0,
            "avg_co2_kg_nm": 83.2 if valid_window else None,
            "avg_co2_g_kwh": 620.0,
            "avg_fuel_flow_kg_h": 300.0,
            "avg_fuel_kg_nm": 25.4 if valid_window else None,
            "avg_sog_kn": 12.4,
            "avg_stw_kn": 12.0,
            "avg_rpm": 74.0,
            "avg_engine_load_pct": 63.0,
            "avg_shaft_power_kw": 9000.0,
            "avg_draft_m": 9.4,
            "avg_trim_m": 0.3,
            "avg_wind_speed_kn": 19.0,
            "avg_relative_wind_angle_deg": 18.0,
            "avg_wave_height_m": 1.6,
            "avg_depth_m": 34.0,
            "avg_ukc_m": 24.6,
            "avg_fouling_multiplier": 1.04,
            "fuel_type": "MGO_PROXY",
            "is_valid_window": valid_window,
            "window_quality_score": 95.0 if valid_window else 40.0,
            "invalid_reasons_json": "[]" if valid_window else json.dumps(["sample_count_below_minimum"]),
        }
    )
    if completed_comparison:
        create_baseline_comparison(
            {
                "comparison_uuid": f"cmp-{window_uuid}",
                "window_id": window.id,
                "vessel_id": vessel_id,
                "state_bucket": state_bucket,
                "comparison_status": "completed",
                "current_co2_kg_nm": 83.2,
                "baseline_co2_kg_nm": 80.0,
                "performance_gap_pct": performance_gap_pct,
                "current_fuel_kg_nm": 25.4,
                "baseline_fuel_kg_nm": 24.8,
                "fuel_gap_pct": performance_gap_pct - 1.0,
                "similar_windows_count": 6,
                "baseline_confidence": baseline_confidence,
                "baseline_window_start_utc": "2026-06-27T00:00:00Z",
                "baseline_window_id": 1,
                "classification": "worse" if performance_gap_pct > 5.0 else "normal",
                "crew_message": "Synthetic ML readiness test comparison.",
                "possible_causes_json": json.dumps(["high_fouling"]),
                "advisor_json": json.dumps({"severity": "warning"}),
            }
        )


def seed_ml_ready_dataset() -> None:
    start = datetime(2026, 6, 28, 0, 0, tzinfo=timezone.utc)
    vessel_ids = ["NODE-READY-0001", "NODE-READY-0002", "NODE-READY-0003"]
    bucket_names = [f"sea_passage|bucket_{index:02d}" for index in range(10)]
    for vessel_offset, vessel_id in enumerate(vessel_ids):
        for bucket_index, bucket_name in enumerate(bucket_names):
            for repeat_index in range(10):
                timestamp = start + timedelta(minutes=((vessel_offset * 1000) + (bucket_index * 100) + repeat_index) * 15)
                create_window_with_optional_comparison(
                    vessel_id=vessel_id,
                    window_uuid=f"{vessel_id}-{bucket_index}-{repeat_index}",
                    window_start_utc=timestamp.isoformat().replace("+00:00", "Z"),
                    state_bucket=bucket_name,
                    valid_window=True,
                    completed_comparison=repeat_index < 4,
                    performance_gap_pct=6.0 + (repeat_index % 3),
                    baseline_confidence=0.6,
                )


def test_ml_readiness_summary_empty_db(temp_db_url: str) -> None:
    summary = summarize_ml_readiness()
    assert summary["readiness_level"] == "not_ready"
    assert summary["ml_ready"] is False
    assert summary["blocking_reasons"]


def test_ml_readiness_summary_not_ready_small_dataset(temp_db_url: str) -> None:
    create_window_with_optional_comparison(
        vessel_id="NODE-SMALL-0001",
        window_uuid="small-1",
        window_start_utc="2026-06-28T00:00:00Z",
        state_bucket="sea_passage|small_bucket",
        valid_window=True,
        completed_comparison=True,
        performance_gap_pct=4.0,
        baseline_confidence=0.4,
    )
    summary = summarize_ml_readiness()
    assert summary["valid_performance_windows"] == 1
    assert summary["readiness_level"] == "not_ready"


def test_ml_readiness_score_ready(temp_db_url: str) -> None:
    seed_ml_ready_dataset()
    score = calculate_ml_readiness_score()
    assert score["readiness_level"] == "ready"
    assert score["ml_ready"] is True
    assert score["readiness_score"] >= 75


def test_ml_readiness_score_borderline(temp_db_url: str) -> None:
    start = datetime(2026, 6, 28, 0, 0, tzinfo=timezone.utc)
    vessel_ids = ["NODE-BORDER-0001", "NODE-BORDER-0002", "NODE-BORDER-0003"]
    bucket_names = [f"sea_passage|border_bucket_{index:02d}" for index in range(10)]
    for vessel_offset, vessel_id in enumerate(vessel_ids):
        for bucket_index, bucket_name in enumerate(bucket_names):
            for repeat_index in range(5):
                timestamp = start + timedelta(minutes=((vessel_offset * 500) + (bucket_index * 50) + repeat_index) * 15)
                create_window_with_optional_comparison(
                    vessel_id=vessel_id,
                    window_uuid=f"{vessel_id}-{bucket_index}-{repeat_index}",
                    window_start_utc=timestamp.isoformat().replace("+00:00", "Z"),
                    state_bucket=bucket_name,
                    valid_window=True,
                    completed_comparison=repeat_index < 2,
                    performance_gap_pct=4.0,
                    baseline_confidence=0.4,
                )
    score = calculate_ml_readiness_score()
    assert score["readiness_level"] == "borderline"
    assert score["ml_ready"] is False


def test_ml_readiness_score_not_ready(temp_db_url: str) -> None:
    create_window_with_optional_comparison(
        vessel_id="NODE-NOTREADY-0001",
        window_uuid="notready-1",
        window_start_utc="2026-06-28T01:00:00Z",
        state_bucket="sea_passage|notready_bucket",
        valid_window=True,
        completed_comparison=False,
    )
    score = calculate_ml_readiness_score()
    assert score["readiness_level"] == "not_ready"
    assert score["readiness_score"] < 50


def test_state_bucket_repetition_counts(temp_db_url: str) -> None:
    for index in range(3):
        create_window_with_optional_comparison(
            vessel_id="NODE-BUCKET-0001",
            window_uuid=f"bucket-{index}",
            window_start_utc=(datetime(2026, 6, 28, 2, 0, tzinfo=timezone.utc) + timedelta(minutes=index * 15)).isoformat().replace("+00:00", "Z"),
            state_bucket="sea_passage|repeat_bucket",
            valid_window=True,
        )
    summary = summarize_state_bucket_repetition()
    assert summary["repeated_state_buckets"] >= 1
    assert summary["average_windows_per_repeated_bucket"] >= 3.0


def test_vessel_training_coverage(temp_db_url: str) -> None:
    for index in range(3):
        create_window_with_optional_comparison(
            vessel_id="NODE-COVERAGE-0001",
            window_uuid=f"coverage-{index}",
            window_start_utc=(datetime(2026, 6, 28, 3, 0, tzinfo=timezone.utc) + timedelta(minutes=index * 15)).isoformat().replace("+00:00", "Z"),
            state_bucket="sea_passage|coverage_bucket",
            valid_window=True,
            completed_comparison=True,
            performance_gap_pct=6.0,
            baseline_confidence=0.55,
        )
    coverage = summarize_vessel_training_coverage()
    assert coverage[0]["trend_ready"] is True
    assert coverage[0]["completed_comparisons"] == 3


def test_ml_readiness_summary_api(client) -> None:
    create_window_with_optional_comparison(
        vessel_id="NODE-API-ML-0001",
        window_uuid="api-ml-1",
        window_start_utc="2026-06-28T04:00:00Z",
        state_bucket="sea_passage|api_ml_bucket",
        valid_window=True,
        completed_comparison=True,
    )
    response = client.get("/ml-readiness/summary")
    assert response.status_code == 200
    assert "readiness_score" in response.json()


def test_ml_readiness_window_coverage_api(client) -> None:
    response = client.get("/ml-readiness/window-coverage")
    assert response.status_code == 200
    assert "valid_performance_windows" in response.json()


def test_ml_readiness_state_buckets_api(client) -> None:
    response = client.get("/ml-readiness/state-buckets")
    assert response.status_code == 200
    assert "repeated_state_buckets" in response.json()


def test_ml_readiness_vessels_api(client) -> None:
    create_window_with_optional_comparison(
        vessel_id="NODE-API-ML-0002",
        window_uuid="api-ml-2",
        window_start_utc="2026-06-28T04:15:00Z",
        state_bucket="sea_passage|api_ml_bucket_2",
        valid_window=True,
        completed_comparison=True,
    )
    response = client.get("/ml-readiness/vessels")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_export_ml_readiness_report_script(temp_db_url: str) -> None:
    create_window_with_optional_comparison(
        vessel_id="NODE-EXPORT-ML-0001",
        window_uuid="export-ml-1",
        window_start_utc="2026-06-28T05:00:00Z",
        state_bucket="sea_passage|export_ml_bucket",
        valid_window=True,
        completed_comparison=True,
    )
    tmp_path = make_workspace_temp_dir()
    try:
        output_path = tmp_path / "ml_readiness_report.json"
        summary = export_ml_readiness_report(output_path=output_path, pretty=True)
        assert summary["output_path"]
        payload = json.loads(output_path.read_text(encoding="utf-8"))
        assert "readiness_level" in payload
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_build_demo_dataset_script_smoke(monkeypatch, temp_db_url: str) -> None:
    calls: list[str] = []

    def record(name: str):
        def _inner(*args, **kwargs):
            calls.append(name)
            if name == "ml":
                return {"readiness_level": "borderline", "readiness_score": 55}
            return {}
        return _inner

    monkeypatch.setattr("scripts.build_demo_dataset.run_simulator_limited", record("run"))
    monkeypatch.setattr("scripts.build_demo_dataset.enrich_jsonl", record("enrich"))
    monkeypatch.setattr("scripts.build_demo_dataset.ingest_enriched_jsonl", record("ingest"))
    monkeypatch.setattr("scripts.build_demo_dataset.build_windows", record("windows"))
    monkeypatch.setattr("scripts.build_demo_dataset.run_baseline", record("baseline"))
    monkeypatch.setattr("scripts.build_demo_dataset.export_analytics_summary", record("analytics"))
    monkeypatch.setattr("scripts.build_demo_dataset.export_worst_windows_csv", record("worst"))
    monkeypatch.setattr("scripts.build_demo_dataset.export_ml_readiness_report", record("ml"))
    monkeypatch.setattr("scripts.build_demo_dataset.reset_local_db", record("reset"))

    summary = build_demo_dataset(batches=30, vessels=3, seed=42, reset_db=True, output_dir="data")
    assert calls == ["reset", "run", "enrich", "ingest", "windows", "baseline", "analytics", "worst", "ml"]
    assert summary["ml_readiness_export"]["readiness_level"] == "borderline"
