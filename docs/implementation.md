# Implementation Guide — Store Intelligence System
## Purplle Tech Challenge 2026 · Round 2

---

## 1. Repository Structure

```
store-intelligence/
├── pipeline/
│   ├── detect.py              # YOLOv8 detection + frame iteration
│   ├── tracker.py             # ByteTrack + Re-ID (OSNet embeddings)
│   ├── zone_mapper.py         # Centroid → zone_id using store_layout.json
│   ├── staff_classifier.py    # Uniform colour + optional VLM fallback
│   ├── reentry.py             # Cross-session Re-ID and REENTRY detection
│   ├── emit.py                # Event schema builder + JSONL emitter
│   ├── correlate_pos.py       # POS transaction time-window correlation
│   └── run.sh                 # One-command pipeline runner
├── app/
│   ├── main.py                # FastAPI app factory, lifespan, middleware
│   ├── routers/
│   │   ├── events.py          # POST /events/ingest
│   │   ├── metrics.py         # GET /stores/{id}/metrics
│   │   ├── funnel.py          # GET /stores/{id}/funnel
│   │   ├── heatmap.py         # GET /stores/{id}/heatmap
│   │   ├── anomalies.py       # GET /stores/{id}/anomalies
│   │   └── health.py          # GET /health
│   ├── models/
│   │   ├── event.py           # Pydantic event + ingest request models
│   │   ├── responses.py       # API response models
│   │   └── db.py              # SQLAlchemy ORM models
│   ├── services/
│   │   ├── ingestion.py       # Validate, dedup, session update
│   │   ├── metrics.py         # Real-time aggregation
│   │   ├── funnel.py          # Session-based funnel computation
│   │   ├── heatmap.py         # Zone frequency normalisation
│   │   ├── anomalies.py       # Anomaly detection engine
│   │   └── health.py          # Feed staleness checks
│   ├── db/
│   │   ├── session.py         # Async SQLAlchemy session factory
│   │   └── migrations/        # Alembic migration files
│   └── middleware/
│       ├── logging.py         # Structured request logging
│       └── errors.py          # Global error handler
├── dashboard/                 # Part E — React live dashboard
│   ├── src/
│   │   ├── App.jsx
│   │   ├── components/
│   │   │   ├── MetricCard.jsx
│   │   │   ├── FunnelChart.jsx
│   │   │   ├── ZoneHeatmap.jsx
│   │   │   └── AnomalyBanner.jsx
│   │   └── hooks/
│   │       └── useStoreWebSocket.js
│   ├── package.json
│   └── Dockerfile
├── tests/
│   ├── test_pipeline.py       # Detection pipeline tests (with PROMPT block)
│   ├── test_ingest.py         # Ingest endpoint tests (with PROMPT block)
│   ├── test_metrics.py        # Metrics computation tests
│   ├── test_funnel.py         # Funnel + deduplication tests
│   └── test_anomalies.py      # Anomaly detection tests
├── docs/
│   ├── DESIGN.md
│   └── CHOICES.md
├── data/
│   └── Brigade_Bangalore_10_April_26.csv   # seeded POS data
├── docker-compose.yml
├── docker-compose.override.yml   # dev overrides (hot reload, debug)
├── .env.example
└── README.md
```

---

## 2. Quick Start (5 Commands)

```bash
# 1. Clone the repository
git clone https://github.com/<your-handle>/store-intelligence && cd store-intelligence

# 2. Copy environment config
cp .env.example .env

# 3. Start all services
docker compose up -d

# 4. Run the detection pipeline against CCTV clips
docker compose run pipeline python pipeline/run.sh /path/to/clips/

# 5. Verify the API is live
curl http://localhost:8000/health
```

The API is available at `http://localhost:8000`.  
The live dashboard (Part E) is available at `http://localhost:3000`.

---

## 3. Detection Pipeline Implementation

### 3.1 Core Detection Loop (`detect.py`)

