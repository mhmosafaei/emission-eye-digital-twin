from __future__ import annotations

import csv
import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.analytics import (
    get_baseline_trend,
    get_worst_baseline_windows,
    rank_vessels_by_baseline_performance,
    summarize_possible_causes,
    summarize_vessel_baseline_performance,
)
from simulator_core.enrichment import enrich_simulator_batch
from app.baseline import compare_window_to_baseline, find_similar_historical_windows, run_baseline_comparisons_with_options
from app.repositories import (
    create_baseline_comparison,
    create_enriched_batch,
    create_performance_window,
    get_baseline_comparisons,
)
from app.windowing import aggregate_feature_rows_to_window, create_performance_windows_from_feature_rows
from scripts.build_windows import build_windows
from scripts.export_analytics_summary import export_analytics_summary
from scripts.export_baseline_comparisons_csv import export_baseline_comparisons_csv
from scripts.export_worst_windows_csv import export_worst_windows_csv
from scripts.export_windows_csv import export_windows_csv
from scripts.diagnose_windows import diagnose_windows
from scripts.run_baseline_comparison import run_baseline


def sample_telemetry() -> dict:
    return {
        "timestamp_utc": "2026-06-28T10:00:00Z",
        "node_id": "NODE-BALTIC-0001",
        "vessel_name": "Container Vessel 1",
        "imo_number": "9387421",
        "mmsi": "230123000",
        "vessel_type": "ContainerVessel",
        "gateway_uid": "GW-BALTIC-0001",
        "vessel_mode": "Steaming",
        "speed_over_ground": 13.2,
        "course_over_ground": 82.4,
        "lat": 65.55,
        "lon": 22.25,
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


def make_series_batch(
    *,
    vessel_id: str = "NODE-BALTIC-0001",
    vessel_name: str = "Container Vessel 1",
    imo_number: str = "9387421",
    start_time: str = "2026-06-28T00:00:00Z",
    window_co2_kg_nm_values: list[float] | None = None,
    samples_per_window: int = 2,
    sample_spacing_minutes: int = 5,
) -> dict:
    window_co2_kg_nm_values = window_co2_kg_nm_values or [80.0, 82.0, 78.0]
    start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00")).astimezone(timezone.utc)
    items = []
    for window_index, co2_kg_nm in enumerate(window_co2_kg_nm_values):
        window_start = start_dt + timedelta(minutes=window_index * 15)
        for sample_index in range(samples_per_window):
            timestamp = window_start + timedelta(minutes=sample_index * sample_spacing_minutes)
            shaft_power_kw = 9000.0 + (window_index * 150.0) + (sample_index * 25.0)
            co2_kg_h = co2_kg_nm * 12.0
            fuel_flow_kg_h = co2_kg_h / 3.114
            item = sample_telemetry() | {
                "timestamp_utc": timestamp.isoformat().replace("+00:00", "Z"),
                "node_id": vessel_id,
                "vessel_name": vessel_name,
                "imo_number": imo_number,
                "distance_from_previous_nm": 1.0,
                "co2_mass_step_kg": co2_kg_nm,
                "co2_value": round(co2_kg_h, 6),
                "fuel_burn_step_kg": round(co2_kg_nm / 3.2, 6),
                "fuel_burn_rate": round(fuel_flow_kg_h, 6),
                "required_power_kw": shaft_power_kw,
                "speed_over_ground": 12.0 + (window_index % 2) * 0.4,
                "quality_flags": sample_telemetry()["quality_flags"] | {"shaft_power_kw": shaft_power_kw},
            }
            items.append(item)
    return {
        "batch_id": f"batch-{vessel_id}",
        "gateway_uid": "GW-BALTIC-0001",
        "items": items,
    }


def make_workspace_temp_dir() -> Path:
    base_dir = Path("C:\\Users\\nedan\\Downloads\\Projects\\New Digital Twin Project\\test_artifacts")
    base_dir.mkdir(parents=True, exist_ok=True)
    index = 0
    while True:
        candidate = base_dir / f"baseline_case_{index}"
        if not candidate.exists():
            candidate.mkdir(parents=True, exist_ok=False)
            return candidate
        index += 1


def create_completed_comparison(
    *,
    vessel_id: str,
    window_uuid: str,
    window_start_utc: str,
    performance_gap_pct: float,
    fuel_gap_pct: float | None = None,
    classification: str = "normal",
    possible_causes: list[str] | None = None,
    state_bucket: str = "sea_passage|laden|speed_12_14|load_50_70|head_wind_15_25|wave_1_2m|deep_water|moderate_fouling",
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
            "valid_sample_count": 3,
            "training_valid_rate": 1.0,
            "operation_mode": "sea_passage",
            "dominant_state_bucket": state_bucket,
            "state_bucket_confidence": 1.0,
            "avg_co2_kg_h": 960.0,
            "avg_co2_kg_nm": round(80.0 * (1.0 + (performance_gap_pct / 100.0)), 6),
            "avg_co2_g_kwh": 620.0,
            "avg_fuel_flow_kg_h": 300.0,
            "avg_fuel_kg_nm": round(25.0 * (1.0 + (((fuel_gap_pct if fuel_gap_pct is not None else performance_gap_pct) / 100.0))), 6),
            "avg_sog_kn": 12.4,
            "avg_stw_kn": 12.0,
            "avg_rpm": 74.0,
            "avg_engine_load_pct": 63.0,
            "avg_shaft_power_kw": 9000.0,
            "avg_draft_m": 9.4,
            "avg_trim_m": 1.7 if "possible_trim_issue" in (possible_causes or []) else 0.3,
            "avg_wind_speed_kn": 21.0 if "high_wind" in (possible_causes or []) else 19.0,
            "avg_relative_wind_angle_deg": 18.0,
            "avg_wave_height_m": 2.7 if "high_wave" in (possible_causes or []) else 1.6,
            "avg_depth_m": 20.0 if "shallow_water_effect" in (possible_causes or []) else 34.0,
            "avg_ukc_m": 10.0,
            "avg_fouling_multiplier": 1.1 if "high_fouling" in (possible_causes or []) else 1.04,
            "fuel_type": "MGO_PROXY",
            "is_valid_window": True,
            "window_quality_score": 95.0,
            "invalid_reasons_json": "[]",
        }
    )
    current_co2 = round(80.0 * (1.0 + (performance_gap_pct / 100.0)), 6)
    current_fuel = round(25.0 * (1.0 + (((fuel_gap_pct if fuel_gap_pct is not None else performance_gap_pct) / 100.0))), 6)
    advisor_payload = {
        "severity": "critical" if classification == "worse" and performance_gap_pct > 15.0 else ("warning" if classification == "worse" else "info"),
        "headline": "Synthetic advisor payload",
        "crew_message": f"Synthetic crew message for {classification}.",
        "recommended_checks": ["trim optimization", "RPM/load balance"],
        "possible_causes": possible_causes or [],
        "commercial_impact_hint": "Synthetic impact hint.",
    }
    create_baseline_comparison(
        {
            "comparison_uuid": f"cmp-{window_uuid}",
            "window_id": window.id,
            "vessel_id": vessel_id,
            "state_bucket": state_bucket,
            "comparison_status": "completed",
            "current_co2_kg_nm": current_co2,
            "baseline_co2_kg_nm": 80.0,
            "performance_gap_pct": performance_gap_pct,
            "current_fuel_kg_nm": current_fuel,
            "baseline_fuel_kg_nm": 25.0,
            "fuel_gap_pct": fuel_gap_pct if fuel_gap_pct is not None else performance_gap_pct,
            "similar_windows_count": 6,
            "baseline_confidence": baseline_confidence,
            "baseline_window_start_utc": "2026-06-27T00:00:00Z",
            "baseline_window_id": 1,
            "classification": classification,
            "crew_message": advisor_payload["crew_message"],
            "possible_causes_json": json.dumps(possible_causes or []),
            "advisor_json": json.dumps(advisor_payload),
        }
    )


