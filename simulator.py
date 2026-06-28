import csv
import hashlib
import json
import math
import os
import random
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Tuple

import requests

try:
    import h5py
except ImportError:
    h5py = None

try:
    import numpy as np
except ImportError:
    np = None


SIMULATOR_SEED = os.getenv("SIMULATOR_SEED", "").strip() or None
SIMULATOR_DRY_RUN_OUTPUT = os.getenv("SIMULATOR_DRY_RUN_OUTPUT", "").strip() or None
SIMULATOR_MODEL_MODE = os.getenv("SIMULATOR_MODEL_MODE", "admiralty_fast").strip() or "admiralty_fast"
SIMULATOR_VALIDATION_CSV = os.getenv("SIMULATOR_VALIDATION_CSV", "").strip() or None
SIMULATOR_SENSOR_ASSIMILATION_CSV = os.getenv("SIMULATOR_SENSOR_ASSIMILATION_CSV", "").strip() or None


def stable_seed_int(*parts: object) -> int:
    raw = "||".join(str(part) for part in parts).encode("utf-8")
    return int(hashlib.sha256(raw).hexdigest()[:16], 16)


REQUEST_TIMEOUT = 30
LOOP_SLEEP_SECONDS = 5
POINTS_PER_BATCH = 1
SIMULATED_MINUTES_PER_LOOP = 12

USE_AUTH_HEADERS = False
DEFAULT_GATEWAY_KEY = "replace-with-real-key-if-needed"
DEFAULT_FUEL_TYPE = "MGO_PROXY"
DEFAULT_SCRUBBER_ACTIVE = False
ENABLE_LNG_CARRIER = os.getenv("ENABLE_LNG_CARRIER", "false").strip().lower() in {"1", "true", "yes", "on"}

ENABLE_DEMO_MERKLE = True
if SIMULATOR_SEED:
    SEQ_BASE = 1_000_000 + (stable_seed_int("seq-base", SIMULATOR_SEED) % 1_000_000)
    START_SIM_TIME_UTC = datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(
        minutes=stable_seed_int("start-sim-time", SIMULATOR_SEED) % (14 * 24 * 60)
    )
else:
    SEQ_BASE = int(datetime.now(timezone.utc).timestamp() * 1000)
    START_SIM_TIME_UTC = datetime.now(timezone.utc) - timedelta(hours=2)

MANOEUVRING_DISTANCE_NM = 20.0
UKC_SAFETY_LIMIT_M = 3.0
MAX_SYNTHETIC_DEPTH_M = 100.0
MAX_UKC_SAFE_SPEED_KN = 6.0
HALF_RPM_PORT_DISTANCE_NM = 12.0
QUARTER_RPM_PORT_DISTANCE_NM = 6.0
STOPPED_PORT_DISTANCE_NM = 0.4
ANCHOR_LOCK_SPEED_KN = 0.1
FLOW_NOTICE_CHANNEL_DEFAULT = "12"

MODE_STOPPED = "Stopped"
MODE_MANOEUVRING_25 = "Manoeuvring (25% steaming RPM)"
MODE_MANOEUVRING_50 = "Manoeuvring (50% steaming RPM)"
MODE_STEAMING = "Steaming"
MODEL_MODE_ADMIRALTY_FAST = "admiralty_fast"
MODEL_MODE_PHYSICS_ENHANCED = "physics_enhanced"
SUPPORTED_MODEL_MODES = {MODEL_MODE_ADMIRALTY_FAST, MODEL_MODE_PHYSICS_ENHANCED}

CO2_EMISSION_FACTOR = 3.114
FOULING_CYCLE_DAYS = 180.0
BATHYMETRY_TILE_DIR = Path(os.getenv("BATHYMETRY_TILE_DIR", "./depth_tiles"))
SIMULATOR_OFFLINE_MODE = os.getenv("SIMULATOR_OFFLINE_MODE", "false").strip().lower() in {"1", "true", "yes", "on"}
FUNCTION_URL = os.getenv("SIMULATOR_FUNCTION_URL")
SIMULATOR_STATUS_URL = os.getenv("SIMULATOR_STATUS_URL")
SUPABASE_REST_URL = os.getenv("SIMULATOR_SUPABASE_URL") or os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = (
    os.getenv("SIMULATOR_SUPABASE_ANON_KEY")
    or os.getenv("SUPABASE_ANON_KEY")
    or os.getenv("VITE_SUPABASE_ANON_KEY")
)

MRV_MEDIAN_KG_CO2_PER_NM_BY_TYPE = {
    "ContainerVessel": 528.96,
    "BulkerVessel": 263.55,
    "TankerVessel": 405.53,
    "LNGCarrier": 435.0,
}

VESSEL_GEOMETRY_DEFAULTS = {
    "ContainerVessel": {
        "length_pp_m": 280.0,
        "beam_m": 40.0,
        "design_draft_m": 12.8,
        "wetted_surface_m2": 15200.0,
        "propulsive_efficiency": 0.70,
        "air_drag_area_m2": 1450.0,
        "hull_roughness_allowance": 1.08,
    },
    "BulkerVessel": {
        "length_pp_m": 225.0,
        "beam_m": 32.0,
        "design_draft_m": 11.4,
        "wetted_surface_m2": 11200.0,
        "propulsive_efficiency": 0.68,
        "air_drag_area_m2": 1180.0,
        "hull_roughness_allowance": 1.07,
    },
    "TankerVessel": {
        "length_pp_m": 245.0,
        "beam_m": 38.0,
        "design_draft_m": 13.1,
        "wetted_surface_m2": 13400.0,
        "propulsive_efficiency": 0.69,
        "air_drag_area_m2": 1260.0,
        "hull_roughness_allowance": 1.07,
    },
    "LNGCarrier": {
        "length_pp_m": 285.0,
        "beam_m": 43.0,
        "design_draft_m": 11.7,
        "wetted_surface_m2": 15800.0,
        "propulsive_efficiency": 0.72,
        "air_drag_area_m2": 1520.0,
        "hull_roughness_allowance": 1.06,
    },
}

MUST_PRESERVE_PAYLOAD_KEYS = (
    "packet_uuid",
    "generated_at",
    "gateway_received_at",
    "cloud_received_at",
    "seq",
    "timestamp_utc",
    "lat",
    "lon",
    "co2_value",
    "ch4_value",
    "n2o_value",
    "nox_value_kg_h",
    "sox_value_kg_h",
    "rpm",
    "cargo_quantity",
    "draft",
    "speed_over_ground",
    "speed_command_kn",
    "course_over_ground",
    "distance_from_previous_nm",
    "distance_to_next_port_nm",
    "route_leg_from",
    "route_leg_to",
    "vessel_mode",
    "vessel_type",
    "vessel_name",
    "mmsi",
    "imo_number",
    "gross_tonnage",
    "deadweight_tonnes",
    "fuel_type",
    "node_id",
    "depth",
    "ukc",
    "squat",
    "effective_draft",
    "bathymetry_source",
    "required_power_kw",
    "fuel_burn_rate",
    "co2_mass_step_kg",
    "fuel_burn_step_kg",
    "energy_use_mj",
    "transport_work_tonne_nm",
    "imo_eeoi_gco2_per_tonne_nm",
    "eu_ttw_co2_g_per_mj",
    "engine_load_ratio",
    "shallow_water_flag",
    "relative_wind_angle",
    "sfoc_g_per_kwh",
    "weather_sea_force_state",
    "weather_sea_force_pct",
    "weather_sea_force_index",
    "efficiency_state",
    "efficiency_reason_summary",
    "dominant_emission_driver",
    "dominant_emission_driver_kw",
    "secondary_emission_driver",
    "secondary_emission_driver_kw",
    "weather_penalty_pct",
    "sea_penalty_pct",
    "cargo_penalty_pct",
    "draft_penalty_pct",
    "water_depth_penalty_pct",
    "fouling_penalty_pct",
    "fouling_cycle_day",
    "fouling_stage",
    "fouling_multiplier",
    "days_since_hull_cleaning",
    "hull_condition_label",
    "weather_wind_speed",
    "weather_wind_direction",
    "weather_wave_height",
    "weather_air_temp",
    "weather_sea_temp",
    "weather_pressure",
    "weather_source",
    "weather_timestamp",
    "weather_is_forecast",
    "weather_fallback_mode",
    "quality_flags",
)

# 2024 EU MRV publication medians used as calibration references:
# - Container ship: ~528.96 kg CO2 / nm, CH4/CO2 ~0.016 per 1000, N2O/CO2 ~0.0576 per 1000
# - Bulk carrier: ~263.55 kg CO2 / nm, CH4/CO2 ~0.016 per 1000, N2O/CO2 ~0.0574 per 1000
# - Oil tanker: ~405.53 kg CO2 / nm, CH4/CO2 ~0.016 per 1000, N2O/CO2 ~0.0574 per 1000
# - LNG carrier: CH4/CO2 median is materially higher (~6.20 per 1000), useful for future LNG vessel modeling.


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def isoformat_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def safe_float(value, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def dm(degrees: float, minutes: float) -> float:
    return round(degrees + (minutes / 60.0), 6)


def round_or_none(value: float | None, digits: int = 2) -> float | None:
    if value is None:
        return None
    return round(value, digits)


def safe_ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator in {None, 0}:
        return None
    return numerator / denominator


def normalize_header(header: str) -> str:
    return header.strip().lower().replace(" ", "_")


def csv_value(row: Dict[str, str], *aliases: str) -> str | None:
    for alias in aliases:
        normalized = normalize_header(alias)
        for key, value in row.items():
            if normalize_header(key) == normalized and str(value).strip() != "":
                return str(value).strip()
    return None


def csv_float(row: Dict[str, str], *aliases: str) -> float | None:
    value = csv_value(row, *aliases)
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def classify_reference_deviation(deviation_pct: float | None) -> str:
    if deviation_pct is None:
        return "not_available"
    if deviation_pct < -12.0:
        return "below_reference"
    if deviation_pct > 12.0:
        return "above_reference"
    return "near_reference"


def confidence_to_validation_status(confidence_score: int, sensor_assimilation_active: bool) -> str:
    if sensor_assimilation_active:
        return "sensor_assimilated"
    if confidence_score >= 75:
        return "validation_ready"
    if confidence_score >= 50:
        return "physics_informed_synthetic"
    return "uncalibrated_synthetic"


def calculate_validation_metrics(actual_values: List[float], predicted_values: List[float]) -> Dict[str, float | int | None]:
    if len(actual_values) != len(predicted_values):
        raise ValueError("actual_values and predicted_values must be the same length")

    sample_count = len(actual_values)
    if sample_count == 0:
        return {
            "sample_count": 0,
            "mae": None,
            "rmse": None,
            "mape": None,
            "bias_pct": None,
            "r2": None,
        }

    absolute_errors = [abs(pred - actual) for actual, pred in zip(actual_values, predicted_values)]
    squared_errors = [(pred - actual) ** 2 for actual, pred in zip(actual_values, predicted_values)]
    percentage_errors = [
        abs((pred - actual) / actual) * 100.0
        for actual, pred in zip(actual_values, predicted_values)
        if actual not in {0, None}
    ]
    actual_mean = sum(actual_values) / sample_count
    bias_pct = (
        (sum((pred - actual) for actual, pred in zip(actual_values, predicted_values)) / sample_count)
        / actual_mean
        * 100.0
        if actual_mean != 0
        else None
    )
    total_sum_squares = sum((actual - actual_mean) ** 2 for actual in actual_values)
    r2 = None if total_sum_squares == 0 else 1.0 - (sum(squared_errors) / total_sum_squares)

    return {
        "sample_count": sample_count,
        "mae": round(sum(absolute_errors) / sample_count, 4),
        "rmse": round(math.sqrt(sum(squared_errors) / sample_count), 4),
        "mape": round(sum(percentage_errors) / len(percentage_errors), 4) if percentage_errors else None,
        "bias_pct": round(bias_pct, 4) if bias_pct is not None else None,
        "r2": round(r2, 4) if r2 is not None else None,
    }


@dataclass
class SensorAssimilationState:
    alpha: float = 0.1
    co2_correction_factor: float = 1.0
    ch4_correction_factor: float = 1.0
    n2o_correction_factor: float = 1.0
    fuel_correction_factor: float = 1.0

    def update_factor(self, current: float, measured: float | None, predicted: float | None) -> float:
        if measured is None or predicted is None or predicted <= 0:
            return current
        measured_ratio = clamp(measured / predicted, 0.5, 1.5)
        return round(((1.0 - self.alpha) * current) + (self.alpha * measured_ratio), 4)

    def apply(
        self,
        measured_co2: float | None,
        measured_ch4: float | None,
        measured_n2o: float | None,
        measured_fuel: float | None,
        predicted_co2: float,
        predicted_ch4: float,
        predicted_n2o: float,
        predicted_fuel: float,
    ) -> Dict:
        self.co2_correction_factor = self.update_factor(self.co2_correction_factor, measured_co2, predicted_co2)
        self.ch4_correction_factor = self.update_factor(self.ch4_correction_factor, measured_ch4, predicted_ch4)
        self.n2o_correction_factor = self.update_factor(self.n2o_correction_factor, measured_n2o, predicted_n2o)
        self.fuel_correction_factor = self.update_factor(self.fuel_correction_factor, measured_fuel, predicted_fuel)

        sensor_calibration_available = any(
            value is not None for value in (measured_co2, measured_ch4, measured_n2o, measured_fuel)
        )
        sensor_assimilation_active = bool(SIMULATOR_SENSOR_ASSIMILATION_CSV and sensor_calibration_available)

        corrected_co2 = predicted_co2 * self.co2_correction_factor if sensor_assimilation_active else predicted_co2
        corrected_ch4 = predicted_ch4 * self.ch4_correction_factor if sensor_assimilation_active else predicted_ch4
        corrected_n2o = predicted_n2o * self.n2o_correction_factor if sensor_assimilation_active else predicted_n2o
        corrected_fuel = predicted_fuel * self.fuel_correction_factor if sensor_assimilation_active else predicted_fuel
        co2_residual_pct = (
            round_or_none(safe_ratio((measured_co2 - predicted_co2) * 100.0, predicted_co2), 4)
            if measured_co2 is not None
            else None
        )
        ch4_residual_pct = (
            round_or_none(safe_ratio((measured_ch4 - predicted_ch4) * 100.0, predicted_ch4), 4)
            if measured_ch4 is not None
            else None
        )
        n2o_residual_pct = (
            round_or_none(safe_ratio((measured_n2o - predicted_n2o) * 100.0, predicted_n2o), 4)
            if measured_n2o is not None
            else None
        )
        fuel_residual_pct = (
            round_or_none(safe_ratio((measured_fuel - predicted_fuel) * 100.0, predicted_fuel), 4)
            if measured_fuel is not None
            else None
        )

        return {
            "sensor_calibration_available": sensor_calibration_available,
            "sensor_assimilation_active": sensor_assimilation_active,
            "measured_co2_kg_h": measured_co2,
            "measured_ch4_kg_h": measured_ch4,
            "measured_n2o_kg_h": measured_n2o,
            "measured_fuel_kg_h": measured_fuel,
            "predicted_co2_kg_h": round(predicted_co2, 3),
            "predicted_ch4_kg_h": round(predicted_ch4, 4),
            "predicted_n2o_kg_h": round(predicted_n2o, 5),
            "predicted_fuel_kg_h": round(predicted_fuel, 3),
            "model_co2_value": round(predicted_co2, 3),
            "corrected_co2_value": round(corrected_co2, 3),
            "corrected_ch4_value": round(corrected_ch4, 4),
            "corrected_n2o_value": round(corrected_n2o, 5),
            "corrected_fuel_burn_rate": round(corrected_fuel, 3),
            "co2_model_residual_pct": co2_residual_pct,
            "ch4_model_residual_pct": ch4_residual_pct,
            "n2o_model_residual_pct": n2o_residual_pct,
            "fuel_model_residual_pct": fuel_residual_pct,
            "ewma_correction_factor": round(self.co2_correction_factor, 4),
            "sensor_assimilation_status": (
                "corrected_from_measured_data"
                if sensor_assimilation_active
                else "no_measured_sensor_data"
                if not sensor_calibration_available
                else "measurement_loaded_but_inactive"
            ),
        }

def deterministic_demo_weather(lat: float, lon: float, reference_time: datetime | None = None) -> Dict:
    lat_factor = math.sin(math.radians(lat * 3.0))
    lon_factor = math.cos(math.radians(lon * 2.0))
    wind_speed = round(7.5 + (lat_factor * 2.8) + (lon_factor * 1.6), 2)
    wind_direction = round((180.0 + (lat * 11.0) + (lon * 3.0)) % 360.0, 2)
    wave_height = round(max(0.4, 1.1 + (lat_factor * 0.45) + (lon_factor * 0.25)), 2)
    air_temp = round(8.0 + (lat_factor * 4.0) - (lon_factor * 1.2), 2)
    sea_temp = round(6.5 + (lat_factor * 2.2), 2)
    pressure = round(1012.0 + (lon_factor * 6.0) - (lat_factor * 3.0), 2)

    return {
        "weather_wind_speed": wind_speed,
        "weather_wind_direction": wind_direction,
        "weather_wave_height": wave_height,
        "weather_air_temp": air_temp,
        "weather_sea_temp": sea_temp,
        "weather_pressure": pressure,
        "weather_source": "offline_demo",
        "weather_timestamp": isoformat_z(reference_time or now_utc()),
        "weather_is_forecast": False,
        "weather_fallback_mode": "offline_demo",
        "marine_query_lat": None,
        "marine_query_lon": None,
    }


def validate_runtime_configuration() -> None:
    if SIMULATOR_MODEL_MODE not in SUPPORTED_MODEL_MODES:
        supported = ", ".join(sorted(SUPPORTED_MODEL_MODES))
        raise RuntimeError(
            f"Unsupported SIMULATOR_MODEL_MODE={SIMULATOR_MODEL_MODE!r}. Supported values: {supported}."
        )

    if SIMULATOR_VALIDATION_CSV:
        return

    if SIMULATOR_OFFLINE_MODE:
        return

    missing_env_vars: List[str] = []
    if not FUNCTION_URL:
        missing_env_vars.append("SIMULATOR_FUNCTION_URL")
    if not SIMULATOR_STATUS_URL:
        missing_env_vars.append("SIMULATOR_STATUS_URL")

    if missing_env_vars:
        joined = ", ".join(missing_env_vars)
        raise RuntimeError(
            f"Simulator online mode requires these environment variables: {joined}. "
            "Set SIMULATOR_OFFLINE_MODE=true to run without Supabase endpoints."
        )


SENSOR_ASSIMILATION_RECORDS_CACHE: Dict | None = None


def load_sensor_assimilation_records() -> Dict:
    global SENSOR_ASSIMILATION_RECORDS_CACHE

    if SENSOR_ASSIMILATION_RECORDS_CACHE is not None:
        return SENSOR_ASSIMILATION_RECORDS_CACHE

    SENSOR_ASSIMILATION_RECORDS_CACHE = {}
    if not SIMULATOR_SENSOR_ASSIMILATION_CSV:
        return SENSOR_ASSIMILATION_RECORDS_CACHE

    csv_path = Path(SIMULATOR_SENSOR_ASSIMILATION_CSV)
    if not csv_path.exists():
        print(f"Sensor assimilation CSV not found: {csv_path}")
        return SENSOR_ASSIMILATION_RECORDS_CACHE

    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            timestamp = csv_value(row, "timestamp_utc")
            if not timestamp:
                continue
            key = (
                timestamp,
                csv_value(row, "imo_number"),
                csv_value(row, "vessel_type"),
            )
            SENSOR_ASSIMILATION_RECORDS_CACHE[key] = {
                "measured_co2_kg_h": csv_float(row, "measured_co2_kg_h", "co2_kg_h"),
                "measured_ch4_kg_h": csv_float(row, "measured_ch4_kg_h", "ch4_kg_h"),
                "measured_n2o_kg_h": csv_float(row, "measured_n2o_kg_h", "n2o_kg_h"),
                "measured_fuel_kg_h": csv_float(row, "measured_fuel_kg_h", "fuel_burn_rate_kg_h"),
            }
    return SENSOR_ASSIMILATION_RECORDS_CACHE


def lookup_sensor_measurement(timestamp_utc: str, imo_number: str, vessel_type: str) -> Dict:
    records = load_sensor_assimilation_records()
    return (
        records.get((timestamp_utc, imo_number, vessel_type))
        or records.get((timestamp_utc, imo_number, None))
        or records.get((timestamp_utc, None, vessel_type))
        or {}
    )


def calculate_reference_comparison(vessel_type: str, co2_mass_step_kg: float | None, distance_nm: float | None) -> Dict:
    reference = MRV_MEDIAN_KG_CO2_PER_NM_BY_TYPE.get(vessel_type)
    co2_kg_per_nm = None
    if co2_mass_step_kg is not None and distance_nm and distance_nm > 0:
        co2_kg_per_nm = round(co2_mass_step_kg / distance_nm, 4)

    deviation_pct = None
    if co2_kg_per_nm is not None and reference not in {None, 0}:
        deviation_pct = round(((co2_kg_per_nm - reference) / reference) * 100.0, 4)

    category = classify_reference_deviation(deviation_pct)
    calibration_status = (
        "not_available"
        if co2_kg_per_nm is None or reference is None
        else "below_reference"
        if category == "below_reference"
        else "above_reference"
        if category == "above_reference"
        else "near_reference"
    )
    return {
        "co2_kg_per_nm": co2_kg_per_nm,
        "mrv_reference_kg_co2_per_nm": reference,
        "mrv_reference_deviation_pct": deviation_pct,
        "mrv_reference_category": category,
        "calibration_status": calibration_status,
    }


def calculate_uncertainty_score(packet_context: dict) -> dict:
    uncertainty_pct = 12.0
    reasons: List[str] = []

    bathymetry_source = str(packet_context.get("bathymetry_source") or "")
    weather_source = str(packet_context.get("weather_source") or "")
    model_mode = str(packet_context.get("model_mode") or MODEL_MODE_ADMIRALTY_FAST)
    vessel_mode = str(packet_context.get("vessel_mode") or "")

    if "synthetic" in bathymetry_source or "fallback" in bathymetry_source:
        uncertainty_pct += 12.0
        reasons.append("synthetic_bathymetry_fallback")
    else:
        uncertainty_pct -= 3.0

    if weather_source in {"offline_demo", "fallback"}:
        uncertainty_pct += 10.0
        reasons.append("fallback_weather")
    elif weather_source == "open_meteo":
        uncertainty_pct -= 4.0

    if model_mode == MODEL_MODE_ADMIRALTY_FAST:
        uncertainty_pct += 8.0
        reasons.append("admiralty_fast_mode")
    else:
        uncertainty_pct -= 4.0

    if packet_context.get("sensor_assimilation_active"):
        uncertainty_pct -= 8.0
    else:
        uncertainty_pct += 6.0
        reasons.append("no_sensor_assimilation")

    if packet_context.get("geometry_defaults_used"):
        uncertainty_pct += 5.0
        reasons.append("geometry_defaults_used")

    if packet_context.get("shallow_water_flag"):
        uncertainty_pct += 6.0
        reasons.append("shallow_water")

    if packet_context.get("fouling_multiplier", 1.0) > 1.08:
        uncertainty_pct += 5.0
        reasons.append("heavy_fouling")

    if vessel_mode in {MODE_STOPPED, MODE_MANOEUVRING_25, MODE_MANOEUVRING_50}:
        uncertainty_pct += 6.0
        reasons.append("low_speed_operating_mode")

    uncertainty_pct = clamp(uncertainty_pct, 5.0, 95.0)
    confidence_score = int(round(clamp(100.0 - uncertainty_pct, 5.0, 100.0)))
    return {
        "uncertainty_pct": round(uncertainty_pct, 2),
        "confidence_score": confidence_score,
        "uncertainty_reasons": reasons or ["baseline_synthetic_model"],
    }


def haversine_nm(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r_km = 6371.0088
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return (r_km * c) / 1.852


def bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dlon = math.radians(lon2 - lon1)

    x = math.sin(dlon) * math.cos(p2)
    y = (
        math.cos(p1) * math.sin(p2)
        - math.sin(p1) * math.cos(p2) * math.cos(dlon)
    )
    return (math.degrees(math.atan2(x, y)) + 360.0) % 360.0


def heading_delta_deg(a: float, b: float) -> float:
    return abs((a - b + 180.0) % 360.0 - 180.0)


def signed_heading_delta_deg(a: float, b: float) -> float:
    return (a - b + 180.0) % 360.0 - 180.0


def build_leg_lengths(route_coords: List[Tuple[float, float]]) -> List[float]:
    lengths = []
    for i in range(len(route_coords) - 1):
        start = route_coords[i]
        end = route_coords[i + 1]
        lengths.append(haversine_nm(start[0], start[1], end[0], end[1]))
    return lengths


def sha256_hex(payload) -> str:
    data = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def compute_merkle(items: List[Dict]) -> str:
    if not items:
        return sha256_hex("empty")

    leaves = [sha256_hex(item) for item in items]
    while len(leaves) > 1:
        if len(leaves) % 2 == 1:
            leaves.append(leaves[-1])
        leaves = [
            sha256_hex(leaves[i] + leaves[i + 1])
            for i in range(0, len(leaves), 2)
        ]
    return leaves[0]


def make_route_labels(points_count: int) -> List[str]:
    labels: List[str] = []
    for idx in range(points_count):
        if idx == 0:
            labels.append("Helsinki")
        elif idx == 8:
            labels.append("Stockholm")
        elif idx == 15:
            labels.append("Visby")
        elif idx == points_count - 1:
            labels.append("Helsinki")
        elif idx < 8:
            labels.append(f"Helsinki -> Stockholm WP{idx}")
        elif idx < 15:
            labels.append(f"Stockholm -> Visby WP{idx - 8}")
        else:
            labels.append(f"Visby -> Helsinki WP{idx - 15}")
    return labels


def reverse_named_leg(points: List[Tuple[str, Tuple[float, float]]]) -> List[Tuple[str, Tuple[float, float]]]:
    return list(reversed(points))


def build_named_route(*segments: List[Tuple[str, Tuple[float, float]]]) -> Tuple[List[str], List[Tuple[float, float]]]:
    labels: List[str] = []
    coords: List[Tuple[float, float]] = []

    for segment in segments:
        segment_points = segment
        if labels:
            segment_points = segment_points[1:]

        for label, coord in segment_points:
            labels.append(label)
            coords.append(coord)

    return labels, coords


def fetch_weather(lat: float, lon: float, reference_time: datetime | None = None) -> Dict:
    if SIMULATOR_OFFLINE_MODE:
        return deterministic_demo_weather(lat, lon, reference_time=reference_time)

    try:
        weather_url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}"
            "&current=wind_speed_10m,wind_direction_10m,temperature_2m,pressure_msl"
            "&timezone=UTC"
        )

        weather_res = requests.get(weather_url, timeout=10)
        weather_res.raise_for_status()
        weather_data = weather_res.json()
        current_weather = weather_data.get("current", {})

        def try_marine(m_lat: float, m_lon: float):
            marine_url = (
                "https://marine-api.open-meteo.com/v1/marine"
                f"?latitude={m_lat}&longitude={m_lon}"
                "&current=wave_height,sea_surface_temperature"
                "&hourly=wave_height,sea_surface_temperature"
                "&timezone=UTC"
                "&cell_selection=sea"
            )

            marine_res = requests.get(marine_url, timeout=10)
            marine_res.raise_for_status()
            marine_data = marine_res.json()
            current_marine = marine_data.get("current", {})

            wave_height = current_marine.get("wave_height")
            sea_temp = current_marine.get("sea_surface_temperature")

            if (wave_height is None or sea_temp is None) and "hourly" in marine_data:
                hourly = marine_data.get("hourly", {})
                times = hourly.get("time", [])
                ts = current_weather.get("time")

                if ts in times:
                    idx = times.index(ts)

                    if wave_height is None:
                        waves = hourly.get("wave_height", [])
                        if idx < len(waves):
                            wave_height = waves[idx]

                    if sea_temp is None:
                        seas = hourly.get("sea_surface_temperature", [])
                        if idx < len(seas):
                            sea_temp = seas[idx]

                if wave_height is None and hourly.get("wave_height"):
                    wave_height = hourly["wave_height"][0]

                if sea_temp is None and hourly.get("sea_surface_temperature"):
                    sea_temp = hourly["sea_surface_temperature"][0]

            return wave_height, sea_temp

        candidate_points = [
            (lat, lon),
            (lat + 0.02, lon),
            (lat - 0.02, lon),
            (lat, lon + 0.02),
            (lat, lon - 0.02),
            (lat + 0.03, lon + 0.03),
            (lat - 0.03, lon - 0.03),
            (lat + 0.03, lon - 0.03),
            (lat - 0.03, lon + 0.03),
        ]

        wave_height = None
        sea_temp = None
        marine_used_lat = lat
        marine_used_lon = lon

        for test_lat, test_lon in candidate_points:
            wave_height, sea_temp = try_marine(test_lat, test_lon)
            if wave_height is not None or sea_temp is not None:
                marine_used_lat = test_lat
                marine_used_lon = test_lon
                break

        return {
            "weather_wind_speed": current_weather.get("wind_speed_10m"),
            "weather_wind_direction": current_weather.get("wind_direction_10m"),
            "weather_wave_height": wave_height,
            "weather_air_temp": current_weather.get("temperature_2m"),
            "weather_sea_temp": sea_temp,
            "weather_pressure": current_weather.get("pressure_msl"),
            "weather_source": "open_meteo",
            "weather_timestamp": current_weather.get("time"),
            "weather_is_forecast": False,
            "weather_fallback_mode": None if (wave_height is not None or sea_temp is not None) else "marine_not_found",
            "marine_query_lat": marine_used_lat,
            "marine_query_lon": marine_used_lon,
        }

    except Exception as e:
        print(f"Weather fetch error: {e}")
        fallback_weather = deterministic_demo_weather(lat, lon, reference_time=reference_time)
        fallback_weather["weather_source"] = "fallback"
        fallback_weather["weather_fallback_mode"] = "error"
        return fallback_weather