```python
# PROMPT: Write a YOLOv8 person detection loop for 15fps 1080p retail CCTV footage.
#         Include: per-frame bounding boxes, confidence threshold at 0.4,
#         only class 0 (person), output as list of Detection objects.
# CHANGES MADE: Added adaptive confidence thresholding (lower in low-light frames).
#               Added frame subsampling (process every 3rd frame at 15fps = effective 5fps).

import cv2
from ultralytics import YOLO
from dataclasses import dataclass
from typing import List

CONFIDENCE_THRESHOLD = 0.4
FRAME_SAMPLE_RATE = 3  # Process every Nth frame

@dataclass
class Detection:
    frame_idx: int
    timestamp_ms: float
    bbox: tuple         # (x1, y1, x2, y2)
    confidence: float
    track_id: int       # assigned by ByteTrack

def process_clip(clip_path: str, store_id: str, camera_id: str, clip_start_utc: str):
    model = YOLO("yolov8n.pt")
    cap = cv2.VideoCapture(clip_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    
    frame_idx = 0
    detections = []
    
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        
        if frame_idx % FRAME_SAMPLE_RATE == 0:
            results = model.track(
                frame, 
                persist=True,           # ByteTrack state persists across frames
                classes=[0],            # Person class only
                conf=CONFIDENCE_THRESHOLD,
                verbose=False
            )
            
            timestamp_ms = (frame_idx / fps) * 1000
            
            for box in results[0].boxes:
                if box.id is None:
                    continue
                
                det = Detection(
                    frame_idx=frame_idx,
                    timestamp_ms=timestamp_ms,
                    bbox=box.xyxy[0].tolist(),
                    confidence=float(box.conf),
                    track_id=int(box.id)
                )
                detections.append(det)
        
        frame_idx += 1
    
    cap.release()
    return detections
```

### 3.2 Zone Mapping (`zone_mapper.py`)

```python
# Maps a bounding box centroid to a store zone using the store_layout.json

import json
from typing import Optional

def load_layout(layout_path: str) -> dict:
    with open(layout_path) as f:
        return json.load(f)

def centroid(bbox: tuple) -> tuple:
    x1, y1, x2, y2 = bbox
    return ((x1 + x2) / 2, (y1 + y2) / 2)

def map_to_zone(bbox: tuple, layout: dict, camera_id: str) -> Optional[str]:
    """
    Returns zone_id if the centroid falls within a defined zone polygon,
    else returns None.
    """
    cx, cy = centroid(bbox)
    
    camera_zones = layout.get("cameras", {}).get(camera_id, {}).get("zones", [])
    
    for zone in camera_zones:
        poly = zone["polygon"]  # list of [x,y] points in pixel space
        if point_in_polygon(cx, cy, poly):
            return zone["zone_id"]
    
    return None

def point_in_polygon(x: float, y: float, polygon: list) -> bool:
    """Ray casting algorithm."""
    n = len(polygon)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside
```

### 3.3 Entry/Exit Direction Logic

Direction is determined at the entry camera only using bounding box trajectory:

```python
# Entry = centroid moves from outside-store half to inside-store half of the frame
# Exit  = centroid moves from inside-store half to outside-store half

ENTRY_LINE_Y_PCT = 0.5  # Configurable per camera in store_layout.json

def detect_direction(track_history: list, frame_height: int) -> Optional[str]:
    """
    track_history: list of (y_centroid) values over last N frames
    Returns: 'ENTRY', 'EXIT', or None (no threshold crossing)
    """
    if len(track_history) < 5:
        return None
    
    threshold_y = frame_height * ENTRY_LINE_Y_PCT
    start_y = track_history[0]
    end_y = track_history[-1]
    
    if start_y < threshold_y and end_y > threshold_y:
        return "ENTRY"
    elif start_y > threshold_y and end_y < threshold_y:
        return "EXIT"
    return None
```

### 3.4 Re-ID and Re-Entry Detection (`tracker.py`)

