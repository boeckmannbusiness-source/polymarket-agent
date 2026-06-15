# Sprint 3.1 — Service Level Objectives

## Price Freshness SLO

| Metric | Target | Measurement |
|---|---|---|
| Prices served from cache (Redis) | ≥ 95% | `solana_price_source_total{source="redis"}` / `solana_price_source_total` total |
| Prices resolved within 120s of last update | ≥ 99% | Redis TTL = 120s; positions priced within 1 cycle (60s) |
| Stale price (DB fallback) rate | < 5% | `solana_price_stale_total` / closed positions per day |

**Rationale:** The 60s tracker loop refreshes prices every cycle. Redis TTL = 120s ensures at least one cache-hit cycle before expiry. DB stale fallback is acceptable transiently but indicates upstream API degradation.

## Eval Loop SLO

| Metric | Target | Measurement |
|---|---|---|
| Per-cycle duration | < 5s p95 | `polymarket_scheduler_execution_duration_seconds{job_name="shadow_eval"}` |
| Positions evaluated per cycle | ≥ 99% of open | `solana_shadow_evals_total{result="held"}` + closed counts match list_open |
| Timeout accuracy | within 60s window | Positions within `SOLANA_SHADOW_TIMEOUT_HOURS` boundary are closed within 1 cycle |

**Rationale:** evaluate_all() is O(n) in-memory after a single query. 10k positions benchmarked at 0.063s. Even with 100k positions, < 5s is safe.

## API SLO

| Endpoint | Target | Measurement |
|---|---|---|
| `/stats` | < 300ms p95 | Inferred from DB query latency (2 queries, benchmarked < 50ms) |
| `/performance` | < 500ms p95 | Single GROUP BY query, O(groups) serialization |
| `/concentration` | < 300ms p95 | Single aggregation query |
| `/wallet-universe` | < 500ms p95 | Single query + top-10 sort |
| All endpoints | Error rate < 1% | `solana_validation_requests_total` / HTTP 5xx count |

## System Health SLO

| Metric | Target | Measurement |
|---|---|---|
| Price resolution success rate | ≥ 95% | `(redis + birdeye + dexscreener + stale) / total` from `solana_price_source_total` |
| Worker uptime | ≥ 99.9% | Loops restart on exception; CancelledError only on shutdown |
| Reconciliation drift | 0 critical, < 1% warning | `solana_shadow_reconciliation_drift_total{severity="critical"}` = 0 |

## Enforcement

SLOs are measured over a rolling 24h window.
Breach triggers:
- **Warning**: > 2σ from target over 1h
- **Critical**: > 3σ from target over 1h, or any critical reconciliation drift

Alert thresholds are defined in `config.py`:
- `SLO_PRICE_STALE_THRESHOLD_SECONDS = 120`
- `SLO_EVAL_MAX_LAG_SECONDS = 5`
- `SLO_PRICE_SUCCESS_RATE_MIN = 0.95`
