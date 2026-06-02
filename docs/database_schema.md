# Database Schema — Store Intelligence System
## Purplle Tech Challenge 2026 · Round 2

---

## 1. Overview

The database is **PostgreSQL 16** (with SQLite supported for development via `aiosqlite`). The schema is designed around three primary concerns:

1. **Raw event storage** — immutable append-only log of all detection events
2. **Session aggregation** — derived visitor sessions from raw events
3. **POS correlation** — transaction matching for conversion computation

All tables use `TIMESTAMPTZ` for timestamps (UTC enforced). The `events` table is the source of truth; all metrics are computed from it at query time (with Redis caching for performance).

---

## 2. Schema Diagram

```
┌─────────────────────┐       ┌──────────────────────────┐
│       stores        │       │         events            │
│─────────────────────│       │──────────────────────────│
│ store_id (PK)       │◄──────│ event_id (PK)             │
│ store_name          │       │ store_id (FK)             │
│ city                │       │ camera_id                 │
│ open_time           │       │ visitor_id                │
│ close_time          │       │ event_type                │
│ timezone            │       │ timestamp                 │
│ layout_json         │       │ zone_id                   │
│ created_at          │       │ dwell_ms                  │
└─────────────────────┘       │ is_staff                  │
                              │ confidence                │
                              │ metadata (JSONB)          │
                              │ ingested_at               │
                              └──────────────────────────┘
                                         │
                    ┌────────────────────┼──────────────────────┐
                    │                   │                       │
                    ▼                   ▼                       ▼
     ┌──────────────────┐  ┌───────────────────┐  ┌──────────────────────┐
     │     sessions     │  │   zone_visits     │  │  pos_transactions    │
     │──────────────────│  │───────────────────│  │──────────────────────│
     │ session_id (PK)  │  │ zone_visit_id(PK) │  │ transaction_id (PK)  │
     │ visitor_id       │  │ session_id (FK)   │  │ store_id (FK)        │
     │ store_id (FK)    │  │ zone_id           │  │ timestamp            │
     │ entry_at         │  │ enter_at          │  │ basket_value_inr     │
     │ exit_at          │  │ exit_at           │  │ correlated_session   │
     │ is_converted     │  │ dwell_ms          │  │ ingested_at          │
     │ reentry_count    │  └───────────────────┘  └──────────────────────┘
     │ session_seq      │
     └──────────────────┘
```

---

## 3. Table Definitions

### 3.1 `stores`

Stores the reference data for each physical retail store.

```sql
CREATE TABLE stores (
    store_id        VARCHAR(20)     PRIMARY KEY,
    store_name      VARCHAR(100)    NOT NULL,
    city            VARCHAR(50)     NOT NULL,
    open_time       TIME            NOT NULL DEFAULT '10:00:00',
    close_time      TIME            NOT NULL DEFAULT '22:00:00',
    timezone        VARCHAR(50)     NOT NULL DEFAULT 'Asia/Kolkata',
    layout_json     JSONB,          -- full store_layout.json content
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

-- Index for city-level queries
CREATE INDEX idx_stores_city ON stores (city);
```

**Sample data (Brigade Road):**

```sql
INSERT INTO stores (store_id, store_name, city, open_time, close_time, timezone)
VALUES ('STORE_BLR_002', 'Brigade Road Bangalore', 'Bangalore', '10:00', '22:00', 'Asia/Kolkata');
```

---

### 3.2 `events`

The core immutable append-only event log. Every detection event from the pipeline lands here. This is the source of truth for all analytics.

```sql
CREATE TABLE events (
    event_id        UUID            PRIMARY KEY,
    store_id        VARCHAR(20)     NOT NULL REFERENCES stores(store_id),
    camera_id       VARCHAR(50)     NOT NULL,
    visitor_id      VARCHAR(20)     NOT NULL,
    event_type      VARCHAR(30)     NOT NULL,
    timestamp       TIMESTAMPTZ     NOT NULL,
    zone_id         VARCHAR(50),
    dwell_ms        INTEGER         NOT NULL DEFAULT 0,
    is_staff        BOOLEAN         NOT NULL DEFAULT FALSE,
    confidence      NUMERIC(4,3)    NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    metadata        JSONB           NOT NULL DEFAULT '{}',
    ingested_at     TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_event_type CHECK (
        event_type IN (
            'ENTRY', 'EXIT', 'ZONE_ENTER', 'ZONE_EXIT', 'ZONE_DWELL',
            'BILLING_QUEUE_JOIN', 'BILLING_QUEUE_ABANDON', 'REENTRY'
        )
    ),
    CONSTRAINT chk_dwell_ms CHECK (dwell_ms >= 0),
    CONSTRAINT chk_zone_for_type CHECK (
        -- ENTRY and EXIT do not require a zone_id
        (event_type IN ('ENTRY', 'EXIT', 'REENTRY') AND zone_id IS NULL)
        OR
        (event_type NOT IN ('ENTRY', 'EXIT', 'REENTRY') AND zone_id IS NOT NULL)
    )
);

-- Primary query pattern: store + time range + event type
CREATE INDEX idx_events_store_time     ON events (store_id, timestamp DESC);
CREATE INDEX idx_events_visitor        ON events (visitor_id, timestamp);
CREATE INDEX idx_events_type_store     ON events (event_type, store_id);
CREATE INDEX idx_events_zone_store     ON events (zone_id, store_id) WHERE zone_id IS NOT NULL;
CREATE INDEX idx_events_staff          ON events (is_staff, store_id);

-- For ingestion deduplication (covered by PK, but explicit for clarity)
-- event_id is already the PK; ON CONFLICT DO NOTHING handles idempotency
```

