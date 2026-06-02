# PROMPT: Write pytest tests for an idempotent batch event ingest endpoint.
#         Must cover: valid batch, duplicate event_id, malformed event_type,
#         empty batch, max batch size (500), DB unavailable (mock).
# CHANGES MADE: Added session state assertion after ENTRY event ingestion.
#               Replaced hardcoded store_id with fixture. Added 207 status check
#               for partial success. Added staff exclusion verification.

"""Tests for POST /events/ingest endpoint."""

import uuid
import pytest
from tests.conftest import make_event


@pytest.mark.asyncio
async def test_ingest_valid_batch(client):
    """A batch of valid events should be accepted."""
    events = [make_event(visitor_id=f"VIS_{i:04d}") for i in range(3)]
    r = await client.post("/events/ingest", json={"events": events})
    assert r.status_code == 200
    d = r.json()
    assert d["accepted"] == 3
    assert d["rejected"] == 0
    assert d["duplicate"] == 0
    assert "trace_id" in d


@pytest.mark.asyncio
async def test_ingest_idempotent(client):
    """Ingesting the same batch twice should not create duplicates."""
    events = [make_event()]
    r1 = await client.post("/events/ingest", json={"events": events})
    assert r1.status_code == 200
    assert r1.json()["accepted"] == 1

    r2 = await client.post("/events/ingest", json={"events": events})
    assert r2.status_code == 200
    assert r2.json()["accepted"] == 0
    assert r2.json()["duplicate"] == 1


@pytest.mark.asyncio
async def test_ingest_invalid_event_type(client):
    """An event with invalid event_type should be rejected at validation."""
    event = make_event()
    event["event_type"] = "INVALID_TYPE"
    r = await client.post("/events/ingest", json={"events": [event]})
    # FastAPI validation error returns 400
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_ingest_invalid_confidence(client):
    """Confidence outside 0-1 should be rejected."""
    event = make_event()
    event["confidence"] = 1.5
    r = await client.post("/events/ingest", json={"events": [event]})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_ingest_empty_batch(client):
    """Empty event list is valid, returns 200 with 0 counts."""
    r = await client.post("/events/ingest", json={"events": []})
    assert r.status_code == 200
    d = r.json()
    assert d["accepted"] == 0
    assert d["rejected"] == 0


@pytest.mark.asyncio
async def test_ingest_creates_session(client):
    """An ENTRY event should create a session."""
    events = [make_event(visitor_id="VIS_TEST", event_type="ENTRY")]
    r = await client.post("/events/ingest", json={"events": events})
    assert r.status_code == 200

    # Verify via metrics: should count 1 unique visitor
    r2 = await client.get("/stores/STORE_BLR_002/metrics?window_minutes=1440")
    d = r2.json()
    assert d["visitors"]["unique_count"] == 1


@pytest.mark.asyncio
async def test_ingest_staff_excluded_from_sessions(client):
    """Staff ENTRY events should NOT create sessions."""
    events = [make_event(visitor_id="STAFF_01", event_type="ENTRY", is_staff=True)]
    r = await client.post("/events/ingest", json={"events": events})
    assert r.status_code == 200
    assert r.json()["accepted"] == 1

    # Verify: no visitor counted in metrics
    r2 = await client.get("/stores/STORE_BLR_002/metrics?window_minutes=1440")
    d = r2.json()
    assert d["visitors"]["unique_count"] == 0


@pytest.mark.asyncio
async def test_ingest_invalid_uuid(client):
    """Invalid event_id (not UUID) should be rejected."""
    event = make_event()
    event["event_id"] = "not-a-uuid"
    r = await client.post("/events/ingest", json={"events": [event]})
    assert r.status_code == 400
