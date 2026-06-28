from __future__ import annotations

from dataclasses import asdict, dataclass

from .state_buckets import build_state_bucket, normalize_operation_mode


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
    operation_mode = normalize_operation_mode(
        telemetry_item.get("operation_mode") or telemetry_item.get("vessel_mode")
    )
    training_valid = _is_valid_for_training(
        telemetry_item=telemetry_item,
        operation_mode=operation_mode,
        sog_kn=sog_kn,
        co2_kg_h=co2_kg_h,
        co2_kg_nm=co2_kg_nm,
        co2_g_kwh=co2_g_kwh,
        shaft_power_kw=shaft_power_kw,
        fuel_flow_kg_h=fuel_flow_kg_h,
        state_bucket=state_bucket,
    )

    return FeatureRow(
        timestamp_utc=str(telemetry_item.get("timestamp_utc") or ""),
        vessel_id=str(
            telemetry_item.get("node_id")
            or telemetry_item.get("imo_number")
            or telemetry_item.get("vessel_name")
            or "unknown_vessel"
        ),
        operation_mode=operation_mode,
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


def _is_valid_for_training(
    *,
    telemetry_item: dict,
    operation_mode: str,
    sog_kn: float,
    co2_kg_h: float,
    co2_kg_nm: float | None,
    co2_g_kwh: float | None,
    shaft_power_kw: float,
    fuel_flow_kg_h: float,
    state_bucket: str,
) -> bool:
    if operation_mode != "sea_passage":
        return False
    if sog_kn < 6.0:
        return False
    if co2_kg_h <= 0:
        return False
    if co2_kg_nm is None or co2_kg_nm <= 0:
        return False
    if co2_g_kwh is None or co2_g_kwh <= 0:
        return False
    if shaft_power_kw <= 0:
        return False
    if fuel_flow_kg_h <= 0:
        return False
    if not state_bucket:
        return False
    if telemetry_item.get("timestamp_utc") in {None, ""}:
        return False
    confidence_score = telemetry_item.get("confidence_score")
    if confidence_score is not None and float(confidence_score) < 30.0:
        return False
    uncertainty_pct = telemetry_item.get("uncertainty_pct")
    if uncertainty_pct is not None and float(uncertainty_pct) > 80.0:
        return False
    return True
