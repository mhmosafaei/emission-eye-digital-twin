from __future__ import annotations

import json

from app.models import BaselineComparison, PerformanceWindow


def generate_baseline_message(comparison: BaselineComparison, window: PerformanceWindow) -> dict:
    possible_causes = _possible_causes(window)
    if comparison.classification == "worse":
        crew_message = (
            f"In similar operating conditions, this vessel previously achieved {comparison.baseline_co2_kg_nm:.1f} kg CO2/nm. "
            f"Current performance is {comparison.current_co2_kg_nm:.1f} kg CO2/nm, about {comparison.performance_gap_pct:.1f}% worse. "
            "Recommended checks: trim, RPM/load balance, rudder activity, fuel-flow stability, weather impact, and hull/propeller resistance."
        )
    elif comparison.classification == "better":
        crew_message = (
            f"In similar operating conditions, this vessel is outperforming its historical baseline. "
            f"Current performance is {abs(comparison.performance_gap_pct or 0.0):.1f}% better than the baseline."
        )
    elif comparison.classification == "normal":
        crew_message = (
            "Current performance is within the vessel's normal historical range for similar operating conditions."
        )
    elif comparison.classification == "insufficient_history":
        crew_message = "There is not yet enough historical data in similar conditions to establish a reliable baseline."
    else:
        invalid_reasons = _invalid_reasons(window)
        reason_text = ", ".join(invalid_reasons) if invalid_reasons else "unknown reasons"
        crew_message = f"This operating window is not valid for baseline comparison. Reasons: {reason_text}."

    return {
        "crew_message": crew_message,
        "possible_causes": possible_causes or (_invalid_reasons(window) if comparison.classification == "invalid_window" else ["unknown"]),
        "possible_causes_json": json.dumps(possible_causes or (_invalid_reasons(window) if comparison.classification == "invalid_window" else ["unknown"])),
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
