# Store Intelligence System — Design Document

## System Overview

The Store Intelligence System is a real-time analytics platform for Purplle's brick-and-mortar retail stores. It processes CCTV camera feeds to detect customer movement patterns, correlates them with POS transaction data, and surfaces actionable insights through a REST API and live dashboard.

The system architecture follows a **4-stage pipeline** model:

```
CCTV Feeds → Detection Pipeline → Event Ingestion API → Analytics Dashboard
                                        ↓
                              PostgreSQL + Redis Cache
```

## Architecture

### Data Flow

1. **Detection Stage**: YOLO-based object detection processes CCTV frames to identify people, classify staff vs. customers, and track movement across store zones.

2. **Ingestion Stage**: Detected events are batched and sent to the REST API via `POST /events/ingest`. Events are immutable and stored in an append-only log with UUID-based idempotency.

3. **Analytics Stage**: The API computes real-time metrics, conversion funnels, zone heatmaps, and anomaly detection by querying the event store and correlating with POS data.

4. **Presentation Stage**: A WebSocket-enabled dashboard presents live metrics, heatmaps, and anomaly alerts to store managers.

### Database Schema

The system uses 6 relational tables with strict referential integrity:

| Table | Purpose | Key Relationships |
|-------|---------|-------------------|
| `stores` | Reference data for physical stores | Parent of all other tables |
| `events` | Immutable event log (source of truth) | FK → stores |
| `sessions` | Derived visitor sessions (ENTRY→EXIT) | FK → stores |
| `zone_visits` | Zone-level visit tracking with dwell | FK → sessions, stores |
| `pos_transactions` | POS data for conversion correlation | FK → stores, sessions |
| `anomaly_log` | Persistent anomaly detection log | FK → stores |

### Key Design Decisions

**Idempotent Ingestion**: Every event carries a UUID `event_id`. Re-ingesting the same event is a no-op, counted as a duplicate. This ensures pipeline restarts and retries never corrupt data.

**Session Derivation**: Sessions are derived on-the-fly from ENTRY/EXIT event pairs. Re-entries create new sessions with incremented `session_seq` to distinguish return visits.

**POS Correlation**: Uses a 5-minute billing window — if a POS transaction occurs within 5 minutes of a visitor's EXIT event, the session is marked as converted.

**Staff Exclusion**: Staff are identified by the detection pipeline and flagged `is_staff=true`. All customer-facing metrics automatically exclude staff events.

## API Design

The API follows REST principles with structured JSON responses:

- **Structured errors**: No raw stack traces. All errors return `{"error": "...", "detail": "...", "trace_id": "..."}`.
- **Trace IDs**: Every request gets a `trc_XXXXXX` identifier for debugging.
- **Window parameters**: Most analytics endpoints accept `window_minutes`, `from`, and `to` parameters for time-based filtering.
- **Zero-safe returns**: Empty stores return zero counts, never null or crashes.

### Endpoint Map

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/events/ingest` | Batch event ingestion |
| GET | `/stores/{id}/metrics` | Real-time visitor metrics |
| GET | `/stores/{id}/funnel` | 4-stage conversion funnel |
| GET | `/stores/{id}/heatmap` | Zone visit frequency heatmap |
| GET | `/stores/{id}/anomalies` | Active anomaly detection |
| GET | `/health` | Service health check |

## Anomaly Detection

The system implements 5 anomaly detection rules:

1. **BILLING_QUEUE_SPIKE**: Queue depth exceeds threshold for sustained period.
2. **CONVERSION_DROP**: Hourly conversion rate drops below 70% of baseline.
3. **DEAD_ZONE**: No zone visits for 30+ minutes during open hours.
4. **STALE_FEED**: No events from any camera for 10+ minutes.
5. **ABANDONMENT_SPIKE**: Queue abandonment rate exceeds 30%.

Each anomaly includes severity (INFO/WARN/CRITICAL), a human-readable description, and a suggested action for store managers.

## Security & Privacy

- No API keys required (internal service mesh).
- Customer phone numbers are not stored (PII compliance).
- No raw stack traces exposed in HTTP responses.
- All configuration via environment variables (no secrets in code).

## Deployment

The system is fully containerized via Docker Compose:
- **PostgreSQL 16**: Persistent event store with connection pooling
- **Redis 7**: Session cache and real-time state
- **API**: FastAPI on uvicorn with structured logging
- **Pipeline**: Separate container with GPU support for YOLO inference