def test_build_performance_windows_from_feature_rows(temp_db_url: str, window_history_enriched_batch: dict) -> None:
    create_enriched_batch(window_history_enriched_batch)
    windows = create_performance_windows_from_feature_rows(window_minutes=15)
    assert len(windows) == 6


def test_window_dominant_state_bucket(temp_db_url: str, window_history_enriched_batch: dict) -> None:
    create_enriched_batch(window_history_enriched_batch)
    windows = create_performance_windows_from_feature_rows(window_minutes=15)
    assert windows[0].dominant_state_bucket is not None
    assert windows[0].dominant_state_bucket.startswith("sea_passage|")


def test_window_quality_score(temp_db_url: str, window_history_enriched_batch: dict) -> None:
    create_enriched_batch(window_history_enriched_batch)
    windows = create_performance_windows_from_feature_rows(window_minutes=15)
    assert windows[0].window_quality_score is not None
    assert 0.0 <= windows[0].window_quality_score <= 100.0


def test_invalid_window_rules(temp_db_url: str) -> None:
    batch = make_series_batch(window_co2_kg_nm_values=[80.0], samples_per_window=1)
    create_enriched_batch(enrich_simulator_batch(batch))
    windows = create_performance_windows_from_feature_rows(window_minutes=15)
    assert len(windows) == 1
    assert windows[0].is_valid_window is False


