# Architecture — Store Intelligence System
## Purplle Tech Challenge 2026 · Round 2

---

## 1. System Overview

The Store Intelligence System is a four-stage pipeline that transforms raw CCTV footage into actionable retail analytics. The architecture follows a **stream-processing model** with a clear separation between the detection layer (offline/batch or simulated real-time), the event ingest layer, the analytics computation layer, and the serving layer.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          STORE INTELLIGENCE PIPELINE                            │
│                                                                                 │
│  ┌──────────┐    ┌──────────────┐    ┌─────────────┐    ┌────────────────────┐ │
│  │  CCTV    │    │  DETECTION   │    │   EVENT     │    │   INTELLIGENCE     │ │
│  │  Clips   │───▶│  LAYER       │───▶│   STREAM    │───▶│   API              │ │
│  │  (Input) │    │  (CV/ML)     │    │   (JSONL)   │    │   (FastAPI)        │ │
│  └──────────┘    └──────────────┘    └─────────────┘    └────────────────────┘ │
│                                                                    │            │
│                       ┌────────────────────────────────────────────▼──────────┐│
│                       │              LIVE DASHBOARD                            ││
│                       │         (WebSocket / SSE + React)                      ││
│                       └───────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Stage 1 — Detection Layer

### 2.1 Responsibilities

- Process CCTV video clips frame by frame
- Detect persons using an object detection model
- Track persons across frames within a camera view
- Classify direction (entry vs exit) at threshold cameras
- Assign session-scoped visitor tokens via Re-ID
- Classify staff vs customers
- Map persons to store zones using bounding box position
- Emit structured behavioural events

### 2.2 Component Design

```
pipeline/
├── detect.py          ← YOLOv8 detection + frame iteration
├── tracker.py         ← ByteTrack multi-object tracker + Re-ID
├── zone_mapper.py     ← Maps bounding box centroids → zone IDs
├── staff_classifier.py← Uniform-based or VLM-assisted staff detection
├── reentry.py         ← Cross-session Re-ID and REENTRY detection
├── emit.py            ← Event schema construction and JSONL output
└── run.sh             ← One-command pipeline runner
```

### 2.3 Detection Flow

```
Video Frame
    │
    ▼
┌─────────────────────┐
│  YOLOv8 Inference   │  → Bounding boxes, confidence scores
│  (person class only)│
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  ByteTrack          │  → track_id assigned per frame
│  Multi-Object       │
│  Tracker            │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Re-ID Module       │  → visitor_id (persists across sessions)
│  (OSNet embeddings) │    Cosine similarity against gallery
└──────────┬──────────┘
           │
    ┌──────┴──────┐
    │             │
    ▼             ▼
┌────────┐  ┌──────────────┐
│ Entry/ │  │ Zone Mapper  │ → zone_id from store_layout.json
│ Exit   │  │ (centroid    │
│ Logic  │  │  → zone)     │
└────┬───┘  └──────┬───────┘
     │             │
     └──────┬──────┘
            ▼
┌───────────────────────┐
│  Event Emitter        │ → Structured JSONL events
│  (schema validation)  │
└───────────────────────┘
```

### 2.4 Cross-Camera Deduplication

When the entry camera and floor camera fields of view overlap, the same person may be detected in both. Deduplication is handled by:
1. Matching Re-ID embeddings across camera feeds within a 3-second time window
2. Keeping the highest-confidence detection; suppressing duplicates
3. Tagging `camera_id` on all events to support audit

### 2.5 Staff Detection Strategy

- **Primary:** Colour-range detection on uniform (known store uniform colour palette)
- **Fallback:** VLM zone (GPT-4V / Claude Vision) — prompt: "Does this person appear to be retail staff? Look for uniform, name tag, or apron."
- Staff flagged `is_staff=true` on all events; excluded from all customer metrics at API layer

### 2.6 Re-Entry Handling

```
Session State Machine (per visitor_id):
  
  [NEW] ──ENTRY──▶ [ACTIVE] ──EXIT──▶ [EXITED]
                                           │
                      ┌────────────────────┘
                      │  Same Re-ID match within 60s window
                      ▼
                  [REENTRY event emitted]
                  visitor_id preserved (not incremented)
```

Re-entry window is configurable (default 60 seconds). Beyond this window, a new `visitor_id` is assigned.

