# Requirements — Store Intelligence System
## Purplle Tech Challenge 2026 · Round 2 | Brigade Road, Bangalore

---

## 1. Project Overview

Build an end-to-end **Store Intelligence Pipeline** for Apex Retail / Purplle's Brigade Road Bangalore store (Store ID: `ST1008`). The system ingests raw CCTV footage, runs computer-vision-based detection and tracking, emits structured behavioural events, and exposes a production-grade REST API that computes real-time store analytics — culminating in a live dashboard.

**North Star Metric:** `Offline Store Conversion Rate = Unique purchasing visitors ÷ Total unique visitors`

---

## 2. Functional Requirements

### 2.1 Detection Pipeline (Part A — 30 pts)

| ID | Requirement |
|----|-------------|
| FR-D01 | Process CCTV clips from 3 camera angles: Entry/Exit, Main Floor, Billing Area |
| FR-D02 | Detect and count individual persons (not groups) crossing the entry threshold |
| FR-D03 | Assign a unique `visitor_id` token per visit session using Re-ID |
| FR-D04 | Determine direction: inbound (ENTRY) vs outbound (EXIT) |
| FR-D05 | Detect and flag store staff (`is_staff=true`) and exclude from customer metrics |
| FR-D06 | Handle group entry (2–4 simultaneous people) — emit individual ENTRY events |
| FR-D07 | Handle re-entry: same physical person after EXIT → emit REENTRY event, not new ENTRY |
| FR-D08 | Track zone transitions: ZONE_ENTER, ZONE_EXIT, ZONE_DWELL (every 30s) |
| FR-D09 | Detect billing queue: BILLING_QUEUE_JOIN with `queue_depth` metadata |
| FR-D10 | Detect queue abandonment: BILLING_QUEUE_ABANDON before POS transaction |
| FR-D11 | Handle partial occlusion gracefully — degrade confidence, never silently drop |
| FR-D12 | Cross-camera deduplication (entry/floor camera overlap) |
| FR-D13 | Correlate visitor sessions with POS transaction window (5-min billing zone window) |
| FR-D14 | Output events in the required JSON schema with all mandatory fields |
| FR-D15 | Emit events for empty-store periods without crashing |

### 2.2 Intelligence API (Part B — 35 pts)

| ID | Endpoint | Requirement |
|----|----------|-------------|
| FR-A01 | `POST /events/ingest` | Accept up to 500 events per batch; validate schema; deduplicate by `event_id`; idempotent; partial success on malformed events |
| FR-A02 | `GET /stores/{id}/metrics` | Return: unique visitors, conversion rate, avg dwell per zone, current queue depth, abandonment rate; real-time; exclude staff |
| FR-A03 | `GET /stores/{id}/funnel` | Session-based conversion funnel: Entry → Zone Visit → Billing Queue → Purchase; drop-off % at each stage; no double-counting on re-entry |
| FR-A04 | `GET /stores/{id}/heatmap` | Zone visit frequency + avg dwell, normalised 0–100; include `data_confidence` flag if < 20 sessions |
| FR-A05 | `GET /stores/{id}/anomalies` | Active anomalies: queue spike, conversion drop vs 7-day avg, dead zone (no visits in 30 min); severity: INFO/WARN/CRITICAL; `suggested_action` string |
| FR-A06 | `GET /health` | Service status; last event timestamp per store; `STALE_FEED` warning if lag > 10 min |

### 2.3 Production Readiness (Part C — 20 pts)

| ID | Requirement |
|----|-------------|
| FR-P01 | `docker compose up` starts the entire system — no manual steps beyond `git clone` |
| FR-P02 | Structured logging per request: `trace_id`, `store_id`, `endpoint`, `latency_ms`, `event_count`, `status_code` |
| FR-P03 | POST /events/ingest is idempotent — safe to call twice with same payload |
| FR-P04 | Graceful degradation: DB unavailable → HTTP 503 with structured body, no raw stack traces |
| FR-P05 | Test statement coverage ≥ 70%; edge cases: empty store, all-staff clip, zero purchases, re-entry in funnel |
| FR-P06 | README: setup in ≤ 5 commands; explains how to run detection and feed into API |