def test_invalid_window_reasons_are_stored(temp_db_url: str) -> None:
    batch = make_series_batch(window_co2_kg_nm_values=[80.0], samples_per_window=1)
    create_enriched_batch(enrich_simulator_batch(batch))
    windows = create_performance_windows_from_feature_rows(window_minutes=15)
    reasons = json.loads(windows[0].invalid_reasons_json or "[]")
    assert "sample_count_below_minimum" in reasons


def test_find_similar_historical_windows(temp_db_url: str, window_history_enriched_batch: dict) -> None:
    create_enriched_batch(window_history_enriched_batch)
    windows = create_performance_windows_from_feature_rows(window_minutes=15)
    current = windows[-1]
    similar = find_similar_historical_windows(
        vessel_id=current.vessel_id,
        state_bucket=current.dominant_state_bucket or "",
        before_time=current.window_start_utc,
        limit=100,
    )
    assert len(similar) == 5


def test_baseline_insufficient_history(temp_db_url: str) -> None:
    batch = make_series_batch(window_co2_kg_nm_values=[80.0, 82.0], samples_per_window=2)
    enriched_batch = enrich_simulator_batch(batch)
    create_enriched_batch(enriched_batch)
    windows = create_performance_windows_from_feature_rows(window_minutes=15)
    comparison = compare_window_to_baseline(windows[-1])
    assert comparison.classification == "insufficient_history"


def test_baseline_better_normal_worse_classification(temp_db_url: str) -> None:
    historical_windows = [
        create_performance_window(
            {
                "window_uuid": f"hist-{index}",
                "vessel_id": "NODE-BALTIC-0001",
                "window_start_utc": f"2026-06-28T0{index}:00:00Z",
                "window_end_utc": f"2026-06-28T0{index}:15:00Z",
                "sample_count": 2,
                "valid_sample_count": 2,
                "training_valid_rate": 1.0,
                "operation_mode": "sea_passage",
                "dominant_state_bucket": "sea_passage|laden|speed_12_14|load_50_70|head_wind_15_25|wave_1_2m|deep_water|moderate_fouling",
                "state_bucket_confidence": 1.0,
                "avg_co2_kg_h": 950.0,
                "avg_co2_kg_nm": value,
                "avg_co2_g_kwh": 620.0,
                "avg_fuel_flow_kg_h": 305.0,
                "avg_fuel_kg_nm": value / 3.2,
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
                "is_valid_window": True,
                "window_quality_score": 92.0,
            }
        )
        for index, value in enumerate([80.0, 82.0, 78.0, 79.0, 81.0], start=1)
    ]

    state_bucket = historical_windows[0].dominant_state_bucket
    better_window = create_performance_window(
        {
            "window_uuid": "current-better",
            "vessel_id": "NODE-BALTIC-0001",
            "window_start_utc": "2026-06-28T06:00:00Z",
            "window_end_utc": "2026-06-28T06:15:00Z",
            "sample_count": 2,
            "valid_sample_count": 2,
            "training_valid_rate": 1.0,
            "operation_mode": "sea_passage",
            "dominant_state_bucket": state_bucket,
            "state_bucket_confidence": 1.0,
            "avg_co2_kg_h": 900.0,
            "avg_co2_kg_nm": 76.0,
            "avg_co2_g_kwh": 610.0,
            "avg_fuel_flow_kg_h": 290.0,
            "avg_fuel_kg_nm": 23.75,
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
            "is_valid_window": True,
            "window_quality_score": 95.0,
        }
    )
    normal_window = create_performance_window({**{k: getattr(better_window, k) for k in better_window.__table__.columns.keys() if k != "id"}, "window_uuid": "current-normal", "window_start_utc": "2026-06-28T06:15:00Z", "window_end_utc": "2026-06-28T06:30:00Z", "avg_co2_kg_nm": 80.5, "avg_fuel_kg_nm": 25.15})
    worse_window = create_performance_window({**{k: getattr(better_window, k) for k in better_window.__table__.columns.keys() if k != "id"}, "window_uuid": "current-worse", "window_start_utc": "2026-06-28T06:30:00Z", "window_end_utc": "2026-06-28T06:45:00Z", "avg_co2_kg_nm": 86.0, "avg_fuel_kg_nm": 26.9})

    assert compare_window_to_baseline(better_window).classification == "better"
    assert compare_window_to_baseline(normal_window).classification == "normal"
    assert compare_window_to_baseline(worse_window).classification == "worse"


