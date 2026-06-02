# Store Intelligence System

Real-time retail analytics for Purplle brick-and-mortar stores. Processes CCTV footage to detect customer movement, correlates with POS data, and surfaces actionable insights via REST API.

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Python 3.11+ (for local dev)

### Local Development (SQLite)

```bash
# Install dependencies
pip install -r app/requirements.txt

# Run the API
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

# Health check
curl http://localhost:8000/health
```

### Docker (Production)

```bash
# Start all services
docker compose up -d

# Check health
curl http://localhost:8000/health
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/events/ingest` | Batch event ingestion (idempotent) |
| `GET` | `/stores/{id}/metrics` | Real-time visitor metrics |
| `GET` | `/stores/{id}/funnel` | 4-stage conversion funnel |
| `GET` | `/stores/{id}/heatmap` | Zone visit frequency heatmap |
| `GET` | `/stores/{id}/anomalies` | Active anomaly detection |
| `GET` | `/health` | Service health + feed status |

### Example: Ingest Events

```bash
curl -X POST http://localhost:8000/events/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "events": [{
      "event_id": "550e8400-e29b-41d4-a716-446655440000",
      "store_id": "STORE_BLR_002",
      "camera_id": "CAM_ENTRY_01",
      "visitor_id": "VIS_0001",
      "event_type": "ENTRY",
      "timestamp": "2026-04-10T14:00:00Z",
      "dwell_ms": 0,
      "is_staff": false,
      "confidence": 0.92,
      "metadata": {"session_seq": 1}
    }]
  }'
```

### Example: Get Metrics

```bash
curl http://localhost:8000/stores/STORE_BLR_002/metrics?window_minutes=60
```

## Running Tests

```bash
pip install pytest pytest-asyncio pytest-cov

# Run all tests with coverage
python -m pytest tests/ -v

# Quick run
python -m pytest tests/ -q
```

## Project Structure

```
purplle/
  app/
    main.py              # FastAPI app factory
    models/
      db.py              # SQLAlchemy ORM models (6 tables)
      event.py           # Pydantic request models
      responses.py       # Pydantic response models
    routers/
      events.py          # POST /events/ingest
      metrics.py         # GET /stores/{id}/metrics
      funnel.py          # GET /stores/{id}/funnel
      heatmap.py         # GET /stores/{id}/heatmap
      anomalies.py       # GET /stores/{id}/anomalies
      health.py          # GET /health
    services/
      ingestion.py       # Event processing + session lifecycle
      metrics.py         # Visitor metrics computation
      funnel.py          # 4-stage funnel computation
      heatmap.py         # Zone heatmap computation
      anomalies.py       # 5-rule anomaly detection
      health.py          # Health check logic
    middleware/
      logging.py         # Structured request logging
      errors.py          # Global error handlers
    db/
      session.py         # Async DB engine management
      init_db.py         # Table creation + data seeding
  pipeline/              # CCTV detection pipeline
  tests/                 # Pytest test suite
  data/                  # POS CSV + store layout
  docs/                  # DESIGN.md, CHOICES.md
  docker-compose.yml     # Full orchestration
```

## Data

- **POS Data**: `data/Brigade_Bangalore_10_April_26.csv` — 101 rows, 24 unique transactions from store ST1008 (Brigade Road Bangalore)
- **CCTV**: 5 camera clips in `data/` (CAM 1-5.mp4)
- **Store Layout**: `data/Brigade Road - Store layoutc5f5d56.xlsx`

## Documentation

- [Design Document](docs/DESIGN.md) — System architecture and design decisions
- [Technical Choices](docs/CHOICES.md) — Trade-off analysis for all technology decisions
- [API Catalog](docs/api_catalog.md) — Full endpoint specifications
- [Database Schema](docs/database_schema.md) — Table definitions and relationships
