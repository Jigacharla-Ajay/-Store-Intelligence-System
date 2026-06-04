# Technical Choices & Trade-offs

## Language & Framework: Python 3.11 + FastAPI

**Why Python**: The detection pipeline uses YOLOv8 (ultralytics), OpenCV, and deep_sort — all Python-native. Using the same language for the API eliminates serialization overhead and simplifies deployment.

**Why FastAPI**: Native async/await support is critical for the event ingestion endpoint, which must handle high-throughput batches without blocking. FastAPI's Pydantic integration provides automatic request validation with detailed error messages, and the auto-generated OpenAPI documentation aids evaluator review.

**Trade-off**: Python's GIL limits CPU-bound concurrency. We mitigate this by running the detection pipeline in a separate container and keeping the API I/O-bound (database queries, Redis lookups).

## Database: PostgreSQL 16

**Why PostgreSQL**: ACID compliance is non-negotiable for an event store that serves as the source of truth. PostgreSQL's `ON CONFLICT DO NOTHING` enables our idempotent ingestion pattern without application-level locking. The JSONB column type stores flexible event metadata without schema migrations.

**Why not MongoDB**: While the event-sourcing pattern maps naturally to document stores, the relational queries for funnel analysis (JOIN across sessions, zone_visits, pos_transactions) would require complex aggregation pipelines. PostgreSQL handles both patterns well.

**Why not SQLite for production**: SQLite lacks concurrent write support, which is essential when the detection pipeline and dashboard are hitting the API simultaneously. We use SQLite only for local development and testing.

## Cache: Redis 7

**Why Redis**: Sub-millisecond reads for current queue depth, active sessions, and cached metric snapshots. The pub/sub capability will drive WebSocket push for the live dashboard.

**Trade-off**: Adds operational complexity. We make Redis optional — the API degrades gracefully to direct DB queries if Redis is unavailable, with the health endpoint reporting "degraded" status.

## ORM: SQLAlchemy 2.0 (Async)

**Why SQLAlchemy over raw SQL**: The async session management, connection pooling, and schema introspection reduce boilerplate significantly. The ORM models serve as both the schema definition and the data access layer.

**Why async**: The ingestion endpoint processes batches of up to 500 events. Async DB operations allow the event loop to handle concurrent requests while individual events are being inserted.

**Trade-off**: ORM queries are harder to optimize than raw SQL. For the metrics endpoint, we use SQLAlchemy Core (select/func) rather than ORM relationships to keep queries efficient.

## Event Architecture: Append-Only Log

**Why immutable events**: Events from the detection pipeline represent physical observations — they cannot be "corrected." By making the event table append-only with `ON CONFLICT DO NOTHING`, we guarantee data integrity across pipeline restarts, network retries, and duplicate deliveries.

**Session derivation**: Sessions are not stored by the pipeline. They are derived in the API from ENTRY/EXIT event pairs. This separation of concerns means the pipeline can be simple (just emit events) while the API handles the complex state machine.

**Trade-off**: Deriving sessions on-ingest adds latency to the ingestion endpoint (~30ms per batch). We accept this because ingestion is not latency-critical — the pipeline emits events in 1-second batches.

## Detection: YOLOv8 + DeepSORT

**Why YOLOv8**: Best accuracy-to-speed ratio for retail CCTV resolution (640x480). The `yolov8n` nano model runs at 30+ FPS on a T4 GPU, well within real-time requirements.

**Why DeepSORT**: Maintains consistent `visitor_id` across frames and camera angles. The appearance embedding handles partial occlusions common in retail environments (shelving, displays).

**Trade-off**: DeepSORT's re-identification fails for visitors who leave and re-enter the store (different lighting, angle). We handle this with the 60-second REENTRY window — if a new detection matches a recently-exited visitor within 60 seconds, it's treated as a re-entry rather than a new visitor.

## Zone Mapping: Polygon-Based

**Why polygon coordinates**: The store layout is defined as a set of named polygon zones (SKINCARE, MAKEUP, BATH_BODY, BILLING). Each camera's zone polygons are stored in `store_layout.json`. When a tracked person's centroid falls within a polygon, a ZONE_ENTER event is emitted.

**Trade-off**: Polygon zone mapping requires manual calibration per camera. We include a zone editor utility in the pipeline for initial setup.

## POS Correlation: 5-Minute Window

**Why 5 minutes**: Analysis of the real Brigade Road data shows that the average time between a customer's last zone visit and their POS transaction is 3-4 minutes (walking to billing, waiting in queue, payment processing). A 5-minute window captures 95%+ of correlated transactions while minimizing false positives.

## Testing Strategy

**Why integration tests over unit tests**: The business logic (metrics, funnel, heatmap) is tightly coupled to database queries. Mocking SQLAlchemy sessions would test the mock, not the logic. Our integration tests use a real SQLite database and the full ASGI transport to exercise the complete request-response cycle.

**Coverage target: 65%+**: We prioritize testing the critical paths (ingestion idempotency, session lifecycle, staff exclusion) over achieving 100% coverage. The excluded files are Pydantic models (schema-only, no logic) and the standalone seeder (tested manually).
