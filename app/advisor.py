from __future__ import annotations

import json
from collections.abc import Iterable

from app.models import BaselineComparison, PerformanceWindow


def generate_baseline_message(comparison: BaselineComparison, window: PerformanceWindow) -> dict:
    possible_causes = _possible_causes(window)
    invalid_reasons = _invalid_reasons(window)
    advisor = _build_advisor_payload(
        comparison=comparison,
        window=window,
        possible_causes=possible_causes,
        invalid_reasons=invalid_reasons,
    )

    return {
        "severity": advisor["severity"],
        "headline": advisor["headline"],
        "crew_message": advisor["crew_message"],
        "recommended_checks": advisor["recommended_checks"],
        "possible_causes": advisor["possible_causes"],
        "commercial_impact_hint": advisor["commercial_impact_hint"],
        "possible_causes_json": json.dumps(advisor["possible_causes"]),
        "advisor_json": json.dumps(advisor),
    }


def _possible_causes(window: PerformanceWindow) -> list[str]:
    causes: list[str] = []
    if (window.avg_wind_speed_kn or 0.0) >= 20.0:
        causes.append("high_wind")
    if (window.avg_wave_height_m or 0.0) >= 2.5:
        causes.append("high_wave")
    if abs(window.avg_trim_m or 0.0) >= 1.5:
        causes.append("possible_trim_issue")
    if (window.avg_fouling_multiplier or 0.0) >= 1.08:
        causes.append("high_fouling")
    if (window.avg_engine_load_pct or 0.0) >= 75.0:
        causes.append("high_engine_load")
    if (window.avg_sog_kn or 0.0) < 11.0 and (window.avg_shaft_power_kw or 0.0) > 9000.0:
        causes.append("low_speed_high_power")
    if (window.avg_draft_m or 0.0) > 0 and (window.avg_depth_m or 0.0) < (window.avg_draft_m * 2.5):
        causes.append("shallow_water_effect")
    return causes


def _invalid_reasons(window: PerformanceWindow) -> list[str]:
    if not window.invalid_reasons_json:
        return []
    try:
        parsed = json.loads(window.invalid_reasons_json)
    except json.JSONDecodeError:
        return []
    return [str(reason) for reason in parsed]


def _build_advisor_payload(
    *,
    comparison: BaselineComparison,
    window: PerformanceWindow,
    possible_causes: list[str],
    invalid_reasons: list[str],
) -> dict:
    severity = _severity_for_comparison(comparison)
    resolved_causes = possible_causes or (invalid_reasons if comparison.classification == "invalid_window" else ["unknown"])
    recommended_checks = _recommended_checks(window, resolved_causes)
    commercial_impact_hint = _commercial_impact_hint(comparison)

    if comparison.classification == "worse":
        headline = "Performance is above baseline"
        crew_message = (
            f"In similar conditions, this vessel previously achieved {comparison.baseline_co2_kg_nm:.1f} kg CO2/nm. "
            f"Current performance is {comparison.current_co2_kg_nm:.1f} kg CO2/nm, about {comparison.performance_gap_pct:.1f}% worse than baseline."
        )
    elif comparison.classification == "better":
        headline = "Performance is better than baseline"
        crew_message = (
            f"Current sea-passage performance is {abs(comparison.performance_gap_pct or 0.0):.1f}% better than the vessel's historical baseline in similar conditions."
        )
    elif comparison.classification == "normal":
        headline = "Performance is within baseline range"
        crew_message = "Current performance is within the vessel's normal historical range for similar operating conditions."
    elif comparison.classification == "insufficient_history":
        headline = "Baseline needs more history"
        crew_message = "There is not yet enough historical data in similar conditions to establish a reliable baseline."
    else:
        headline = "Window not valid for baseline comparison"
        reason_text = ", ".join(invalid_reasons) if invalid_reasons else "unknown reasons"
        crew_message = f"This operating window is not valid for baseline comparison. Reasons: {reason_text}."

    return {
        "severity": severity,
        "headline": headline,
        "crew_message": crew_message,
        "recommended_checks": recommended_checks,
        "possible_causes": resolved_causes,
        "commercial_impact_hint": commercial_impact_hint,
    }


def _severity_for_comparison(comparison: BaselineComparison) -> str:
    if comparison.classification in {"better", "normal", "insufficient_history", "invalid_window"}:
        return "info"
    gap = float(comparison.performance_gap_pct or 0.0)
    if gap > 15.0:
        return "critical"
    return "warning"


def _commercial_impact_hint(comparison: BaselineComparison) -> str:
    if comparison.classification == "worse":
        return (
            "If this gap persisted over a full sea passage, fuel and CO2 costs would be materially higher than the vessel's own demonstrated baseline."
        )
    if comparison.classification == "better":
        return "If this improvement is repeatable, the vessel is demonstrating a commercially favorable operating pattern."
    if comparison.classification == "normal":
        return "Current performance is broadly aligned with the vessel's demonstrated operating baseline."
    if comparison.classification == "insufficient_history":
        return "Commercial interpretation should wait until a larger history of comparable windows is available."
    return "This window should be excluded from commercial performance interpretation until data validity improves."


def _recommended_checks(window: PerformanceWindow, causes: Iterable[str]) -> list[str]:
    cause_set = {str(cause) for cause in causes}
    checks: list[str] = []
    if "possible_trim_issue" in cause_set:
        checks.append("trim optimization")
    if {"high_engine_load", "low_speed_high_power"} & cause_set:
        checks.append("RPM/load balance")
    if "high_fouling" in cause_set:
        checks.append("hull and propeller condition")
        checks.append("fouling check")
    if {"high_wind", "high_wave"} & cause_set:
        checks.append("weather routing impact")
    if "shallow_water_effect" in cause_set:
        checks.append("shallow-water effect")
    if (window.avg_fuel_flow_kg_h or 0.0) > 0:
        checks.append("fuel-flow sensor stability")
    if (window.avg_shaft_power_kw or 0.0) > 0:
        checks.append("shaft power consistency")
    if _speed_discrepancy(window):
        checks.append("speed-through-water vs speed-over-ground discrepancy")
    if not checks:
        checks.extend(["trim optimization", "RPM/load balance", "weather routing impact"])
    return _dedupe_preserve_order(checks)


def _speed_discrepancy(window: PerformanceWindow) -> bool:
    if window.avg_sog_kn is None or window.avg_stw_kn is None:
        return False
    return abs(window.avg_sog_kn - window.avg_stw_kn) >= 1.0


def _dedupe_preserve_order(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered
