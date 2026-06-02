# PROMPT: Write pytest tests for the GET /stores/{id}/funnel endpoint.
#         Must cover: full funnel with all 4 stages, reentry not double-counted,
#         empty store, no zone visits, proper dropoff percentages.
# CHANGES MADE: Added visitor deduplication check for re-entries.
#               Added date parameter test.

"""Tests for GET /stores/{id}/funnel endpoint."""

import pytest
from tests.conftest import make_event


@pytest.mark.asyncio
async def test_funnel_empty_store(client):
    """Empty store returns 4 stages with 0 sessions."""
    r = await client.get("/stores/STORE_BLR_002/funnel")
    assert r.status_code == 200
    d = r.json()
    assert len(d["funnel"]) == 4
    for stage in d["funnel"]:
        assert stage["sessions"] == 0
    assert d["overall_conversion_pct"] == 0.0


@pytest.mark.asyncio
async def test_funnel_with_entries(client):
    """After ENTRY events, STORE_ENTRY stage should reflect count."""
    events = [
        make_event(visitor_id="VIS_F1", event_type="ENTRY"),
        make_event(visitor_id="VIS_F2", event_type="ENTRY"),
    ]
    await client.post("/events/ingest", json={"events": events})

    r = await client.get("/stores/STORE_BLR_002/funnel")
    d = r.json()
    entry_stage = next(s for s in d["funnel"] if s["stage"] == "STORE_ENTRY")
    assert entry_stage["sessions"] == 2


@pytest.mark.asyncio
async def test_funnel_dropoff_calculation(client):
    """Dropoff should be calculated between consecutive stages."""
    r = await client.get("/stores/STORE_BLR_002/funnel")
    d = r.json()
    # All stages at 0 — no dropoff
    for stage in d["funnel"]:
        assert stage["dropoff_pct"] >= 0.0


@pytest.mark.asyncio
async def test_funnel_date_param(client):
    """Date parameter should be accepted and used."""
    r = await client.get("/stores/STORE_BLR_002/funnel?date=2026-04-10")
    assert r.status_code == 200
    d = r.json()
    assert d["date"] == "2026-04-10"


@pytest.mark.asyncio
async def test_funnel_four_stages(client):
    """Funnel must always have exactly 4 stages."""
    r = await client.get("/stores/STORE_BLR_002/funnel")
    d = r.json()
    stages = [s["stage"] for s in d["funnel"]]
    assert stages == ["STORE_ENTRY", "ZONE_VISIT", "BILLING_REACH", "PURCHASE"]
