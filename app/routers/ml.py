from __future__ import annotations

from fastapi import APIRouter, Query

from app.ml_prediction import format_prediction_result, predict_expected_co2_for_windows, summarize_ml_predictions
from app.ml_training import load_model_metadata, train_expected_co2_model
from app.repositories import get_latest_ml_prediction, get_ml_predictions
from app.schemas import (
    MLModelMetadataOut,
    MLPredictionResultOut,
    MLPredictionSummaryOut,
    MLPredictSummaryOut,
    MLTrainingSummaryOut,
)

router = APIRouter(tags=["ml"])


@router.post("/ml/train", response_model=MLTrainingSummaryOut)
def ml_train(vessel_id: str | None = None) -> MLTrainingSummaryOut:
    return MLTrainingSummaryOut(**train_expected_co2_model(vessel_id=vessel_id))


@router.get("/ml/model-metadata", response_model=MLModelMetadataOut | None)
def ml_model_metadata() -> MLModelMetadataOut | None:
    metadata = load_model_metadata()
    return MLModelMetadataOut(**metadata) if metadata is not None else None


@router.post("/ml/predict", response_model=MLPredictSummaryOut)
def ml_predict(
    vessel_id: str | None = None,
    limit: int = Query(default=100, ge=1, le=5000),
) -> MLPredictSummaryOut:
    return MLPredictSummaryOut(**predict_expected_co2_for_windows(vessel_id=vessel_id, limit=limit))


@router.get("/ml/predictions", response_model=list[MLPredictionResultOut])
def ml_predictions(
    vessel_id: str | None = None,
    classification: str | None = None,
    limit: int = Query(default=100, ge=1, le=5000),
) -> list[MLPredictionResultOut]:
    return [MLPredictionResultOut(**format_prediction_result(row)) for row in get_ml_predictions(vessel_id=vessel_id, classification=classification, limit=limit)]


@router.get("/ml/predictions/latest", response_model=MLPredictionResultOut | None)
def ml_predictions_latest(vessel_id: str | None = None) -> MLPredictionResultOut | None:
    row = get_latest_ml_prediction(vessel_id=vessel_id)
    return MLPredictionResultOut(**format_prediction_result(row)) if row is not None else None


@router.get("/ml/summary", response_model=MLPredictionSummaryOut)
def ml_summary(vessel_id: str | None = None) -> MLPredictionSummaryOut:
    return MLPredictionSummaryOut(**summarize_ml_predictions(vessel_id=vessel_id))
