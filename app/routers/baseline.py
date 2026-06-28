from __future__ import annotations

from fastapi import APIRouter, Query

from app.baseline import run_baseline_comparisons_with_options
from app.repositories import (
    get_baseline_comparisons,
    get_baseline_summary,
    get_latest_baseline_comparison,
    get_latest_completed_baseline_comparison,
)
from app.schemas import BaselineCompareRequest, BaselineCompareSummary, BaselineComparisonOut, BaselineSummaryOut

router = APIRouter(tags=["baseline"])


@router.post("/baseline/compare", response_model=BaselineCompareSummary)
def baseline_compare(request: BaselineCompareRequest) -> BaselineCompareSummary:
    comparisons = run_baseline_comparisons_with_options(
        vessel_id=request.vessel_id,
        limit=request.limit,
        valid_windows_only=request.valid_windows_only,
    )
    counts = {
        "better": 0,
        "normal": 0,
        "worse": 0,
        "insufficient_history": 0,
        "invalid_window": 0,
    }
    for comparison in comparisons:
        counts[comparison.classification] = counts.get(comparison.classification, 0) + 1
    return BaselineCompareSummary(comparisons_created=len(comparisons), **counts)


@router.get("/baseline/comparisons", response_model=list[BaselineComparisonOut])
def baseline_comparisons(
    vessel_id: str | None = None,
    classification: str | None = None,
    state_bucket: str | None = None,
    status: str | None = None,
    valid_only: bool = False,
    limit: int = Query(default=100, ge=1, le=5000),
) -> list[BaselineComparisonOut]:
    return get_baseline_comparisons(
        vessel_id=vessel_id,
        classification=classification,
        state_bucket=state_bucket,
        status=status,
        valid_only=valid_only,
        limit=limit,
    )


@router.get("/baseline/latest", response_model=BaselineComparisonOut | None)
def baseline_latest(vessel_id: str | None = None) -> BaselineComparisonOut | None:
    return get_latest_baseline_comparison(vessel_id=vessel_id)


@router.get("/baseline/latest-completed", response_model=BaselineComparisonOut | None)
def baseline_latest_completed(vessel_id: str | None = None) -> BaselineComparisonOut | None:
    return get_latest_completed_baseline_comparison(vessel_id=vessel_id)


@router.get("/baseline/summary", response_model=BaselineSummaryOut)
def baseline_summary(vessel_id: str | None = None) -> BaselineSummaryOut:
    return BaselineSummaryOut(**get_baseline_summary(vessel_id=vessel_id))
