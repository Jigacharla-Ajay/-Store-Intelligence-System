# Project Plan — Store Intelligence System
## Purplle Tech Challenge 2026 · Round 2 | 48-Hour Execution Plan

---

## 1. Objectives

Build and deliver a complete Store Intelligence Pipeline for the Brigade Road, Bangalore Purplle store (ST1008) within the 48-hour challenge window, targeting a score of **85+/110**.

**Scoring target breakdown:**

| Part | Max | Target | Priority |
|------|-----|--------|----------|
| A — Detection Pipeline | 30 | 26 | High |
| B — Intelligence API | 35 | 30 | Critical |
| C — Production Readiness | 20 | 18 | High |
| D — AI Engineering | 15 | 13 | Medium |
| E — Live Dashboard (bonus) | +10 | +8 | Medium |
| **Total** | **110** | **95** | |

---

## 2. 48-Hour Timeline

### Hour 0–4: Foundation (Setup + Scaffolding)

**Goals:** Docker working, DB migrations running, `/health` returning 200.

| Task | Owner | Duration | Output |
|------|-------|----------|--------|
| Set up repo structure (pipeline/, app/, tests/, docs/) | Dev | 30 min | Git repo |
| Write `docker-compose.yml` (postgres, redis, api, dashboard) | Dev | 30 min | `docker compose up` works |
| Create SQLAlchemy models (stores, events, sessions, zone_visits, pos_transactions, anomaly_log) | Dev | 45 min | ORM models |
| Write Alembic migrations | Dev | 30 min | `alembic upgrade head` passes |
| Implement FastAPI skeleton (`main.py`, all routers return 501 stubs) | Dev | 45 min | API boots |
| Implement `GET /health` (DB check, Redis check, uptime) | Dev | 30 min | 200 response |
| Seed POS data from Brigade_Bangalore CSV | Dev | 30 min | 101 transactions in DB |

**Acceptance check:** `docker compose up && curl localhost:8000/health` → `{"status":"healthy"}`

---

### Hour 4–12: Detection Pipeline (Part A)

**Goals:** Pipeline produces valid event JSONL from a sample clip.

| Task | Owner | Duration | Output |
|------|-------|----------|--------|
| Install YOLOv8 + ByteTrack in pipeline Dockerfile | Dev | 45 min | `detect.py` imports work |
| Implement `detect.py` — frame iteration, YOLOv8 inference, ByteTrack | Dev | 2h | bounding boxes + track_ids |
| Implement `zone_mapper.py` — centroid to zone_id mapping | Dev | 1h | zone assignments |
| Implement `emit.py` — build canonical event dict, write JSONL | Dev | 45 min | valid event schema |
| Implement direction detection (ENTRY/EXIT) from trajectory | Dev | 1h | ENTRY/EXIT events emitted |
| Implement staff classifier (colour-range on uniform) | Dev | 1h | `is_staff` flag set |
| Run pipeline on sample clip — validate against `sample_events.jsonl` | Dev | 1h | Schema validation pass |
| Test with `assertions.py` | Dev | 30 min | ≥ 7/10 assertions pass |

**Acceptance check:** `python pipeline/run.sh clips/sample/ --output events.jsonl` → valid JSONL

---

### Hour 12–20: Core API Endpoints (Part B)

**Goals:** All 5 endpoints returning correct data from ingested events.

| Task | Owner | Duration | Output |
|------|-------|----------|--------|
| Implement `POST /events/ingest` — validate, dedup, persist, session update | Dev | 2h | Idempotent ingest working |
| Implement `GET /stores/{id}/metrics` — visitors, conversion, dwell, queue | Dev | 2h | Metrics from real events |
| Implement `GET /stores/{id}/funnel` — session-based funnel, drop-off % | Dev | 1.5h | Funnel stages correct |
| Implement `GET /stores/{id}/heatmap` — zone frequency, 0–100 normalisation | Dev | 1h | Heatmap data correct |
| Implement `GET /stores/{id}/anomalies` — queue spike, conversion drop, dead zone | Dev | 1.5h | Anomalies detected |
| Verify Re-ID-based REENTRY deduplication in funnel | Dev | 30 min | No double-counting |

**Acceptance check:** Ingest 200 events from JSONL → `/metrics`, `/funnel`, `/heatmap` all return plausible values.

---

### Hour 20–26: Re-ID and Edge Cases (Part A polish)

**Goals:** Handle all 7 known edge cases from the footage spec.

| Edge Case | Implementation | Time |
|-----------|---------------|------|
| Group entry | Confirm ByteTrack assigns separate track_ids to simultaneous entrants | 1h |
| Staff exclusion | Validate staff events excluded from `/metrics`; add test | 30 min |
| Re-entry handling | Implement `reentry.py` with OSNet embeddings or bbox trajectory fallback | 2h |
| Partial occlusion | Tune confidence threshold; log low-confidence events rather than drop | 30 min |
| Billing queue | Implement queue depth tracking from concurrent billing zone occupants | 1h |
| Empty store periods | Verify `/metrics` returns 0 counts (not null, not crash) | 30 min |
| Cross-camera dedup | Implement embedding match across CAM_ENTRY / CAM_FLOOR within 3s window | 1h |

---

### Hour 26–32: Production Hardening (Part C)

**Goals:** 70%+ test coverage, structured logging, graceful errors.