class BathymetryCatalog:
    def __init__(self, tile_dir: Path) -> None:
        self.tile_dir = tile_dir
        self.datasets: List[Dict] = []
        self.available = False
        self.load_error: str | None = None
        self._load()

    def _load(self) -> None:
        if h5py is None or np is None:
            self.load_error = "h5py/numpy not available"
            return

        if not self.tile_dir.exists():
            self.load_error = f"Tile directory not found: {self.tile_dir}"
            return

        nc_files = sorted(self.tile_dir.glob("*.nc"), reverse=True)
        if not nc_files:
            self.load_error = f"No NetCDF files found in {self.tile_dir}"
            return

        for path in nc_files:
            try:
                handle = h5py.File(path, "r")
                lat = handle["lat"][:]
                lon = handle["lon"][:]
                elevation = handle["elevation"]
                self.datasets.append(
                    {
                        "path": path,
                        "handle": handle,
                        "lat": lat,
                        "lon": lon,
                        "elevation": elevation,
                        "lat_min": float(lat[0]),
                        "lat_max": float(lat[-1]),
                        "lon_min": float(lon[0]),
                        "lon_max": float(lon[-1]),
                    }
                )
            except Exception as exc:
                self.load_error = f"Failed to load {path.name}: {exc}"

        self.available = len(self.datasets) > 0

    @staticmethod
    def _nearest_index(values, target: float) -> int:
        idx = int(np.searchsorted(values, target))
        if idx <= 0:
            return 0
        if idx >= len(values):
            return len(values) - 1
        return idx if abs(values[idx] - target) < abs(values[idx - 1] - target) else idx - 1

    def lookup_depth(self, lat: float, lon: float) -> Dict:
        if not self.available or np is None:
            return {"depth": None, "source": "synthetic_fallback", "elevation_raw": None}

        for dataset in self.datasets:
            if not (dataset["lat_min"] <= lat <= dataset["lat_max"] and dataset["lon_min"] <= lon <= dataset["lon_max"]):
                continue

            lat_idx = self._nearest_index(dataset["lat"], lat)
            lon_idx = self._nearest_index(dataset["lon"], lon)

            try:
                elevation = float(dataset["elevation"][lat_idx, lon_idx])
            except Exception:
                continue

            if math.isnan(elevation):
                continue

            depth = max(-elevation, 0.0)
            return {
                "depth": round(depth, 2),
                "source": dataset["path"].name,
                "elevation_raw": round(elevation, 3),
            }

        return {"depth": None, "source": "synthetic_fallback", "elevation_raw": None}


BATHYMETRY = BathymetryCatalog(BATHYMETRY_TILE_DIR)


@dataclass(frozen=True)
class PortZone:
    name: str
    zone_type: str
    lat: float
    lon: float
    radius_nm: float | None = None
    line_lon: float | None = None
    vhf_channel: str = FLOW_NOTICE_CHANNEL_DEFAULT


@dataclass(frozen=True)
class SeaZone:
    name: str
    lat: float
    lon: float
    radius_nm: float
    current_base_kn: float
    current_variability_kn: float
    current_direction_deg: float
    current_direction_swing_deg: float
    wave_bias_deg: float
    wave_period_range_s: Tuple[float, float]


PORT_ZONES: List[PortZone] = [
    PortZone("Lulea", "port_limit", dm(65, 19.8), dm(22, 45.3), radius_nm=2.0, vhf_channel="14"),
    PortZone("Oulu", "port_limit", dm(64, 57.1), dm(24, 15.0), line_lon=dm(24, 15.0), vhf_channel="67"),
    PortZone("Stockholm", "pilot_area", dm(59, 15.1), dm(19, 1.0), radius_nm=1.5, vhf_channel="12"),
    PortZone("Tallinn", "anchorage", dm(59, 31.0), dm(24, 45.0), radius_nm=1.0, vhf_channel="14"),
    PortZone("Helsinki", "vts_gate", dm(60, 2.5), dm(24, 57.0), line_lon=dm(24, 57.0), vhf_channel="71"),
    PortZone("Kotka", "anchorage", dm(60, 15.2), dm(26, 30.0), radius_nm=1.2, vhf_channel="67"),
    PortZone("Riga", "port_limit", dm(57, 6.5), dm(23, 53.0), radius_nm=2.5, vhf_channel="9"),
    PortZone("Gdansk", "anchorage", dm(54, 29.5), dm(18, 40.0), radius_nm=0.8, vhf_channel="14"),
    PortZone("Klaipeda", "port_gate", dm(55, 44.0), dm(21, 0.0), radius_nm=0.5, vhf_channel="9"),
]


SEA_ZONES: List[SeaZone] = [
    SeaZone(
        name="Bothnian Bay",
        lat=64.95,
        lon=23.10,
        radius_nm=140.0,
        current_base_kn=0.45,
        current_variability_kn=0.55,
        current_direction_deg=205.0,
        current_direction_swing_deg=42.0,
        wave_bias_deg=24.0,
        wave_period_range_s=(3.8, 6.6),
    ),
    SeaZone(
        name="Sea of Bothnia",
        lat=61.85,
        lon=19.60,
        radius_nm=135.0,
        current_base_kn=0.55,
        current_variability_kn=0.50,
        current_direction_deg=190.0,
        current_direction_swing_deg=48.0,
        wave_bias_deg=18.0,
        wave_period_range_s=(4.5, 7.6),
    ),
    SeaZone(
        name="Gulf of Finland",
        lat=59.80,
        lon=25.10,
        radius_nm=125.0,
        current_base_kn=0.60,
        current_variability_kn=0.65,
        current_direction_deg=78.0,
        current_direction_swing_deg=58.0,
        wave_bias_deg=14.0,
        wave_period_range_s=(4.2, 7.2),
    ),
    SeaZone(
        name="Gulf of Riga",
        lat=57.45,
        lon=23.25,
        radius_nm=95.0,
        current_base_kn=0.70,
        current_variability_kn=0.75,
        current_direction_deg=42.0,
        current_direction_swing_deg=72.0,
        wave_bias_deg=20.0,
        wave_period_range_s=(3.9, 6.8),
    ),
    SeaZone(
        name="Central Baltic",
        lat=58.35,
        lon=19.90,
        radius_nm=180.0,
        current_base_kn=0.40,
        current_variability_kn=0.45,
        current_direction_deg=160.0,
        current_direction_swing_deg=68.0,
        wave_bias_deg=26.0,
        wave_period_range_s=(4.8, 8.4),
    ),
    SeaZone(
        name="Southern Baltic",
        lat=55.20,
        lon=19.25,
        radius_nm=120.0,
        current_base_kn=0.48,
        current_variability_kn=0.52,
        current_direction_deg=118.0,
        current_direction_swing_deg=54.0,
        wave_bias_deg=16.0,
        wave_period_range_s=(4.6, 7.9),
    ),
]


