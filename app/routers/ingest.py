from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.repositories import create_enriched_batch, create_raw_batch
from app.schemas import EnrichedBatchIn, IngestSummary

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("/enriched-batch", response_model=IngestSummary)
def ingest_enriched_batch(batch: EnrichedBatchIn, db: Session = Depends(get_db)) -> IngestSummary:
    payload = _model_to_dict(batch)
    summary = create_enriched_batch(payload, session=db)
    db.commit()
    return IngestSummary(
        source="enriched_simulator",
        batch_id=summary["batch_id"],
        received=summary["received"],
        stored_records=summary["stored_records"],
        stored_feature_rows=summary["stored_feature_rows"],
        rejected=summary["rejected"],
    )


@router.post("/raw-simulator-batch", response_model=IngestSummary)
def ingest_raw_simulator_batch(batch: EnrichedBatchIn, db: Session = Depends(get_db)) -> IngestSummary:
    payload = _model_to_dict(batch)
    summary = create_raw_batch(payload, session=db)
    db.commit()
    return IngestSummary(
        source="raw_simulator",
        batch_id=summary["batch_id"],
        received=summary["received"],
        enriched=summary["enriched"],
        stored_records=summary["stored_records"],
        stored_feature_rows=summary["stored_feature_rows"],
        rejected=summary["rejected"],
    )


def _model_to_dict(model: Any) -> dict:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()
