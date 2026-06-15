# Sprint 3.1 — Production Readiness Report

## 1. System Architecture Summary

### Shadow Pipeline

```
ResearchTrade
  → ShadowPortfolioService.open_from_research_trade()
    → ShadowPosition created (status=open, entry_price, size, tp/sl)
    → solana_shadow_positions_total{status="open"} +1
```

### Price Pipeline

```
_shadow_price_tracker_loop (every 60s, +0s stagger)
  → list_open() → batch JOIN ResearchTrade+SolanaWalletTrade
  → distinct mints dedup
  → PriceTrackingService.resolve_price(mint)
    → Redis cache check (TTL=120s)
    → Birdeye API (10s timeout)
    → DexScreener API (5s timeout)
    → DB stale price (last known from wallet_trade)
    → source="unavailable" + source="error"
  → ShadowPositionRepository.update_current_price(id, price)
```

### Evaluation Pipeline

```
_shadow_eval_loop (every 60s, +15s stagger)
  → list_open()
  → for each position:
      current_price ≥ tp_price → close (take_profit)
      current_price ≤ sl_price → close (stop_loss)
      opened_at + 72h < now → close (timeout)
    else → held
```

## 2. Failure Modes

| Failure | Behavior | Mitigation |
|---|---|---|
| **Birdeye API down** | Falls through to DexScreener | Price chain |
| **DexScreener API down** | Falls through to DB stale | Price chain |
| **Both APIs down** | DB stale price used | `solana_price_stale_total` +1 |
| **Redis down** | `get_cached_price_redis()` / `cache_price_redis()` silently fail via `except Exception: pass` | Falls back to API providers |
| **DB connection lost** | Session error → caught by `except Exception` in loop → 5s retry | Crash recovery |
| **DB slow query (>200ms)** | Loop iteration delayed but still completes | Injected in chaos tests |
| **NULL entry_price** | `_compute_pnl` returns (0, 0); position skipped by evaluate_all | Integrity guard |
| **NULL size_usd** | Same as above | Integrity guard |
| **Manual close during eval** | close_position returns None on second call; eval skips already-closed positions | Idempotency |
| **CancelledError (shutdown)** | Loop exits gracefully via break | Cancellation safety |
| **Price resolution unavailable** | Position retains previous current_price; no crash | Error path tested |

## 3. Known Limitations

1. **External API dependency**: Price freshness depends on Birdeye/DexScreener availability. During extended API outages, stale DB prices are used. No circuit breaker or backoff is implemented on API calls.

2. **Eventual consistency in price updates**: Prices are refreshed every 60s. Between cycles, `current_price` reflects the last resolved value. TP/SL evaluations use this cached price, so there is up to 60s of latency in trigger detection.

3. **60s evaluation granularity**: TP/SL/timeout checks run every 60s. A rapid price move past TP within a cycle is not detected until the next evaluation. This is acceptable for a shadow/simulation system but would need sub-cycle monitoring for live trading.

4. **No cross-cycle state**: Each cycle of the price tracker and eval loop is stateless. If an API fails and a position's price cannot be updated, the previous cycle's price persists. There is no accumulation of failure counts.

5. **Reconciliation is read-only**: The reconciliation service detects drift but does NOT correct stored values. Corrections require manual intervention or a separate repair job.

6. **SQLite test database**: Performance benchmarks run on SQLite in-memory. PostgreSQL timings under load will differ.

## 4. Rollback Strategy

### Disable Shadow Evaluation

```python
# In config.py or environment:
SOLANA_SHADOW_TIMEOUT_HOURS = 999999  # effectively disables timeout closes
# Remove or comment out in main.py lifespan():
# bg_tasks.append(asyncio.create_task(_shadow_eval_loop(), name="shadow_eval"))
```

### Disable Price Tracking

```python
# Remove or comment out in main.py lifespan():
# bg_tasks.append(asyncio.create_task(_shadow_price_tracker_loop(), name="shadow_price_tracker"))
```

### Freeze Positions Safely

```python
# All open positions remain in the DB with their current state.
# No evaluation, no price updates = positions frozen as-is.
# To unfreeze, re-enable the loops.
```

### Full Rollback

```bash
git revert <sprint3-commit-hash> --no-commit
# Or selectively revert shadow modules
```

## 5. Go/No-Go Checklist

| Check | Status |
|---|---|
| All worker loops handle CancelledError gracefully | ✅ |
| All worker loops catch and log generic exceptions | ✅ |
| 5s crash recovery delay active on both loops | ✅ |
| Price resolution chain returns PriceResult (never raises) | ✅ |
| No unhandled exceptions in price or eval paths | ✅ |
| Reconciliation drift count = 0 | ✅ |
| No N+1 queries in shadow analytics | ✅ |
| All chaos tests pass (API cascade, Redis outage, DB spike, corruption, race) | ✅ |
| Metrics stable (no negative counters, no duplicate registration) | ✅ |
| SLO definitions documented | ✅ |
| Startup ordering: price tracker → 15s → eval | ✅ |
| Shadow layer isolated from scoring/ranking/confidence | ✅ |

**Decision**: GO
