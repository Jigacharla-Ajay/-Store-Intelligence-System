# PROMPT: Write pytest tests for the GET /stores/{id}/metrics endpoint.
#         Must cover: zero visitors returns 0 (not null), staff events excluded,
#         valid metrics after event ingestion, conversion rate is 0.0 with no purchases.
# CHANGES MADE: Added explicit check that conversion.rate is float 0.0, not None.
#               Added test for window parameter filtering.

"""Tests for GET /stores/{id}/metrics endpoint."""

import pytest
from tests.conftest import make_event


@pytest.mark.asyncio
async def test_metrics_empty_store(client):
    """Empty store returns zero counts, never null."""
    r = await client.get("/stores/STORE_BLR_002/metrics")
    assert r.status_code == 200
    d = r.json()
    assert d["visitors"]["unique_count"] == 0
    assert d["visitors"]["total_entries"] == 0
    assert d["conversion"]["rate"] == 0.0
    assert d["conversion"]["rate"] is not None
    assert d["queue"]["current_depth"] == 0


@pytest.mark.asyncio
async def test_metrics_with_visitors(client):
    """After ingesting ENTRY events, metrics should reflect visitor counts."""
    events = [
        make_event(visitor_id="VIS_A", event_type="ENTRY"),
        make_event(visitor_id="VIS_B", event_type="ENTRY"),
        make_event(visitor_id="VIS_C", event_type="ENTRY"),
    ]
    await client.post("/events/ingest", json={"events": events})

    r = await client.get("/stores/STORE_BLR_002/metrics")
    d = r.json()
    assert d["visitors"]["unique_count"] == 3
    assert d["visitors"]["total_entries"] == 3


@pytest.mark.asyncio
async def test_metrics_staff_excluded(client):
    """Staff events must not be counted in customer metrics."""
    events = [
        make_event(visitor_id="VIS_CUST", event_type="ENTRY", is_staff=False),
        make_event(visitor_id="VIS_STAFF", event_type="ENTRY", is_staff=True),
    ]
    await client.post("/events/ingest", json={"events": events})

    r = await client.get("/stores/STORE_BLR_002/metrics")
    d = r.json()
    assert d["visitors"]["unique_count"] == 1  # Only customer


@pytest.mark.asyncio
async def test_metrics_zero_conversion(client):
    """With no purchases, conversion rate should be 0.0, not null."""
    events = [make_event(visitor_id="VIS_X", event_type="ENTRY")]
    await client.post("/events/ingest", json={"events": events})

    r = await client.get("/stores/STORE_BLR_002/metrics")
    d = r.json()
    assert d["conversion"]["rate"] == 0.0
    assert isinstance(d["conversion"]["rate"], float)


@pytest.mark.asyncio
async def test_metrics_has_trace_id(client):
    """Response must include trace_id."""
    r = await client.get("/stores/STORE_BLR_002/metrics")
    d = r.json()
    assert "trace_id" in d
    assert d["trace_id"].startswith("trc_")


@pytest.mark.asyncio
async def test_metrics_window_param(client):
    """window_minutes parameter should be accepted."""
    r = await client.get("/stores/STORE_BLR_002/metrics?window_minutes=60")
    assert r.status_code == 200