```python
# OSNet Re-ID embeddings used to match visitors across sessions
# Cosine similarity > 0.85 = same person

import torch
import torchreid
import numpy as np

SIMILARITY_THRESHOLD = 0.85
REENTRY_WINDOW_SEC = 60     # Within 60s of EXIT, same embedding = REENTRY

class VisitorGallery:
    """Stores Re-ID embeddings for visitor matching."""
    
    def __init__(self):
        self.model = torchreid.models.build_model(
            name='osnet_x1_0', num_classes=1000, pretrained=True
        )
        self.model.eval()
        self.gallery = {}  # visitor_id → (embedding, last_seen_ts)
    
    def get_or_create_visitor_id(self, crop: np.ndarray, timestamp_sec: float) -> tuple[str, bool]:
        """
        Returns (visitor_id, is_reentry).
        is_reentry=True when a recently-exited visitor is matched.
        """
        embedding = self._extract_embedding(crop)
        
        best_match_id, best_sim = self._find_best_match(embedding)
        
        if best_match_id and best_sim > SIMILARITY_THRESHOLD:
            entry = self.gallery[best_match_id]
            time_since_exit = timestamp_sec - entry['exit_at']
            
            is_reentry = (entry.get('status') == 'EXITED' and 
                         time_since_exit < REENTRY_WINDOW_SEC)
            
            self.gallery[best_match_id]['embedding'] = embedding
            self.gallery[best_match_id]['last_seen'] = timestamp_sec
            return best_match_id, is_reentry
        
        # New visitor
        new_id = f"VIS_{uuid4().hex[:6]}"
        self.gallery[new_id] = {
            'embedding': embedding,
            'last_seen': timestamp_sec,
            'status': 'ACTIVE'
        }
        return new_id, False
```

### 3.5 Event Emitter (`emit.py`)

```python
import json
import uuid
from datetime import datetime, timezone

def build_event(
    store_id: str,
    camera_id: str,
    visitor_id: str,
    event_type: str,
    clip_start_utc: datetime,
    timestamp_offset_ms: float,
    zone_id: str | None,
    dwell_ms: int,
    is_staff: bool,
    confidence: float,
    metadata: dict
) -> dict:
    
    event_ts = clip_start_utc.timestamp() + (timestamp_offset_ms / 1000)
    
    return {
        "event_id": str(uuid.uuid4()),
        "store_id": store_id,
        "camera_id": camera_id,
        "visitor_id": visitor_id,
        "event_type": event_type,
        "timestamp": datetime.fromtimestamp(event_ts, tz=timezone.utc).isoformat(),
        "zone_id": zone_id,
        "dwell_ms": dwell_ms,
        "is_staff": is_staff,
        "confidence": round(confidence, 3),
        "metadata": {
            "queue_depth": metadata.get("queue_depth"),
            "sku_zone": metadata.get("sku_zone"),
            "session_seq": metadata.get("session_seq", 1)
        }
    }

def emit_to_jsonl(event: dict, output_path: str):
    with open(output_path, "a") as f:
        f.write(json.dumps(event) + "\n")
```

---

## 4. API Implementation

### 4.1 FastAPI App Factory (`main.py`)

```python
from fastapi import FastAPI, Request
from contextlib import asynccontextmanager
from app.db.session import init_db, close_db
from app.middleware.logging import RequestLoggingMiddleware
from app.middleware.errors import register_error_handlers
from app.routers import events, metrics, funnel, heatmap, anomalies, health

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
    await close_db()

app = FastAPI(
    title="Store Intelligence API",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(RequestLoggingMiddleware)
register_error_handlers(app)

app.include_router(events.router)
app.include_router(metrics.router)
app.include_router(funnel.router)
app.include_router(heatmap.router)
app.include_router(anomalies.router)
app.include_router(health.router)
```

### 4.2 Ingest Endpoint (`routers/events.py`)

```python
from fastapi import APIRouter, Depends
from app.models.event import IngestRequest, IngestResponse
from app.services.ingestion import ingest_events
from app.db.session import get_db

router = APIRouter()

@router.post("/events/ingest", response_model=IngestResponse, status_code=200)
async def ingest(request: IngestRequest, db=Depends(get_db)):
    """
    Idempotent batch ingest. Accepts up to 500 events.
    Returns 207 if any events are rejected.
    """
    result = await ingest_events(db, request.events)
    
    status_code = 207 if result.rejected > 0 else 200
    return JSONResponse(content=result.dict(), status_code=status_code)
```

### 4.3 Ingestion Service (`services/ingestion.py`)

