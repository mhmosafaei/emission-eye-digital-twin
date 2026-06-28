from __future__ import annotations

from copy import deepcopy

from .feature_store import telemetry_to_feature_row
from .machinery import AuxiliaryEngineSystem, BoilerSystem, MachinerySnapshot, MainEngine
from .scenarios import ScenarioConfig
from .sensor_model import synthesize_sensor_readings
from .state_buckets import build_state_bucket
from .validation_suite import summarize_telemetry
from .vessel_geometry import (
    calculate_depth_draft_ratio,
    classify_depth_condition,
    estimate_displacement_proxy,
)

VESSEL_ENRICHMENT_DEFAULTS = {
    "ContainerVessel": {
        "length_pp_m": 280.0,
        "beam_m": 40.0,
        "design_draft_m": 12.8,
        "gross_tonnage": 54000.0,
        "deadweight_tonnes": 32000.0,
        "main_engine_power_kw": 18000.0,
        "aux_power_kw": 2400.0,
        "boiler_power_kw": 900.0,
        "main_engine_sfoc_g_per_kwh": 178.0,
        "aux_engine_sfoc_g_per_kwh": 210.0,
        "boiler_sfoc_g_per_kwh": 225.0,
    },
    "BulkerVessel": {
        "length_pp_m": 225.0,
        "beam_m": 32.0,
        "design_draft_m": 11.4,
        "gross_tonnage": 30000.0,
        "deadweight_tonnes": 18000.0,
        "main_engine_power_kw": 14000.0,
        "aux_power_kw": 1800.0,
        "boiler_power_kw": 700.0,
        "main_engine_sfoc_g_per_kwh": 180.0,
        "aux_engine_sfoc_g_per_kwh": 212.0,
        "boiler_sfoc_g_per_kwh": 230.0,
    },
    "TankerVessel": {
        "length_pp_m": 245.0,
        "beam_m": 38.0,
        "design_draft_m": 13.1,
        "gross_tonnage": 43000.0,
        "deadweight_tonnes": 52000.0,
        "main_engine_power_kw": 18000.0,
        "aux_power_kw": 2400.0,
        "boiler_power_kw": 1000.0,
        "main_engine_sfoc_g_per_kwh": 176.0,
        "aux_engine_sfoc_g_per_kwh": 209.0,
        "boiler_sfoc_g_per_kwh": 228.0,
    },
    "LNGCarrier": {
        "length_pp_m": 285.0,
        "beam_m": 43.0,
        "design_draft_m": 11.7,
        "gross_tonnage": 92000.0,
        "deadweight_tonnes": 76000.0,
        "main_engine_power_kw": 32000.0,
        "aux_power_kw": 3000.0,
        "boiler_power_kw": 1200.0,
        "main_engine_sfoc_g_per_kwh": 155.0,
        "aux_engine_sfoc_g_per_kwh": 198.0,
        "boiler_sfoc_g_per_kwh": 210.0,
    },
}


def enrich_simulator_item(item: dict, scenario: ScenarioConfig | None = None) -> dict:
    working_item = deepcopy(item)
    geometry = _build_geometry_summary(working_item, scenario)
    derived_item = deepcopy(working_item)
    derived_item.setdefault("trim_m", geometry["trim_m"])
    if scenario and "loading_condition" not in derived_item:
        derived_item["loading_condition"] = scenario.loading_condition

    state_bucket = build_state_bucket(derived_item)
    feature_row = telemetry_to_feature_row(derived_item).as_dict()
    sensor_fields = synthesize_sensor_readings(
        derived_item,
        sensor_quality_mode=_sensor_quality_mode(scenario),
    ).as_dict()
    machinery_breakdown = _build_machinery_breakdown(derived_item).as_dict()

    enriched_item = deepcopy(working_item)
    enriched_item["ee_enrichment"] = {
        "state_bucket": state_bucket,
        "is_valid_for_training": feature_row["is_valid_for_training"],
        "feature_row": feature_row,
        "sensor_fields": sensor_fields,
        "machinery_breakdown": {
            "main_engine": machinery_breakdown["main_engine"],
            "auxiliary_engines": machinery_breakdown["auxiliary_system"],
            "boiler": machinery_breakdown["boiler_system"],
            "total": machinery_breakdown["total"],
        },
        "geometry": geometry,
        "validation_flags": _build_validation_flags(working_item, feature_row, scenario),
    }
    if scenario is not None:
        enriched_item["ee_enrichment"]["scenario"] = {
            "scenario_name": scenario.scenario_name,
            "route_name": scenario.route_name,
            "fuel_type": scenario.fuel_type,
            "loading_condition": scenario.loading_condition,
            "weather_severity": scenario.weather_severity,
            "wave_direction_mode": scenario.wave_direction_mode,
            "fouling_level": scenario.fouling_level,
            "sensor_quality_mode": scenario.sensor_quality_mode,
            "duration_minutes": scenario.duration_minutes,
            "random_seed": scenario.random_seed,
        }
    return enriched_item