def test_baseline_comparison_api(client, window_history_enriched_batch: dict) -> None:
    client.post("/ingest/enriched-batch", json=window_history_enriched_batch)
    build_response = client.post("/windows/build", json={"window_minutes": 15})
    assert build_response.status_code == 200
    response = client.post("/baseline/compare", json={"limit": 100})
    assert response.status_code == 200
    body = response.json()
    assert body["comparisons_created"] >= 1


def test_windows_api(client, window_history_enriched_batch: dict) -> None:
    client.post("/ingest/enriched-batch", json=window_history_enriched_batch)
    client.post("/windows/build", json={"window_minutes": 15})
    response = client.get("/windows", params={"valid_only": True})
    assert response.status_code == 200
    rows = response.json()
    assert rows
    assert rows[0]["operation_mode"] == "sea_passage"


def test_baseline_summary_api(client, window_history_enriched_batch: dict) -> None:
    client.post("/ingest/enriched-batch", json=window_history_enriched_batch)
    client.post("/windows/build", json={"window_minutes": 15})
    client.post("/baseline/compare", json={"limit": 100})
    response = client.get("/baseline/summary")
    assert response.status_code == 200
    body = response.json()
    assert body["total_comparisons"] >= 1


def test_run_baseline_comparison_defaults_to_valid_windows_only(temp_db_url: str, window_history_enriched_batch: dict) -> None:
    create_enriched_batch(window_history_enriched_batch)
    invalid_batch = make_series_batch(window_co2_kg_nm_values=[80.0], samples_per_window=1)
    create_enriched_batch(enrich_simulator_batch(invalid_batch))
    build_windows(window_minutes=15)
    summary = run_baseline(limit=100)
    assert summary["invalid_window"] == 0


def test_run_baseline_comparison_can_include_invalid_windows(temp_db_url: str, window_history_enriched_batch: dict) -> None:
    create_enriched_batch(window_history_enriched_batch)
    invalid_batch = make_series_batch(
        vessel_id="NODE-INVALID-0001",
        vessel_name="Invalid Window Vessel",
        imo_number="9990001",
        start_time="2026-06-29T00:00:00Z",
        window_co2_kg_nm_values=[80.0],
        samples_per_window=1,
    )
    create_enriched_batch(enrich_simulator_batch(invalid_batch))
    build_windows(window_minutes=15)
    summary = run_baseline(limit=100, valid_windows_only=False)
    assert summary["invalid_window"] >= 1


def test_latest_completed_baseline_endpoint(client, window_history_enriched_batch: dict) -> None:
    client.post("/ingest/enriched-batch", json=window_history_enriched_batch)
    client.post("/windows/build", json={"window_minutes": 15})
    client.post("/baseline/compare", json={"limit": 100})
    response = client.get("/baseline/latest-completed")
    assert response.status_code == 200
    body = response.json()
    assert body["classification"] in {"better", "normal", "worse"}


def test_baseline_comparisons_status_completed_filter(client, window_history_enriched_batch: dict) -> None:
    client.post("/ingest/enriched-batch", json=window_history_enriched_batch)
    client.post("/windows/build", json={"window_minutes": 15})
    client.post("/baseline/compare", json={"limit": 100, "valid_windows_only": False})
    response = client.get("/baseline/comparisons", params={"status": "completed", "limit": 100})
    assert response.status_code == 200
    rows = response.json()
    assert rows
    assert all(row["comparison_status"] == "completed" for row in rows)


