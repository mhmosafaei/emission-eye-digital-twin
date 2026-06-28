from __future__ import annotations

from fastapi import APIRouter, Query

from app.analytics import (
    get_baseline_trend,
    get_worst_baseline_windows,
    rank_vessels_by_baseline_performance,
    summarize_possible_causes,
    summarize_vessel_baseline_performance,
)
from app.schemas import (
    BaselineTrendOut,
    FleetRankingOut,
    PossibleCauseSummaryOut,
    VesselBaselineSummaryOut,
    WorstBaselineWindowOut,
)

router = APIRouter(tags=["analytics"])


@router.get("/analytics/vessel-summary", response_model=VesselBaselineSummaryOut)
def analytics_vessel_summary(vessel_id: str | None = None) -> VesselBaselineSummaryOut:
    return VesselBaselineSummaryOut(**summarize_vessel_baseline_performance(vessel_id=vessel_id))


@router.get("/analytics/worst-windows", response_model=list[WorstBaselineWindowOut])
def analytics_worst_windows(
    vessel_id: str | None = None,
    limit: int = Query(default=10, ge=1, le=500),
) -> list[WorstBaselineWindowOut]:
    return [WorstBaselineWindowOut(**row) for row in get_worst_baseline_windows(vessel_id=vessel_id, limit=limit)]


@router.get("/analytics/trend", response_model=BaselineTrendOut)
def analytics_trend(
    vessel_id: str | None = None,
    state_bucket: str | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
) -> BaselineTrendOut:
    return BaselineTrendOut(**get_baseline_trend(vessel_id=vessel_id, bucket=state_bucket, limit=limit))


@router.get("/analytics/causes", response_model=PossibleCauseSummaryOut)
def analytics_causes(vessel_id: str | None = None) -> PossibleCauseSummaryOut:
    return PossibleCauseSummaryOut(**summarize_possible_causes(vessel_id=vessel_id))


@router.get("/analytics/fleet-ranking", response_model=list[FleetRankingOut])
def analytics_fleet_ranking() -> list[FleetRankingOut]:
    return [FleetRankingOut(**row) for row in rank_vessels_by_baseline_performance()]