def enrich_simulator_batch(batch: dict, scenario: ScenarioConfig | None = None) -> dict:
    enriched_batch = deepcopy(batch)
    items = []
    items_failed = 0

    for item in batch.get("items", []):
        try:
            items.append(enrich_simulator_item(item, scenario))
        except Exception as exc:
            failed_item = deepcopy(item)
            failed_item["ee_enrichment"] = {"error": str(exc)}
            items.append(failed_item)
            items_failed += 1

    enriched_batch["items"] = items
    successful_items = [item for item in items if "feature_row" in (item.get("ee_enrichment") or {})]
    enriched_batch["ee_batch_enrichment"] = {
        "item_count": len(batch.get("items", [])),
        "items_enriched": len(successful_items),
        "items_failed": items_failed,
        "scenario_name": scenario.scenario_name if scenario else None,
        "validation_summary": summarize_telemetry(successful_items).as_dict() if successful_items else None,
    }
    return enriched_batch


def _build_geometry_summary(item: dict, scenario: ScenarioConfig | None) -> dict:
    defaults = _defaults_for(item, scenario)
    mean_draft_m = float(item.get("draft") or item.get("effective_draft") or defaults["design_draft_m"] * 0.75)
    trim_m = float(item.get("trim_m") or 0.0)
    depth_m = float(item.get("depth") or max(mean_draft_m * 3.0, 1.0))
    depth_draft_ratio = calculate_depth_draft_ratio(depth_m, max(mean_draft_m, 0.1))
    return {
        "mean_draft_m": round(mean_draft_m, 6),
        "trim_m": round(trim_m, 6),
        "depth_draft_ratio": round(depth_draft_ratio, 6),
        "depth_condition": classify_depth_condition(depth_draft_ratio),
        "displacement_proxy": round(
            estimate_displacement_proxy(
                length_pp_m=defaults["length_pp_m"],
                beam_m=defaults["beam_m"],
                mean_draft_m=mean_draft_m,
            ),
            6,
        ),
    }


def _build_machinery_breakdown(item: dict) -> MachinerySnapshot:
    defaults = _defaults_for(item, None)
    quality_flags = item.get("quality_flags") or {}
    main_engine_power_kw = float(quality_flags.get("shaft_power_kw") or item.get("required_power_kw") or 0.0)
    auxiliary_power_kw = float(
        quality_flags.get("auxiliary_load_kw")
        or quality_flags.get("generator_load_ratio", 0.0) * defaults["aux_power_kw"]
        or max(main_engine_power_kw * 0.08, 0.0)
    )
    boiler_power_kw = float(
        quality_flags.get("boiler_power_kw")
        or (defaults["boiler_power_kw"] * 0.35 if main_engine_power_kw > 0 else defaults["boiler_power_kw"] * 0.15)
    )

    snapshot = MachinerySnapshot.build(
        main_engine=MainEngine(
            rated_power_kw=defaults["main_engine_power_kw"],
            sfoc_g_per_kwh=defaults["main_engine_sfoc_g_per_kwh"],
            fuel_type=str(item.get("fuel_type") or "MGO_PROXY"),
        ),
        auxiliary_system=AuxiliaryEngineSystem(
            rated_power_kw=defaults["aux_power_kw"],
            sfoc_g_per_kwh=defaults["aux_engine_sfoc_g_per_kwh"],
            fuel_type=str(item.get("fuel_type") or "MGO_PROXY"),
        ),
        boiler_system=BoilerSystem(
            rated_power_kw=defaults["boiler_power_kw"],
            sfoc_g_per_kwh=defaults["boiler_sfoc_g_per_kwh"],
            fuel_type=str(item.get("fuel_type") or "MGO_PROXY"),
        ),
        main_engine_power_kw=main_engine_power_kw,
        auxiliary_power_kw=auxiliary_power_kw,
        boiler_power_kw=boiler_power_kw,
    )
    return snapshot


def _build_validation_flags(item: dict, feature_row: dict, scenario: ScenarioConfig | None) -> dict:
    required = ("timestamp_utc", "fuel_burn_rate", "co2_value", "speed_over_ground", "draft", "depth")
    missing = [field_name for field_name in required if item.get(field_name) in {None, ""}]
    return {
        "has_required_fields": not missing,
        "missing_fields": missing,
        "scenario_applied": scenario is not None,
        "training_valid": feature_row["is_valid_for_training"],
        "confidence_score": item.get("confidence_score"),
        "uncertainty_pct": item.get("uncertainty_pct"),
    }


def _sensor_quality_mode(scenario: ScenarioConfig | None) -> str:
    if scenario is None:
        return "standard"
    return scenario.sensor_quality_mode


def _defaults_for(item: dict, scenario: ScenarioConfig | None) -> dict:
    vessel_type = str(item.get("vessel_type") or (scenario.vessel_type if scenario else "") or "ContainerVessel")
    defaults = VESSEL_ENRICHMENT_DEFAULTS.get(vessel_type, VESSEL_ENRICHMENT_DEFAULTS["ContainerVessel"]).copy()
    defaults["gross_tonnage"] = float(item.get("gross_tonnage") or defaults["gross_tonnage"])
    defaults["deadweight_tonnes"] = float(item.get("deadweight_tonnes") or defaults["deadweight_tonnes"])
    return defaults