def test_baseline_comparisons_valid_only_filter(client, window_history_enriched_batch: dict) -> None:
    client.post("/ingest/enriched-batch", json=window_history_enriched_batch)
    client.post("/windows/build", json={"window_minutes": 15})
    client.post("/baseline/compare", json={"limit": 100, "valid_windows_only": False})
    response = client.get("/baseline/comparisons", params={"valid_only": True, "limit": 100})
    assert response.status_code == 200
    rows = response.json()
    assert rows
    assert all(row["classification"] in {"better", "normal", "worse"} for row in rows)


def test_build_windows_script(temp_db_url: str, window_history_enriched_batch: dict) -> None:
    create_enriched_batch(window_history_enriched_batch)
    summary = build_windows(window_minutes=15)
    assert summary["windows_created"] == 6


def test_run_baseline_comparison_script(temp_db_url: str, window_history_enriched_batch: dict) -> None:
    create_enriched_batch(window_history_enriched_batch)
    build_windows(window_minutes=15)
    summary = run_baseline(limit=100)
    assert summary["comparisons_created"] == 6


def test_export_baseline_comparisons_csv_script(temp_db_url: str, window_history_enriched_batch: dict) -> None:
    create_enriched_batch(window_history_enriched_batch)
    build_windows(window_minutes=15)
    run_baseline(limit=100)
    tmp_path = make_workspace_temp_dir()
    try:
        output_path = tmp_path / "baseline.csv"
        summary = export_baseline_comparisons_csv(output_path=output_path, limit=100)
        assert summary["rows_written"] == 6
        with output_path.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        assert rows[0]["classification"]
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_diagnose_windows_script(temp_db_url: str, window_history_enriched_batch: dict) -> None:
    create_enriched_batch(window_history_enriched_batch)
    invalid_batch = make_series_batch(window_co2_kg_nm_values=[80.0], samples_per_window=1)
    create_enriched_batch(enrich_simulator_batch(invalid_batch))
    build_windows(window_minutes=15)
    summary = diagnose_windows(sea_passage_only=True)
    assert summary["total_windows"] >= 1
    assert "invalid_reasons_count" in summary


def test_export_windows_csv_script(temp_db_url: str, window_history_enriched_batch: dict) -> None:
    create_enriched_batch(window_history_enriched_batch)
    build_windows(window_minutes=15)
    tmp_path = make_workspace_temp_dir()
    try:
        output_path = tmp_path / "windows.csv"
        summary = export_windows_csv(output_path=output_path, sea_passage_only=True, limit=100)
        assert summary["rows_written"] >= 1
        with output_path.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        assert "invalid_reasons_json" in rows[0]
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_vessel_baseline_summary(temp_db_url: str) -> None:
    create_completed_comparison(
        vessel_id="NODE-ARCTIC-0003",
        window_uuid="summary-1",
        window_start_utc="2026-06-28T00:00:00Z",
        performance_gap_pct=8.0,
        fuel_gap_pct=5.0,
        classification="worse",
        possible_causes=["high_fouling", "high_engine_load"],
    )
    create_completed_comparison(
        vessel_id="NODE-ARCTIC-0003",
        window_uuid="summary-2",
        window_start_utc="2026-06-28T00:15:00Z",
        performance_gap_pct=4.0,
        fuel_gap_pct=3.0,
        classification="normal",
        possible_causes=["high_fouling"],
    )
    create_completed_comparison(
        vessel_id="NODE-ARCTIC-0003",
        window_uuid="summary-3",
        window_start_utc="2026-06-28T00:30:00Z",
        performance_gap_pct=-3.0,
        fuel_gap_pct=-2.0,
        classification="better",
        possible_causes=[],
    )
    summary = summarize_vessel_baseline_performance(vessel_id="NODE-ARCTIC-0003")
    assert summary["completed_comparisons"] == 3
    assert summary["worse"] == 1
    assert summary["dominant_classification"] in {"better", "normal", "worse"}
    assert summary["top_possible_causes"][0]["cause"] == "high_fouling"


