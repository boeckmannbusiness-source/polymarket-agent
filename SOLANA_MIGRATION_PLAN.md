# Solana Migration Plan — Layer-by-Layer Cost Estimation

**Date:** 2026-07-01
**Framework:** Each layer classified as KEEP / ADAPT / REBUILD based on current ownership vs. target Solana-native ownership.

---

## Current State Summary

| Layer | Current Owner | Target Owner | Gap |
|-------|--------------|-------------|-----|
| Ingestion | Polymarket | Solana | Full |
| Signals | Polymarket | Solana | Full |
| Strategy | Polymarket | Solana | Full |
| Decision | Polymarket | Solana | Full |
| Execution | **Solana** (partial) | Solana | Partial |
| Shadow | Polymarket | Solana | Full |
| Evidence | Polymarket | Solana | Full |
| Promotion | Polymarket | Solana | Full |
| Reporting | Polymarket | Solana | Full |
| Persistence | Polymarket | Solana | Full |

**Only Execution is partially migrated.** Everything else belongs to Polymarket.

---

## Layer-by-Layer Migration Plan

### 1. Ingestion

| Property | Value |
|----------|-------|
| **Current** | `PolymarketRESTIngester`, `PolymarketWSIngester`, `PolygonRPCListener` |
| **Identity** | `condition_id` |
| **Action** | REBUILD |
| **Complexity** | HIGH |
| **Effort** | 2-3 sprints |
| **What** | Replace with Solana DEX data feeds (Birdeye, Helius, Jupiter API). Tokens/pools identified by `mint_address` instead of `condition_id`. Price feeds from DEX pools instead of CLOB order books. |
| **Risk** | Data structure entirely different. No direct 1:1 mapping between prediction market events and swap events. |
| **Dependencies** | All downstream layers depend on this data format. |

---

### 2. Signals

| Property | Value |
|----------|-------|
| **Current** | `SignalService.create_signal(market_id, signal_type, direction=BUY_YES/BUY_NO, ...)` |
| **Identity** | `market_id` (UUID) |
| **Action** | REBUILD |
| **Complexity** | VERY HIGH |
| **Effort** | 3-4 sprints |
| **What** | New signal model: `Signal(token_mint, pool_address, side=BULL/BEAR, quantity, entry_price_range, ...)`. Direction changes from binary outcome (YES/NO) to directional bet (LONG/SHORT). Confidence becomes price-movement confidence, not prediction confidence. |
| **Risk** | Requires entirely new signal schema, new signal types. Existing strategies (whale_following, liquidity_vacuum, etc.) are prediction-market-specific and cannot be adapted — they must be rebuilt for token markets. |

---

### 3. Strategy

| Property | Value |
|----------|-------|
| **Current** | 10+ strategies all generating `StructuredSignal` with `signal=BUY_YES/BUY_NO` |
| **Identity** | `market_condition_id` + `market_id` |
| **Action** | REBUILD |
| **Complexity** | VERY HIGH |
| **Effort** | 4-6 sprints |
| **What** | Rewrite every strategy to reason about token price action, liquidity depth, pool composition, DEX volume. Prediction-market-specific logic (outcome probability, implied probability, binary resolution) replaced with technical/fundamental analysis for token markets. |
| **Risk** | Core intellectual property of the system lives here. This is the highest-risk and highest-effort layer. Strategy performance on prediction markets does not predict performance on token markets. |

---

### 4. Decision

| Property | Value |
|----------|-------|
| **Current** | `ShadowDecisionLog` keyed by `market_id`, decision = buy/sell prediction outcome |
| **Identity** | `market_id` |
| **Action** | REBUILD |
| **Complexity** | MEDIUM |
| **Effort** | 1 sprint |
| **What** | New decision model: `TradeDecision(pool_id, direction=LONG/SHORT, size, entry_price, stop_loss, take_profit, expected_alpha)`. Remove outcome-specific fields. |
| **Risk** | Low — this is a data model change with clear mapping. |

---

### 5. Execution

| Property | Value |
|----------|-------|
| **Current** | `JupiterExecutionAdapter` (simulated), `TransactionPlan` routing through Jupiter |
| **Identity** | `Instrument(venue, symbol)` — venue-neutral |
| **Action** | KEEP + HARDEN |
| **Complexity** | MEDIUM |
| **Effort** | 1-2 sprints |
| **What** | The existing Jupiter execution path is the right architecture. Needs: (a) make it default instead of `paper`, (b) add real on-chain simulation (not the current trivial pass-through), (c) add real price feeds instead of placeholders. |
| **Risk** | Low-medium. Architecture is correct; implementation needs hardening. |

---

### 6. Shadow

