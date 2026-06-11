# Solana MVP v1 Plan: Research & Shadow Trading (Focused)

## Objective
The primary goal of MVP v1 is to determine whether Smart Wallet tracking on Solana produces a statistically meaningful edge. We are building a research platform to validate alpha before any execution infrastructure is developed.

---

## Architecture Changes

### Data Pipeline
- **Helius Ingester:** Webhook-based ingestion of `onchain_trade` events.
- **Birdeye Enrichment:** API-based enrichment for token prices and metadata.
- **Event Bus:** Normalized Solana events published to `market:data`.

### Agent & Service Logic
- **SmartWalletAgent (fka WhaleAgent):** Refactored to track individual wallet performance metrics (Win Rate, ROI, Activity). Clustering and Sybil detection are **removed**.
- **SignalAgent:** Simplified to output only "Smart Wallet Follow" signals. All technical and experimental strategies are **disabled**.
- **RiskAgent:** Retained to enforce realistic position limits on shadow trades.
- **ShadowPortfolioService:** The centerpiece of MVP v1. Responsible for simulated entry/exit, deterministic PnL tracking, and performance reporting.

---

## Database Changes

### Updated Models

#### SmartWallet
- `address` (PK, string)
- `trades_tracked` (int)
- `win_rate` (float)
- `roi_7d` (float)
- `roi_30d` (float)
- `avg_holding_duration` (interval)
- `avg_trade_size_usd` (float)
- `smart_wallet_score` (float)
- `last_active_at` (datetime)

#### ShadowPosition
- `id` (PK, uuid)
- `mint_address` (string)
- `symbol` (string)
- `entry_timestamp` (datetime)
- `entry_price_usd` (float)
- `exit_timestamp` (datetime, nullable)
- `exit_price_usd` (float, nullable)
- `holding_duration` (interval, nullable)
- `size_usd` (float)
- `pnl_percent` (float, nullable)
- `pnl_usd` (float, nullable)
- `source_wallet_address` (string, FK)
- `source_signal_id` (uuid, FK)
- `status` (string) # open, closed

---

## SmartWalletScore v1

Scoring is transparent and explainable:
`SmartWalletScore = (WinRate * 0.40) + (ROI_Score * 0.35) + (Consistency_Score * 0.15) + (Activity_Score * 0.10)`

---

## Deterministic Exit Rules

To ensure a consistent and reliable dataset for evaluation, the `ShadowPortfolioService` will apply the following rules to every shadow trade:

| Rule | Threshold |
| :--- | :--- |
| **Take Profit** | +25% |
| **Stop Loss** | -15% |
| **Max Holding Time** | 72 hours |

*Trades will be closed automatically upon hitting whichever condition occurs first.*

---

## Success Criteria (Revised)

Validation requires a statistically robust dataset:
- **Minimum Dataset:** 100+ completed shadow trades.

**Success Benchmarks:**
1. **Win Rate:** > 55%
2. **Profit Factor:** > 1.20
3. **Net ROI:** Positive after simulated fees and slippage.
4. **Sharpe Ratio:** Positive and stable.
5. **Wallet Diversification:** No single wallet may contribute > 25% of total profits.

---

## Milestones & Effort

### Milestone 1: Core Data & Models (Effort: 3 days)
- [ ] Helius Webhook listener & Birdeye pricing integration.
- [ ] Deploy `SmartWallet` and `ShadowPosition` models.

### Milestone 2: SmartWallet Scoring (Effort: 3 days)
- [ ] Implement `SmartWalletAgent` metrics calculation (no clustering).
- [ ] Transparent scoring formula implementation.

### Milestone 3: Shadow Tracking (Effort: 4 days)
- [ ] `ShadowPortfolioService` with deterministic exit logic.
- [ ] Performance dashboard for shadow trade analytics.

### Milestone 4: Alpha Observation (Effort: 2-4 weeks)
- [ ] Accumulate 100+ shadow trades.
- [ ] Statistical analysis of Go/No-Go for Phase 2.

**Total Estimated Engineering Effort:** 2 weeks.

---

## Deferred Until Phase 2
- Wallet clustering and Sybil detection.
- Jupiter/Jito execution infrastructure.
- Solana Signer and Priority Fee logic.
- Live capital deployment.
