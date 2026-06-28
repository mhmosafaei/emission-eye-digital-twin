from __future__ import annotations

from fastapi import APIRouter, Query

from app.repositories import count_records, get_latest_record, get_records, get_state_bucket_counts
from app.schemas import RecordOut

router = APIRouter(tags=["records"])


@router.get("/records/latest", response_model=RecordOut | None)
def latest_record(vessel_id: str | None = None) -> RecordOut | None:
    return get_latest_record(vessel_id=vessel_id)


@router.get("/records", response_model=list[RecordOut])
def records(
    vessel_id: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    state_bucket: str | None = None,
    valid_for_training: bool | None = None,
    limit: int = Query(default=100, ge=1, le=5000),
) -> list[RecordOut]:
    return get_records(
        vessel_id=vessel_id,
        start_time=start_time,
        end_time=end_time,
        state_bucket=state_bucket,
        valid_for_training=valid_for_training,
        limit=limit,
    )


@router.get("/records/count")
def records_count(vessel_id: str | None = None) -> dict:
    return {"count": count_records(vessel_id=vessel_id)}


@router.get("/state-buckets")
def state_buckets() -> list[dict]:
    return get_state_bucket_counts()