def test_worst_windows_are_completed_only(temp_db_url: str) -> None:
    create_completed_comparison(
        vessel_id="NODE-ARCTIC-0003",
        window_uuid="worst-1",
        window_start_utc="2026-06-28T01:00:00Z",
        performance_gap_pct=16.0,
        classification="worse",
        possible_causes=["high_fouling"],
    )
    create_completed_comparison(
        vessel_id="NODE-ARCTIC-0003",
        window_uuid="worst-2",
        window_start_utc="2026-06-28T01:15:00Z",
        performance_gap_pct=3.0,
        classification="normal",
        possible_causes=["high_engine_load"],
    )
    rows = get_worst_baseline_windows(vessel_id="NODE-ARCTIC-0003", limit=10)
    assert rows
    assert rows[0]["performance_gap_pct"] >= rows[-1]["performance_gap_pct"]
    assert all(row["classification"] in {"better", "normal", "worse"} for row in rows)


def test_trend_direction_insufficient_data(temp_db_url: str) -> None:
    create_completed_comparison(
        vessel_id="NODE-TREND-0001",
        window_uuid="trend-short-1",
        window_start_utc="2026-06-28T02:00:00Z",
        performance_gap_pct=5.0,
        classification="worse",
    )
    create_completed_comparison(
        vessel_id="NODE-TREND-0001",
        window_uuid="trend-short-2",
        window_start_utc="2026-06-28T02:15:00Z",
        performance_gap_pct=4.0,
        classification="normal",
    )
    trend = get_baseline_trend(vessel_id="NODE-TREND-0001")
    assert trend["trend_direction"] == "insufficient_data"


def test_trend_direction_improving_worsening_stable(temp_db_url: str) -> None:
    for index, gap in enumerate([10.0, 8.0, 4.0, 2.0], start=1):
        create_completed_comparison(
            vessel_id="NODE-TREND-IMPROVING",
            window_uuid=f"trend-improving-{index}",
            window_start_utc=(datetime(2026, 6, 28, 3, 0, tzinfo=timezone.utc) + timedelta(minutes=(index - 1) * 15)).isoformat().replace("+00:00", "Z"),
            performance_gap_pct=gap,
            classification="worse" if gap > 5.0 else "normal",
        )
    for index, gap in enumerate([1.0, 2.0, 5.0, 7.0], start=1):
        create_completed_comparison(
            vessel_id="NODE-TREND-WORSENING",
            window_uuid=f"trend-worsening-{index}",
            window_start_utc=(datetime(2026, 6, 28, 4, 0, tzinfo=timezone.utc) + timedelta(minutes=(index - 1) * 15)).isoformat().replace("+00:00", "Z"),
            performance_gap_pct=gap,
            classification="worse" if gap > 5.0 else "normal",
        )
    for index, gap in enumerate([4.0, 3.5, 4.2, 3.8], start=1):
        create_completed_comparison(
            vessel_id="NODE-TREND-STABLE",
            window_uuid=f"trend-stable-{index}",
            window_start_utc=(datetime(2026, 6, 28, 5, 0, tzinfo=timezone.utc) + timedelta(minutes=(index - 1) * 15)).isoformat().replace("+00:00", "Z"),
            performance_gap_pct=gap,
            classification="normal",
        )
    assert get_baseline_trend(vessel_id="NODE-TREND-IMPROVING")["trend_direction"] == "improving"
    assert get_baseline_trend(vessel_id="NODE-TREND-WORSENING")["trend_direction"] == "worsening"
    assert get_baseline_trend(vessel_id="NODE-TREND-STABLE")["trend_direction"] == "stable"


def test_possible_cause_summary(temp_db_url: str) -> None:
    create_completed_comparison(
        vessel_id="NODE-CAUSE-0001",
        window_uuid="cause-1",
        window_start_utc="2026-06-28T06:00:00Z",
        performance_gap_pct=9.0,
        classification="worse",
        possible_causes=["high_fouling", "high_engine_load"],
    )
    create_completed_comparison(
        vessel_id="NODE-CAUSE-0001",
        window_uuid="cause-2",
        window_start_utc="2026-06-28T06:15:00Z",
        performance_gap_pct=6.0,
        classification="worse",
        possible_causes=["high_fouling"],
    )
    summary = summarize_possible_causes(vessel_id="NODE-CAUSE-0001")
    assert summary["comparisons_with_causes"] == 2
    assert summary["top_possible_causes"][0] == {"cause": "high_fouling", "count": 2}


