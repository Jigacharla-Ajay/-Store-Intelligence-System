# PROMPT: Write pytest tests for the GET /stores/{id}/heatmap endpoint.
#         Must cover: valid response structure, zero visits included,
#         normalized scores (0-100), LOW confidence flag when < 20 sessions.
# CHANGES MADE: Added check that all known zones are always present.
#               Added validation of score bounds.

"""Tests for GET /stores/{id}/heatmap endpoint."""

import pytest
from tests.conftest import make_event


@pytest.mark.asyncio
async def test_heatmap_empty_store(client):
    """Empty store returns all zones with 0 visits."""
    r = await client.get("/stores/STORE_BLR_002/heatmap")
    assert r.status_code == 200
    d = r.json()
    assert len(d["zones"]) == 4  # SKINCARE, MAKEUP, BATH_BODY, BILLING
    for zone in d["zones"]:
        assert zone["visit_count"] == 0
        assert zone["visit_score"] == 0


@pytest.mark.asyncio
async def test_heatmap_low_confidence(client):
    """With < 20 sessions, data_confidence should be LOW."""
    r = await client.get("/stores/STORE_BLR_002/heatmap")
    d = r.json()
    assert d["data_confidence"] == "LOW"


@pytest.mark.asyncio
async def test_heatmap_all_zones_present(client):
    """All known zones must be present even with no visits."""
    r = await client.get("/stores/STORE_BLR_002/heatmap")
    d = r.json()
    zone_ids = [z["zone_id"] for z in d["zones"]]
    assert "SKINCARE" in zone_ids
    assert "MAKEUP" in zone_ids
    assert "BATH_BODY" in zone_ids
    assert "BILLING" in zone_ids


@pytest.mark.asyncio
async def test_heatmap_scores_bounded(client):
    """Visit and dwell scores must be between 0 and 100."""
    r = await client.get("/stores/STORE_BLR_002/heatmap")
    d = r.json()
    for zone in d["zones"]:
        assert 0 <= zone["visit_score"] <= 100
        assert 0 <= zone["dwell_score"] <= 100
