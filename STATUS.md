## Phase 2C — WebSocket + Alert System Hardening

### Completed

**Event Durability + Replay (Task 1):**
- `services/stream/event_store.py` — persists events to Redis Streams with entity-based indexing
- `GET /api/v1/events/replay` — query by time range, entity_type, entity_id, event_type

**Deduplication (Task 2):**
- `services/stream/deduplication.py` — LRU cache (10k entries), hit rate tracking, mark_seen
- Integrated into `ws/manager.py` — duplicates dropped before broadcast

**WS Ordering Guarantee (Task 3):**
- `sequence` field added to every event at broadcast time
- Per-connection sequence counter via `_sequences` dict
- Extended event format: `{event_id, sequence, entity_type, entity_id, timestamp, payload}`

**Latency Measurement (Task 4):**
- `services/monitoring/latency_service.py` — histogram buckets per metric, p50/p95/p99, 1m + 15m windows
- Tracks: fill_latency, fill_processing, snapshot_generation, ws_emission, replay_query
- `GET /api/v1/events/monitoring/latency` endpoint

**Alert System Hardening (Task 5):**
- Entity-level cooldowns (per rule/entity)
- Severity escalation: info → warning → critical every 3 fires
- 5-second spam dedup window per entity+rule
- Alert lifecycle: triggered → acknowledged → resolved
- `resolve_all_for_entity()` for bulk resolution
- `get_stats()` for observability
- Alerts persisted to event store

**WS Resilience Layer (Task 6):**
- `useWebSocket` hook: gap detection via `shouldRefetchOnGap()`, 10s disconnect → auto-refetch
- `useLivePortfolio`: integrated with `eventApplier`, sequence gap → snapshot refetch
- Silent recovery mode (no UI flicker) — state merges via applier

**Event Applier Engine (Task 7):**
- `lib/eventApplier.ts` — pure functions: fill.created updates positions, order.updated merges orders, portfolio.snapshot replaces cache, pnl.updated merges into snapshot, alert.created dedup'd
- Deterministic, testable, 12 tests

**Observability Dashboard (Task 8):**
- WS connection count, dedup cache size, dedup hit rate, event throughput
- Latency panels (fill, snapshot, replay) with p50/p95/p99
- Debug mode: raw event stream, entity_type filter, pause/resume toggle
- Sequence numbers in event stream viewer

**Backpressure + Load Control (Task 9):**
- Server: `max_msgs_per_sec` per client, `_backpressure` tracking, batch window (50ms), batch_size limit
- Client: ignore stale UI updates via event applier's dedup, gap-based refetch throttling

**Tests (Task 10):**
- Backend: 127 passed (+22 new), 1 skipped (Redis)
- Frontend: 29 passed (+12 new eventApplier tests)
- `next build`: all 11 routes compile clean

### Test Results
```
Backend: 127 passed, 1 skipped, 0 failed  (11.64s)
Frontend: 29 passed, 0 failed  (3.85s)
Build: 11 routes, zero errors
```

### New/Modified Files
- `backend/app/services/stream/event_store.py` — EventStore + DedupCache
- `backend/app/services/stream/deduplication.py` — EventDeduplicator
- `backend/app/services/monitoring/latency_service.py` — LatencyTracker
- `backend/app/services/alerts/alert_service.py` — hardened (rewritten)
- `backend/app/services/execution/fill_handler.py` — +latency tracking
- `backend/app/ws/manager.py` — +sequence, dedup, backpressure, event_store
- `backend/app/api/events.py` — replay + latency + ws-stats endpoints
- `backend/app/api/router.py` — +events router
- `frontend/lib/eventApplier.ts` — deterministic state update engine
- `frontend/lib/ws.ts` — (unchanged)
- `frontend/hooks/useWebSocket.ts` — +gap detection, disconnect recovery
- `frontend/hooks/useLivePortfolio.ts` — +eventApplier, sequence gap refetch
- `frontend/app/monitoring/page.tsx` — full observability expansion
- `backend/app/tests/test_phase2c.py` — dedup + latency tests
- `backend/app/tests/test_alert_hardening.py` — alert service tests
- `frontend/__tests__/eventApplier.test.ts` — applier tests
