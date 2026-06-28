"""Foundation modules for the Emission-Eye simulator extension layer."""

from .enrichment import enrich_simulator_batch, enrich_simulator_item
from .feature_store import FeatureRow, telemetry_to_feature_row
from .machinery import (
    AuxiliaryEngineSystem,
    BoilerSystem,
    MachineryComponentOutput,
    MachinerySnapshot,
    MainEngine,
)
from .scenarios import ScenarioConfig, load_scenario
from .sensor_model import SensorReadings, synthesize_sensor_readings
from .state_buckets import build_state_bucket
from .validation_suite import ValidationSummary, summarize_telemetry
from .vessel_geometry import (
    VesselGeometry,
    calculate_depth_draft_ratio,
    calculate_mean_draft,
    calculate_trim,
    classify_depth_condition,
    estimate_displacement_proxy,
)

__all__ = [
    "AuxiliaryEngineSystem",
    "BoilerSystem",
    "FeatureRow",
    "MachineryComponentOutput",
    "MachinerySnapshot",
    "MainEngine",
    "ScenarioConfig",
    "SensorReadings",
    "ValidationSummary",
    "VesselGeometry",
    "enrich_simulator_batch",
    "enrich_simulator_item",
    "build_state_bucket",
    "calculate_depth_draft_ratio",
    "calculate_mean_draft",
    "calculate_trim",
    "classify_depth_condition",
    "estimate_displacement_proxy",
    "load_scenario",
    "summarize_telemetry",
    "synthesize_sensor_readings",
    "telemetry_to_feature_row",
]
