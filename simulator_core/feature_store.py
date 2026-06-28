from __future__ import annotations

from dataclasses import asdict, dataclass

from .state_buckets import build_state_bucket


@dataclass(frozen=True)
class FeatureRow:
    timestamp_utc: str
    vessel_id: str
    operation_mode: str
    sog_kn: float
    stw_kn: float
    rpm: float
    engine_load_pct: float
    shaft_power_kw: float
    fuel_flow_kg_h: float
    co2_kg_h: float
    co2_kg_nm: float | None
    co2_g_kwh: float | None
    draft_m: float
    trim_m: float
    wind_speed_kn: float
    relative_wind_angle_deg: float
    wave_height_m: float
    depth_m: float
    ukc_m: float
    fouling_multiplier: float
    fuel_type: str
    state_bucket: str
    is_valid_for_training: bool

    def as_dict(self) -> dict:
        return asdict(self)


def telemetry_to_feature_row(telemetry_item: dict) -> FeatureRow:
    quality_flags = telemetry_item.get("quality_flags") or {}
    sog_kn = float(telemetry_item.get("speed_over_ground") or 0.0)
    current_along_track_kn = float(quality_flags.get("current_along_track_kn") or 0.0)
    stw_kn = max(sog_kn - current_along_track_kn, 0.0)
    shaft_power_kw = float(
        quality_flags.get("shaft_power_kw")
        or telemetry_item.get("required_power_kw")
        or 0.0
    )
    fuel_flow_kg_h = float(
        telemetry_item.get("fuel_burn_rate")
        or telemetry_item.get("predicted_fuel_kg_h")
        or 0.0
    )
    co2_kg_h = float(
        telemetry_item.get("co2_value")
        or telemetry_item.get("corrected_co2_value")
        or 0.0
    )
    distance_nm = telemetry_item.get("distance_from_previous_nm")
    co2_mass_step_kg = telemetry_item.get("co2_mass_step_kg")
    co2_kg_nm = None
    if distance_nm not in {None, 0} and co2_mass_step_kg is not None:
        co2_kg_nm = round(float(co2_mass_step_kg) / float(distance_nm), 6)

    co2_g_kwh = None
    if shaft_power_kw > 0:
        co2_g_kwh = round((co2_kg_h * 1000.0) / shaft_power_kw, 6)

    engine_load_pct = round(float(telemetry_item.get("engine_load_ratio") or 0.0) * 100.0, 6)
    draft_m = float(telemetry_item.get("draft") or telemetry_item.get("draft_m") or 0.0)
    trim_m = float(telemetry_item.get("trim_m") or 0.0)
    state_bucket = build_state_bucket(telemetry_item)
    training_valid = _is_valid_for_training(telemetry_item, co2_kg_nm)

    return FeatureRow(
        timestamp_utc=str(telemetry_item.get("timestamp_utc") or ""),
        vessel_id=str(
            telemetry_item.get("node_id")
            or telemetry_item.get("imo_number")
            or telemetry_item.get("vessel_name")
            or "unknown_vessel"
        ),
        operation_mode=str(telemetry_item.get("vessel_mode") or telemetry_item.get("operation_mode") or "unknown"),
        sog_kn=round(sog_kn, 6),
        stw_kn=round(stw_kn, 6),
        rpm=float(telemetry_item.get("rpm") or 0.0),
        engine_load_pct=engine_load_pct,
        shaft_power_kw=round(shaft_power_kw, 6),
        fuel_flow_kg_h=round(fuel_flow_kg_h, 6),
        co2_kg_h=round(co2_kg_h, 6),
        co2_kg_nm=co2_kg_nm,
        co2_g_kwh=co2_g_kwh,
        draft_m=round(draft_m, 6),
        trim_m=round(trim_m, 6),
        wind_speed_kn=float(telemetry_item.get("weather_wind_speed") or 0.0),
        relative_wind_angle_deg=float(telemetry_item.get("relative_wind_angle") or 0.0),
        wave_height_m=float(telemetry_item.get("weather_wave_height") or 0.0),
        depth_m=float(telemetry_item.get("depth") or telemetry_item.get("depth_m") or 0.0),
        ukc_m=float(telemetry_item.get("ukc") or 0.0),
        fouling_multiplier=float(telemetry_item.get("fouling_multiplier") or 1.0),
        fuel_type=str(telemetry_item.get("fuel_type") or "unknown"),
        state_bucket=state_bucket,
        is_valid_for_training=training_valid,
    )


def _is_valid_for_training(telemetry_item: dict, co2_kg_nm: float | None) -> bool:
    if co2_kg_nm is None:
        return False
    if telemetry_item.get("validation_status") in {"uncalibrated_synthetic"}:
        return False
    if float(telemetry_item.get("confidence_score") or 0.0) < 50.0:
        return False
    for field_name in ("timestamp_utc", "fuel_burn_rate", "co2_value", "speed_over_ground"):
        if telemetry_item.get(field_name) in {None, ""}:
            return False
    return True
