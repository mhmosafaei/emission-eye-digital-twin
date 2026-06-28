from __future__ import annotations


def test_ingest_enriched_batch(client, enriched_batch: dict) -> None:
    response = client.post("/ingest/enriched-batch", json=enriched_batch)
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "enriched_simulator"
    assert body["received"] == 2
    assert body["stored_records"] == 2
    assert body["stored_feature_rows"] == 2
    assert body["rejected"] == 0


def test_ingest_raw_simulator_batch(client, raw_batch: dict) -> None:
    response = client.post("/ingest/raw-simulator-batch", json=raw_batch)
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "raw_simulator"
    assert body["received"] == 2
    assert body["enriched"] == 2
    assert body["stored_records"] == 2
    assert body["stored_feature_rows"] == 2
    assert body["rejected"] == 0
