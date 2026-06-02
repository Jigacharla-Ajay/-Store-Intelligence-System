# PROMPT: Write pytest tests for the GET /stores/{id}/anomalies endpoint.
#         Must cover: queue spike detection, dead zone detection, no anomalies
#         when store is active, stale feed warning, empty anomaly list.
# CHANGES MADE: Added check for anomaly_count field matching list length.
#               Added structured response validation (anomaly_id, type, severity).

"""Tests for GET /stores/{id}/anomalies endpoint."""

import pytest
from tests.conftest import make_event


@pytest.mark.asyncio
async def test_anomalies_empty_store(client):
    """Empty store (no events) should not crash, returns valid response."""
    r = await client.get("/stores/STORE_BLR_002/anomalies")
    assert r.status_code == 200
    d = r.json()
    assert "active_anomalies" in d
    assert "anomaly_count" in d
    assert d["anomaly_count"] == len(d["active_anomalies"])


@pytest.mark.asyncio
async def test_anomalies_response_structure(client):
    """Each anomaly should have required fields."""
    r = await client.get("/stores/STORE_BLR_002/anomalies")
    d = r.json()
    for a in d["active_anomalies"]:
        assert "anomaly_id" in a
        assert "type" in a
        assert "severity" in a
        assert "detected_at" in a
        assert "description" in a
        assert "suggested_action" in a


@pytest.mark.asyncio
async def test_anomalies_dead_zones_detected(client):
    """With no zone visits, dead zone anomalies should be detected."""
    # Ingest one event so feed isn't stale
    events = [make_event(visitor_id="VIS_AZ", event_type="ENTRY")]
    await client.post("/events/ingest", json={"events": events})

    r = await client.get("/stores/STORE_BLR_002/anomalies")
    d = r.json()
    types = [a["type"] for a in d["active_anomalies"]]
    assert "DEAD_ZONE" in types


@pytest.mark.asyncio
async def test_anomalies_severity_values(client):
    """Severity should be one of INFO, WARN, CRITICAL."""
    r = await client.get("/stores/STORE_BLR_002/anomalies")
    d = r.json()
    valid_severities = {"INFO", "WARN", "CRITICAL"}
    for a in d["active_anomalies"]:
        assert a["severity"] in valid_severities


@pytest.mark.asyncio
async def test_anomalies_has_trace_id(client):
    """Response must include trace_id."""
    r = await client.get("/stores/STORE_BLR_002/anomalies")
    d = r.json()
    assert "trace_id" in d