**Idempotency at ingest:**

```sql
INSERT INTO events (event_id, store_id, camera_id, visitor_id, event_type, ...)
VALUES ($1, $2, $3, $4, $5, ...)
ON CONFLICT (event_id) DO NOTHING;
```

---

### 3.3 `sessions`

Derived sessions computed from ENTRY/EXIT event pairs. Updated incrementally as events arrive. One row per visitor visit session (a re-entry creates a new row with the same `visitor_id`).

```sql
CREATE TABLE sessions (
    session_id      UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    visitor_id      VARCHAR(20)     NOT NULL,
    store_id        VARCHAR(20)     NOT NULL REFERENCES stores(store_id),
    entry_at        TIMESTAMPTZ     NOT NULL,
    exit_at         TIMESTAMPTZ,                -- NULL if session still open
    is_converted    BOOLEAN         NOT NULL DEFAULT FALSE,
    reentry_count   SMALLINT        NOT NULL DEFAULT 0,
    session_seq     SMALLINT        NOT NULL DEFAULT 1, -- 1 = first visit, 2 = re-entry

    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

-- Core query: all sessions for a store in a date range
CREATE INDEX idx_sessions_store_entry  ON sessions (store_id, entry_at DESC);
CREATE INDEX idx_sessions_visitor      ON sessions (visitor_id, store_id);
CREATE INDEX idx_sessions_converted    ON sessions (store_id, is_converted, entry_at);
```

---

### 3.4 `zone_visits`

Individual zone visit records linked to a session. Used for heatmap computation and funnel stage 2.

```sql
CREATE TABLE zone_visits (
    zone_visit_id   UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID            NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    store_id        VARCHAR(20)     NOT NULL REFERENCES stores(store_id),
    zone_id         VARCHAR(50)     NOT NULL,
    enter_at        TIMESTAMPTZ     NOT NULL,
    exit_at         TIMESTAMPTZ,                -- NULL if still in zone
    dwell_ms        INTEGER         GENERATED ALWAYS AS (
                        CASE 
                            WHEN exit_at IS NOT NULL 
                            THEN EXTRACT(EPOCH FROM (exit_at - enter_at)) * 1000 
                            ELSE NULL 
                        END
                    ) STORED,

    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_zone_visits_session   ON zone_visits (session_id);
CREATE INDEX idx_zone_visits_store_zone ON zone_visits (store_id, zone_id, enter_at DESC);
```

---

### 3.5 `pos_transactions`

POS transaction records loaded from the Brigade Road CSV. Used for conversion rate computation.

```sql
CREATE TABLE pos_transactions (
    transaction_id      VARCHAR(30)     PRIMARY KEY,
    store_id            VARCHAR(20)     NOT NULL REFERENCES stores(store_id),
    timestamp           TIMESTAMPTZ     NOT NULL,
    basket_value_inr    NUMERIC(10,2)   NOT NULL CHECK (basket_value_inr >= 0),
    correlated_session  UUID            REFERENCES sessions(session_id),
    -- correlated_session populated when a billing-zone visitor is matched
    ingested_at         TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_pos_store_time     ON pos_transactions (store_id, timestamp DESC);
CREATE INDEX idx_pos_correlation    ON pos_transactions (correlated_session) WHERE correlated_session IS NOT NULL;
```

**POS Correlation Logic (SQL):**

```sql
-- Find sessions whose visitor was in the billing zone within 5 minutes before a transaction
UPDATE pos_transactions pt
SET correlated_session = s.session_id
FROM sessions s
JOIN zone_visits zv ON zv.session_id = s.session_id
WHERE pt.store_id = s.store_id
  AND zv.zone_id = 'BILLING'
  AND zv.enter_at BETWEEN pt.timestamp - INTERVAL '5 minutes' AND pt.timestamp
  AND pt.correlated_session IS NULL
ORDER BY zv.enter_at DESC
LIMIT 1;
```

---

### 3.6 `anomaly_log`

Persistent log of anomalies detected. Active anomalies are those with `resolved_at IS NULL`.

