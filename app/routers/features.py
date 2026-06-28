from __future__ import annotations

from fastapi import APIRouter, Query

from app.repositories import count_feature_rows, get_feature_rows
from app.schemas import FeatureRowOut

router = APIRouter(tags=["features"])


@router.get("/features", response_model=list[FeatureRowOut])
def features(
    vessel_id: str | None = None,
    state_bucket: str | None = None,
    valid_for_training: bool | None = None,
    limit: int = Query(default=1000, ge=1, le=10000),
) -> list[FeatureRowOut]:
    return get_feature_rows(
        vessel_id=vessel_id,
        state_bucket=state_bucket,
        valid_for_training=valid_for_training,
        limit=limit,
    )


@router.get("/features/count")
def features_count(vessel_id: str | None = None) -> dict:
    return {"count": count_feature_rows(vessel_id=vessel_id)}
