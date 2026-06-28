from __future__ import annotations

import os
import shutil
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
