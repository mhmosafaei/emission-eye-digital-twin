from __future__ import annotations

from fastapi import APIRouter, Query

from app.schemas import PerformanceWindowOut, WindowBuildRequest, WindowBuildSummary
from app.windowing import create_performance_windows_from_feature_rows
from app.repositories import count_performance_windows, get_performance_windows

router = APIRouter(tags=["windows"])


@router.post("/windows/build", response_model=WindowBuildSummary)
def build_windows(request: WindowBuildRequest) -> WindowBuildSummary:
    windows = create_performance_windows_from_feature_rows(vessel_id=request.vessel_id, window_minutes=request.window_minutes)
    valid_windows = sum(int(window.is_valid_window) for window in windows)
    return WindowBuildSummary(
        windows_created=len(windows),
        valid_windows=valid_windows,
        invalid_windows=len(windows) - valid_windows,
    )


@router.get("/windows", response_model=list[PerformanceWindowOut])
def windows(
    vessel_id: str | None = None,
    state_bucket: str | None = None,
    valid_only: bool | None = None,
    limit: int = Query(default=100, ge=1, le=5000),
) -> list[PerformanceWindowOut]:
    return get_performance_windows(vessel_id=vessel_id, state_bucket=state_bucket, valid_only=valid_only, limit=limit)


@router.get("/windows/count")
def windows_count(vessel_id: str | None = None) -> dict:
    return {"count": count_performance_windows(vessel_id=vessel_id)}
