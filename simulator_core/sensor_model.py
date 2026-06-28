from __future__ import annotations

from dataclasses import asdict, dataclass


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


@dataclass(frozen=True)
class SensorReadings:
    co2_percent: float
    ch4_ppm: float
    n2o_ppm: float
    o2_percent: float
    exhaust_flow_kg_h: float
    exhaust_temp_c: float
    exhaust_pressure_kpa: float
    exhaust_moisture_pct: float
    sensor_drift_pct: float
    calibration_valid: bool
    condensation_flag: bool
    sensor_quality_flag: str

    def as_dict(self) -> dict:
        return asdict(self)


def synthesize_sensor_readings(
    telemetry_item: dict,
    *,
    sensor_quality_mode: str = "standard",
) -> SensorReadings:
    fuel_flow_kg_h = float(telemetry_item.get("fuel_burn_rate") or telemetry_item.get("predicted_fuel_kg_h") or 0.0)
    co2_kg_h = float(telemetry_item.get("co2_value") or 0.0)
    ch4_kg_h = float(telemetry_item.get("ch4_value") or 0.0)
    n2o_kg_h = float(telemetry_item.get("n2o_value") or 0.0)
    engine_load_ratio = float(telemetry_item.get("engine_load_ratio") or 0.0)
    wave_height = float(telemetry_item.get("weather_wave_height") or 0.0)
    air_temp = float(telemetry_item.get("weather_air_temp") or 15.0)

    quality_profiles = {
        "high": (0.2, True),
        "standard": (0.75, True),
        "low": (1.8, False),
        "degraded": (3.5, False),
    }
    drift_pct, calibration_valid = quality_profiles.get(sensor_quality_mode, quality_profiles["standard"])

    exhaust_flow_kg_h = max(fuel_flow_kg_h * (14.5 + (engine_load_ratio * 3.5)), 1.0)
    co2_percent = _clamp((co2_kg_h / exhaust_flow_kg_h) * 100.0, 0.0, 20.0)
    ch4_ppm = _clamp((ch4_kg_h / exhaust_flow_kg_h) * 1_000_000.0, 0.0, 100_000.0)
    n2o_ppm = _clamp((n2o_kg_h / exhaust_flow_kg_h) * 1_000_000.0, 0.0, 25_000.0)
    o2_percent = _clamp(16.0 - (engine_load_ratio * 5.0), 2.0, 18.0)
    exhaust_temp_c = 165.0 + (engine_load_ratio * 210.0)
    exhaust_pressure_kpa = 101.3 + (engine_load_ratio * 18.0)
    exhaust_moisture_pct = _clamp(7.0 + (fuel_flow_kg_h / 5000.0) * 4.0, 4.0, 16.0)
    condensation_flag = exhaust_temp_c < (air_temp + 25.0) or wave_height > 4.0
    sensor_quality_flag = "ok" if calibration_valid and drift_pct <= 1.0 else "check"

    return SensorReadings(
        co2_percent=round(co2_percent, 4),
        ch4_ppm=round(ch4_ppm, 4),
        n2o_ppm=round(n2o_ppm, 4),
        o2_percent=round(o2_percent, 4),
        exhaust_flow_kg_h=round(exhaust_flow_kg_h, 4),
        exhaust_temp_c=round(exhaust_temp_c, 4),
        exhaust_pressure_kpa=round(exhaust_pressure_kpa, 4),
        exhaust_moisture_pct=round(exhaust_moisture_pct, 4),
        sensor_drift_pct=drift_pct,
        calibration_valid=calibration_valid,
        condensation_flag=condensation_flag,
        sensor_quality_flag=sensor_quality_flag,
    )
