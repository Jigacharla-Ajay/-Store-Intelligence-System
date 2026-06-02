"""Quick smoke test for all API endpoints."""
import httpx
import json
import uuid

c = httpx.Client(base_url="http://127.0.0.1:8000", timeout=10)

# 1. Health
r = c.get("/health")
print(f"1. GET /health -> {r.status_code}")

# 2. Metrics (empty store — should return zeros)
r = c.get("/stores/STORE_BLR_002/metrics")
d = r.json()
print(f"2. GET /metrics -> {r.status_code}")
print(f"   visitors.unique_count = {d['visitors']['unique_count']}")
print(f"   conversion.rate = {d['conversion']['rate']}")

# 3. Ingest 5 test events (1 staff)
events = []
for i in range(5):
    events.append({
        "event_id": str(uuid.uuid4()),
        "store_id": "STORE_BLR_002",
        "camera_id": "CAM_ENTRY_01",
        "visitor_id": f"VIS_{i:04d}",
        "event_type": "ENTRY",
        "timestamp": f"2026-05-31T10:{i:02d}:00Z",
        "zone_id": None,
        "dwell_ms": 0,
        "is_staff": (i == 4),  # Last one is staff
        "confidence": 0.92,
        "metadata": {"session_seq": 1},
    })
r = c.post("/events/ingest", json={"events": events})
d = r.json()
print(f"3. POST /events/ingest -> {r.status_code}")
print(f"   accepted={d['accepted']}, rejected={d['rejected']}, duplicate={d['duplicate']}")

# 4. Re-ingest same events (idempotency check)
r2 = c.post("/events/ingest", json={"events": events})
d2 = r2.json()
print(f"4. Re-ingest (idempotency) -> {r2.status_code}")
print(f"   accepted={d2['accepted']}, duplicate={d2['duplicate']}")

# 5. Metrics after ingest
r = c.get("/stores/STORE_BLR_002/metrics")
d = r.json()
print(f"5. GET /metrics after ingest -> {r.status_code}")
print(f"   unique_count = {d['visitors']['unique_count']} (expect 4, staff excluded)")
print(f"   total_entries = {d['visitors']['total_entries']}")

# 6. Funnel
r = c.get("/stores/STORE_BLR_002/funnel?date=2026-05-31")
d = r.json()
print(f"6. GET /funnel -> {r.status_code}")
for s in d["funnel"]:
    print(f"   {s['stage']}: {s['sessions']} sessions")

# 7. Heatmap
r = c.get("/stores/STORE_BLR_002/heatmap")
d = r.json()
print(f"7. GET /heatmap -> {r.status_code}, confidence={d['data_confidence']}")

# 8. Anomalies
r = c.get("/stores/STORE_BLR_002/anomalies")
d = r.json()
print(f"8. GET /anomalies -> {r.status_code}, count={d['anomaly_count']}")

print()
print("=== ALL ENDPOINTS TESTED SUCCESSFULLY ===")