def test_fleet_ranking(temp_db_url: str) -> None:
    create_completed_comparison(
        vessel_id="NODE-FLEET-WORSE",
        window_uuid="fleet-1",
        window_start_utc="2026-06-28T07:00:00Z",
        performance_gap_pct=12.0,
        classification="worse",
    )
    create_completed_comparison(
        vessel_id="NODE-FLEET-BETTER",
        window_uuid="fleet-2",
        window_start_utc="2026-06-28T07:15:00Z",
        performance_gap_pct=-4.0,
        classification="better",
    )
    ranking = rank_vessels_by_baseline_performance()
    assert ranking[0]["vessel_id"] == "NODE-FLEET-WORSE"


def test_advisor_severity_critical_for_large_worse_gap(temp_db_url: str) -> None:
    historical_windows = [
        create_performance_window(
            {
                "window_uuid": f"severity-hist-{index}",
                "vessel_id": "NODE-SEVERITY-0001",
                "window_start_utc": f"2026-06-28T0{index}:00:00Z",
                "window_end_utc": f"2026-06-28T0{index}:15:00Z",
                "sample_count": 3,
                "valid_sample_count": 3,
                "training_valid_rate": 1.0,
                "operation_mode": "sea_passage",
                "dominant_state_bucket": "sea_passage|laden|speed_12_14|load_50_70|head_wind_15_25|wave_1_2m|deep_water|moderate_fouling",
                "state_bucket_confidence": 1.0,
                "avg_co2_kg_h": 960.0,
                "avg_co2_kg_nm": value,
                "avg_co2_g_kwh": 620.0,
                "avg_fuel_flow_kg_h": 305.0,
                "avg_fuel_kg_nm": value / 3.2,
                "avg_sog_kn": 12.4,
                "avg_stw_kn": 10.8,
                "avg_rpm": 74.0,
                "avg_engine_load_pct": 80.0,
                "avg_shaft_power_kw": 9200.0,
                "avg_draft_m": 9.4,
                "avg_trim_m": 1.8,
                "avg_wind_speed_kn": 22.0,
                "avg_relative_wind_angle_deg": 18.0,
                "avg_wave_height_m": 2.8,
                "avg_depth_m": 34.0,
                "avg_ukc_m": 24.6,
                "avg_fouling_multiplier": 1.1,
                "fuel_type": "MGO_PROXY",
                "is_valid_window": True,
                "window_quality_score": 92.0,
                "invalid_reasons_json": "[]",
            }
        )
        for index, value in enumerate([80.0, 81.0, 79.0, 82.0, 78.0], start=1)
    ]
    current_window = create_performance_window(
        {
            "window_uuid": "severity-current",
            "vessel_id": "NODE-SEVERITY-0001",
            "window_start_utc": "2026-06-28T06:00:00Z",
            "window_end_utc": "2026-06-28T06:15:00Z",
            "sample_count": 3,
            "valid_sample_count": 3,
            "training_valid_rate": 1.0,
            "operation_mode": "sea_passage",
            "dominant_state_bucket": historical_windows[0].dominant_state_bucket,
            "state_bucket_confidence": 1.0,
            "avg_co2_kg_h": 1160.0,
            "avg_co2_kg_nm": 96.0,
            "avg_co2_g_kwh": 640.0,
            "avg_fuel_flow_kg_h": 350.0,
            "avg_fuel_kg_nm": 30.0,
            "avg_sog_kn": 12.4,
            "avg_stw_kn": 10.8,
            "avg_rpm": 74.0,
            "avg_engine_load_pct": 80.0,
            "avg_shaft_power_kw": 9500.0,
            "avg_draft_m": 9.4,
            "avg_trim_m": 1.8,
            "avg_wind_speed_kn": 22.0,
            "avg_relative_wind_angle_deg": 18.0,
            "avg_wave_height_m": 2.8,
            "avg_depth_m": 34.0,
            "avg_ukc_m": 24.6,
            "avg_fouling_multiplier": 1.1,
            "fuel_type": "MGO_PROXY",
            "is_valid_window": True,
            "window_quality_score": 95.0,
            "invalid_reasons_json": "[]",
        }
    )
    comparison = compare_window_to_baseline(current_window)
    advisor = json.loads(comparison.advisor_json or "{}")
    assert comparison.classification == "worse"
    assert advisor["severity"] == "critical"
    assert advisor["recommended_checks"]


