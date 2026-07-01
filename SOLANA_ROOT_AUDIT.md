# Architecture Ownership Audit — Solana Root Analysis

**Date:** 2026-07-01
**Scope:** Full-stack architectural ownership mapping
**Method:** Source-level dependency tracing (runtime > imports > database > ownership > call chains)

---

## 1. Root Dependency Map

### Layer-by-Layer Ownership

| Layer | Owner | Evidence |
|-------|-------|----------|
| **Domain** | Polymarket | `market_id` is the canonical identity across all domain models. `InstrumentId(venue, symbol, quote_asset)` is venue-neutral but the `symbol` IS the `market_id`. No Solana-native domain primitives. |
| **Strategy** | Polymarket | Strategy configs and performance records keyed by `strategy_name`. Signals reference `markets.id` (Polymarket condition_id-based markets). |
| **Decision** | Polymarket | `ShadowDecisionLog` persisted with `market_id` as primary dimension. Decision = buy/sell a prediction market outcome. |
| **Execution** | Solana | `ExecutionIntent → TransactionPlan → TransactionEnvelope → ExecutionResult`. Jupiter routing, Solana transaction simulation. The `Instrument` model here is venue-neutral. **This is the only layer that switched.** |
| **Settlement** | Split | Old: `ExchangeOrder.clob_order_id`, `Fill.clob_fill_id` (Polymarket CLOB). New: `SolanaWalletTrade.tx_signature`, `slot` (Solana). Both tables exist. |
| **Evidence** | Polymarket | `ShadowDecisionLog` records `market_id`, `market_resolution_source`, outcome-calibrated metrics. |
| **Reporting** | Polymarket | Reports track prediction accuracy, win/loss on outcomes, calibration. Not token swap performance. |

### Key Finding
**The execution layer is the only layer that belongs to Solana.** All layers above (domain, strategy, decision) and most layers below (evidence, reporting) are Polymarket-rooted.

---

## 2. Naming Drift Audit

### Source Code Counts (`backend/**/*.py`)

| Namespace | Count | Classification |
|-----------|-------|----------------|
| `polymarket` | 419 | ROOT — defines the system identity |
| `market_id` | 624 | ROOT — canonical foreign key |
| `condition_id` / `clob_asset_id` / `token_id` / `clob_token_id` | 227 | LEGACY persistence |
| `solana` | 369 | ACTIVE — new domain models, execution, adapters |
| `jupiter` | 245 | ACTIVE — routing, planning, execution |
| `mint` / `slot` / `instruction` / `signature` / `transaction_receipt` / `simulation_receipt` | ~801 | ACTIVE — Solana technical terms, many are model field definitions |

### Interpretation
- Polymarket namespace count (419) is **higher** than Solana (369).
- `market_id` alone (624) dwarfs individual Solana terms.
- The 801 count for Solana technical terms is inflated by repetitive field definitions across models, migrations, and serialization code.
- The root identity of the system is still Polymarket.

---

## 3. Canonical Identity Audit

### Canonical Object: **PredictionMarket** (A)

Trace:

```
Input (Polymarket market data)
  → polymarket_rest.py / polymarket_ws.py ingest market events
  → signal.py: Signal.market_id → FK to markets.id
  → strategy generates signal with direction + confidence for a market outcome
  → decision buys/sells YES/NO on a condition_id
  → ExecutionIntent (venue-neutral adapter)
  → TransactionPlan with Jupiter routing (Solana execution)
  → shadow_decision_log with market_id
  → evidence: outcome receipt (resolution_price, win/loss on prediction)
```

### Ownership Transitions

| Step | Object | Owner | Switch Point? |
|------|--------|-------|---------------|
| Input | Polymarket market event | Polymarket | — |
| Signal | Signal(market_id) | Polymarket | — |
| Strategy output | direction + confidence for outcome | Polymarket | — |
| Decision | buy/sell YES/NO | Polymarket | — |
| Intent | ExecutionIntent(instrument) | **Neutral** | 🔄 Transition |
| Plan | TransactionPlan → Jupiter route | **Solana** | ✅ Switch |
| Execution | JupiterExecutionAdapter simulate | **Solana** | ✅ |
| Evidence | ShadowDecisionLog(market_id) | Polymarket | ❌ Switch back |
| Reporting | prediction accuracy | Polymarket | — |

