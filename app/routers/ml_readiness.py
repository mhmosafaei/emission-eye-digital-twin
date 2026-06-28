from __future__ import annotations

from fastapi import APIRouter

from app.ml_readiness import (
    summarize_ml_readiness,
    summarize_state_bucket_repetition,
    summarize_vessel_training_coverage,
    summarize_window_coverage,
)
from app.schemas import (
    MLReadinessSummaryOut,
    StateBucketCoverageSummaryOut,
    VesselTrainingCoverageOut,
    WindowCoverageSummaryOut,
)

router = APIRouter(tags=["ml-readiness"])


@router.get("/ml-readiness/summary", response_model=MLReadinessSummaryOut)
def ml_readiness_summary() -> MLReadinessSummaryOut:
    return MLReadinessSummaryOut(**summarize_ml_readiness())


@router.get("/ml-readiness/window-coverage", response_model=WindowCoverageSummaryOut)
def ml_readiness_window_coverage() -> WindowCoverageSummaryOut:
    return WindowCoverageSummaryOut(**summarize_window_coverage())


@router.get("/ml-readiness/state-buckets", response_model=StateBucketCoverageSummaryOut)
def ml_readiness_state_buckets() -> StateBucketCoverageSummaryOut:
    return StateBucketCoverageSummaryOut(**summarize_state_bucket_repetition())


@router.get("/ml-readiness/vessels", response_model=list[VesselTrainingCoverageOut])
def ml_readiness_vessels() -> list[VesselTrainingCoverageOut]:
    return [VesselTrainingCoverageOut(**row) for row in summarize_vessel_training_coverage()]