def test_analytics_vessel_summary_api(client) -> None:
    create_completed_comparison(
        vessel_id="NODE-API-0001",
        window_uuid="api-summary-1",
        window_start_utc="2026-06-28T08:00:00Z",
        performance_gap_pct=7.0,
        classification="worse",
        possible_causes=["high_fouling"],
    )
    response = client.get("/analytics/vessel-summary", params={"vessel_id": "NODE-API-0001"})
    assert response.status_code == 200
    assert response.json()["completed_comparisons"] == 1


def test_analytics_worst_windows_api(client) -> None:
    create_completed_comparison(
        vessel_id="NODE-API-0002",
        window_uuid="api-worst-1",
        window_start_utc="2026-06-28T08:15:00Z",
        performance_gap_pct=11.0,
        classification="worse",
        possible_causes=["high_engine_load"],
    )
    response = client.get("/analytics/worst-windows", params={"vessel_id": "NODE-API-0002", "limit": 10})
    assert response.status_code == 200
    body = response.json()
    assert body
    assert body[0]["classification"] in {"better", "normal", "worse"}


def test_analytics_trend_api(client) -> None:
    for index, gap in enumerate([9.0, 6.0, 3.0], start=1):
        create_completed_comparison(
            vessel_id="NODE-API-0003",
            window_uuid=f"api-trend-{index}",
            window_start_utc=(datetime(2026, 6, 28, 9, 0, tzinfo=timezone.utc) + timedelta(minutes=(index - 1) * 15)).isoformat().replace("+00:00", "Z"),
            performance_gap_pct=gap,
            classification="worse" if gap > 5.0 else "normal",
        )
    response = client.get("/analytics/trend", params={"vessel_id": "NODE-API-0003"})
    assert response.status_code == 200
    assert response.json()["trend_direction"] == "improving"


def test_analytics_causes_api(client) -> None:
    create_completed_comparison(
        vessel_id="NODE-API-0004",
        window_uuid="api-causes-1",
        window_start_utc="2026-06-28T10:00:00Z",
        performance_gap_pct=7.0,
        classification="worse",
        possible_causes=["high_fouling", "high_engine_load"],
    )
    response = client.get("/analytics/causes", params={"vessel_id": "NODE-API-0004"})
    assert response.status_code == 200
    assert response.json()["top_possible_causes"][0]["cause"] == "high_fouling"


def test_analytics_fleet_ranking_api(client) -> None:
    create_completed_comparison(
        vessel_id="NODE-API-RANK-1",
        window_uuid="api-rank-1",
        window_start_utc="2026-06-28T11:00:00Z",
        performance_gap_pct=10.0,
        classification="worse",
    )
    create_completed_comparison(
        vessel_id="NODE-API-RANK-2",
        window_uuid="api-rank-2",
        window_start_utc="2026-06-28T11:15:00Z",
        performance_gap_pct=-2.0,
        classification="better",
    )
    response = client.get("/analytics/fleet-ranking")
    assert response.status_code == 200
    assert response.json()[0]["vessel_id"] == "NODE-API-RANK-1"


def test_export_analytics_summary_script(temp_db_url: str) -> None:
    create_completed_comparison(
        vessel_id="NODE-EXPORT-0001",
        window_uuid="export-summary-1",
        window_start_utc="2026-06-28T12:00:00Z",
        performance_gap_pct=6.0,
        classification="worse",
        possible_causes=["high_fouling"],
    )
    tmp_path = make_workspace_temp_dir()
    try:
        output_path = tmp_path / "analytics_summary.json"
        summary = export_analytics_summary(output_path=output_path, vessel_id="NODE-EXPORT-0001")
        assert summary["sections_written"] == 3
        payload = json.loads(output_path.read_text(encoding="utf-8"))
        assert payload["vessel_summary"]["completed_comparisons"] == 1
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_export_worst_windows_csv_script(temp_db_url: str) -> None:
    create_completed_comparison(
        vessel_id="NODE-EXPORT-0002",
        window_uuid="export-worst-1",
        window_start_utc="2026-06-28T12:15:00Z",
        performance_gap_pct=14.0,
        classification="worse",
        possible_causes=["high_engine_load"],
    )
    tmp_path = make_workspace_temp_dir()
    try:
        output_path = tmp_path / "worst_windows.csv"
        summary = export_worst_windows_csv(output_path=output_path, vessel_id="NODE-EXPORT-0002", limit=20)
        assert summary["rows_written"] == 1
        with output_path.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        assert rows[0]["possible_causes"]
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)
