from __future__ import annotations

import os
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from simulator_core.enrichment import enrich_simulator_batch


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
        candidate = base_dir / f"case_{index}"
        if not candidate.exists():
            candidate.mkdir(parents=True, exist_ok=False)
            return candidate
        index += 1


@pytest.fixture
def raw_batch() -> dict:
    return {
        "batch_id": "batch-001",
        "gateway_uid": "GW-BALTIC-0001",
        "items": [
            sample_telemetry(),
            sample_telemetry()
            | {
                "timestamp_utc": "2026-06-28T10:12:00Z",
                "node_id": "NODE-BALTIC-0002",
                "vessel_name": "Container Vessel 2",
                "imo_number": "9387422",
                "confidence_score": 60,
            },
        ],
    }


@pytest.fixture
def enriched_batch(raw_batch: dict) -> dict:
    return enrich_simulator_batch(raw_batch)


@pytest.fixture
def window_history_batch() -> dict:
    return make_series_batch(window_co2_kg_nm_values=[80.0, 82.0, 78.0, 79.0, 81.0, 90.0])


@pytest.fixture
def window_history_enriched_batch(window_history_batch: dict) -> dict:
    return enrich_simulator_batch(window_history_batch)


@pytest.fixture
def temp_db_url() -> str:
    tmp_dir = make_workspace_temp_dir()
    db_path = tmp_dir / "emission_eye_test.sqlite3"
    os.environ["EMISSION_EYE_DB_URL"] = f"sqlite:///{db_path.as_posix()}"
    yield os.environ["EMISSION_EYE_DB_URL"]
    os.environ.pop("EMISSION_EYE_DB_URL", None)
    shutil.rmtree(tmp_dir, ignore_errors=True)


@pytest.fixture
def client(temp_db_url: str):
    from fastapi.testclient import TestClient

    from app.database import dispose_db, init_db
    from app.main import app

    dispose_db()
    init_db()
    with TestClient(app) as test_client:
        yield test_client
    dispose_db()
