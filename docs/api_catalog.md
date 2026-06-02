# API Catalog — Store Intelligence API
## Purplle Tech Challenge 2026 · Round 2

Base URL: `http://localhost:8000`  
API Version: `v1`  
Auth: None (challenge scope — production would use API keys)

---

## Global Conventions

| Convention | Detail |
|------------|--------|
| Content-Type | `application/json` |
| Timestamps | ISO-8601 UTC (`2026-04-10T14:22:10Z`) |
| Error format | `{"error": "...", "detail": "...", "trace_id": "..."}` |
| Idempotency | `POST /events/ingest` is idempotent by `event_id` |
| Pagination | None required for challenge scope |
| Staff filter | All customer metrics exclude `is_staff=true` events |

---

## 1. Event Ingestion

### `POST /events/ingest`

Accepts a batch of structured detection events from the pipeline. Validates schema, deduplicates by `event_id`, and persists to the database. Supports partial success on malformed events.

**Request Body**

```json
{
  "events": [
    {
      "event_id": "550e8400-e29b-41d4-a716-446655440001",
      "store_id": "STORE_BLR_002",
      "camera_id": "CAM_ENTRY_01",
      "visitor_id": "VIS_c8a2f1",
      "event_type": "ENTRY",
      "timestamp": "2026-04-10T14:22:10Z",
      "zone_id": null,
      "dwell_ms": 0,
      "is_staff": false,
      "confidence": 0.94,
      "metadata": {
        "queue_depth": null,
        "sku_zone": null,
        "session_seq": 1
      }
    }
  ]
}
```

**Constraints:**
- Maximum 500 events per batch
- `event_id` must be UUID v4
- `event_type` must be one of: `ENTRY`, `EXIT`, `ZONE_ENTER`, `ZONE_EXIT`, `ZONE_DWELL`, `BILLING_QUEUE_JOIN`, `BILLING_QUEUE_ABANDON`, `REENTRY`
- `confidence` must be 0.0–1.0
- Duplicate `event_id` values are silently deduplicated (idempotent)

**Response — 200 OK (full success)**

```json
{
  "accepted": 47,
  "rejected": 0,
  "duplicate": 3,
  "errors": [],
  "trace_id": "trc_9f2a1c"
}
```

**Response — 207 Multi-Status (partial success)**

```json
{
  "accepted": 44,
  "rejected": 3,
  "duplicate": 0,
  "errors": [
    {
      "index": 12,
      "event_id": "bad-uuid",
      "reason": "event_id is not a valid UUID v4"
    },
    {
      "index": 23,
      "event_id": "550e8400-e29b-41d4-a716-446655440099",
      "reason": "event_type 'DWELL' is not in allowed catalogue"
    }
  ],
  "trace_id": "trc_9f2a1c"
}
```

**Response — 503 Service Unavailable (DB down)**

```json
{
  "error": "DATABASE_UNAVAILABLE",
  "detail": "Storage layer is temporarily unavailable. Retry after 30s.",
  "trace_id": "trc_9f2a1c"
}
```

---

## 2. Store Metrics

### `GET /stores/{store_id}/metrics`

Returns real-time store analytics for today. All metrics exclude staff events.

**Path Parameters**

| Parameter | Type | Description |
|-----------|------|-------------|
| `store_id` | string | Store identifier (e.g., `STORE_BLR_002`) |

**Query Parameters**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `window_minutes` | int | 1440 (today) | Rolling window for metric computation |
| `from` | datetime | Start of today (UTC) | Override window start |
| `to` | datetime | Now (UTC) | Override window end |

**Response — 200 OK**

```json
{
  "store_id": "STORE_BLR_002",
  "computed_at": "2026-04-10T18:45:00Z",
  "window": {
    "from": "2026-04-10T00:00:00Z",
    "to": "2026-04-10T18:45:00Z"
  },
  "visitors": {
    "unique_count": 87,
    "total_entries": 94,
    "reentry_count": 7
  },
  "conversion": {
    "rate": 0.34,
    "converted_visitors": 30,
    "total_visitors": 87
  },
  "dwell": {
    "avg_total_ms": 412000,
    "by_zone": {
      "SKINCARE": 185000,
      "MAKEUP": 143000,
      "BATH_BODY": 98000,
      "BILLING": 67000
    }
  },
  "queue": {
    "current_depth": 2,
    "max_depth_today": 8,
    "avg_wait_ms": 124000
  },
  "abandonment": {
    "rate": 0.18,
    "abandoned_count": 7,
    "billing_entries": 38
  }
}
```

