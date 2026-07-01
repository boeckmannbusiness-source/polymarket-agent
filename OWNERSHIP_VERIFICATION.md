# Ownership Verification — Complete Runtime Path Trace

**Date:** 2026-07-01
**Method:** Static code-path tracing from scheduler through promotion

---

## Complete Trace

| Step | Object | Identity | Owner | Evidence |
|------|--------|----------|-------|----------|
| **Scheduler** | `TaskScheduler` | N/A | Neutral | Generic scheduler, no domain identity |
| **Ingestion (REST)** | `PolymarketRESTIngester` | `condition_id` | **Polymarket** | `_upsert_market()` uses `conditionId` from Gamma API. Persisted to `markets.condition_id`. |
| **Ingestion (WS)** | `PolymarketWSIngester` | `asset_id` → `condition_id` | **Polymarket** | Subscribes by `asset_id` (CLOB token IDs), normalizes to `condition_id`. |
| **Ingestion (RPC)** | `PolygonRPCListener` | `condition_id` | **Polymarket** | ABI-decodes CTF trade events, extracts `condition_id`. |
| **Market Ingestion** | `MarketService.upsert_market()` | `condition_id` → `market_id` | **Polymarket** | Stores Polymarket market metadata. Canonical `condition_id` mapped to internal UUID. |
| **Whale Agent** | `WhaleAgent` | `condition_id` + `wallet` | **Polymarket** | Subscribes to `market:data`, enriches wallet scores, publishes to `wallet:trade`. |
| **Signal Generation** | Strategy.generate_signal() → `StructuredSignal` | `market_condition_id` + `market_id` | **Polymarket** | All 10+ strategies produce BUY_YES/BUY_NO/NEUTRAL signals for prediction markets. |
| **Signal Persistence** | `SignalService.create_signal()` → `Signal` | `market_id` (UUID FK) | **Polymarket** | `Signal.market_id` FK to `markets.id`. Direction = BUY_YES/BUY_NO. |
| **Risk Agent** | `RiskAgent` | `market_id` + `signal_id` | **Polymarket** | Evaluates risk of prediction market decision using signal metadata. |
| **Intent Factory** | `ExecutionIntentFactory.create_from_trade()` | `Instrument(symbol=market_id)` | **Neutral** (adapter) | Converts Polymarket decision to venue-neutral Intent. `compat_outcome` retained for backward compat. |
| **Planner** | `Planner.plan()` → `TransactionPlan` | `Instrument(venue, symbol)` | **Solana** | Jupiter routing, swap instructions, slippage model. Solana-native output. |
| **Execution Adapter** | `JupiterExecutionAdapter.execute()` | `ExecutionResult.execution_id` | **Solana** | Simulated fill generation from TransactionPlan. Adapter = "jupiter_simulated". |
| **Order Persistence** | `ExchangeOrder` | `trade_id` → `Trade.market_id` | **Polymarket** | Columns: `clob_order_id`, `clob_asset_id`, `clob_signature`, `outcome`. All Polymarket concepts. |
| **Fill Persistence** | `Fill` | `market_id` + `outcome` | **Polymarket** | Columns: `clob_fill_id`, `market_id`, `outcome`. Polymarket-specific. |
| **Shadow Ledger** | `ShadowLedger.record_decision()` → `ShadowDecisionLog` | `market_id` + `strategy_id` | **Polymarket** | Fields: `market_id`, `confidence`, `predicted_direction`, `predicted_probability`, `expected_ev`. All prediction market concepts. |
| **Outcome Engine** | `OutcomeClosureEngine.resolve()` | `decision_id` → `market_id` | **Polymarket** | Compares `resolution_price` to `simulated_entry_price` for win/loss. Prediction outcome, not swap PnL. |
| **Scorecard** | `ScorecardEngine.compute_metrics()` | `strategy_id` | **Polymarket** | Metrics: win_rate, realized_ev, brier_score, replay_parity — all from prediction outcomes. |
| **Evidence** | `EvidenceEngine.build_snapshot()` | `strategy_id` | **Polymarket** | `PromotionEvidenceSnapshot` contains prediction-based metrics (EV, Brier, replay). |
| **Promotion Readiness** | `PromotionReadinessService.get_readiness()` | `strategy_id` | **Polymarket** | Gates: decision_count >= 500, replay_parity >= 0.95, realized_ev > 0, brier_score <= 0.25. |
| **Promotion Audit** | `PromotionAuditService.audit_strategy()` | `strategy_id` | **Polymarket** | Audits 6 prediction-based gates against evidence snapshot. |

---

## Identity Transitions

```
Ingestion                           Signal                         Execution                      Evidence
────────                           ──────                         ─────────                      ────────
condition_id ─────► market_id ────► market_id ────► Instrument ──► TransactionPlan         ┌────► market_id
(Polymarket)      (UUID)          (Signal)        (symbol=       (Solana-native,           │    (ShadowDecisionLog)
  ▲                                                market_id)     but still keyed by        │
  │                                                                 market_id via symbol)    │
  │                                                                                         │
  └──────────────────────── Polymarket owns the round-trip ─────────────────────────────────┘
```

**The Solana execution window is narrow:**
```
Planner.plan() ──────────► JupiterExecutionAdapter.execute()
     │                               │
 TransactionPlan              ExecutionResult
 (Solana-native)              (Solana-native)
     │                               │
     └──────── 2 objects ────────────┘
```

The transaction plan and its execution result are the ONLY Solana-native objects in the entire runtime path. Everything before and after is Polymarket.
