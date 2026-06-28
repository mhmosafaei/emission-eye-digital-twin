from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable

from .feature_store import FeatureRow, telemetry_to_feature_row


@dataclass(frozen=True)
class ValidationSummary:
    sample_count: int
    mean_co2_kg_nm: float | None
    mean_fuel_kg_nm: float | None
    min_co2_kg_nm: float | None
    max_co2_kg_nm: float | None
    missing_rate: float
    training_valid_rate: float
    confidence_mean: float | None
    uncertainty_mean: float | None

    def as_dict(self) -> dict:
        return asdict(self)


def summarize_telemetry(telemetry_items: Iterable[dict]) -> ValidationSummary:
    items = list(telemetry_items)
    if not items:
        return ValidationSummary(0, None, None, None, None, 0.0, 0.0, None, None)

    feature_rows = [_feature_row_from_item(item) for item in items]
    co2_per_nm_values = [row.co2_kg_nm for row in feature_rows if row.co2_kg_nm is not None]
    fuel_per_nm_values = []
    confidence_values = []
    uncertainty_values = []
    missing_cells = 0
    total_cells = 0
    training_valid_count = 0

    for item, row in zip(items, feature_rows):
        distance_nm = item.get("distance_from_previous_nm")
        fuel_step_kg = item.get("fuel_burn_step_kg")
        if distance_nm not in {None, 0} and fuel_step_kg is not None:
            fuel_per_nm_values.append(float(fuel_step_kg) / float(distance_nm))

        confidence = item.get("confidence_score")
        if confidence is not None:
            confidence_values.append(float(confidence))

        uncertainty = item.get("uncertainty_pct")
        if uncertainty is not None:
            uncertainty_values.append(float(uncertainty))

        row_dict = row.as_dict()
        training_valid_count += int(row.is_valid_for_training)
        total_cells += len(row_dict)
        missing_cells += sum(1 for value in row_dict.values() if value in {None, ""})

    return ValidationSummary(
        sample_count=len(items),
        mean_co2_kg_nm=_mean_or_none(co2_per_nm_values),
        mean_fuel_kg_nm=_mean_or_none(fuel_per_nm_values),
        min_co2_kg_nm=min(co2_per_nm_values) if co2_per_nm_values else None,
        max_co2_kg_nm=max(co2_per_nm_values) if co2_per_nm_values else None,
        missing_rate=round(missing_cells / total_cells, 6) if total_cells else 0.0,
        training_valid_rate=round(training_valid_count / len(feature_rows), 6) if feature_rows else 0.0,
        confidence_mean=_mean_or_none(confidence_values),
        uncertainty_mean=_mean_or_none(uncertainty_values),
    )


def _mean_or_none(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 6)


def _feature_row_from_item(item: dict) -> FeatureRow:
    ee_enrichment = item.get("ee_enrichment") or {}
    feature_row = ee_enrichment.get("feature_row")
    if isinstance(feature_row, dict):
        return FeatureRow(**feature_row)
    return telemetry_to_feature_row(item)
