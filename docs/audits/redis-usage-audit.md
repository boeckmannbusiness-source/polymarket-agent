# Redis / Upstash Usage Audit

**Date:** 2026-07-09
**Project:** Polymarket Intelligence Agent
**Auditor:** OpenCode
**Context:** Upstash Redis cost ~$194/month triggered this audit. Goal is to remove unnecessary managed Redis dependency and prepare for self-hosted Valkey.

---

## Executive Summary

Redis is **required** for the core event bus (streams + pub/sub). However, ~70% of Redis consumers are **optional** with graceful fallbacks already implemented. The remaining critical path (`trade_service.py` fail-closed on `remote:state`) can be isolated behind a `StateStore` abstraction.

**Recommendation:** Keep Redis for the event bus; isolate behind interface; prepare Valkey migration path.

---

## 1. Current Redis Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Python Backend                           │
│                                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────┐ │
│  │ EventBus │  │ State    │  │ Cache    │  │ Control    │ │
│  │ (streams │  │ Store    │  │ Services │  │ Plane      │ │
│  │ + pubsub)│  │ (KV)     │  │          │  │            │ │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └─────┬──────┘ │
│       │              │             │               │         │
│       └──────────┬───┴─────────────┴───────────────┘         │
│                  │                                           │
│         ┌────────▼────────┐                                  │
│         │  Redis Client   │  (Singleton pool, max 8 conn)    │
│         │  redis-py 5.2+  │                                  │
│         └────────┬────────┘                                  │
└──────────────────┼───────────────────────────────────────────┘
                   │
    ┌──────────────┼──────────────┐
    │              │              │
┌───▼────┐  ┌─────▼─────┐  ┌────▼────┐
│ Upstash│  │ Self-host │  │ Valkey  │
│ Redis  │  │ Redis     │  │ (future)│
│ (CURRENT) │ (docker)  │  │         │
└────────┘  └───────────┘  └─────────┘