### 2.4 AI Engineering (Part D — 15 pts)

| ID | Requirement |
|----|-------------|
| FR-AI01 | Prompt blocks at top of each test file (`# PROMPT: ...` / `# CHANGES MADE: ...`) |
| FR-AI02 | `DESIGN.md` with architecture overview and "AI-Assisted Decisions" section |
| FR-AI03 | `CHOICES.md` covering: model selection, event schema design, one API architecture choice |

### 2.5 Live Dashboard (Part E — +10 bonus pts)

| ID | Requirement |
|----|-------------|
| FR-E01 | At minimum one metric updating in real time as events flow from detection |
| FR-E02 | Web UI preferred over terminal output |

---

## 3. Non-Functional Requirements

| Category | Requirement |
|----------|-------------|
| **Performance** | `/metrics` endpoint response < 200ms for a store with up to 10K daily events |
| **Throughput** | Ingest endpoint handles 500 events/batch; target 1000+ events/min sustained |
| **Reliability** | API must not crash on zero-traffic, all-staff, or malformed-event inputs |
| **Scalability** | Architecture must support 40 stores (design for, implement for 5) |
| **Observability** | All requests logged with trace ID; health endpoint always accurate |
| **Data Integrity** | `event_id` globally unique; deduplication enforced at ingest |
| **Security** | No sensitive PII stored; customer phone numbers from POS anonymised |
| **Portability** | Fully containerised; runs on any machine with Docker + Docker Compose |

---

## 4. Data Requirements

### 4.1 Input Data (from Brigade Road Store — ST1008)

**POS Transactions CSV** (`Brigade_Bangalore_10_April_26.csv`):
- 101 transaction records, April 10, 2026
- Fields: `order_id`, `invoice_number`, `invoice_type`, `order_date`, `order_time`, `store_id`, `customer_number`, `sku`, `product_name`, `brand_name`, `dep_name`, `sub_category`, `qty`, `GMV`, `NMV`, `coupon_amount`, `item_promotion`, `total_amount`, `tax_amt`
- Key categories: skin, makeup, bath-and-body
- Key brands: DERMDOC, Good Vibes, Faces Canada, Lakme (PB brand type)

**Store Layout** (`Brigade_Road_Store_layout.xlsx`):
- Zone definitions for Brigade Road store
- Camera coverage per zone
- Store open hours

**CCTV Clips**:
- 5 stores × 3 cameras × 20-minute clips
- 1080p, 15fps, face-blurred, no audio
- Known edge cases: group entry, staff movement, re-entry, partial occlusion, billing queue, empty periods, camera overlap

### 4.2 Event Schema (Output)