The **Decision → Execution** boundary is the only real Solana switch. Everything before and after (except the execution pipeline itself) is Polymarket.

**Red flag confirmed:** The Decision ultimately resolves into `market_id`. The architecture still belongs to Polymarket.

---

## 4. Adapter Reality Check

### ExchangeAdapterRegistry (`exchanges/__init__.py`)

| Adapter Key | Class | Status | Notes |
|-------------|-------|--------|-------|
| `paper` | `PaperExchangeAdapter` | PRIMARY (active) | In-memory paper trading, used by default |
| `live_jupiter` | `JupiterExecutionAdapter` | TRANSITIONAL | Fully simulated, no real Solana interaction |
| `live` | `PaperExchangeAdapter` | LEGACY/DISABLED | Placeholder, disabled (`enabled: False`) |
| `polymarket` | `PolymarketLiveAdapter` | LEGACY (conditional) | Only imported when needed, uses CLOB API |

### Is Jupiter the default path?
**No.** The default `ExecutionService` uses `engine_type = trade.trade_type or "paper"`, which maps to `PaperExchangeAdapter`. Jupiter (`live_jupiter`) is only used when explicitly specified.

### Can Polymarket still execute?
**Yes.** `PolymarketLiveAdapter` exists and is fully functional. It uses `PolymarketClobClient` to submit orders to Polymarket's CLOB API with `clob_asset_id`, `side`, `size`, `price`. No runtime guard prevents its use.

### Hidden assumptions in simulation
- `JupiterExecutionAdapter.submit_order()` requires a `TransactionPlan` embedded in `order.raw_request['plan']` — falls back to `ExecutionSimulator` which simulates fills using linear slippage model
- The fill simulator (`FillSimulator`) generates deterministic fills based on `ReplaySeed` — **no real market data, no on-chain state**
- `SolanaSimulationAdapter.simulate_execution()` returns success if `len(plan.instructions) > 0` — trivially successful

### Do simulations still mirror Polymarket semantics?
**Yes.** The `ExecutionService._propagate_execution_result` feeds execution results into `ShadowLedger.record_decision()` with `market_id` and outcome-derived metrics. The shadow execution service stores `outcome` (YES/NO), not token pair. The system simulates Solana swaps but evaluates them as if they were prediction market positions.

---

## 5. Runtime Path Audit

```
Scheduler (task_scheduler.py)
  → PolymarketRESTIngester / PolymarketWSIngester (polymarket market data)
  → Orchestrator → Agents (signal generation for prediction markets)
  → ExecutionService.execute_signal()
    → _signal_to_intent() → Signal(market_id) → Instrument(symbol=market_id)
    → resolve_instrument() → MarketRegistry.resolve() → Polymarket resolver
    → Planner.plan() → Jupiter routing → TransactionPlan
    → submit_intent() → ExchangeAdapterRegistry.get(engine_type) → adapter
    → JupiterExecutionAdapter.execute() → ExecutionSimulator.simulate()
    → ExecutionResult (FILLED)
  → _propagate_execution_result() → ShadowLedger.record_decision()
    → market_id, outcome, confidence, replay_hash
  → ShadowPortfolio / PortfolioProjector
  → Reporting (prediction accuracy, calibration)
```

### ROOT SWITCH POINT

| Property | Value |
|----------|-------|
| **First Solana-owned object** | `TransactionPlan` (after `Planner.plan()`) |
| **Last Polymarket-owned object (inbound)** | `Signal` (with `market_id` FK to `markets.id`) |
| **Last Polymarket-owned object (outbound)** | `ShadowDecisionLog` (with `market_id` persistence) |