┌──────────────────────────────────────────────┐
│              TypeScript Remote Control         │
│                                                │
│  ┌──────────────┐  ┌──────────────────┐       │
│  │ remoteState  │  │ commandHandler    │       │
│  │ (ioredis)    │  │ (ioredis)        │       │
│  └──────┬───────┘  └───────┬──────────┘       │
│         │                  │                   │
│  ┌──────▼──────────────────▼──────────┐        │
│  │        Redis (separate clients)    │        │
│  └────────────────────────────────────┘        │
└──────────────────────────────────────────────┘
```

### 1.1 Python Redis Client

| File | Details |
|------|---------|
| `backend/app/redis.py` | Singleton `_BlockingPool` (extends `ConnectionPool`), max 8 connections, decode_responses, retry-on-timeout, 10s connect timeout, 30s socket timeout |
| `backend/app/redis.py:37` | `close_redis()` — pool teardown on shutdown |

### 1.2 TypeScript Redis Clients

| File | Details | Purpose |
|------|---------|---------|
| `src/remote/remoteState.ts` | `ioredis` with lazy connect, TLS support, exponential backoff retry (max 10 attempts) | Read/write `remote:state` (trading kill switch) |
| `src/remote/commandHandler.ts` | `ioredis` instantiated at module level | Audit logging (`XADD remote:audit`), close-confirm tokens |
| `src/remote/telegramBot.ts` | `ioredis` instantiated at module level | Blocking `XREAD` on `remote:notifications` stream |

---

## 2. Complete Redis Consumer Inventory

### 2.1 Critical Consumers (Category C: Requires Redis-compatible store)

#### C1. Event Bus — Streams

| File:Line | Operation | Purpose |
|-----------|-----------|---------|
| `backend/app/core/events.py:76-82` | `XADD` (with maxlen trim) | Publish events to streams |
| `backend/app/core/events.py:94` | `XGROUP_CREATE` | Create consumer groups on subscribe |
| `backend/app/core/events.py:104` | `XREADGROUP` | Read messages as consumer group member |
| `backend/app/core/events.py:118` | `XPENDING_RANGE` | Read pending (unacked) messages |
| `backend/app/core/events.py:124` | `XRANGE` | Fetch specific message by ID |
| `backend/app/core/events.py:139` | `XACK` | Ack processed messages |

**Criticality:** HIGH — Entire inter-service communication depends on streams. No fallback exists.

**Streams in use:** `market:data`, `wallet:trade`, `signal:generated`, `trade:request`, `agent:event`, `system:dlq:pending`, `audit:log`, plus dynamic streams per consumer.

#### C2. Event Bus — Pub/Sub

| File:Line | Operation | Purpose |
|-----------|-----------|---------|
| `backend/app/core/events.py:71` | `PUBLISH` | Publish to dashboard channels |
| `backend/app/core/events.py:144-146` | `pubsub()`, `SUBSCRIBE` | Subscribe to channels |
| `backend/app/main.py:1129-1131` | `pubsub()`, `SUBSCRIBE`, `listen()` | WS-Redis bridge for real-time dashboard |

**Criticality:** HIGH — Real-time WebSocket dashboard depends on Redis PubSub for broadcasting market data, trades, signals, and alerts. No fallback.

**Channels:** `dashboard:markets`, `dashboard:whales`, `dashboard:signals`, `dashboard:trades`, `telegram:alerts`

#### C3. Remote State (Fail-Closed Kill Switch)

| File:Line | Operation | Purpose |
|-----------|-----------|---------|
| `backend/app/services/trade_service.py:81-83` | `GET remote:state` | Check if trading is enabled by remote control |
| `src/remote/remoteState.ts:75,95` | `GET` / `SET remote:state` | Read/write remote kill switch state |

**Criticality:** HIGH — `trade_service.py:90-96` raises `SystemHaltException` on Redis failure. This is **fail-closed**: ALL trading stops if Redis is unreachable.

#### C4. System Mode Persistence

| File:Line | Operation | Purpose |
|-----------|-----------|---------|
| `backend/app/core/system_mode.py:291-294` | `SET system:mode` (1h TTL) | Persist system mode |
| `backend/app/core/system_mode.py:301-304` | `GET system:mode` | Load system mode on startup |

**Criticality:** MEDIUM — Mode is also kept in local cache. On restart without Redis, defaults to `normal`. Mode transitions are also recorded to PostgreSQL.

---

### 2.2 Optional Consumers (Category B: Move to PostgreSQL/Local Memory)

#### B1. Control Plane State

| File:Line | Operation | Fallback |
|-----------|-----------|----------|
| `backend/app/services/control/control_plane.py:37,48,60` | `GET`/`SET` for trading_enabled, execution_mode | Local state fallback |
| `backend/app/services/control/control_plane.py:86,96,108,119` | `SISMEMBER`/`SADD`/`SREM`/`SMEMBERS` for paused strategies/markets | Local state fallback |

**Migration:** All operations have `_local_*` state. Can move entirely to in-memory + PostgreSQL.

#### B2. Circuit Breakers

| File:Line | Operation | Fallback |
|-----------|-----------|----------|
| `backend/app/services/risk/circuit_breakers.py:39,59,68,81` | `HGET`/`HSET`/`HDEL` for active breakers | Local `_local_trigger` fallback |

**Migration:** State is ephemeral (cooldown-based). In-memory is sufficient.

#### B3. Shadow Execution Persistence

| File:Line | Operation | Fallback |
|-----------|-----------|----------|
| `backend/app/services/shadow/shadow_execution_service.py:65-68` | `HKEYS`/`HGET` on `shadow:executions` | In-memory `_executions` dict |
| `backend/app/services/shadow/shadow_execution_service.py:80-84` | `HSET` shadow execution | Graceful skip on failure |
| `backend/app/services/shadow/shadow_execution_service.py:136-165` | `WATCH` + pipeline + `HSET` (optimistic lock) | Returns None |
| `backend/app/services/shadow/shadow_execution_service.py:189-227` | `WATCH` + pipeline + `HSET` (optimistic lock) | Returns None |
| `backend/app/services/shadow/shadow_execution_service.py:273,318-320` | `SMEMBERS`/`SADD` processed signal IDs | Local tracking |

**Migration:** Shadow data can be persisted to PostgreSQL. Optimistic locking with `WATCH` is a Redis-specific pattern that would need PostgreSQL `SELECT ... FOR UPDATE` or application-level versioning.

#### B4. Portfolio Cache

| File:Line | Operation | Fallback |
|-----------|-----------|----------|
| `backend/app/services/portfolio/portfolio_cache_service.py:37` | `GET` portfolio data | In-memory `_memory` dict |
| `backend/app/services/portfolio/portfolio_cache_service.py:61` | `SETEX` portfolio data | Graceful skip on failure |
| `backend/app/services/portfolio/portfolio_cache_service.py:72` | `DELETE` | Graceful skip |

**Migration:** In-memory cache is already the primary. Redis is just a secondary tier. Can be removed entirely.

#### B5. Analytics Cache

| File:Line | Operation | Fallback |
|-----------|-----------|----------|
| `backend/app/services/shadow/shadow_analytics_service.py:38` | `GET` cached analytics | Returns None (recomputes) |
| `backend/app/services/shadow/shadow_analytics_service.py:50` | `SETEX` analytics (60s TTL) | Graceful skip |

**Migration:** 60s TTL cache — in-memory LRU is sufficient.

#### B6. Research Caches (5 files)

| File | Operation | Fallback |
|------|-----------|----------|
| `backend/app/services/research/signal_registry.py:19-20` | `_safe_redis()` → `get_redis()` | Lazy import, returns None on failure |
| `backend/app/services/research/strategy_registry.py:17-18` | Same pattern | Returns None |
| `backend/app/services/research/research_report_service.py:20-21` | Same pattern | Returns None |
| `backend/app/services/research/strategy_health_service.py:19-20` | Same pattern | Returns None |
| `backend/app/services/research/champion_challenger_service.py:19-20` | Same pattern | Returns None |

**Migration:** All use `try/except` with `_safe_redis()` returning `None`. Can be converted to local caches.

#### B7. Dedup Cache

| File:Line | Operation | Fallback |
|-----------|-----------|----------|
| `backend/app/core/dedup.py:14` | `EXISTS` dedup key | Returns False (allow-dupe) when `DEDUP_REDIS_ENABLED=False` |
| `backend/app/core/dedup.py:29` | `SETEX` dedup key (1h TTL) | Graceful skip |
| `backend/app/core/dedup.py:41` | `SCAN` count | Returns -1 |
| `backend/app/core/dedup.py:57-59` | `SCAN` + `DELETE` clear | Returns 0 |

**Migration:** Can move to in-memory LRU with TTL. Toggle `DEDUP_REDIS_ENABLED=False` already supported.

#### B8. Notification Stream

| File:Line | Operation | Fallback |
|-----------|-----------|----------|
| `backend/app/services/notification_service.py:57` | `XADD remote:notifications` (maxlen=1000) | Logs error, continues |
| `src/remote/telegramBot.ts:37` | `XREAD remote:notifications` | Retries after 5s on error |

**Migration:** Notifications can be sent directly via Telegram API or queued in PostgreSQL.

#### B9. Audit Stream

| File:Line | Operation | Fallback |
|-----------|-----------|----------|
| `src/remote/commandHandler.ts:73` | `XADD remote:audit` | Non-blocking; also persisted to DB via HTTP POST |
| `backend/app/services/audit/audit_logger.py:64` | Uses `get_redis()` for audit events | Graceful skip in most paths |

**Migration:** Already dual-persisted (Redis stream + HTTP POST to DB). Redis stream is expendable.

#### B10. Close-Confirm Tokens

| File:Line | Operation | Fallback |
|-----------|-----------|----------|
| `src/remote/commandHandler.ts:227` | `SET remote:closeall:token:{userId} EX 60` | 60s TTL tokens |
| `src/remote/commandHandler.ts:237` | `GET token` | Token validation |
| `src/remote/commandHandler.ts:245` | `DEL token` | Cleanup |

**Migration:** Could use HMAC-signed tokens (no storage needed) or in-memory Map with TTL.

---

### 2.3 Infrastructure Consumers (Category A: Can Remove)

#### A1. Redis Monitoring / Prometheus Metrics

| File:Line | Operations | Purpose |
|-----------|------------|---------|
| `backend/app/services/redis_monitor.py:24-67` | `XINFO_STREAM`, `XPENDING`, `INFO memory`, `INFO keyspace`, `CONFIG GET appendonly` | Prometheus metrics for stream length, PEL depth, memory usage, keyspace |

**Migration:** Remove entirely. Stream metrics are not actionable for cost optimization.

#### A2. Startup Config Validation

| File:Line | Operations | Purpose |
|-----------|------------|---------|
| `backend/app/main.py:160-218` | `INFO memory`, `CONFIG GET maxmemory-policy`, `CONFIG GET appendonly` | Validate Redis config on startup |

**Migration:** Remove or make non-fatal warning without Redis.

#### A3. Redis Health Checks

| File:Line | Operations | Purpose |
|-----------|------------|---------|
| `backend/app/api/health.py:121-130` | `PING` | Redis liveness check |
| `backend/app/api/health.py:144-153` | `EXISTS event_store` | Event store readiness check |

**Migration:** Remove Redis from health check critical path. Keep only as optional diagnostic.

#### A4. Persistence Verification

| File:Line | Operations | Purpose |
|-----------|------------|---------|
| `backend/app/services/reconciliation_service.py:132-154` | `CONFIG GET appendonly`, `CONFIG GET save` | Verify Redis AOF/RDB persistence |

**Migration:** Remove. Owned by Redis operator, not application.

#### A5. Diagnostic Scripts

| File | Operations | Purpose |
|------|------------|---------|
| `scripts/redis_live_investigation.py` | Various `INFO`, `MEMORY DOCTOR`, `CLIENT LIST` | Ad-hoc debugging |
| `scripts/redis_memory_audit.py` | Memory analysis | Ad-hoc debugging |

**Migration:** Keep as tooling, not part of application runtime.

---

## 3. Dependency Classification Summary

| Category | Count | Files | Description |
|----------|-------|-------|-------------|
| **C: Requires Valkey** | 4 groups | events.py, main.py, trade_service.py, system_mode.py, remoteState.ts, commandHandler.ts, telegramBot.ts, notification_service.py | Event bus (streams + pub/sub), remote kill switch, system mode persistence |
| **B: Move to PG/Memory** | 11 groups | control_plane.py, circuit_breakers.py, shadow_execution_service.py, portfolio_cache_service.py, shadow_analytics_service.py, 5 research cache files, dedup.py, audit_logger.py | All have existing fallbacks; migrate to local cache or PostgreSQL |
| **A: Remove completely** | 5 groups | redis_monitor.py, health.py (redis checks), main.py (redis config validation), reconciliation_service.py (AOF check), diagnostic scripts | Not needed for application correctness |

---

## 4. Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| `trade_service.py` fail-closed on Redis failure | **High** — ALL trading stops | Keep Redis for now; isolate behind `StateStore` interface; add PostgreSQL fallback |
| Event bus (streams) without Redis | **High** — no inter-service communication | Needs Valkey or message broker replacement |
| Dashboards without pub/sub | **Medium** — real-time updates stop | Fall back to polling or WebSocket direct broadcast |
| Shadow execution optimistic locking (`WATCH`) | **Low** — Redis-specific pattern; in-memory fallback exists | Replace with Postgres `SELECT FOR UPDATE` or remove locking |
| Dedup without Redis | **Low** — possible duplicate events | In-memory LRU with TTL is sufficient |
| Remote control (TypeScript) without Redis | **Medium** — Telegram bot cannot read notifications or audit | Migrate to HTTP API calls instead of Redis streams |

---

## 5. Replacement Options

### 5.1 Event Bus (Streams + Pub/Sub)

| Option | Pros | Cons | Effort |
|--------|------|------|--------|
| **Valkey** (self-hosted) | Drop-in Redis replacement, same protocol | Need to manage infrastructure | Low |
| **PostgreSQL + LISTEN/NOTIFY** | No new infra | No consumer groups, no stream replay, 8000msg/channel limit | High |
| **NATS JetStream** | Native stream support, persistent | New infrastructure, different protocol | High |
| **RabbitMQ Streams** | Mature, persistent | New infrastructure, different protocol | High |
| **In-process asyncio queues** | No infra needed | Lost on restart, single process | Medium |

**Recommended: Valkey** — lowest risk, same protocol, self-hosted cost ~$5-15/month on a VM.

### 5.2 Key-Value Store (State, Cache)

| Option | Pros | Cons | Effort |
|--------|------|------|--------|
| **PostgreSQL** | Already have it | Higher latency, connection pool pressure | Medium |
| **In-memory dict** | Zero infra | Lost on restart | Low |
| **Local SQLite** | Persistent, zero infra | Single-node only | Low |
| **Valkey** | Same as current, fast | Adds infra | Low |

**Recommended: In-memory + PostgreSQL** — for state that must survive restart, use PostgreSQL.

### 5.3 Remote Control Data

| Option | Pros | Cons | Effort |
|--------|------|------|--------|
| **REST API calls** | No Redis needed for TypeScript | Slightly higher latency | Low |
| **WebSocket** | Real-time, no Redis | More complex | Medium |

**Recommended: REST API** — Telegram bot already calls HTTP endpoints for most operations.

---

## 6. Migration Path to Valkey

### Phase 1: Abstraction (Current — do NOW)
- [x] Create `StateStore` abstract interface
- [x] Implement `RedisStateStore` (thin wrapper around current `get_redis()`)
- [x] Implement `LocalStateStore` (in-memory dict)
- [ ] Route all non-stream Redis calls through `StateStore`
- [ ] Make `get_redis()` internally check REDIS_URL and return None if empty
- [ ] Add graceful fallback for all optional consumers

### Phase 2: Prepare (Before Valkey deployment)
- [ ] Set up Valkey instance on same VM or cheap VPS
- [ ] Configure TLS, authentication, persistence (AOF + RDB)
- [ ] Update `redis.conf` for Valkey compatibility
- [ ] Create Valkey Docker service in docker-compose.yml
- [ ] Update CI workflow to test with Valkey

### Phase 3: Switchover
- [ ] Point REDIS_URL at Valkey
- [ ] Run full integration test suite
- [ ] Monitor for 48 hours in shadow mode
- [ ] Switch production traffic

### Phase 4: Decommission Upstash
- [ ] Verify all data migrated
- [ ] Delete Upstash Redis database
- [ ] Remove Upstash from billing

---

## 7. Cost Analysis

| Option | Monthly Cost | Latency | Maintenance |
|--------|-------------|---------|-------------|
| **Upstash Redis (current)** | ~$194 | <1ms | Zero |
| **Self-hosted Valkey (VM)** | ~$5-15 | <1ms local | Medium |
| **Self-hosted Valkey (K8s)** | ~$10-30 | <1ms | High |
| **No Redis (all local)** | $0 | N/A | Zero |
| **PostgreSQL only** | $0 (included) | 2-5ms | Zero |

**Savings:** $179-194/month by switching from Upstash to self-hosted Valkey.

---

## 8. Implementation Plan

### 8.1 Files to Create
| File | Purpose |
|------|---------|
| `backend/app/core/state_store.py` | Abstract `StateStore` interface + `RedisStateStore` + `LocalStateStore` |

### 8.2 Files to Modify
| File | Change |
|------|--------|
| `backend/app/config.py` | Make `REDIS_URL` default to empty string; add `REDIS_ENABLED` computed property |
| `backend/app/redis.py` | Handle empty `REDIS_URL` — return `None` from `get_redis()` |
| `backend/app/services/control/control_plane.py` | Use `StateStore` abstraction |
| `backend/app/services/risk/circuit_breakers.py` | Use `StateStore` abstraction |
| `backend/app/core/system_mode.py` | Use `StateStore` abstraction |
| `backend/app/core/dedup.py` | Add in-memory LRU fallback; default `DEDUP_REDIS_ENABLED=False` |
| `backend/app/services/portfolio/portfolio_cache_service.py` | Make Redis optional (already has in-memory fallback) |
| `backend/app/api/health.py` | Make Redis health check non-critical |
| `backend/app/main.py` | Make Redis startup config validation non-fatal |
| `backend/app/services/redis_monitor.py` | Handle Redis being unavailable |
| `backend/app/services/reconciliation_service.py` | Handle Redis being unavailable |
| `backend/app/services/notification_service.py` | Handle Redis being unavailable |
| `pyproject.toml` | Move `redis[hiredis]` to optional dependencies |
| `.env.example` | Add Valkey migration notes; mark REDIS_URL as optional |
| `backend/.env.runtime` | Keep `REDIS_URL` empty (already) |

### 8.3 Files NOT Modified
| File | Reason |
|------|--------|
| `backend/app/core/events.py` | Event bus stays on Redis/Valkey — too risky to change |
| `backend/app/services/trade_service.py` | Trading logic — safety requirement |
| `backend/app/services/shadow/shadow_execution_service.py` | Simulation/replay logic — safety requirement |
| `src/remote/remoteState.ts` | TypeScript — separate project; document for future |
| `src/remote/commandHandler.ts` | TypeScript — separate project; document for future |
| `src/remote/telegramBot.ts` | TypeScript — separate project; document for future |
| `docker-compose.yml` | Redis service remains for local dev |
| `redis.conf` | Remains for local dev |
| `render.yaml` | Deployment config — stays until Valkey is deployed |

---

## 9. Test Coverage

| Test File | What It Tests | Redis Required? |
|-----------|---------------|-----------------|
| `test_integration.py` | Integration tests with real Redis | Yes (CI provides redis:7) |
| `test_exception_boundaries.py` | Mocked Redis failure scenarios | No (mocked) |
| `test_fail_closed_audit.py` | Fail-closed behavior when Redis down | No (mocked) |
| `test_shadow.py` | Shadow execution with mocked Redis | No (mocked) |
| `test_shadow_chaos.py` | Redis outage fallback | No (monkeypatched) |
| `test_research_orchestrator.py` | Research pipeline with `_no_redis()` fixture | No (mocked) |
| `test_research.py` | Various research services with `_no_redis()` | No (mocked) |
| `test_portfolio_review.py` | Portfolio cache Redis fallback | No (mocked) |
| `test_protocol_enforcement.py` | Fail-closed Redis tests | No (mocked) |

All existing tests that mock Redis will continue to work. Integration tests need actual Redis (CI already provides it).

---

## Appendices

### A. All Files Containing `get_redis()` or `from app.redis`

| # | File | Line | Pattern |
|---|------|------|---------|
| 1 | `backend/app/redis.py` | 21, 37 | Definition |
| 2 | `backend/app/core/events.py` | 10, 67, 92, 143 | Import + usage |
| 3 | `backend/app/core/system_mode.py` | 12, 292, 303 | Import + usage |
| 4 | `backend/app/core/dedup.py` | 4, 12, 27, 36, 52 | Import + usage |
| 5 | `backend/app/core/event_bridge.py` | N/A | Not found (name mismatch) |
| 6 | `backend/app/main.py` | 160, 1128 | Import + usage |
| 7 | `backend/app/api/health.py` | 123, 147 | Import + usage |
| 8 | `backend/app/services/control/control_plane.py` | 5, 27 | Import + usage |
| 9 | `backend/app/services/risk/circuit_breakers.py` | 6, 18 | Import + usage |
| 10 | `backend/app/services/trade_service.py` | 81 | Import + usage |
| 11 | `backend/app/services/notification_service.py` | 55 | Import + usage |
| 12 | `backend/app/services/portfolio/portfolio_cache_service.py` | 8, 29, 36, 60, 71 | Import + usage |
| 13 | `backend/app/services/shadow/shadow_execution_service.py` | 55 | Import + usage |
| 14 | `backend/app/services/shadow/shadow_analytics_service.py` | 28 | Import + usage |
| 15 | `backend/app/services/redis_monitor.py` | 3, 20 | Import + usage |
| 16 | `backend/app/services/reconciliation_service.py` | 132 | Usage (passes `r` argument) |
| 17 | `backend/app/services/incidents/incident_service.py` | 6, 15 | Import + usage |
| 18 | `backend/app/services/alerts/alert_service.py` | 7 | Import |
| 19 | `backend/app/services/audit/audit_logger.py` | 64 | Usage |
| 20 | `backend/app/services/stream/event_store.py` | 7 | Import |
| 21 | `backend/app/services/research/signal_registry.py` | 19-20 | Import + usage |
| 22 | `backend/app/services/research/strategy_registry.py` | 17-18 | Import + usage |
| 23 | `backend/app/services/research/research_report_service.py` | 20-21 | Import + usage |
| 24 | `backend/app/services/research/strategy_health_service.py` | 19-20 | Import + usage |
| 25 | `backend/app/services/research/champion_challenger_service.py` | 19-20 | Import + usage |

### B. TypeScript Redis Consumers

| # | File | Pattern | Purpose |
|---|------|---------|---------|
| 1 | `src/remote/remoteState.ts` | `new Redis()`, `GET`, `SET` | Remote kill switch state |
| 2 | `src/remote/commandHandler.ts` | `new Redis()`, `XADD`, `GET`, `SET`, `DEL` | Audit logging, close-confirm tokens |
| 3 | `src/remote/telegramBot.ts` | `new Redis()`, `XREAD` | Notification reading |
