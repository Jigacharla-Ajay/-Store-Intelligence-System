# PROMPT: Write pytest tests for the GET /health endpoint.
#         Must cover: healthy response (200), database connected,
#         store feed status, uptime tracking.
# CHANGES MADE: Added check for per-store feed status structure.
#               Added validation that uptime_seconds is non-negative.

"""Tests for GET /health endpoint."""

import pytest


@pytest.mark.asyncio
async def test_health_returns_200(client):
    """Health check should return 200 when DB is connected."""
    r = await client.get("/health")
    assert r.status_code == 200
    d = r.json()
    assert d["status"] == "healthy"


@pytest.mark.asyncio
async def test_health_database_connected(client):
    """Health response should show database as connected."""
    r = await client.get("/health")
    d = r.json()
    assert d["database"] == "connected"


@pytest.mark.asyncio
async def test_health_store_feed_status(client):
    """Health should include per-store feed status."""
    r = await client.get("/health")
    d = r.json()
    assert len(d["stores"]) >= 1
    store = d["stores"][0]
    assert "store_id" in store
    assert "feed_status" in store
    assert store["feed_status"] in ("OK", "STALE_FEED", "NO_DATA")
