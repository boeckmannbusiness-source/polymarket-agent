# MEMORY — Key Decisions & Bugs Found

## Architecture Decisions

### Why PostgreSQL on Neon Cloud?
- Free tier with 0.5GB storage, enough for 131K+ trade events
- PostgreSQL for relational integrity (markets, trades, signals all linked)
- Neon provides branching for testing without affecting production

### Why FastAPI (not Flask/Django)?
- Async-native — needed for WebSocket connections to Polymarket
- Automatic OpenAPI docs — useful for debugging 55+ endpoints
- Lifespan hooks for starting/stopping ingesters with the app

### Why 4-tier LLM Fallback?
- All free providers have rate limits and may go down
- Chain: z.ai (GLM) → Groq (Llama) → Ollama Cloud (Ministral) → Mistral (Mistral Small)
- Each fallback adds ~2-3s latency
- Currently only the `market_regime` agent uses LLM (all other strategies are deterministic)

### Why ReplayEngine (not live paper trading)?
- Live paper trading would take months to validate strategies
- ReplayEngine can test 7 days of data in ~15 seconds
- Deterministic — same inputs always produce same outputs (verified with hash comparison)

### Why Signal_Interval_Seconds defaults to 60?
- Each strategy checks all market contexts every 60 seconds
- Too fast (<10s): generates too many signals from same event
- Too slow (>300s): misses short-term opportunities
- Trade-off: 60s gives ~400 signals/day for whale_following

---

## Bugs Found & Fixed

### Bug #1: PnL Directionality (Phase 3)
**File:** `backend/app/replay/engine.py`, `market_state.py`

**Root Cause:** `MarketContext.current_price` was a single float. When event A was a YES trade at 0.50 and event B was a NO trade at 0.18, `current_price` flipped to 0.18. A signal that entered on event A (BUY_YES at 0.50) would be evaluated at the next tick against 0.18, computing PnL = 0.18 - 0.50 = -0.32. But that's wrong — the NO trade at 0.18 doesn't affect the YES token price.

**Fix:**
- Added `outcome_prices: dict[str, float]` tracking prices per outcome separately
- Added `get_outcome_price(signal_direction)` mapping BUY_YES→first outcome, BUY_NO→second
- Removed `BUY_NO` sign flip hack (no longer needed with correct prices)

**Impact:** Whale following 15m win rate went from ~0% (random) to 70% (real edge).

### Bug #2: Pending Outcomes Mixed Between Markets (Phase 3)
**File:** `backend/app/replay/engine.py`

**Root Cause:** `pending_outcomes` was a global list shared across all markets. A signal from market A would be evaluated against price movements in market B.

**Fix:** Changed to `pending_by_cid: dict[str, list[PendingOutcome]]` — each market tracks its own pending signals.

### Bug #3: Momentum Window Too Narrow (Phase 4)
**File:** `backend/app/replay/market_state.py` — `get_momentum()`

**Root Cause:** The function searched for a trade at exactly 3600 seconds ago within a 60-second window (`ts.timestamp() < cutoff and ts.timestamp() >= cutoff - 60`). Trades don't happen at regular 1-hour intervals, so this almost never matched real data.

**Fix:** Changed to nearest-neighbor search — find the closest price to the 3600-second mark, regardless of exact timestamp.

**Impact:** MomentumSpike went from 0 signals to 2,804 signals.

### Bug #4: Price History Pruned Too Aggressively (Phase 4)
**File:** `backend/app/replay/market_state.py` — `_prune_windows()`

**Root Cause:** `price_history` was pruned to only 5 minutes (`cutoff_5m`), but `get_momentum()` needs 1 hour of history. Momentum was computed against ~5-minute-old prices, not 1-hour-old prices.

**Fix:** Changed pruning to 1 hour (`cutoff_1h`) so price_history has enough data for momentum.

**Impact:** Results were similar for active markets (enough trades within 5 min to approximate 1h momentum), but different for sparse markets.

### Bug #5: WebSocket Bridge Ignores Price Events
**File:** `app/services/event_persistence_bridge.py`

**Root Cause:** Bridge only handles `"trade"` and `"market_metadata"` event types. Polymarket WebSocket publishes `"price_change"` events which are silently dropped.

**Status:** Known, not yet fixed.

### Bug #6: Render OOM on Backtest Execution
**File:** N/A (infrastructure)

**Root Cause:** Render free tier (512MB RAM) can't load 46K+ SQLAlchemy ORM objects into memory at once.

**Workaround:** Run backtests locally. The `/debug/replay-drift` endpoint auto-scales its window to stay within memory limits.

---

## Strategy Performance Summary

| Strategy | 15m Win Rate | 15m PnL | Signal Count | Notes |
|----------|-------------|---------|-------------|-------|
| whale_following | 69.9% | +$29 | 633 | Best performer, trades with whales for 15m |
| momentum_spike | 50.8% | +$33.58 | 2,804 | Many signals, small edge; close reversal is strong (32%) |

### Key Insight: Mean Reversion at Close
Both strategies show strong mean reversion at close:
- whale_following: 98.7% close win rate (PnL +$24) — always reverts
- momentum_spike: 32.1% close win rate (PnL -$107) — sharp moves revert HARD

This suggests a "buy-the-dip, sell-the-pump" strategy (opposite direction of momentum) would have 68% win rate at close.

---

## Data Quality Notes

- **131,508 total events** across 186 markets
- ~42K synthetic events (source=None, random prices, 6h intervals) — should be filtered
- ~89K real events from Data API backfill
- Latest event: 2026-05-23 07:41 UTC (WebSocket is ~11 hours behind)
- Data density: 46K events in last 15 min before latest timestamp (very bursty)
- Earliest event: 2026-04-27

---

## Infrastructure

| Service | URL | Tier |
|---------|-----|------|
| Backend API | https://polymarket-agent-nw0o.onrender.com | Free (512MB) |
| Dashboard | https://polymarket-agent-tau.vercel.app | Free |
| Database | Neon (summer-violet-36819767) | Free (0.5GB) |
| Grafana | https://boeckmannbusiness.grafana.net | Free |
| GitHub | https://github.com/boeckmannbusiness-source/polymarket-agent | Free |

### Environment Variables Needed
- `DATABASE_URL` — Neon PostgreSQL connection string
- `REDIS_URL` — Redis Cloud connection string
- `LLM_API_KEYS` — API keys for z.ai, Groq, Ollama, Mistral
- `POLYMARKET_WS_URL` — wss://ws-subscriptions-clob.polymarket.com/ws/market

---

## API Endpoints (55+ total)

### Health & Debug
- `GET /health` — Server status
- `GET /system/status` — Component health
- `GET /debug/replay-check` — Quick replay test (3 sample signals)
- `GET /debug/replay-drift` — Determinism check (call twice, compare hashes)

### Markets
- `GET /api/v1/markets` — List all markets
- `GET /api/v1/markets/{id}` — Market details
- `GET /api/v1/markets/{id}/events` — Trade events for a market

### Signals & Trades
- `GET /api/v1/signals` — Generated signals
- `GET /api/v1/trades` — Trade history

### Backtesting
- `GET /api/v1/backtesting/strategies` — List available strategies
- `POST /api/v1/backtesting/runs` — Create a backtest run
- `POST /api/v1/backtesting/runs/{id}/execute` — Execute (OOM on Render)
- `GET /api/v1/backtesting/runs/{id}` — Get results