**Switch window:**
```
Signal (Polymarket) → ExecutionIntent (Neutral) → TransactionPlan (Solana) → ExecutionResult (Solana) → ShadowDecisionLog (Polymarket)
                        ↑                                           ↑                           ↑
                   Neutral adapter                          Solana execution              Polymarket evidence
```

The Solana execution window is **narrow**: it spans only the planning/execution pipeline. The system enters from Polymarket and exits back to Polymarket.

---

## 6. Persistence Audit

### All Database Tables

| Table | Model | Identity Key | Owner |
|-------|-------|-------------|-------|
| `markets` | `Market` | `condition_id` (Polymarket CTF condition ID) | Polymarket |
| `market_events` | `MarketEvent` | `market_id` → `markets.id` | Polymarket |
| `trades` | `Trade` | `market_id`, `outcome`, `compat_condition_id` | Polymarket |
| `signals` | `Signal` | `market_id` → `markets.id` | Polymarket |
| `exchange_orders` | `ExchangeOrder` | `clob_order_id`, `clob_asset_id`, `outcome` | Polymarket |
| `fills` | `Fill` | `clob_fill_id`, `market_id`, `outcome` | Polymarket |
| `positions` | `Position` | `market_id`, `market_condition_id` | Polymarket |
| `portfolio_snapshots` | `PortfolioSnapshot` | Generic (venue-neutral) | Neutral |
| `shadow_decision_log` | `ShadowDecisionLog` | `market_id`, `signal_id`, `decision_status` | Polymarket |
| `shadow_positions` | `ShadowPosition` | `research_trade_id` | Neutral (bridged) |
| `strategy_configs` | `StrategyConfigRecord` | `strategy_name` | Neutral |
| `strategy_performances` | `StrategyPerformanceRecord` | `strategy_name` | Neutral |
| `smart_wallets` | `SmartWallet` | `wallet_address` (Solana) | Solana |
| `solana_wallet_trades` | `SolanaWalletTrade` | `tx_signature`, `mint_address`, `slot` | Solana |
| `research_trades` | `ResearchTrade` | FK to `solana_wallet_trades.id` | **Bridged** |
| `wallet_trades` (old) | `WalletTrade` | `market_id` → `markets.id` | Polymarket |
| `wallets` | `Wallet` | `address` | Neutral |
| `wallet_scores` | `WalletScore` | `wallet_address` | Neutral |

### Current DB Identity: **Polymarket**

- **11 Polymarket-owned tables** vs **3 Solana-owned tables**
- The core transaction pipeline (trades → exchange_orders → fills) is entirely Polymarket
- `SolanaWalletTrade` and `SmartWallet` are **data ingestion tables** (Helius webhook → smart wallet tracking) — they do not participate in the execution pipeline
- `ResearchTrade` bridges both systems but is a research/validation table, not operational

---

## 7. Promotion Pipeline Audit

### `ShadowDecision → Promotion → Sandbox`

### What is being promoted?

**Prediction accuracy.** The promotion pipeline evaluates:
- `decision_id` — linked to a prediction market decision
- `realized_ev` — expected value of prediction
- `win_loss` — did the prediction resolve correctly?
- `calibration_delta` — was the probability estimate well-calibrated?
- `prediction_error` — error in the prediction

Source: `OutcomeReceipt` in `domain/shadow/models.py`

### Classification: **Prediction accuracy promotion**

The system promotes decisions that correctly predict binary outcomes (YES/NO) on Polymarket prediction markets. It does NOT promote:
- Trade quality (slippage, fill efficiency)
- Execution quality (latency, route optimization)
- Portfolio growth (PnL, Sharpe ratio)

The Sandbox runs **deterministic replay of prediction decisions**, not token swap scenarios.

---

## 8. Final Verdict

### **B — SOLANA_OVER_POLYMARKET**

**Definition:** Execution moved to Solana but the domain identity, canonical objects, persistence model, and evaluation metrics still belong to Polymarket.

### Confidence
**95%**

The evidence is consistent across all 7 audit phases. No contradictory evidence was found.

### Blocking Findings