---

## 3. Stage 2 — Event Stream

### 3.1 Schema

All events conform to the canonical schema:

```json
{
  "event_id": "<uuid-v4>",
  "store_id": "STORE_BLR_002",
  "camera_id": "CAM_ENTRY_01",
  "visitor_id": "VIS_c8a2f1",
  "event_type": "ZONE_DWELL",
  "timestamp": "2026-04-10T14:22:10Z",
  "zone_id": "SKINCARE",
  "dwell_ms": 8400,
  "is_staff": false,
  "confidence": 0.91,
  "metadata": {
    "queue_depth": null,
    "sku_zone": "MOISTURISER",
    "session_seq": 5
  }
}
```

### 3.2 Transport

- **Batch mode:** Detection pipeline writes events to `events.jsonl`; API ingested via `POST /events/ingest`
- **Streaming mode (Part E):** Events pushed to Redis Streams; API consumer reads from stream in near real-time

### 3.3 Event Type Catalogue

| Event | Trigger | Notes |
|-------|---------|-------|
| ENTRY | Inbound threshold crossing | Starts session |
| EXIT | Outbound threshold crossing | Closes session |
| ZONE_ENTER | Person enters named zone | Zone from store_layout.json |
| ZONE_EXIT | Person leaves named zone | |
| ZONE_DWELL | 30+ seconds continuous in zone | Emitted every 30s |
| BILLING_QUEUE_JOIN | Enters billing zone when queue_depth > 0 | Sets queue_depth metadata |
| BILLING_QUEUE_ABANDON | Leaves billing before POS transaction | POS correlation required |
| REENTRY | Same visitor_id after prior EXIT | Re-ID system catches this |

---

## 4. Stage 3 — Intelligence API

### 4.1 Application Architecture

```
app/
├── main.py            ← FastAPI app factory, middleware, lifespan
├── routers/
│   ├── events.py      ← POST /events/ingest
│   ├── metrics.py     ← GET /stores/{id}/metrics
│   ├── funnel.py      ← GET /stores/{id}/funnel
│   ├── heatmap.py     ← GET /stores/{id}/heatmap
│   ├── anomalies.py   ← GET /stores/{id}/anomalies
│   └── health.py      ← GET /health
├── models/
│   ├── event.py       ← Pydantic event schema
│   ├── metrics.py     ← Response models
│   └── db.py          ← SQLAlchemy ORM models
├── services/
│   ├── ingestion.py   ← Validate, dedup, persist events
│   ├── metrics.py     ← Aggregation queries
│   ├── funnel.py      ← Session-based funnel computation
│   ├── heatmap.py     ← Zone frequency normalisation
│   ├── anomalies.py   ← Anomaly detection rules
│   └── health.py      ← Feed staleness checks
├── db/
│   ├── session.py     ← Async SQLAlchemy session factory
│   └── migrations/    ← Alembic migrations
└── middleware/
    ├── logging.py     ← Structured request logging
    └── errors.py      ← Global error handler (no raw tracebacks)
```

### 4.2 Data Layer Architecture

```
┌──────────────────────────────────────────────────────┐
│                   PostgreSQL                          │
│                                                      │
│  events          sessions         pos_transactions   │
│  ─────────       ─────────        ───────────────    │
│  event_id (PK)   session_id (PK)  transaction_id     │
│  store_id        visitor_id       store_id           │
│  visitor_id      store_id         timestamp          │
│  event_type      entry_at         basket_value_inr   │
│  timestamp       exit_at                             │
│  zone_id         is_converted     zone_visits        │
│  dwell_ms        reentry_count    ──────────────     │
│  is_staff                         zone_visit_id      │
│  confidence                       session_id         │
│  metadata (JSONB)                 zone_id            │
│                                   enter_at           │
│                                   exit_at            │
│                                   total_dwell_ms     │
└──────────────────────────────────────────────────────┘
          │                              │
          ▼                              ▼
┌──────────────────┐          ┌────────────────────┐
│  Redis           │          │  Computed Metrics  │
│  ─────────────── │          │  Cache (Redis)     │
│  metric_cache    │          │  TTL: 30 seconds   │
│  anomaly_state   │          └────────────────────┘
│  session_state   │
└──────────────────┘
```