**Edge Cases:**
- Zero visitors → `unique_count: 0`, `rate: 0.0` (never null)
- Zero purchases → `conversion.rate: 0.0`, not a division error
- Store not found → 404 with structured error

---

## 3. Conversion Funnel

### `GET /stores/{store_id}/funnel`

Returns session-based conversion funnel from entry to purchase. Sessions are the unit of analysis, not raw events. Re-entries are deduplicated — a visitor returning counts once in the funnel.

**Path Parameters**

| Parameter | Type | Description |
|-----------|------|-------------|
| `store_id` | string | Store identifier |

**Query Parameters**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `date` | date | today | Date for funnel computation (YYYY-MM-DD) |

**Response — 200 OK**

```json
{
  "store_id": "STORE_BLR_002",
  "date": "2026-04-10",
  "funnel": [
    {
      "stage": "STORE_ENTRY",
      "label": "Entered Store",
      "sessions": 87,
      "dropoff_pct": 0.0
    },
    {
      "stage": "ZONE_VISIT",
      "label": "Visited at least one product zone",
      "sessions": 74,
      "dropoff_pct": 14.9
    },
    {
      "stage": "BILLING_REACH",
      "label": "Reached billing area",
      "sessions": 38,
      "dropoff_pct": 48.6
    },
    {
      "stage": "PURCHASE",
      "label": "Completed purchase",
      "sessions": 30,
      "dropoff_pct": 21.1
    }
  ],
  "overall_conversion_pct": 34.5,
  "largest_dropoff_stage": "BILLING_REACH"
}
```

---

## 4. Zone Heatmap

### `GET /stores/{store_id}/heatmap`

Returns zone visit frequency and average dwell time, normalised to 0–100 scale for rendering as a grid heatmap.

**Path Parameters**

| Parameter | Type | Description |
|-----------|------|-------------|
| `store_id` | string | Store identifier |

**Query Parameters**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `window_minutes` | int | 60 | Lookback window |

**Response — 200 OK**

```json
{
  "store_id": "STORE_BLR_002",
  "window_minutes": 60,
  "computed_at": "2026-04-10T18:45:00Z",
  "data_confidence": "HIGH",
  "zones": [
    {
      "zone_id": "SKINCARE",
      "label": "Skincare",
      "visit_count": 43,
      "avg_dwell_ms": 185000,
      "visit_score": 100,
      "dwell_score": 100
    },
    {
      "zone_id": "MAKEUP",
      "label": "Makeup",
      "visit_count": 31,
      "avg_dwell_ms": 143000,
      "visit_score": 72,
      "dwell_score": 77
    },
    {
      "zone_id": "BATH_BODY",
      "label": "Bath & Body",
      "visit_count": 18,
      "avg_dwell_ms": 98000,
      "visit_score": 42,
      "dwell_score": 53
    },
    {
      "zone_id": "BILLING",
      "label": "Billing",
      "visit_count": 38,
      "avg_dwell_ms": 67000,
      "visit_score": 88,
      "dwell_score": 36
    }
  ]
}
```

**Notes:**
- `data_confidence: "LOW"` when fewer than 20 sessions in the window
- `visit_score` and `dwell_score` are normalised 0–100 relative to the highest-scoring zone
- Zones with zero visits are included with `visit_count: 0`, `visit_score: 0`

---

## 5. Anomaly Detection

### `GET /stores/{store_id}/anomalies`

Returns currently active anomalies for the store. Each anomaly includes severity and a suggested operational action.

**Path Parameters**

| Parameter | Type | Description |
|-----------|------|-------------|
| `store_id` | string | Store identifier |

**Response — 200 OK**

