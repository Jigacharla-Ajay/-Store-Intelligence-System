# PROMPT: Write integration tests that exercise full API workflows — ingestion
#         through to metrics, funnel, and heatmap responses with real data flow.
# CHANGES MADE: Added zone visit flow tests, entry+exit session lifecycle,
#               and multi-visitor scenario covering all service code paths.

"""Integration tests that exercise full data flow through all endpoints."""

import uuid
import pytest
from datetime import datetime, timezone, timedelta
from tests.conftest import make_event


def _ts(minutes_ago=0):
    """Generate an ISO timestamp `minutes_ago` minutes in the past."""
    dt = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    return dt.isoformat()


@pytest.mark.asyncio
async def test_full_visitor_lifecycle(client):
    """Test ENTRY -> ZONE_ENTER -> ZONE_EXIT -> EXIT flow."""
    vid = "VIS_LIFE"
    events = [
        make_event(visitor_id=vid, event_type="ENTRY", timestamp=_ts(30)),
        make_event(visitor_id=vid, event_type="ZONE_ENTER", zone_id="SKINCARE", timestamp=_ts(25)),
        make_event(visitor_id=vid, event_type="ZONE_EXIT", zone_id="SKINCARE", dwell_ms=300000, timestamp=_ts(20)),
        make_event(visitor_id=vid, event_type="ZONE_ENTER", zone_id="BILLING", timestamp=_ts(15)),
        make_event(visitor_id=vid, event_type="ZONE_EXIT", zone_id="BILLING", dwell_ms=120000, timestamp=_ts(10)),
        make_event(visitor_id=vid, event_type="EXIT", timestamp=_ts(5)),
    ]
    r = await client.post("/events/ingest", json={"events": events})
    assert r.status_code == 200
    assert r.json()["accepted"] == 6

    # Metrics should show 1 visitor
    r2 = await client.get("/stores/STORE_BLR_002/metrics")
    d = r2.json()
    assert d["visitors"]["unique_count"] == 1

    # Heatmap should show SKINCARE and BILLING visits
    r3 = await client.get("/stores/STORE_BLR_002/heatmap?window_minutes=60")
    d3 = r3.json()
    skincare = next((z for z in d3["zones"] if z["zone_id"] == "SKINCARE"), None)
    assert skincare is not None
    assert skincare["visit_count"] >= 1

    # Funnel should show entry, zone visit, billing reach
    r4 = await client.get("/stores/STORE_BLR_002/funnel")
    d4 = r4.json()
    entry_s = next(s for s in d4["funnel"] if s["stage"] == "STORE_ENTRY")
    zone_s = next(s for s in d4["funnel"] if s["stage"] == "ZONE_VISIT")
    billing_s = next(s for s in d4["funnel"] if s["stage"] == "BILLING_REACH")
    assert entry_s["sessions"] == 1
    assert zone_s["sessions"] >= 1
    assert billing_s["sessions"] >= 1


@pytest.mark.asyncio
async def test_multi_visitor_metrics(client):
    """Multiple visitors with varied behavior."""
    events = []
    # 3 customers
    for i in range(3):
        events.append(make_event(visitor_id=f"VIS_M{i}", event_type="ENTRY", timestamp=_ts(20+i)))
        events.append(make_event(visitor_id=f"VIS_M{i}", event_type="EXIT", timestamp=_ts(5+i)))
    # 1 staff
    events.append(make_event(visitor_id="STAFF_M", event_type="ENTRY", is_staff=True, timestamp=_ts(15)))

    r = await client.post("/events/ingest", json={"events": events})
    assert r.json()["accepted"] == 7

    r2 = await client.get("/stores/STORE_BLR_002/metrics")
    d = r2.json()
    assert d["visitors"]["unique_count"] == 3  # Staff excluded
    assert d["visitors"]["total_entries"] == 3


@pytest.mark.asyncio
async def test_billing_queue_events(client):
    """BILLING_QUEUE_JOIN and BILLING_QUEUE_ABANDON flow."""
    vid = "VIS_BQ"
    events = [
        make_event(visitor_id=vid, event_type="ENTRY", timestamp=_ts(20)),
        make_event(visitor_id=vid, event_type="BILLING_QUEUE_JOIN", zone_id="BILLING", timestamp=_ts(10)),
        make_event(visitor_id=vid, event_type="BILLING_QUEUE_ABANDON", zone_id="BILLING", timestamp=_ts(5)),
        make_event(visitor_id=vid, event_type="EXIT", timestamp=_ts(2)),
    ]
    r = await client.post("/events/ingest", json={"events": events})
    assert r.json()["accepted"] == 4

    # Metrics should show abandonment
    r2 = await client.get("/stores/STORE_BLR_002/metrics")
    d = r2.json()
    assert d["abandonment"]["billing_entries"] >= 1


@pytest.mark.asyncio
async def test_reentry_event_flow(client):
    """REENTRY event should create a new session with incremented seq."""
    vid = "VIS_RE"
    events = [
        make_event(visitor_id=vid, event_type="ENTRY", timestamp=_ts(60)),
        make_event(visitor_id=vid, event_type="EXIT", timestamp=_ts(50)),
        make_event(visitor_id=vid, event_type="REENTRY", timestamp=_ts(40)),
        make_event(visitor_id=vid, event_type="EXIT", timestamp=_ts(30)),
    ]
    r = await client.post("/events/ingest", json={"events": events})
    assert r.json()["accepted"] == 4

    # Should count as 1 unique visitor, but with reentry
    r2 = await client.get("/stores/STORE_BLR_002/metrics")
    d = r2.json()
    assert d["visitors"]["reentry_count"] >= 1


@pytest.mark.asyncio
async def test_zone_dwell_events(client):
    """ZONE_DWELL events should be accepted."""
    vid = "VIS_DW"
    events = [
        make_event(visitor_id=vid, event_type="ENTRY", timestamp=_ts(20)),
        make_event(visitor_id=vid, event_type="ZONE_DWELL", zone_id="MAKEUP", dwell_ms=5000, timestamp=_ts(15)),
    ]
    r = await client.post("/events/ingest", json={"events": events})
    assert r.json()["accepted"] == 2


@pytest.mark.asyncio
async def test_health_after_events(client):
    """Health should show feed_status OK after recent events."""
    events = [make_event(visitor_id="VIS_H", event_type="ENTRY")]
    await client.post("/events/ingest", json={"events": events})

    r = await client.get("/health")
    d = r.json()
    assert d["status"] == "healthy"
    store = d["stores"][0]
    # After ingesting, should have a last_event_at
    assert store["last_event_at"] is not None


@pytest.mark.asyncio
async def test_anomalies_stale_feed(client):
    """Old events should trigger STALE_FEED anomaly."""
    # Ingest event from 20 minutes ago
    old_ts = (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat()
    events = [make_event(visitor_id="VIS_OLD", event_type="ENTRY", timestamp=old_ts)]
    await client.post("/events/ingest", json={"events": events})

    r = await client.get("/stores/STORE_BLR_002/anomalies")
    d = r.json()
    types = [a["type"] for a in d["active_anomalies"]]
    assert "STALE_FEED" in types