```sql
CREATE TABLE anomaly_log (
    anomaly_id      UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    store_id        VARCHAR(20)     NOT NULL REFERENCES stores(store_id),
    anomaly_type    VARCHAR(40)     NOT NULL,
    severity        VARCHAR(10)     NOT NULL CHECK (severity IN ('INFO', 'WARN', 'CRITICAL')),
    detected_at     TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    resolved_at     TIMESTAMPTZ,
    metadata        JSONB           NOT NULL DEFAULT '{}',
    suggested_action TEXT
);

CREATE INDEX idx_anomaly_store_active  ON anomaly_log (store_id, resolved_at) WHERE resolved_at IS NULL;
CREATE INDEX idx_anomaly_type          ON anomaly_log (anomaly_type, store_id);
```

---

## 4. Key Analytical Queries

### 4.1 Unique Visitors Today (Excluding Staff)

```sql
SELECT COUNT(DISTINCT visitor_id) AS unique_visitors
FROM events
WHERE store_id = $1
  AND timestamp >= DATE_TRUNC('day', NOW())
  AND event_type = 'ENTRY'
  AND is_staff = FALSE;
```

### 4.2 Conversion Rate

```sql
WITH
  total_visitors AS (
    SELECT COUNT(DISTINCT visitor_id) AS cnt
    FROM events
    WHERE store_id = $1
      AND timestamp >= DATE_TRUNC('day', NOW())
      AND event_type = 'ENTRY'
      AND is_staff = FALSE
  ),
  converted AS (
    SELECT COUNT(DISTINCT s.visitor_id) AS cnt
    FROM sessions s
    JOIN pos_transactions pt ON pt.correlated_session = s.session_id
    WHERE s.store_id = $1
      AND s.entry_at >= DATE_TRUNC('day', NOW())
  )
SELECT
  COALESCE(converted.cnt, 0)::FLOAT / NULLIF(total_visitors.cnt, 0) AS conversion_rate,
  total_visitors.cnt,
  converted.cnt
FROM total_visitors, converted;
```

### 4.3 Zone Dwell Average (for Heatmap)

```sql
SELECT
  zone_id,
  COUNT(*)                        AS visit_count,
  AVG(dwell_ms)                   AS avg_dwell_ms,
  MAX(dwell_ms)                   AS max_dwell_ms
FROM zone_visits zv
JOIN sessions s ON s.session_id = zv.session_id
WHERE zv.store_id = $1
  AND zv.enter_at >= NOW() - ($2 || ' minutes')::INTERVAL
GROUP BY zone_id
ORDER BY visit_count DESC;
```

### 4.4 Funnel Stages

```sql
-- Stage counts for the funnel endpoint
SELECT
  COUNT(DISTINCT s.session_id) FILTER (WHERE TRUE)                    AS entry_sessions,
  COUNT(DISTINCT s.session_id) FILTER (WHERE zv.zone_id IS NOT NULL)  AS zone_visit_sessions,
  COUNT(DISTINCT s.session_id) FILTER (WHERE billing.session_id IS NOT NULL) AS billing_sessions,
  COUNT(DISTINCT s.session_id) FILTER (WHERE s.is_converted)         AS purchase_sessions
FROM sessions s
LEFT JOIN zone_visits zv          ON zv.session_id = s.session_id
LEFT JOIN zone_visits billing     ON billing.session_id = s.session_id AND billing.zone_id = 'BILLING'
WHERE s.store_id = $1
  AND s.entry_at >= $2
  AND s.entry_at < $3;
```

---

## 5. Migrations

Managed with **Alembic**. Migration files live in `app/db/migrations/versions/`.

```
alembic upgrade head    # apply all migrations
alembic downgrade -1    # roll back one version
alembic revision --autogenerate -m "add anomaly_log"
```

Initial migration creates all tables in dependency order:
1. `stores`
2. `events`
3. `sessions`
4. `zone_visits`
5. `pos_transactions`
6. `anomaly_log`

---

## 6. Development vs Production

| Setting | Development | Production |
|---------|-------------|------------|
| Engine | SQLite (aiosqlite) | PostgreSQL 16 |
| Connection | `sqlite+aiosqlite:///./dev.db` | `postgresql+asyncpg://...` |
| Migrations | `alembic upgrade head` on startup | CI/CD pipeline |
| Index strategy | Basic | Full index set as above |
| Partitioning | None | Partition `events` by `(store_id, month)` |
| TimescaleDB | No | Optional hypertable on `events(timestamp)` |

---

## 7. Redis Key Schema

| Key Pattern | Type | TTL | Purpose |
|-------------|------|-----|---------|
| `metrics:{store_id}:{date}` | Hash | 30s | Cached metrics response |
| `session:{visitor_id}:{store_id}` | Hash | 2h | Active session state |
| `queue_depth:{store_id}` | String | 60s | Current billing queue depth |
| `last_event:{store_id}` | String | None | Timestamp of last ingested event (health check) |
| `anomaly_state:{store_id}` | Hash | None | Active anomaly tracking |