def fetch_vessel_record_by_imo(imo_number: str) -> Dict | None:
    if SIMULATOR_OFFLINE_MODE:
        return None

    if not SUPABASE_REST_URL or not SUPABASE_ANON_KEY:
        return None

    try:
        response = requests.get(
            f"{SUPABASE_REST_URL}/rest/v1/vessels",
            params={
                "select": "id,name,imo_number",
                "imo_number": f"eq.{imo_number}",
                "limit": "1",
            },
            headers={
                "apikey": SUPABASE_ANON_KEY,
                "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
            },
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
        if isinstance(data, list) and data:
            return data[0]
    except Exception as exc:
        print(f"Vessel metadata lookup failed for IMO {imo_number}: {exc}")

    return None


def get_simulator_enabled() -> bool:
    if SIMULATOR_OFFLINE_MODE:
        return True

    if not SIMULATOR_STATUS_URL:
        raise RuntimeError(
            "SIMULATOR_STATUS_URL is required in online mode. "
            "Set SIMULATOR_OFFLINE_MODE=true to skip remote simulator control."
        )

    try:
        response = requests.get(SIMULATOR_STATUS_URL, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        data = response.json()

        if not isinstance(data, dict):
            return False

        control = data.get("control")
        if not control:
            return False

        enabled = control.get("enabled", False)
        status = control.get("status", "stopped")
        return bool(enabled) and status == "running"

    except Exception as e:
        print(f"Simulator control check error: {e}")
        return False


@dataclass
class VesselState:
    name: str
    gateway_uid: str
    gateway_key: str
    imo_number: str
    mmsi: str
    node_id: str
    route_labels: List[str]
    route_coords: List[Tuple[float, float]]
    seq: int
    cargo_max: float
    ballast_draft: float
    draft_factor: float
    port_1_label: str = "Helsinki"
    port_2_label: str = "Stockholm"
    port_3_label: str = "Visby"
    return_load_port_label: str | None = None
    leg_index: int = 0
    leg_progress: float = 0.0
    speed_jitter: float = 0.0
    sim_time: datetime = field(default_factory=lambda: START_SIM_TIME_UTC)
    cargo_quantity: float = 0.0
    cargo_stage: str = "outbound_full"
    vessel_mode: str = "Steaming"
    vessel_type: str = "Generic"
    fuel_type: str = "MGO_PROXY"
    fuel_lhv_mj_per_kg: float = 42.7
    gross_tonnage: float = 12000.0
    deadweight_tonnes: float = 18000.0
    admiralty_coefficient: float = 450.0
    block_coefficient: float = 0.72
    lightship_tonnes: float = 15000.0
    ballast_water_tonnes: float = 5000.0
    installed_power_kw: float = 18000.0
    hotel_load_kw: float = 800.0
    sfoc_steaming_g_per_kwh: float = 178.0
    sfoc_manoeuvring_g_per_kwh: float = 192.0
    methane_slip_steaming_factor: float = 0.0016
    methane_slip_manoeuvring_factor: float = 0.0030
    n2o_factor: float = 0.00012
    manoeuvring_efficiency_penalty: float = 1.10
    ballast_efficiency_modifier: float = 0.98
    loaded_efficiency_modifier: float = 1.04
    sea_speed_min: float = 12.0
    sea_speed_max: float = 14.0
    man_speed_min: float = 4.0
    man_speed_max: float = 8.0
    rpm_range_steaming: Tuple[int, int] = (60, 92)
    rpm_range_manoeuvring_half: Tuple[int, int] = (35, 52)
    rpm_range_manoeuvring_quarter: Tuple[int, int] = (18, 32)
    engine_make: str = "Generic"
    engine_model: str = "Generic marine engine"
    engine_curve_mcr_kw: float = 0.0
    engine_curve_points: Tuple[Tuple[float, float, float], ...] = (
        (0.25, 180.0, 560.52),
        (0.50, 170.0, 529.38),
        (0.75, 165.0, 513.81),
        (0.85, 166.0, 516.92),
        (1.00, 168.0, 523.15),
    )
    fouling_offset_days: float = 0.0
    scrubber_active: bool = DEFAULT_SCRUBBER_ACTIVE
    anchor_locked: bool = False
    drag_anchor_active: bool = False
    commanded_through_water_speed_kn: float | None = None
    actual_through_water_speed_kn: float | None = None
    lagged_required_power_kw: float = 0.0
    lagged_rpm: float = 0.0
    shaft_power_kw: float = 0.0
    shaft_rpm: float = 0.0
    governor_integral: float = 0.0
    governor_prev_error: float = 0.0
    speed_control_integral: float = 0.0
    speed_control_prev_error: float = 0.0
    turbocharger_state: float = 0.84
    combustion_quality_state: float = 0.88
    engine_thermal_state: float = 0.92
    minutes_since_engine_restart: float = 180.0
    main_engine_running_last_step: bool = True
    has_scr: bool = False
    scr_design_nox_reduction: float = 0.0
    scr_n2o_penalty_factor: float = 1.0
    engine_maintenance_interval_days: float = 365.0
    engine_condition_penalty_max: float = 0.12
    engine_maintenance_offset_days: float = 0.0
    aux_installed_power_kw: float = 2000.0
    aux_genset_count: int = 4
    aux_base_sfoc_g_per_kwh: float = 210.0
    length_pp_m: float | None = None
    beam_m: float | None = None
    design_draft_m: float | None = None
    wetted_surface_m2: float | None = None
    propulsive_efficiency: float | None = None
    air_drag_area_m2: float | None = None
    hull_roughness_allowance: float | None = None
    last_active_zone_names: Tuple[str, ...] = field(default_factory=tuple)
    last_vts_notice: str | None = None
    rng: random.Random = field(init=False, repr=False)
    geometry_defaults_used: Tuple[str, ...] = field(init=False, default_factory=tuple)
    sensor_assimilation_state: SensorAssimilationState = field(default_factory=SensorAssimilationState, repr=False)

    def __post_init__(self) -> None:
        if len(self.route_labels) != len(self.route_coords):
            raise ValueError(f"{self.name}: route_labels and route_coords must have same length")
        if len(self.route_coords) < 2:
            raise ValueError(f"{self.name}: at least 2 route points are required")

        self.rng = self.build_rng()
        self.apply_geometry_defaults()
        self.leg_lengths = build_leg_lengths(self.route_coords)
        if self.cargo_quantity <= 0:
            self.cargo_quantity = self.cargo_max
        if self.engine_maintenance_offset_days <= 0:
            self.engine_maintenance_offset_days = self.rng.uniform(
                0.0,
                self.engine_maintenance_interval_days * 0.65,
            )

    def build_rng(self) -> random.Random:
        if not SIMULATOR_SEED:
            return random.Random()

        seed_value = stable_seed_int(
            "vessel-rng",
            SIMULATOR_SEED,
            self.gateway_uid,
            self.node_id,
            self.imo_number,
            self.name,
        )
        return random.Random(seed_value)

    def seeded_uuid(self, label: str, *parts: object) -> str:
        if not SIMULATOR_SEED:
            return str(uuid.uuid4())

        token = "||".join(
            [
                str(label),
                SIMULATOR_SEED,
                self.gateway_uid,
                self.node_id,
                self.imo_number,
                *(str(part) for part in parts),
            ]
        )
        return str(uuid.uuid5(uuid.NAMESPACE_URL, token))

    def runtime_event_time(self, fallback: datetime | None = None) -> datetime:
        if SIMULATOR_SEED:
            return fallback or self.sim_time
        return now_utc()

    def apply_geometry_defaults(self) -> None:
        defaults = VESSEL_GEOMETRY_DEFAULTS.get(self.vessel_type, {})
        applied: List[str] = []
        for field_name, default_value in defaults.items():
            if getattr(self, field_name) in {None, 0}:
                setattr(self, field_name, default_value)
                applied.append(field_name)
        self.geometry_defaults_used = tuple(applied)

    @staticmethod
    def step_toward(current: float, target: float, max_delta: float) -> float:
        if max_delta <= 0:
            return target
        if target > current:
            return min(current + max_delta, target)
        return max(current - max_delta, target)

    def current_leg_start(self) -> Tuple[float, float]:
        return self.route_coords[self.leg_index]

    def current_leg_end(self) -> Tuple[float, float]:
        return self.route_coords[self.leg_index + 1]

    def current_leg_from_label(self) -> str:
        return self.route_labels[self.leg_index]

    def current_leg_to_label(self) -> str:
        return self.route_labels[self.leg_index + 1]

    def current_leg_length_nm(self) -> float:
        return self.leg_lengths[self.leg_index]

    def current_leg_heading(self) -> float:
        start = self.current_leg_start()
        end = self.current_leg_end()
        return bearing_deg(start[0], start[1], end[0], end[1])

    def current_position(self) -> Tuple[float, float]:
        start = self.current_leg_start()
        end = self.current_leg_end()
        return (
            lerp(start[0], end[0], self.leg_progress),
            lerp(start[1], end[1], self.leg_progress),
        )

    def distance_to_next_port_nm(self) -> float:
        return max((1.0 - self.leg_progress) * self.current_leg_length_nm(), 0.0)

    def active_port_zones(self, lat: float, lon: float) -> List[PortZone]:
        zones: List[PortZone] = []
        for zone in PORT_ZONES:
            if zone.line_lon is not None:
                if abs(lon - zone.line_lon) <= 0.10:
                    zones.append(zone)
                continue

            if zone.radius_nm is None:
                continue

            if haversine_nm(lat, lon, zone.lat, zone.lon) <= zone.radius_nm:
                    zones.append(zone)
        return zones

    def active_sea_zone(self, lat: float, lon: float) -> SeaZone | None:
        best_zone: SeaZone | None = None
        best_distance = float("inf")

        for zone in SEA_ZONES:
            distance = haversine_nm(lat, lon, zone.lat, zone.lon)
            if distance <= zone.radius_nm and distance < best_distance:
                best_distance = distance
                best_zone = zone

        return best_zone

    def build_vts_notice(self, zones: List[PortZone]) -> str | None:
        current_names = tuple(sorted(zone.name for zone in zones))
        if current_names == self.last_active_zone_names:
            return None

        self.last_active_zone_names = current_names
        if not zones:
            return None

        zone = zones[0]
        return f"Entering {zone.name} VTS Area. Switch to VHF Channel {zone.vhf_channel}."

    def handle_port_arrival(self, port_label: str) -> None:
        if port_label == self.port_2_label and self.cargo_stage == "outbound_full":
            self.cargo_quantity = round(self.cargo_max * 0.5, 2)
            self.cargo_stage = "outbound_half"
            return

        if port_label == self.port_3_label and self.cargo_stage in {"outbound_full", "outbound_half"}:
            self.cargo_quantity = 0.0
            self.cargo_stage = "ballast"
            return

        if port_label == self.port_1_label and self.cargo_stage in {"ballast", "return_full"}:
            self.cargo_quantity = self.cargo_max
            self.cargo_stage = "outbound_full"

    def determine_mode(
        self,
        distance_to_port_nm: float,
        ukc_m: float | None = None,
        draft_m: float | None = None,
    ) -> str:
        draft = draft_m if draft_m is not None else self.calculate_draft()

        if distance_to_port_nm <= STOPPED_PORT_DISTANCE_NM:
            return MODE_STOPPED

        if ukc_m is not None:
            if ukc_m <= UKC_SAFETY_LIMIT_M:
                return MODE_STOPPED
            if UKC_SAFETY_LIMIT_M < ukc_m < draft:
                return MODE_MANOEUVRING_25
            if draft <= ukc_m <= (2.0 * draft):
                return MODE_MANOEUVRING_50

        if distance_to_port_nm <= QUARTER_RPM_PORT_DISTANCE_NM:
            return MODE_MANOEUVRING_25
        if distance_to_port_nm <= HALF_RPM_PORT_DISTANCE_NM:
            return MODE_MANOEUVRING_50
        if distance_to_port_nm <= MANOEUVRING_DISTANCE_NM:
            return MODE_MANOEUVRING_50
        return MODE_STEAMING

    def get_mode_speed_bounds(self, mode: str) -> Tuple[float, float]:
        if mode == MODE_STOPPED:
            return (0.0, 0.0)
        if mode == MODE_MANOEUVRING_25:
            return (
                max(2.0, self.sea_speed_min * 0.22),
                max(3.8, self.sea_speed_max * 0.30),
            )
        if mode == MODE_MANOEUVRING_50:
            return (
                max(4.2, self.sea_speed_min * 0.42),
                min(self.man_speed_max + 1.0, self.sea_speed_max * 0.58),
            )
        return (self.sea_speed_min, self.sea_speed_max)

    def choose_speed_for_mode(self, mode: str) -> float:
        if mode == MODE_STOPPED:
            self.speed_jitter = 0.0
            return 0.0

        low, high = self.get_mode_speed_bounds(mode)

        if mode in {MODE_MANOEUVRING_25, MODE_MANOEUVRING_50}:
            base = self.rng.uniform(low, high)
            self.speed_jitter = clamp(
                self.speed_jitter + self.rng.uniform(-0.08, 0.08),
                -0.25,
                0.25,
            )
            return clamp(base + self.speed_jitter, low, high)

        base = self.rng.uniform(low, high)
        if self.cargo_stage == "ballast":
            base += 0.25

        self.speed_jitter = clamp(
            self.speed_jitter + self.rng.uniform(-0.20, 0.20),
            -0.60,
            0.60,
        )
        return clamp(base + self.speed_jitter, low, high)

    def environmental_speed_loss_kn(
        self,
        mode: str,
        target_speed_kn: float,
        depth_m: float,
        heading_deg: float,
        weather: Dict,
        lat: float,
        lon: float,
        zone_snapshot: Dict | None = None,
    ) -> Dict:
        draft = self.calculate_draft()
        effective_draft = draft + self.calculate_squat(target_speed_kn)
        ukc = depth_m - effective_draft
        sea_zone = self.active_sea_zone(lat, lon)
        sim_elapsed_days = self.get_sim_elapsed_days()
        relative_wind_angle = self.calculate_relative_wind_angle(heading_deg, weather)
        relative_wave_angle = self.calculate_relative_wave_angle(heading_deg, weather, sim_elapsed_days, sea_zone)
        current_snapshot = self.calculate_current_snapshot(lat, lon, heading_deg, sea_zone)
        wave_height = safe_float(weather.get("weather_wave_height"), 0.0)
        wave_period_s = self.calculate_wave_period_s(weather, wave_height, relative_wave_angle, sea_zone)
        weather_sea_snapshot = self.calculate_weather_sea_force_snapshot(
            relative_wind_angle,
            relative_wave_angle,
            safe_float(weather.get("weather_wind_speed"), 0.0),
            wave_height,
            wave_period_s,
            current_snapshot["current_along_track_kn"],
        )

        loss_kn = 0.0
        reasons: List[str] = []

        against_force_pct = max(weather_sea_snapshot["weather_sea_force_index"], 0.0)
        if against_force_pct > 0:
            weather_loss = min(target_speed_kn * 0.16, target_speed_kn * (against_force_pct / 100.0) * 0.32)
            loss_kn += weather_loss
            if weather_loss >= 0.15:
                reasons.append("adverse_weather")

        severe_head_sea = (
            weather_sea_snapshot["weather_sea_force_state"] == "against"
            and relative_wave_angle <= 55.0
            and wave_height >= 1.8
            and wave_period_s >= 5.5
        )
        if severe_head_sea:
            operator_sea_margin_loss = min(target_speed_kn * 0.10, 1.6)
            loss_kn += operator_sea_margin_loss
            reasons.append("operator_head_sea_rpm_reduction")

        if current_snapshot["current_along_track_kn"] < -0.15:
            current_loss = min(target_speed_kn * 0.12, abs(current_snapshot["current_along_track_kn"]) * 0.45)
            loss_kn += current_loss
            reasons.append("adverse_current")

        if ukc < (1.35 * draft):
            shallow_ratio = clamp(((1.35 * draft) - ukc) / max(draft, 0.5), 0.0, 1.0)
            shallow_loss = target_speed_kn * (0.08 + (0.12 * shallow_ratio))
            loss_kn += shallow_loss
            reasons.append("shallow_water")
            if target_speed_kn > MAX_UKC_SAFE_SPEED_KN:
                loss_kn += min(target_speed_kn * 0.08, 1.2)
                reasons.append("operator_shallow_water_acceleration_limit")

        if mode == MODE_STEAMING and zone_snapshot and zone_snapshot.get("in_port_zone"):
            loss_kn += min(0.5, target_speed_kn * 0.03)
            reasons.append("port_approach")

        if self.cargo_stage != "ballast" and target_speed_kn > self.man_speed_max:
            cargo_ratio = clamp(self.cargo_quantity / max(self.cargo_max, 1.0), 0.0, 1.0)
            cargo_loss = target_speed_kn * cargo_ratio * 0.025
            if cargo_loss >= 0.12:
                loss_kn += cargo_loss
                reasons.append("laden_resistance")

        if mode in {MODE_MANOEUVRING_25, MODE_MANOEUVRING_50, MODE_STOPPED}:
            loss_kn *= 0.55

        attainable_speed_kn = max(target_speed_kn - loss_kn, 0.0)
        return {
            "attainable_speed_kn": round(attainable_speed_kn, 3),
            "speed_loss_kn": round(max(loss_kn, 0.0), 3),
            "speed_loss_reason": ", ".join(dict.fromkeys(reasons)) if reasons else "none",
            "weather_sea_force_index": weather_sea_snapshot["weather_sea_force_index"],
            "severe_head_sea": severe_head_sea,
        }

    def apply_speed_response(self, target_speed_kn: float, mode: str, resistance_factor: float) -> float:
        if self.commanded_through_water_speed_kn is None:
            self.commanded_through_water_speed_kn = target_speed_kn
        if self.actual_through_water_speed_kn is None:
            self.actual_through_water_speed_kn = target_speed_kn

        if mode == MODE_STOPPED:
            command_delta = 2.4
            actual_delta = 1.9
        elif mode == MODE_MANOEUVRING_25:
            command_delta = 1.4
            actual_delta = 1.0
        elif mode == MODE_MANOEUVRING_50:
            command_delta = 1.8
            actual_delta = 1.25
        else:
            command_delta = 2.1
            actual_delta = 1.5

        resistance_modifier = clamp(1.05 - resistance_factor, 0.45, 1.0)
        self.commanded_through_water_speed_kn = self.step_toward(
            self.commanded_through_water_speed_kn,
            target_speed_kn,
            command_delta,
        )
        self.actual_through_water_speed_kn = self.step_toward(
            self.actual_through_water_speed_kn,
            self.commanded_through_water_speed_kn,
            actual_delta * resistance_modifier,
        )
        return round(max(self.actual_through_water_speed_kn, 0.0), 3)

    def calculate_propeller_shaft_snapshot(
        self,
        delivered_power_kw: float,
        rpm: float,
        speed_kn: float,
        fouling_multiplier: float,
        mode: str,
    ) -> Dict:
        shaft_line_efficiency = 0.985 if mode == MODE_STEAMING else 0.978 if mode in {MODE_MANOEUVRING_25, MODE_MANOEUVRING_50} else 0.965
        shaft_power_kw = max(delivered_power_kw * shaft_line_efficiency, 0.0)
        shaft_rpm = max(rpm, 0.0)
        shaft_rps = max(shaft_rpm / 60.0, 0.05)
        shaft_torque_knm = shaft_power_kw / (2.0 * math.pi * shaft_rps)
        reference_kn_per_rpm = max(self.sea_speed_max / max(self.rpm_range_steaming[1], 1), 0.02)
        advance_speed_kn = shaft_rpm * reference_kn_per_rpm
        slip_ratio = clamp((advance_speed_kn - speed_kn) / max(advance_speed_kn, 0.25), 0.02, 0.65)
        load_ratio = clamp(shaft_power_kw / max(self.installed_power_kw, 1.0), 0.0, 1.15)
        propeller_open_water_efficiency = clamp(
            0.74
            + (0.10 * load_ratio)
            - (0.18 * abs(slip_ratio - 0.18))
            - ((fouling_multiplier - 1.0) * 0.16),
            0.42,
            0.82,
        )
        propeller_delivered_thrust_kw = shaft_power_kw * propeller_open_water_efficiency
        return {
            "shaft_line_efficiency": round(shaft_line_efficiency, 4),
            "shaft_power_kw": round(shaft_power_kw, 2),
            "shaft_rpm": round(shaft_rpm, 2),
            "shaft_torque_knm": round(max(shaft_torque_knm, 0.0), 3),
            "propeller_slip_ratio": round(slip_ratio, 4),
            "propeller_open_water_efficiency": round(propeller_open_water_efficiency, 4),
            "propeller_delivered_thrust_kw": round(propeller_delivered_thrust_kw, 2),
        }

    def calculate_propulsion_control_snapshot(
        self,
        commanded_speed_kn: float,
        actual_speed_kn: float,
        raw_required_power_kw: float,
        raw_engine_load_ratio: float,
        weather_sea_snapshot: Dict,
        shallow_water_flag: bool,
        mode: str,
    ) -> Dict:
        dt_hours = SIMULATED_MINUTES_PER_LOOP / 60.0
        speed_error = max(commanded_speed_kn - actual_speed_kn, 0.0)
        if mode == MODE_STOPPED:
            kp = 0.0
            ki = 0.0
            kd = 0.0
        elif mode in {MODE_MANOEUVRING_25, MODE_MANOEUVRING_50}:
            kp = 0.10
            ki = 0.030
            kd = 0.035
        else:
            kp = 0.15
            ki = 0.040
            kd = 0.055

        self.speed_control_integral = clamp(
            self.speed_control_integral + (speed_error * dt_hours),
            -1.5,
            1.5,
        )
        speed_derivative = (speed_error - self.speed_control_prev_error) / max(dt_hours, 1e-6)
        self.speed_control_prev_error = speed_error

        pid_trim = (kp * speed_error) + (ki * self.speed_control_integral) + (kd * speed_derivative * 0.05)
        sea_margin_factor = 0.05
        if weather_sea_snapshot["weather_sea_force_state"] == "against":
            sea_margin_factor += 0.04
        if shallow_water_flag:
            sea_margin_factor += 0.02

        if speed_error <= 0.08 and weather_sea_snapshot["weather_sea_force_state"] != "against":
            pid_trim = min(pid_trim, 0.0)

        controller_factor = clamp(1.0 + sea_margin_factor + pid_trim, 0.82, 1.25)
        target_power_kw = raw_required_power_kw * controller_factor
        target_load_ratio = clamp(target_power_kw / max(self.installed_power_kw, 1.0), 0.05, 1.15)
        return {
            "speed_error_kn": round(speed_error, 3),
            "speed_pid_trim": round(pid_trim, 4),
            "sea_margin_factor": round(sea_margin_factor, 4),
            "controller_factor": round(controller_factor, 4),
            "target_power_kw": round(target_power_kw, 2),
            "target_load_ratio": round(target_load_ratio, 4),
            "raw_engine_load_ratio": round(raw_engine_load_ratio, 4),
        }

    def apply_propulsion_response(
        self,
        target_required_power_kw: float,
        target_rpm: int,
        mode: str,
        target_load_ratio: float,
    ) -> Tuple[float, int, Dict]:
        if mode == MODE_STOPPED:
            self.lagged_required_power_kw = 0.0
            self.lagged_rpm = 0.0
            self.shaft_power_kw = 0.0
            self.shaft_rpm = 0.0
            self.governor_integral = 0.0
            self.governor_prev_error = 0.0
            return (
                0.0,
                0,
                {
                    "governor_error": 0.0,
                    "governor_integral": 0.0,
                    "governor_trim": 0.0,
                    "governor_target_power_kw": 0.0,
                    "shaft_power_kw": 0.0,
                    "shaft_rpm": 0.0,
                },
            )

        if self.lagged_required_power_kw <= 0:
            self.lagged_required_power_kw = target_required_power_kw
        if self.lagged_rpm <= 0 and target_rpm > 0:
            self.lagged_rpm = float(target_rpm)
        if self.shaft_power_kw <= 0:
            self.shaft_power_kw = max(target_required_power_kw * 0.98, 0.0)
        if self.shaft_rpm <= 0 and target_rpm > 0:
            self.shaft_rpm = float(target_rpm)

        if mode == MODE_STOPPED:
            power_delta = max(self.installed_power_kw * 0.22, 1800.0)
            rpm_delta = 18.0
            governor_kp = 0.55
            governor_ki = 0.08
            governor_kd = 0.02
        elif mode in {MODE_MANOEUVRING_25, MODE_MANOEUVRING_50}:
            power_delta = max(self.installed_power_kw * 0.16, 1200.0)
            rpm_delta = 10.0
            governor_kp = 0.68
            governor_ki = 0.16
            governor_kd = 0.05
        else:
            power_delta = max(self.installed_power_kw * 0.12, 1600.0)
            rpm_delta = 8.0
            governor_kp = 0.74
            governor_ki = 0.18
            governor_kd = 0.06

        dt_hours = SIMULATED_MINUTES_PER_LOOP / 60.0
        current_load_ratio = clamp(self.shaft_power_kw / max(self.installed_power_kw, 1.0), 0.0, 1.15)
        governor_error = clamp(target_load_ratio - current_load_ratio, -0.55, 0.55)
        self.governor_integral = clamp(self.governor_integral + (governor_error * dt_hours), -1.25, 1.25)
        governor_derivative = (governor_error - self.governor_prev_error) / max(dt_hours, 1e-6)
        self.governor_prev_error = governor_error
        governor_trim = (
            governor_kp * governor_error
            + governor_ki * self.governor_integral
            + governor_kd * governor_derivative * 0.05
        )
        governor_target_power_kw = target_required_power_kw * clamp(1.0 + governor_trim, 0.78, 1.22)

        self.lagged_required_power_kw = self.step_toward(
            self.lagged_required_power_kw,
            governor_target_power_kw,
            power_delta,
        )
        self.lagged_rpm = self.step_toward(
            self.lagged_rpm,
            float(target_rpm),
            rpm_delta,
        )
        shaft_power_delta = power_delta * 0.92
        shaft_rpm_delta = rpm_delta * 0.82
        self.shaft_power_kw = self.step_toward(
            self.shaft_power_kw,
            self.lagged_required_power_kw * 0.985,
            shaft_power_delta,
        )
        self.shaft_rpm = self.step_toward(
            self.shaft_rpm,
            self.lagged_rpm,
            shaft_rpm_delta,
        )
        return (
            round(max(self.lagged_required_power_kw, 0.0), 2),
            int(round(max(self.lagged_rpm, 0.0))),
            {
                "governor_error": round(governor_error, 4),
                "governor_integral": round(self.governor_integral, 4),
                "governor_trim": round(governor_trim, 4),
                "governor_target_power_kw": round(max(governor_target_power_kw, 0.0), 2),
                "shaft_power_kw": round(max(self.shaft_power_kw, 0.0), 2),
                "shaft_rpm": round(max(self.shaft_rpm, 0.0), 2),
            },
        )

    def calculate_transient_combustion_snapshot(
        self,
        engine_load_ratio: float,
        governor_snapshot: Dict,
        mode: str,
    ) -> Dict:
        dt_hours = SIMULATED_MINUTES_PER_LOOP / 60.0
        shaft_load_ratio = clamp(governor_snapshot["shaft_power_kw"] / max(self.installed_power_kw, 1.0), 0.0, 1.15)
        turbocharger_target = clamp(0.72 + (0.30 * shaft_load_ratio), 0.68, 1.02)
        turbo_delta = 0.22 if mode == MODE_STEAMING else 0.28
        self.turbocharger_state = self.step_toward(
            self.turbocharger_state,
            turbocharger_target,
            turbo_delta * dt_hours,
        )

        load_change_ratio = abs(governor_snapshot["governor_error"])
        combustion_target = clamp(
            0.90
            + (0.10 * self.turbocharger_state)
            - (0.08 * load_change_ratio)
            - (0.06 if mode in {MODE_MANOEUVRING_25, MODE_MANOEUVRING_50} else 0.0),
            0.74,
            1.03,
        )
        self.combustion_quality_state = self.step_toward(
            self.combustion_quality_state,
            combustion_target,
            0.30 * dt_hours,
        )

        sfoc_transient_multiplier = clamp(
            1.0
            + ((0.95 - self.combustion_quality_state) * 0.28)
            + (abs(shaft_load_ratio - engine_load_ratio) * 0.10),
            0.96,
            1.12,
        )
        nox_transient_multiplier = clamp(
            0.96 + (0.12 * self.combustion_quality_state) + (0.05 * shaft_load_ratio),
            0.88,
            1.10,
        )
        methane_transient_multiplier = clamp(
            1.0 + ((0.96 - self.combustion_quality_state) * 0.85),
            0.92,
            1.28,
        )
        n2o_transient_multiplier = clamp(
            0.98 + ((1.0 - self.combustion_quality_state) * 0.42),
            0.90,
            1.12,
        )
        return {
            "turbocharger_state": round(self.turbocharger_state, 4),
            "combustion_quality_state": round(self.combustion_quality_state, 4),
            "sfoc_transient_multiplier": round(sfoc_transient_multiplier, 4),
            "nox_transient_multiplier": round(nox_transient_multiplier, 4),
            "methane_transient_multiplier": round(methane_transient_multiplier, 4),
            "n2o_transient_multiplier": round(n2o_transient_multiplier, 4),
        }

    def apply_zone_navigation_logic(
        self,
        command_speed_kn: float,
        actual_speed_kn: float,
        weather: Dict,
        zones: List[PortZone],
    ) -> Dict:
        in_port_zone = any(zone.zone_type in {"port_limit", "pilot_area", "vts_gate", "port_gate"} for zone in zones)
        in_anchorage = any(zone.zone_type == "anchorage" for zone in zones)

        adjusted_command_speed = command_speed_kn
        adjusted_actual_speed = actual_speed_kn

        if in_port_zone:
            adjusted_command_speed = min(adjusted_command_speed, max(self.man_speed_min + 0.5, 8.5))
            adjusted_actual_speed = min(adjusted_actual_speed, adjusted_command_speed)

        drag_anchor = False
        if in_anchorage and adjusted_actual_speed <= ANCHOR_LOCK_SPEED_KN:
            wind_speed = safe_float(weather.get("weather_wind_speed"), 0.0)
            drag_probability = clamp((wind_speed - 12.0) / 18.0, 0.0, 0.45)
            drag_anchor = self.rng.random() < drag_probability
            self.anchor_locked = not drag_anchor
            self.drag_anchor_active = drag_anchor
            if self.anchor_locked:
                adjusted_actual_speed = 0.0
                adjusted_command_speed = 0.0
        else:
            self.anchor_locked = False
            self.drag_anchor_active = False

        return {
            "command_speed_kn": adjusted_command_speed,
            "actual_speed_kn": adjusted_actual_speed,
            "in_port_zone": in_port_zone,
            "in_anchorage": in_anchorage,
            "drag_anchor": drag_anchor,
        }

    def calculate_draft(self) -> float:
        return round(self.ballast_draft + self.cargo_quantity * self.draft_factor, 2)

    def calculate_depth(self, distance_to_port_nm: float) -> float:
        return round(min(MAX_SYNTHETIC_DEPTH_M, 5.0 + (distance_to_port_nm * 2.0)), 2)

    def get_bathymetric_depth(self, lat: float, lon: float, distance_to_port_nm: float) -> Dict:
        lookup = BATHYMETRY.lookup_depth(lat, lon)
        if lookup["depth"] is not None:
            return lookup

        return {
            "depth": self.calculate_depth(distance_to_port_nm),
            "source": "synthetic_fallback",
            "elevation_raw": None,
        }

    def calculate_squat(self, speed_kn: float) -> float:
        speed_kn = max(speed_kn, 0.0)
        return round(self.block_coefficient * ((speed_kn ** 2) / 100.0), 3)

    def estimate_displacement_tonnes(self) -> float:
        ballast_fill_tonnes = self.ballast_water_tonnes if self.cargo_stage == "ballast" else self.ballast_water_tonnes * 0.55
        displacement = self.lightship_tonnes + ballast_fill_tonnes + self.cargo_quantity
        return max(displacement, self.lightship_tonnes)

    def get_sim_elapsed_days(self) -> float:
        return max((self.sim_time - START_SIM_TIME_UTC).total_seconds() / 86400.0, 0.0)

    def get_fouling_cycle_day(self, sim_elapsed_days: float) -> float:
        return (self.fouling_offset_days + sim_elapsed_days) % FOULING_CYCLE_DAYS

    def get_fouling_stage(self, cycle_day: float) -> str:
        if cycle_day <= 30.0:
            return "slime_biofilm"
        if cycle_day <= 120.0:
            return "weed_algae"
        return "hard_fouling"

    def get_hull_condition_label(self, multiplier: float) -> str:
        if multiplier < 1.10:
            return "clean_to_light_slime"
        if multiplier < 1.30:
            return "moderate_biofouling"
        return "heavy_hard_fouling"

    def get_fouling_multiplier(self, sim_elapsed_days: float) -> float:
        cycle_day = self.get_fouling_cycle_day(sim_elapsed_days)

        if cycle_day <= 30.0:
            ratio = cycle_day / 30.0
            increase = 0.10 * ratio
        elif cycle_day <= 120.0:
            ratio = (cycle_day - 30.0) / 90.0
            increase = 0.10 + (0.20 * ratio)
        else:
            ratio = (cycle_day - 120.0) / 60.0
            increase = 0.30 + (0.50 * ratio)

        return round(1.0 + increase, 4)

    def get_propeller_fouling_multiplier(self, sim_elapsed_days: float) -> float:
        return self.get_fouling_multiplier(sim_elapsed_days)

    def get_propeller_condition_label(self, multiplier: float) -> str:
        if multiplier < 1.10:
            return "clean_propeller"
        if multiplier < 1.30:
            return "moderate_propeller_fouling"
        return "heavy_propeller_fouling"

    def co2_factor_for_fuel(self) -> float:
        return 2.75 if self.is_lng_fueled() else CO2_EMISSION_FACTOR

    def sfoc_at_load(self, base_sfoc_g_per_kwh: float, engine_load_fraction: float, role: str = "main") -> float:
        load = clamp(engine_load_fraction, 0.05, 1.10)

        if role == "aux":
            if load < 0.20:
                correction = 1.38 - (load / 0.20) * 0.18
            elif load < 0.80:
                correction = 1.20 - ((load - 0.20) / 0.60) * 0.12
            elif load <= 1.00:
                correction = 1.00
            else:
                correction = 1.00 + (load - 1.00) * 1.4
            return base_sfoc_g_per_kwh * correction

        if self.is_lng_fueled():
            if load < 0.20:
                correction = 1.48 - (load / 0.20) * 0.30
            elif load < 0.80:
                correction = 1.18 - ((load - 0.20) / 0.60) * 0.18
            elif load <= 1.00:
                correction = 1.00
            else:
                correction = 1.00 + (load - 1.00) * 1.8
            return base_sfoc_g_per_kwh * correction

        if load < 0.20:
            correction = 1.60 - (load / 0.20) * 0.45
        elif load < 0.85:
            correction = 1.15 - ((load - 0.20) / 0.65) * 0.15
        elif load <= 1.00:
            correction = 1.00
        else:
            correction = 1.00 + (load - 1.00) * 2.0
        return base_sfoc_g_per_kwh * correction

    def calculate_engine_warmup_snapshot(self, mode: str, in_anchorage: bool) -> Dict:
        dt_minutes = SIMULATED_MINUTES_PER_LOOP
        running_now = mode != MODE_STOPPED and not in_anchorage

        if running_now and not self.main_engine_running_last_step:
            self.minutes_since_engine_restart = 0.0
            self.engine_thermal_state = min(self.engine_thermal_state, 0.68)
        elif running_now:
            self.minutes_since_engine_restart += dt_minutes

        if running_now:
            target_thermal_state = 1.0 if mode == MODE_STEAMING else 0.94
            thermal_delta = 0.06 if mode == MODE_STEAMING else 0.08
            self.engine_thermal_state = self.step_toward(
                self.engine_thermal_state,
                target_thermal_state,
                thermal_delta,
            )
        else:
            cool_target = 0.76 if in_anchorage else 0.72
            self.engine_thermal_state = self.step_toward(
                self.engine_thermal_state,
                cool_target,
                0.035,
            )

        warmup_progress = clamp(self.minutes_since_engine_restart / 30.0, 0.0, 1.0) if running_now else 1.0
        warmup_intensity = 1.0 - warmup_progress
        warmup_sfoc_multiplier = 1.0 + (0.12 * warmup_intensity) + max(0.88 - self.engine_thermal_state, 0.0) * 0.10
        warmup_methane_multiplier = 1.0 + (0.95 * warmup_intensity) + max(0.90 - self.engine_thermal_state, 0.0) * 0.65
        warmup_combustion_penalty = max(0.0, (0.92 - self.engine_thermal_state) * 0.45) + (0.08 * warmup_intensity)

        self.main_engine_running_last_step = running_now
        return {
            "engine_thermal_state": round(self.engine_thermal_state, 4),
            "minutes_since_engine_restart": round(self.minutes_since_engine_restart, 2),
            "warmup_sfoc_multiplier": round(clamp(warmup_sfoc_multiplier, 1.0, 1.22), 4),
            "warmup_methane_multiplier": round(clamp(warmup_methane_multiplier, 1.0, 2.15), 4),
            "warmup_combustion_penalty": round(clamp(warmup_combustion_penalty, 0.0, 0.18), 4),
        }

    def calculate_engine_condition_snapshot(self, sim_elapsed_days: float) -> Dict:
        days_since_engine_maintenance = (sim_elapsed_days + self.engine_maintenance_offset_days) % max(
            self.engine_maintenance_interval_days,
            1.0,
        )
        maintenance_progress = clamp(
            days_since_engine_maintenance / max(self.engine_maintenance_interval_days, 1.0),
            0.0,
            1.0,
        )
        engine_condition_factor = 1.0 + (self.engine_condition_penalty_max * (maintenance_progress ** 0.85))
        maintenance_sfoc_multiplier = 1.0 + ((engine_condition_factor - 1.0) * 0.95)
        maintenance_methane_multiplier = 1.0 + ((engine_condition_factor - 1.0) * 1.35)
        combustion_quality_penalty = min((engine_condition_factor - 1.0) * 0.45, 0.08)

        return {
            "days_since_engine_maintenance": round(days_since_engine_maintenance, 2),
            "engine_condition_factor": round(engine_condition_factor, 4),
            "maintenance_sfoc_multiplier": round(maintenance_sfoc_multiplier, 4),
            "maintenance_methane_multiplier": round(maintenance_methane_multiplier, 4),
            "maintenance_combustion_penalty": round(combustion_quality_penalty, 4),
        }

    def calculate_scr_snapshot(self, engine_load_ratio: float, mode: str, warmup_snapshot: Dict) -> Dict:
        if not self.has_scr or mode == MODE_STOPPED or engine_load_ratio <= 0.12:
            return {
                "scr_active": False,
                "scr_efficiency": 0.0,
                "scr_n2o_multiplier": 1.0,
            }

        thermal_state = safe_float(warmup_snapshot.get("engine_thermal_state"), 1.0)
        load_window = clamp((engine_load_ratio - 0.18) / 0.28, 0.0, 1.0)
        thermal_window = clamp((thermal_state - 0.76) / 0.18, 0.0, 1.0)
        mode_window = 0.92 if mode in {MODE_MANOEUVRING_25, MODE_MANOEUVRING_50} else 1.0
        scr_efficiency = self.scr_design_nox_reduction * load_window * thermal_window * mode_window
        scr_active = scr_efficiency > 0.05
        scr_n2o_multiplier = 1.0 + ((self.scr_n2o_penalty_factor - 1.0) * clamp(scr_efficiency / max(self.scr_design_nox_reduction, 0.01), 0.0, 1.0))
        return {
            "scr_active": scr_active,
            "scr_efficiency": round(clamp(scr_efficiency, 0.0, 0.98), 4),
            "scr_n2o_multiplier": round(clamp(scr_n2o_multiplier, 1.0, 1.35), 4),
        }

    def calculate_auxiliary_load_snapshot(self, mode: str, in_port_zone: bool, in_anchorage: bool) -> Dict:
        hotel_load_kw = self.hotel_load_kw
        berth_services_kw = 0.0
        cargo_services_kw = 0.0

        if mode == MODE_STOPPED or in_anchorage:
            berth_services_kw = max(280.0, hotel_load_kw * 0.22)
        elif in_port_zone:
            berth_services_kw = max(180.0, hotel_load_kw * 0.14)

        if in_port_zone and self.cargo_stage in {"outbound_full", "outbound_half"}:
            cargo_services_kw = max(120.0, self.installed_power_kw * 0.007)

        hotel_and_services_kw = hotel_load_kw + berth_services_kw + cargo_services_kw
        genset_rating_kw = self.aux_installed_power_kw / max(self.aux_genset_count, 1)
        generator_count = max(1, min(self.aux_genset_count, math.ceil(hotel_and_services_kw / max(genset_rating_kw * 0.85, 1.0))))
        available_kw = generator_count * genset_rating_kw
        generator_load_ratio = clamp(hotel_and_services_kw / max(available_kw, 1.0), 0.05, 1.05)

        if generator_load_ratio < 0.20:
            generator_efficiency_penalty = 1.12
        elif generator_load_ratio < 0.40:
            generator_efficiency_penalty = 1.05
        else:
            generator_efficiency_penalty = 1.0

        effective_aux_kw = hotel_and_services_kw * generator_efficiency_penalty
        aux_sfoc = self.sfoc_at_load(self.aux_base_sfoc_g_per_kwh, generator_load_ratio, role="aux")
        ae_fuel_burn_kg_hr = effective_aux_kw * aux_sfoc / 1000.0
        ae_co2_factor = self.co2_factor_for_fuel()
        if self.is_lng_fueled():
            ae_ch4_factor = 0.0007 if in_anchorage or in_port_zone else 0.00045
            ae_n2o_factor = 0.00010
            ae_nox_g_per_kwh = 2.8 + (1.2 * generator_load_ratio)
        else:
            ae_ch4_factor = 0.00002
            ae_n2o_factor = 0.00014
            ae_nox_g_per_kwh = 11.5 - (1.2 * generator_load_ratio)
        scrubber_reduction = 0.03 if self.scrubber_active else 1.0
        ae_sox_kg_hr = ae_fuel_burn_kg_hr * self.fuel_sulfur_fraction() * 2.0 * scrubber_reduction

        return {
            "hotel_load_kw": round(hotel_load_kw, 2),
            "auxiliary_total_kw": round(effective_aux_kw, 2),
            "auxiliary_requested_kw": round(hotel_and_services_kw, 2),
            "generator_count": generator_count,
            "generator_load_ratio": round(generator_load_ratio, 4),
            "generator_efficiency_penalty": round(generator_efficiency_penalty, 4),
            "ae_gensets_online": generator_count,
            "ae_load_fraction_pct": round(generator_load_ratio * 100.0, 2),
            "ae_sfoc_g_per_kwh": round(aux_sfoc, 2),
            "ae_fuel_burn_kg_hr": round(ae_fuel_burn_kg_hr, 3),
            "ae_co2_kg_hr": round(ae_fuel_burn_kg_hr * ae_co2_factor, 3),
            "ae_ch4_kg_hr": round(ae_fuel_burn_kg_hr * ae_ch4_factor, 4),
            "ae_n2o_kg_hr": round(ae_fuel_burn_kg_hr * ae_n2o_factor, 5),
            "ae_nox_kg_hr": round((effective_aux_kw * ae_nox_g_per_kwh) / 1000.0, 4),
            "ae_sox_kg_hr": round(ae_sox_kg_hr, 5),
        }

    def is_lng_fueled(self) -> bool:
        return self.fuel_type.upper().startswith("LNG")

    def fuel_sulfur_fraction(self) -> float:
        fuel = self.fuel_type.upper()
        if fuel.startswith("LNG"):
            return 0.00001
        if fuel.startswith("MGO"):
            return 0.0010
        if fuel.startswith("MDO"):
            return 0.0015
        if fuel.startswith("HFO"):
            return 0.0050
        return 0.0010

    def get_engine_curve_snapshot(self, load: float) -> Dict:
        points = sorted(self.engine_curve_points, key=lambda item: item[0])
        clamped_load = clamp(load, points[0][0], points[-1][0])

        for idx in range(len(points) - 1):
            left = points[idx]
            right = points[idx + 1]
            if left[0] <= clamped_load <= right[0]:
                span = max(right[0] - left[0], 1e-6)
                ratio = (clamped_load - left[0]) / span
                fuel_g_per_kwh = lerp(left[1], right[1], ratio)
                co2_g_per_kwh = lerp(left[2], right[2], ratio)
                return {
                    "fuel_g_per_kwh": round(fuel_g_per_kwh, 3),
                    "co2_g_per_kwh": round(co2_g_per_kwh, 3),
                }

        return {
            "fuel_g_per_kwh": round(points[-1][1], 3),
            "co2_g_per_kwh": round(points[-1][2], 3),
        }

    def get_wave_direction_deg(self, weather: Dict, sim_elapsed_days: float, sea_zone: SeaZone | None) -> float:
        wind_direction = safe_float(weather.get("weather_wind_direction"), 0.0)
        wave_bias_deg = sea_zone.wave_bias_deg if sea_zone else 18.0
        swell_offset = (wave_bias_deg + 6.0) * math.sin((sim_elapsed_days / 2.7) + math.radians(wind_direction / 3.0))
        return (wind_direction + wave_bias_deg + swell_offset) % 360.0

    def calculate_relative_wave_angle(self, heading_deg: float, weather: Dict, sim_elapsed_days: float, sea_zone: SeaZone | None) -> float:
        wave_direction = self.get_wave_direction_deg(weather, sim_elapsed_days, sea_zone)
        return round(heading_delta_deg(heading_deg, wave_direction), 2)

    def calculate_current_snapshot(self, lat: float, lon: float, heading_deg: float, sea_zone: SeaZone | None) -> Dict:
        hours = self.sim_time.timestamp() / 3600.0
        zone = sea_zone
        current_base_kn = zone.current_base_kn if zone else 0.45
        current_variability_kn = zone.current_variability_kn if zone else 0.55
        current_direction_deg = zone.current_direction_deg if zone else heading_deg
        current_direction_swing_deg = zone.current_direction_swing_deg if zone else 65.0

        speed = clamp(
            current_base_kn
            + current_variability_kn * math.sin(hours / 6.2 + math.radians(lat * 1.8))
            + (current_variability_kn * 0.55) * math.cos(hours / 3.9 + math.radians(lon * 2.3)),
            -1.8,
            1.8,
        )
        current_speed_kn = abs(speed)
        current_direction_deg = (
            current_direction_deg
            + current_direction_swing_deg * math.sin(hours / 7.4 + math.radians(lat))
            + (current_direction_swing_deg * 0.45) * math.cos(hours / 5.1 + math.radians(lon))
        ) % 360.0
        relative_current_signed = signed_heading_delta_deg(current_direction_deg, heading_deg)
        along_track_kn = current_speed_kn * math.cos(math.radians(relative_current_signed))
        cross_track_kn = current_speed_kn * math.sin(math.radians(relative_current_signed))

        return {
            "sea_zone_name": zone.name if zone else "Open Baltic fallback",
            "current_speed_kn": round(current_speed_kn, 3),
            "current_direction_deg": round(current_direction_deg, 2),
            "current_along_track_kn": round(along_track_kn, 3),
            "current_cross_track_kn": round(cross_track_kn, 3),
        }

    def calculate_wave_period_s(
        self,
        weather: Dict,
        wave_height_m: float,
        relative_wave_angle: float,
        sea_zone: SeaZone | None,
    ) -> float:
        wind_speed = safe_float(weather.get("weather_wind_speed"), 0.0)
        low, high = sea_zone.wave_period_range_s if sea_zone else (4.0, 7.0)
        encounter_factor = max(math.cos(math.radians(relative_wave_angle)), 0.0)
        swell_factor = clamp((wave_height_m / 2.5), 0.0, 1.0)
        wind_factor = clamp(wind_speed / 22.0, 0.0, 1.0)
        period = low + ((high - low) * (0.35 + (0.35 * swell_factor) + (0.20 * wind_factor) + (0.10 * encounter_factor)))
        return round(clamp(period, low, high + 0.6), 2)

    def get_position_jitter(self, mode: str) -> Tuple[float, float]:
        if mode != MODE_STEAMING:
            return (0.0, 0.0)

        return (
            self.rng.uniform(-0.00010, 0.00010),
            self.rng.uniform(-0.00010, 0.00010),
        )

    def navigation_safety_snapshot(self, depth_m: float, distance_to_port_nm: float, speed_kn: float) -> Dict:
        draft = self.calculate_draft()
        depth = depth_m
        squat = self.calculate_squat(speed_kn)
        effective_draft = draft + squat
        ukc = depth - effective_draft

        mode = self.determine_mode(distance_to_port_nm, ukc, draft)
        constrained_speed = speed_kn

        mode_speed_caps = {
            MODE_STOPPED: 0.0,
            MODE_MANOEUVRING_25: max(3.5, self.sea_speed_max * 0.30),
            MODE_MANOEUVRING_50: min(MAX_UKC_SAFE_SPEED_KN, self.sea_speed_max * 0.55),
            MODE_STEAMING: self.sea_speed_max,
        }
        constrained_speed = min(constrained_speed, mode_speed_caps.get(mode, self.sea_speed_max))

        if mode != MODE_STOPPED and ukc < UKC_SAFETY_LIMIT_M:
            constrained_speed = min(constrained_speed, MAX_UKC_SAFE_SPEED_KN)
            squat = self.calculate_squat(constrained_speed)
            effective_draft = draft + squat
            ukc = depth - effective_draft
            mode = self.determine_mode(distance_to_port_nm, ukc, draft)

        return {
            "mode": mode,
            "speed_kn": constrained_speed,
            "depth": round(depth, 2),
            "draft": round(draft, 2),
            "squat": round(squat, 3),
            "effective_draft": round(effective_draft, 3),
            "ukc": round(ukc, 3),
        }

    def calculate_relative_wind_angle(self, heading_deg: float, weather: Dict) -> float:
        wind_direction = weather.get("weather_wind_direction")
        if wind_direction is None:
            return 0.0
        return round(heading_delta_deg(heading_deg, safe_float(wind_direction)), 2)

    def calculate_weather_sea_force_snapshot(
        self,
        relative_wind_angle: float,
        relative_wave_angle: float,
        wind_speed: float,
        wave_height: float,
        wave_period_s: float,
        current_along_track_kn: float,
    ) -> Dict:
        wind_radians = math.radians(relative_wind_angle)
        wave_radians = math.radians(relative_wave_angle)

        wind_head_component = max(math.cos(wind_radians), 0.0)
        wind_tail_component = max(-math.cos(wind_radians), 0.0)
        wind_beam_component = abs(math.sin(wind_radians))

        wave_head_component = max(math.cos(wave_radians), 0.0)
        wave_follow_component = max(-math.cos(wave_radians), 0.0)
        wave_beam_component = abs(math.sin(wave_radians))

        wind_head_penalty = ((wind_speed / 24.0) ** 2) * wind_head_component * 0.085
        wind_beam_penalty = ((wind_speed / 24.0) ** 2) * wind_beam_component * 0.045
        tailwind_relief = ((wind_speed / 24.0) ** 2) * wind_tail_component * 0.040

        period_factor = clamp(0.88 + ((wave_period_s - 4.0) / 6.0) * 0.28, 0.82, 1.24)
        wave_base = min((wave_height ** 2) * 0.05 * period_factor, 0.52)
        wave_head_penalty = wave_base * (0.70 + (0.30 * wave_head_component))
        wave_beam_penalty = wave_base * wave_beam_component * 0.32
        following_sea_relief = wave_base * wave_follow_component * 0.24

        current_force_pct = clamp((-current_along_track_kn / max(self.sea_speed_min, 1.0)) * 100.0, -12.0, 12.0)

        wind_multiplier = clamp(1.0 + wind_head_penalty + wind_beam_penalty - tailwind_relief, 0.92, 1.38)
        wave_multiplier = clamp(1.0 + wave_head_penalty + wave_beam_penalty - following_sea_relief, 0.93, 1.42)

        signed_force_pct = (
            (wind_head_penalty + wind_beam_penalty + wave_head_penalty + wave_beam_penalty) * 100.0
            - (tailwind_relief + following_sea_relief) * 100.0
            + current_force_pct
        )
        if signed_force_pct > 4.0:
            force_state = "against"
        elif signed_force_pct < -4.0:
            force_state = "favorable"
        else:
            force_state = "neutral"

        return {
            "wind_multiplier": round(wind_multiplier, 4),
            "wave_multiplier": round(wave_multiplier, 4),
            "weather_sea_force_state": force_state,
            "weather_sea_force_pct": round(abs(signed_force_pct), 2),
            "weather_sea_force_index": round(signed_force_pct, 2),
            "wind_penalty_pct": round(max((wind_multiplier - 1.0) * 100.0, 0.0), 2),
            "sea_penalty_pct": round(max((wave_multiplier - 1.0) * 100.0, 0.0), 2),
        }

    def calculate_shallow_water_multiplier(self, depth_m: float, draft_m: float) -> Tuple[bool, float]:
        if draft_m <= 0:
            return False, 1.0

        threshold = 1.5 * draft_m
        if depth_m >= threshold:
            return False, 1.0

        severity = clamp((threshold - depth_m) / max(0.5 * draft_m, 0.1), 0.0, 1.0)
        multiplier = 1.15 + (0.10 * severity)
        return True, round(multiplier, 4)

    def calculate_calm_water_power_kw(self, displacement_tonnes: float, sog_kn: float) -> float:
        if sog_kn <= 0:
            return 0.0
        return ((displacement_tonnes ** (2.0 / 3.0)) * (sog_kn ** 3)) / max(self.admiralty_coefficient, 1.0)

    def calculate_physics_enhanced_power(
        self,
        speed_kn: float,
        draft_m: float,
        depth_m: float,
        weather: Dict,
        fouling_multiplier: float,
        shallow_water_multiplier: float,
        mode_multiplier: float,
        relative_wind_angle: float,
    ) -> Dict:
        if speed_kn <= 0:
            return {
                "model_mode": MODEL_MODE_PHYSICS_ENHANCED,
                "speed_ms": 0.0,
                "reynolds_number": 0.0,
                "friction_coefficient": 0.0,
                "friction_resistance_kn": 0.0,
                "residual_resistance_kn": 0.0,
                "air_resistance_kn": 0.0,
                "shallow_water_multiplier": shallow_water_multiplier,
                "fouling_multiplier": fouling_multiplier,
                "propulsive_efficiency": round(self.propulsive_efficiency or 0.7, 4),
                "raw_power_kw": 0.0,
                "clamped_power_kw": 0.0,
            }

        rho_water = 1025.0
        rho_air = 1.225
        kinematic_viscosity = 1.19e-6
        speed_ms = speed_kn * 0.514444
        reynolds_number = max((speed_ms * max(self.length_pp_m or 1.0, 1.0)) / kinematic_viscosity, 1.0)
        log_re = max(math.log10(reynolds_number), 2.01)
        friction_coefficient = 0.075 / ((log_re - 2.0) ** 2)
        friction_resistance_n = 0.5 * rho_water * (speed_ms ** 2) * max(self.wetted_surface_m2 or 1.0, 1.0) * friction_coefficient
        residual_factor = 0.10 + (0.20 * self.block_coefficient) + (0.04 * max((draft_m / max(self.design_draft_m or draft_m, 0.1)) - 1.0, 0.0))
        residual_resistance_n = friction_resistance_n * residual_factor
        relative_wind_component = max(math.cos(math.radians(relative_wind_angle)), 0.0)
        relative_wind_speed_ms = max(safe_float(weather.get("weather_wind_speed"), 0.0) * 0.514444 * relative_wind_component, 0.0)
        air_drag_area = max(self.air_drag_area_m2 or 1.0, 1.0)
        air_resistance_n = 0.5 * rho_air * (relative_wind_speed_ms ** 2) * air_drag_area * 0.9
        total_resistance_n = (
            (friction_resistance_n + residual_resistance_n + air_resistance_n)
            * max(self.hull_roughness_allowance or 1.0, 1.0)
            * fouling_multiplier
            * shallow_water_multiplier
            * mode_multiplier
        )
        propulsive_efficiency = clamp(self.propulsive_efficiency or 0.7, 0.45, 0.85)
        raw_power_kw = (total_resistance_n / 1000.0) * speed_ms / propulsive_efficiency
        clamped_power_kw = clamp(raw_power_kw, 0.0, self.installed_power_kw * 1.15)
        return {
            "model_mode": MODEL_MODE_PHYSICS_ENHANCED,
            "speed_ms": round(speed_ms, 4),
            "reynolds_number": round(reynolds_number, 2),
            "friction_coefficient": round(friction_coefficient, 6),
            "friction_resistance_kn": round(friction_resistance_n / 1000.0, 4),
            "residual_resistance_kn": round(residual_resistance_n / 1000.0, 4),
            "air_resistance_kn": round(air_resistance_n / 1000.0, 4),
            "shallow_water_multiplier": round(shallow_water_multiplier, 4),
            "fouling_multiplier": round(fouling_multiplier, 4),
            "propulsive_efficiency": round(propulsive_efficiency, 4),
            "raw_power_kw": round(raw_power_kw, 2),
            "clamped_power_kw": round(clamped_power_kw, 2),
        }

    def calculate_model_power_diagnostics(
        self,
        speed_kn: float,
        draft_m: float,
        depth_m: float,
        weather: Dict,
        fouling_multiplier: float,
        shallow_water_multiplier: float,
        mode_multiplier: float,
        relative_wind_angle: float,
        raw_required_power_kw: float,
    ) -> Dict:
        if SIMULATOR_MODEL_MODE == MODEL_MODE_PHYSICS_ENHANCED:
            return self.calculate_physics_enhanced_power(
                speed_kn=speed_kn,
                draft_m=draft_m,
                depth_m=depth_m,
                weather=weather,
                fouling_multiplier=fouling_multiplier,
                shallow_water_multiplier=shallow_water_multiplier,
                mode_multiplier=mode_multiplier,
                relative_wind_angle=relative_wind_angle,
            )

        return {
            "model_mode": MODEL_MODE_ADMIRALTY_FAST,
            "speed_ms": round(speed_kn * 0.514444, 4),
            "reynolds_number": None,
            "friction_coefficient": None,
            "friction_resistance_kn": None,
            "residual_resistance_kn": None,
            "air_resistance_kn": None,
            "shallow_water_multiplier": round(shallow_water_multiplier, 4),
            "fouling_multiplier": round(fouling_multiplier, 4),
            "propulsive_efficiency": round(self.propulsive_efficiency or 0.7, 4),
            "raw_power_kw": round(raw_required_power_kw, 2),
            "clamped_power_kw": round(clamp(raw_required_power_kw, 0.0, self.installed_power_kw * 1.15), 2),
        }

    def build_validation_prediction(self, row: Dict[str, str]) -> Dict:
        speed_kn = max(csv_float(row, "speed_over_ground") or 0.0, 0.0)
        draft_m = csv_float(row, "draft") or self.calculate_draft()
        wave_height = csv_float(row, "weather_wave_height", "wave_height") or 1.0
        wind_speed = csv_float(row, "weather_wind_speed", "wind_speed") or 8.0
        weather = {
            "weather_wind_speed": wind_speed,
            "weather_wind_direction": 180.0,
            "weather_wave_height": wave_height,
            "weather_air_temp": 10.0,
            "weather_sea_temp": 8.0,
            "weather_pressure": 1013.0,
            "weather_source": "validation_csv",
            "weather_timestamp": csv_value(row, "timestamp_utc"),
            "weather_is_forecast": False,
            "weather_fallback_mode": None,
        }
        shallow_water_flag, shallow_water_multiplier = self.calculate_shallow_water_multiplier(
            max(draft_m * 3.0, draft_m + 5.0),
            draft_m,
        )
        fouling_multiplier = self.get_fouling_multiplier(self.get_sim_elapsed_days())
        relative_wind_angle = 0.0
        model_diagnostics = self.calculate_model_power_diagnostics(
            speed_kn=speed_kn,
            draft_m=draft_m,
            depth_m=max(draft_m * 3.0, draft_m + 5.0),
            weather=weather,
            fouling_multiplier=fouling_multiplier,
            shallow_water_multiplier=shallow_water_multiplier,
            mode_multiplier=1.0,
            relative_wind_angle=relative_wind_angle,
            raw_required_power_kw=self.calculate_calm_water_power_kw(self.estimate_displacement_tonnes(), speed_kn),
        )
        predicted_power_kw = model_diagnostics["clamped_power_kw"]
        engine_curve_snapshot = self.get_engine_curve_snapshot(max(predicted_power_kw / max(self.installed_power_kw, 1.0), 0.25))
        predicted_fuel_kg_h = (
            predicted_power_kw * engine_curve_snapshot["fuel_g_per_kwh"] / 1000.0
            if predicted_power_kw > 0
            else 0.0
        )
        predicted_co2_kg_h = (
            predicted_power_kw * engine_curve_snapshot["co2_g_per_kwh"] / 1000.0
            if predicted_power_kw > 0
            else 0.0
        )
        return {
            "predicted_power_kw": round(predicted_power_kw, 3),
            "predicted_fuel_kg_h": round(predicted_fuel_kg_h, 3),
            "predicted_co2_kg_h": round(predicted_co2_kg_h, 3),
            "shallow_water_flag": shallow_water_flag,
            "model_diagnostics": model_diagnostics,
        }

    def calculate_power_snapshot(
        self,
        speed_kn: float,
        heading_deg: float,
        depth_m: float,
        distance_to_port_nm: float,
        weather: Dict,
        lat: float,
        lon: float,
        commanded_speed_kn: float | None = None,
        zone_snapshot: Dict | None = None,
    ) -> Dict:
        draft = self.calculate_draft()
        depth = depth_m
        squat = self.calculate_squat(speed_kn)
        effective_draft = draft + squat
        ukc = depth - effective_draft
        mode = self.determine_mode(distance_to_port_nm, ukc, draft)
        in_port_zone = bool(zone_snapshot and zone_snapshot.get("in_port_zone"))
        in_anchorage = bool(zone_snapshot and zone_snapshot.get("in_anchorage"))
        if in_anchorage:
            mode = MODE_STOPPED

        sim_elapsed_days = self.get_sim_elapsed_days()
        fouling_cycle_day = self.get_fouling_cycle_day(sim_elapsed_days)
        fouling_stage = self.get_fouling_stage(fouling_cycle_day)
        fouling_multiplier = self.get_fouling_multiplier(sim_elapsed_days)
        hull_condition_label = self.get_hull_condition_label(fouling_multiplier)
        propeller_fouling_multiplier = self.get_propeller_fouling_multiplier(sim_elapsed_days)
        propeller_condition_label = self.get_propeller_condition_label(propeller_fouling_multiplier)
        sea_zone = self.active_sea_zone(lat, lon)

        wind_speed = safe_float(weather.get("weather_wind_speed"), 0.0)
        wave_height = safe_float(weather.get("weather_wave_height"), 0.0)
        relative_wind_angle = self.calculate_relative_wind_angle(heading_deg, weather)
        relative_wave_angle = self.calculate_relative_wave_angle(heading_deg, weather, sim_elapsed_days, sea_zone)
        current_snapshot = self.calculate_current_snapshot(lat, lon, heading_deg, sea_zone)
        wave_period_s = self.calculate_wave_period_s(weather, wave_height, relative_wave_angle, sea_zone)
        weather_sea_snapshot = self.calculate_weather_sea_force_snapshot(
            relative_wind_angle,
            relative_wave_angle,
            wind_speed,
            wave_height,
            wave_period_s,
            current_snapshot["current_along_track_kn"],
        )

        shallow_water_flag, shallow_water_multiplier = self.calculate_shallow_water_multiplier(depth, draft)
        wind_multiplier = weather_sea_snapshot["wind_multiplier"]
        wave_multiplier = weather_sea_snapshot["wave_multiplier"]
        squat_multiplier = 1.0 + min((squat / max(draft, 1.0)) * 0.25, 0.12)
        loading_ratio = clamp(self.cargo_quantity / max(self.cargo_max, 1.0), 0.0, 1.05)
        ballast_hydrodynamic_multiplier = (
            0.93 + (0.05 * loading_ratio) + (0.02 * self.block_coefficient)
            if self.cargo_stage == "ballast"
            else 1.0 + (0.03 * loading_ratio) + (0.015 * max(draft - self.ballast_draft, 0.0))
        )
        load_condition_multiplier = self.ballast_efficiency_modifier if self.cargo_stage == "ballast" else self.loaded_efficiency_modifier
        mode_multiplier = (
            1.0 if mode == MODE_STEAMING
            else self.manoeuvring_efficiency_penalty
            if mode == MODE_MANOEUVRING_50
            else self.manoeuvring_efficiency_penalty + 0.05
            if mode == MODE_MANOEUVRING_25
            else 0.0
        )

        auxiliary_snapshot = self.calculate_auxiliary_load_snapshot(mode, in_port_zone, in_anchorage)
        warmup_snapshot = self.calculate_engine_warmup_snapshot(mode, in_anchorage)
        engine_condition_snapshot = self.calculate_engine_condition_snapshot(sim_elapsed_days)

        displacement_tonnes = self.estimate_displacement_tonnes()
        calm_water_power_kw = self.calculate_calm_water_power_kw(displacement_tonnes, speed_kn)
        calm_water_power_kw *= ballast_hydrodynamic_multiplier
        after_fouling_kw = calm_water_power_kw * fouling_multiplier
        fouling_added_kw = after_fouling_kw - calm_water_power_kw
        after_propeller_kw = after_fouling_kw * propeller_fouling_multiplier
        propeller_fouling_added_kw = after_propeller_kw - after_fouling_kw
        after_wind_kw = after_propeller_kw * wind_multiplier
        weather_added_kw = after_wind_kw - after_propeller_kw
        after_wave_kw = after_wind_kw * wave_multiplier
        sea_added_kw = after_wave_kw - after_wind_kw
        after_squat_kw = after_wave_kw * squat_multiplier
        draft_added_kw = after_squat_kw - after_wave_kw
        after_shallow_kw = after_squat_kw * shallow_water_multiplier
        water_depth_added_kw = after_shallow_kw - after_squat_kw
        after_load_kw = after_shallow_kw * load_condition_multiplier
        cargo_added_kw = after_load_kw - after_shallow_kw
        propulsion_power_kw = after_load_kw * mode_multiplier
        manoeuvring_added_kw = propulsion_power_kw - after_load_kw

        raw_required_power_kw = max(propulsion_power_kw, 0.0)
        model_diagnostics = self.calculate_model_power_diagnostics(
            speed_kn=speed_kn,
            draft_m=draft,
            depth_m=depth,
            weather=weather,
            fouling_multiplier=fouling_multiplier,
            shallow_water_multiplier=shallow_water_multiplier,
            mode_multiplier=mode_multiplier,
            relative_wind_angle=relative_wind_angle,
            raw_required_power_kw=raw_required_power_kw,
        )
        if SIMULATOR_MODEL_MODE == MODEL_MODE_PHYSICS_ENHANCED:
            raw_required_power_kw = safe_float(model_diagnostics["clamped_power_kw"], raw_required_power_kw)
        raw_engine_load_ratio = 0.0 if raw_required_power_kw <= 0 else clamp(raw_required_power_kw / max(self.installed_power_kw, 1.0), 0.05, 1.15)

        efficiency_drivers = {
            "weather": max(weather_added_kw, 0.0),
            "sea": max(sea_added_kw, 0.0),
            "cargo": max(cargo_added_kw, 0.0),
            "draft": max(draft_added_kw, 0.0),
            "water_depth": max(water_depth_added_kw, 0.0),
            "fouling": max(fouling_added_kw, 0.0),
            "propeller_fouling": max(propeller_fouling_added_kw, 0.0),
            "manoeuvring": max(manoeuvring_added_kw, 0.0),
        }
        sorted_drivers = sorted(efficiency_drivers.items(), key=lambda item: item[1], reverse=True)
        primary_driver, primary_driver_kw = sorted_drivers[0]
        secondary_driver, secondary_driver_kw = sorted_drivers[1]

        significant_driver_labels = [
            name.replace("_", " ")
            for name, kw in sorted_drivers
            if kw >= max(calm_water_power_kw * 0.03, 25.0)
        ]
        efficiency_reason_summary = ", ".join(significant_driver_labels[:3]) if significant_driver_labels else "baseline calm-water operation"

        if mode == MODE_STOPPED:
            efficiency_state = "stopped_for_safety_or_berth"
        elif mode in {MODE_MANOEUVRING_25, MODE_MANOEUVRING_50} and water_depth_added_kw > 0:
            efficiency_state = "constrained_by_water_depth"
        elif primary_driver == "propeller_fouling":
            efficiency_state = "efficiency_penalized_by_propeller_fouling"
        elif weather_sea_snapshot["weather_sea_force_state"] == "against":
            efficiency_state = "weather_and_sea_against_vessel"
        elif primary_driver == "fouling":
            efficiency_state = "efficiency_penalized_by_fouling"
        elif primary_driver == "cargo":
            efficiency_state = "loaded_condition_penalty"
        else:
            efficiency_state = "normal_open_water_efficiency"

        control_snapshot = self.calculate_propulsion_control_snapshot(
            commanded_speed_kn if commanded_speed_kn is not None else speed_kn,
            speed_kn,
            raw_required_power_kw,
            max(raw_engine_load_ratio, 0.05),
            weather_sea_snapshot,
            shallow_water_flag,
            mode,
        )

        target_load_ratio = 0.0 if mode == MODE_STOPPED else control_snapshot["target_load_ratio"]
        if mode == MODE_STOPPED:
            target_rpm = 0
        else:
            if mode == MODE_MANOEUVRING_25:
                rpm_low, rpm_high = self.rpm_range_manoeuvring_quarter
            elif mode == MODE_MANOEUVRING_50:
                rpm_low, rpm_high = self.rpm_range_manoeuvring_half
            else:
                rpm_low, rpm_high = self.rpm_range_steaming
            target_rpm = int(round(rpm_low + ((rpm_high - rpm_low) * clamp(target_load_ratio, 0.0, 1.0))))

        required_power_kw, rpm, governor_snapshot = self.apply_propulsion_response(
            0.0 if mode == MODE_STOPPED else control_snapshot["target_power_kw"],
            target_rpm,
            mode,
            max(target_load_ratio, 0.0),
        )
        main_engine_running = mode != MODE_STOPPED and required_power_kw > 80.0
        engine_load_ratio = clamp(required_power_kw / max(self.installed_power_kw, 1.0), 0.05, 1.15) if main_engine_running else 0.0
        transient_combustion_snapshot = self.calculate_transient_combustion_snapshot(
            max(engine_load_ratio, 0.05),
            governor_snapshot,
            mode,
        )
        shaft_snapshot = self.calculate_propeller_shaft_snapshot(
            governor_snapshot["shaft_power_kw"] if main_engine_running else 0.0,
            governor_snapshot["shaft_rpm"] if main_engine_running else 0.0,
            speed_kn,
            propeller_fouling_multiplier,
            mode,
        )
        scr_snapshot = self.calculate_scr_snapshot(engine_load_ratio, mode, warmup_snapshot)

        effective_combustion_quality = clamp(
            transient_combustion_snapshot["combustion_quality_state"]
            - warmup_snapshot["warmup_combustion_penalty"]
            - engine_condition_snapshot["maintenance_combustion_penalty"],
            0.70,
            1.03,
        )
        sfoc_transient_multiplier = (
            transient_combustion_snapshot["sfoc_transient_multiplier"]
            * warmup_snapshot["warmup_sfoc_multiplier"]
            * engine_condition_snapshot["maintenance_sfoc_multiplier"]
        )
        methane_transient_multiplier = (
            transient_combustion_snapshot["methane_transient_multiplier"]
            * warmup_snapshot["warmup_methane_multiplier"]
            * engine_condition_snapshot["maintenance_methane_multiplier"]
        )
        nox_transient_multiplier = transient_combustion_snapshot["nox_transient_multiplier"]
        n2o_transient_multiplier = transient_combustion_snapshot["n2o_transient_multiplier"] * scr_snapshot["scr_n2o_multiplier"]

        engine_curve_snapshot = self.get_engine_curve_snapshot(max(engine_load_ratio, 0.25))
        base_sfoc = engine_curve_snapshot["fuel_g_per_kwh"]
        base_co2_g_per_kwh = engine_curve_snapshot["co2_g_per_kwh"]
        if mode in {MODE_MANOEUVRING_25, MODE_MANOEUVRING_50}:
            base_sfoc *= 1.03
            base_co2_g_per_kwh *= 1.01
        elif mode == MODE_STOPPED:
            base_sfoc *= 1.10
            base_co2_g_per_kwh *= 1.02
        if in_port_zone or in_anchorage:
            base_sfoc *= 1.04 if self.is_lng_fueled() else 1.07
            base_co2_g_per_kwh *= 1.01

        low_load_penalty = 1.0
        if main_engine_running:
            if engine_load_ratio < 0.15:
                low_load_penalty = 1.12
            elif engine_load_ratio < 0.25:
                low_load_penalty = 1.08
            elif engine_load_ratio < 0.40:
                low_load_penalty = 1.04
            elif engine_load_ratio < 0.65:
                low_load_penalty = 1.02

        slow_steaming_sfoc = self.sfoc_at_load(base_sfoc, max(engine_load_ratio, 0.05))
        sfoc_g_per_kwh = slow_steaming_sfoc * low_load_penalty * sfoc_transient_multiplier if main_engine_running else 0.0
        main_engine_fuel_burn_rate = (required_power_kw * sfoc_g_per_kwh / 1000.0) if main_engine_running else 0.0

        methane_zone_multiplier = 1.0
        methane_load_band_multiplier = 1.0
        n2o_load_band_multiplier = 1.0
        me_co2_value = 0.0
        me_ch4_value = 0.0
        me_n2o_value = 0.0
        me_nox_value_kg_h = 0.0
        me_sox_value_kg_h = 0.0
        nox_g_per_kwh = 0.0
        sulfur_fraction = self.fuel_sulfur_fraction()
        scrubber_reduction = 0.03 if self.scrubber_active else 1.0

        if main_engine_running:
            if self.is_lng_fueled():
                methane_zone_multiplier = 1.18 if (in_port_zone or in_anchorage) else 1.0
                methane_load_band_multiplier = 1.0 + max(0.0, 0.55 - engine_load_ratio) * 2.1
                n2o_load_band_multiplier = 0.78 if engine_load_ratio < 0.25 else 0.86 if engine_load_ratio < 0.60 else 0.94
                ch4_g_per_kwh = 6.0 * ((1.0 - engine_load_ratio) ** 2) + 0.5
                nox_g_per_kwh = (2.0 + 2.0 * engine_load_ratio) * nox_transient_multiplier
                me_co2_value = required_power_kw * base_co2_g_per_kwh / 1000.0
                me_ch4_value = (
                    (required_power_kw * ch4_g_per_kwh / 1000.0)
                    * methane_zone_multiplier
                    * methane_load_band_multiplier
                    * methane_transient_multiplier
                )
                me_n2o_value = (
                    main_engine_fuel_burn_rate
                    * self.n2o_factor
                    * n2o_load_band_multiplier
                    * n2o_transient_multiplier
                )
            else:
                methane_slip_factor = self.methane_slip_manoeuvring_factor if mode in {MODE_MANOEUVRING_25, MODE_MANOEUVRING_50} else self.methane_slip_steaming_factor
                if engine_load_ratio < 0.15:
                    methane_load_band_multiplier = 2.15
                    n2o_load_band_multiplier = 0.82
                elif engine_load_ratio < 0.25:
                    methane_load_band_multiplier = 1.72
                    n2o_load_band_multiplier = 0.90
                elif engine_load_ratio < 0.40:
                    methane_load_band_multiplier = 1.34
                    n2o_load_band_multiplier = 0.98
                elif engine_load_ratio < 0.75:
                    methane_load_band_multiplier = 1.0
                    n2o_load_band_multiplier = 1.04
                else:
                    methane_load_band_multiplier = 0.94
                    n2o_load_band_multiplier = 1.12
                methane_low_load_factor = (1.0 + clamp(0.70 - engine_load_ratio, 0.0, 0.70) * 1.10) * methane_load_band_multiplier
                methane_zone_multiplier = 1.18 + clamp(0.30 - engine_load_ratio, 0.0, 0.25) * 1.6 if (in_port_zone or in_anchorage) else 1.0
                nox_g_per_kwh = (18.0 - 5.0 * engine_load_ratio) * nox_transient_multiplier
                me_co2_value = required_power_kw * base_co2_g_per_kwh / 1000.0
                me_ch4_value = (
                    main_engine_fuel_burn_rate
                    * methane_slip_factor
                    * methane_low_load_factor
                    * methane_zone_multiplier
                    * methane_transient_multiplier
                )
                me_n2o_value = (
                    main_engine_fuel_burn_rate
                    * self.n2o_factor
                    * (0.90 + (0.40 * engine_load_ratio))
                    * n2o_load_band_multiplier
                    * n2o_transient_multiplier
                )

            nox_g_per_kwh = max(nox_g_per_kwh * (1.0 - scr_snapshot["scr_efficiency"]), 0.0)
            me_nox_value_kg_h = required_power_kw * nox_g_per_kwh / 1000.0
            me_sox_value_kg_h = main_engine_fuel_burn_rate * sulfur_fraction * 2.0 * scrubber_reduction

        co2_value = me_co2_value + auxiliary_snapshot["ae_co2_kg_hr"]
        ch4_value = me_ch4_value + auxiliary_snapshot["ae_ch4_kg_hr"]
        n2o_value = me_n2o_value + auxiliary_snapshot["ae_n2o_kg_hr"]
        nox_value_kg_h = me_nox_value_kg_h + auxiliary_snapshot["ae_nox_kg_hr"]
        sox_value_kg_h = me_sox_value_kg_h + auxiliary_snapshot["ae_sox_kg_hr"]
        fuel_burn_rate = main_engine_fuel_burn_rate + auxiliary_snapshot["ae_fuel_burn_kg_hr"]
        sox_g_per_kwh = (sox_value_kg_h * 1000.0 / max(required_power_kw + auxiliary_snapshot["auxiliary_total_kw"], 1.0)) if (required_power_kw + auxiliary_snapshot["auxiliary_total_kw"]) > 0 else 0.0
        black_smoke_proxy = (
            main_engine_running
            and engine_load_ratio < 0.18
            and (in_port_zone or in_anchorage or mode in {MODE_MANOEUVRING_25, MODE_MANOEUVRING_50})
        ) or (main_engine_running and engine_load_ratio > 0.94 and weather_sea_snapshot["weather_sea_force_state"] == "against")

        return {
            "mode": mode,
            "draft": round(draft, 2),
            "depth": round(depth, 2),
            "squat": round(squat, 3),
            "effective_draft": round(effective_draft, 3),
            "ukc": round(ukc, 3),
            "fouling_cycle_day": round(fouling_cycle_day, 3),
            "fouling_stage": fouling_stage,
            "fouling_multiplier": fouling_multiplier,
            "propeller_fouling_multiplier": propeller_fouling_multiplier,
            "days_since_hull_cleaning": round(fouling_cycle_day, 3),
            "hull_condition_label": hull_condition_label,
            "propeller_condition_label": propeller_condition_label,
            "relative_wind_angle": round(relative_wind_angle, 2),
            "relative_wave_angle": round(relative_wave_angle, 2),
            "wave_period_s": wave_period_s,
            "sea_zone_name": current_snapshot["sea_zone_name"],
            "current_speed_kn": current_snapshot["current_speed_kn"],
            "current_direction_deg": current_snapshot["current_direction_deg"],
            "current_along_track_kn": current_snapshot["current_along_track_kn"],
            "current_cross_track_kn": current_snapshot["current_cross_track_kn"],
            "weather_sea_force_state": weather_sea_snapshot["weather_sea_force_state"],
            "weather_sea_force_pct": weather_sea_snapshot["weather_sea_force_pct"],
            "weather_sea_force_index": weather_sea_snapshot["weather_sea_force_index"],
            "efficiency_state": efficiency_state,
            "efficiency_reason_summary": efficiency_reason_summary,
            "dominant_emission_driver": primary_driver,
            "dominant_emission_driver_kw": round(primary_driver_kw, 2),
            "secondary_emission_driver": secondary_driver,
            "secondary_emission_driver_kw": round(secondary_driver_kw, 2),
            "weather_penalty_pct": weather_sea_snapshot["wind_penalty_pct"],
            "sea_penalty_pct": weather_sea_snapshot["sea_penalty_pct"],
            "cargo_penalty_pct": round(max((load_condition_multiplier - 1.0) * 100.0, 0.0), 2),
            "draft_penalty_pct": round(max(((squat_multiplier * ballast_hydrodynamic_multiplier) - 1.0) * 100.0, 0.0), 2),
            "water_depth_penalty_pct": round(max((shallow_water_multiplier - 1.0) * 100.0, 0.0), 2),
            "fouling_penalty_pct": round(max((fouling_multiplier - 1.0) * 100.0, 0.0), 2),
            "shallow_water_flag": shallow_water_flag,
            "wind_multiplier": round(wind_multiplier, 4),
            "wave_multiplier": round(wave_multiplier, 4),
            "squat_multiplier": round(squat_multiplier, 4),
            "shallow_water_multiplier": round(shallow_water_multiplier, 4),
            "ballast_hydrodynamic_multiplier": round(ballast_hydrodynamic_multiplier, 4),
            "load_condition_multiplier": round(load_condition_multiplier, 4),
            "mode_multiplier": round(mode_multiplier, 4),
            "calm_water_power_kw": round(calm_water_power_kw, 2),
            "hotel_load_kw": auxiliary_snapshot["hotel_load_kw"],
            "auxiliary_load_kw": auxiliary_snapshot["auxiliary_total_kw"],
            "generator_count": auxiliary_snapshot["generator_count"],
            "generator_load_ratio": auxiliary_snapshot["generator_load_ratio"],
            "speed_error_kn": control_snapshot["speed_error_kn"],
            "speed_pid_trim": control_snapshot["speed_pid_trim"],
            "sea_margin_factor": control_snapshot["sea_margin_factor"],
            "controller_factor": control_snapshot["controller_factor"],
            "target_load_ratio": round(target_load_ratio, 4),
            "governor_error": governor_snapshot["governor_error"],
            "governor_integral": governor_snapshot["governor_integral"],
            "governor_trim": governor_snapshot["governor_trim"],
            "governor_target_power_kw": governor_snapshot["governor_target_power_kw"],
            "raw_required_power_kw": round(raw_required_power_kw, 2),
            "required_power_kw": round(required_power_kw, 2),
            "shaft_power_kw": shaft_snapshot["shaft_power_kw"],
            "shaft_rpm": shaft_snapshot["shaft_rpm"],
            "shaft_torque_knm": shaft_snapshot["shaft_torque_knm"],
            "shaft_line_efficiency": shaft_snapshot["shaft_line_efficiency"],
            "propeller_slip_ratio": shaft_snapshot["propeller_slip_ratio"],
            "propeller_open_water_efficiency": shaft_snapshot["propeller_open_water_efficiency"],
            "propeller_delivered_thrust_kw": shaft_snapshot["propeller_delivered_thrust_kw"],
            "fuel_burn_rate": round(fuel_burn_rate, 3),
            "main_engine_fuel_burn_rate": round(main_engine_fuel_burn_rate, 3),
            "aux_engine_fuel_burn_rate": auxiliary_snapshot["ae_fuel_burn_kg_hr"],
            "model_mode": model_diagnostics["model_mode"],
            "speed_ms": model_diagnostics["speed_ms"],
            "reynolds_number": model_diagnostics["reynolds_number"],
            "friction_coefficient": model_diagnostics["friction_coefficient"],
            "friction_resistance_kn": model_diagnostics["friction_resistance_kn"],
            "residual_resistance_kn": model_diagnostics["residual_resistance_kn"],
            "air_resistance_kn": model_diagnostics["air_resistance_kn"],
            "propulsive_efficiency": model_diagnostics["propulsive_efficiency"],
            "raw_power_kw": model_diagnostics["raw_power_kw"],
            "clamped_power_kw": model_diagnostics["clamped_power_kw"],
            "engine_load_ratio": round(engine_load_ratio, 4),
            "sfoc_g_per_kwh": round(sfoc_g_per_kwh, 2),
            "engine_thermal_state": warmup_snapshot["engine_thermal_state"],
            "minutes_since_engine_restart": warmup_snapshot["minutes_since_engine_restart"],
            "warmup_sfoc_multiplier": warmup_snapshot["warmup_sfoc_multiplier"],
            "warmup_methane_multiplier": warmup_snapshot["warmup_methane_multiplier"],
            "days_since_engine_maintenance": engine_condition_snapshot["days_since_engine_maintenance"],
            "engine_condition_factor": engine_condition_snapshot["engine_condition_factor"],
            "scr_active": scr_snapshot["scr_active"],
            "scr_efficiency": scr_snapshot["scr_efficiency"],
            "scr_n2o_multiplier": scr_snapshot["scr_n2o_multiplier"],
            "turbocharger_state": round(self.turbocharger_state, 4),
            "combustion_quality_state": round(effective_combustion_quality, 4),
            "sfoc_transient_multiplier": round(sfoc_transient_multiplier, 4),
            "nox_transient_multiplier": round(nox_transient_multiplier, 4),
            "methane_transient_multiplier": round(methane_transient_multiplier, 4),
            "n2o_transient_multiplier": round(n2o_transient_multiplier, 4),
            "methane_zone_multiplier": round(methane_zone_multiplier, 4),
            "methane_load_band_multiplier": round(methane_load_band_multiplier, 4),
            "n2o_load_band_multiplier": round(n2o_load_band_multiplier, 4),
            "nox_g_per_kwh": round(max(nox_g_per_kwh, 0.0), 4),
            "nox_value_kg_h": round(nox_value_kg_h, 4),
            "sox_g_per_kwh": round(max(sox_g_per_kwh, 0.0), 4),
            "sox_value_kg_h": round(sox_value_kg_h, 5),
            "me_co2_kg_hr": round(me_co2_value, 3),
            "me_ch4_kg_hr": round(me_ch4_value, 4),
            "me_n2o_kg_hr": round(me_n2o_value, 5),
            "me_nox_kg_hr": round(me_nox_value_kg_h, 4),
            "me_sox_kg_hr": round(me_sox_value_kg_h, 5),
            "ae_co2_kg_hr": auxiliary_snapshot["ae_co2_kg_hr"],
            "ae_ch4_kg_hr": auxiliary_snapshot["ae_ch4_kg_hr"],
            "ae_n2o_kg_hr": auxiliary_snapshot["ae_n2o_kg_hr"],
            "ae_nox_kg_hr": auxiliary_snapshot["ae_nox_kg_hr"],
            "ae_sox_kg_hr": auxiliary_snapshot["ae_sox_kg_hr"],
            "ae_gensets_online": auxiliary_snapshot["ae_gensets_online"],
            "ae_load_fraction_pct": auxiliary_snapshot["ae_load_fraction_pct"],
            "black_smoke_proxy": black_smoke_proxy,
            "rpm": rpm,
            "co2_value": round(co2_value, 3),
            "ch4_value": round(ch4_value, 4),
            "n2o_value": round(n2o_value, 5),
            "nox_value_kg_h": round(nox_value_kg_h, 4),
            "sox_value_kg_h": round(sox_value_kg_h, 5),
        }

    def advance_one_step(self) -> Dict:
        self.seq += 1
        self.sim_time += timedelta(minutes=SIMULATED_MINUTES_PER_LOOP)

        prev_from_label = self.current_leg_from_label()
        prev_to_label = self.current_leg_to_label()
        prev_leg_index = self.leg_index
        prev_leg_progress = self.leg_progress
        prev_lat, prev_lon = self.current_position()
        current_leg_heading = self.current_leg_heading()
        distance_to_port_before = self.distance_to_next_port_nm()
        pre_bathymetry = self.get_bathymetric_depth(prev_lat, prev_lon, distance_to_port_before)
        pre_weather = fetch_weather(prev_lat, prev_lon, reference_time=self.sim_time)
        pre_zones = self.active_port_zones(prev_lat, prev_lon)
        pre_sea_zone = self.active_sea_zone(prev_lat, prev_lon)
        vts_notice = self.build_vts_notice(pre_zones)
        if vts_notice:
            self.last_vts_notice = vts_notice

        base_mode = self.determine_mode(distance_to_port_before, draft_m=self.calculate_draft())
        command_speed_kn = self.choose_speed_for_mode(base_mode)
        current_snapshot = self.calculate_current_snapshot(prev_lat, prev_lon, current_leg_heading, pre_sea_zone)
        through_water_target_kn = max(command_speed_kn - current_snapshot["current_along_track_kn"], 0.0)
        safety_snapshot = self.navigation_safety_snapshot(
            depth_m=pre_bathymetry["depth"],
            distance_to_port_nm=distance_to_port_before,
            speed_kn=through_water_target_kn,
        )
        speed_loss_snapshot = self.environmental_speed_loss_kn(
            mode=safety_snapshot["mode"],
            target_speed_kn=safety_snapshot["speed_kn"],
            depth_m=pre_bathymetry["depth"],
            heading_deg=current_leg_heading,
            weather=pre_weather,
            lat=prev_lat,
            lon=prev_lon,
            zone_snapshot={"in_port_zone": any(zone.zone_type in {"port_limit", "pilot_area", "vts_gate", "port_gate"} for zone in pre_zones)},
        )
        through_water_speed_kn = self.apply_speed_response(
            speed_loss_snapshot["attainable_speed_kn"],
            safety_snapshot["mode"],
            max(speed_loss_snapshot["speed_loss_kn"] / max(safety_snapshot["speed_kn"], 1.0), 0.0),
        )
        actual_speed_kn = clamp(
            through_water_speed_kn + current_snapshot["current_along_track_kn"],
            0.0,
            self.sea_speed_max + 2.0,
        )
        zone_navigation = self.apply_zone_navigation_logic(command_speed_kn, actual_speed_kn, pre_weather, pre_zones)
        command_speed_kn = zone_navigation["command_speed_kn"]
        actual_speed_kn = zone_navigation["actual_speed_kn"]
        self.vessel_mode = safety_snapshot["mode"]

        travel_nm = actual_speed_kn * (SIMULATED_MINUTES_PER_LOOP / 60.0)

        while travel_nm > 0:
            leg_len = self.current_leg_length_nm()
            remaining_nm = max((1.0 - self.leg_progress) * leg_len, 0.0001)

            if travel_nm < remaining_nm:
                self.leg_progress += travel_nm / leg_len
                travel_nm = 0.0
            else:
                travel_nm -= remaining_nm
                self.leg_progress = 0.0
                self.leg_index += 1
                if self.leg_index >= len(self.route_coords) - 1:
                    self.leg_index = 0

                arrived_label = self.route_labels[self.leg_index]
                self.handle_port_arrival(arrived_label)

        lat, lon = self.current_position()
        jitter_lat, jitter_lon = self.get_position_jitter(self.vessel_mode)
        lat += jitter_lat
        lon += jitter_lon

        weather = fetch_weather(lat, lon, reference_time=self.sim_time)
        active_zones = self.active_port_zones(lat, lon)
        current_sea_zone = self.active_sea_zone(lat, lon)
        zone_navigation = self.apply_zone_navigation_logic(command_speed_kn, actual_speed_kn, weather, active_zones)
        command_speed_kn = zone_navigation["command_speed_kn"]
        actual_speed_kn = zone_navigation["actual_speed_kn"]

        distance_from_previous_nm = haversine_nm(prev_lat, prev_lon, lat, lon)
        cog = bearing_deg(prev_lat, prev_lon, lat, lon) if distance_from_previous_nm > 0 else current_leg_heading
        distance_to_next_port_nm = self.distance_to_next_port_nm()
        bathymetry = self.get_bathymetric_depth(lat, lon, distance_to_next_port_nm)
        safety_snapshot = self.navigation_safety_snapshot(
            depth_m=bathymetry["depth"],
            distance_to_port_nm=distance_to_next_port_nm,
            speed_kn=max(command_speed_kn - current_snapshot["current_along_track_kn"], 0.0),
        )
        current_snapshot = self.calculate_current_snapshot(lat, lon, cog, current_sea_zone)
        speed_loss_snapshot = self.environmental_speed_loss_kn(
            mode=safety_snapshot["mode"],
            target_speed_kn=safety_snapshot["speed_kn"],
            depth_m=bathymetry["depth"],
            heading_deg=cog,
            weather=weather,
            lat=lat,
            lon=lon,
            zone_snapshot=zone_navigation,
        )
        through_water_speed_kn = self.apply_speed_response(
            speed_loss_snapshot["attainable_speed_kn"],
            safety_snapshot["mode"],
            max(speed_loss_snapshot["speed_loss_kn"] / max(safety_snapshot["speed_kn"], 1.0), 0.0),
        )
        actual_speed_kn = clamp(
            through_water_speed_kn + current_snapshot["current_along_track_kn"],
            0.0,
            self.sea_speed_max + 2.0,
        )

        power_snapshot = self.calculate_power_snapshot(
            speed_kn=through_water_speed_kn,
            heading_deg=cog,
            depth_m=bathymetry["depth"],
            distance_to_port_nm=distance_to_next_port_nm,
            weather=weather,
            lat=lat,
            lon=lon,
            commanded_speed_kn=max(command_speed_kn - current_snapshot["current_along_track_kn"], 0.0),
            zone_snapshot=zone_navigation,
        )

        self.vessel_mode = power_snapshot["mode"]
        if self.vessel_mode == MODE_STOPPED:
            self.leg_index = prev_leg_index
            self.leg_progress = prev_leg_progress
            lat, lon = prev_lat, prev_lon
            command_speed_kn = 0.0
            actual_speed_kn = 0.0
            through_water_speed_kn = 0.0
            distance_from_previous_nm = 0.0
            distance_to_next_port_nm = distance_to_port_before
            cog = current_leg_heading
            weather = pre_weather
            bathymetry = pre_bathymetry
            active_zones = pre_zones
            active_zone_types = [zone.zone_type for zone in active_zones]
            current_sea_zone = pre_sea_zone
            zone_navigation = self.apply_zone_navigation_logic(0.0, 0.0, pre_weather, pre_zones)
            power_snapshot["raw_required_power_kw"] = 0.0
            power_snapshot["required_power_kw"] = 0.0
            power_snapshot["shaft_power_kw"] = 0.0
            power_snapshot["shaft_rpm"] = 0.0
            power_snapshot["shaft_torque_knm"] = 0.0
            power_snapshot["propeller_delivered_thrust_kw"] = 0.0
            power_snapshot["engine_load_ratio"] = 0.0
            power_snapshot["sfoc_g_per_kwh"] = 0.0
            power_snapshot["rpm"] = 0
            power_snapshot["target_load_ratio"] = 0.0
            power_snapshot["speed_error_kn"] = 0.0
            power_snapshot["speed_pid_trim"] = 0.0
            power_snapshot["sea_margin_factor"] = 0.0
            power_snapshot["controller_factor"] = 0.0
            power_snapshot["governor_error"] = 0.0
            power_snapshot["governor_integral"] = 0.0
            power_snapshot["governor_trim"] = 0.0
            power_snapshot["governor_target_power_kw"] = 0.0
            power_snapshot["main_engine_fuel_burn_rate"] = 0.0
            power_snapshot["me_co2_kg_hr"] = 0.0
            power_snapshot["me_ch4_kg_hr"] = 0.0
            power_snapshot["me_n2o_kg_hr"] = 0.0
            power_snapshot["me_nox_kg_hr"] = 0.0
            power_snapshot["me_sox_kg_hr"] = 0.0
            power_snapshot["co2_value"] = round(power_snapshot["ae_co2_kg_hr"], 3)
            power_snapshot["ch4_value"] = round(power_snapshot["ae_ch4_kg_hr"], 4)
            power_snapshot["n2o_value"] = round(power_snapshot["ae_n2o_kg_hr"], 5)
            power_snapshot["nox_value_kg_h"] = round(power_snapshot["ae_nox_kg_hr"], 4)
            power_snapshot["sox_value_kg_h"] = round(power_snapshot["ae_sox_kg_hr"], 5)
            power_snapshot["fuel_burn_rate"] = round(power_snapshot["aux_engine_fuel_burn_rate"], 3)
        else:
            active_zone_types = [zone.zone_type for zone in active_zones]

        generated_time = isoformat_z(self.runtime_event_time(self.sim_time))
        timestamp_utc = isoformat_z(self.sim_time)
        step_hours = SIMULATED_MINUTES_PER_LOOP / 60.0
        co2_mass_step_kg = round(power_snapshot["co2_value"] * step_hours, 4)
        fuel_burn_step_kg = round(power_snapshot["fuel_burn_rate"] * step_hours, 4)
        energy_use_mj = round(fuel_burn_step_kg * self.fuel_lhv_mj_per_kg, 4)
        transport_work_tonne_nm = round(self.cargo_quantity * distance_from_previous_nm, 4)
        imo_eeoi_gco2_per_tonne_nm = (
            round((co2_mass_step_kg * 1000.0) / transport_work_tonne_nm, 4)
            if transport_work_tonne_nm > 0
            else None
        )
        eu_ttw_co2_g_per_mj = (
            round((co2_mass_step_kg * 1000.0) / energy_use_mj, 4)
            if energy_use_mj > 0
            else None
        )
        eca_compliant = not any(zone.zone_type == "port_limit" for zone in active_zones) or self.fuel_type == DEFAULT_FUEL_TYPE or self.scrubber_active
        active_zone_names = [zone.name for zone in active_zones]
        measurement = lookup_sensor_measurement(timestamp_utc, self.imo_number, self.vessel_type)
        assimilation_snapshot = self.sensor_assimilation_state.apply(
            measured_co2=measurement.get("measured_co2_kg_h"),
            measured_ch4=measurement.get("measured_ch4_kg_h"),
            measured_n2o=measurement.get("measured_n2o_kg_h"),
            measured_fuel=measurement.get("measured_fuel_kg_h"),
            predicted_co2=power_snapshot["co2_value"],
            predicted_ch4=power_snapshot["ch4_value"],
            predicted_n2o=power_snapshot["n2o_value"],
            predicted_fuel=power_snapshot["fuel_burn_rate"],
        )
        final_co2_value = assimilation_snapshot["corrected_co2_value"]
        final_ch4_value = assimilation_snapshot["corrected_ch4_value"]
        final_n2o_value = assimilation_snapshot["corrected_n2o_value"]
        final_fuel_burn_rate = assimilation_snapshot["corrected_fuel_burn_rate"]
        co2_mass_step_kg = round(final_co2_value * step_hours, 4)
        fuel_burn_step_kg = round(final_fuel_burn_rate * step_hours, 4)
        energy_use_mj = round(fuel_burn_step_kg * self.fuel_lhv_mj_per_kg, 4)
        reference_snapshot = calculate_reference_comparison(
            vessel_type=self.vessel_type,
            co2_mass_step_kg=co2_mass_step_kg,
            distance_nm=distance_from_previous_nm,
        )
        uncertainty_snapshot = calculate_uncertainty_score(
            {
                "bathymetry_source": bathymetry["source"],
                "weather_source": weather["weather_source"],
                "model_mode": power_snapshot["model_mode"],
                "sensor_assimilation_active": assimilation_snapshot["sensor_assimilation_active"],
                "geometry_defaults_used": bool(self.geometry_defaults_used),
                "shallow_water_flag": power_snapshot["shallow_water_flag"],
                "fouling_multiplier": power_snapshot["fouling_multiplier"],
                "vessel_mode": self.vessel_mode,
            }
        )
        validation_status = confidence_to_validation_status(
            uncertainty_snapshot["confidence_score"],
            assimilation_snapshot["sensor_assimilation_active"],
        )

        return {
            "packet_uuid": self.seeded_uuid("packet", self.seq, timestamp_utc),
            "generated_at": generated_time,
            "gateway_received_at": generated_time,
            "cloud_received_at": generated_time,
            "seq": self.seq,
            "timestamp_utc": timestamp_utc,
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "co2_value": final_co2_value,
            "ch4_value": final_ch4_value,
            "n2o_value": final_n2o_value,
            "nox_value_kg_h": power_snapshot["nox_value_kg_h"],
            "sox_value_kg_h": power_snapshot["sox_value_kg_h"],
            "rpm": power_snapshot["rpm"],
            "cargo_quantity": round(self.cargo_quantity, 2),
            "draft": power_snapshot["draft"],
            "speed_over_ground": round(actual_speed_kn, 2),
            "speed_command_kn": round(command_speed_kn, 2),
            "course_over_ground": round(cog, 2),
            "distance_from_previous_nm": round(distance_from_previous_nm, 3),
            "distance_to_next_port_nm": round(distance_to_next_port_nm, 2),
            "route_leg_from": prev_from_label,
            "route_leg_to": prev_to_label,
            "vessel_mode": self.vessel_mode,
            "vessel_type": self.vessel_type,
            "vessel_name": self.name,
            "mmsi": self.mmsi,
            "imo_number": self.imo_number,
            "gross_tonnage": round(self.gross_tonnage, 1),
            "deadweight_tonnes": round(self.deadweight_tonnes, 1),
            "fuel_type": self.fuel_type,
            "node_id": self.node_id,
            "depth": power_snapshot["depth"],
            "ukc": power_snapshot["ukc"],
            "squat": power_snapshot["squat"],
            "effective_draft": power_snapshot["effective_draft"],
            "bathymetry_source": bathymetry["source"],
            "required_power_kw": power_snapshot["required_power_kw"],
            "fuel_burn_rate": final_fuel_burn_rate,
            "co2_mass_step_kg": co2_mass_step_kg,
            "fuel_burn_step_kg": fuel_burn_step_kg,
            "energy_use_mj": energy_use_mj,
            "transport_work_tonne_nm": transport_work_tonne_nm,
            "imo_eeoi_gco2_per_tonne_nm": imo_eeoi_gco2_per_tonne_nm,
            "eu_ttw_co2_g_per_mj": eu_ttw_co2_g_per_mj,
            "engine_load_ratio": power_snapshot["engine_load_ratio"],
            "shallow_water_flag": power_snapshot["shallow_water_flag"],
            "relative_wind_angle": power_snapshot["relative_wind_angle"],
            "sfoc_g_per_kwh": power_snapshot["sfoc_g_per_kwh"],
            "weather_sea_force_state": power_snapshot["weather_sea_force_state"],
            "weather_sea_force_pct": power_snapshot["weather_sea_force_pct"],
            "weather_sea_force_index": power_snapshot["weather_sea_force_index"],
            "efficiency_state": power_snapshot["efficiency_state"],
            "efficiency_reason_summary": power_snapshot["efficiency_reason_summary"],
            "dominant_emission_driver": power_snapshot["dominant_emission_driver"],
            "dominant_emission_driver_kw": power_snapshot["dominant_emission_driver_kw"],
            "secondary_emission_driver": power_snapshot["secondary_emission_driver"],
            "secondary_emission_driver_kw": power_snapshot["secondary_emission_driver_kw"],
            "weather_penalty_pct": power_snapshot["weather_penalty_pct"],
            "sea_penalty_pct": power_snapshot["sea_penalty_pct"],
            "cargo_penalty_pct": power_snapshot["cargo_penalty_pct"],
            "draft_penalty_pct": power_snapshot["draft_penalty_pct"],
            "water_depth_penalty_pct": power_snapshot["water_depth_penalty_pct"],
            "fouling_penalty_pct": power_snapshot["fouling_penalty_pct"],
            "fouling_cycle_day": power_snapshot["fouling_cycle_day"],
            "fouling_stage": power_snapshot["fouling_stage"],
            "fouling_multiplier": power_snapshot["fouling_multiplier"],
            "days_since_hull_cleaning": power_snapshot["days_since_hull_cleaning"],
            "hull_condition_label": power_snapshot["hull_condition_label"],
            "weather_wind_speed": weather["weather_wind_speed"],
            "weather_wind_direction": weather["weather_wind_direction"],
            "weather_wave_height": weather["weather_wave_height"],
            "weather_air_temp": weather["weather_air_temp"],
            "weather_sea_temp": weather["weather_sea_temp"],
            "weather_pressure": weather["weather_pressure"],
            "weather_source": weather["weather_source"],
            "weather_timestamp": weather["weather_timestamp"],
            "weather_is_forecast": weather["weather_is_forecast"],
            "weather_fallback_mode": weather["weather_fallback_mode"],
            "model_mode": power_snapshot["model_mode"],
            "validation_status": validation_status,
            "co2_kg_per_nm": reference_snapshot["co2_kg_per_nm"],
            "mrv_reference_kg_co2_per_nm": reference_snapshot["mrv_reference_kg_co2_per_nm"],
            "mrv_reference_deviation_pct": reference_snapshot["mrv_reference_deviation_pct"],
            "mrv_reference_category": reference_snapshot["mrv_reference_category"],
            "calibration_status": reference_snapshot["calibration_status"],
            "uncertainty_pct": uncertainty_snapshot["uncertainty_pct"],
            "confidence_score": uncertainty_snapshot["confidence_score"],
            "uncertainty_reasons": uncertainty_snapshot["uncertainty_reasons"],
            "sensor_calibration_available": assimilation_snapshot["sensor_calibration_available"],
            "sensor_assimilation_active": assimilation_snapshot["sensor_assimilation_active"],
            "measured_co2_kg_h": assimilation_snapshot["measured_co2_kg_h"],
            "measured_ch4_kg_h": assimilation_snapshot["measured_ch4_kg_h"],
            "measured_n2o_kg_h": assimilation_snapshot["measured_n2o_kg_h"],
            "measured_fuel_kg_h": assimilation_snapshot["measured_fuel_kg_h"],
            "predicted_co2_kg_h": assimilation_snapshot["predicted_co2_kg_h"],
            "predicted_ch4_kg_h": assimilation_snapshot["predicted_ch4_kg_h"],
            "predicted_n2o_kg_h": assimilation_snapshot["predicted_n2o_kg_h"],
            "predicted_fuel_kg_h": assimilation_snapshot["predicted_fuel_kg_h"],
            "model_co2_value": assimilation_snapshot["model_co2_value"],
            "corrected_co2_value": assimilation_snapshot["corrected_co2_value"],
            "co2_model_residual_pct": assimilation_snapshot["co2_model_residual_pct"],
            "ch4_model_residual_pct": assimilation_snapshot["ch4_model_residual_pct"],
            "n2o_model_residual_pct": assimilation_snapshot["n2o_model_residual_pct"],
            "fuel_model_residual_pct": assimilation_snapshot["fuel_model_residual_pct"],
            "ewma_correction_factor": assimilation_snapshot["ewma_correction_factor"],
            "sensor_assimilation_status": assimilation_snapshot["sensor_assimilation_status"],
            "quality_flags": {
                "active_port_zones": active_zone_names,
                "active_zone_types": active_zone_types,
                "active_sea_zone": current_snapshot["sea_zone_name"],
                "in_port_zone": zone_navigation["in_port_zone"],
                "in_anchorage": zone_navigation["in_anchorage"],
                "anchor_locked": self.anchor_locked,
                "drag_anchor": zone_navigation["drag_anchor"],
                "vts_notice": self.last_vts_notice if active_zones else None,
                "eca_compliant": eca_compliant,
                "scrubber_active": self.scrubber_active,
                "methane_zone_multiplier": power_snapshot["methane_zone_multiplier"],
                "methane_load_band_multiplier": power_snapshot["methane_load_band_multiplier"],
                "n2o_load_band_multiplier": power_snapshot["n2o_load_band_multiplier"],
                "nox_g_per_kwh": power_snapshot["nox_g_per_kwh"],
                "nox_value_kg_h": power_snapshot["nox_value_kg_h"],
                "sox_g_per_kwh": power_snapshot["sox_g_per_kwh"],
                "sox_value_kg_h": power_snapshot["sox_value_kg_h"],
                "wave_period_s": power_snapshot["wave_period_s"],
                "current_speed_kn": power_snapshot["current_speed_kn"],
                "current_direction_deg": power_snapshot["current_direction_deg"],
                "current_along_track_kn": power_snapshot["current_along_track_kn"],
                "current_cross_track_kn": power_snapshot["current_cross_track_kn"],
                "speed_loss_kn": speed_loss_snapshot["speed_loss_kn"],
                "speed_loss_reason": speed_loss_snapshot["speed_loss_reason"],
                "generator_count": power_snapshot["generator_count"],
                "generator_load_ratio": power_snapshot["generator_load_ratio"],
                "auxiliary_load_kw": power_snapshot["auxiliary_load_kw"],
                "speed_error_kn": power_snapshot["speed_error_kn"],
                "speed_pid_trim": power_snapshot["speed_pid_trim"],
                "sea_margin_factor": power_snapshot["sea_margin_factor"],
                "controller_factor": power_snapshot["controller_factor"],
                "target_load_ratio": power_snapshot["target_load_ratio"],
                "governor_error": power_snapshot["governor_error"],
                "governor_integral": power_snapshot["governor_integral"],
                "governor_trim": power_snapshot["governor_trim"],
                "governor_target_power_kw": power_snapshot["governor_target_power_kw"],
                "shaft_power_kw": power_snapshot["shaft_power_kw"],
                "shaft_rpm": power_snapshot["shaft_rpm"],
                "shaft_torque_knm": power_snapshot["shaft_torque_knm"],
                "shaft_line_efficiency": power_snapshot["shaft_line_efficiency"],
                "propeller_slip_ratio": power_snapshot["propeller_slip_ratio"],
                "propeller_open_water_efficiency": power_snapshot["propeller_open_water_efficiency"],
                "propeller_delivered_thrust_kw": power_snapshot["propeller_delivered_thrust_kw"],
                "propeller_fouling_multiplier": power_snapshot["propeller_fouling_multiplier"],
                "propeller_condition_label": power_snapshot["propeller_condition_label"],
                "turbocharger_state": power_snapshot["turbocharger_state"],
                "combustion_quality_state": power_snapshot["combustion_quality_state"],
                "sfoc_transient_multiplier": power_snapshot["sfoc_transient_multiplier"],
                "nox_transient_multiplier": power_snapshot["nox_transient_multiplier"],
                "methane_transient_multiplier": power_snapshot["methane_transient_multiplier"],
                "n2o_transient_multiplier": power_snapshot["n2o_transient_multiplier"],
                "engine_thermal_state": power_snapshot["engine_thermal_state"],
                "minutes_since_engine_restart": power_snapshot["minutes_since_engine_restart"],
                "warmup_sfoc_multiplier": power_snapshot["warmup_sfoc_multiplier"],
                "warmup_methane_multiplier": power_snapshot["warmup_methane_multiplier"],
                "days_since_engine_maintenance": power_snapshot["days_since_engine_maintenance"],
                "engine_condition_factor": power_snapshot["engine_condition_factor"],
                "scr_active": power_snapshot["scr_active"],
                "scr_efficiency": power_snapshot["scr_efficiency"],
                "scr_n2o_multiplier": power_snapshot["scr_n2o_multiplier"],
                "main_engine_fuel_burn_rate": power_snapshot["main_engine_fuel_burn_rate"],
                "aux_engine_fuel_burn_rate": power_snapshot["aux_engine_fuel_burn_rate"],
                "ae_gensets_online": power_snapshot["ae_gensets_online"],
                "ae_load_fraction_pct": power_snapshot["ae_load_fraction_pct"],
                "me_co2_kg_hr": power_snapshot["me_co2_kg_hr"],
                "ae_co2_kg_hr": power_snapshot["ae_co2_kg_hr"],
                "black_smoke_proxy": power_snapshot["black_smoke_proxy"],
                "model_diagnostics": {
                    "model_mode": power_snapshot["model_mode"],
                    "speed_ms": power_snapshot["speed_ms"],
                    "reynolds_number": power_snapshot["reynolds_number"],
                    "friction_coefficient": power_snapshot["friction_coefficient"],
                    "friction_resistance_kn": power_snapshot["friction_resistance_kn"],
                    "residual_resistance_kn": power_snapshot["residual_resistance_kn"],
                    "air_resistance_kn": power_snapshot["air_resistance_kn"],
                    "shallow_water_multiplier": power_snapshot["shallow_water_multiplier"],
                    "fouling_multiplier": power_snapshot["fouling_multiplier"],
                    "propulsive_efficiency": power_snapshot["propulsive_efficiency"],
                    "raw_power_kw": power_snapshot["raw_power_kw"],
                    "clamped_power_kw": power_snapshot["clamped_power_kw"],
                },
                "geometry_defaults_used": list(self.geometry_defaults_used),
            },
        }

    def make_batch(self) -> Dict:
        items = [self.advance_one_step() for _ in range(POINTS_PER_BATCH)]
        audit_time = isoformat_z(self.runtime_event_time(self.sim_time))
        batch_id = f"batch-{self.seeded_uuid('batch', self.seq, len(items))}"
        if ENABLE_DEMO_MERKLE:
            merkle_root = compute_merkle(items)
        else:
            merkle_root = f"demo-root-{self.seeded_uuid('demo-root', self.seq).replace('-', '')[:12]}"
        return {
            "batch_id": batch_id,
            "gateway_uid": self.gateway_uid,
            "audit_timestamp": audit_time,
            "merkle_root": merkle_root,
            "items": items,
        }


@dataclass
class ContainerVessel(VesselState):
    vessel_type: str = "ContainerVessel"
    fuel_type: str = "MGO_PROXY"
    fuel_lhv_mj_per_kg: float = 42.7
    gross_tonnage: float = 52000.0
    deadweight_tonnes: float = 62000.0
    admiralty_coefficient: float = 550.0
    block_coefficient: float = 0.67
    lightship_tonnes: float = 24000.0
    ballast_water_tonnes: float = 9000.0
    installed_power_kw: float = 46000.0
    hotel_load_kw: float = 1800.0
    sfoc_steaming_g_per_kwh: float = 171.0
    sfoc_manoeuvring_g_per_kwh: float = 188.0
    has_scr: bool = True
    scr_design_nox_reduction: float = 0.82
    scr_n2o_penalty_factor: float = 1.10
    aux_installed_power_kw: float = 4000.0
    aux_genset_count: int = 4
    aux_base_sfoc_g_per_kwh: float = 205.0
    methane_slip_steaming_factor: float = 0.00005
    methane_slip_manoeuvring_factor: float = 0.000085
    n2o_factor: float = 0.00018
    manoeuvring_efficiency_penalty: float = 1.10
    ballast_efficiency_modifier: float = 0.98
    loaded_efficiency_modifier: float = 1.05
    sea_speed_min: float = 18.0
    sea_speed_max: float = 22.0
    man_speed_min: float = 4.0
    man_speed_max: float = 8.0
    rpm_range_steaming: Tuple[int, int] = (68, 98)
    rpm_range_manoeuvring_half: Tuple[int, int] = (36, 54)
    rpm_range_manoeuvring_quarter: Tuple[int, int] = (18, 32)
    engine_make: str = "MAN B&W"
    engine_model: str = "12S90ME-C10.5"
    engine_curve_mcr_kw: float = 65200.0
    engine_curve_points: Tuple[Tuple[float, float, float], ...] = (
        (0.25, 179.0, 557.4),
        (0.50, 167.5, 521.5),
        (0.75, 163.0, 507.5),
        (0.85, 163.5, 509.1),
        (1.00, 167.0, 520.0),
    )


@dataclass
class BulkerVessel(VesselState):
    vessel_type: str = "BulkerVessel"
    fuel_type: str = "MGO_PROXY"
    fuel_lhv_mj_per_kg: float = 42.7
    gross_tonnage: float = 32000.0
    deadweight_tonnes: float = 38000.0
    admiralty_coefficient: float = 400.0
    block_coefficient: float = 0.80
    lightship_tonnes: float = 18000.0
    ballast_water_tonnes: float = 6500.0
    installed_power_kw: float = 16000.0
    hotel_load_kw: float = 950.0
    sfoc_steaming_g_per_kwh: float = 177.0
    sfoc_manoeuvring_g_per_kwh: float = 194.0
    has_scr: bool = False
    scr_design_nox_reduction: float = 0.0
    scr_n2o_penalty_factor: float = 1.0
    aux_installed_power_kw: float = 1800.0
    aux_genset_count: int = 3
    aux_base_sfoc_g_per_kwh: float = 212.0
    methane_slip_steaming_factor: float = 0.00005
    methane_slip_manoeuvring_factor: float = 0.00009
    n2o_factor: float = 0.00018
    manoeuvring_efficiency_penalty: float = 1.12
    ballast_efficiency_modifier: float = 0.97
    loaded_efficiency_modifier: float = 1.06
    sea_speed_min: float = 12.0
    sea_speed_max: float = 14.0
    man_speed_min: float = 4.0
    man_speed_max: float = 7.0
    rpm_range_steaming: Tuple[int, int] = (58, 88)
    rpm_range_manoeuvring_half: Tuple[int, int] = (30, 46)
    rpm_range_manoeuvring_quarter: Tuple[int, int] = (16, 28)
    engine_make: str = "WinGD"
    engine_model: str = "11X92-B"
    engine_curve_mcr_kw: float = 58520.0
    engine_curve_points: Tuple[Tuple[float, float, float], ...] = (
        (0.25, 177.0, 551.1),
        (0.50, 166.0, 516.9),
        (0.75, 162.0, 504.4),
        (0.85, 162.5, 506.0),
        (1.00, 166.5, 518.4),
    )


@dataclass
class TankerVessel(VesselState):
    vessel_type: str = "TankerVessel"
    fuel_type: str = "MGO_PROXY"
    fuel_lhv_mj_per_kg: float = 42.7
    gross_tonnage: float = 43000.0
    deadweight_tonnes: float = 52000.0
    admiralty_coefficient: float = 420.0
    block_coefficient: float = 0.83
    lightship_tonnes: float = 22000.0
    ballast_water_tonnes: float = 8000.0
    installed_power_kw: float = 18000.0
    hotel_load_kw: float = 1100.0
    sfoc_steaming_g_per_kwh: float = 176.0
    sfoc_manoeuvring_g_per_kwh: float = 193.0
    has_scr: bool = True
    scr_design_nox_reduction: float = 0.78
    scr_n2o_penalty_factor: float = 1.08
    aux_installed_power_kw: float = 2400.0
    aux_genset_count: int = 3
    aux_base_sfoc_g_per_kwh: float = 209.0
    methane_slip_steaming_factor: float = 0.00005
    methane_slip_manoeuvring_factor: float = 0.00009
    n2o_factor: float = 0.00018
    manoeuvring_efficiency_penalty: float = 1.14
    ballast_efficiency_modifier: float = 0.98
    loaded_efficiency_modifier: float = 1.05
    sea_speed_min: float = 12.0
    sea_speed_max: float = 14.0
    man_speed_min: float = 4.0
    man_speed_max: float = 7.0
    rpm_range_steaming: Tuple[int, int] = (56, 86)
    rpm_range_manoeuvring_half: Tuple[int, int] = (30, 45)
    rpm_range_manoeuvring_quarter: Tuple[int, int] = (16, 27)
    engine_make: str = "MAN B&W"
    engine_model: str = "11G95ME-C10.5"
    engine_curve_mcr_kw: float = 60170.0
    engine_curve_points: Tuple[Tuple[float, float, float], ...] = (
        (0.25, 176.0, 548.0),
        (0.50, 164.5, 512.2),
        (0.75, 160.5, 499.8),
        (0.85, 161.0, 501.3),
        (1.00, 165.0, 513.8),
    )


@dataclass
class LNGCarrierVessel(VesselState):
    vessel_type: str = "LNGCarrier"
    fuel_type: str = "LNG_DF"
    fuel_lhv_mj_per_kg: float = 49.5
    gross_tonnage: float = 92000.0
    deadweight_tonnes: float = 76000.0
    admiralty_coefficient: float = 575.0
    block_coefficient: float = 0.78
    lightship_tonnes: float = 29000.0
    ballast_water_tonnes: float = 10000.0
    installed_power_kw: float = 32000.0
    hotel_load_kw: float = 1500.0
    sfoc_steaming_g_per_kwh: float = 155.0
    sfoc_manoeuvring_g_per_kwh: float = 168.0
    has_scr: bool = True
    scr_design_nox_reduction: float = 0.86
    scr_n2o_penalty_factor: float = 1.15
    aux_installed_power_kw: float = 3000.0
    aux_genset_count: int = 4
    aux_base_sfoc_g_per_kwh: float = 198.0
    methane_slip_steaming_factor: float = 0.0
    methane_slip_manoeuvring_factor: float = 0.0
    n2o_factor: float = 0.00013
    manoeuvring_efficiency_penalty: float = 1.09
    ballast_efficiency_modifier: float = 0.97
    loaded_efficiency_modifier: float = 1.04
    sea_speed_min: float = 14.5
    sea_speed_max: float = 18.0
    man_speed_min: float = 4.5
    man_speed_max: float = 8.5
    rpm_range_steaming: Tuple[int, int] = (62, 90)
    rpm_range_manoeuvring_half: Tuple[int, int] = (34, 50)
    rpm_range_manoeuvring_quarter: Tuple[int, int] = (18, 30)
    engine_make: str = "WinGD"
    engine_model: str = "11X92-DF 2.0"
    engine_curve_mcr_kw: float = 58520.0
    engine_curve_points: Tuple[Tuple[float, float, float], ...] = (
        (0.25, 153.4, 466.8),
        (0.50, 137.3, 418.4),
        (0.75, 130.9, 398.8),
        (0.85, 130.4, 397.0),
        (1.00, 135.3, 412.3),
    )


ROUTE_1_AB = [
    ("Lulea berth / departure", (dm(65, 34.11), dm(22, 14.15))),
    ("Lulea channel smoothing point", (dm(65, 30.20), dm(22, 18.40))),
    ("Sandoleden WOP", (dm(65, 28.52), dm(22, 21.35))),
    ("Lulea Pilot", (dm(65, 19.82), dm(22, 45.30))),
    ("Bothnian Mid", (dm(65, 5.00), dm(23, 40.00))),
    ("Oulu VTS Gate", (dm(64, 57.05), dm(24, 15.00))),
    ("Oulu Pilot", (dm(65, 2.15), dm(24, 33.60))),
    ("Oulu fairway node", (dm(65, 1.40), dm(24, 50.00))),
    ("Oulu berth / arrival", (dm(65, 0.25), dm(25, 7.35))),
]

ROUTE_1_BC = [
    ("Oulu berth / departure", (dm(65, 0.25), dm(25, 7.35))),
    ("Oulu fairway node", (dm(65, 1.40), dm(24, 50.00))),
    ("Oulu Pilot", (dm(65, 2.15), dm(24, 33.60))),
    ("Oulu VTS Gate", (dm(64, 57.05), dm(24, 15.00))),
    ("Bothnian Mid southbound", (64.75, 23.45)),
    ("Mid Quark transit", (dm(64, 5.00), dm(22, 40.00))),
    ("Skelleftea Pilot", (dm(64, 35.50), dm(21, 30.00))),
    ("Skelleftea fairway node", (dm(64, 40.20), dm(21, 17.50))),
    ("Gasoren WOP", (dm(64, 39.80), dm(21, 19.10))),
    ("Skelleftea berth / arrival", (dm(64, 41.10), dm(21, 15.50))),
]

ROUTE_2_AB = [
    ("Stockholm Vartahamnen berth / departure", (dm(59, 21.10), dm(18, 6.50))),
    ("Tralhavet WOP", (dm(59, 26.30), dm(18, 23.50))),
    ("Sandhamn Pilot", (dm(59, 17.30), dm(18, 55.40))),
    ("Tallinn VTS entry", (dm(59, 35.00), dm(24, 30.00))),
    ("Tallinn Pilot", (dm(59, 31.00), dm(24, 45.50))),
    ("Tallinn Old Port berth / arrival", (dm(59, 26.80), dm(24, 46.50))),
]

ROUTE_2_BC = [
    ("Tallinn Old Port berth / departure", (dm(59, 26.80), dm(24, 46.50))),
    ("Tallinn Light", (dm(59, 42.70), dm(24, 43.90))),
    ("GOFREP reporting point", (dm(59, 54.00), dm(24, 50.00))),
    ("Eastern Gulf transit", (60.02, 25.65)),
    ("Orrengrund Pilot", (dm(60, 16.50), dm(26, 26.50))),
    ("Kotka Mussalo berth / arrival", (dm(60, 26.40), dm(26, 54.30))),
]

ROUTE_3_AB = [
    ("Riga berth / departure", (dm(57, 3.50), dm(24, 1.20))),
    ("Reception Buoy B", (dm(57, 6.50), dm(23, 53.00))),
    ("Kolkasrags", (dm(57, 49.00), dm(22, 40.00))),
    ("Almagrundet", (dm(59, 9.30), dm(19, 7.50))),
    ("Sandhamn Pilot", (dm(59, 17.30), dm(18, 55.40))),
    ("Stockholm Vartahamnen berth / arrival", (dm(59, 21.10), dm(18, 6.50))),
]

ROUTE_3_BC = [
    ("Stockholm Vartahamnen berth / departure", (dm(59, 21.10), dm(18, 6.50))),
    ("Soderarm fairway cleanup", (dm(59, 45.10), dm(19, 24.40))),
    ("Sandhamn Pilot", (dm(59, 17.30), dm(18, 55.40))),
    ("Central Baltic transit", (57.85, 19.85)),
    ("Hel Peninsula", (dm(54, 36.00), dm(19, 0.00))),
    ("Gdansk Pilot", (dm(54, 27.50), dm(18, 42.10))),
    ("Gdansk DCT berth / arrival", (dm(54, 24.10), dm(18, 43.20))),
]

ROUTE_4_AB = [
    ("Stockholm Vartahamnen berth / departure", (dm(59, 21.10), dm(18, 6.50))),
    ("Tralhavet WOP", (dm(59, 26.30), dm(18, 23.50))),
    ("Sandhamn Pilot", (dm(59, 17.30), dm(18, 55.40))),
    ("Tallinn VTS entry", (dm(59, 35.00), dm(24, 30.00))),
    ("Tallinn Pilot", (dm(59, 31.00), dm(24, 45.50))),
    ("Tallinn Old Port berth / arrival", (dm(59, 26.80), dm(24, 46.50))),
]

ROUTE_4_BC = [
    ("Tallinn Old Port berth / departure", (dm(59, 26.80), dm(24, 46.50))),
    ("Tallinn Light", (dm(59, 42.70), dm(24, 43.90))),
    ("Helsinki TSS South", (dm(59, 54.00), dm(24, 50.00))),
    ("Harmaja Pilot Gate", (dm(60, 6.30), dm(24, 58.50))),
    ("Helsinki Port berth / arrival", (dm(60, 9.50), dm(24, 57.80))),
]

SHIP_1_LABELS, SHIP_1_WAYPOINTS = build_named_route(
    ROUTE_1_AB,
    ROUTE_1_BC,
    reverse_named_leg(ROUTE_1_BC),
    reverse_named_leg(ROUTE_1_AB),
)

SHIP_2_LABELS, SHIP_2_WAYPOINTS = build_named_route(
    ROUTE_2_AB,
    ROUTE_2_BC,
    reverse_named_leg(ROUTE_2_BC),
    reverse_named_leg(ROUTE_2_AB),
)

SHIP_3_LABELS, SHIP_3_WAYPOINTS = build_named_route(
    ROUTE_3_AB,
    ROUTE_3_BC,
    reverse_named_leg(ROUTE_3_BC),
    reverse_named_leg(ROUTE_3_AB),
)

SHIP_4_LABELS, SHIP_4_WAYPOINTS = build_named_route(
    ROUTE_4_AB,
    ROUTE_4_BC,
    reverse_named_leg(ROUTE_4_BC),
    reverse_named_leg(ROUTE_4_AB),
)


VESSELS = [
    ContainerVessel(
        name="Container Vessel 1",
        gateway_uid="GW-BALTIC-0001",
        gateway_key=DEFAULT_GATEWAY_KEY,
        imo_number="9387421",
        mmsi="230123000",
        node_id="NODE-BALTIC-0001",
        route_labels=SHIP_1_LABELS,
        route_coords=SHIP_1_WAYPOINTS,
        seq=SEQ_BASE + 100000,
        cargo_max=32000.0,
        ballast_draft=5.4,
        draft_factor=0.00012,
        port_1_label="Lulea berth / departure",
        port_2_label="Oulu berth / arrival",
        port_3_label="Skelleftea berth / arrival",
        fouling_offset_days=0.0,
    ),
    BulkerVessel(
        name="Bulker Vessel 1",
        gateway_uid="GW-NORDIC-0002",
        gateway_key=DEFAULT_GATEWAY_KEY,
        imo_number="9450012",
        mmsi="230456000",
        node_id="NODE-NORDIC-0002",
        route_labels=SHIP_2_LABELS,
        route_coords=SHIP_2_WAYPOINTS,
        seq=SEQ_BASE + 200000,
        cargo_max=18000.0,
        ballast_draft=4.9,
        draft_factor=0.00016,
        port_1_label="Stockholm Vartahamnen berth / departure",
        port_2_label="Tallinn Old Port berth / arrival",
        port_3_label="Kotka Mussalo berth / arrival",
        fouling_offset_days=60.0,
    ),
    TankerVessel(
        name="Tanker Vessel 1",
        gateway_uid="GW-ARCTIC-0003",
        gateway_key=DEFAULT_GATEWAY_KEY,
        imo_number="9527788",
        mmsi="257789000",
        node_id="NODE-ARCTIC-0003",
        route_labels=SHIP_3_LABELS,
        route_coords=SHIP_3_WAYPOINTS,
        seq=SEQ_BASE + 300000,
        cargo_max=22000.0,
        ballast_draft=5.1,
        draft_factor=0.00014,
        port_1_label="Riga berth / departure",
        port_2_label="Stockholm Vartahamnen berth / arrival",
        port_3_label="Gdansk DCT berth / arrival",
        fouling_offset_days=30.0,
    ),
]

if ENABLE_LNG_CARRIER:
    VESSELS.append(
        LNGCarrierVessel(
            name="LNG Carrier 1",
            gateway_uid="GW-LNG-0004",
            gateway_key=DEFAULT_GATEWAY_KEY,
            imo_number="9786012",
            mmsi="257995000",
            node_id="NODE-LNG-0004",
            route_labels=SHIP_4_LABELS,
            route_coords=SHIP_4_WAYPOINTS,
            seq=SEQ_BASE + 400000,
            cargo_max=145000.0,
            ballast_draft=7.8,
            draft_factor=0.000045,
            port_1_label="Stockholm Vartahamnen berth / departure",
            port_2_label="Tallinn Old Port berth / arrival",
            port_3_label="Helsinki Port berth / arrival",
            fouling_offset_days=15.0,
        )
    )


def sync_vessel_identity_from_supabase(vessels: List[VesselState]) -> None:
    if SIMULATOR_OFFLINE_MODE:
        print("Offline mode: vessel identity sync skipped")
        return

    if not SUPABASE_REST_URL or not SUPABASE_ANON_KEY:
        print("Supabase vessel identity sync skipped: missing REST URL or anon key")
        return

    for vessel in vessels:
        record = fetch_vessel_record_by_imo(vessel.imo_number)
        if not record:
            continue

        vessel_name = record.get("name")
        if vessel_name:
            vessel.name = vessel_name


def write_dry_run_payload(payload: Dict) -> None:
    if not SIMULATOR_DRY_RUN_OUTPUT:
        return

    output_path = Path(SIMULATOR_DRY_RUN_OUTPUT)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload) + "\n")