```json
{
  "store_id": "STORE_BLR_002",
  "checked_at": "2026-04-10T18:45:00Z",
  "active_anomalies": [
    {
      "anomaly_id": "anm_001",
      "type": "BILLING_QUEUE_SPIKE",
      "severity": "CRITICAL",
      "detected_at": "2026-04-10T18:32:00Z",
      "description": "Billing queue depth is 9 (threshold: 5). Queue has been elevated for 8 minutes.",
      "suggested_action": "Open an additional billing counter immediately. Current queue will clear in ~12 minutes at current service rate.",
      "metadata": {
        "current_depth": 9,
        "threshold": 5,
        "elevated_since_ms": 480000
      }
    },
    {
      "anomaly_id": "anm_002",
      "type": "DEAD_ZONE",
      "severity": "INFO",
      "detected_at": "2026-04-10T18:10:00Z",
      "description": "Zone BATH_BODY has had no customer visits for 35 minutes during open hours.",
      "suggested_action": "Consider repositioning promotional display or having staff engage customers near Bath & Body zone.",
      "metadata": {
        "zone_id": "BATH_BODY",
        "no_visit_duration_ms": 2100000
      }
    }
  ],
  "anomaly_count": 2
}
```

**Anomaly Types:**

| Type | Trigger | Default Severity |
|------|---------|-----------------|
| `BILLING_QUEUE_SPIKE` | queue_depth > 5 for > 3 min | WARN; CRITICAL if > 10 |
| `CONVERSION_DROP` | Rate < 70% of 7-day rolling avg | WARN |
| `DEAD_ZONE` | No zone visits for 30+ min during open hours | INFO |
| `STALE_FEED` | No events from camera for > 10 min | WARN |
| `ABANDONMENT_SPIKE` | Queue abandonment > 30% of billing entries | WARN |

**Response — 200 OK (no anomalies)**

```json
{
  "store_id": "STORE_BLR_002",
  "checked_at": "2026-04-10T18:45:00Z",
  "active_anomalies": [],
  "anomaly_count": 0
}
```

---

## 6. Health Check

### `GET /health`

Returns service health status, last event timestamp per store, and any stale feed warnings. This is the first endpoint an on-call engineer checks.

**Response — 200 OK (healthy)**

```json
{
  "status": "healthy",
  "checked_at": "2026-04-10T18:45:00Z",
  "database": "connected",
  "redis": "connected",
  "stores": [
    {
      "store_id": "STORE_BLR_002",
      "last_event_at": "2026-04-10T18:44:48Z",
      "lag_seconds": 12,
      "feed_status": "OK"
    },
    {
      "store_id": "STORE_BLR_003",
      "last_event_at": "2026-04-10T18:23:15Z",
      "lag_seconds": 1305,
      "feed_status": "STALE_FEED"
    }
  ],
  "uptime_seconds": 43200
}
```

**Response — 503 Service Unavailable (degraded)**

```json
{
  "status": "degraded",
  "checked_at": "2026-04-10T18:45:00Z",
  "database": "disconnected",
  "redis": "connected",
  "error": "DATABASE_UNAVAILABLE",
  "trace_id": "trc_9f2a1c"
}
```

**Feed Status Values:**

| Status | Meaning |
|--------|---------|
| `OK` | Events received within the last 10 minutes |
| `STALE_FEED` | No events received for > 10 minutes |
| `NO_DATA` | Store has never sent events |

---

## 7. Error Codes Reference

| HTTP Status | Error Code | Meaning |
|-------------|------------|---------|
| 400 | `VALIDATION_ERROR` | Request body fails schema validation |
| 404 | `STORE_NOT_FOUND` | `store_id` does not exist in the system |
| 422 | `INVALID_EVENT_TYPE` | `event_type` not in allowed catalogue |
| 503 | `DATABASE_UNAVAILABLE` | Storage layer unreachable |
| 503 | `REDIS_UNAVAILABLE` | Cache layer unreachable |

All error responses follow the structure:

```json
{
  "error": "<ERROR_CODE>",
  "detail": "<human-readable description>",
  "trace_id": "<request trace ID>"
}
```

Raw stack traces are **never** included in API responses.

---

## 8. WebSocket — Live Dashboard Feed

### `WS /ws/stores/{store_id}`

Pushes metric updates in real time as events are ingested. Used by the Part E live dashboard.

**Message Format (server → client)**

```json
{
  "type": "METRIC_UPDATE",
  "store_id": "STORE_BLR_002",
  "timestamp": "2026-04-10T18:45:02Z",
  "metrics": {
    "unique_visitors": 88,
    "conversion_rate": 0.35,
    "current_queue_depth": 3,
    "active_anomaly_count": 1
  }
}
```

**Message Types:**

| Type | Trigger |
|------|---------|
| `METRIC_UPDATE` | Any new event ingested |
| `ANOMALY_ALERT` | New anomaly detected or severity escalated |
| `FEED_STATUS` | Feed becomes stale or recovers |