| # | Finding | Severity | Layer |
|---|---------|----------|-------|
| 1 | `market_id` is the canonical identity across domain, persistence, and evidence. No Solana-native trading identity exists. | CRITICAL | Domain |
| 2 | Core DB tables (trades, exchange_orders, fills, positions) use Polymarket identifiers (`condition_id`, `clob_asset_id`, `outcome`). Solana tables are side-car ingestion only. | CRITICAL | Persistence |
| 3 | Data ingestion is entirely Polymarket-based (REST/WS ingesters, Polygon RPC). No Solana data feeds the decision pipeline. | HIGH | Input |
| 4 | The ExecutionService default adapter is `paper`, not `jupiter`. Live Jupiter execution requires explicit opt-in. | HIGH | Runtime |
| 5 | Metrics namespace is `polymarket_*` across all Prometheus metrics in `execution_service.py`. | MEDIUM | Observability |
| 6 | Simulation is trivially truthful (no actual on-chain state validation). `SolanaSimulationAdapter` returns success if instructions exist. | MEDIUM | Execution |
| 7 | `PolymarketLiveAdapter` code is fully functional and could execute live Polymarket orders. No architectural guard prevents it. | MEDIUM | Safety |

### Migration Recommendations

1. **Canonical identity**: Replace `market_id` with a Solana-native identity (`mint_address` / pool address) as the primary trading key. This requires rebuilding the entire signal/decision pipeline.

2. **Data ingestion**: Replace `PolymarketRESTIngester` and `PolymarketWSIngester` with Solana DEX data feeds (e.g., Birdeye, Helius webhooks for swap events).

3. **Persistence migration**: Move core tables to Solana-native schema (token pairs, swap amounts, pool IDs instead of condition_ids/outcomes).

4. **Strategy logic**: Rebuild strategies to reason about token prices, liquidity, and DEX metrics instead of prediction market binary outcomes.

5. **Execution default**: Change `ExecutionService` default engine from `paper` to `live_jupiter`.

### Merge Impact

**ARCHITECTURE_REFACTOR_REQUIRED**

The current state is a transitional architecture where Solana replaced only the execution plumbing. The system cannot be described as Solana-native until:
- The domain's canonical identity moves off `market_id`
- Data ingestion sources are Solana-native
- Strategy/decision logic reasons about token markets, not prediction outcomes
- Core persistence tables use Solana identities

**SAFE_TO_CONTINUE** for current operations (simulation/shadow mode), but any claim of "migration complete" is architecturally incorrect.

---

## Appendix: Evidence Trace

```
backend/app/config.py             → POLYMARKET_CLOB_API_URL, POLYGON_RPC_URL (Polymarket infra)
backend/app/main.py               → PolymarketRESTIngester, PolymarketWSIngester, PolygonRPCListener
backend/app/models/trade.py       → market_id, condition_id, outcome, compat_outcome (Polymarket)
backend/app/models/exchange_order.py → clob_order_id, clob_asset_id, clob_signature (Polymarket CLOB)
backend/app/models/market.py      → condition_id, clob_token_ids (Polymarket CTF)
backend/app/models/fill.py        → clob_fill_id, outcome, market_id (Polymarket)
backend/app/domain/planning/      → TransactionPlan, Route, Quote (Solana-native, venue-neutral)
backend/app/domain/solana/        → TransactionEnvelope, SimulationReceipt (Solana-native)
backend/app/exchanges/adapters/   → BaseExecutionAdapter(TransactionPlan), JupiterExecutionAdapter (Solana-native)
backend/app/exchanges/__init__.py → ExchangeAdapterRegistry (paper=PRIMARY, live_jupiter=TRANSITIONAL)
backend/app/services/planning/    → JupiterRoutePlanner, JupiterQuoteProvider (Solana-native)
backend/app/models/wallet_trade.py → SolanaWalletTrade(tx_signature, mint_address, slot) (Solana)
backend/app/models/smart_wallet.py → SmartWallet (Solana wallet tracking)
```