| Task | Duration | Output |
|------|----------|--------|
| Write tests: `test_ingest.py` (idempotency, partial success, schema validation) | 1.5h | 8+ test cases |
| Write tests: `test_metrics.py` (zero visitors, all-staff, zero purchases) | 1h | 6+ test cases |
| Write tests: `test_funnel.py` (re-entry dedup, empty store) | 1h | 5+ test cases |
| Write tests: `test_anomalies.py` (queue spike, dead zone, conversion drop) | 45 min | 5+ test cases |
| Implement `RequestLoggingMiddleware` (trace_id, latency_ms, store_id) | 45 min | JSON logs in stdout |
| Implement `register_error_handlers` (DB down → 503, no stack traces) | 30 min | Structured error responses |
| Verify `docker compose up` clean start on fresh machine | 30 min | All services healthy |
| Verify README completeness (≤ 5 commands to running state) | 30 min | README.md complete |

**Acceptance check:** `pytest --cov=app --cov-fail-under=70` → passes

---

### Hour 32–38: AI Engineering Documentation (Part D)

**Goals:** DESIGN.md and CHOICES.md score 13+/15.

| Task | Duration | Output |
|------|----------|--------|
| Write `DESIGN.md` — plain-language architecture, data flow diagram (ASCII), "AI-Assisted Decisions" section (3 decisions) | 1.5h | > 400 words |
| Write `CHOICES.md` — 3 decisions (detection model, event schema, API architecture): options considered, AI suggestion, what was chosen + why | 1.5h | > 400 words |
| Add `# PROMPT: ... / # CHANGES MADE: ...` blocks to all test files | 30 min | Prompt blocks present |
| Document VLM usage (if used) with prompt text in DESIGN.md | 30 min | VLM rationale documented |

**Key differentiator:** Document one place where the AI suggestion was **overridden** and why. Reviewers score this higher than generic acceptance.

---

### Hour 38–44: Live Dashboard (Part E — bonus)

**Goals:** At least one metric updating live as events flow.

| Task | Duration | Output |
|------|----------|--------|
| Add WebSocket endpoint to FastAPI (`/ws/stores/{id}`) | 45 min | WS endpoint |
| Set up React project in `dashboard/` with Dockerfile | 30 min | Dashboard builds |
| Implement `useStoreWebSocket` hook | 30 min | Live data in browser |
| Build `MetricCard` (live visitor count) | 30 min | Updates on new events |
| Build `FunnelChart` (Recharts bar chart) | 45 min | Funnel visualised |
| Build `ZoneHeatmap` (CSS grid, colour-coded by score) | 1h | Heatmap renders |
| Build `AnomalyBanner` (live anomaly alerts) | 30 min | Alerts show live |
| Test end-to-end: run pipeline → events appear in dashboard | 30 min | Proof of live connection |

---

### Hour 44–48: Final Validation and Submission

**Goals:** Clean submission passing all acceptance gate checks.

| Task | Duration |
|------|----------|
| `docker compose down && docker compose up` on clean environment | 30 min |
| Run full detection pipeline against provided clips | 30 min |
| Ingest generated events into API | 15 min |
| Verify `GET /stores/STORE_BLR_002/metrics` returns valid JSON | 5 min |
| Run `pytest --cov=app` → confirm ≥ 70% | 15 min |
| Review DESIGN.md and CHOICES.md word counts (> 250 each) | 15 min |
| Verify all prompt blocks present in test files | 10 min |
| Final README review (≤ 5 commands, detection run instructions) | 15 min |
| Push to private git repo | 5 min |
| Submit repo link via challenge email | 5 min |

---

## 3. Risk Register

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| YOLOv8 inference too slow on CPU | Medium | High | Pre-process clips offline; use frame subsampling (every 3rd frame) |
| Re-ID quality poor with face blur | Medium | Medium | Fall back to bounding box size/trajectory similarity |
| Cross-camera dedup complex | High | Medium | Implement time-window matching first; embedding matching as enhancement |
| Docker GPU pass-through fails | High | Low | Pipeline runs in CPU mode (slower but correct) |
| POS correlation ambiguous | Low | Medium | 5-min window is generous; document assumption in CHOICES.md |
| Test coverage < 70% | Low | High | Write tests in parallel with implementation; cover edge cases first |

---

## 4. Dependency Map

```
[Docker Compose] ──requires──▶ [DB Migrations] ──requires──▶ [ORM Models]
                                      │
                                      ▼
[POST /events/ingest] ──requires──▶ [Event Schema (Pydantic)]
         │
         ▼
[GET /metrics] ──requires──▶ [Session State Logic]
[GET /funnel]  ──requires──▶ [Session State Logic]
[GET /heatmap] ──requires──▶ [Zone Visit Records]
[GET /anomalies] ──requires──▶ [Metrics baseline data]
         │
         ▼
[Dashboard WS] ──requires──▶ [POST /events/ingest working]
         │
         ▼
[Detection Pipeline] ──feeds──▶ [POST /events/ingest]
```

---

## 5. Submission Checklist

- [ ] `docker compose up` starts without manual steps
- [ ] README: setup in ≤ 5 commands
- [ ] README: how to run detection pipeline + feed into API
- [ ] `POST /events/ingest` returns non-5xx
- [ ] `GET /stores/STORE_BLR_002/metrics` returns valid JSON
- [ ] `DESIGN.md` > 250 words + "AI-Assisted Decisions" section
- [ ] `CHOICES.md` > 250 words covering all 3 required decisions
- [ ] Prompt blocks at top of every test file
- [ ] `pytest --cov=app --cov-fail-under=70` passes
- [ ] If Part E: `http://localhost:3000` noted in README
- [ ] Private repo with reviewer handle invited
- [ ] No API keys or secrets committed
- [ ] CCTV footage not committed to repo (add to .gitignore)
