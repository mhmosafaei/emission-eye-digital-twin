from __future__ import annotations

from app.repositories import count_records, create_enriched_batch, get_latest_record, get_records


def test_records_count(temp_db_url: str, enriched_batch: dict) -> None:
    summary = create_enriched_batch(enriched_batch)
    assert summary["stored_records"] == 2
    assert count_records() == 2


def test_latest_record(temp_db_url: str, enriched_batch: dict) -> None:
    create_enriched_batch(enriched_batch)
    latest = get_latest_record()
    assert latest is not None
    assert latest.timestamp_utc == "2026-06-28T10:12:00Z"


def test_records_query(temp_db_url: str, enriched_batch: dict) -> None:
    create_enriched_batch(enriched_batch)
    records = get_records(vessel_id="NODE-BALTIC-0001", valid_for_training=True)
    assert len(records) == 1
    assert records[0].vessel_id == "NODE-BALTIC-0001"