### 4.3 Funnel Computation Logic

```
Session Unit (not raw events):
  
  Total unique visitor sessions (ENTRY events, is_staff=false)
        │
        ▼ (drop-off #1: visitors who only entered, never visited a zone)
  Sessions with at least one ZONE_ENTER event
        │
        ▼ (drop-off #2: browsed but never reached billing)
  Sessions with BILLING_QUEUE_JOIN OR entered billing zone
        │
        ▼ (drop-off #3: reached billing but didn't purchase)
  Sessions matched to a POS transaction (5-min billing window)
  
  Re-entries: REENTRY events increment session_seq but do NOT
  create a new funnel unit — visitor_id deduplication enforced.
```

### 4.4 Anomaly Detection Rules

| Anomaly | Rule | Severity |
|---------|------|----------|
| `QUEUE_SPIKE` | `queue_depth > 5` for > 3 minutes | WARN → CRITICAL if > 10 |
| `CONVERSION_DROP` | Conversion rate < 70% of 7-day rolling average | WARN |
| `DEAD_ZONE` | No ZONE_ENTER events in any zone for 30+ min during open hours | INFO |
| `STALE_FEED` | No events received from a camera for > 10 min | WARN |
| `ABANDONMENT_SPIKE` | Queue abandonment > 30% of billing entries | WARN |

### 4.5 Request Flow

```
HTTP Request
     │
     ▼
FastAPI Router
     │
     ├── Middleware: trace_id injection, structured logging
     │
     ▼
Service Layer (business logic)
     │
     ├── Redis cache check (for GET endpoints)
     │       └── cache hit → return immediately
     │
     ▼
Database (async SQLAlchemy)
     │
     ├── Query execution
     │
     ▼
Response Model (Pydantic)
     │
     ▼
Structured JSON Response
```

---

## 5. Stage 4 — Live Dashboard

### 5.1 Architecture

```
Detection Pipeline (real-time or simulated)
     │
     │ JSONL events → POST /events/ingest
     ▼
FastAPI Backend
     │
     │ WebSocket / SSE at ws://localhost:8000/ws/stores/{id}
     ▼
React Dashboard (port 3000)
     │
     ├── Live visitor count (updates every event)
     ├── Conversion rate gauge (updates every transaction correlation)
     ├── Zone heatmap (updates every ZONE_DWELL)
     └── Anomaly banner (updates on anomaly state change)
```

---

## 6. Infrastructure Architecture (Docker Compose)

```yaml
services:
  db:
    image: postgres:16
    
  redis:
    image: redis:7-alpine
    
  api:
    build: ./app
    depends_on: [db, redis]
    ports: ["8000:8000"]
    
  dashboard:         # Part E
    build: ./dashboard
    ports: ["3000:3000"]
    
  pipeline:          # Optional: run detection as a service
    build: ./pipeline
    depends_on: [api]
    profiles: ["detection"]
```

---

## 7. AI-Assisted Decisions

### 7.1 Event Schema Design
Claude was used to evaluate whether `visitor_id` should be stable across re-entries or reset. Claude suggested preserving the same `visitor_id` and emitting a REENTRY event — which was adopted because it enables accurate funnel deduplication without losing the trajectory context.

### 7.2 Detection Model Selection
GPT-4 was queried for a comparison of YOLOv8 vs RT-DETR for retail CCTV scenarios. The output correctly identified YOLOv8's speed advantage at 15fps but noted RT-DETR's superior accuracy on partially occluded detections. The final decision (YOLOv8 with ByteTrack) weighted inference speed over peak accuracy, which was a deliberate override of the AI recommendation given the real-time constraint.

### 7.3 Session Deduplication
An LLM was used to prototype the billing-zone-to-POS-transaction correlation logic (5-minute window). The initial suggestion used exact timestamp matching, which was corrected to a range query with configurable window size.

---

## 8. Scalability Considerations

The current implementation targets 5 stores during the challenge. For production at 40 stores:

- Replace SQLite with PostgreSQL + TimescaleDB for time-series metric partitioning
- Add Kafka between detection pipeline and ingest API to buffer event bursts
- Horizontal scaling of the FastAPI service behind a load balancer
- Partition `events` table by `store_id` + `date` for query performance
- Move anomaly detection to a separate Celery worker to avoid blocking the API