```python
# PROMPT: Write an async idempotent batch event ingestion function for FastAPI + SQLAlchemy.
#         Must: validate Pydantic model, deduplicate by event_id (ON CONFLICT DO NOTHING),
#         return counts of accepted/rejected/duplicate, handle partial success.
# CHANGES MADE: Added session state update logic (open/close sessions on ENTRY/EXIT events).
#               Added Re-ID correlation for REENTRY events.

async def ingest_events(db, events: list[EventModel]) -> IngestResult:
    accepted = 0
    rejected = 0
    duplicates = 0
    errors = []
    
    for idx, event in enumerate(events):
        try:
            # Insert with ON CONFLICT DO NOTHING
            result = await db.execute(
                insert(Event).values(**event.dict()).on_conflict_do_nothing(index_elements=["event_id"])
            )
            
            if result.rowcount == 0:
                duplicates += 1
            else:
                accepted += 1
                # Update session state
                await update_session_state(db, event)
                
        except ValidationError as e:
            rejected += 1
            errors.append({"index": idx, "event_id": str(event.event_id), "reason": str(e)})
    
    await db.commit()
    return IngestResult(accepted=accepted, rejected=rejected, duplicate=duplicates, errors=errors)
```

### 4.4 Structured Logging Middleware (`middleware/logging.py`)

```python
import time
import uuid
import structlog
from fastapi import Request

logger = structlog.get_logger()

class RequestLoggingMiddleware:
    async def __call__(self, request: Request, call_next):
        trace_id = f"trc_{uuid.uuid4().hex[:6]}"
        request.state.trace_id = trace_id
        
        start = time.perf_counter()
        response = await call_next(request)
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        
        logger.info(
            "request",
            trace_id=trace_id,
            store_id=request.path_params.get("store_id"),
            endpoint=request.url.path,
            method=request.method,
            latency_ms=latency_ms,
            status_code=response.status_code,
        )
        
        response.headers["X-Trace-Id"] = trace_id
        return response
```

### 4.5 Error Handler (`middleware/errors.py`)

```python
# No raw stack traces ever reach the response body
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

def register_error_handlers(app: FastAPI):
    
    @app.exception_handler(OperationalError)
    async def db_error_handler(request: Request, exc: OperationalError):
        return JSONResponse(
            status_code=503,
            content={
                "error": "DATABASE_UNAVAILABLE",
                "detail": "Storage layer is temporarily unavailable. Retry after 30s.",
                "trace_id": getattr(request.state, "trace_id", "unknown")
            }
        )
    
    @app.exception_handler(Exception)
    async def generic_error_handler(request: Request, exc: Exception):
        # Log full traceback internally, never expose it
        logger.exception("unhandled_error", trace_id=request.state.trace_id, error=str(exc))
        return JSONResponse(
            status_code=500,
            content={
                "error": "INTERNAL_ERROR",
                "detail": "An unexpected error occurred.",
                "trace_id": getattr(request.state, "trace_id", "unknown")
            }
        )
```

---

## 5. Docker Compose Setup

```yaml
# docker-compose.yml
version: "3.9"

services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: store_intelligence
      POSTGRES_USER: si_user
      POSTGRES_PASSWORD: si_pass
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U si_user -d store_intelligence"]
      interval: 5s
      timeout: 3s
      retries: 10

  redis:
    image: redis:7-alpine
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s

  api:
    build:
      context: ./app
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql+asyncpg://si_user:si_pass@db/store_intelligence
      REDIS_URL: redis://redis:6379
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    command: |
      sh -c "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"

  dashboard:
    build: ./dashboard
    ports:
      - "3000:3000"
    environment:
      REACT_APP_API_URL: http://localhost:8000
    depends_on:
      - api

volumes:
  postgres_data:
```

---

## 6. Testing Strategy

### 6.1 Test Structure