def vessel_for_validation_row(row: Dict[str, str]) -> VesselState:
    imo_number = csv_value(row, "imo_number")
    vessel_type = csv_value(row, "vessel_type")
    for vessel in VESSELS:
        if imo_number and vessel.imo_number == imo_number:
            return vessel
    for vessel in VESSELS:
        if vessel_type and vessel.vessel_type.lower() == vessel_type.lower():
            return vessel
    return VESSELS[0]


def run_validation(csv_path: str) -> dict:
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"Validation CSV not found: {csv_path}")

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)

    if not rows:
        raise ValueError("Validation CSV is empty.")

    required_any = [
        ("timestamp_utc",),
        ("speed_over_ground",),
        ("draft",),
        ("fuel_burn_rate_kg_h", "fuel_burn_t_day"),
        ("co2_kg_h", "co2_t_day"),
    ]
    missing = []
    for aliases in required_any:
        if not any(csv_value(rows[0], alias) is not None for alias in aliases):
            missing.append("/".join(aliases))
    if missing:
        raise ValueError(f"Validation CSV is missing required columns: {', '.join(missing)}")

    fuel_actual: List[float] = []
    fuel_predicted: List[float] = []
    co2_actual: List[float] = []
    co2_predicted: List[float] = []

    for row in rows:
        vessel = vessel_for_validation_row(row)
        prediction = vessel.build_validation_prediction(row)

        measured_fuel = csv_float(row, "fuel_burn_rate_kg_h")
        if measured_fuel is None:
            fuel_t_day = csv_float(row, "fuel_burn_t_day")
            measured_fuel = (fuel_t_day * 1000.0 / 24.0) if fuel_t_day is not None else None

        measured_co2 = csv_float(row, "co2_kg_h")
        if measured_co2 is None:
            co2_t_day = csv_float(row, "co2_t_day")
            measured_co2 = (co2_t_day * 1000.0 / 24.0) if co2_t_day is not None else None

        if measured_fuel is not None:
            fuel_actual.append(measured_fuel)
            fuel_predicted.append(prediction["predicted_fuel_kg_h"])
        if measured_co2 is not None:
            co2_actual.append(measured_co2)
            co2_predicted.append(prediction["predicted_co2_kg_h"])

    report = {
        "validation_status": "completed",
        "csv_path": str(path),
        "sample_count": len(rows),
        "fuel_burn_rate_kg_h": calculate_validation_metrics(fuel_actual, fuel_predicted),
        "co2_kg_h": calculate_validation_metrics(co2_actual, co2_predicted),
        "model_mode": SIMULATOR_MODEL_MODE,
    }

    output_path = Path("validation_report.json")
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("Validation summary")
    print(json.dumps(report, indent=2))
    return report