```json
{
  "event_id": "uuid-v4",
  "store_id": "STORE_BLR_002",
  "camera_id": "CAM_ENTRY_01",
  "visitor_id": "VIS_c8a2f1",
  "event_type": "ZONE_DWELL",
  "timestamp": "2026-03-03T14:22:10Z",
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

**Event Types:** ENTRY, EXIT, ZONE_ENTER, ZONE_EXIT, ZONE_DWELL, BILLING_QUEUE_JOIN, BILLING_QUEUE_ABANDON, REENTRY

---

## 5. Tech Stack Requirements

### 5.1 Detection Pipeline

| Component | Recommended Options | Rationale |
|-----------|--------------------|-----------| 
| **Object Detection** | YOLOv8 / YOLOv9 / RT-DETR | Real-time, pre-trained on persons, good occlusion handling |
| **Person Tracking** | ByteTrack / DeepSORT / StrongSORT | Multi-object tracking across frames |
| **Re-ID** | OSNet / torchreid / bounding-box trajectory | Same person across sessions and cameras |
| **VLM (optional)** | GPT-4V / Claude Vision / Gemini Vision | Zone classification, staff detection via prompt |
| **Video Processing** | OpenCV / FFmpeg | Frame extraction, preprocessing |
| **Runtime** | Python 3.11+ | Ecosystem compatibility |

### 5.2 API & Backend

| Component | Choice | Rationale |
|-----------|--------|-----------|
| **Web Framework** | FastAPI | Async, automatic OpenAPI docs, Pydantic validation, best scoring harness coverage |
| **Schema Validation** | Pydantic v2 | Event schema enforcement, structured error responses |
| **Database** | PostgreSQL (prod) / SQLite (dev) | Relational for session/funnel logic; TimescaleDB extension for time-series metrics |
| **ORM / Query** | SQLAlchemy 2.0 + asyncpg | Async queries, connection pooling |
| **Caching** | Redis | Real-time metric caching, anomaly state |
| **Event Queue** | Redis Streams / Kafka (optional) | Decoupled ingest from computation |
| **Background Jobs** | FastAPI BackgroundTasks / Celery | Async metric recalculation |

### 5.3 Infrastructure & DevOps

| Component | Choice | Rationale |
|-----------|--------|-----------|
| **Containerisation** | Docker + Docker Compose | Required by challenge; single-command startup |
| **Reverse Proxy** | Nginx (optional) | Production-aware routing |
| **Logging** | structlog / python-json-logger | Structured JSON logs with trace_id |
| **Monitoring** | Prometheus + Grafana (optional) | Metrics observability |
| **Testing** | pytest + pytest-asyncio + httpx | Async FastAPI testing |
| **Coverage** | pytest-cov | Enforce ≥ 70% statement coverage |

### 5.4 Dashboard (Part E)

| Component | Choice | Rationale |
|-----------|--------|-----------|
| **Web Dashboard** | React + Recharts / D3.js | Real-time charts, WebSocket support |
| **Real-time Updates** | WebSocket / SSE | Push metrics from API to dashboard |
| **Terminal Fallback** | Python `rich` library | Lightweight alternative if no web UI |

### 5.5 Full Dependency List

```
# Detection Pipeline
ultralytics>=8.0          # YOLOv8/v9
opencv-python>=4.8
torch>=2.1
torchvision>=0.16
torchreid                  # OSNet Re-ID
lap                        # ByteTrack dependency
numpy>=1.24
Pillow>=10.0

# API
fastapi>=0.111
uvicorn[standard]>=0.29
pydantic>=2.7
sqlalchemy[asyncio]>=2.0
asyncpg>=0.29              # PostgreSQL async driver
aiosqlite>=0.20            # SQLite async driver (dev)
redis>=5.0
python-json-logger>=2.0
structlog>=24.0
httpx>=0.27                # Async HTTP client for testing

# Testing
pytest>=8.0
pytest-asyncio>=0.23
pytest-cov>=5.0
factory-boy>=3.3

# Utilities
python-dotenv>=1.0
uuid7>=0.1
```

---

## 6. Constraints

1. `docker compose up` must be the sole startup command
2. No API keys or secrets committed to repository
3. CCTV footage must not be published, trained on, or redistributed (challenge licence)
4. No raw stack traces in HTTP responses
5. Detection pipeline output must validate against the defined event schema
6. `event_id` must be UUID v4, globally unique across all events
7. All timestamps in ISO-8601 UTC format
8. Staff events (`is_staff=true`) must be excluded from all customer-facing metrics
9. Conversion rate correlation uses 5-minute billing zone window before POS transaction timestamp

---

## 7. Acceptance Criteria (Scoring Gate)

A submission is accepted for scoring only if:

1. `docker compose up` starts the API without manual steps
2. README explains how to run detection pipeline against clips
3. `POST /events/ingest` returns non-5xx response
4. `GET /stores/STORE_BLR_002/metrics` returns valid JSON
5. `DESIGN.md` and `CHOICES.md` both exist with > 250 words each

---

## 8. Scoring Targets

| Part | Max Points | Target (80+ score) |
|------|-----------|-------------------|
| A — Detection Pipeline | 30 | ≥ 24 |
| B — Intelligence API | 35 | ≥ 28 |
| C — Production Readiness | 20 | ≥ 18 |
| D — AI Engineering | 15 | ≥ 12 |
| E — Live Dashboard (bonus) | +10 | +8 |
| **Total** | **100+10** | **≥ 82** |

Score interpretation: 85+ = Strong candidate | 70–85 = Suitable for interview