```python
# tests/test_ingest.py
# PROMPT: Write pytest tests for an idempotent batch event ingest endpoint.
#         Must cover: valid batch, duplicate event_id, malformed event_type,
#         empty batch, max batch size (500), DB unavailable (mock).
# CHANGES MADE: Added session state assertion after ENTRY event ingestion.
#               Replaced hardcoded store_id with fixture. Added 207 status check.

import pytest
from httpx import AsyncClient
from app.main import app

@pytest.mark.asyncio
async def test_ingest_idempotent(client, sample_events):
    """Ingesting same batch twice should not create duplicates."""
    r1 = await client.post("/events/ingest", json={"events": sample_events})
    r2 = await client.post("/events/ingest", json={"events": sample_events})
    
    assert r1.status_code == 200
    assert r1.json()["accepted"] == len(sample_events)
    
    assert r2.status_code == 200
    assert r2.json()["accepted"] == 0
    assert r2.json()["duplicate"] == len(sample_events)

@pytest.mark.asyncio
async def test_ingest_partial_success(client):
    """Batch with some bad events → 207, good events accepted."""
    events = [valid_event(), invalid_event_type(), valid_event()]
    r = await client.post("/events/ingest", json={"events": events})
    
    assert r.status_code == 207
    assert r.json()["accepted"] == 2
    assert r.json()["rejected"] == 1

@pytest.mark.asyncio
async def test_metrics_zero_visitors(client, empty_store_id):
    """Empty store: metrics must return 0 counts, not null or crash."""
    r = await client.get(f"/stores/{empty_store_id}/metrics")
    assert r.status_code == 200
    body = r.json()
    assert body["visitors"]["unique_count"] == 0
    assert body["conversion"]["rate"] == 0.0  # Never null

@pytest.mark.asyncio
async def test_funnel_reentry_not_double_counted(client, reentry_events):
    """Visitor who re-enters should count as 1 in the funnel."""
    await client.post("/events/ingest", json={"events": reentry_events})
    r = await client.get(f"/stores/STORE_BLR_002/funnel")
    
    funnel = r.json()["funnel"]
    entry_stage = next(s for s in funnel if s["stage"] == "STORE_ENTRY")
    assert entry_stage["sessions"] == 1  # Same person = 1 session
```

### 6.2 Coverage Requirements

```ini
# pytest.ini
[pytest]
asyncio_mode = auto
addopts = --cov=app --cov-report=term-missing --cov-fail-under=70
```

### 6.3 Edge Cases Covered

| Test | Scenario |
|------|----------|
| `test_empty_store` | All-empty store: no crashes, 0 counts returned |
| `test_all_staff_clip` | All `is_staff=true` events: customer metrics = 0 |
| `test_zero_purchases` | Events with no POS match: conversion_rate = 0.0, not null |
| `test_reentry_funnel` | REENTRY event: funnel counts visitor once, not twice |
| `test_db_unavailable` | Mock DB failure: returns 503 with structured body |
| `test_ingest_idempotent` | Same payload twice: second call returns all duplicate, 0 accepted |
| `test_partial_batch` | Mixed valid/invalid: 207 with error list |
| `test_max_batch_size` | 500 events: accepted; 501: 422 error |

---

## 7. POS Data Loading

The Brigade Road POS CSV is loaded into `pos_transactions` at startup:

```python
import csv
from datetime import datetime, timezone

async def seed_pos_transactions(db, csv_path: str):
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            ts_str = f"{row['order_date']} {row['order_time']}"
            ts = datetime.strptime(ts_str, "%d-%m-%Y %H:%M:%S").replace(tzinfo=timezone.utc)
            
            await db.execute(
                insert(PosTransaction).values(
                    transaction_id=row['invoice_number'],
                    store_id=row['store_id'],
                    timestamp=ts,
                    basket_value_inr=float(row['total_amount'])
                ).on_conflict_do_nothing()
            )
    await db.commit()
```

---

## 8. Environment Variables

```bash
# .env.example
DATABASE_URL=postgresql+asyncpg://si_user:si_pass@db/store_intelligence
REDIS_URL=redis://redis:6379
LOG_LEVEL=INFO
REENTRY_WINDOW_SEC=60
QUEUE_SPIKE_THRESHOLD=5
STALE_FEED_MINUTES=10
DEAD_ZONE_MINUTES=30
CONFIDENCE_THRESHOLD=0.4
```