def send_batch(vessel: VesselState) -> None:
    payload = vessel.make_batch()

    if SIMULATOR_OFFLINE_MODE:
        write_dry_run_payload(payload)
        print("=" * 80)
        print(f"{vessel.name} | OFFLINE MODE | payload generated locally")
        if payload["items"]:
            item = payload["items"][-1]
            print(
                f"{item['timestamp_utc']} | "
                f"{item['route_leg_from']} -> {item['route_leg_to']} | "
                f"type={item['vessel_type']} | "
                f"mode={item['vessel_mode']} | "
                f"SOG={item['speed_over_ground']} kn | "
                f"draft={item['draft']} m | "
                f"depth={item['depth']} m | "
                f"UKC={item['ukc']} m | "
                f"fouling={item['fouling_stage']} ({item['fouling_multiplier']}) | "
                f"power={item['required_power_kw']} kW | "
                f"fuel={item['fuel_burn_rate']} kg/h | "
                f"CO2={item['co2_value']} | "
                f"CH4={item['ch4_value']} | "
                f"N2O={item['n2o_value']}"
            )
        return

    if not FUNCTION_URL:
        raise RuntimeError(
            "SIMULATOR_FUNCTION_URL is required in online mode. "
            "Set SIMULATOR_OFFLINE_MODE=true to skip Supabase upload."
        )

    headers: Dict[str, str] = {}
    if SUPABASE_ANON_KEY:
        headers["apikey"] = SUPABASE_ANON_KEY
        headers["Authorization"] = f"Bearer {SUPABASE_ANON_KEY}"
    if USE_AUTH_HEADERS:
        headers["x-gateway-uid"] = vessel.gateway_uid
        headers["x-gateway-key"] = vessel.gateway_key

    try:
        response = requests.post(
            FUNCTION_URL,
            json=payload,
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException as e:
        print("=" * 80)
        print(f"{vessel.name} | REQUEST ERROR: {e}")
        return

    print("=" * 80)
    print(f"{vessel.name} | Status: {response.status_code}")

    if payload["items"]:
        item = payload["items"][-1]
        print(
            f"{item['timestamp_utc']} | "
            f"{item['route_leg_from']} -> {item['route_leg_to']} | "
            f"type={item['vessel_type']} | "
            f"mode={item['vessel_mode']} | "
            f"SOG={item['speed_over_ground']} kn | "
            f"draft={item['draft']} m | "
            f"depth={item['depth']} m | "
            f"UKC={item['ukc']} m | "
            f"fouling={item['fouling_stage']} ({item['fouling_multiplier']}) | "
            f"power={item['required_power_kw']} kW | "
            f"fuel={item['fuel_burn_rate']} kg/h | "
            f"CO2={item['co2_value']} | "
            f"CH4={item['ch4_value']} | "
            f"N2O={item['n2o_value']}"
        )

    if response.status_code != 200:
        print("ERROR RESPONSE:")
        try:
            print(json.dumps(response.json(), indent=2))
        except Exception:
            print(response.text)
    else:
        try:
            print("OK RESPONSE:")
            print(json.dumps(response.json(), indent=2))
        except Exception:
            print("OK")


def main() -> None:
    if SIMULATOR_VALIDATION_CSV:
        run_validation(SIMULATOR_VALIDATION_CSV)
        return

    validate_runtime_configuration()

    sync_vessel_identity_from_supabase(VESSELS)
    print("Fleet simulator started")
    if SIMULATOR_OFFLINE_MODE:
        print("Simulator running in OFFLINE MODE - no Supabase upload will be performed.")
    else:
        print("Simulator running in ONLINE MODE - telemetry will be sent to configured Supabase endpoint.")
        print(f"Function URL: {FUNCTION_URL}")
        print(f"Control URL: {SIMULATOR_STATUS_URL}")
    print(f"Model mode: {SIMULATOR_MODEL_MODE}")
    print(f"Loop every {LOOP_SLEEP_SECONDS}s, simulated step = {SIMULATED_MINUTES_PER_LOOP} minutes")
    print(f"Points per batch: {POINTS_PER_BATCH}")
    print(f"Vessels: {len(VESSELS)}")
    print(f"Bathymetry tile directory: {BATHYMETRY_TILE_DIR}")
    if BATHYMETRY.available:
        print(f"Bathymetry data available from {BATHYMETRY.tile_dir}")
    else:
        print(
            "Bathymetry data unavailable - synthetic fallback will be used. "
            f"Reason: {BATHYMETRY.load_error or 'no supported tiles found'}"
        )

    while True:
        enabled = get_simulator_enabled()

        if enabled:
            if SIMULATOR_OFFLINE_MODE:
                print("Offline mode active - generating telemetry locally")
            else:
                print("Simulator enabled - sending telemetry")
            for vessel in VESSELS:
                send_batch(vessel)
        else:
            print("Simulator disabled - waiting")

        time.sleep(LOOP_SLEEP_SECONDS)


if __name__ == "__main__":
    main()
