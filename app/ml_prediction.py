from __future__ import annotations

import json
import statistics
import uuid
from typing import Any

from app.ml_features import build_prediction_dataset
from app.ml_training import load_model_artifact, load_model_metadata
from app.models import MLPrediction, PerformanceWindow
from app.repositories import (
    create_ml_predictions,
    get_latest_ml_prediction,
    get_ml_predictions,
    get_unpredicted_performance_windows_for_model,
)


def predict_expected_co2_for_windows(
    *,
    vessel_id: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    artifact = load_model_artifact()
    metadata = load_model_metadata() or artifact.get("metadata") or {}
    model = artifact["model"]
    vectorizer = artifact["vectorizer"]
    model_version = str(metadata.get("model_version") or "unknown")

    candidate_windows = get_unpredicted_performance_windows_for_model(
        model_version=model_version,
        vessel_id=vessel_id,
        limit=limit,
    )
    rows = [window for window in candidate_windows if _is_predictable(window)]
    features = [build_prediction_row(window) for window in rows]
    if not rows:
        return {
            "predictions_created": 0,
            "model_version": model_version,
            "model_type": metadata.get("model_type"),
        }

    x_matrix = vectorizer.transform(features)
    expected_values = model.predict(x_matrix)
    created = create_ml_predictions(
        [
            _build_prediction_record(
                window=window,
                expected_co2=float(expected),
                metadata=metadata,
            )
            for window, expected in zip(rows, expected_values, strict=False)
        ]
    )
    summary = summarize_ml_predictions()
    return {
        "predictions_created": len(created),
        "model_version": model_version,
        "model_type": metadata.get("model_type"),
        "summary": summary,
    }


def build_prediction_row(window: PerformanceWindow) -> dict[str, Any]:
    from app.ml_features import build_feature_row

    return build_feature_row(window)


def summarize_ml_predictions(vessel_id: str | None = None) -> dict[str, Any]:
    predictions = get_ml_predictions(vessel_id=vessel_id, limit=100000)
    total_predictions = len(predictions)
    gap_values = [float(prediction.ml_gap_pct) for prediction in predictions if prediction.ml_gap_pct is not None]
    latest = get_latest_ml_prediction(vessel_id=vessel_id)
    counts = {
        "ml_better": sum(1 for prediction in predictions if prediction.classification == "ml_better"),
        "ml_normal": sum(1 for prediction in predictions if prediction.classification == "ml_normal"),
        "ml_worse": sum(1 for prediction in predictions if prediction.classification == "ml_worse"),
    }
    return {
        "total_predictions": total_predictions,
        **counts,
        "average_ml_gap_pct": round(statistics.mean(gap_values), 6) if gap_values else None,
        "worst_ml_gap_pct": round(max(gap_values), 6) if gap_values else None,
        "best_ml_gap_pct": round(min(gap_values), 6) if gap_values else None,
        "model_type": latest.model_type if latest is not None else None,
        "model_version": latest.model_version if latest is not None else None,
        "interpretation": _summary_interpretation(counts, total_predictions),
    }


def format_prediction_result(prediction: MLPrediction) -> dict[str, Any]:
    return {
        "id": prediction.id,
        "prediction_uuid": prediction.prediction_uuid,
        "window_id": prediction.window_id,
        "vessel_id": prediction.vessel_id,
        "window_start_utc": prediction.window_start_utc,
        "actual_co2_kg_nm": prediction.actual_co2_kg_nm,
        "expected_co2_kg_nm": prediction.expected_co2_kg_nm,
        "ml_gap_kg_nm": prediction.ml_gap_kg_nm,
        "ml_gap_pct": prediction.ml_gap_pct,
        "classification": prediction.classification,
        "prediction_status": prediction.prediction_status,
        "model_type": prediction.model_type,
        "model_version": prediction.model_version,
        "model_metadata_json": prediction.model_metadata_json,
        "interpretation": _prediction_interpretation(prediction.classification),
        "created_at": prediction.created_at,
    }


def classify_ml_gap(ml_gap_pct: float | None) -> str:
    if ml_gap_pct is None:
        return "ml_unknown"
    if ml_gap_pct < -3.0:
        return "ml_better"
    if ml_gap_pct <= 5.0:
        return "ml_normal"
    return "ml_worse"


def _build_prediction_record(*, window: PerformanceWindow, expected_co2: float, metadata: dict[str, Any]) -> dict[str, Any]:
    actual = float(window.avg_co2_kg_nm or 0.0)
    ml_gap_kg_nm = round(actual - expected_co2, 6)
    ml_gap_pct = round(((actual - expected_co2) / expected_co2) * 100.0, 6) if expected_co2 != 0 else None
    classification = classify_ml_gap(ml_gap_pct)
    return {
        "prediction_uuid": str(uuid.uuid4()),
        "window_id": window.id,
        "vessel_id": window.vessel_id,
        "window_start_utc": window.window_start_utc,
        "actual_co2_kg_nm": actual,
        "expected_co2_kg_nm": round(expected_co2, 6),
        "ml_gap_kg_nm": ml_gap_kg_nm,
        "ml_gap_pct": ml_gap_pct,
        "classification": classification,
        "prediction_status": "completed",
        "model_type": metadata.get("model_type"),
        "model_version": metadata.get("model_version"),
        "model_metadata_json": json.dumps(metadata),
    }


def _is_predictable(window: PerformanceWindow) -> bool:
    return bool(window.is_valid_window) and window.avg_co2_kg_nm is not None and window.avg_sog_kn is not None and window.avg_fuel_kg_nm is not None


def _prediction_interpretation(classification: str) -> str:
    if classification == "ml_worse":
        return "Actual CO2 intensity is above ML-expected performance for these conditions."
    if classification == "ml_better":
        return "Actual CO2 intensity is better than the ML-expected level for these conditions."
    if classification == "ml_normal":
        return "Actual CO2 intensity is close to the ML-expected level for these conditions."
    return "ML prediction is available, but the performance classification is inconclusive."


def _summary_interpretation(counts: dict[str, int], total_predictions: int) -> str:
    if total_predictions == 0:
        return "No ML predictions are stored yet."
    if counts["ml_worse"] > counts["ml_normal"] and counts["ml_worse"] >= counts["ml_better"]:
        return "The model identifies repeated windows operating above expected CO2 intensity."
    if counts["ml_better"] > counts["ml_worse"]:
        return "The model identifies repeated windows operating better than expected CO2 intensity."
    return "Most predicted windows are operating near the model's expected CO2 intensity."