| Property | Value |
|----------|-------|
| **Current** | Shadow tracks prediction market positions: `shadow_positions` linked to `research_trades` linked to `solana_wallet_trades` |
| **Identity** | `strategy` + `market_id` |
| **Action** | ADAPT |
| **Complexity** | MEDIUM |
| **Effort** | 1-2 sprints |
| **What** | Shadow system needs to track token positions instead of prediction positions. Entry/exit price semantics are similar (buy low, sell high). PnL calculation is simpler (token price delta vs. prediction outcome binary). |
| **Risk** | Medium — shadow logic is mostly price-based already but the portfolio projector assumes prediction outcomes. |

---

### 7. Evidence

| Property | Value |
|----------|-------|
| **Current** | `PromotionEvidenceSnapshot` with prediction-based metrics (EV, Brier, win_rate) |
| **Identity** | `strategy_id` |
| **Action** | REBUILD |
| **Complexity** | MEDIUM |
| **Effort** | 1 sprint |
| **What** | New evidence model: swap execution quality (slippage, route efficiency, fill rate), token PnL metrics (realized PnL, Sharpe, alpha). Remove Brier score, calibration metrics — replace with price prediction accuracy for alpha models. |
| **Risk** | Low-medium — evidence schema is straightforward. |

---

### 8. Promotion

| Property | Value |
|----------|-------|
| **Current** | Promotion audits prediction accuracy (6 gates: volume, replay parity, EV, Brier, violations, origin) |
| **Identity** | `strategy_id` |
| **Action** | REBUILD |
| **Complexity** | MEDIUM |
| **Effort** | 1-2 sprints |
| **What** | New promotion gates: (a) minimum trades executed, (b) positive PnL, (c) Sharpe > threshold, (d) drawdown limits, (e) execution quality metrics. Remove prediction-specific gates (Brier, calibration). |
| **Risk** | Medium — changes the promotion criteria entirely. Current strategies optimized for prediction accuracy may not pass new gates. |

---

### 9. Reporting

| Property | Value |
|----------|-------|
| **Current** | Prediction accuracy, calibration, replay parity reports |
| **Identity** | `strategy_id` |
| **Action** | ADAPT |
| **Complexity** | LOW |
| **Effort** | 1 sprint |
| **What** | Replace prediction-centric dashboards with token-trading dashboards (PnL curves, Sharpe, drawdown, win rate by token). Most reporting infrastructure is reusable. |
| **Risk** | Low — reporting is a presentation layer. |

---

### 10. Persistence

| Property | Value |
|----------|-------|
| **Current** | 11 Polymarket-owned tables, 3 Solana-owned tables |
| **Identity** | `market_id` (core), `mint_address` (side-car) |
| **Action** | REBUILD |
| **Complexity** | HIGH |
| **Effort** | 2-3 sprints |
| **What** | New schema: `token_pools (pool_id, mint_a, mint_b, dex, liquidity)`, `swap_trades (pool_id, side, amount_in, amount_out, price, slippage, tx_signature)`, `trade_decisions (pool_id, direction, size, entry, stop, take_profit)`. Deprecate `markets`, `exchange_orders` with `clob_*` columns, `fills` with `outcome`. Migrate existing data or archive. |
| **Risk** | High — schema change affects every query, every repository, every report. Historical data loss if not carefully migrated. |

---

## Summary

| Layer | Current Owner | Target Owner | Action | Complexity | Effort |
|-------|--------------|-------------|--------|-----------|--------|
| Ingestion | Polymarket | Solana | REBUILD | HIGH | 2-3 sprints |
| Signals | Polymarket | Solana | REBUILD | VERY HIGH | 3-4 sprints |
| Strategy | Polymarket | Solana | REBUILD | VERY HIGH | 4-6 sprints |
| Decision | Polymarket | Solana | REBUILD | MEDIUM | 1 sprint |
| Execution | Solana (partial) | Solana | KEEP + HARDEN | MEDIUM | 1-2 sprints |
| Shadow | Polymarket | Solana | ADAPT | MEDIUM | 1-2 sprints |
| Evidence | Polymarket | Solana | REBUILD | MEDIUM | 1 sprint |
| Promotion | Polymarket | Solana | REBUILD | MEDIUM | 1-2 sprints |
| Reporting | Polymarket | Solana | ADAPT | LOW | 1 sprint |
| Persistence | Polymarket | Solana | REBUILD | HIGH | 2-3 sprints |

**Total estimated effort: 17-25 sprints (4-6 months with a dedicated team)**

**Risk distribution:**
- 60% of risk is in Strategy + Signals + Ingestion (the cognitive pipeline)
- 25% of risk is in Persistence (data migration)
- 15% of risk is in Execution hardening + everything else
