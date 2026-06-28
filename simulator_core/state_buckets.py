from __future__ import annotations

from .vessel_geometry import calculate_depth_draft_ratio, classify_depth_condition


def build_state_bucket(telemetry_item: dict) -> str:
    operation_mode = _normalize_operation_mode(telemetry_item)
    loading_label = _loading_label(telemetry_item)
    speed_label = _range_label("speed", float(telemetry_item.get("speed_over_ground") or 0.0), 2, 20)
    load_pct = float(telemetry_item.get("engine_load_ratio") or 0.0) * 100.0
    load_label = _load_band(load_pct)
    wind_label = _wind_label(telemetry_item)
    wave_label = _wave_label(float(telemetry_item.get("weather_wave_height") or 0.0))
    depth_label = _depth_label(telemetry_item)
    fouling_label = _fouling_label(telemetry_item)
    return "|".join(
        [
            operation_mode,
            loading_label,
            speed_label,
            load_label,
            wind_label,
            wave_label,
            depth_label,
            fouling_label,
        ]
    )


def _normalize_operation_mode(telemetry_item: dict) -> str:
    mode = str(telemetry_item.get("vessel_mode") or telemetry_item.get("operation_mode") or "sea_passage").lower()
    if "stop" in mode:
        return "stopped"
    if "manoeuv" in mode or "maneuv" in mode:
        return "maneuvering"
    if "anchor" in mode:
        return "anchorage"
    return "sea_passage"


def _loading_label(telemetry_item: dict) -> str:
    explicit = telemetry_item.get("loading_condition")
    if explicit:
        return str(explicit).strip().lower()

    cargo = telemetry_item.get("cargo_quantity")
    deadweight = telemetry_item.get("deadweight_tonnes")
    if cargo is not None and deadweight not in {None, 0}:
        load_ratio = float(cargo) / float(deadweight)
        return "laden" if load_ratio >= 0.45 else "ballast"

    draft = telemetry_item.get("draft") or telemetry_item.get("draft_m")
    design_draft = telemetry_item.get("design_draft_m")
    if draft is not None and design_draft not in {None, 0}:
        return "laden" if (float(draft) / float(design_draft)) >= 0.7 else "ballast"
    return "unknown_load"


def _range_label(prefix: str, value: float, step: int, upper_cap: int) -> str:
    low = max(int(value // step) * step, 0)
    high = min(low + step, upper_cap)
    return f"{prefix}_{low}_{high}"


def _load_band(load_pct: float) -> str:
    if load_pct <= 0:
        return "load_0_10"
    bands = [(10, 30), (30, 50), (50, 70), (70, 90), (90, 110)]
    for low, high in bands:
        if low <= load_pct < high:
            return f"load_{low}_{high}"
    return "load_90_110"


def _wind_label(telemetry_item: dict) -> str:
    wind_speed = float(telemetry_item.get("weather_wind_speed") or 0.0)
    angle = float(telemetry_item.get("relative_wind_angle") or 0.0) % 360.0
    if angle <= 45 or angle >= 315:
        direction = "head_wind"
    elif 135 <= angle <= 225:
        direction = "tail_wind"
    else:
        direction = "cross_wind"

    if wind_speed < 5:
        band = "0_5"
    elif wind_speed < 15:
        band = "5_15"
    elif wind_speed < 25:
        band = "15_25"
    else:
        band = "25_plus"
    return f"{direction}_{band}"


def _wave_label(wave_height_m: float) -> str:
    if wave_height_m < 1:
        return "wave_0_1m"
    if wave_height_m < 2:
        return "wave_1_2m"
    if wave_height_m < 4:
        return "wave_2_4m"
    return "wave_4m_plus"


def _depth_label(telemetry_item: dict) -> str:
    draft = float(telemetry_item.get("draft") or telemetry_item.get("draft_m") or 0.0)
    depth = telemetry_item.get("depth") or telemetry_item.get("depth_m")
    if draft <= 0 or depth in {None, 0}:
        return "unknown_depth"
    ratio = calculate_depth_draft_ratio(float(depth), draft)
    return classify_depth_condition(ratio)


def _fouling_label(telemetry_item: dict) -> str:
    stage = telemetry_item.get("fouling_stage")
    if stage:
        return str(stage).strip().lower().replace(" ", "_")
    multiplier = float(telemetry_item.get("fouling_multiplier") or 1.0)
    if multiplier < 1.03:
        return "clean_hull"
    if multiplier < 1.08:
        return "light_fouling"
    if multiplier < 1.15:
        return "moderate_fouling"
    return "heavy_fouling"
