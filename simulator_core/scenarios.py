from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict


@dataclass(frozen=True)
class ScenarioConfig:
    scenario_name: str
    vessel_type: str
    route_name: str
    fuel_type: str
    loading_condition: str
    weather_severity: str
    wave_direction_mode: str
    fouling_level: str
    sensor_quality_mode: str
    duration_minutes: int
    random_seed: int

    @classmethod
    def from_mapping(cls, raw: Dict[str, Any]) -> "ScenarioConfig":
        required = {
            "scenario_name",
            "vessel_type",
            "route_name",
            "fuel_type",
            "loading_condition",
            "weather_severity",
            "wave_direction_mode",
            "fouling_level",
            "sensor_quality_mode",
            "duration_minutes",
            "random_seed",
        }
        missing = sorted(required - set(raw))
        if missing:
            raise ValueError(f"Scenario is missing required fields: {', '.join(missing)}")

        return cls(
            scenario_name=str(raw["scenario_name"]).strip(),
            vessel_type=str(raw["vessel_type"]).strip(),
            route_name=str(raw["route_name"]).strip(),
            fuel_type=str(raw["fuel_type"]).strip(),
            loading_condition=str(raw["loading_condition"]).strip(),
            weather_severity=str(raw["weather_severity"]).strip(),
            wave_direction_mode=str(raw["wave_direction_mode"]).strip(),
            fouling_level=str(raw["fouling_level"]).strip(),
            sensor_quality_mode=str(raw["sensor_quality_mode"]).strip(),
            duration_minutes=int(raw["duration_minutes"]),
            random_seed=int(raw["random_seed"]),
        )


def load_scenario(path: str | Path) -> ScenarioConfig:
    scenario_path = Path(path)
    raw_text = scenario_path.read_text(encoding="utf-8")
    suffix = scenario_path.suffix.lower()

    if suffix == ".json":
        payload = json.loads(raw_text)
    elif suffix in {".yaml", ".yml"}:
        payload = _load_yaml_like_mapping(raw_text)
    else:
        raise ValueError(f"Unsupported scenario file type: {scenario_path.suffix}")

    if not isinstance(payload, dict):
        raise ValueError("Scenario payload must be a mapping/object")
    return ScenarioConfig.from_mapping(payload)


def _load_yaml_like_mapping(raw_text: str) -> Dict[str, Any]:
    try:
        import yaml  # type: ignore

        payload = yaml.safe_load(raw_text)
        if isinstance(payload, dict):
            return payload
    except ImportError:
        pass

    mapping: Dict[str, Any] = {}
    for raw_line in raw_text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        if ":" not in line:
            raise ValueError(f"Unsupported YAML line: {raw_line!r}")
        key, value = line.split(":", 1)
        mapping[key.strip()] = _parse_scalar(value.strip())
    return mapping


def _parse_scalar(value: str) -> Any:
    if value == "":
        return ""
    lowered = value.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    if value.startswith(("'", '"')) and value.endswith(("'", '"')) and len(value) >= 2:
        return value[1:-1]
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value
